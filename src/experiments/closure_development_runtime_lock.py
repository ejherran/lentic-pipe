#!/usr/bin/env python
"""Build and validate the external Closure V1 E0-DL implementation lock.

This module is outcome-free.  It hashes bytes, inspects Git and DVC pointer
metadata, validates the closed runtime contract, and semantically audits only
the deterministic pre-2022 expert-state Parquet.  It never reads scientific
outcome rows, trains a model, emits predictions, or authorizes E0-U.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    load_yaml_mapping,
    validate_json_schema,
)
from src.experiments.closure_runtime_contract import (
    configure_torch_cpu_execution_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_CONFIG = Path("configs/closure_v1/development_runtime.yaml")
DEFAULT_RUNTIME_SCHEMA = Path("configs/closure_v1/development_runtime.schema.json")
DEFAULT_LOCK_SCHEMA = Path("configs/closure_v1/development_runtime_lock.schema.json")
DEFAULT_LOCK_PATH = Path("reports/closure_v1/00_protocol/development_runtime_lock.json")

LOCK_VERSION = "closure_development_runtime_lock_v1"
EXPECTED_GATE = "E0-DL"
EXPECTED_EXPERIMENT_ID = "closure_v1"
EXPECTED_RUNTIME_STATUS = "ready_to_lock"
EXPECTED_PATH_COUNT = 201
EXPECTED_PATH_DIGEST = "833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c"
EXPECTED_AUTHORIZATIONS = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
}
EXPECTED_SEALS = {
    "future_outcomes_accessed": False,
    "post_2021_outcome_semantic_decode": False,
    "lock_generation_semantically_audits_expert_state_rows": True,
    "lock_generation_reads_scientific_outcome_rows": False,
    "lock_generation_reads_post_2021_outcomes": False,
    "does_not_replace_e0_m_model_lock": True,
    "external_lock_bundle_committed_before_fit": True,
}
TYPE_CHECK_COMMAND = ("poetry", "run", "ty", "check")
PACKAGE_DISTRIBUTIONS = (
    "numpy",
    "pandas",
    "pyarrow",
    "torch",
    "PyYAML",
    "scikit-learn",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CANONICAL_ORIGIN_IDENTITY_SHA256 = (
    "475fdf8ad6839d3d291010ff999b4e4c0f8604a0e8d8a09fcebe5ccb843d1905"
)
CANONICAL_ORIGIN_IDENTITY_ALGORITHM = "git_remote_host_path_v1_sha256_utf8"
DVC_REMOTE_VERIFICATION_METHOD = "two_targeted_idempotent_pushes_v1"
DVC_PUSH_RESULT_UP_TO_DATE = "everything_up_to_date"
DVC_REMOTE_ENVIRONMENT = {
    "LC_ALL": "C",
    "LANG": "C",
    "DVC_NO_ANALYTICS": "1",
}
OPAQUE_DVC_PARENT_ROLES = frozenset(
    {"common_origin", "expert_state", "restored_panel", "restored_expert_anchor"}
)
EXPERT_FILE_RECORD_KEYS = frozenset({"path", "role", "bytes", "sha256"})
EXPERT_COMPLETION_KEYS = frozenset(
    {
        "manifest_version",
        "status",
        "generated_at_utc",
        "experiment_id",
        "surface_id",
        "model_id",
        "artifact_role",
        "future_outcomes_accessed",
        "post_2021_outcomes_materialized",
        "zero_holdout_overlap",
        "evaluation_authorized",
        "e0_u_authorized",
        "runtime",
        "state_mapping",
        "source_projection",
        "output_allowlist",
        "time_roles",
        "source_repository",
        "counts",
        "script",
        "inputs",
        "dependencies",
        "completion_marker_written_last",
        "outputs",
    }
)
EXPERT_LINEAGE_KEYS = frozenset(
    {
        "audit_version",
        "status",
        "experiment_id",
        "surface_id",
        "future_outcomes_accessed",
        "post_2021_outcomes_materialized",
        "e0_u_authorized",
        "checks",
        "source_projection",
        "output_allowlist",
        "rows",
        "locations",
        "minimum_year_month",
        "maximum_year_month",
        "role_counts",
        "delta_previous_month_missing_count",
        "scan",
        "zero_holdout_overlap",
        "zero_unknown_assignment_overlap",
        "full_current_chla_sibling_columns",
        "optional_context_columns",
        "delta_geometry",
    }
)
EXPERT_LINEAGE_CHECK_KEYS = frozenset(
    {
        "exact_raw_projection",
        "locked_development_key_membership",
        "zero_holdout_overlap",
        "zero_unknown_assignment_overlap",
        "exact_state_mapping",
        "no_current_chla_state_allowlist",
        "one_month_delta_geometry",
        "no_optional_context_columns",
        "no_post_2021_materialization",
    }
)
EXPERT_LINEAGE_SCAN_KEYS = frozenset(
    {"materialized_rows", "returned_rows", "boundary_crossing_rows", "role_counts"}
)


class DevelopmentRuntimeLockError(ClosureContractError):
    """Raised when the E0-DL lock or one of its physical parents drifts."""


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    *,
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise DevelopmentRuntimeLockError(f"{context} keys drifted from the exact dialect")
    return value


def _exact_value_matches(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return observed is expected
    if isinstance(expected, Mapping):
        return (
            isinstance(observed, Mapping)
            and set(observed) == set(expected)
            and all(
                _exact_value_matches(observed[key], expected_value)
                for key, expected_value in expected.items()
            )
        )
    if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)):
        return (
            isinstance(observed, Sequence)
            and not isinstance(observed, (str, bytes))
            and len(observed) == len(expected)
            and all(
                _exact_value_matches(observed_value, expected_value)
                for observed_value, expected_value in zip(observed, expected, strict=True)
            )
        )
    return observed == expected


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def canonical_git_remote_identity(raw_url: str) -> str:
    """Normalize supported Git URLs to a credential-free ``host/path``."""
    if (
        not isinstance(raw_url, str)
        or not raw_url
        or raw_url != raw_url.strip()
        or any(character.isspace() or ord(character) < 32 for character in raw_url)
    ):
        raise DevelopmentRuntimeLockError("Canonical Git remote URL is malformed")

    host: str
    path: str
    if "://" in raw_url:
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"https", "ssh"}:
            raise DevelopmentRuntimeLockError("Canonical Git remote scheme is forbidden")
        try:
            parsed_port = parsed.port
        except ValueError as exc:
            raise DevelopmentRuntimeLockError(
                "Canonical Git remote port is malformed"
            ) from exc
        if parsed.query or parsed.fragment or parsed_port is not None:
            raise DevelopmentRuntimeLockError("Canonical Git remote modifiers are forbidden")
        if parsed.password is not None or (parsed.scheme == "https" and parsed.username is not None):
            raise DevelopmentRuntimeLockError("Canonical Git remote credentials are forbidden")
        if parsed.hostname is None:
            raise DevelopmentRuntimeLockError("Canonical Git remote host is missing")
        host = parsed.hostname.lower()
        path = parsed.path.lstrip("/")
    else:
        match = re.fullmatch(
            r"(?:(?P<user>[A-Za-z0-9._-]+)@)?(?P<host>[A-Za-z0-9.-]+):(?P<path>[^?#]+)",
            raw_url,
        )
        if match is None:
            raise DevelopmentRuntimeLockError("Canonical Git remote must be HTTPS, SSH, or SCP")
        host = str(match.group("host")).lower()
        path = str(match.group("path"))

    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4].rstrip("/")
    if (
        not host
        or host.startswith(".")
        or host.endswith(".")
        or ".." in host
        or not path
        or path.startswith("/")
        or "//" in path
        or "\\" in path
        or "%" in path
    ):
        raise DevelopmentRuntimeLockError("Canonical Git remote host/path is malformed")
    segments = path.split("/")
    if not path or any(segment in {"", ".", ".."} for segment in segments):
        raise DevelopmentRuntimeLockError("Canonical Git remote path is malformed")
    return f"{host}/{path}"


def canonical_origin_identity(runtime: Mapping[str, Any]) -> dict[str, Any]:
    """Verify every configured fetch and push URL without retaining raw URLs."""
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    policy = implementation.get("canonical_origin_identity")
    if not isinstance(policy, Mapping):
        raise DevelopmentRuntimeLockError("canonical_origin_identity policy is missing")
    remote_name = policy.get("remote_name")
    expected_digest = policy.get("expected_identity_sha256")
    if remote_name != "origin" or expected_digest != EXPECTED_CANONICAL_ORIGIN_IDENTITY_SHA256:
        raise DevelopmentRuntimeLockError("Canonical origin identity policy drifted")

    def configured_urls(*extra: str) -> list[str]:
        result = subprocess.run(
            ["git", "remote", "get-url", *extra, "origin"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        urls = [line for line in result.stdout.splitlines() if line]
        if result.returncode != 0 or not urls:
            raise DevelopmentRuntimeLockError("Canonical origin URL set cannot be verified")
        return urls

    fetch_urls = configured_urls("--all")
    push_urls = configured_urls("--push", "--all")
    identities = [canonical_git_remote_identity(url) for url in [*fetch_urls, *push_urls]]
    digests = [hashlib.sha256(identity.encode("utf-8")).hexdigest() for identity in identities]
    if any(digest != expected_digest for digest in digests):
        raise DevelopmentRuntimeLockError("Canonical origin identity differs from the locked digest")
    return {
        "remote_name": "origin",
        "identity_algorithm": CANONICAL_ORIGIN_IDENTITY_ALGORITHM,
        "identity_sha256": expected_digest,
        "fetch_url_count": len(fetch_urls),
        "push_url_count": len(push_urls),
        "fetch_push_identity_equal": True,
    }


def locked_parent_publication_identity(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    """Bind H to local origin/main and, for real locking, the live remote."""
    head = _git("rev-parse", "HEAD")
    tracking_oid = _git("rev-parse", "origin/main")
    if (
        GIT_COMMIT_PATTERN.fullmatch(head) is None
        or GIT_COMMIT_PATTERN.fullmatch(tracking_oid) is None
        or head != tracking_oid
    ):
        raise DevelopmentRuntimeLockError(
            "E0-DL parent HEAD is not the published local origin/main"
        )
    remote_oid: str | None = None
    if verify_remote:
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DevelopmentRuntimeLockError(
                "E0-DL parent live remote publication cannot be verified"
            ) from exc
        rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
        if (
            result.returncode != 0
            or len(rows) != 1
            or len(rows[0]) != 2
            or rows[0][1] != "refs/heads/main"
            or GIT_COMMIT_PATTERN.fullmatch(rows[0][0]) is None
        ):
            raise DevelopmentRuntimeLockError(
                "E0-DL parent live remote publication cannot be verified"
            )
        remote_oid = rows[0][0]
        if remote_oid != head:
            raise DevelopmentRuntimeLockError(
                "E0-DL parent live remote main differs from HEAD"
            )
    return {
        "head": head,
        "tracking_ref": "origin/main",
        "tracking_oid": tracking_oid,
        "local_tracking_verified": True,
        "remote_ref": "refs/heads/main",
        "remote_oid": remote_oid,
        "remote_verified": verify_remote,
    }


def clean_published_repository_identity(
    runtime: Mapping[str, Any],
    *,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Require a clean committed HEAD already published as canonical origin/main."""
    state = _require_clean_repository()
    canonical_origin = canonical_origin_identity(runtime)
    publication = locked_parent_publication_identity(verify_remote=verify_remote)
    if publication["head"] != state["head"]:
        raise DevelopmentRuntimeLockError(
            "Clean repository HEAD differs from publication evidence"
        )
    return {
        "head": state["head"],
        "branch": state["branch"],
        "worktree_status_at_start": "clean",
        "canonical_origin": canonical_origin,
        "publication": publication,
    }


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimeLockError(f"Path escapes the repository: {path}") from exc
    return resolved


def _repository_relative(path: str | Path) -> str:
    resolved = _resolve_repo_path(path)
    return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()


def _canonical_repo_path(path: str | Path) -> str:
    raw = Path(path)
    canonical = raw.as_posix()
    if raw.is_absolute() or canonical != str(path) or ".." in raw.parts or "." in raw.parts:
        raise DevelopmentRuntimeLockError(f"Path is not canonical repository-relative: {path}")
    return _repository_relative(raw)


def file_record(path: str | Path, *, role: str) -> dict[str, Any]:
    """Return a physical SHA-256 record without interpreting file contents."""
    if not role:
        raise DevelopmentRuntimeLockError("File-record role must be non-empty")
    relative = _canonical_repo_path(path)
    resolved = _resolve_repo_path(relative)
    if not resolved.is_file():
        raise DevelopmentRuntimeLockError(f"Required E0-DL file is missing: {relative}")
    return {
        "path": relative,
        "role": role,
        "bytes": resolved.stat().st_size,
        "sha256": _sha256_file(resolved),
    }


def opaque_file_record(path: str | Path, *, role: str) -> dict[str, Any]:
    record = file_record(path, role=role)
    record["semantic_decode"] = False
    return record


def repository_state() -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    return {
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current") or "detached",
        "worktree_status": "clean" if not status else "dirty",
        "dirty_paths": status.splitlines(),
    }


def _require_clean_repository() -> dict[str, Any]:
    state = repository_state()
    if state["worktree_status"] != "clean" or state["dirty_paths"] != []:
        raise DevelopmentRuntimeLockError(
            "E0-DL generation requires a fully clean committed HEAD"
        )
    if not GIT_COMMIT_PATTERN.fullmatch(str(state["head"])):
        raise DevelopmentRuntimeLockError("Current Git HEAD is not a full SHA-1 commit")
    return state


def _require_tracked(path: str | Path) -> str:
    relative = _canonical_repo_path(path)
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DevelopmentRuntimeLockError(
            f"E0-DL component must be Git-tracked: {relative}"
        )
    return relative


def _require_unmodified(path: str | Path) -> str:
    relative = _require_tracked(path)
    status = _git("status", "--porcelain", "--untracked-files=all", "--", relative)
    if status:
        raise DevelopmentRuntimeLockError(f"E0-DL path is modified: {status}")
    return relative


def _validated_file_record_metadata(
    record: Mapping[str, Any],
    *,
    context: str,
) -> tuple[str, int, str]:
    """Validate one lock record without requiring its payload to be restored."""
    path = record.get("path")
    role = record.get("role")
    expected_bytes = record.get("bytes")
    expected_sha256 = record.get("sha256")
    if not isinstance(path, str) or not path:
        raise DevelopmentRuntimeLockError(f"{context}.path must be non-empty")
    if not isinstance(role, str) or not role:
        raise DevelopmentRuntimeLockError(f"{context}.role must be non-empty")
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise DevelopmentRuntimeLockError(f"{context}.bytes must be a non-negative integer")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        raise DevelopmentRuntimeLockError(f"{context}.sha256 must be a SHA-256 digest")
    relative = _canonical_repo_path(path)
    return relative, expected_bytes, expected_sha256


def _record_matches_physical(record: Mapping[str, Any], *, context: str) -> None:
    relative, expected_bytes, expected_sha256 = _validated_file_record_metadata(
        record,
        context=context,
    )
    resolved = _resolve_repo_path(relative)
    if not resolved.is_file():
        raise DevelopmentRuntimeLockError(f"{context} file is missing: {relative}")
    if resolved.stat().st_size != expected_bytes:
        raise DevelopmentRuntimeLockError(f"{context} byte count drifted: {relative}")
    if _sha256_file(resolved) != expected_sha256:
        raise DevelopmentRuntimeLockError(f"{context} SHA-256 drifted: {relative}")


def _records_by_path(records: Sequence[Any], *, context: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise DevelopmentRuntimeLockError(f"{context}[{index}] must be an object")
        path = raw_record.get("path")
        if not isinstance(path, str):
            raise DevelopmentRuntimeLockError(f"{context}[{index}].path must be a string")
        canonical = _canonical_repo_path(path)
        if canonical in indexed:
            raise DevelopmentRuntimeLockError(f"{context} contains duplicate path: {canonical}")
        indexed[canonical] = raw_record
    return indexed


def _component_mapping(runtime: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    lock = runtime.get("implementation_lock")
    if not isinstance(lock, Mapping):
        raise DevelopmentRuntimeLockError("development_runtime.implementation_lock is missing")
    raw_mapping = lock.get("required_component_paths")
    if not isinstance(raw_mapping, Mapping) or not raw_mapping:
        raise DevelopmentRuntimeLockError(
            "implementation_lock.required_component_paths must bind every role to exact paths"
        )
    raw_roles = lock.get("required_component_roles")
    if not isinstance(raw_roles, Sequence) or isinstance(raw_roles, (str, bytes)):
        raise DevelopmentRuntimeLockError("implementation_lock.required_component_roles is invalid")
    roles = tuple(str(role) for role in raw_roles)
    if set(raw_mapping) != set(roles):
        raise DevelopmentRuntimeLockError(
            "required_component_paths keys must exactly match required_component_roles"
        )
    normalized: dict[str, tuple[str, ...]] = {}
    seen_paths: dict[str, str] = {}
    for role in roles:
        raw_paths = raw_mapping[role]
        if isinstance(raw_paths, str):
            values = (raw_paths,)
        elif isinstance(raw_paths, Sequence) and not isinstance(raw_paths, (str, bytes)):
            values = tuple(str(value) for value in raw_paths)
        else:
            raise DevelopmentRuntimeLockError(
                f"required_component_paths.{role} must be a path or path list"
            )
        if not values:
            raise DevelopmentRuntimeLockError(f"Component role has no paths: {role}")
        canonical_values: list[str] = []
        for value in values:
            canonical = _canonical_repo_path(value)
            previous_role = seen_paths.get(canonical)
            if previous_role is not None and previous_role != role:
                raise DevelopmentRuntimeLockError(
                    f"Component path {canonical} is assigned to both {previous_role} and {role}"
                )
            seen_paths[canonical] = role
            canonical_values.append(canonical)
        normalized[role] = tuple(canonical_values)
    configured_locker = lock.get("locker_path")
    locker_paths = normalized.get("runtime_locker", ())
    if not isinstance(configured_locker, str) or configured_locker not in locker_paths:
        raise DevelopmentRuntimeLockError(
            "runtime_locker must bind the configured implementation_lock.locker_path"
        )
    return normalized


def component_records(runtime: Mapping[str, Any]) -> list[dict[str, Any]]:
    mapping = _component_mapping(runtime)
    records: list[dict[str, Any]] = []
    for role, paths in mapping.items():
        for path in paths:
            _require_tracked(path)
            records.append(file_record(path, role=role))
    return sorted(records, key=lambda record: (str(record["path"]), str(record["role"])))


def _module_file_candidates(module_parts: Sequence[str]) -> list[Path]:
    if not module_parts or module_parts[0] != "src":
        return []
    base = PROJECT_ROOT.joinpath(*module_parts)
    candidates = [base.with_suffix(".py"), base / "__init__.py"]
    return [candidate for candidate in candidates if candidate.is_file()]


def _package_init_paths(module_parts: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    for index in range(1, len(module_parts)):
        candidate = PROJECT_ROOT.joinpath(*module_parts[:index]) / "__init__.py"
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _imported_local_paths(path: Path) -> set[Path]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise DevelopmentRuntimeLockError(f"Cannot parse local dependency {path}: {exc}") from exc
    relative_parts = list(path.relative_to(PROJECT_ROOT).with_suffix("").parts)
    current_package = relative_parts[:-1]
    if relative_parts[-1] == "__init__":
        current_package = relative_parts[:-1]
    imported: set[Path] = set()

    def add_module(parts: Sequence[str]) -> None:
        for candidate in [*_package_init_paths(parts), *_module_file_candidates(parts)]:
            imported.add(candidate.resolve())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                add_module(parts)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(current_package) - (node.level - 1)
                if keep < 0:
                    continue
                base_parts = current_package[:keep]
                if node.module:
                    base_parts = [*base_parts, *node.module.split(".")]
            elif node.module:
                base_parts = node.module.split(".")
            else:
                continue
            add_module(base_parts)
            for alias in node.names:
                if alias.name != "*":
                    add_module([*base_parts, *alias.name.split(".")])
    return imported


def recursive_runtime_dependency_paths(runtime: Mapping[str, Any]) -> list[str]:
    mapping = _component_mapping(runtime)
    lock = cast(Mapping[str, Any], runtime["implementation_lock"])
    raw_legacy = lock.get("required_legacy_dependency_paths")
    if not isinstance(raw_legacy, Sequence) or isinstance(raw_legacy, (str, bytes)):
        raise DevelopmentRuntimeLockError("required_legacy_dependency_paths is invalid")
    root_paths = {
        _resolve_repo_path(path)
        for role, paths in mapping.items()
        if role not in {"relevant_tests", "pyproject", "poetry_lock"}
        for path in paths
        if path.endswith(".py")
    }
    required_legacy = {_resolve_repo_path(str(path)) for path in raw_legacy}
    for path in required_legacy:
        if not path.is_file():
            raise DevelopmentRuntimeLockError(
                f"Required legacy runtime dependency is missing: {_repository_relative(path)}"
            )
    pending = sorted(root_paths | required_legacy, key=lambda item: item.as_posix())
    closure: set[Path] = set()
    while pending:
        path = pending.pop(0).resolve()
        if path in closure:
            continue
        closure.add(path)
        for imported in sorted(_imported_local_paths(path), key=lambda item: item.as_posix()):
            if imported not in closure:
                pending.append(imported)
    missing_legacy = required_legacy.difference(closure)
    if missing_legacy:
        raise DevelopmentRuntimeLockError(
            "Recursive dependency closure omitted required legacy paths: "
            f"{sorted(_repository_relative(path) for path in missing_legacy)}"
        )
    return sorted((_repository_relative(path) for path in closure), key=lambda value: value.encode("utf-8"))


def runtime_dependency_records(runtime: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in recursive_runtime_dependency_paths(runtime):
        _require_tracked(path)
        records.append(file_record(path, role="runtime_transitive_dependency"))
    return records


def _find_protocol_source_record(protocol_lock: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    records = protocol_lock.get("source_artifacts")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise DevelopmentRuntimeLockError("Protocol lock has no source_artifacts")
    matches = [record for record in records if isinstance(record, Mapping) and record.get("path") == path]
    if len(matches) != 1:
        raise DevelopmentRuntimeLockError(f"Protocol lock must contain one source record for {path}")
    return matches[0]


def restored_development_source_records(runtime: Mapping[str, Any]) -> list[dict[str, Any]]:
    authority = runtime.get("authority")
    anfis = runtime.get("anfis")
    if not isinstance(authority, Mapping) or not isinstance(anfis, Mapping):
        raise DevelopmentRuntimeLockError("Runtime authority/ANFIS sections are missing")
    projection = anfis.get("source_projection")
    if not isinstance(projection, Mapping):
        raise DevelopmentRuntimeLockError("anfis.source_projection is missing")
    protocol_path = str(authority.get("protocol_lock_path", ""))
    protocol_lock = load_json_mapping(protocol_path)
    panel_path = str(projection.get("panel_path", ""))
    expert_path = str(projection.get("expert_anchor_path", ""))
    protocol_panel = _find_protocol_source_record(protocol_lock, panel_path)
    expected_panel_hash = protocol_panel.get("sha256")
    expected_expert_hash = projection.get("expert_anchor_sha256")
    records = [
        opaque_file_record(panel_path, role="restored_monthly_panel_source"),
        opaque_file_record(expert_path, role="restored_expert_anchor_source"),
    ]
    if records[0]["sha256"] != expected_panel_hash:
        raise DevelopmentRuntimeLockError("Restored panel SHA-256 does not match the protocol lock")
    if records[1]["sha256"] != expected_expert_hash:
        raise DevelopmentRuntimeLockError("Restored expert anchor SHA-256 does not match runtime contract")
    return records


def _validate_restored_source_lock_metadata(
    observed: Sequence[Any],
    runtime: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate locked source hashes without requiring DVC payload restoration."""
    authority = runtime.get("authority")
    anfis = runtime.get("anfis")
    if not isinstance(authority, Mapping) or not isinstance(anfis, Mapping):
        raise DevelopmentRuntimeLockError("Runtime authority/ANFIS sections are missing")
    projection = anfis.get("source_projection")
    if not isinstance(projection, Mapping):
        raise DevelopmentRuntimeLockError("anfis.source_projection is missing")
    protocol_lock = load_json_mapping(str(authority.get("protocol_lock_path", "")))
    panel_path = str(projection.get("panel_path", ""))
    expert_path = str(projection.get("expert_anchor_path", ""))
    panel_source = _find_protocol_source_record(protocol_lock, panel_path)
    observed_by_path = _records_by_path(observed, context="restored_development_sources")
    if set(observed_by_path) != {panel_path, expert_path}:
        raise DevelopmentRuntimeLockError(
            "Restored development-source paths drifted from the runtime contract"
        )
    expected = {
        panel_path: {
            "role": "restored_monthly_panel_source",
            "bytes": panel_source.get("bytes"),
            "sha256": panel_source.get("sha256"),
        },
        expert_path: {
            "role": "restored_expert_anchor_source",
            "sha256": projection.get("expert_anchor_sha256"),
        },
    }
    normalized: list[dict[str, Any]] = []
    for path in (panel_path, expert_path):
        record = observed_by_path[path]
        _validated_file_record_metadata(
            record,
            context=f"restored_development_sources.{path}",
        )
        if record.get("semantic_decode") is not False:
            raise DevelopmentRuntimeLockError(
                f"Restored development source must remain byte-opaque: {path}"
            )
        for field, value in expected[path].items():
            if record.get(field) != value:
                raise DevelopmentRuntimeLockError(
                    f"Restored development-source {field} drifted: {path}"
                )
        normalized.append(dict(record))
    return normalized


def _load_dvc_pointer_metadata(artifact_path: str | Path) -> dict[str, Any]:
    """Validate a tracked explicit pointer without opening its DVC payload."""
    artifact_relative = _canonical_repo_path(artifact_path)
    pointer_relative = f"{artifact_relative}.dvc"
    pointer = _resolve_repo_path(pointer_relative)
    if not pointer.is_file():
        raise DevelopmentRuntimeLockError(f"Explicit DVC pointer is missing: {pointer_relative}")
    _require_tracked(pointer_relative)
    payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or not isinstance(payload.get("outs"), list):
        raise DevelopmentRuntimeLockError(f"Malformed DVC pointer: {pointer_relative}")
    outputs = payload["outs"]
    if len(outputs) != 1 or not isinstance(outputs[0], Mapping):
        raise DevelopmentRuntimeLockError(f"DVC pointer must contain exactly one output: {pointer_relative}")
    output = cast(Mapping[str, Any], outputs[0])
    if output.get("path") != Path(artifact_relative).name:
        raise DevelopmentRuntimeLockError(f"DVC pointer output path drifted: {pointer_relative}")
    hash_name = str(output.get("hash", "md5"))
    hash_value = output.get(hash_name, output.get("md5"))
    size = output.get("size")
    if (
        hash_name != "md5"
        or not isinstance(hash_value, str)
        or re.fullmatch(r"[0-9a-f]{32}", hash_value) is None
    ):
        raise DevelopmentRuntimeLockError(f"E0-DL explicit pointer must use a file MD5: {pointer_relative}")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise DevelopmentRuntimeLockError(f"DVC pointer size is invalid: {pointer_relative}")
    return {
        "pointer_path": pointer_relative,
        "pointer_bytes": pointer.stat().st_size,
        "pointer_sha256": _sha256_file(pointer),
        "owner_strategy": "explicit_pointer",
        "hash_name": hash_name,
        "hash_value": hash_value,
        "size": size,
        "pointer_metadata_verified": True,
    }


def _load_dvc_pointer_for_file(artifact_path: str | Path) -> dict[str, Any]:
    artifact_relative = _canonical_repo_path(artifact_path)
    artifact = _resolve_repo_path(artifact_relative)
    if not artifact.is_file():
        raise DevelopmentRuntimeLockError(f"Materialized DVC artifact is missing: {artifact_relative}")
    record = _load_dvc_pointer_metadata(artifact_relative)
    if record["size"] != artifact.stat().st_size:
        raise DevelopmentRuntimeLockError(
            f"DVC pointer size drifted: {record['pointer_path']}"
        )
    if _md5_file(artifact) != record["hash_value"]:
        raise DevelopmentRuntimeLockError(
            f"DVC pointer content hash drifted: {record['pointer_path']}"
        )
    record["payload_verified_at_lock"] = True
    return record


def _dvc_remote_configuration_fingerprint(remote_name: str) -> dict[str, str]:
    """Read only the selected remote name/URL and retain no raw URL."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", remote_name):
        raise DevelopmentRuntimeLockError("DVC remote name is invalid")
    values: dict[tuple[str, str], str] = {}
    for config_path in (PROJECT_ROOT / ".dvc/config", PROJECT_ROOT / ".dvc/config.local"):
        if not config_path.is_file():
            continue
        section = ""
        for raw_line in config_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                raw_section = line[1:-1].strip()
                remote_match = re.search(
                    r"remote\s+[\"'](?P<name>[^\"']+)[\"']",
                    raw_section,
                )
                section = (
                    f'remote "{remote_match.group("name")}"'
                    if remote_match is not None
                    else raw_section.strip("'\"")
                )
                continue
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            values[(section, key.strip())] = raw_value.strip().strip("'\"")
    remote_section = f'remote "{remote_name}"'
    url = values.get((remote_section, "url"))
    if (
        not isinstance(url, str)
        or not url
        or any(character.isspace() or ord(character) < 32 for character in url)
    ):
        raise DevelopmentRuntimeLockError("Selected DVC remote URL cannot be fingerprinted")
    return {
        "remote_name": remote_name,
        "remote_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
    }


def _dvc_remote_name(runtime: Mapping[str, Any]) -> str:
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    remote_name = implementation.get("dvc_remote_name")
    if remote_name != "gcsremote":
        raise DevelopmentRuntimeLockError("E0-DL DVC remote name drifted")
    return str(remote_name)


def dvc_remote_push_command(
    runtime: Mapping[str, Any],
    common_origin: Mapping[str, Any],
    expert_state: Mapping[str, Any],
) -> tuple[str, ...]:
    pointers: list[str] = []
    for context, artifact in (("common_origin", common_origin), ("expert_state", expert_state)):
        dvc = artifact.get("dvc")
        if not isinstance(dvc, Mapping):
            raise DevelopmentRuntimeLockError(f"{context} DVC metadata is missing")
        pointer_path = dvc.get("pointer_path")
        if not isinstance(pointer_path, str):
            raise DevelopmentRuntimeLockError(f"{context} pointer path is missing")
        pointers.append(_canonical_repo_path(pointer_path))
    return (
        "poetry",
        "run",
        "dvc",
        "push",
        "-j",
        "1",
        "-r",
        _dvc_remote_name(runtime),
        *pointers,
    )


def _normalized_dvc_push_result(stdout: bytes, stderr: bytes, returncode: int) -> str:
    if returncode != 0:
        return "failed"
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text).lower()
    if re.search(r"\b(?:file|files) pushed\b", text):
        return "objects_uploaded"
    if "everything is up to date" in text:
        return DVC_PUSH_RESULT_UP_TO_DATE
    return "unexpected_success_output"


def verify_dvc_remote_by_idempotent_push(
    runtime: Mapping[str, Any],
    common_origin: Mapping[str, Any],
    expert_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Run two exact targeted pushes and accept only an already-synced state."""
    command = dvc_remote_push_command(runtime, common_origin, expert_state)
    environment = os.environ.copy()
    environment.update(DVC_REMOTE_ENVIRONMENT)
    attempts: list[dict[str, Any]] = []
    for attempt in (1, 2):
        try:
            result = subprocess.run(
                list(command),
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=False,
                env=environment,
                timeout=600,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DevelopmentRuntimeLockError(
                "Targeted DVC remote verification could not complete"
            ) from exc
        attempts.append(
            {
                "attempt": attempt,
                "exit_code": result.returncode,
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                "normalized_result": _normalized_dvc_push_result(
                    result.stdout,
                    result.stderr,
                    result.returncode,
                ),
            }
        )

    targets: list[dict[str, Any]] = []
    for role, artifact in (("common_origin", common_origin), ("expert_state", expert_state)):
        dvc = cast(Mapping[str, Any], artifact["dvc"])
        targets.append(
            {
                "artifact_role": role,
                "pointer_path": dvc["pointer_path"],
                "pointer_sha256": dvc["pointer_sha256"],
                "hash_name": dvc["hash_name"],
                "hash_value": dvc["hash_value"],
                "size": dvc["size"],
            }
        )
    fingerprint = _dvc_remote_configuration_fingerprint(_dvc_remote_name(runtime))
    evidence = {
        "method": DVC_REMOTE_VERIFICATION_METHOD,
        "command": list(command),
        "environment": dict(DVC_REMOTE_ENVIRONMENT),
        **fingerprint,
        "targets": targets,
        "attempts": attempts,
        "dvc_remote_verified_at_lock": all(
            attempt["exit_code"] == 0
            and attempt["normalized_result"] == DVC_PUSH_RESULT_UP_TO_DATE
            for attempt in attempts
        ),
    }
    if evidence["dvc_remote_verified_at_lock"] is not True:
        raise DevelopmentRuntimeLockError(
            "E0-DL requires two already-up-to-date targeted DVC pushes; rerun after synchronization"
        )
    return evidence


def validate_dvc_remote_verification_evidence(
    evidence: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    common_origin: Mapping[str, Any],
    expert_state: Mapping[str, Any],
    verify_current_remote_config: bool,
) -> None:
    """Cross-bind locked DVC evidence to both explicit pointer identities."""
    expected_command = list(dvc_remote_push_command(runtime, common_origin, expert_state))
    if evidence.get("method") != DVC_REMOTE_VERIFICATION_METHOD:
        raise DevelopmentRuntimeLockError("E0-DL DVC verification method drifted")
    if evidence.get("command") != expected_command:
        raise DevelopmentRuntimeLockError("E0-DL targeted DVC push command drifted")
    if evidence.get("environment") != DVC_REMOTE_ENVIRONMENT:
        raise DevelopmentRuntimeLockError("E0-DL DVC verification environment drifted")
    if evidence.get("remote_name") != _dvc_remote_name(runtime):
        raise DevelopmentRuntimeLockError("E0-DL DVC remote name drifted")
    remote_url_sha256 = evidence.get("remote_url_sha256")
    if not isinstance(remote_url_sha256, str) or SHA256_PATTERN.fullmatch(remote_url_sha256) is None:
        raise DevelopmentRuntimeLockError("E0-DL DVC remote URL fingerprint is invalid")
    if verify_current_remote_config:
        current = _dvc_remote_configuration_fingerprint(_dvc_remote_name(runtime))
        if dict(current) != {
            "remote_name": evidence.get("remote_name"),
            "remote_url_sha256": remote_url_sha256,
        }:
            raise DevelopmentRuntimeLockError("Current DVC remote fingerprint differs from E0-DL")

    expected_targets = []
    for role, artifact in (("common_origin", common_origin), ("expert_state", expert_state)):
        dvc = cast(Mapping[str, Any], artifact["dvc"])
        expected_targets.append(
            {
                "artifact_role": role,
                "pointer_path": dvc["pointer_path"],
                "pointer_sha256": dvc["pointer_sha256"],
                "hash_name": dvc["hash_name"],
                "hash_value": dvc["hash_value"],
                "size": dvc["size"],
            }
        )
    if evidence.get("targets") != expected_targets:
        raise DevelopmentRuntimeLockError("E0-DL DVC target pointer identities drifted")
    attempts = evidence.get("attempts")
    if (
        not isinstance(attempts, Sequence)
        or isinstance(attempts, (str, bytes))
        or len(attempts) != 2
    ):
        raise DevelopmentRuntimeLockError("E0-DL requires exactly two DVC push attempts")
    for index, raw_attempt in enumerate(attempts, start=1):
        if not isinstance(raw_attempt, Mapping):
            raise DevelopmentRuntimeLockError("E0-DL DVC push evidence is not idempotent")
        attempt = cast(Mapping[str, Any], raw_attempt)
        if (
            attempt.get("attempt") != index
            or attempt.get("exit_code") != 0
            or attempt.get("normalized_result") != DVC_PUSH_RESULT_UP_TO_DATE
            or not isinstance(attempt.get("stdout_sha256"), str)
            or SHA256_PATTERN.fullmatch(str(attempt.get("stdout_sha256"))) is None
            or not isinstance(attempt.get("stderr_sha256"), str)
            or SHA256_PATTERN.fullmatch(str(attempt.get("stderr_sha256"))) is None
        ):
            raise DevelopmentRuntimeLockError("E0-DL DVC push evidence is not idempotent")
    if evidence.get("dvc_remote_verified_at_lock") is not True:
        raise DevelopmentRuntimeLockError("E0-DL DVC remote evidence is not verified")


def _completion_output_record(payload: Mapping[str, Any], *, expected_path: str) -> Mapping[str, Any]:
    raw_output = payload.get("output")
    if isinstance(raw_output, Mapping):
        records: Sequence[Any] = [raw_output]
    else:
        raw_outputs = payload.get("outputs")
        records = list(raw_outputs) if isinstance(raw_outputs, Sequence) and not isinstance(raw_outputs, (str, bytes)) else []
    matches: list[Mapping[str, Any]] = []
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            continue
        record = cast(Mapping[str, Any], raw_record)
        if record.get("path") == expected_path:
            matches.append(record)
    if len(matches) != 1:
        raise DevelopmentRuntimeLockError(
            f"Completion manifest must bind exactly one output record for {expected_path}"
        )
    return matches[0]


def _completion_artifact_record(
    payload: Mapping[str, Any],
    *,
    expected_path: str,
    role: str,
    context: str,
    require_physical_artifact: bool,
    expected_output_role: str | None = None,
) -> dict[str, Any]:
    output = _completion_output_record(payload, expected_path=expected_path)
    if expected_output_role is not None and output.get("role") != expected_output_role:
        raise DevelopmentRuntimeLockError(
            f"{context}.role must equal {expected_output_role!r}"
        )
    record = {**dict(output), "role": role}
    _validated_file_record_metadata(record, context=context)
    if require_physical_artifact:
        _record_matches_physical(record, context=context)
    return record


def _validate_common_origin_completion(
    path: str,
    artifact_path: str,
    *,
    require_physical_artifact: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = load_json_mapping(path)
    expected = {
        "manifest_version": "closure_common_origin_manifest_v1",
        "status": "completed",
        "future_outcomes_accessed": False,
        "target_parquet_semantically_opened": False,
        "post_cutoff_target_rows_materialized": 0,
    }
    for field, value in expected.items():
        if payload.get(field) != value or (value is False and payload.get(field) is not False):
            raise DevelopmentRuntimeLockError(
                f"Common-origin completion requires {field}={value!r}"
            )
    if not isinstance(payload.get("output"), Mapping) or "outputs" in payload:
        raise DevelopmentRuntimeLockError(
            "Common-origin completion must use one singular output record"
        )
    artifact_record = _completion_artifact_record(
        payload,
        expected_path=artifact_path,
        role="common_origin",
        context="common_origin.output",
        require_physical_artifact=require_physical_artifact,
    )
    return file_record(path, role="common_origin_completion_manifest"), artifact_record


def common_origin_lock_record(
    runtime: Mapping[str, Any],
    *,
    require_physical_artifact: bool = True,
) -> dict[str, Any]:
    authority = runtime.get("authority")
    if not isinstance(authority, Mapping):
        raise DevelopmentRuntimeLockError("Runtime authority is missing")
    artifact_path = str(authority.get("common_origin_manifest_path", ""))
    completion_path = str(authority.get("common_origin_completion_manifest_path", ""))
    completion, artifact = _validate_common_origin_completion(
        completion_path,
        artifact_path,
        require_physical_artifact=require_physical_artifact,
    )
    dvc = (
        _load_dvc_pointer_for_file(artifact_path)
        if require_physical_artifact
        else _load_dvc_pointer_metadata(artifact_path)
    )
    if dvc["size"] != artifact["bytes"]:
        raise DevelopmentRuntimeLockError(
            "Common-origin completion bytes differ from its DVC pointer size"
        )
    return {
        "artifact": artifact,
        "completion_records": [completion],
        "dvc": dvc,
    }


def _validate_expert_source_repository(
    source_repository: Any,
    *,
    runtime: Mapping[str, Any],
) -> None:
    if not isinstance(source_repository, Mapping) or set(source_repository) != {
        "head",
        "branch",
        "worktree_status_at_start",
        "canonical_origin",
        "publication",
    }:
        raise DevelopmentRuntimeLockError(
            "Expert-state source repository evidence is missing or open-ended"
        )
    source_head = source_repository.get("head")
    publication = source_repository.get("publication")
    if isinstance(publication, Mapping):
        _require_exact_keys(
            publication,
            frozenset(
                {
                    "head",
                    "tracking_ref",
                    "tracking_oid",
                    "local_tracking_verified",
                    "remote_ref",
                    "remote_oid",
                    "remote_verified",
                }
            ),
            context="Expert-state source repository publication",
        )
    if (
        not isinstance(source_head, str)
        or GIT_COMMIT_PATTERN.fullmatch(source_head) is None
        or not isinstance(source_repository.get("branch"), str)
        or not source_repository.get("branch")
        or source_repository.get("worktree_status_at_start") != "clean"
        or not _exact_value_matches(
            source_repository.get("canonical_origin"),
            canonical_origin_identity(runtime),
        )
        or not isinstance(publication, Mapping)
        or publication.get("head") != source_head
        or publication.get("tracking_ref") != "origin/main"
        or publication.get("tracking_oid") != source_head
        or publication.get("local_tracking_verified") is not True
        or publication.get("remote_ref") != "refs/heads/main"
        or publication.get("remote_oid") != source_head
        or publication.get("remote_verified") is not True
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state source repository publication evidence drifted"
        )
    _require_ancestor(source_head, _git("rev-parse", "HEAD"))


def _validate_expert_completion(
    path: str,
    artifact_path: str,
    lineage_path: str,
    *,
    runtime: Mapping[str, Any],
    runtime_config: Path,
    runtime_schema: Path,
    require_physical_artifact: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from src.experiments.build_closure_expert_state import (
        expert_dependency_paths_and_roles,
    )
    from src.experiments.closure_development_guard import (
        DEVELOPMENT_ROLES,
        load_development_gate,
    )

    payload = load_json_mapping(path)
    _require_exact_keys(
        payload,
        EXPERT_COMPLETION_KEYS,
        context="Expert-state completion manifest",
    )
    state = runtime.get("primary_autoregressive_state")
    artifacts = runtime.get("artifacts")
    if not isinstance(state, Mapping) or not isinstance(artifacts, Mapping):
        raise DevelopmentRuntimeLockError("Runtime expert-state contract is missing")
    export = state.get("state_export")
    mappings = state.get("model_state_mappings")
    p0 = mappings.get("P0") if isinstance(mappings, Mapping) else None
    if not isinstance(export, Mapping) or not isinstance(p0, Mapping):
        raise DevelopmentRuntimeLockError("Runtime P0 expert-state mapping is missing")
    expected = {
        "manifest_version": "closure_expert_no_current_state_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "model_id": "P0",
        "artifact_role": "deterministic_expert_state_pre_e0_dl",
        "future_outcomes_accessed": False,
        "post_2021_outcomes_materialized": False,
        "zero_holdout_overlap": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected.items():
        observed = payload.get(field)
        if not _exact_value_matches(observed, value):
            raise DevelopmentRuntimeLockError(
                f"Expert-state manifest requires {field}={value!r}"
            )
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest generated_at_utc must be an ISO-8601 timestamp"
        )
    try:
        parsed_generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest generated_at_utc must be an ISO-8601 timestamp"
        ) from exc
    if parsed_generated_at.tzinfo is None:
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest generated_at_utc must include a timezone"
        )
    if payload.get("surface_id") != state.get("surface_id"):
        raise DevelopmentRuntimeLockError("Expert-state manifest surface_id drifted")
    if payload.get("state_mapping") != p0.get("input_state_mapping"):
        raise DevelopmentRuntimeLockError("Expert-state manifest state_mapping drifted")
    if payload.get("source_projection") != export.get("p0_source_projection_columns"):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest source projection drifted"
        )
    if payload.get("output_allowlist") != export.get("p0_output_columns"):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest output allowlist drifted"
        )
    if payload.get("time_roles") != list(DEVELOPMENT_ROLES):
        raise DevelopmentRuntimeLockError("Expert-state manifest time roles drifted")
    _validate_expert_source_repository(
        payload.get("source_repository"),
        runtime=runtime,
    )
    raw_outputs = payload.get("outputs")
    if (
        "output" in payload
        or not isinstance(raw_outputs, Sequence)
        or isinstance(raw_outputs, (str, bytes))
        or len(raw_outputs) != 2
        or {
            record.get("path")
            for record in raw_outputs
            if isinstance(record, Mapping)
        }
        != {artifact_path, lineage_path}
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state completion must bind exactly the artifact and lineage outputs"
        )
    for index, raw_output in enumerate(raw_outputs):
        _require_exact_keys(
            raw_output,
            EXPERT_FILE_RECORD_KEYS,
            context=f"Expert-state completion outputs[{index}]",
        )
    runtime_record = payload.get("runtime")
    expected_runtime_record = {
        "config_path": _canonical_repo_path(runtime_config),
        "config_sha256": _sha256_file(_resolve_repo_path(runtime_config)),
        "schema_path": _canonical_repo_path(runtime_schema),
        "schema_sha256": _sha256_file(_resolve_repo_path(runtime_schema)),
        "fit_authorized": False,
    }
    if not _exact_value_matches(runtime_record, expected_runtime_record):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest runtime config/schema identity drifted"
        )
    counts = payload.get("counts")
    if (
        not isinstance(counts, Mapping)
        or set(counts) != {"rows", "locations", "delta_previous_month_missing"}
        or isinstance(counts.get("rows"), bool)
        or not isinstance(counts.get("rows"), int)
        or int(counts["rows"]) <= 0
        or counts.get("locations") != 353
        or isinstance(counts.get("delta_previous_month_missing"), bool)
        or not isinstance(counts.get("delta_previous_month_missing"), int)
        or int(counts["delta_previous_month_missing"]) < 0
        or int(counts["delta_previous_month_missing"]) > int(counts["rows"])
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest must retain all 353 development locations"
        )

    script = payload.get("script")
    generating_path = "src/experiments/build_closure_expert_state.py"
    expected_script = file_record(generating_path, role="generating_script")
    if script != expected_script:
        raise DevelopmentRuntimeLockError("Expert-state generating script record drifted")

    gate = load_development_gate()
    source_path = _canonical_repo_path(str(export.get("p0_source_path", "")))
    expected_inputs = {
        source_path: "locked_expert_anchor",
        _repository_relative(gate.assignment_path): "holdout_assignment",
    }
    raw_inputs = payload.get("inputs")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise DevelopmentRuntimeLockError("Expert-state manifest inputs are missing")
    inputs_by_path = _records_by_path(raw_inputs, context="expert_state.inputs")
    for input_path, record in inputs_by_path.items():
        _require_exact_keys(
            record,
            EXPERT_FILE_RECORD_KEYS,
            context=f"expert_state.inputs.{input_path}",
        )
    if {
        input_path: str(record.get("role")) for input_path, record in inputs_by_path.items()
    } != expected_inputs:
        raise DevelopmentRuntimeLockError("Expert-state input path/role set drifted")
    expected_anchor_sha = cast(Mapping[str, Any], runtime["anfis"])["source_projection"][
        "expert_anchor_sha256"
    ]
    for input_path, record in inputs_by_path.items():
        _validated_file_record_metadata(record, context=f"expert_state.inputs.{input_path}")
        if input_path == source_path:
            if record.get("sha256") != expected_anchor_sha:
                raise DevelopmentRuntimeLockError("Expert-state anchor input hash drifted")
            if require_physical_artifact:
                _record_matches_physical(record, context=f"expert_state.inputs.{input_path}")
        else:
            _record_matches_physical(record, context=f"expert_state.inputs.{input_path}")

    dependency_specs = expert_dependency_paths_and_roles(
        runtime_config=_resolve_repo_path(runtime_config),
        runtime_schema=_resolve_repo_path(runtime_schema),
        source_path=_resolve_repo_path(source_path),
        gate=gate,
        runtime=runtime,
    )
    expected_dependencies = {
        _repository_relative(dependency_path): role
        for dependency_path, role in dependency_specs
    }
    raw_dependencies = payload.get("dependencies")
    if not isinstance(raw_dependencies, Sequence) or isinstance(
        raw_dependencies, (str, bytes)
    ):
        raise DevelopmentRuntimeLockError("Expert-state manifest dependencies are missing")
    dependencies_by_path = _records_by_path(
        raw_dependencies,
        context="expert_state.dependencies",
    )
    for dependency_path, record in dependencies_by_path.items():
        _require_exact_keys(
            record,
            EXPERT_FILE_RECORD_KEYS,
            context=f"expert_state.dependencies.{dependency_path}",
        )
    if {
        dependency_path: str(record.get("role"))
        for dependency_path, record in dependencies_by_path.items()
    } != expected_dependencies:
        raise DevelopmentRuntimeLockError("Expert-state dependency path/role set drifted")
    opaque_dependency_roles = {"restored_expert_anchor_source", "common_origin"}
    for dependency_path, record in dependencies_by_path.items():
        _validated_file_record_metadata(
            record,
            context=f"expert_state.dependencies.{dependency_path}",
        )
        role = str(record["role"])
        if require_physical_artifact or role not in opaque_dependency_roles:
            _record_matches_physical(
                record,
                context=f"expert_state.dependencies.{dependency_path}",
            )
    if dependencies_by_path[source_path].get("sha256") != expected_anchor_sha:
        raise DevelopmentRuntimeLockError("Expert-state dependency anchor hash drifted")
    common_completion = load_json_mapping(
        str(cast(Mapping[str, Any], runtime["authority"])["common_origin_completion_manifest_path"])
    )
    common_path = str(cast(Mapping[str, Any], runtime["authority"])["common_origin_manifest_path"])
    common_output = _completion_output_record(common_completion, expected_path=common_path)
    if dict(dependencies_by_path[common_path]) != {
        **dict(common_output),
        "role": "common_origin",
    }:
        raise DevelopmentRuntimeLockError("Expert-state common-origin dependency drifted")
    artifact_record = _completion_artifact_record(
        payload,
        expected_path=artifact_path,
        role="expert_state",
        context="expert_state.output",
        require_physical_artifact=require_physical_artifact,
        expected_output_role="expert_no_current_state",
    )
    lineage_output = _completion_output_record(payload, expected_path=lineage_path)
    if lineage_output.get("role") != "lineage_audit":
        raise DevelopmentRuntimeLockError(
            "Expert-state completion lineage output role drifted"
        )
    _record_matches_physical(
        lineage_output,
        context="expert_state.lineage_output",
    )
    return file_record(path, role="expert_state_completion_manifest"), artifact_record


def _validate_expert_lineage_payload(
    payload: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
) -> None:
    """Validate the exact dialect emitted by build_closure_expert_state."""
    _require_exact_keys(
        payload,
        EXPERT_LINEAGE_KEYS,
        context="Expert-state lineage audit",
    )
    state = runtime.get("primary_autoregressive_state")
    if not isinstance(state, Mapping) or not isinstance(state.get("state_export"), Mapping):
        raise DevelopmentRuntimeLockError("Runtime expert-state export is missing")
    export = cast(Mapping[str, Any], state["state_export"])
    expected = {
        "audit_version": "closure_expert_no_current_state_lineage_v1",
        "status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": state.get("surface_id"),
        "future_outcomes_accessed": False,
        "post_2021_outcomes_materialized": False,
        "e0_u_authorized": False,
        "locations": 353,
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "full_current_chla_sibling_columns": False,
        "optional_context_columns": [],
        "delta_geometry": "current_minus_exact_previous_calendar_month",
    }
    for field, value in expected.items():
        observed = payload.get(field)
        if not _exact_value_matches(observed, value):
            raise DevelopmentRuntimeLockError(
                f"Expert-state lineage audit requires {field}={value!r}"
            )
    expected_checks = {
        "exact_raw_projection": True,
        "locked_development_key_membership": True,
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "exact_state_mapping": True,
        "no_current_chla_state_allowlist": True,
        "one_month_delta_geometry": True,
        "no_optional_context_columns": True,
        "no_post_2021_materialization": True,
    }
    observed_checks = payload.get("checks")
    if (
        not isinstance(observed_checks, Mapping)
        or set(observed_checks) != EXPERT_LINEAGE_CHECK_KEYS
        or any(observed_checks.get(key) is not True for key in EXPERT_LINEAGE_CHECK_KEYS)
        or dict(observed_checks) != expected_checks
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state lineage audit checks drifted from the strict builder dialect"
        )
    if payload.get("source_projection") != export.get("p0_source_projection_columns"):
        raise DevelopmentRuntimeLockError("Expert-state lineage source projection drifted")
    if payload.get("output_allowlist") != export.get("p0_output_columns"):
        raise DevelopmentRuntimeLockError("Expert-state lineage output allowlist drifted")
    maximum_month = payload.get("maximum_year_month")
    minimum_month = payload.get("minimum_year_month")
    if (
        not isinstance(minimum_month, str)
        or not isinstance(maximum_month, str)
        or re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", minimum_month) is None
        or re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", maximum_month) is None
        or minimum_month > maximum_month
        or maximum_month > "2021-12"
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state lineage audit materialized a row after 2021-12"
        )
    rows = payload.get("rows")
    role_counts = payload.get("role_counts")
    if (
        isinstance(rows, bool)
        or not isinstance(rows, int)
        or rows < 353
        or not isinstance(role_counts, Mapping)
        or set(role_counts) != {"training", "model_selection", "calibration_threshold"}
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in role_counts.values())
        or sum(cast(int, value) for value in role_counts.values()) != rows
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state lineage row/role counts are invalid"
        )
    source_scan = payload.get("scan")
    source_scan_role_counts = (
        source_scan.get("role_counts") if isinstance(source_scan, Mapping) else None
    )
    if (
        not isinstance(source_scan, Mapping)
        or set(source_scan) != EXPERT_LINEAGE_SCAN_KEYS
        or isinstance(source_scan.get("boundary_crossing_rows"), bool)
        or source_scan.get("boundary_crossing_rows") != 0
        or isinstance(source_scan.get("materialized_rows"), bool)
        or source_scan.get("materialized_rows") != rows
        or isinstance(source_scan.get("returned_rows"), bool)
        or source_scan.get("returned_rows") != rows
        or not isinstance(source_scan_role_counts, Mapping)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in source_scan_role_counts.values()
        )
        or dict(source_scan_role_counts)
        != {role: count for role, count in role_counts.items() if count > 0}
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state lineage source scan crossed the sealed development boundary"
        )


def _validate_expert_lineage_audit(
    path: str,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    payload = load_json_mapping(path)
    _validate_expert_lineage_payload(payload, runtime=runtime)
    return file_record(path, role="expert_state_lineage_audit")


def _expert_semantic_audit_from_lineage(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "audit_version": "closure_expert_no_current_state_semantic_audit_v1",
        "schema_allowlist_verified": True,
        "exact_development_locations_verified": True,
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "locked_time_roles_verified": True,
        "unit_interval_values_verified": True,
        "signed_deltas_verified": True,
        "exact_month_delta_recomputation_verified": True,
        "no_post_2021_materialization": True,
        "future_outcomes_accessed": False,
        "rows": payload.get("rows"),
        "locations": payload.get("locations"),
        "minimum_year_month": payload.get("minimum_year_month"),
        "maximum_year_month": payload.get("maximum_year_month"),
        "role_counts": payload.get("role_counts"),
        "delta_previous_month_missing_count": payload.get(
            "delta_previous_month_missing_count"
        ),
        "source_projection": payload.get("source_projection"),
        "output_allowlist": payload.get("output_allowlist"),
    }


def expert_state_lock_record(
    runtime: Mapping[str, Any],
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    require_physical_artifact: bool = True,
) -> dict[str, Any]:
    artifacts = runtime.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise DevelopmentRuntimeLockError("Runtime artifacts section is missing")
    artifact_path = str(artifacts.get("expert_state_path", ""))
    manifest_path = str(artifacts.get("expert_state_manifest_path", ""))
    audit_path = str(artifacts.get("expert_state_lineage_audit_path", ""))
    completion, artifact = _validate_expert_completion(
        manifest_path,
        artifact_path,
        audit_path,
        runtime=runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        require_physical_artifact=require_physical_artifact,
    )
    manifest_payload = load_json_mapping(manifest_path)
    lineage_payload = load_json_mapping(audit_path)
    manifest_counts = manifest_payload.get("counts")
    if (
        not isinstance(manifest_counts, Mapping)
        or manifest_counts.get("rows") != lineage_payload.get("rows")
        or manifest_counts.get("locations") != lineage_payload.get("locations")
        or manifest_counts.get("delta_previous_month_missing")
        != lineage_payload.get("delta_previous_month_missing_count")
    ):
        raise DevelopmentRuntimeLockError(
            "Expert-state manifest and lineage counts disagree"
        )
    dvc = (
        _load_dvc_pointer_for_file(artifact_path)
        if require_physical_artifact
        else _load_dvc_pointer_metadata(artifact_path)
    )
    if dvc["size"] != artifact["bytes"]:
        raise DevelopmentRuntimeLockError(
            "Expert-state completion bytes differ from its DVC pointer size"
        )
    _validate_expert_lineage_payload(lineage_payload, runtime=runtime)
    semantic_audit = _expert_semantic_audit_from_lineage(lineage_payload)
    if require_physical_artifact:
        from src.experiments.build_closure_expert_state import (
            audit_materialized_expert_state,
        )

        physical_audit = audit_materialized_expert_state(
            _resolve_repo_path(artifact_path),
            runtime=runtime,
        )
        if physical_audit != semantic_audit:
            raise DevelopmentRuntimeLockError(
                "Expert-state semantic audit differs from its locked lineage audit"
            )
    return {
        "artifact": artifact,
        "completion_records": [
            completion,
            _validate_expert_lineage_audit(audit_path, runtime=runtime),
        ],
        "dvc": dvc,
        "semantic_audit": semantic_audit,
    }


def parent_records(
    runtime: Mapping[str, Any],
    *,
    common_origin: Mapping[str, Any],
    expert_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    del common_origin, expert_state
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    raw_paths = implementation.get("required_parent_paths")
    raw_roles = implementation.get("required_parent_hashes")
    if (
        not isinstance(raw_paths, Mapping)
        or not isinstance(raw_roles, Sequence)
        or isinstance(raw_roles, (str, bytes))
    ):
        raise DevelopmentRuntimeLockError(
            "implementation_lock required parent paths/roles are missing"
        )
    synthetic_roles = {"planned_artifact_paths", "runtime_transitive_source_dependencies"}
    expected_file_roles = {str(role) for role in raw_roles}.difference(synthetic_roles)
    if set(raw_paths) != expected_file_roles:
        raise DevelopmentRuntimeLockError(
            "required_parent_paths must bind every physical required parent role"
        )
    records = [
        file_record(str(path), role=str(role))
        for role, path in raw_paths.items()
    ]
    return sorted(records, key=lambda record: (str(record["path"]), str(record["role"])))


def _validate_parent_lock_metadata(
    observed: Sequence[Any],
    runtime: Mapping[str, Any],
    *,
    common_origin: Mapping[str, Any],
    expert_state: Mapping[str, Any],
    restored_sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Rebuild Git parents and cross-bind absent DVC payload records."""
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    raw_paths = implementation.get("required_parent_paths")
    raw_roles = implementation.get("required_parent_hashes")
    if (
        not isinstance(raw_paths, Mapping)
        or not isinstance(raw_roles, Sequence)
        or isinstance(raw_roles, (str, bytes))
    ):
        raise DevelopmentRuntimeLockError(
            "implementation_lock required parent paths/roles are missing"
        )
    synthetic_roles = {"planned_artifact_paths", "runtime_transitive_source_dependencies"}
    expected_roles = {str(role) for role in raw_roles}.difference(synthetic_roles)
    if set(raw_paths) != expected_roles:
        raise DevelopmentRuntimeLockError(
            "required_parent_paths must bind every physical required parent role"
        )
    observed_by_path = _records_by_path(observed, context="parents")
    expected_paths = {_canonical_repo_path(str(path)) for path in raw_paths.values()}
    if set(observed_by_path) != expected_paths:
        raise DevelopmentRuntimeLockError("E0-DL parent paths drifted")

    common_record = cast(Mapping[str, Any], common_origin.get("artifact"))
    expert_record = cast(Mapping[str, Any], expert_state.get("artifact"))
    restored_by_path = {
        str(record["path"]): record
        for record in restored_sources
    }
    opaque_by_role: dict[str, Mapping[str, Any]] = {
        "common_origin": common_record,
        "expert_state": expert_record,
    }
    for role, source_role in (
        ("restored_panel", "restored_monthly_panel_source"),
        ("restored_expert_anchor", "restored_expert_anchor_source"),
    ):
        matches = [
            record
            for record in restored_by_path.values()
            if record.get("role") == source_role
        ]
        if len(matches) != 1:
            raise DevelopmentRuntimeLockError(f"Missing locked source record for {role}")
        opaque_by_role[role] = matches[0]

    expected_records: list[dict[str, Any]] = []
    for role, raw_path in raw_paths.items():
        role_name = str(role)
        path = _canonical_repo_path(str(raw_path))
        observed_record = observed_by_path[path]
        _validated_file_record_metadata(observed_record, context=f"parents.{path}")
        if observed_record.get("role") != role_name:
            raise DevelopmentRuntimeLockError(f"E0-DL parent role drifted: {path}")
        if role_name in opaque_by_role:
            source = opaque_by_role[role_name]
            expected_record = {
                "path": path,
                "role": role_name,
                "bytes": source.get("bytes"),
                "sha256": source.get("sha256"),
            }
        else:
            expected_record = file_record(path, role=role_name)
        if dict(observed_record) != expected_record:
            raise DevelopmentRuntimeLockError(f"E0-DL parent record drifted: {path}")
        expected_records.append(expected_record)
    return sorted(
        expected_records,
        key=lambda record: (str(record["path"]), str(record["role"])),
    )


def _rendered_runtime_paths(runtime: Mapping[str, Any]) -> tuple[list[str], str]:
    # Local import avoids a module cycle when the runtime validator delegates
    # external-lock validation back to this module.
    from src.experiments.closure_runtime_contract import (
        render_runtime_artifact_paths,
        validate_seed_slots,
    )

    seeds = runtime.get("seeds")
    if not isinstance(seeds, Mapping):
        raise DevelopmentRuntimeLockError("Runtime seeds section is missing")
    slots = validate_seed_slots(cast(Sequence[Any], seeds.get("ordered_slots")))
    paths, digest = render_runtime_artifact_paths(runtime, slots)
    if len(paths) != EXPECTED_PATH_COUNT or digest != EXPECTED_PATH_DIGEST:
        raise DevelopmentRuntimeLockError("Runtime planned artifact path expansion drifted")
    return paths, digest


def _git_blob_at_head(head: str, path: str) -> bytes | None:
    canonical = _canonical_repo_path(path)
    present = subprocess.run(
        ["git", "cat-file", "-e", f"{head}:{canonical}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    if present.returncode != 0:
        return None
    return subprocess.run(
        ["git", "show", f"{head}:{canonical}"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def planned_artifact_records(
    runtime: Mapping[str, Any],
    *,
    locked_head: str,
    expert_state: Mapping[str, Any],
    verify_current_prefit: bool = False,
) -> dict[str, Any]:
    """Recompute the exact pre-fit artifact snapshot from locked Git H."""
    paths, digest = _rendered_runtime_paths(runtime)
    artifacts = cast(Mapping[str, Any], runtime["artifacts"])
    expected_ownership = {
        "data/closure_v1": "explicit_pointer_per_materialized_parquet",
        "models/closure_v1": "models.dvc_monolithic_parent",
        "reports/closure_v1": "explicit_pointer_per_materialized_parquet",
    }
    if artifacts.get("dvc_ownership_plan") != expected_ownership:
        raise DevelopmentRuntimeLockError("Runtime DVC ownership plan drifted")
    expert_state_path = str(artifacts["expert_state_path"])
    locked_expert_record = expert_state.get("artifact")
    locked_expert_dvc = expert_state.get("dvc")
    if not isinstance(locked_expert_record, Mapping) or not isinstance(locked_expert_dvc, Mapping):
        raise DevelopmentRuntimeLockError("Locked expert-state DVC metadata is missing")
    records: list[dict[str, Any]] = []
    for path in paths:
        suffix = Path(path).suffix
        heavy = suffix in {".parquet", ".pt"}
        if verify_current_prefit and heavy and path != expert_state_path:
            if _resolve_repo_path(path).is_file():
                raise DevelopmentRuntimeLockError(
                    f"Pre-fit heavy output is already materialized: {path}"
                )
            if suffix == ".parquet" and _resolve_repo_path(f"{path}.dvc").exists():
                raise DevelopmentRuntimeLockError(
                    f"Unmaterialized output has a forbidden DVC pointer: {path}.dvc"
                )
        materialized = False
        materialized_bytes: int | None = None
        materialized_sha256: str | None = None
        pointer_verified = False
        if suffix == ".parquet":
            strategy = "explicit_pointer"
            owner_path: str | None = f"{path}.dvc"
            pointer_blob = _git_blob_at_head(locked_head, owner_path)
            if path == expert_state_path:
                if pointer_blob is None:
                    raise DevelopmentRuntimeLockError(
                        "Expert-state DVC pointer was not committed in locked H"
                    )
                if locked_expert_record.get("path") != path:
                    raise DevelopmentRuntimeLockError("Locked expert-state path drifted")
                if (
                    locked_expert_dvc.get("pointer_path") != owner_path
                    or locked_expert_dvc.get("pointer_bytes") != len(pointer_blob)
                    or locked_expert_dvc.get("pointer_sha256")
                    != hashlib.sha256(pointer_blob).hexdigest()
                ):
                    raise DevelopmentRuntimeLockError(
                        "Expert-state DVC pointer does not match locked H"
                    )
                materialized = True
                materialized_bytes = cast(int, locked_expert_record.get("bytes"))
                materialized_sha256 = cast(str, locked_expert_record.get("sha256"))
                pointer_verified = True
            elif pointer_blob is not None:
                raise DevelopmentRuntimeLockError(
                    f"Pre-fit output has a forbidden DVC pointer in locked H: {owner_path}"
                )
        elif suffix == ".pt":
            strategy = "models_dvc_monolithic_parent"
            owner_path = "models.dvc"
            if _git_blob_at_head(locked_head, owner_path) is None:
                raise DevelopmentRuntimeLockError("models.dvc was not committed in locked H")
        else:
            strategy = "git_when_materialized"
            blob = _git_blob_at_head(locked_head, path)
            materialized = blob is not None
            owner_path = path if materialized else None
            if blob is not None:
                materialized_bytes = len(blob)
                materialized_sha256 = hashlib.sha256(blob).hexdigest()
        records.append(
            {
                "path": path,
                "artifact_class": "heavy" if heavy else "lightweight",
                "materialized_at_lock": materialized,
                "owner_strategy": strategy,
                "owner_path": owner_path,
                "bytes": materialized_bytes,
                "sha256": materialized_sha256,
                "pointer_verified": pointer_verified,
            }
        )
    return {"count": len(paths), "sha256": digest, "records": records}


def environment_payload(
    device: str,
    runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if device != "cpu":
        raise DevelopmentRuntimeLockError(
            "Closure V1 E0-DL locks device=cpu; CUDA requires a new reviewed contract"
        )
    active_runtime = runtime or load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
    cpu_policy = configure_torch_cpu_execution_policy(active_runtime)
    packages: list[dict[str, str]] = []
    for distribution in PACKAGE_DISTRIBUTIONS:
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise DevelopmentRuntimeLockError(
                f"Required runtime distribution is not installed: {distribution}"
            ) from exc
        packages.append({"name": distribution, "version": version})
    packages.sort(key=lambda item: item["name"].lower())
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_name": Path(sys.executable).name,
        "platform": platform.platform(),
        "machine": platform.machine() or "unknown",
        "device": device,
        "cublas_workspace_config": None,
        "cpu_execution_policy": cpu_policy,
        "packages": packages,
    }


def focused_test_command(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    mapping = _component_mapping(runtime)
    tests = mapping.get("relevant_tests", ())
    if not tests or any(not path.startswith("tests/") or not path.endswith(".py") for path in tests):
        raise DevelopmentRuntimeLockError(
            "relevant_tests must be an explicit non-empty list of tests/*.py paths"
        )
    return ("poetry", "run", "pytest", *tests, "-q")


def command_evidence(command: Sequence[str]) -> dict[str, Any]:
    """Run one fixed verification command and retain tamper-evident output digests."""
    if not command or any(not isinstance(value, str) or not value for value in command):
        raise DevelopmentRuntimeLockError("Verification command must be a non-empty argv list")
    try:
        result = subprocess.run(
            list(command),
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=False,
            timeout=3600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DevelopmentRuntimeLockError(
            "E0-DL verification command could not complete within its fixed bound"
        ) from exc
    if result.returncode != 0:
        stdout_sha256 = hashlib.sha256(result.stdout).hexdigest()
        stderr_sha256 = hashlib.sha256(result.stderr).hexdigest()
        raise DevelopmentRuntimeLockError(
            "E0-DL verification command failed without echoing captured output: "
            f"exit_code={result.returncode}, stdout_sha256={stdout_sha256}, "
            f"stderr_sha256={stderr_sha256}"
        )
    return {
        "command": list(command),
        "exit_code": 0,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        "passed": True,
    }


def _runtime_paths_match_contract(
    runtime: Mapping[str, Any],
    *,
    runtime_config: Path,
    runtime_schema: Path,
    lock_schema: Path,
    lock_path: Path,
) -> None:
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    expected = {
        "lock_manifest_path": _canonical_repo_path(lock_path),
        "lock_schema_path": _canonical_repo_path(lock_schema),
    }
    for field, value in expected.items():
        if implementation.get(field) != value:
            raise DevelopmentRuntimeLockError(
                f"implementation_lock.{field} must equal {value}"
            )
    if runtime.get("status") != EXPECTED_RUNTIME_STATUS:
        raise DevelopmentRuntimeLockError("Runtime contract status must remain ready_to_lock")
    _require_tracked(runtime_config)
    _require_tracked(runtime_schema)
    _require_tracked(lock_schema)


def _validate_runtime_prelock_contract(
    runtime: Mapping[str, Any],
    runtime_schema_payload: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = True,
) -> dict[str, Any]:
    """Run the existing closed contract without loading the external lock."""
    from src.experiments.closure_runtime_contract import validate_development_runtime

    summary = validate_development_runtime(
        runtime,
        runtime_schema_payload,
        cross_validate_locked=True,
        validate_repository=True,
        require_restored_development_sources=require_physical_artifacts,
    )
    required_true = ["cross_validated_locked_contract", "common_origin_completion_validated"]
    if require_physical_artifacts:
        required_true.extend(
            [
                "common_origin_materialized",
                "common_origin_output_verified",
                "restored_development_sources_verified",
            ]
        )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise DevelopmentRuntimeLockError(
            f"Runtime prelock contract did not satisfy required gates: {failed}"
        )
    return summary


def collect_prelock_state(
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    lock_schema: Path = DEFAULT_LOCK_SCHEMA,
    lock_path: Path = DEFAULT_LOCK_PATH,
    device: str,
    verify_parent_remote_publication: bool = True,
) -> dict[str, Any]:
    """Collect the clean, outcome-free state from which a real lock may be built."""
    state = _require_clean_repository()
    runtime = load_yaml_mapping(runtime_config)
    runtime_schema_payload = load_json_mapping(runtime_schema)
    try:
        validate_json_schema(runtime, runtime_schema_payload, instance_path="$.development_runtime")
    except ClosureContractError as exc:
        raise DevelopmentRuntimeLockError(str(exc)) from exc
    _runtime_paths_match_contract(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        lock_schema=lock_schema,
        lock_path=lock_path,
    )
    _validate_runtime_prelock_contract(runtime, runtime_schema_payload)
    origin_identity = canonical_origin_identity(runtime)
    parent_publication = locked_parent_publication_identity(
        verify_remote=verify_parent_remote_publication
    )
    if parent_publication["head"] != state["head"]:
        raise DevelopmentRuntimeLockError(
            "E0-DL parent publication evidence differs from the clean repository HEAD"
        )
    components = component_records(runtime)
    dependencies = runtime_dependency_records(runtime)
    restored_sources = restored_development_source_records(runtime)
    common_origin = common_origin_lock_record(runtime)
    expert_state = expert_state_lock_record(runtime)
    planned = planned_artifact_records(
        runtime,
        locked_head=str(state["head"]),
        expert_state=expert_state,
        verify_current_prefit=True,
    )
    parents = parent_records(runtime, common_origin=common_origin, expert_state=expert_state)
    environment = environment_payload(device, runtime)
    return {
        "runtime": runtime,
        "locked_repository": state,
        "canonical_origin": origin_identity,
        "locked_parent_publication": parent_publication,
        "runtime_contract": {
            "config": file_record(runtime_config, role="development_runtime_config"),
            "schema": file_record(runtime_schema, role="development_runtime_schema"),
            "status": EXPECTED_RUNTIME_STATUS,
        },
        "components": components,
        "runtime_dependencies": dependencies,
        "parents": parents,
        "restored_development_sources": restored_sources,
        "common_origin": common_origin,
        "expert_state": expert_state,
        "planned_artifacts": planned,
        "environment": environment,
    }


def build_development_runtime_lock_payload(
    prelock: Mapping[str, Any],
    *,
    full_type_check: Mapping[str, Any],
    focused_tests: Mapping[str, Any],
    dvc_remote_verification: Mapping[str, Any],
    created_at_utc: str,
) -> dict[str, Any]:
    """Build the non-self-referential external lock from verified prelock state."""
    payload = {
        "lock_version": LOCK_VERSION,
        "status": "locked",
        "gate": EXPECTED_GATE,
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "created_at_utc": created_at_utc,
        "locked_repository": prelock["locked_repository"],
        "canonical_origin": prelock["canonical_origin"],
        "locked_parent_publication": prelock["locked_parent_publication"],
        "runtime_contract": prelock["runtime_contract"],
        "components": prelock["components"],
        "runtime_dependencies": prelock["runtime_dependencies"],
        "parents": prelock["parents"],
        "restored_development_sources": prelock["restored_development_sources"],
        "common_origin": prelock["common_origin"],
        "expert_state": prelock["expert_state"],
        "planned_artifacts": prelock["planned_artifacts"],
        "environment": prelock["environment"],
        "dvc_remote_verification": dict(dvc_remote_verification),
        "verification": {
            "full_type_check": dict(full_type_check),
            "focused_tests": dict(focused_tests),
        },
        "audits": {
            "common_origin_validated": True,
            "expert_state_validated": True,
            "expert_state_semantic_audit_verified": True,
            "zero_holdout_overlap": True,
            "no_post_2021_materialization": True,
            "restored_source_hashes_verified": True,
            "component_hashes_verified": True,
            "recursive_dependency_hashes_verified": True,
            "planned_artifact_paths_verified": True,
            "prelock_dvc_ownership_verified": True,
            "dvc_remote_verified_at_lock": True,
            "canonical_origin_identity_verified": True,
            "locked_parent_published_at_lock": True,
            "environment_locked": True,
        },
        "authorizations": dict(EXPECTED_AUTHORIZATIONS),
        "seals": dict(EXPECTED_SEALS),
    }
    return payload


def _require_exact_record_set(
    observed: Sequence[Any],
    expected: Sequence[Mapping[str, Any]],
    *,
    context: str,
) -> None:
    observed_index = _records_by_path(observed, context=context)
    expected_index = _records_by_path(expected, context=f"expected_{context}")
    if tuple(observed_index) != tuple(expected_index):
        raise DevelopmentRuntimeLockError(
            f"{context} paths drifted: observed={list(observed_index)}, expected={list(expected_index)}"
        )
    for path, record in observed_index.items():
        if dict(record) != dict(expected_index[path]):
            raise DevelopmentRuntimeLockError(f"{context} record drifted: {path}")
        _record_matches_physical(record, context=f"{context}.{path}")


def validate_development_runtime_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    """Validate the closed JSON structure and non-negotiable authorization seals."""
    try:
        validate_json_schema(payload, schema, instance_path="$.development_runtime_lock")
    except ClosureContractError as exc:
        raise DevelopmentRuntimeLockError(str(exc)) from exc
    try:
        created_at = datetime.fromisoformat(
            str(payload["created_at_utc"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise DevelopmentRuntimeLockError("created_at_utc must be valid ISO-8601") from exc
    if created_at.utcoffset() is None:
        raise DevelopmentRuntimeLockError("created_at_utc must include a timezone")
    if payload.get("authorizations") != EXPECTED_AUTHORIZATIONS:
        raise DevelopmentRuntimeLockError("E0-DL authorization fields drifted")
    if payload.get("seals") != EXPECTED_SEALS:
        raise DevelopmentRuntimeLockError("E0-DL outcome/model-lock seals drifted")
    canonical_origin = payload.get("canonical_origin")
    expected_origin_fields = {
        "remote_name": "origin",
        "identity_algorithm": CANONICAL_ORIGIN_IDENTITY_ALGORITHM,
        "identity_sha256": EXPECTED_CANONICAL_ORIGIN_IDENTITY_SHA256,
        "fetch_push_identity_equal": True,
    }
    if not isinstance(canonical_origin, Mapping) or any(
        canonical_origin.get(field) != value
        for field, value in expected_origin_fields.items()
    ):
        raise DevelopmentRuntimeLockError("E0-DL canonical origin evidence drifted")
    for field in ("fetch_url_count", "push_url_count"):
        value = canonical_origin.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DevelopmentRuntimeLockError("E0-DL canonical origin URL counts are invalid")
    parent_publication = payload.get("locked_parent_publication")
    locked_repository = payload.get("locked_repository")
    locked_head = (
        locked_repository.get("head")
        if isinstance(locked_repository, Mapping)
        else None
    )
    if (
        not isinstance(parent_publication, Mapping)
        or parent_publication.get("head") != locked_head
        or parent_publication.get("tracking_ref") != "origin/main"
        or parent_publication.get("tracking_oid") != locked_head
        or parent_publication.get("local_tracking_verified") is not True
        or parent_publication.get("remote_ref") != "refs/heads/main"
        or parent_publication.get("remote_oid") != locked_head
        or parent_publication.get("remote_verified") is not True
    ):
        raise DevelopmentRuntimeLockError(
            "E0-DL locked parent publication evidence drifted"
        )
    dvc_evidence = payload.get("dvc_remote_verification")
    if (
        not isinstance(dvc_evidence, Mapping)
        or dvc_evidence.get("dvc_remote_verified_at_lock") is not True
        or dvc_evidence.get("method") != DVC_REMOTE_VERIFICATION_METHOD
    ):
        raise DevelopmentRuntimeLockError("E0-DL DVC remote evidence is missing")
    runtime_contract = cast(Mapping[str, Any], payload["runtime_contract"])
    for key in ("config", "schema"):
        _validated_file_record_metadata(
            cast(Mapping[str, Any], runtime_contract[key]),
            context=f"runtime_contract.{key}",
        )
    for section in ("components", "runtime_dependencies", "parents"):
        raw_records = cast(Sequence[Any], payload[section])
        _records_by_path(raw_records, context=section)
        for index, record in enumerate(raw_records):
            _validated_file_record_metadata(
                cast(Mapping[str, Any], record),
                context=f"{section}[{index}]",
            )
    restored_records = cast(Sequence[Any], payload["restored_development_sources"])
    _records_by_path(restored_records, context="restored_development_sources")
    for index, record in enumerate(restored_records):
        _validated_file_record_metadata(
            cast(Mapping[str, Any], record),
            context=f"restored_development_sources[{index}]",
        )
    for section in ("common_origin", "expert_state"):
        artifact = cast(Mapping[str, Any], payload[section])
        _validated_file_record_metadata(
            cast(Mapping[str, Any], artifact["artifact"]),
            context=f"{section}.artifact",
        )
        for index, record in enumerate(cast(Sequence[Any], artifact["completion_records"])):
            _validated_file_record_metadata(
                cast(Mapping[str, Any], record),
                context=f"{section}.completion_records[{index}]",
            )
        dvc = cast(Mapping[str, Any], artifact["dvc"])
        _canonical_repo_path(str(dvc["pointer_path"]))
        for field in ("pointer_bytes", "size"):
            value = dvc[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DevelopmentRuntimeLockError(f"{section}.dvc.{field} must be non-negative")
    planned = payload.get("planned_artifacts")
    if not isinstance(planned, Mapping):
        raise DevelopmentRuntimeLockError("planned_artifacts is missing")
    records = planned.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise DevelopmentRuntimeLockError("planned_artifacts.records is invalid")
    paths = [record.get("path") for record in records if isinstance(record, Mapping)]
    if len(paths) != EXPECTED_PATH_COUNT or len(set(paths)) != EXPECTED_PATH_COUNT:
        raise DevelopmentRuntimeLockError("Planned artifact records must contain 201 unique paths")
    if paths != sorted(cast(list[str], paths), key=lambda value: value.encode("utf-8")):
        raise DevelopmentRuntimeLockError("Planned artifact records are not UTF-8 sorted")
    for index, raw_record in enumerate(records):
        record = cast(Mapping[str, Any], raw_record)
        path = str(record["path"])
        suffix = Path(path).suffix
        heavy = suffix in {".parquet", ".pt"}
        if record["artifact_class"] != ("heavy" if heavy else "lightweight"):
            raise DevelopmentRuntimeLockError(
                f"Planned artifact class drifted at records[{index}]"
            )
        materialized = bool(record["materialized_at_lock"])
        record_bytes = record["bytes"]
        record_sha256 = record["sha256"]
        if materialized:
            if (
                isinstance(record_bytes, bool)
                or not isinstance(record_bytes, int)
                or record_bytes < 0
                or not isinstance(record_sha256, str)
                or SHA256_PATTERN.fullmatch(record_sha256) is None
            ):
                raise DevelopmentRuntimeLockError(
                    f"Materialized planned artifact lacks bytes/SHA-256: {path}"
                )
        elif record_bytes is not None or record_sha256 is not None:
            raise DevelopmentRuntimeLockError(
                f"Unmaterialized planned artifact carries content metadata: {path}"
            )


def _require_lock_published(
    lock_path: Path,
    *,
    verify_remote: bool,
) -> tuple[str, str, str, str, str | None]:
    relative = _require_unmodified(lock_path)
    execution_head = _git("rev-parse", "HEAD")
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{execution_head}:{relative}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DevelopmentRuntimeLockError(
            "E0-DL lock must be committed and published in the execution HEAD"
        )
    committed = subprocess.run(
        ["git", "show", f"{execution_head}:{relative}"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    physical = _resolve_repo_path(relative).read_bytes()
    if committed != physical:
        raise DevelopmentRuntimeLockError("Working E0-DL lock differs from execution HEAD")
    published_ref = "origin/main"
    published_head = _git("rev-parse", published_ref)
    if not GIT_COMMIT_PATTERN.fullmatch(published_head):
        raise DevelopmentRuntimeLockError("origin/main does not resolve to a full commit ID")
    published = subprocess.run(
        ["git", "show", f"{published_ref}:{relative}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    if published.returncode != 0 or published.stdout != physical:
        raise DevelopmentRuntimeLockError(
            "E0-DL lock must be pushed unchanged to origin/main before fit"
        )
    remote_main_oid: str | None = None
    if verify_remote:
        try:
            remote = subprocess.run(
                ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DevelopmentRuntimeLockError(
                "Cannot query the real origin main ref before development fit"
            ) from exc
        fields = remote.stdout.strip().split()
        if remote.returncode != 0 or len(fields) != 2 or fields[1] != "refs/heads/main":
            raise DevelopmentRuntimeLockError(
                "Cannot verify the real origin main ref before development fit"
            )
        remote_main_oid = fields[0]
        if (
            not GIT_COMMIT_PATTERN.fullmatch(remote_main_oid)
            or remote_main_oid != published_head
        ):
            raise DevelopmentRuntimeLockError(
                "Local origin/main is stale or differs from the real remote main ref"
            )
    return relative, execution_head, published_ref, published_head, remote_main_oid


def _require_ancestor(ancestor: str, descendant: str) -> None:
    if not GIT_COMMIT_PATTERN.fullmatch(ancestor) or not GIT_COMMIT_PATTERN.fullmatch(descendant):
        raise DevelopmentRuntimeLockError("E0-DL repository ancestry uses invalid commit IDs")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DevelopmentRuntimeLockError(
            f"Locked pre-fit HEAD {ancestor} is not an ancestor of {descendant}"
        )


def _require_records_committed_at_head(records: Sequence[Any], head: str, *, context: str) -> None:
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise DevelopmentRuntimeLockError(f"{context}[{index}] must be an object")
        path = str(raw_record["path"])
        result = subprocess.run(
            ["git", "show", f"{head}:{path}"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            raise DevelopmentRuntimeLockError(f"Locked component was not committed in H: {path}")
        if hashlib.sha256(result.stdout).hexdigest() != raw_record.get("sha256"):
            raise DevelopmentRuntimeLockError(f"Locked component bytes do not match H: {path}")


def _require_tracked_records_committed_at_head(
    records: Sequence[Any],
    head: str,
    *,
    context: str,
    opaque_dvc_roles: frozenset[str] = frozenset(),
) -> None:
    """Require every critical parent in H; only named DVC payloads stay opaque."""
    tracked_records: list[Any] = []
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            raise DevelopmentRuntimeLockError(f"{context} contains a non-object record")
        path = str(raw_record.get("path", ""))
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if tracked.returncode == 0:
            tracked_records.append(raw_record)
        elif raw_record.get("role") not in opaque_dvc_roles:
            raise DevelopmentRuntimeLockError(
                f"Critical E0-DL parent was not Git-tracked in H: {path}"
            )
    _require_records_committed_at_head(tracked_records, head, context=context)


def _materialized_artifact_git_records(
    artifact: Mapping[str, Any],
    *,
    context: str,
) -> list[dict[str, Any]]:
    completions = artifact.get("completion_records")
    dvc = artifact.get("dvc")
    if (
        not isinstance(completions, Sequence)
        or isinstance(completions, (str, bytes))
        or not isinstance(dvc, Mapping)
    ):
        raise DevelopmentRuntimeLockError(f"{context} metadata is malformed")
    records = [dict(cast(Mapping[str, Any], record)) for record in completions]
    pointer_record = {
        "path": dvc.get("pointer_path"),
        "role": f"{context}_dvc_pointer",
        "bytes": dvc.get("pointer_bytes"),
        "sha256": dvc.get("pointer_sha256"),
    }
    _validated_file_record_metadata(pointer_record, context=f"{context}.dvc")
    records.append(pointer_record)
    return records


def _locked_artifact_matches_observed_metadata(
    locked: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    context: str,
) -> None:
    """Compare a lock-time artifact while leaving its current payload opaque."""
    locked_dvc = locked.get("dvc")
    observed_dvc = observed.get("dvc")
    if not isinstance(locked_dvc, Mapping) or not isinstance(observed_dvc, Mapping):
        raise DevelopmentRuntimeLockError(f"{context} DVC metadata is malformed")
    expected_locked_dvc = {**dict(observed_dvc), "payload_verified_at_lock": True}
    if dict(locked_dvc) != expected_locked_dvc:
        raise DevelopmentRuntimeLockError(f"{context} DVC pointer identity drifted")
    expected = {**dict(observed), "dvc": expected_locked_dvc}
    if dict(locked) != expected:
        raise DevelopmentRuntimeLockError(f"{context} E0-DL record drifted")


def load_and_validate_development_runtime_lock(
    lock_path: Path = DEFAULT_LOCK_PATH,
    lock_schema: Path = DEFAULT_LOCK_SCHEMA,
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    device: str | None = None,
    require_published: bool = True,
    require_physical_artifacts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate E0-DL in strict-fit or source-only metadata mode.

    Metadata mode still verifies the published lock, Git ancestry, source code,
    manifests, DVC pointers, and the snapshot recorded at locked H.  It never
    turns the payload's authorization declaration into effective fit authority.
    """
    if not _resolve_repo_path(lock_path).is_file():
        raise DevelopmentRuntimeLockError(f"E0-DL lock is absent: {_canonical_repo_path(lock_path)}")
    payload = load_json_mapping(lock_path)
    schema = load_json_mapping(lock_schema)
    validate_development_runtime_lock_payload(payload, schema)
    runtime = load_yaml_mapping(runtime_config)
    runtime_schema_payload = load_json_mapping(runtime_schema)
    try:
        validate_json_schema(runtime, runtime_schema_payload, instance_path="$.development_runtime")
    except ClosureContractError as exc:
        raise DevelopmentRuntimeLockError(str(exc)) from exc
    _runtime_paths_match_contract(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        lock_schema=lock_schema,
        lock_path=lock_path,
    )
    _validate_runtime_prelock_contract(
        runtime,
        runtime_schema_payload,
        require_physical_artifacts=require_physical_artifacts,
    )
    current_origin = canonical_origin_identity(runtime)
    if payload.get("canonical_origin") != current_origin:
        raise DevelopmentRuntimeLockError("Canonical origin identity drifted from E0-DL")
    if require_published:
        (
            relative_lock_path,
            execution_head,
            published_ref,
            published_head,
            remote_main_oid,
        ) = _require_lock_published(
            lock_path,
            verify_remote=require_physical_artifacts,
        )
    else:
        relative_lock_path = _canonical_repo_path(lock_path)
        execution_head = _git("rev-parse", "HEAD")
        published_ref = None
        published_head = None
        remote_main_oid = None
    locked_repository = payload.get("locked_repository")
    if not isinstance(locked_repository, Mapping):
        raise DevelopmentRuntimeLockError("locked_repository is missing")
    locked_head = str(locked_repository.get("head", ""))
    _require_ancestor(locked_head, execution_head)
    if published_head is not None:
        _require_ancestor(locked_head, published_head)
        _require_ancestor(published_head, execution_head)

    expected_runtime_contract = {
        "config": file_record(runtime_config, role="development_runtime_config"),
        "schema": file_record(runtime_schema, role="development_runtime_schema"),
        "status": EXPECTED_RUNTIME_STATUS,
    }
    if payload.get("runtime_contract") != expected_runtime_contract:
        raise DevelopmentRuntimeLockError("Runtime config/schema records drifted from E0-DL")
    _require_tracked_records_committed_at_head(
        [expected_runtime_contract["config"], expected_runtime_contract["schema"]],
        locked_head,
        context="runtime_contract",
    )
    expected_components = component_records(runtime)
    expected_dependencies = runtime_dependency_records(runtime)
    _require_exact_record_set(
        cast(Sequence[Any], payload["components"]),
        expected_components,
        context="components",
    )
    _require_exact_record_set(
        cast(Sequence[Any], payload["runtime_dependencies"]),
        expected_dependencies,
        context="runtime_dependencies",
    )
    _require_records_committed_at_head(payload["components"], locked_head, context="components")
    _require_records_committed_at_head(
        payload["runtime_dependencies"], locked_head, context="runtime_dependencies"
    )

    locked_restored = cast(Sequence[Any], payload["restored_development_sources"])
    if require_physical_artifacts:
        restored = restored_development_source_records(runtime)
        if locked_restored != restored:
            raise DevelopmentRuntimeLockError("Restored development-source records drifted")
    else:
        restored = _validate_restored_source_lock_metadata(locked_restored, runtime)
    common_origin = common_origin_lock_record(
        runtime,
        require_physical_artifact=require_physical_artifacts,
    )
    expert_state = expert_state_lock_record(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        require_physical_artifact=require_physical_artifacts,
    )
    locked_common_origin = cast(Mapping[str, Any], payload["common_origin"])
    locked_expert_state = cast(Mapping[str, Any], payload["expert_state"])
    if require_physical_artifacts:
        if locked_common_origin != common_origin:
            raise DevelopmentRuntimeLockError("Common-origin E0-DL record drifted")
        if locked_expert_state != expert_state:
            raise DevelopmentRuntimeLockError("Expert-state E0-DL record drifted")
    else:
        _locked_artifact_matches_observed_metadata(
            locked_common_origin,
            common_origin,
            context="common_origin",
        )
        _locked_artifact_matches_observed_metadata(
            locked_expert_state,
            expert_state,
            context="expert_state",
        )
        common_origin = dict(locked_common_origin)
        expert_state = dict(locked_expert_state)
    _require_records_committed_at_head(
        _materialized_artifact_git_records(common_origin, context="common_origin"),
        locked_head,
        context="common_origin_metadata",
    )
    _require_records_committed_at_head(
        _materialized_artifact_git_records(expert_state, context="expert_state"),
        locked_head,
        context="expert_state_metadata",
    )
    if require_physical_artifacts:
        expected_parents = parent_records(
            runtime,
            common_origin=common_origin,
            expert_state=expert_state,
        )
        _require_exact_record_set(
            cast(Sequence[Any], payload["parents"]),
            expected_parents,
            context="parents",
        )
    else:
        expected_parents = _validate_parent_lock_metadata(
            cast(Sequence[Any], payload["parents"]),
            runtime,
            common_origin=common_origin,
            expert_state=expert_state,
            restored_sources=restored,
        )
    _require_tracked_records_committed_at_head(
        cast(Sequence[Any], payload["parents"]),
        locked_head,
        context="parents",
        opaque_dvc_roles=OPAQUE_DVC_PARENT_ROLES,
    )

    dvc_evidence = cast(Mapping[str, Any], payload["dvc_remote_verification"])
    validate_dvc_remote_verification_evidence(
        dvc_evidence,
        runtime=runtime,
        common_origin=common_origin,
        expert_state=expert_state,
        verify_current_remote_config=require_physical_artifacts,
    )

    expected_planned = planned_artifact_records(
        runtime,
        locked_head=locked_head,
        expert_state=expert_state,
    )
    paths = [str(record["path"]) for record in expected_planned["records"]]
    digest = str(expected_planned["sha256"])
    planned = cast(Mapping[str, Any], payload["planned_artifacts"])
    if dict(planned) != expected_planned:
        raise DevelopmentRuntimeLockError(
            "Planned artifact records drifted from the pre-fit snapshot at locked H"
        )

    locked_environment = payload.get("environment")
    if not isinstance(locked_environment, Mapping):
        raise DevelopmentRuntimeLockError("Locked environment is missing")
    locked_device = str(locked_environment.get("device", ""))
    if device is not None and device != locked_device:
        raise DevelopmentRuntimeLockError(
            f"Requested device {device!r} differs from E0-DL device {locked_device!r}"
        )
    if require_physical_artifacts:
        current_environment = environment_payload(locked_device, runtime)
        if dict(locked_environment) != current_environment:
            raise DevelopmentRuntimeLockError("Execution environment drifted from E0-DL")

    verification = cast(Mapping[str, Any], payload["verification"])
    if tuple(verification["full_type_check"]["command"]) != TYPE_CHECK_COMMAND:
        raise DevelopmentRuntimeLockError("E0-DL type-check command drifted")
    expected_test_command = focused_test_command(runtime)
    if tuple(verification["focused_tests"]["command"]) != expected_test_command:
        raise DevelopmentRuntimeLockError("E0-DL focused-test command drifted")

    fit_predicates = {
        "payload_authorization_verified": payload.get("authorizations")
        == EXPECTED_AUTHORIZATIONS,
        "locked_parent_published_at_lock": True,
        "physical_artifacts_verified": require_physical_artifacts,
        "publication_verified": require_published,
        "live_git_remote_verified": remote_main_oid is not None,
        "canonical_origin_identity_verified": True,
        "common_origin_output_verified": require_physical_artifacts,
        "expert_state_output_verified": require_physical_artifacts,
        "restored_development_sources_verified": require_physical_artifacts,
        "dvc_remote_verified_at_lock": dvc_evidence.get(
            "dvc_remote_verified_at_lock"
        )
        is True,
        "locked_head_is_ancestor": True,
    }
    effective_fit_authorized = all(fit_predicates.values())
    summary = {
        "lock_path": relative_lock_path,
        "lock_sha256": _sha256_file(_resolve_repo_path(lock_path)),
        "lock_version": LOCK_VERSION,
        "status": "locked",
        "locked_repository_head": locked_head,
        "execution_head": execution_head,
        "published_ref": published_ref,
        "published_head": published_head,
        "remote_main_oid": remote_main_oid,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "publication_verified": require_published,
        "tracking_ref_publication_verified": require_published,
        "remote_publication_verified": remote_main_oid is not None,
        "canonical_origin_identity_verified": True,
        "component_count": len(expected_components),
        "planned_artifact_path_count": len(paths),
        "planned_artifact_paths_sha256": digest,
        "device": locked_device,
        "metadata_verified": True,
        "physical_artifacts_required": require_physical_artifacts,
        "physical_artifacts_verified": require_physical_artifacts,
        "common_origin_output_verified": require_physical_artifacts,
        "expert_state_output_verified": require_physical_artifacts,
        "restored_development_sources_verified": require_physical_artifacts,
        "dvc_remote_verified_at_lock": True,
        "dvc_remote_verified": True,
        "fit_authorization_predicates": fit_predicates,
        "payload_development_fit_authorized": True,
        "payload_evaluation_authorized": False,
        "payload_e0_u_authorized": False,
        "development_fit_authorized": effective_fit_authorized,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "fit_authorized": effective_fit_authorized,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_development_fit_authorized(
    *,
    device: str | None = None,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
) -> dict[str, Any]:
    """Fail closed unless published E0-DL authorizes development-only fit.

    Strict adapters must call this function before any modeling-row I/O.  The
    function performs configuration, byte-hash, DVC-pointer, environment and
    Git checks, plus the outcome-free expert-state semantic audit; it never
    reads scientific outcome rows.
    """
    runtime = load_yaml_mapping(runtime_config)
    configure_torch_cpu_execution_policy(runtime)
    implementation = runtime.get("implementation_lock")
    if not isinstance(implementation, Mapping):
        raise DevelopmentRuntimeLockError("Runtime implementation_lock is missing")
    lock_path = Path(str(implementation.get("lock_manifest_path", DEFAULT_LOCK_PATH)))
    lock_schema = Path(str(implementation.get("lock_schema_path", DEFAULT_LOCK_SCHEMA)))
    _, summary = load_and_validate_development_runtime_lock(
        lock_path,
        lock_schema,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        device=device,
        require_published=True,
        require_physical_artifacts=True,
    )
    required_predicates = {
        "physical_artifacts_verified": True,
        "publication_verified": True,
        "remote_publication_verified": True,
        "canonical_origin_identity_verified": True,
        "common_origin_output_verified": True,
        "expert_state_output_verified": True,
        "restored_development_sources_verified": True,
        "dvc_remote_verified_at_lock": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
    }
    failed = [
        field
        for field, expected in required_predicates.items()
        if summary.get(field) is not expected
    ]
    if failed:
        raise DevelopmentRuntimeLockError(
            f"E0-DL did not satisfy explicit development-fit predicates: {failed}"
        )
    if summary.get("evaluation_authorized") is not False or summary.get("e0_u_authorized") is not False:
        raise DevelopmentRuntimeLockError("E0-DL evaluation/E0-U seals drifted")
    return summary
