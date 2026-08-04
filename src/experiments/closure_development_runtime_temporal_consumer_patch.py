#!/usr/bin/env python
"""Validate the additive Closure V1 temporal-consumer patch authority.

E0-DLT preserves the published E0-DL/E0-DLP/E0-DLS chain.  It records six
E0-DLS components as explicitly superseded, preserves the remaining five, and
binds the already published P0 sequence bundle before any temporal consumer is
allowed to run.  This module never grants evaluation, E0-U, holdout, or
post-2021 outcome access.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml

from src.experiments.closure_contract import (
    ClosureContractError,
    validate_json_schema,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_development_runtime_temporal_consumer_patch_lock_v1"
PATCH_GATE = "E0-DLT"
PATCH_ID = "development_runtime_temporal_consumer_atomicity_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
PUBLISHED_REF = "origin/main"

DLS_PATCH_HEAD = "b660a81d65ca8bf1d40ada2f083124f558c8a4c5"
DLS_LOCK_COMMIT = "92a9fb1ba17a61cb91c0b89782f2dd4bf956b5e1"
P0_BUNDLE_COMMIT = "b075d4f1606aa35c1b86493604c18845f2d28a2f"
PATCH_BASE_COMMIT = P0_BUNDLE_COMMIT
DLS_BASE_REPOSITORY_HEAD = "45705d620ad529b702624706b07e8a39fc138f72"
P_DLS_BASE_PRESERVED_COUNT = 40
P_DLS_BASE_PRESERVED_PATHS_SHA256 = (
    "59df505f57176cba4b737404da194bf0d48e58dbf729fa9a9704019fa4316322"
)
P_DLS_BASE_PRESERVED_RECORDS_SHA256 = (
    "65d1f5ed5338269b7f491111b16f02007d36fa23ffdfbe42f6d63f3e31c5ef33"
)

DEFAULT_DLS_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock.json"
)
DEFAULT_DLS_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock_manifest.json"
)
DEFAULT_DLS_SCHEMA_PATH = Path(
    "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_temporal_consumer_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "development_runtime_temporal_consumer_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_temporal_consumer_patch_lock.schema.json"
)

DLS_AUTHORITY_RECORDS = {
    DEFAULT_DLS_LOCK_PATH.as_posix(): {
        "path": DEFAULT_DLS_LOCK_PATH.as_posix(),
        "role": "base_development_runtime_sequence_patch_lock",
        "bytes": 24976,
        "sha256": "0e04e25c793aeba473cde7a55697172cda379aa55cf3ddb0d1ffce678db3bd61",
    },
    DEFAULT_DLS_MANIFEST_PATH.as_posix(): {
        "path": DEFAULT_DLS_MANIFEST_PATH.as_posix(),
        "role": "base_development_runtime_sequence_patch_companion",
        "bytes": 1853,
        "sha256": "71f6e0a9cf03c2798c730129fe154f879a7ae21279196582c420a01ec4c7b086",
    },
    DEFAULT_DLS_SCHEMA_PATH.as_posix(): {
        "path": DEFAULT_DLS_SCHEMA_PATH.as_posix(),
        "role": "base_development_runtime_sequence_patch_schema",
        "bytes": 13416,
        "sha256": "b78fc7a2576463bbe4491e49c6b24ed59b7f5fa878487392846878f7cc46f721",
    },
}

SUPERSEDED_COMPONENT_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/rollout_closure_pipe.py",
    "src/experiments/train_closure_pipe.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PRESERVED_DLS_COMPONENT_PATHS = (
    "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json",
    "docs/closure_v1/E0_D_RUNTIME_SEQUENCE_PATCH_1.md",
    "src/experiments/closure_development_runtime_sequence_patch.py",
    "src/experiments/lock_closure_development_runtime_sequence_patch.py",
    "tests/test_closure_development_runtime_sequence_patch.py",
)

PATCH_COMPONENT_ROLES = {
    "configs/closure_v1/development_runtime_temporal_consumer_patch_lock.schema.json": (
        "temporal_consumer_patch_lock_schema"
    ),
    "docs/closure_v1/E0_D_RUNTIME_TEMPORAL_CONSUMER_PATCH_1.md": (
        "temporal_consumer_patch_protocol"
    ),
    "src/experiments/build_closure_pipe_sequences.py": "sequence_builder_gate_routing",
    "src/experiments/closure_development_runtime_temporal_consumer_patch.py": (
        "temporal_consumer_patch_validator"
    ),
    "src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py": (
        "temporal_consumer_patch_locker"
    ),
    "src/experiments/rollout_closure_pipe.py": "rollout_gate_routing",
    "src/experiments/train_closure_pipe.py": "temporal_consumer",
    "tests/test_build_closure_pipe_sequences.py": "sequence_builder_gate_tests",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py": (
        "temporal_consumer_patch_tests"
    ),
    "tests/test_rollout_closure_pipe.py": "rollout_gate_tests",
    "tests/test_train_closure_pipe.py": "temporal_consumer_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in SUPERSEDED_COMPONENT_PATHS
)

P0_POINTER_PATH = Path(
    "data/closure_v1/development/sequences/P0/expert_no_current.parquet.dvc"
)
P0_PAYLOAD_PATH = Path(
    "data/closure_v1/development/sequences/P0/expert_no_current.parquet"
)
P0_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"
)
P0_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_summary.csv"
)
P0_BUNDLE_GIT_PATHS = (
    P0_POINTER_PATH.as_posix(),
    P0_MANIFEST_PATH.as_posix(),
    P0_SUMMARY_PATH.as_posix(),
    "src/experiments/audit_closure_p0_sequence_bundle.py",
    "tests/test_audit_closure_p0_sequence_bundle.py",
)
P0_BUNDLE_SHA256 = {
    P0_POINTER_PATH.as_posix(): "955ea4612f2fa705d05aac7e325db57ba728ef319536c1184528b8f02a54196a",
    P0_MANIFEST_PATH.as_posix(): "ec5c4a88eeb44c431484bced3053adf4f2824cda3db2a60ab9719f7be2f310fc",
    P0_SUMMARY_PATH.as_posix(): "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    "src/experiments/audit_closure_p0_sequence_bundle.py": (
        "07c40c63282c9de623e2fb0dc38de6e8735cd85fb3a9a1d932cd05a7ea5273b7"
    ),
    "tests/test_audit_closure_p0_sequence_bundle.py": (
        "01923d42d5d63135ea66907260ee5f1f2d688086477d6a299bec77e50995e672"
    ),
}
P0_PAYLOAD_SHA256 = "a10fbe5054d795b44dac1da2853a387b4dbead3e04dd7d9d942313b2aa5318fd"
P0_PAYLOAD_MD5 = "690735883981160b6347a722420603e0"
P0_PAYLOAD_BYTES = 1_377_124

REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
TEMPORAL_OUTPUT_NAMES = (
    "model",
    "checkpoint",
    "preprocessor",
    "metrics",
    "training_curve",
    "blend_weights",
    "blend_search",
    "report",
    "manifest",
)

PATCH_CORRECTION = {
    "classification": "implementation_hardening_only",
    "scientific_runtime_contract_changed": False,
    "seed_set_changed": False,
    "denominator_changed": False,
    "state_mapping_changed": False,
    "model_unavailable_semantics_changed": False,
    "consumer_publication": "exclusive_slot_guard_atomic_no_clobber_manifest_last",
    "consumer_failure_rollback": "owned_inode_only",
    "expected_p0_slot_status": "model_unavailable",
    "expected_p0_fit_status": "not_attempted",
    "expected_p0_failure_reason": "sequence_fit_rows_unavailable",
    "failed_slot_replacement": False,
}
PATCH_AUTHORIZATIONS = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "base_e0_dl_preserved": True,
    "base_e0_dlp_preserved": True,
    "base_e0_dls_preserved_as_historical_authority": True,
    "p0_sequence_bundle_preserved": True,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_development_runtime_sequence_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py",
    "-q",
)
FOCUSED_TEST_COUNT = 156
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
DVC_PUSH_COMMAND = (
    "scripts/dvc_data_assistant.sh",
    "push",
    "--target",
    P0_POINTER_PATH.as_posix(),
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class DevelopmentRuntimeTemporalConsumerPatchError(RuntimeError):
    """Raised when the additive E0-DLT authority is not exact."""


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_digest(paths: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(paths).encode("utf-8"))


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(
            list(records),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _resolve(path: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Path escapes repository: {path}"
        ) from exc
    return resolved


def _relative(path: Path) -> str:
    return _resolve(path).relative_to(PROJECT_ROOT.resolve()).as_posix()


def _read_regular_bytes(path: Path, *, context: str) -> bytes:
    logical = _relative(path)
    repository_root = PROJECT_ROOT.resolve()
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    try:
        relative = Path(os.path.abspath(candidate)).relative_to(repository_root)
    except ValueError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Path escapes repository: {path}"
        ) from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} path is not canonical: {logical}"
        )
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_descriptor = os.open(repository_root, directory_flags)
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Repository root could not be opened safely"
        ) from exc
    descriptor: int | None = None
    try:
        for component in relative.parts[:-1]:
            try:
                child = os.open(component, directory_flags, dir_fd=directory_descriptor)
            except FileNotFoundError as exc:
                raise DevelopmentRuntimeTemporalConsumerPatchError(
                    f"{context} is absent: {logical}"
                ) from exc
            except OSError as exc:
                raise DevelopmentRuntimeTemporalConsumerPatchError(
                    f"{context} contains an unavailable or linked ancestor: {logical}"
                ) from exc
            try:
                child_metadata = os.fstat(child)
                if not stat.S_ISDIR(child_metadata.st_mode):
                    raise DevelopmentRuntimeTemporalConsumerPatchError(
                        f"{context} contains a non-directory ancestor: {logical}"
                    )
            except BaseException:
                os.close(child)
                raise
            parent_descriptor = directory_descriptor
            directory_descriptor = child
            os.close(parent_descriptor)
        name = relative.parts[-1]
        try:
            before = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} is absent: {logical}"
            ) from exc
        except OSError as exc:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} could not be inspected safely: {logical}"
            ) from exc
        if not stat.S_ISREG(before.st_mode):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} is not a regular file: {logical}"
            )
        file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(name, file_flags, dir_fd=directory_descriptor)
        except OSError as exc:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} could not be opened safely: {logical}"
            ) from exc
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} changed before reading"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        opened_after = os.fstat(descriptor)
        try:
            named_after = os.stat(
                name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} disappeared while reading"
            ) from exc
        expected_identity = (before.st_dev, before.st_ino, before.st_size)
        if expected_identity != (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
        ) or expected_identity != (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
        ):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} changed while reading"
            )
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


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
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} is not canonical JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} must contain a JSON object"
        )
    return dict(value)


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    return _decode_json(_read_regular_bytes(path, context=context), context=context)


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    payload = _read_regular_bytes(path, context=role)
    return {
        "path": _relative(path),
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


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
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Bounded Git command timed out"
        ) from exc
    if result.returncode != 0:
        operation = args[0] if args else "unknown"
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Bounded Git command failed: {operation} (exit {result.returncode})"
        )
    return result.stdout.strip()


def _require_commit(value: str, *, context: str) -> str:
    commit = value.strip().lower()
    if COMMIT_RE.fullmatch(commit) is None:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} is not a full commit OID"
        )
    if _git("cat-file", "-t", commit) != "commit":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} does not resolve to a commit"
        )
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
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Bounded Git ancestry check timed out"
        ) from exc
    if result.returncode != 0:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
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
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Bounded Git blob read timed out"
        ) from exc
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 128:
        return None
    raise DevelopmentRuntimeTemporalConsumerPatchError(
        f"Unable to read required Git blob: {path}"
    )


def _introduced_commit(path: str) -> str:
    commits = _git("log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    if len(commits) != 1:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Expected one introduction commit for {path}: {commits}"
        )
    return _require_commit(commits[0], context=f"introduction commit for {path}")


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    output = _git("diff", "--name-status", "--no-renames", base, head)
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M"}:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"E0-DLT forbids Git diff entry: {line}"
            )
        entries.append({"status": fields[0], "path": fields[1]})
    return entries


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    if base == descendant:
        return
    touched = _git("rev-list", "--full-history", f"{base}..{descendant}", "--", *paths)
    if touched:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} paths were touched after publication"
        )


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-DLT")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "H-DLT must be a direct non-merge child of the published P0 bundle"
        )
    expected = [
        {
            "status": "M" if path in SUPERSEDED_COMPONENT_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    observed = _observed_diff_entries(PATCH_BASE_COMMIT, patch_head)
    if observed != expected:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"H-DLT diff differs from its closed allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-DLT")
    records: list[dict[str, Any]] = []
    for path in PATCH_PATHS:
        blob = _git_blob(patch_head, path)
        if blob is None:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"H-DLT component is absent: {path}"
            )
        records.append(
            {
                "path": path,
                "role": PATCH_COMPONENT_ROLES[path],
                "bytes": len(blob),
                "sha256": _sha256_bytes(blob),
            }
        )
    return {
        "count": len(records),
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def partition_dls_component_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_path = {str(record.get("path")): dict(record) for record in records}
    expected = set(SUPERSEDED_COMPONENT_PATHS).union(PRESERVED_DLS_COMPONENT_PATHS)
    if set(by_path) != expected or len(by_path) != len(records):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS component paths differ from the closed 6+5 partition"
        )
    superseded = [by_path[path] for path in SUPERSEDED_COMPONENT_PATHS]
    preserved = [by_path[path] for path in PRESERVED_DLS_COMPONENT_PATHS]
    return superseded, preserved


def _assert_record_at_commit(record: Mapping[str, Any], commit: str) -> None:
    path = str(record.get("path", ""))
    blob = _git_blob(commit, path)
    if (
        blob is None
        or len(blob) != record.get("bytes")
        or _sha256_bytes(blob) != record.get("sha256")
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Historical Git component drifted: {path}"
        )


def _assert_current_records(
    records: Sequence[Mapping[str, Any]],
    *,
    execution_head: str,
) -> None:
    for record in records:
        path = Path(str(record["path"]))
        physical = _file_record(path, role=str(record["role"]))
        if physical != dict(record):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Physical component drifted: {path.as_posix()}"
            )
        _assert_record_at_commit(record, execution_head)


def temporal_consumer_output_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for seed in REGISTERED_SEEDS:
        model_root = Path("models/closure_v1/pipe/P0")
        report_root = Path("reports/closure_v1/02_models/P0")
        finals = (
            model_root / f"seed_{seed}.pt",
            model_root / f"seed_{seed}.checkpoint.pt",
            report_root / f"seed_{seed}_preprocessor.json",
            report_root / f"seed_{seed}_metrics.csv",
            report_root / f"seed_{seed}_training_curve.csv",
            report_root / f"seed_{seed}_blend_weights.csv",
            report_root / f"seed_{seed}_blend_search.csv",
            report_root / f"seed_{seed}_report.md",
            report_root / f"seed_{seed}_manifest.json",
        )
        for final in finals:
            paths.extend((final, final.with_suffix(final.suffix + ".tmp")))
        paths.append(Path(f"tmp/closure_v1_temporal_consumer/P0_seed_{seed}.guard"))
    return tuple(paths)


def consumer_namespace_absence(
    paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    candidates = tuple(paths) if paths is not None else temporal_consumer_output_paths()
    relative = [_relative(path) for path in candidates]
    if len(relative) != len(set(relative)):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Temporal consumer absence paths must be unique"
        )
    existing: list[str] = []
    for path, logical in zip(candidates, relative, strict=True):
        resolved = path if path.is_absolute() else PROJECT_ROOT / path
        try:
            resolved.lstat()
        except FileNotFoundError:
            continue
        existing.append(logical)
    if existing:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Temporal consumer outputs must be absent at H-DLT lock: {existing}"
        )
    return {
        "model_id": "P0",
        "base_seeds": list(REGISTERED_SEEDS),
        "count": len(relative),
        "paths": relative,
        "paths_sha256": _path_digest(relative),
        "all_absent_at_lock": True,
    }


def _validate_p0_bundle(*, require_physical_artifacts: bool) -> dict[str, Any]:
    parent = _git("rev-list", "--parents", "-n", "1", P0_BUNDLE_COMMIT).split()
    if parent != [P0_BUNDLE_COMMIT, DLS_LOCK_COMMIT]:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "The P0 bundle must be a direct child of P-DLS"
        )
    expected_diff = [{"status": "A", "path": path} for path in P0_BUNDLE_GIT_PATHS]
    if _observed_diff_entries(DLS_LOCK_COMMIT, P0_BUNDLE_COMMIT) != expected_diff:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "The P0 bundle Git scope drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    records: list[dict[str, Any]] = []
    for path in P0_BUNDLE_GIT_PATHS:
        blob = _git_blob(P0_BUNDLE_COMMIT, path)
        expected_sha = P0_BUNDLE_SHA256[path]
        if blob is None or _sha256_bytes(blob) != expected_sha:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Published P0 Git blob drifted: {path}"
            )
        record = _file_record(Path(path), role="published_p0_bundle_component")
        if record["sha256"] != expected_sha or record["bytes"] != len(blob):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Physical P0 Git component drifted: {path}"
            )
        _assert_record_at_commit(record, execution_head)
        records.append(record)
    _assert_paths_untouched(
        P0_BUNDLE_COMMIT,
        execution_head,
        P0_BUNDLE_GIT_PATHS,
        context="Published P0 bundle",
    )

    payload_record = {
        "path": P0_PAYLOAD_PATH.as_posix(),
        "role": "p0_sequence_payload",
        "bytes": P0_PAYLOAD_BYTES,
        "sha256": P0_PAYLOAD_SHA256,
        "md5": P0_PAYLOAD_MD5,
    }
    pointer_bytes = _read_regular_bytes(P0_POINTER_PATH, context="P0 DVC pointer")
    if _sha256_bytes(pointer_bytes) != P0_BUNDLE_SHA256[P0_POINTER_PATH.as_posix()]:
        raise DevelopmentRuntimeTemporalConsumerPatchError("P0 DVC pointer drifted")
    try:
        pointer = yaml.safe_load(pointer_bytes)
    except yaml.YAMLError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P0 DVC pointer is not valid YAML"
        ) from exc
    if pointer != {
        "outs": [
            {
                "md5": P0_PAYLOAD_MD5,
                "size": P0_PAYLOAD_BYTES,
                "hash": "md5",
                "path": "expert_no_current.parquet",
            }
        ]
    }:
        raise DevelopmentRuntimeTemporalConsumerPatchError("P0 DVC pointer drifted")
    if require_physical_artifacts:
        payload = _read_regular_bytes(P0_PAYLOAD_PATH, context="P0 sequence payload")
        observed_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        if (
            len(payload) != P0_PAYLOAD_BYTES
            or _sha256_bytes(payload) != P0_PAYLOAD_SHA256
            or observed_md5 != P0_PAYLOAD_MD5
        ):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "P0 sequence payload hash or size drifted"
            )
    manifest = _load_regular_json(P0_MANIFEST_PATH, context="P0 sequence manifest")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P0 sequence manifest outputs are malformed"
        )
    parquet_records = [
        record
        for record in outputs
        if isinstance(record, Mapping)
        and record.get("path") == P0_PAYLOAD_PATH.as_posix()
    ]
    if parquet_records != [
        {
            "path": P0_PAYLOAD_PATH.as_posix(),
            "bytes": P0_PAYLOAD_BYTES,
            "sha256": P0_PAYLOAD_SHA256,
        }
    ]:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P0 sequence manifest does not bind the exact Parquet"
        )
    return {
        "commit": P0_BUNDLE_COMMIT,
        "parent": DLS_LOCK_COMMIT,
        "records": records,
        "records_sha256": _record_digest(records),
        "payload": payload_record,
        "pointer_md5": P0_PAYLOAD_MD5,
        "pointer_size": P0_PAYLOAD_BYTES,
        "physical_payload_verified": True,
        "future_outcomes_accessed": False,
    }


def _historical_dls_authority(*, require_physical_artifacts: bool) -> dict[str, Any]:
    from src.experiments.closure_development_runtime_sequence_patch import (
        validate_development_runtime_sequence_patch_lock_payload,
    )

    payload = _load_regular_json(DEFAULT_DLS_LOCK_PATH, context="P-DLS lock")
    schema = _load_regular_json(DEFAULT_DLS_SCHEMA_PATH, context="P-DLS schema")
    try:
        validate_development_runtime_sequence_patch_lock_payload(
            payload,
            schema,
            require_physical_artifacts=require_physical_artifacts,
        )
    except (ClosureContractError, RuntimeError, ValueError) as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Historical P-DLS validation failed: {exc}"
        ) from exc

    authority_records: list[dict[str, Any]] = []
    for path in sorted(DLS_AUTHORITY_RECORDS):
        expected = DLS_AUTHORITY_RECORDS[path]
        observed = _file_record(Path(path), role=str(expected["role"]))
        if observed != expected:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Historical P-DLS authority bytes drifted: {path}"
            )
        _assert_record_at_commit(expected, DLS_LOCK_COMMIT)
        authority_records.append(observed)
    if (
        _introduced_commit(DEFAULT_DLS_LOCK_PATH.as_posix()) != DLS_LOCK_COMMIT
        or _introduced_commit(DEFAULT_DLS_MANIFEST_PATH.as_posix()) != DLS_LOCK_COMMIT
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS lock and companion introduction commits drifted"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", DLS_LOCK_COMMIT).split()
    if ancestry != [DLS_LOCK_COMMIT, DLS_PATCH_HEAD]:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS must remain a direct child of H-DLS"
        )
    expected_publication = [
        {"status": "A", "path": DEFAULT_DLS_LOCK_PATH.as_posix()},
        {"status": "A", "path": DEFAULT_DLS_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(DLS_PATCH_HEAD, DLS_LOCK_COMMIT) != expected_publication:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS publication diff drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(DLS_LOCK_COMMIT, execution_head)
    _assert_paths_untouched(
        DLS_LOCK_COMMIT,
        execution_head,
        tuple(sorted(DLS_AUTHORITY_RECORDS)),
        context="P-DLS authority",
    )

    raw_base_authority = payload.get("base_authority")
    if not isinstance(raw_base_authority, Mapping):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS base authority is malformed"
        )
    raw_base_preserved = raw_base_authority.get("preserved_components")
    if not isinstance(raw_base_preserved, Mapping):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS base preserved-component bundle is malformed"
        )
    if set(raw_base_preserved) != {
        "count",
        "paths",
        "paths_sha256",
        "records",
        "records_sha256",
    }:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS base preserved-component dialect drifted"
        )
    raw_base_paths = raw_base_preserved.get("paths")
    raw_base_records = raw_base_preserved.get("records")
    if (
        raw_base_preserved.get("count") != P_DLS_BASE_PRESERVED_COUNT
        or raw_base_preserved.get("paths_sha256")
        != P_DLS_BASE_PRESERVED_PATHS_SHA256
        or raw_base_preserved.get("records_sha256")
        != P_DLS_BASE_PRESERVED_RECORDS_SHA256
        or not isinstance(raw_base_paths, Sequence)
        or isinstance(raw_base_paths, (str, bytes))
        or not isinstance(raw_base_records, Sequence)
        or isinstance(raw_base_records, (str, bytes))
        or len(raw_base_paths) != P_DLS_BASE_PRESERVED_COUNT
        or len(raw_base_records) != P_DLS_BASE_PRESERVED_COUNT
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS base preserved-component bundle drifted"
        )
    base_paths = [str(path) for path in raw_base_paths]
    base_records = [
        dict(record) for record in raw_base_records if isinstance(record, Mapping)
    ]
    if (
        len(base_records) != len(raw_base_records)
        or len(base_paths) != len(set(base_paths))
        or [record.get("path") for record in base_records] != base_paths
        or any(record.get("role") != "preserved_locked_component" for record in base_records)
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS base preserved-component records drifted"
        )
    _assert_current_records(base_records, execution_head=execution_head)
    _assert_paths_untouched(
        DLS_BASE_REPOSITORY_HEAD,
        execution_head,
        base_paths,
        context="P-DLS base preserved components",
    )

    components = cast(Mapping[str, Any], payload.get("patch_components"))
    raw_records = components.get("records")
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS component records are malformed"
        )
    component_records = [
        dict(record) for record in raw_records if isinstance(record, Mapping)
    ]
    if len(component_records) != len(raw_records):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLS component records are malformed"
        )
    superseded, preserved = partition_dls_component_records(component_records)
    for record in superseded:
        _assert_record_at_commit(record, DLS_PATCH_HEAD)
    _assert_current_records(preserved, execution_head=execution_head)
    _assert_paths_untouched(
        DLS_PATCH_HEAD,
        execution_head,
        PRESERVED_DLS_COMPONENT_PATHS,
        context="Preserved E0-DLS components",
    )
    return {
        "dls_patch_head": DLS_PATCH_HEAD,
        "dls_lock_commit": DLS_LOCK_COMMIT,
        "records": authority_records,
        "records_sha256": _record_digest(authority_records),
        "p_dls_base_preserved_components": dict(raw_base_preserved),
        "preserved_components": {
            "count": len(preserved),
            "paths": list(PRESERVED_DLS_COMPONENT_PATHS),
            "paths_sha256": _path_digest(PRESERVED_DLS_COMPONENT_PATHS),
            "records": preserved,
            "records_sha256": _record_digest(preserved),
        },
        "superseded_components": {
            "count": len(superseded),
            "paths": list(SUPERSEDED_COMPONENT_PATHS),
            "paths_sha256": _path_digest(SUPERSEDED_COMPONENT_PATHS),
            "historical_records": superseded,
            "historical_records_sha256": _record_digest(superseded),
            "historical_records_verified_at_h_dls": True,
            "current_bytes_required_to_match_h_dls": False,
        },
        "p_dls_payload_validated": True,
        "p_dls_companion_hash_validated": True,
        "physical_development_authority_verified": True,
        "p0_bundle": _validate_p0_bundle(
            require_physical_artifacts=require_physical_artifacts
        ),
    }


def _remote_main_oid() -> str:
    output = _git("ls-remote", "--exit-code", "origin", "refs/heads/main")
    fields = output.split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Live origin/main response is malformed"
        )
    return _require_commit(fields[0], context="live origin/main")


def collect_temporal_consumer_patch_prelock_state(
    *,
    require_physical_artifacts: bool = True,
    verify_remote: bool = True,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"H-DLT locker requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-DLT HEAD")
    if _git("branch", "--show-current") != "main":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "H-DLT must be locked from branch main"
        )
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    _assert_current_records(records, execution_head=head)
    published_head = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published_head != head:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "H-DLT must equal origin/main before locking"
        )
    remote_oid = _remote_main_oid() if verify_remote else None
    if remote_oid is not None and remote_oid != head:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "H-DLT differs from live origin/main"
        )
    authority = _historical_dls_authority(
        require_physical_artifacts=require_physical_artifacts
    )
    return {
        "base_authority": authority,
        "patch_repository": {
            "head": head,
            "parent": PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": PUBLISHED_REF,
            "published_head": head,
            "remote_main_oid": head if remote_oid is not None else None,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "patch_components": components,
        "git_diff": git_diff,
        "consumer_prelock": consumer_namespace_absence(),
    }


def _validate_command_evidence(
    evidence: Mapping[str, Any],
    *,
    command: Sequence[str],
    focused: bool = False,
    dvc: bool = False,
) -> None:
    required = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if focused:
        required.update({"test_count", "skipped_count", "deselected_count"})
    if dvc:
        required.add("terminal_status")
    if set(evidence) != required or evidence.get("command") != list(command):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT command evidence dialect drifted"
        )
    if evidence.get("returncode") != 0:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT verification command did not pass"
        )
    for key in ("stdout_sha256", "stderr_sha256"):
        if not isinstance(evidence.get(key), str) or SHA256_RE.fullmatch(
            cast(str, evidence[key])
        ) is None:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT command evidence hash drifted"
            )
    for key in ("stdout_line_count", "stderr_line_count"):
        if not isinstance(evidence.get(key), int) or cast(int, evidence[key]) < 0:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT command evidence line count drifted"
            )
    if focused and (
        not isinstance(evidence.get("test_count"), int)
        or evidence.get("test_count") != FOCUSED_TEST_COUNT
        or evidence.get("skipped_count") != 0
        or evidence.get("deselected_count") != 0
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT focused-test evidence drifted"
        )
    if dvc and evidence.get("terminal_status") != "Everything is up to date.":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT DVC evidence is not exact and idempotent"
        )


def validate_temporal_consumer_patch_verification(
    verification: Mapping[str, Any],
) -> None:
    if set(verification) != {
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "dvc_push_first",
        "dvc_push_second",
    }:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT verification set drifted"
        )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["full_type_check"]),
        command=TYPE_CHECK_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["focused_tests"]),
        command=FOCUSED_TEST_COMMAND,
        focused=True,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["poetry_check"]),
        command=POETRY_CHECK_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["publication_guard"]),
        command=PUBLICATION_GUARD_COMMAND,
    )
    _validate_command_evidence(
        cast(Mapping[str, Any], verification["git_diff_check"]),
        command=DIFF_CHECK_COMMAND,
    )
    for key in ("dvc_push_first", "dvc_push_second"):
        _validate_command_evidence(
            cast(Mapping[str, Any], verification[key]),
            command=DVC_PUSH_COMMAND,
            dvc=True,
        )


def build_temporal_consumer_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    validate_temporal_consumer_patch_verification(verification)
    return {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "base_authority": dict(cast(Mapping[str, Any], prelock["base_authority"])),
        "patch_repository": dict(
            cast(Mapping[str, Any], prelock["patch_repository"])
        ),
        "patch_components": dict(
            cast(Mapping[str, Any], prelock["patch_components"])
        ),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "correction": dict(PATCH_CORRECTION),
        "consumer_prelock": dict(
            cast(Mapping[str, Any], prelock["consumer_prelock"])
        ),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_temporal_consumer_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_development_runtime_temporal_consumer_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = False,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.development_runtime_temporal_consumer_patch_lock",
        )
    except ClosureContractError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(str(exc)) from exc
    fixed = {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "correction": PATCH_CORRECTION,
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_temporal_consumer_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"E0-DLT fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT timestamp is invalid"
        )
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT timestamp is invalid"
        ) from exc
    if timestamp.utcoffset() is None:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT timestamp requires a timezone"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="locked H-DLT")
    if repository != {
        "head": patch_head,
        "parent": PATCH_BASE_COMMIT,
        "branch": "main",
        "published_ref": PUBLISHED_REF,
        "published_head": patch_head,
        "remote_main_oid": patch_head,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise DevelopmentRuntimeTemporalConsumerPatchError("E0-DLT Git diff drifted")
    if payload.get("patch_components") != patch_component_bundle(patch_head):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT component bundle drifted"
        )
    if payload.get("base_authority") != _historical_dls_authority(
        require_physical_artifacts=require_physical_artifacts
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT historical authority drifted"
        )
    expected_absence = {
        "model_id": "P0",
        "base_seeds": list(REGISTERED_SEEDS),
        "count": len(temporal_consumer_output_paths()),
        "paths": [_relative(path) for path in temporal_consumer_output_paths()],
        "paths_sha256": _path_digest(
            [_relative(path) for path in temporal_consumer_output_paths()]
        ),
        "all_absent_at_lock": True,
    }
    if payload.get("consumer_prelock") != expected_absence:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT consumer prelock evidence drifted"
        )
    validate_temporal_consumer_patch_verification(
        cast(Mapping[str, Any], payload["verification"])
    )


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
    dls_lock = next(
        record
        for record in authority_records
        if record["path"] == DEFAULT_DLS_LOCK_PATH.as_posix()
    )
    dls_companion = next(
        record
        for record in authority_records
        if record["path"] == DEFAULT_DLS_MANIFEST_PATH.as_posix()
    )
    p0_bundle = cast(Mapping[str, Any], authority["p0_bundle"])
    p0_records = cast(Sequence[Mapping[str, Any]], p0_bundle["records"])
    p0_by_path = {str(record["path"]): record for record in p0_records}

    def authority_input(record: Mapping[str, Any], role: str) -> dict[str, Any]:
        return {
            "path": record["path"],
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    return {
        "manifest_version": "closure_development_runtime_temporal_consumer_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py",
            "generating_script",
        ),
        "inputs": [
            dict(dls_lock),
            dict(dls_companion),
            component(
                DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
                "temporal_consumer_patch_lock_schema",
            ),
            component(
                "src/experiments/closure_development_runtime_temporal_consumer_patch.py",
                "temporal_consumer_patch_validator",
            ),
            authority_input(
                p0_by_path[P0_POINTER_PATH.as_posix()],
                "published_p0_sequence_dvc_pointer",
            ),
            authority_input(
                p0_by_path[P0_MANIFEST_PATH.as_posix()],
                "published_p0_sequence_manifest",
            ),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
    }


def _validate_publication_bundle(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
    verify_remote: bool,
) -> tuple[str, str]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLT lock and companion commits differ"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLT must be a direct child of H-DLT"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "P-DLT must add exactly lock plus companion"
        )
    published_head = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if execution_head != published_head:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Execution HEAD differs from origin/main"
        )
    remote_oid = _remote_main_oid() if verify_remote else published_head
    if remote_oid != published_head:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "Local and live origin/main differ"
        )
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="E0-DLT publication",
    )
    return lock_commit, published_head


def load_and_validate_development_runtime_temporal_consumer_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    lock_schema: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    companion_path: Path = DEFAULT_PATCH_MANIFEST_PATH,
    *,
    require_published: bool = True,
    require_physical_artifacts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        _relative(lock_path) != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or _relative(lock_schema) != DEFAULT_PATCH_LOCK_SCHEMA.as_posix()
        or _relative(companion_path) != DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT requires closed default paths"
        )
    payload = _load_regular_json(lock_path, context="E0-DLT lock")
    schema = _load_regular_json(lock_schema, context="E0-DLT schema")
    validate_development_runtime_temporal_consumer_patch_lock_payload(
        payload,
        schema,
        require_physical_artifacts=require_physical_artifacts,
    )
    lock_record = _file_record(
        lock_path,
        role="external_development_runtime_temporal_consumer_patch_lock",
    )
    companion = _load_regular_json(companion_path, context="E0-DLT companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT companion drifted"
        )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    records = cast(
        Sequence[Mapping[str, Any]],
        cast(Mapping[str, Any], payload["patch_components"])["records"],
    )
    _assert_current_records(records, execution_head=execution_head)
    _assert_paths_untouched(
        patch_head,
        execution_head,
        PATCH_PATHS,
        context="E0-DLT components",
    )
    status = _git("status", "--porcelain", "--untracked-files=all")
    if require_published and status:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT execution requires a clean worktree: {status}"
        )
    if require_published:
        lock_commit, published_head = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=require_physical_artifacts,
        )
    else:
        if execution_head != patch_head:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "Unpublished E0-DLT validation must run at H-DLT"
            )
        lock_commit = ""
        published_head = ""
    effective = require_published and require_physical_artifacts
    summary = {
        "lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
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
        "development_fit_authorized": effective,
        "fit_authorized": effective,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_development_fit_authorized_with_temporal_consumer_patch(
    *,
    device: str | None = None,
) -> dict[str, Any]:
    """Fail closed until the additive P-DLT lock is committed and published."""
    if device is not None and device != "cpu":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT only authorizes the locked CPU device, not {device!r}"
        )
    _, summary = load_and_validate_development_runtime_temporal_consumer_patch_lock(
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
        "development_fit_authorized": True,
        "fit_authorized": True,
    }
    failed = [field for field, expected in required.items() if summary.get(field) is not expected]
    if failed:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT did not satisfy development-fit predicates: {failed}"
        )
    if (
        summary.get("evaluation_authorized") is not False
        or summary.get("e0_u_authorized") is not False
        or summary.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT evaluation seals drifted"
        )
    return summary


__all__ = [
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "DevelopmentRuntimeTemporalConsumerPatchError",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_PATHS",
    "PRESERVED_DLS_COMPONENT_PATHS",
    "SUPERSEDED_COMPONENT_PATHS",
    "build_temporal_consumer_patch_lock_payload",
    "collect_temporal_consumer_patch_prelock_state",
    "consumer_namespace_absence",
    "load_and_validate_development_runtime_temporal_consumer_patch_lock",
    "partition_dls_component_records",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "require_development_fit_authorized_with_temporal_consumer_patch",
    "temporal_consumer_output_paths",
    "validate_development_runtime_temporal_consumer_patch_lock_payload",
    "validate_temporal_consumer_patch_verification",
]
