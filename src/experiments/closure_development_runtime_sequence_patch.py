#!/usr/bin/env python
"""Validate the additive Closure V1 E0-DLS sequence-serialization patch.

E0-DLS preserves the published E0-DL and E0-DLP locks.  It authorizes a
Parquet representation correction for logically null fixed-size tensors plus
fail-closed one-shot publication hardening.  Evaluation, E0-U, future outcomes,
and every scientific decision remain sealed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    validate_json_schema,
)
from src.experiments.closure_development_runtime_lock import (
    DEFAULT_LOCK_PATH as DEFAULT_BASE_LOCK_PATH,
    DEFAULT_LOCK_SCHEMA as DEFAULT_BASE_LOCK_SCHEMA,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
)
from src.experiments.closure_development_runtime_patch import (
    DEFAULT_PATCH_LOCK_MANIFEST_PATH as DEFAULT_BASE_PATCH_MANIFEST_PATH,
    DEFAULT_PATCH_LOCK_PATH as DEFAULT_BASE_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_SCHEMA as DEFAULT_BASE_PATCH_LOCK_SCHEMA,
    _base_lock_snapshot,
    _validate_dvc_remote_evidence,
    _validate_base_physical_authority,
    _validate_locked_models_owner,
    adopted_seed_bundle_record,
    environment_payload,
    validate_development_runtime_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_development_runtime_sequence_patch_lock_v1"
PATCH_GATE = "E0-DLS"
PATCH_ID = "development_runtime_sequence_serialization_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"

BASE_REPOSITORY_HEAD = "45705d620ad529b702624706b07e8a39fc138f72"
BASE_PATCH_HEAD = "5bb01e92b9b8c9b099b07b2f2cc5b8b9be359b30"
BASE_PATCH_LOCK_COMMIT = "9123b5120f9470bba8643c6f4c73b86f85ccec25"
PUBLISHED_REF = "origin/main"

DEFAULT_SEQUENCE_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock.json"
)
DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock_manifest.json"
)
DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json"
)

PATCH_MODIFIED_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/rollout_closure_pipe.py",
    "src/experiments/train_closure_pipe.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PATCH_COMPONENT_ROLES = {
    "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json": (
        "sequence_patch_lock_schema"
    ),
    "docs/closure_v1/E0_D_RUNTIME_SEQUENCE_PATCH_1.md": "sequence_patch_protocol",
    "src/experiments/build_closure_pipe_sequences.py": "sequence_builder",
    "src/experiments/closure_development_runtime_sequence_patch.py": (
        "sequence_patch_validator"
    ),
    "src/experiments/lock_closure_development_runtime_sequence_patch.py": (
        "sequence_patch_locker"
    ),
    "src/experiments/rollout_closure_pipe.py": "rollout_builder",
    "src/experiments/train_closure_pipe.py": "sequence_consumer",
    "tests/test_build_closure_pipe_sequences.py": "sequence_builder_tests",
    "tests/test_closure_development_runtime_sequence_patch.py": (
        "sequence_patch_tests"
    ),
    "tests/test_rollout_closure_pipe.py": "rollout_builder_tests",
    "tests/test_train_closure_pipe.py": "sequence_consumer_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS)

P0_SEQUENCE_PATH = Path(
    "data/closure_v1/development/sequences/P0/expert_no_current.parquet"
)
P0_SEQUENCE_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_summary.csv"
)
P0_SEQUENCE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"
)
P0_ONE_SHOT_PATHS = (
    P0_SEQUENCE_PATH,
    P0_SEQUENCE_PATH.with_suffix(P0_SEQUENCE_PATH.suffix + ".tmp"),
    Path(f"{P0_SEQUENCE_PATH.as_posix()}.dvc"),
    Path(f"{P0_SEQUENCE_PATH.as_posix()}.dvc.tmp"),
    P0_SEQUENCE_SUMMARY_PATH,
    P0_SEQUENCE_SUMMARY_PATH.with_suffix(P0_SEQUENCE_SUMMARY_PATH.suffix + ".tmp"),
    P0_SEQUENCE_MANIFEST_PATH,
    P0_SEQUENCE_MANIFEST_PATH.with_suffix(P0_SEQUENCE_MANIFEST_PATH.suffix + ".tmp"),
)

SEQUENCE_PATCH_TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
SEQUENCE_PATCH_FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_development_runtime_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_closure_development_runtime_lock.py",
    "tests/test_fit_closure_anfis_state.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_closure_development_runtime_sequence_patch.py",
    "-q",
)
SEQUENCE_PATCH_FOCUSED_TEST_COUNT = 310
SEQUENCE_PATCH_TEST_ENVIRONMENT = {
    "PYTEST_ADDOPTS": "",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTEST_PLUGINS": "",
    "PY_COLORS": "0",
}
SEQUENCE_PATCH_POETRY_CHECK_COMMAND = ("poetry", "check")
SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND = (
    "scripts/check_repo_publication_ready.sh",
)
SEQUENCE_PATCH_DIFF_CHECK_COMMAND = ("git", "diff", "--check")

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

BASE_AUTHORITY_RECORDS = {
    DEFAULT_BASE_PATCH_LOCK_PATH.as_posix(): {
        "path": DEFAULT_BASE_PATCH_LOCK_PATH.as_posix(),
        "role": "base_development_runtime_patch_lock",
        "bytes": 92_714,
        "sha256": "d15a471ca293de0b48e5b52c1b52527640f2bd1ac1233e6b0796c4afa127fac4",
    },
    DEFAULT_BASE_PATCH_MANIFEST_PATH.as_posix(): {
        "path": DEFAULT_BASE_PATCH_MANIFEST_PATH.as_posix(),
        "role": "base_development_runtime_patch_companion",
        "bytes": 2_052,
        "sha256": "ac0c84f0fffa458a64df351ad6c51d450bb8b7b4991d8ac38fa51c049b711b46",
    },
    DEFAULT_BASE_PATCH_LOCK_SCHEMA.as_posix(): {
        "path": DEFAULT_BASE_PATCH_LOCK_SCHEMA.as_posix(),
        "role": "base_development_runtime_patch_lock_schema",
        "bytes": 78_141,
        "sha256": "652fa86482b585985eb0db260af1e499ddc16a620b8fa8c6f54e87c5c767dbac",
    },
}

PATCH_AUTHORIZATIONS = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "scientific_decisions_changed": False,
    "common_origin_denominator_changed": False,
    "role_denominators_changed": False,
    "state_or_target_values_imputed": False,
    "runtime_config_changed": False,
    "base_e0_dl_replaced": False,
    "base_e0_dlp_replaced": False,
    "p0_materialized_at_lock": False,
    "evaluation_opened": False,
    "e0_u_opened": False,
    "future_outcomes_accessed": False,
    "dvc_operation_executed": False,
}
PATCH_CORRECTION = {
    "trigger_exception": (
        "pyarrow.lib.ArrowNotImplementedError: Lists with non-zero length null "
        "components are not supported"
    ),
    "upstream_reference": "apache/arrow#24425",
    "affected_storage": "Parquet",
    "sequence_physical_type": "fixed_size_list<float32>[12]",
    "sequence_failure_encoding": "outer_valid_with_12_null_float32_children",
    "sequence_logical_null_policy": "none_or_exact_shape_12_all_missing",
    "rollout_state_physical_type": "fixed_size_list<float32>[128]",
    "rollout_irc_physical_type": "fixed_size_list<float64>[128]",
    "rollout_failure_encoding": "outer_valid_with_128_null_children",
    "success_payload_changed": False,
    "scalar_target_null_encoding_changed": False,
    "failure_status_is_authoritative": True,
    "partially_null_tensor_accepted": False,
    "finite_failure_placeholder_accepted": False,
    "sequence_bundle_guard": "exclusive_ignored_guard_held_through_publication",
    "sequence_output_publication": "exclusive_temp_inode_hardlink_no_clobber",
}


class DevelopmentRuntimeSequencePatchError(RuntimeError):
    """Raised when E0-DLS is absent, unpublished, or inconsistent."""


def _resolve(path: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimeSequencePatchError(f"Path escapes repository: {path}") from exc
    return resolved


def _relative(path: Path) -> str:
    return _resolve(path).relative_to(PROJECT_ROOT.resolve()).as_posix()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_regular_bytes(path: Path, *, context: str) -> bytes:
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    try:
        before = resolved.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimeSequencePatchError(f"{context} is absent: {_relative(path)}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise DevelopmentRuntimeSequencePatchError(f"{context} is not a regular file: {_relative(path)}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise DevelopmentRuntimeSequencePatchError(f"{context} changed before reading")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    after = resolved.lstat()
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise DevelopmentRuntimeSequencePatchError(f"{context} changed while reading")
    return b"".join(chunks)


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    payload = _read_regular_bytes(path, context=role)
    return {
        "path": _relative(path),
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _decode_json(payload: bytes, *, context: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        decoded: dict[str, Any] = {}
        for key, value in pairs:
            if key in decoded:
                raise ValueError("duplicate JSON object key")
            decoded[key] = value
        return decoded

    def reject_nonfinite(_value: str) -> Any:
        raise ValueError("non-finite JSON number")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise DevelopmentRuntimeSequencePatchError(f"{context} is not canonical JSON") from exc
    if not isinstance(value, Mapping):
        raise DevelopmentRuntimeSequencePatchError(f"{context} must contain a JSON object")
    return dict(value)


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    return _decode_json(_read_regular_bytes(path, context=context), context=context)


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevelopmentRuntimeSequencePatchError("Bounded Git command timed out") from exc
    if result.returncode != 0:
        raise DevelopmentRuntimeSequencePatchError(
            f"Bounded Git command failed: {args[0] if args else 'unknown'}"
        )
    return result.stdout.strip()


def _require_commit(value: str, *, context: str) -> str:
    commit = value.strip().lower()
    if COMMIT_RE.fullmatch(commit) is None:
        raise DevelopmentRuntimeSequencePatchError(f"{context} is not a full commit OID")
    if _git("cat-file", "-t", commit) != "commit":
        raise DevelopmentRuntimeSequencePatchError(f"{context} does not resolve to a commit")
    return commit


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevelopmentRuntimeSequencePatchError("Bounded Git ancestry check timed out") from exc
    if result.returncode != 0:
        raise DevelopmentRuntimeSequencePatchError(
            f"Required ancestry is absent: {ancestor} -> {descendant}"
        )


def _git_blob(commit: str, path: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevelopmentRuntimeSequencePatchError("Bounded Git blob read timed out") from exc
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 128:
        return None
    raise DevelopmentRuntimeSequencePatchError(f"Unable to read required Git blob: {path}")


def _introduced_commit(path: str) -> str:
    commits = _git("log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    if len(commits) != 1:
        raise DevelopmentRuntimeSequencePatchError(
            f"Expected exactly one introduction commit for {path}: {commits}"
        )
    return _require_commit(commits[0], context=f"introduction commit for {path}")


def _path_digest(paths: Sequence[str]) -> str:
    payload = "\n".join(paths).encode("utf-8")
    return _sha256_bytes(payload)


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        list(records),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _expected_diff_entries() -> list[dict[str, str]]:
    return [
        {"status": "M" if path in PATCH_MODIFIED_PATHS else "A", "path": path}
        for path in PATCH_PATHS
    ]


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    output = _git("diff", "--name-status", "--no-renames", base, head)
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M"}:
            raise DevelopmentRuntimeSequencePatchError(f"E0-DLS forbids Git diff entry: {line}")
        entries.append({"status": fields[0], "path": fields[1]})
    return entries


def sequence_patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-DLS")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, BASE_REPOSITORY_HEAD]:
        raise DevelopmentRuntimeSequencePatchError(
            "H-DLS must be a direct non-merge child of the incident base"
        )
    entries = _observed_diff_entries(BASE_REPOSITORY_HEAD, patch_head)
    expected = _expected_diff_entries()
    if entries != expected:
        raise DevelopmentRuntimeSequencePatchError(
            f"H-DLS diff differs from the closed 6M+5A patch: {entries}"
        )
    return {
        "base_commit": BASE_REPOSITORY_HEAD,
        "patch_head": patch_head,
        "entries": entries,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def _component_records_at_head(patch_head: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in PATCH_PATHS:
        blob = _git_blob(patch_head, path)
        if blob is None:
            raise DevelopmentRuntimeSequencePatchError(f"H-DLS component is absent: {path}")
        records.append(
            {
                "path": path,
                "role": PATCH_COMPONENT_ROLES[path],
                "bytes": len(blob),
                "sha256": _sha256_bytes(blob),
            }
        )
    return records


def sequence_patch_component_bundle(patch_head: str) -> dict[str, Any]:
    records = _component_records_at_head(patch_head)
    return {
        "count": len(records),
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def _assert_records_physical_and_current(
    records: Sequence[Mapping[str, Any]],
    *,
    execution_head: str,
) -> None:
    for record in records:
        path = str(record["path"])
        physical = _file_record(Path(path), role=str(record["role"]))
        if dict(record) != physical:
            raise DevelopmentRuntimeSequencePatchError(f"E0-DLS physical component drifted: {path}")
        blob = _git_blob(execution_head, path)
        if blob is None or len(blob) != record["bytes"] or _sha256_bytes(blob) != record["sha256"]:
            raise DevelopmentRuntimeSequencePatchError(f"E0-DLS HEAD component drifted: {path}")


def _assert_paths_untouched(base: str, descendant: str, paths: Sequence[str], *, context: str) -> None:
    if base == descendant:
        return
    touched = _git("rev-list", "--full-history", f"{base}..{descendant}", "--", *paths)
    if touched:
        raise DevelopmentRuntimeSequencePatchError(f"{context} paths were touched after publication")


def _preserved_component_bundle(
    base_payload: Mapping[str, Any],
    patch_payload: Mapping[str, Any],
) -> dict[str, Any]:
    paths: set[str] = set()
    for field, context in (
        ("components", "Base E0-DL components"),
        ("runtime_dependencies", "Base E0-DL runtime dependencies"),
    ):
        collection = base_payload.get(field)
        if not isinstance(collection, Sequence) or isinstance(
            collection, (str, bytes)
        ):
            raise DevelopmentRuntimeSequencePatchError(f"{context} are malformed")
        for record in collection:
            if isinstance(record, Mapping) and isinstance(record.get("path"), str):
                paths.add(str(record["path"]))
    runtime_contract = base_payload.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        raise DevelopmentRuntimeSequencePatchError("Base E0-DL runtime contract is malformed")
    for key in ("config", "schema"):
        record = runtime_contract.get(key)
        if isinstance(record, Mapping) and isinstance(record.get("path"), str):
            paths.add(str(record["path"]))
    patch_components = patch_payload.get("patch_components")
    base_drift = patch_payload.get("base_component_drift")
    for collection, context in (
        (patch_components, "E0-DLP patch components"),
        (base_drift, "E0-DLP base component drift"),
    ):
        if not isinstance(collection, Mapping):
            raise DevelopmentRuntimeSequencePatchError(f"{context} is malformed")
        records = collection.get("records")
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise DevelopmentRuntimeSequencePatchError(f"{context} records are malformed")
        for record in records:
            if isinstance(record, Mapping) and isinstance(record.get("path"), str):
                paths.add(str(record["path"]))
    preserved_paths = tuple(sorted(paths.difference(PATCH_MODIFIED_PATHS)))
    records: list[dict[str, Any]] = []
    for path in preserved_paths:
        blob = _git_blob(BASE_REPOSITORY_HEAD, path)
        if blob is None:
            raise DevelopmentRuntimeSequencePatchError(
                f"Preserved authority component is absent at the incident base: {path}"
            )
        records.append(
            {
                "path": path,
                "role": "preserved_locked_component",
                "bytes": len(blob),
                "sha256": _sha256_bytes(blob),
            }
        )
    return {
        "count": len(records),
        "paths": list(preserved_paths),
        "paths_sha256": _path_digest(preserved_paths),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def _assert_preserved_components(
    bundle: Mapping[str, Any],
    *,
    execution_head: str,
) -> None:
    records = bundle.get("records")
    paths = bundle.get("paths")
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or not isinstance(paths, Sequence)
        or isinstance(paths, (str, bytes))
    ):
        raise DevelopmentRuntimeSequencePatchError("Preserved component bundle is malformed")
    typed_records = [
        cast(Mapping[str, Any], record)
        for record in records
        if isinstance(record, Mapping)
    ]
    typed_paths = [str(path) for path in paths]
    if len(typed_records) != len(records) or len(typed_paths) != len(paths):
        raise DevelopmentRuntimeSequencePatchError("Preserved component bundle is malformed")
    _assert_records_physical_and_current(typed_records, execution_head=execution_head)
    _assert_paths_untouched(
        BASE_REPOSITORY_HEAD,
        execution_head,
        typed_paths,
        context="Preserved E0-DL/E0-DLP components",
    )


def _validate_historical_e0_dlp_physical_authority(
    base: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    execution_head: str,
) -> None:
    base_physical = _validate_base_physical_authority(
        base,
        runtime_config=DEFAULT_RUNTIME_CONFIG,
        runtime_schema=DEFAULT_RUNTIME_SCHEMA,
        require_physical_artifacts=True,
    )
    runtime = cast(Mapping[str, Any], base_physical["runtime"])
    locked_bundle = cast(Mapping[str, Any], payload["adopted_seed_bundle"])
    locked_dvc = cast(Mapping[str, Any], locked_bundle["dvc"])
    locked_models_owner = cast(Mapping[str, Any], locked_dvc["models_owner"])
    _validate_locked_models_owner(
        locked_models_owner,
        patch_head=BASE_PATCH_HEAD,
    )
    observed_bundle = adopted_seed_bundle_record(
        base,
        require_physical_artifacts=True,
        locked_models_owner=locked_models_owner,
        execution_head=execution_head,
        runtime=runtime,
    )
    if locked_bundle != observed_bundle:
        raise DevelopmentRuntimeSequencePatchError(
            "Historical E0-DLP adopted seed bundle changed"
        )
    if payload.get("environment") != environment_payload("cpu", runtime):
        raise DevelopmentRuntimeSequencePatchError(
            "Historical E0-DLP execution environment drifted"
        )
    _validate_dvc_remote_evidence(
        cast(Mapping[str, Any], payload["dvc_remote_verification"]),
        locked_bundle,
        runtime=runtime,
        verify_current_remote_config=True,
    )


def _historical_authority_record(*, require_physical_artifacts: bool) -> dict[str, Any]:
    payload = _load_regular_json(DEFAULT_BASE_PATCH_LOCK_PATH, context="E0-DLP lock")
    schema = _load_regular_json(DEFAULT_BASE_PATCH_LOCK_SCHEMA, context="E0-DLP schema")
    try:
        validate_development_runtime_patch_lock_payload(payload, schema)
    except (ClosureContractError, RuntimeError, ValueError) as exc:
        raise DevelopmentRuntimeSequencePatchError(f"Historical E0-DLP validation failed: {exc}") from exc
    if cast(Mapping[str, Any], payload.get("patch_repository", {})).get("head") != BASE_PATCH_HEAD:
        raise DevelopmentRuntimeSequencePatchError("Historical E0-DLP patch head drifted")
    base_payload = _load_regular_json(DEFAULT_BASE_LOCK_PATH, context="E0-DL lock")
    observed_records: list[dict[str, Any]] = []
    for path in sorted(BASE_AUTHORITY_RECORDS):
        expected = BASE_AUTHORITY_RECORDS[path]
        observed = _file_record(Path(path), role=str(expected["role"]))
        if observed != expected:
            raise DevelopmentRuntimeSequencePatchError(f"Historical authority bytes drifted: {path}")
        blob = _git_blob(BASE_PATCH_LOCK_COMMIT, path)
        if blob is None or len(blob) != expected["bytes"] or _sha256_bytes(blob) != expected["sha256"]:
            raise DevelopmentRuntimeSequencePatchError(f"Historical authority Git blob drifted: {path}")
        observed_records.append(observed)
    if (
        _introduced_commit(DEFAULT_BASE_PATCH_LOCK_PATH.as_posix()) != BASE_PATCH_LOCK_COMMIT
        or _introduced_commit(DEFAULT_BASE_PATCH_MANIFEST_PATH.as_posix())
        != BASE_PATCH_LOCK_COMMIT
    ):
        raise DevelopmentRuntimeSequencePatchError("Historical E0-DLP publication commit drifted")
    ancestry = _git("rev-list", "--parents", "-n", "1", BASE_PATCH_LOCK_COMMIT).split()
    if ancestry != [BASE_PATCH_LOCK_COMMIT, BASE_PATCH_HEAD]:
        raise DevelopmentRuntimeSequencePatchError("Historical P-DLP topology drifted")
    expected_publication = [
        {"status": "A", "path": DEFAULT_BASE_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": DEFAULT_BASE_PATCH_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(BASE_PATCH_HEAD, BASE_PATCH_LOCK_COMMIT) != expected_publication:
        raise DevelopmentRuntimeSequencePatchError("Historical P-DLP diff drifted")
    _require_ancestor(BASE_PATCH_LOCK_COMMIT, BASE_REPOSITORY_HEAD)
    _assert_paths_untouched(
        BASE_PATCH_LOCK_COMMIT,
        _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD"),
        tuple(sorted(BASE_AUTHORITY_RECORDS)),
        context="Historical E0-DLP authority",
    )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    preserved_components = _preserved_component_bundle(base_payload, payload)
    _assert_preserved_components(preserved_components, execution_head=execution_head)
    if require_physical_artifacts:
        base = _base_lock_snapshot(DEFAULT_BASE_LOCK_PATH, DEFAULT_BASE_LOCK_SCHEMA)
        _validate_historical_e0_dlp_physical_authority(
            base,
            execution_head=execution_head,
            payload=payload,
        )
    return {
        "base_repository_head": BASE_REPOSITORY_HEAD,
        "e0_dlp_patch_head": BASE_PATCH_HEAD,
        "e0_dlp_lock_commit": BASE_PATCH_LOCK_COMMIT,
        "records": observed_records,
        "records_sha256": _record_digest(observed_records),
        "preserved_components": preserved_components,
        "base_e0_dl_unchanged": True,
        "base_e0_dlp_unchanged": True,
        "historical_schema_and_payload_validated": True,
        "physical_development_authority_verified": True,
        "e0_dlp_adopted_seed_physical_artifacts_verified": True,
    }


def assert_p0_one_shot_outputs_absent(
    paths: Sequence[Path] = P0_ONE_SHOT_PATHS,
) -> dict[str, Any]:
    relative_paths: list[str] = []
    for path in paths:
        resolved = path if path.is_absolute() else PROJECT_ROOT / path
        relative_paths.append(_relative(path))
        try:
            resolved.lstat()
        except FileNotFoundError:
            continue
        raise DevelopmentRuntimeSequencePatchError(
            f"P0 one-shot path must be absent at E0-DLS lock: {_relative(path)}"
        )
    return {
        "count": len(relative_paths),
        "paths": relative_paths,
        "paths_sha256": _path_digest(relative_paths),
        "all_absent_at_lock": True,
    }


def _remote_main_oid() -> str:
    output = _git("ls-remote", "--exit-code", "origin", "refs/heads/main")
    fields = output.split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise DevelopmentRuntimeSequencePatchError("Live origin/main response is malformed")
    return _require_commit(fields[0], context="live origin/main")


def collect_sequence_patch_prelock_state(
    *,
    require_physical_artifacts: bool = True,
    verify_remote: bool = True,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise DevelopmentRuntimeSequencePatchError(
            f"H-DLS locker requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-DLS HEAD")
    branch = _git("branch", "--show-current")
    if branch != "main":
        raise DevelopmentRuntimeSequencePatchError("H-DLS must be locked from branch main")
    git_diff = sequence_patch_git_diff_payload(head)
    components = sequence_patch_component_bundle(head)
    _assert_records_physical_and_current(
        cast(Sequence[Mapping[str, Any]], components["records"]),
        execution_head=head,
    )
    published_head = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published_head != head:
        raise DevelopmentRuntimeSequencePatchError("H-DLS must equal origin/main before locking")
    remote_oid = _remote_main_oid() if verify_remote else None
    if remote_oid is not None and remote_oid != head:
        raise DevelopmentRuntimeSequencePatchError("H-DLS differs from live origin/main")
    authority = _historical_authority_record(
        require_physical_artifacts=require_physical_artifacts
    )
    p0_absence = assert_p0_one_shot_outputs_absent()
    return {
        "base_authority": authority,
        "patch_repository": {
            "head": head,
            "parent": BASE_REPOSITORY_HEAD,
            "branch": "main",
            "published_ref": PUBLISHED_REF,
            "published_head": head,
            "remote_main_oid": head if remote_oid is not None else None,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "patch_components": components,
        "git_diff": git_diff,
        "p0_outputs": p0_absence,
    }


def _validate_command_evidence(
    evidence: Mapping[str, Any],
    *,
    command: Sequence[str],
    expected_test_count: int | None = None,
) -> None:
    stdout_line_count = evidence.get("stdout_line_count")
    stderr_line_count = evidence.get("stderr_line_count")
    base_fields = {
        "command",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
        "success_marker_verified",
    }
    focused_fields = {"test_count", "skipped_count", "deselected_count"}
    expected_fields = (
        base_fields | focused_fields if expected_test_count is not None else base_fields
    )
    if (
        set(evidence) != expected_fields
        or evidence.get("command") != list(command)
        or evidence.get("exit_code") != 0
        or evidence.get("success_marker_verified") is not True
        or isinstance(stdout_line_count, bool)
        or not isinstance(stdout_line_count, int)
        or stdout_line_count < 0
        or isinstance(stderr_line_count, bool)
        or not isinstance(stderr_line_count, int)
        or stderr_line_count < 0
        or SHA256_RE.fullmatch(str(evidence.get("stdout_sha256", ""))) is None
        or SHA256_RE.fullmatch(str(evidence.get("stderr_sha256", ""))) is None
    ):
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS command evidence drifted: {' '.join(command)}"
        )
    if expected_test_count is not None and (
        evidence.get("test_count") != expected_test_count
        or evidence.get("skipped_count") != 0
        or evidence.get("deselected_count") != 0
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS focused-test evidence drifted")


def validate_sequence_patch_verification(verification: Mapping[str, Any]) -> None:
    if set(verification) != {
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }:
        raise DevelopmentRuntimeSequencePatchError("E0-DLS verification set drifted")
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["full_type_check"]),
        command=SEQUENCE_PATCH_TYPE_CHECK_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["focused_tests"]),
        command=SEQUENCE_PATCH_FOCUSED_TEST_COMMAND,
        expected_test_count=SEQUENCE_PATCH_FOCUSED_TEST_COUNT,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["poetry_check"]),
        command=SEQUENCE_PATCH_POETRY_CHECK_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["publication_guard"]),
        command=SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["git_diff_check"]),
        command=SEQUENCE_PATCH_DIFF_CHECK_COMMAND,
    )


def build_sequence_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    validate_sequence_patch_verification(verification)
    return {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "base_authority": dict(cast(Mapping[str, Any], prelock["base_authority"])),
        "patch_repository": dict(cast(Mapping[str, Any], prelock["patch_repository"])),
        "patch_components": dict(cast(Mapping[str, Any], prelock["patch_components"])),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "compatibility_correction": dict(PATCH_CORRECTION),
        "p0_outputs": dict(cast(Mapping[str, Any], prelock["p0_outputs"])),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_sequence_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_development_runtime_sequence_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = False,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.development_runtime_sequence_patch_lock",
        )
    except ClosureContractError as exc:
        raise DevelopmentRuntimeSequencePatchError(str(exc)) from exc
    if (
        payload.get("lock_version") != LOCK_VERSION
        or payload.get("status") != PATCH_STATUS
        or payload.get("experiment_id") != EXPERIMENT_ID
        or payload.get("gate") != PATCH_GATE
        or payload.get("patch_id") != PATCH_ID
        or payload.get("compatibility_correction") != PATCH_CORRECTION
        or payload.get("authorizations") != PATCH_AUTHORIZATIONS
        or payload.get("seals") != PATCH_SEALS
        or payload.get("lock_artifact")
        != {
            "path": DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_sequence_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        }
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS fixed contract fields drifted")
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevelopmentRuntimeSequencePatchError("E0-DLS timestamp is invalid") from exc
    if timestamp.utcoffset() is None:
        raise DevelopmentRuntimeSequencePatchError("E0-DLS timestamp requires a timezone")
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="locked H-DLS")
    if repository != {
        "head": patch_head,
        "parent": BASE_REPOSITORY_HEAD,
        "branch": "main",
        "published_ref": PUBLISHED_REF,
        "published_head": patch_head,
        "remote_main_oid": patch_head,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise DevelopmentRuntimeSequencePatchError("E0-DLS patch repository record drifted")
    if payload.get("git_diff") != sequence_patch_git_diff_payload(patch_head):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS Git diff drifted")
    if payload.get("patch_components") != sequence_patch_component_bundle(patch_head):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS component bundle drifted")
    if payload.get("base_authority") != _historical_authority_record(
        require_physical_artifacts=require_physical_artifacts
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS historical authority drifted")
    expected_p0 = {
        "count": len(P0_ONE_SHOT_PATHS),
        "paths": [path.as_posix() for path in P0_ONE_SHOT_PATHS],
        "paths_sha256": _path_digest([path.as_posix() for path in P0_ONE_SHOT_PATHS]),
        "all_absent_at_lock": True,
    }
    if payload.get("p0_outputs") != expected_p0:
        raise DevelopmentRuntimeSequencePatchError("E0-DLS P0 absence evidence drifted")
    validate_sequence_patch_verification(cast(Mapping[str, Any], payload["verification"]))


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}

    def component(path: str, role: str) -> dict[str, Any]:
        record = by_path[path]
        return {
            "path": path,
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    authority = cast(Mapping[str, Any], payload["base_authority"])
    authority_records = cast(Sequence[Mapping[str, Any]], authority["records"])
    base_lock = next(
        record
        for record in authority_records
        if record["path"] == DEFAULT_BASE_PATCH_LOCK_PATH.as_posix()
    )
    return {
        "manifest_version": "closure_development_runtime_sequence_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_development_runtime_sequence_patch.py",
            "generating_script",
        ),
        "inputs": [
            {
                "path": base_lock["path"],
                "role": "base_development_runtime_patch_lock",
                "bytes": base_lock["bytes"],
                "sha256": base_lock["sha256"],
            },
            component(
                "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json",
                "sequence_patch_lock_schema",
            ),
            component(
                "src/experiments/closure_development_runtime_sequence_patch.py",
                "sequence_patch_validator",
            ),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
    }


def _validate_publication_bundle(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
    verify_remote: bool,
) -> tuple[str, str]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise DevelopmentRuntimeSequencePatchError("P-DLS lock and companion commits differ")
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise DevelopmentRuntimeSequencePatchError("P-DLS must be a direct child of H-DLS")
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise DevelopmentRuntimeSequencePatchError("P-DLS must add exactly lock plus companion")
    published_head = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if execution_head != published_head:
        raise DevelopmentRuntimeSequencePatchError("Execution HEAD differs from origin/main")
    remote_oid = _remote_main_oid() if verify_remote else published_head
    if remote_oid != published_head:
        raise DevelopmentRuntimeSequencePatchError("Local and live origin/main differ")
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="E0-DLS publication",
    )
    return lock_commit, published_head


def load_and_validate_development_runtime_sequence_patch_lock(
    lock_path: Path = DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
    lock_schema: Path = DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA,
    companion_path: Path = DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
    *,
    require_published: bool = True,
    require_physical_artifacts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        _relative(lock_path) != DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix()
        or _relative(lock_schema) != DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA.as_posix()
        or _relative(companion_path) != DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH.as_posix()
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS requires closed default paths")
    payload = _load_regular_json(lock_path, context="E0-DLS lock")
    schema = _load_regular_json(lock_schema, context="E0-DLS schema")
    validate_development_runtime_sequence_patch_lock_payload(
        payload,
        schema,
        require_physical_artifacts=require_physical_artifacts,
    )
    lock_record = _file_record(lock_path, role="external_development_runtime_sequence_patch_lock")
    companion = _load_regular_json(companion_path, context="E0-DLS companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS companion drifted")
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    records = cast(
        Sequence[Mapping[str, Any]],
        cast(Mapping[str, Any], payload["patch_components"])["records"],
    )
    _assert_records_physical_and_current(records, execution_head=execution_head)
    _assert_paths_untouched(
        patch_head,
        execution_head,
        PATCH_PATHS,
        context="E0-DLS components",
    )
    status = _git("status", "--porcelain", "--untracked-files=all")
    if require_published and status:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS execution requires a clean worktree: {status}"
        )
    if require_published:
        lock_commit, published_head = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=require_physical_artifacts,
        )
    else:
        if execution_head != patch_head:
            raise DevelopmentRuntimeSequencePatchError(
                "Unpublished E0-DLS validation must run at H-DLS"
            )
        lock_commit = ""
        published_head = ""
    effective = require_published and require_physical_artifacts
    summary = {
        "lock_path": DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
        "lock_sha256": lock_record["sha256"],
        "lock_version": LOCK_VERSION,
        "status": "locked",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": lock_commit or None,
        "execution_head": execution_head,
        "published_ref": PUBLISHED_REF if require_published else None,
        "published_head": published_head or None,
        "publication_verified": require_published,
        "remote_publication_verified": effective,
        "physical_artifacts_verified": require_physical_artifacts,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "development_fit_authorized": effective,
        "fit_authorized": effective,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_development_fit_authorized_with_sequence_patch(
    *,
    device: str | None = None,
) -> dict[str, Any]:
    """Fail closed unless published E0-DLS authorizes development-only work."""
    if device is not None and device != "cpu":
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS only authorizes the locked CPU device, not {device!r}"
        )
    _, summary = load_and_validate_development_runtime_sequence_patch_lock(
        require_published=True,
        require_physical_artifacts=True,
    )
    required = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "physical_artifacts_verified": True,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
    }
    failed = [field for field, expected in required.items() if summary.get(field) is not expected]
    if failed:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS did not satisfy development-fit predicates: {failed}"
        )
    if (
        summary.get("evaluation_authorized") is not False
        or summary.get("e0_u_authorized") is not False
        or summary.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS evaluation seals drifted")
    return summary


__all__ = [
    "BASE_REPOSITORY_HEAD",
    "DEFAULT_SEQUENCE_PATCH_LOCK_PATH",
    "DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA",
    "DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH",
    "DevelopmentRuntimeSequencePatchError",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_CORRECTION",
    "PATCH_GATE",
    "PATCH_ID",
    "PATCH_MODIFIED_PATHS",
    "PATCH_PATHS",
    "P0_ONE_SHOT_PATHS",
    "SEQUENCE_PATCH_DIFF_CHECK_COMMAND",
    "SEQUENCE_PATCH_FOCUSED_TEST_COMMAND",
    "SEQUENCE_PATCH_FOCUSED_TEST_COUNT",
    "SEQUENCE_PATCH_POETRY_CHECK_COMMAND",
    "SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND",
    "SEQUENCE_PATCH_TEST_ENVIRONMENT",
    "SEQUENCE_PATCH_TYPE_CHECK_COMMAND",
    "assert_p0_one_shot_outputs_absent",
    "build_sequence_patch_lock_payload",
    "collect_sequence_patch_prelock_state",
    "load_and_validate_development_runtime_sequence_patch_lock",
    "require_development_fit_authorized_with_sequence_patch",
    "sequence_patch_component_bundle",
    "sequence_patch_git_diff_payload",
    "validate_development_runtime_sequence_patch_lock_payload",
    "validate_sequence_patch_verification",
]
