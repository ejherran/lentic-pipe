#!/usr/bin/env python
"""Reopen and audit the immutable Closure V1 P0 sequence bundle read-only."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.experiments.build_closure_pipe_sequences import (
    COMMON_ORIGIN_REQUIRED_COLUMNS,
    DEFAULT_COMMON_COMPLETION,
    DEFAULT_COMMON_ORIGINS,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_LOCK,
    DEFAULT_RUNTIME_SCHEMA,
    EXPECTED_INTENT_ORIGINS,
    EXPECTED_INTENT_ORIGINS_BY_ROLE,
    HISTORY_LENGTH,
    INPUT_COLUMNS,
    MODEL_STATE_MAPPINGS,
    SEQUENCE_COLUMNS,
    SURFACE_ID,
    TARGET_COLUMNS,
    TARGET_TO_NEXT_INPUT_MAPPING,
    SequenceBuildAudit,
    build_closure_pipe_sequences,
    expected_cpu_execution_policy_record,
    sequence_arrow_table,
    state_projection_columns,
)
from src.experiments.closure_development_guard import (
    ASSIGNMENT_DEVELOPMENT,
    ASSIGNMENT_HOLDOUT,
    DEFAULT_ASSIGNMENT,
    DEFAULT_HOLDOUT_MANIFEST,
    DEFAULT_PROTOCOL_LOCK,
    validate_assignment_frame,
)
AUDIT_VERSION = "closure_p0_sequence_bundle_audit_v1"
CHECK_ONLY_FLAG = "--check-only"
P0_STATE_PATH = Path(
    "data/closure_v1/development/expert/expert_no_current_state.parquet"
)
P0_STATE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"
)
P0_SEQUENCE_PATH = Path(
    "data/closure_v1/development/sequences/P0/expert_no_current.parquet"
)
P0_POINTER_PATH = Path(f"{P0_SEQUENCE_PATH.as_posix()}.dvc")
P0_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_summary.csv"
)
P0_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"
)
P0_GUARD_DIRECTORY = Path("tmp/closure_v1_sequence_builder")
P_DLS_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock.json"
)
P_DLS_COMPANION_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "development_runtime_sequence_patch_lock_manifest.json"
)
AUDITOR_PATH = Path("src/experiments/audit_closure_p0_sequence_bundle.py")
RECONSTRUCTION_SOURCE_PATHS = (
    Path("src/experiments/build_closure_pipe_sequences.py"),
    Path("src/experiments/build_closure_holdout.py"),
    Path("src/experiments/closure_contract.py"),
    Path("src/experiments/closure_development_guard.py"),
    Path("src/experiments/closure_runtime_contract.py"),
)

EXPECTED_P_DLS_RECORDS = {
    P_DLS_LOCK_PATH.as_posix(): {
        "path": P_DLS_LOCK_PATH.as_posix(),
        "bytes": 24_976,
        "sha256": "0e04e25c793aeba473cde7a55697172cda379aa55cf3ddb0d1ffce678db3bd61",
    },
    P_DLS_COMPANION_PATH.as_posix(): {
        "path": P_DLS_COMPANION_PATH.as_posix(),
        "bytes": 1_853,
        "sha256": "71f6e0a9cf03c2798c730129fe154f879a7ae21279196582c420a01ec4c7b086",
    },
}
EXPECTED_P0_RECORDS = {
    P0_SEQUENCE_PATH.as_posix(): {
        "path": P0_SEQUENCE_PATH.as_posix(),
        "bytes": 1_377_124,
        "sha256": "a10fbe5054d795b44dac1da2853a387b4dbead3e04dd7d9d942313b2aa5318fd",
    },
    P0_SUMMARY_PATH.as_posix(): {
        "path": P0_SUMMARY_PATH.as_posix(),
        "bytes": 356,
        "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    },
    P0_MANIFEST_PATH.as_posix(): {
        "path": P0_MANIFEST_PATH.as_posix(),
        "bytes": 5_954,
        "sha256": "ec5c4a88eeb44c431484bced3053adf4f2824cda3db2a60ab9719f7be2f310fc",
    },
}
EXPECTED_STATUS_COUNTS = {
    "success": 9_227,
    "autoregressive_target_unavailable": 505,
}
EXPECTED_FAILURE_REASON_COUNTS = {"missing_target_state": 505}
EXPECTED_FIT_STATUS_COUNTS = {
    "success": 8_925,
    "autoregressive_target_unavailable": 488,
}
EXPECTED_FIT_FAILURE_REASON_COUNTS = {"missing_target_state": 488}
EXPECTED_CALIBRATION_FAILURES = 17
EXPECTED_ASSIGNMENT_COUNTS = {
    "eligible_locations": 441,
    "development_locations": 353,
    "holdout_locations": 88,
}
FIT_ROLES = ("training", "model_selection")
P_DLS_PATCH_HEAD = "b660a81d65ca8bf1d40ada2f083124f558c8a4c5"
DVC_POINTER_PATTERN = re.compile(
    rb"outs:\n"
    rb"- md5: (?P<md5>[0-9a-f]{32})\n"
    rb"  size: (?P<size>0|[1-9][0-9]*)\n"
    rb"  hash: md5\n"
    rb"  path: expert_no_current\.parquet\n"
)

MANIFEST_KEYS = {
    "manifest_version",
    "status",
    "generated_at_utc",
    "experiment_id",
    "surface_id",
    "model_id",
    "base_seed",
    "future_outcomes_accessed",
    "evaluation_authorized",
    "e0_u_authorized",
    "script",
    "cpu_execution_policy",
    "input_state_mapping",
    "target_state_mapping",
    "target_to_next_input_mapping",
    "input_columns",
    "target_columns",
    "optional_context_columns",
    "serialization",
    "counts",
    "inputs",
    "source_code",
    "outputs",
    "completion_marker_written_last",
}
MANIFEST_COUNT_KEYS = {
    "intent_origins",
    "successful_origins",
    "failed_origins",
    "role_counts",
    "status_counts",
    "failure_reason_counts",
    "delta_previous_month_missing_count",
    "delta_previous_month_missing_history_values",
    "delta_previous_month_missing_target_values",
    "holdout_overlap",
    "post_2021_rows",
}


class ClosureP0SequenceAuditError(ValueError):
    """Raised when the physical P0 bundle differs from its closed evidence."""


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_mode),
        int(metadata.st_uid),
        int(metadata.st_gid),
        int(metadata.st_nlink),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
        int(metadata.st_ctime_ns),
    )


@dataclass(frozen=True)
class _PinnedFile:
    relative_path: Path
    descriptor: int
    parent_parts: tuple[str, ...]
    name: str
    payload: bytes
    fingerprint: tuple[int, ...]

    @property
    def record(self) -> dict[str, Any]:
        return {
            "path": self.relative_path.as_posix(),
            "bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    @property
    def snapshot(self) -> dict[str, Any]:
        metadata = self.fingerprint
        return {
            **self.record,
            "device": metadata[0],
            "inode": metadata[1],
            "mode": stat.S_IMODE(metadata[2]),
            "uid": metadata[3],
            "gid": metadata[4],
            "links": metadata[5],
            "mtime_ns": metadata[7],
            "ctime_ns": metadata[8],
        }


class _RepoReadSession:
    """Pin repository files and directories for one mutation-free audit."""

    def __init__(self, root: Path) -> None:
        self.root = Path(os.path.abspath(root))
        self._directories: dict[tuple[str, ...], tuple[int, tuple[int, ...]]] = {}
        self._files: dict[str, _PinnedFile] = {}
        self._absent: set[tuple[tuple[str, ...], str]] = set()
        self._closed = False

    def __enter__(self) -> _RepoReadSession:
        for required in ("O_DIRECTORY", "O_NOFOLLOW"):
            if not hasattr(os, required):
                raise ClosureP0SequenceAuditError(
                    f"Secure audit reads require os.{required}"
                )
        if not hasattr(os, "pread"):
            raise ClosureP0SequenceAuditError("Secure audit reads require os.pread")
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(self.root, flags)
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                "Repository root cannot be opened without following links"
            ) from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosureP0SequenceAuditError("Repository root is not a real directory")
        except BaseException:
            os.close(descriptor)
            raise
        self._directories[()] = (descriptor, _fingerprint(metadata))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        verification_error: BaseException | None = None
        close_error: BaseException | None = None
        try:
            self.verify_unchanged()
        except BaseException as caught:  # preserve physical drift over a semantic error
            verification_error = caught
        try:
            self.close()
        except BaseException as caught:
            close_error = caught
        if verification_error is not None:
            if exc is not None:
                raise verification_error from exc
            if close_error is not None:
                raise verification_error from close_error
            raise verification_error
        if close_error is not None:
            if exc is not None:
                raise close_error from exc
            raise close_error
        return False

    def _relative(self, path: Path) -> Path:
        candidate = path if path.is_absolute() else self.root / path
        absolute = Path(os.path.abspath(candidate))
        try:
            relative = absolute.relative_to(self.root)
        except ValueError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit path escapes the repository: {path}"
            ) from exc
        if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            raise ClosureP0SequenceAuditError(f"Audit file path is not canonical: {path}")
        return relative

    def _open_directory(self, parts: tuple[str, ...]) -> int:
        if parts in self._directories:
            return self._directories[parts][0]
        parent_parts = parts[:-1]
        parent = self._open_directory(parent_parts)
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(parts[-1], flags, dir_fd=parent)
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit ancestor is absent, linked, or not a directory: {'/'.join(parts)}"
            ) from exc
        transferred = False
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosureP0SequenceAuditError(
                    f"Audit ancestor is not a real directory: {'/'.join(parts)}"
                )
            self._directories[parts] = (descriptor, _fingerprint(metadata))
            transferred = True
            return descriptor
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit ancestor cannot be inspected safely: {'/'.join(parts)}"
            ) from exc
        finally:
            if not transferred:
                os.close(descriptor)

    def pin(self, path: Path) -> _PinnedFile:
        relative = self._relative(path)
        key = relative.as_posix()
        if key in self._files:
            return self._files[key]
        parent_parts = tuple(relative.parts[:-1])
        parent = self._open_directory(parent_parts)
        flags = (
            os.O_RDONLY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(relative.name, flags, dir_fd=parent)
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Required audit file is absent, linked, or unreadable: {key}"
            ) from exc
        transferred = False
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ClosureP0SequenceAuditError(
                    f"Audit input is not a regular file: {key}"
                )
            before_fingerprint = _fingerprint(before)
            chunks: list[bytes] = []
            offset = 0
            while chunk := os.pread(descriptor, 1024 * 1024, offset):
                chunks.append(chunk)
                offset += len(chunk)
            payload = b"".join(chunks)
            after = os.fstat(descriptor)
            if before_fingerprint != _fingerprint(after) or len(payload) != before.st_size:
                raise ClosureP0SequenceAuditError(f"Audit file changed while reading: {key}")
            lexical = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
            if _fingerprint(lexical) != before_fingerprint:
                raise ClosureP0SequenceAuditError(
                    f"Audit file identity changed while reading: {key}"
                )
            pinned = _PinnedFile(
                relative_path=relative,
                descriptor=descriptor,
                parent_parts=parent_parts,
                name=relative.name,
                payload=payload,
                fingerprint=before_fingerprint,
            )
            self._files[key] = pinned
            transferred = True
            return pinned
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit file cannot be inspected safely: {key}"
            ) from exc
        finally:
            if not transferred:
                os.close(descriptor)

    def list_directory(self, path: Path, *, allow_absent: bool = False) -> list[str] | None:
        relative = self._relative(path / ".audit-directory-placeholder").parent
        parts = tuple(relative.parts)
        if parts in self._directories:
            return sorted(os.listdir(self._directories[parts][0]))
        parent_parts = parts[:-1]
        parent = self._open_directory(parent_parts)
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(parts[-1], flags, dir_fd=parent)
        except FileNotFoundError:
            if not allow_absent:
                raise ClosureP0SequenceAuditError(
                    f"Required audit directory is absent: {relative.as_posix()}"
                )
            self._absent.add((parent_parts, parts[-1]))
            return None
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit namespace is linked or not a directory: {relative.as_posix()}"
            ) from exc
        transferred = False
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosureP0SequenceAuditError(
                    f"Audit namespace is not a real directory: {relative.as_posix()}"
                )
            entries = sorted(os.listdir(descriptor))
            self._directories[parts] = (descriptor, _fingerprint(metadata))
            transferred = True
            return entries
        except OSError as exc:
            raise ClosureP0SequenceAuditError(
                f"Audit namespace cannot be inspected safely: {relative.as_posix()}"
            ) from exc
        finally:
            if not transferred:
                os.close(descriptor)

    def verify_unchanged(self) -> None:
        if self._closed:
            return
        for pinned in self._files.values():
            if _fingerprint(os.fstat(pinned.descriptor)) != pinned.fingerprint:
                raise ClosureP0SequenceAuditError(
                    f"Pinned audit file changed: {pinned.relative_path.as_posix()}"
                )
            parent = self._directories[pinned.parent_parts][0]
            try:
                lexical = os.stat(pinned.name, dir_fd=parent, follow_symlinks=False)
            except OSError as exc:
                raise ClosureP0SequenceAuditError(
                    f"Pinned audit filename changed: {pinned.relative_path.as_posix()}"
                ) from exc
            if _fingerprint(lexical) != pinned.fingerprint:
                raise ClosureP0SequenceAuditError(
                    f"Pinned audit filename changed: {pinned.relative_path.as_posix()}"
                )
        directory_paths: list[tuple[str, ...]] = sorted(
            self._directories,
            key=lambda item: len(item),
            reverse=True,
        )
        for parts in directory_paths:
            descriptor, expected = self._directories[parts]
            if _fingerprint(os.fstat(descriptor)) != expected:
                label = "/".join(parts) or "."
                raise ClosureP0SequenceAuditError(f"Pinned audit directory changed: {label}")
            if parts:
                parent = self._directories[parts[:-1]][0]
                try:
                    lexical = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                except OSError as exc:
                    raise ClosureP0SequenceAuditError(
                        f"Pinned audit directory name changed: {'/'.join(parts)}"
                    ) from exc
                if _fingerprint(lexical) != expected:
                    raise ClosureP0SequenceAuditError(
                        f"Pinned audit directory name changed: {'/'.join(parts)}"
                    )
        for parent_parts, name in self._absent:
            parent = self._directories[parent_parts][0]
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ClosureP0SequenceAuditError(
                f"Forbidden audit namespace appeared: {'/'.join((*parent_parts, name))}"
            )

    def close(self) -> None:
        if self._closed:
            return
        errors: list[OSError] = []
        for pinned in self._files.values():
            try:
                os.close(pinned.descriptor)
            except OSError as exc:
                errors.append(exc)
        directory_paths: list[tuple[str, ...]] = sorted(
            self._directories,
            key=lambda item: len(item),
            reverse=True,
        )
        for parts in directory_paths:
            try:
                os.close(self._directories[parts][0])
            except OSError as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            raise ClosureP0SequenceAuditError(
                f"Failed to close {len(errors)} pinned audit descriptor(s)"
            ) from errors[0]


def _read_pinned(path: Path) -> _PinnedFile:
    with _RepoReadSession(PROJECT_ROOT) as session:
        pinned = session.pin(path)
    return pinned


def _decode_strict_json(payload_bytes: bytes, *, path: str) -> dict[str, Any]:

    def reject_constant(value: str) -> None:
        raise ClosureP0SequenceAuditError(
            f"JSON contains a non-finite constant in {path}: {value}"
        )

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ClosureP0SequenceAuditError(
                    f"JSON contains a duplicate key in {path}: {key}"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            payload_bytes.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureP0SequenceAuditError(f"JSON cannot be decoded strictly: {path}") from exc
    if not isinstance(payload, dict):
        raise ClosureP0SequenceAuditError(f"JSON root must be an object: {path}")
    return payload


def _strict_json_object(path: Path) -> dict[str, Any]:
    pinned = _read_pinned(path)
    return _decode_strict_json(pinned.payload, path=pinned.relative_path.as_posix())


def _typed_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _typed_equal(observed[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _typed_equal(left, right) for left, right in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


def _assert_pinned_record(
    pinned: _PinnedFile,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    record = pinned.record
    if not _typed_equal(record, dict(expected)):
        raise ClosureP0SequenceAuditError(f"Closed file record drifted: {record['path']}")
    return record


def _expected_input_paths() -> tuple[Path, ...]:
    return (
        PROJECT_ROOT / DEFAULT_COMMON_ORIGINS,
        PROJECT_ROOT / DEFAULT_COMMON_COMPLETION,
        PROJECT_ROOT / DEFAULT_RUNTIME_CONFIG,
        PROJECT_ROOT / DEFAULT_RUNTIME_SCHEMA,
        PROJECT_ROOT / DEFAULT_RUNTIME_LOCK,
        PROJECT_ROOT / DEFAULT_ASSIGNMENT,
        PROJECT_ROOT / DEFAULT_HOLDOUT_MANIFEST,
        PROJECT_ROOT / DEFAULT_PROTOCOL_LOCK,
        PROJECT_ROOT / "src/experiments/build_closure_pipe_sequences.py",
        PROJECT_ROOT / P0_STATE_MANIFEST_PATH,
        PROJECT_ROOT / P0_STATE_PATH,
    )


def _closed_paths(*, pointer_present: bool) -> tuple[Path, ...]:
    paths = (
        *_expected_input_paths(),
        *(
            PROJECT_ROOT / path
            for path in RECONSTRUCTION_SOURCE_PATHS
            if path != Path("src/experiments/build_closure_pipe_sequences.py")
        ),
        PROJECT_ROOT / P0_SEQUENCE_PATH,
        PROJECT_ROOT / P0_SUMMARY_PATH,
        PROJECT_ROOT / P0_MANIFEST_PATH,
        PROJECT_ROOT / P_DLS_LOCK_PATH,
        PROJECT_ROOT / P_DLS_COMPANION_PATH,
        PROJECT_ROOT / AUDITOR_PATH,
    )
    return (*paths, PROJECT_ROOT / P0_POINTER_PATH) if pointer_present else paths


def _namespace_snapshot(session: _RepoReadSession) -> dict[str, Any]:
    return {
        "data": session.list_directory((PROJECT_ROOT / P0_SEQUENCE_PATH).parent),
        "reports": session.list_directory((PROJECT_ROOT / P0_SUMMARY_PATH).parent),
        "guards": session.list_directory(
            PROJECT_ROOT / P0_GUARD_DIRECTORY,
            allow_absent=True,
        ),
    }


def _validate_closed_namespace(snapshot: Mapping[str, Any]) -> bool:
    data = snapshot.get("data")
    reports = snapshot.get("reports")
    guards = snapshot.get("guards")
    pre_dvc = [P0_SEQUENCE_PATH.name]
    post_dvc = sorted((P0_SEQUENCE_PATH.name, P0_POINTER_PATH.name))
    if data not in (pre_dvc, post_dvc):
        raise ClosureP0SequenceAuditError(
            "P0 data namespace must contain only the Parquet and optional exact DVC pointer"
        )
    expected_reports = sorted((P0_MANIFEST_PATH.name, P0_SUMMARY_PATH.name))
    if reports != expected_reports:
        raise ClosureP0SequenceAuditError(
            "P0 report namespace must contain exactly summary plus manifest"
        )
    if guards not in (None, []):
        raise ClosureP0SequenceAuditError("P0 audit forbids active sequence builder guards")
    return data == post_dvc


def _validate_dvc_pointer(
    sequence: _PinnedFile,
    pointer: _PinnedFile | None,
) -> dict[str, Any]:
    if pointer is None:
        return {
            "state": "pre_dvc",
            "pointer_present": False,
            "pointer_payload_binding_verified": False,
            "cache_verified": False,
            "remote_verified": False,
            "dvc_command_executed_by_auditor": False,
        }
    match = DVC_POINTER_PATTERN.fullmatch(pointer.payload)
    if match is None:
        raise ClosureP0SequenceAuditError("P0 explicit DVC pointer dialect drifted")
    expected_md5 = hashlib.md5(sequence.payload, usedforsecurity=False).hexdigest()
    observed_md5 = match.group("md5").decode("ascii")
    observed_size = int(match.group("size"))
    if observed_md5 != expected_md5 or observed_size != len(sequence.payload):
        raise ClosureP0SequenceAuditError("P0 DVC pointer does not bind the physical Parquet")
    return {
        "state": "post_dvc",
        "pointer_present": True,
        "pointer": pointer.record,
        "payload_md5": observed_md5,
        "payload_bytes": observed_size,
        "pointer_payload_binding_verified": True,
        "cache_verified": False,
        "remote_verified": False,
        "dvc_command_executed_by_auditor": False,
    }


def _validate_p_dls_reference(
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
    reconstruction_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    authorizations = lock.get("authorizations")
    patch_repository = lock.get("patch_repository")
    p0_outputs = lock.get("p0_outputs")
    physical_contract = lock.get("compatibility_correction")
    seals = lock.get("seals")
    if not isinstance(authorizations, Mapping):
        raise ClosureP0SequenceAuditError("P-DLS authorization record is absent")
    if {
        "development_fit_authorized": authorizations.get("development_fit_authorized"),
        "evaluation_authorized": authorizations.get("evaluation_authorized"),
        "e0_u_authorized": authorizations.get("e0_u_authorized"),
        "future_outcomes_accessed": authorizations.get("future_outcomes_accessed"),
    } != {
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }:
        raise ClosureP0SequenceAuditError("P-DLS authorization seals drifted")
    expected_identity = {
        "lock_version": "closure_development_runtime_sequence_patch_lock_v1",
        "status": "locked",
        "experiment_id": "closure_v1",
        "patch_id": "development_runtime_sequence_serialization_patch_1",
    }
    for field, expected in expected_identity.items():
        if not _typed_equal(lock.get(field), expected):
            raise ClosureP0SequenceAuditError(f"P-DLS lock identity drifted: {field}")
    if not isinstance(patch_repository, Mapping) or any(
        patch_repository.get(field) != expected
        for field, expected in {
            "head": P_DLS_PATCH_HEAD,
            "published_head": P_DLS_PATCH_HEAD,
            "remote_main_oid": P_DLS_PATCH_HEAD,
            "published_ref": "origin/main",
            "worktree_status": "clean",
        }.items()
    ):
        raise ClosureP0SequenceAuditError("P-DLS sealed publication record drifted")
    if not isinstance(p0_outputs, Mapping) or p0_outputs.get("all_absent_at_lock") is not True:
        raise ClosureP0SequenceAuditError("P-DLS no-output-at-lock seal drifted")
    if not isinstance(physical_contract, Mapping) or any(
        physical_contract.get(field) != expected
        for field, expected in {
            "sequence_physical_type": "fixed_size_list<float32>[12]",
            "sequence_failure_encoding": "outer_valid_with_12_null_float32_children",
            "partially_null_tensor_accepted": False,
            "finite_failure_placeholder_accepted": False,
        }.items()
    ):
        raise ClosureP0SequenceAuditError("P-DLS physical serialization seal drifted")
    if not isinstance(seals, Mapping) or any(
        seals.get(field) is not False
        for field in ("e0_u_opened", "evaluation_opened", "future_outcomes_accessed")
    ):
        raise ClosureP0SequenceAuditError("P-DLS closure seals drifted")
    companion_identity = {
        "manifest_version": "closure_development_runtime_sequence_patch_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "gate": "E0-DLS",
        "patch_id": "development_runtime_sequence_serialization_patch_1",
        "authoritative_contract": False,
        "authoritative_lock_path": P_DLS_LOCK_PATH.as_posix(),
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    for field, expected in companion_identity.items():
        if not _typed_equal(companion.get(field), expected):
            raise ClosureP0SequenceAuditError(f"P-DLS companion identity drifted: {field}")
    outputs = companion.get("outputs")
    expected_output = {**dict(lock_record), "role": "external_development_runtime_sequence_patch_lock"}
    if not isinstance(outputs, list) or outputs != [expected_output]:
        raise ClosureP0SequenceAuditError("P-DLS companion does not bind the exact lock")
    patch_components = lock.get("patch_components")
    base_authority = lock.get("base_authority")
    preserved_components = (
        base_authority.get("preserved_components")
        if isinstance(base_authority, Mapping)
        else None
    )
    patch_records = (
        patch_components.get("records")
        if isinstance(patch_components, Mapping)
        else None
    )
    preserved_records = (
        preserved_components.get("records")
        if isinstance(preserved_components, Mapping)
        else None
    )
    if not isinstance(patch_records, list) or not isinstance(preserved_records, list):
        raise ClosureP0SequenceAuditError("P-DLS component records are absent")
    sealed_records = {
        str(record.get("path")): record
        for record in [*patch_records, *preserved_records]
        if isinstance(record, Mapping)
    }
    expected_paths = [path.as_posix() for path in RECONSTRUCTION_SOURCE_PATHS]
    if [str(record.get("path")) for record in reconstruction_records] != expected_paths:
        raise ClosureP0SequenceAuditError("Reconstruction source record order drifted")
    for current in reconstruction_records:
        path = str(current["path"])
        sealed = sealed_records.get(path)
        if not isinstance(sealed, Mapping) or any(
            current.get(field) != sealed.get(field)
            for field in ("path", "bytes", "sha256")
        ):
            raise ClosureP0SequenceAuditError(
                f"Reconstruction source differs from P-DLS: {path}"
            )
    return {
        "validation_scope": "exact_identity_and_selected_locked_seals",
        "lock_record": dict(lock_record),
        "historical_patch_head": P_DLS_PATCH_HEAD,
        "sealed_publication_record_reconciled": True,
        "reconstruction_sources_physically_reconciled": True,
        "reconstruction_source_records": [dict(record) for record in reconstruction_records],
        "full_schema_revalidated": False,
        "full_gate_reexecuted": False,
        "git_publication_revalidated": False,
        "remote_publication_revalidated": False,
        "command_evidence_reexecuted": False,
    }


def _validate_p0_state_manifest(
    payload: Mapping[str, Any],
    *,
    state_record: Mapping[str, Any],
) -> None:
    expected = {
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected.items():
        if not _typed_equal(payload.get(field), value):
            raise ClosureP0SequenceAuditError(f"P0 state manifest field drifted: {field}")
    outputs = payload.get("outputs")
    matches = [
        record
        for record in outputs
        if isinstance(record, Mapping)
        and record.get("path") == P0_STATE_PATH.as_posix()
        and record.get("role") == "expert_no_current_state"
    ] if isinstance(outputs, list) else []
    expected_record = {**dict(state_record), "role": "expert_no_current_state"}
    if matches != [expected_record]:
        raise ClosureP0SequenceAuditError("P0 state manifest does not bind the physical state")


def _load_assignment(payload: bytes) -> pd.DataFrame:
    try:
        assignment = pd.read_csv(io.BytesIO(payload))
        return validate_assignment_frame(
            assignment,
            expected_counts=EXPECTED_ASSIGNMENT_COUNTS,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ClosureP0SequenceAuditError("Locked holdout assignment is invalid") from exc


def _derive_boundary_evidence(
    frame: pd.DataFrame,
    assignment: pd.DataFrame,
    *,
    enforce_closed: bool = True,
) -> dict[str, int]:
    assignment_map = {
        (str(row["source_id"]), str(row["site_id"])): (
            str(row["assignment_role"]),
            str(row["holdout_group_id"]),
        )
        for row in assignment.to_dict(orient="records")
    }
    holdout = assignment.loc[
        assignment["assignment_role"].eq(ASSIGNMENT_HOLDOUT),
        ["source_id", "site_id"],
    ]
    development = assignment.loc[
        assignment["assignment_role"].eq(ASSIGNMENT_DEVELOPMENT),
        ["source_id", "site_id"],
    ]
    holdout_keys = set(zip(holdout["source_id"], holdout["site_id"], strict=True))
    development_keys = set(
        zip(development["source_id"], development["site_id"], strict=True)
    )
    row_keys = list(zip(frame["source_id"].astype(str), frame["site_id"].astype(str), strict=True))
    unique_keys = set(row_keys)
    holdout_rows = sum(key in holdout_keys for key in row_keys)
    holdout_locations = len(unique_keys.intersection(holdout_keys))
    unknown_locations = len(unique_keys.difference(development_keys).difference(holdout_keys))
    role_mismatches = 0
    group_mismatches = 0
    for row, key in zip(frame.to_dict(orient="records"), row_keys, strict=True):
        if key not in assignment_map:
            continue
        expected_role, expected_group = assignment_map[key]
        role_mismatches += int(str(row["assignment_role"]) != expected_role)
        group_mismatches += int(str(row["holdout_group_id"]) != expected_group)
    targets = pd.PeriodIndex(frame["target_year_month"].astype(str), freq="M")
    post_2021 = int((targets > pd.Period("2021-12", freq="M")).sum())
    evidence = {
        "development_assignment_locations": len(development_keys),
        "holdout_assignment_locations": len(holdout_keys),
        "sequence_locations": len(unique_keys),
        "holdout_overlap": holdout_locations,
        "holdout_overlap_rows": holdout_rows,
        "unknown_assignment_locations": unknown_locations,
        "assignment_role_mismatch_rows": role_mismatches,
        "holdout_group_mismatch_rows": group_mismatches,
        "post_2021_rows": post_2021,
    }
    expected = {
        "development_assignment_locations": 353,
        "holdout_assignment_locations": 88,
        "sequence_locations": 353,
        "holdout_overlap": 0,
        "holdout_overlap_rows": 0,
        "unknown_assignment_locations": 0,
        "assignment_role_mismatch_rows": 0,
        "holdout_group_mismatch_rows": 0,
        "post_2021_rows": 0,
    }
    if enforce_closed and evidence != expected:
        raise ClosureP0SequenceAuditError(f"P0 development boundary evidence drifted: {evidence}")
    return evidence


def _summary_frame(frame: pd.DataFrame) -> pd.DataFrame:
    summary = cast(
        pd.DataFrame,
        frame.groupby(
            ["time_role", "sequence_status", "failure_reason"],
            dropna=False,
            as_index=False,
        ).size(),
    )
    return summary.rename(columns={"size": "rows"}).sort_values(
        ["time_role", "sequence_status", "failure_reason"],
        kind="mergesort",
    )


def _summary_bytes(frame: pd.DataFrame) -> bytes:
    return _summary_frame(frame).to_csv(index=False, lineterminator="\n").encode("utf-8")


def _manifest_counts(
    audit: SequenceBuildAudit,
    boundary: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "intent_origins": audit.intent_origins,
        "successful_origins": audit.successful_origins,
        "failed_origins": audit.failed_origins,
        "role_counts": audit.role_counts,
        "status_counts": audit.status_counts,
        "failure_reason_counts": audit.failure_reason_counts,
        "delta_previous_month_missing_count": (
            audit.delta_previous_month_missing_history_values
        ),
        "delta_previous_month_missing_history_values": (
            audit.delta_previous_month_missing_history_values
        ),
        "delta_previous_month_missing_target_values": (
            audit.delta_previous_month_missing_target_values
        ),
        "holdout_overlap": boundary["holdout_overlap"],
        "post_2021_rows": boundary["post_2021_rows"],
    }


def _validate_physical_schema(schema: pa.Schema) -> None:
    if schema.names != list(SEQUENCE_COLUMNS):
        raise ClosureP0SequenceAuditError("P0 Parquet columns/order drifted")
    for column in SEQUENCE_COLUMNS:
        field = schema.field(column)
        if column in INPUT_COLUMNS:
            valid = (
                pa.types.is_fixed_size_list(field.type)
                and field.type.list_size == HISTORY_LENGTH
                and field.type.value_type == pa.float32()
                and field.type.value_field.name in {"item", "element"}
                and field.nullable
            )
        elif column in TARGET_COLUMNS:
            valid = field.type == pa.float32() and field.nullable
        elif column == "base_seed":
            valid = field.type == pa.int64() and field.nullable
        elif column == "history_length_months":
            valid = field.type == pa.int16() and not field.nullable
        else:
            valid = field.type == pa.string() and not field.nullable
        if not valid:
            raise ClosureP0SequenceAuditError(f"P0 physical schema drifted: {column}")


def _validate_physical_payload(table: pa.Table) -> dict[str, int]:
    _validate_physical_schema(table.schema)
    statuses = np.asarray(table.column("sequence_status").to_pylist(), dtype=object)
    success = statuses == "success"
    failure = ~success
    row_count = int(table.num_rows)
    if row_count != EXPECTED_INTENT_ORIGINS:
        raise ClosureP0SequenceAuditError("P0 Parquet intent denominator drifted")
    failed_input_tensors = 0
    for column in INPUT_COLUMNS:
        values = table.column(column).combine_chunks()
        field = table.schema.field(column)
        if (
            not pa.types.is_fixed_size_list(field.type)
            or field.type.list_size != HISTORY_LENGTH
            or field.type.value_type != pa.float32()
            or not field.nullable
        ):
            raise ClosureP0SequenceAuditError(f"P0 input schema drifted: {column}")
        if values.null_count:
            raise ClosureP0SequenceAuditError(
                f"P0 input list parents must remain physically valid: {column}"
            )
        child_null = np.asarray(values.values.is_null().to_pylist(), dtype=bool).reshape(
            row_count,
            HISTORY_LENGTH,
        )
        if bool(child_null[success].any()):
            raise ClosureP0SequenceAuditError(f"Successful P0 input contains nulls: {column}")
        if failure.any() and not bool(child_null[failure].all()):
            raise ClosureP0SequenceAuditError(
                f"Unavailable P0 input is not an exact all-null tensor: {column}"
            )
        child_values = np.asarray(values.values.to_pylist(), dtype=np.float64).reshape(
            row_count,
            HISTORY_LENGTH,
        )
        if not bool(np.isfinite(child_values[success]).all()):
            raise ClosureP0SequenceAuditError(
                f"Successful P0 input contains a non-finite value: {column}"
            )
        failed_input_tensors += int(failure.sum())
    failed_targets = 0
    for column in TARGET_COLUMNS:
        values = table.column(column).combine_chunks()
        field = table.schema.field(column)
        nulls = np.asarray(values.is_null().to_pylist(), dtype=bool)
        if field.type != pa.float32() or not field.nullable:
            raise ClosureP0SequenceAuditError(f"P0 target schema drifted: {column}")
        if bool(nulls[success].any()) or (failure.any() and not bool(nulls[failure].all())):
            raise ClosureP0SequenceAuditError(f"P0 target null policy drifted: {column}")
        success_values = [value for value, keep in zip(values.to_pylist(), success, strict=True) if keep]
        if not bool(np.isfinite(np.asarray(success_values, dtype=np.float64)).all()):
            raise ClosureP0SequenceAuditError(
                f"Successful P0 target contains a non-finite value: {column}"
            )
        failed_targets += int(failure.sum())
    base_seed = table.column("base_seed").combine_chunks()
    if base_seed.null_count != row_count:
        raise ClosureP0SequenceAuditError("Shared P0 sequence must retain a null base_seed")
    return {
        "rows": row_count,
        "successful_rows": int(success.sum()),
        "failed_rows": int(failure.sum()),
        "failed_input_tensors_all_null": failed_input_tensors,
        "failed_targets_null": failed_targets,
    }


def _validate_manifest(
    payload: Mapping[str, Any],
    *,
    builder_record: Mapping[str, Any],
    input_records: Sequence[Mapping[str, Any]],
    output_records: Sequence[Mapping[str, Any]],
    audit: SequenceBuildAudit,
    boundary: Mapping[str, int],
) -> None:
    if set(payload) != MANIFEST_KEYS:
        raise ClosureP0SequenceAuditError("P0 manifest top-level dialect drifted")
    expected_identity = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": None,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, expected in expected_identity.items():
        if not _typed_equal(payload.get(field), expected):
            raise ClosureP0SequenceAuditError(f"P0 manifest field drifted: {field}")
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise ClosureP0SequenceAuditError("P0 manifest timestamp is absent")
    try:
        parsed_time = datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ClosureP0SequenceAuditError("P0 manifest timestamp is invalid") from exc
    if parsed_time.tzinfo is None:
        raise ClosureP0SequenceAuditError("P0 manifest timestamp must be timezone-aware")
    expected_script = dict(builder_record)
    exact_sections = {
        "script": expected_script,
        "source_code": [expected_script],
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "optional_context_columns": [],
        "serialization": {
            "rows_per_common_origin": 1,
            "input_physical_type": "fixed_size_list<float32>[12]",
            "target_physical_type": "float32",
            "canonical_order": [
                "source_id",
                "site_id",
                "origin_year_month",
                "target_year_month",
            ],
        },
        "inputs": [dict(record) for record in input_records],
        "outputs": [dict(record) for record in output_records],
    }
    for field, expected in exact_sections.items():
        if not _typed_equal(payload.get(field), expected):
            raise ClosureP0SequenceAuditError(f"P0 manifest section drifted: {field}")
    counts = payload.get("counts")
    if not isinstance(counts, Mapping) or set(counts) != MANIFEST_COUNT_KEYS:
        raise ClosureP0SequenceAuditError("P0 manifest count dialect drifted")
    if not _typed_equal(dict(counts), _manifest_counts(audit, boundary)):
        raise ClosureP0SequenceAuditError("P0 manifest counts differ from reconstruction")


def _fit_evidence(frame: pd.DataFrame) -> dict[str, Any]:
    total_statuses = {
        str(key): int(value) for key, value in frame["sequence_status"].value_counts().items()
    }
    total_failures = {
        str(key): int(value)
        for key, value in frame.loc[
            ~frame["sequence_status"].eq("success"), "failure_reason"
        ].value_counts().items()
    }
    if total_statuses != EXPECTED_STATUS_COUNTS:
        raise ClosureP0SequenceAuditError("P0 total availability evidence drifted")
    if total_failures != EXPECTED_FAILURE_REASON_COUNTS:
        raise ClosureP0SequenceAuditError("P0 total failure reasons drifted")
    fit = frame.loc[frame["time_role"].isin(FIT_ROLES)]
    statuses = {
        str(key): int(value) for key, value in fit["sequence_status"].value_counts().items()
    }
    failures = {
        str(key): int(value)
        for key, value in fit.loc[
            ~fit["sequence_status"].eq("success"), "failure_reason"
        ].value_counts().items()
    }
    calibration_failures = int(
        (
            frame["time_role"].eq("calibration_threshold")
            & ~frame["sequence_status"].eq("success")
        ).sum()
    )
    if statuses != EXPECTED_FIT_STATUS_COUNTS or failures != EXPECTED_FIT_FAILURE_REASON_COUNTS:
        raise ClosureP0SequenceAuditError("P0 fit-role availability evidence drifted")
    if calibration_failures != EXPECTED_CALIBRATION_FAILURES:
        raise ClosureP0SequenceAuditError("P0 calibration failure count drifted")
    return {
        "available": False,
        "observed_total_status_counts": total_statuses,
        "observed_total_failure_reason_counts": total_failures,
        "observed_fit_status_counts": statuses,
        "observed_fit_failure_reason_counts": failures,
        "observed_calibration_failure_count": calibration_failures,
        "expected_fit_status": "not_attempted",
        "expected_temporal_slot_status": "model_unavailable",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "expected_rows_dropped": 0,
        "expected_rows_imputed": 0,
        "expected_replacement_model_authorized": False,
        "expected_model_or_checkpoint_emitted": False,
        "availability_inferred_from_closed_counts": True,
        "consumer_executed": False,
        "fit_or_model_construction_executed": False,
    }


def _parquet_table(
    pinned: _PinnedFile,
    *,
    columns: Sequence[str] | None = None,
) -> tuple[pa.Schema, pa.Table]:
    try:
        reader = pq.ParquetFile(pa.BufferReader(pinned.payload), pre_buffer=False)
        try:
            schema = reader.schema_arrow
            table = reader.read(
                columns=list(columns) if columns is not None else None,
                use_threads=False,
            )
        finally:
            reader.close()
    except (OSError, ValueError, pa.ArrowException) as exc:
        raise ClosureP0SequenceAuditError(
            f"Parquet cannot be decoded from its pinned bytes: {pinned.relative_path.as_posix()}"
        ) from exc
    return schema, table


def audit_p0_sequence_bundle() -> dict[str, Any]:
    result: dict[str, Any]
    with _RepoReadSession(PROJECT_ROOT) as session:
        namespace_before = _namespace_snapshot(session)
        pointer_present = _validate_closed_namespace(namespace_before)
        pinned = {
            session._relative(path).as_posix(): session.pin(path)
            for path in _closed_paths(pointer_present=pointer_present)
        }

        def file_for(path: Path) -> _PinnedFile:
            return pinned[session._relative(PROJECT_ROOT / path).as_posix()]

        p_dls_records = {
            path: _assert_pinned_record(file_for(Path(path)), record)
            for path, record in EXPECTED_P_DLS_RECORDS.items()
        }
        p0_records = {
            path: _assert_pinned_record(file_for(Path(path)), record)
            for path, record in EXPECTED_P0_RECORDS.items()
        }
        lock_payload = _decode_strict_json(
            file_for(P_DLS_LOCK_PATH).payload,
            path=P_DLS_LOCK_PATH.as_posix(),
        )
        companion_payload = _decode_strict_json(
            file_for(P_DLS_COMPANION_PATH).payload,
            path=P_DLS_COMPANION_PATH.as_posix(),
        )
        reconstruction_records = [
            file_for(path).record for path in RECONSTRUCTION_SOURCE_PATHS
        ]
        p_dls = _validate_p_dls_reference(
            lock_payload,
            companion_payload,
            lock_record=p_dls_records[P_DLS_LOCK_PATH.as_posix()],
            reconstruction_records=reconstruction_records,
        )
        sequence_file = file_for(P0_SEQUENCE_PATH)
        pointer_file = file_for(P0_POINTER_PATH) if pointer_present else None
        dvc_registration = _validate_dvc_pointer(sequence_file, pointer_file)

        input_paths = _expected_input_paths()
        input_files = [
            pinned[session._relative(path).as_posix()]
            for path in input_paths
        ]
        input_records = [item.record for item in input_files]
        state_file = file_for(P0_STATE_PATH)
        state_manifest = _decode_strict_json(
            file_for(P0_STATE_MANIFEST_PATH).payload,
            path=P0_STATE_MANIFEST_PATH.as_posix(),
        )
        _validate_p0_state_manifest(state_manifest, state_record=state_file.record)
        assignment = _load_assignment(file_for(DEFAULT_ASSIGNMENT).payload)

        common = pd.read_parquet(
            io.BytesIO(file_for(DEFAULT_COMMON_ORIGINS).payload),
            engine="pyarrow",
            columns=list(COMMON_ORIGIN_REQUIRED_COLUMNS),
        )
        state = pd.read_parquet(
            io.BytesIO(state_file.payload),
            engine="pyarrow",
            columns=state_projection_columns("P0"),
        )
        expected_frame, build_audit = build_closure_pipe_sequences(
            state,
            common,
            model_id="P0",
            base_seed=None,
            expected_origin_count=EXPECTED_INTENT_ORIGINS,
            expected_role_counts=EXPECTED_INTENT_ORIGINS_BY_ROLE,
        )
        expected_table = sequence_arrow_table(expected_frame)
        physical_schema, actual_table = _parquet_table(sequence_file)
        if physical_schema.names != list(SEQUENCE_COLUMNS):
            raise ClosureP0SequenceAuditError("P0 physical Parquet schema has extra or reordered columns")
        physical = _validate_physical_payload(actual_table)
        differing_columns = [
            column
            for column in SEQUENCE_COLUMNS
            if not actual_table.column(column).equals(expected_table.column(column))
        ]
        if differing_columns or actual_table.num_rows != expected_table.num_rows:
            raise ClosureP0SequenceAuditError(
                "P0 Parquet rows differ from the sealed in-memory reconstruction: "
                f"columns={differing_columns}"
            )
        expected_physical = {
            "rows": EXPECTED_INTENT_ORIGINS,
            "successful_rows": EXPECTED_STATUS_COUNTS["success"],
            "failed_rows": EXPECTED_STATUS_COUNTS["autoregressive_target_unavailable"],
            "failed_input_tensors_all_null": (
                EXPECTED_STATUS_COUNTS["autoregressive_target_unavailable"]
                * len(INPUT_COLUMNS)
            ),
            "failed_targets_null": (
                EXPECTED_STATUS_COUNTS["autoregressive_target_unavailable"]
                * len(TARGET_COLUMNS)
            ),
        }
        if physical != expected_physical:
            raise ClosureP0SequenceAuditError("P0 physical null evidence drifted")
        if build_audit.status_counts != EXPECTED_STATUS_COUNTS:
            raise ClosureP0SequenceAuditError("P0 reconstructed status counts drifted")
        if build_audit.failure_reason_counts != EXPECTED_FAILURE_REASON_COUNTS:
            raise ClosureP0SequenceAuditError("P0 reconstructed failure reasons drifted")
        boundary_columns = [
            "source_id",
            "site_id",
            "holdout_group_id",
            "assignment_role",
            "target_year_month",
        ]
        boundary = _derive_boundary_evidence(
            actual_table.select(boundary_columns).to_pandas(),
            assignment,
        )
        expected_summary = _summary_bytes(expected_frame)
        if file_for(P0_SUMMARY_PATH).payload != expected_summary:
            raise ClosureP0SequenceAuditError("P0 summary bytes differ from reconstructed rows")
        manifest = _decode_strict_json(
            file_for(P0_MANIFEST_PATH).payload,
            path=P0_MANIFEST_PATH.as_posix(),
        )
        builder_record = file_for(
            Path("src/experiments/build_closure_pipe_sequences.py")
        ).record
        _validate_manifest(
            manifest,
            builder_record=builder_record,
            input_records=input_records,
            output_records=(
                p0_records[P0_SEQUENCE_PATH.as_posix()],
                p0_records[P0_SUMMARY_PATH.as_posix()],
            ),
            audit=build_audit,
            boundary=boundary,
        )
        fit = _fit_evidence(expected_frame)
        namespace_after = _namespace_snapshot(session)
        if namespace_before != namespace_after:
            raise ClosureP0SequenceAuditError("P0 audit namespace changed during readback")
        session.verify_unchanged()
        result = {
            "audit_version": AUDIT_VERSION,
            "status": "validated",
            "experiment_id": "closure_v1",
            "model_id": "P0",
            "base_seed": None,
            "sequence_bundle_status": "completed",
            "auditor": file_for(AUDITOR_PATH).record,
            "p_dls": {
                **p_dls,
                "records": [
                    p_dls_records[path.as_posix()]
                    for path in (P_DLS_LOCK_PATH, P_DLS_COMPANION_PATH)
                ],
            },
            "outputs": [
                p0_records[path.as_posix()]
                for path in (P0_SEQUENCE_PATH, P0_SUMMARY_PATH, P0_MANIFEST_PATH)
            ],
            "counts": _manifest_counts(build_audit, boundary),
            "development_boundary": boundary,
            "physical_evidence": physical,
            "fit_availability": fit,
            "dvc_registration": dvc_registration,
            "dvc_pointer_present": pointer_present,
            "closed_logical_schema_exact": True,
            "arrow_child_field_label_equality_claimed": False,
            "rows_equal_reconstruction": True,
            "summary_reconciled": True,
            "manifest_reconciled": True,
            "builder_reconstruction_executed": True,
            "builder_cli_executed": False,
            "fit_or_model_construction_executed": False,
            "inputs_unchanged": True,
            "outputs_unchanged": True,
            "audited_namespaces_unchanged": True,
            "dvc_operation_executed_by_auditor": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
        }
    result["pinned_read_session_verified"] = True
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only audit of the closed Closure V1 P0 sequence bundle."
    )
    parser.add_argument(
        CHECK_ONLY_FLAG,
        action="store_true",
        required=True,
        help="Reopen and validate the fixed P0 bundle without writing outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    try:
        result = audit_p0_sequence_bundle()
    except Exception as exc:
        failure = {
            "audit_version": AUDIT_VERSION,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(
            json.dumps(failure, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
