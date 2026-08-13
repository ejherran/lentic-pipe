#!/usr/bin/env python
"""Adopt the verified DVC hardlink identity of the locked evaluation panel.

E0-MIC is a narrow authority overlay over published P-E0-MIB.  H/P are
metadata-only.  The one-shot R producer remains the byte/row-contract audited
E0-MIB implementation; this module replaces only its panel reader with the
existing descriptor-anchored DVC-cache identity validator.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import closure_locked_evaluation_input_bundle as mib


mcal = mib.mcal
mcalm = mib.mcalm
mt = mib.mt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_P_MIB_COMMIT = "ddd00ae96fa8cb589f368cb2f7b98d9e2561491d"
BASE_H_MIB_COMMIT = "0ee4fa9737ecc81fe20d77b24271eeb0c8ea79d4"
PATCH_GATE = "E0-MIC"
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = (
    "closure_locked_evaluation_input_panel_dvc_identity_patch_lock_v1"
)
COMPANION_SCHEMA_VERSION = (
    "closure_locked_evaluation_input_panel_dvc_identity_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/"
    "locked_evaluation_input_panel_dvc_identity_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "configs/closure_v1/"
    "locked_evaluation_input_panel_dvc_identity_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "configs/closure_v1/"
    "locked_evaluation_input_panel_dvc_identity_patch_lock_manifest.json"
)
LOCKER_PATH = Path(
    "src/experiments/"
    "lock_closure_locked_evaluation_input_panel_dvc_identity_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mic/"
    "locked_evaluation_input_panel_dvc_identity_patch_lock.guard"
)

PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = (
    "src/experiments/"
    "closure_locked_evaluation_input_panel_dvc_identity_patch.py"
)
TEST_PATH = (
    "tests/test_closure_locked_evaluation_input_panel_dvc_identity_patch.py"
)
DOCUMENTATION_PATH = (
    "docs/closure_v1/"
    "E0_M_LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_PATCH.md"
)
PATCH_PATHS = tuple(
    sorted(
        (
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            DOCUMENTATION_PATH,
            PRECOMMIT_PATH,
            CORE_PATH,
            LOCKER_PATH.as_posix(),
            TEST_PATH,
        )
    )
)
PATCH_COMPONENT_GIT_MODES = {
    path: ("100755" if path == PRECOMMIT_PATH else "100644")
    for path in PATCH_PATHS
}
LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_H_STAGED_SCOPE = {
    path: ("M" if path == PRECOMMIT_PATH else "A") for path in PATCH_PATHS
}
LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}

R_PHYSICAL_OUTPUT_PATHS = tuple(mib.R_PHYSICAL_OUTPUT_PATHS)
R_POINTER_PATHS = tuple(mib.R_POINTER_PATHS)
R_LIGHT_OUTPUT_PATHS = tuple(mib.R_LIGHT_OUTPUT_PATHS)
R_TRACKED_OUTPUT_PATHS = tuple(mib.R_TRACKED_OUTPUT_PATHS)
LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_R_STAGED_SCOPE = {
    path.as_posix(): "A" for path in R_TRACKED_OUTPUT_PATHS
}
R8_OUTPUT_CONTRACT = tuple(mib.R8_OUTPUT_CONTRACT)
P_MIB_PATHS = tuple(mib.CURRENT_LOCK_PATHS)
H_MIB_PATHS = tuple(Path(path) for path in mib.PATCH_PATHS)
CURRENT_LOCK_PATHS = (
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_MANIFEST_PATH,
)
LOCK_TEMPORARY_PATHS = tuple(mcal._temporary_path(path) for path in CURRENT_LOCK_PATHS)

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 6
EXPECTED_COMPANION_OUTPUT_COUNT = 1
TYPE_CHECK_COMMAND = mib.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_prepare_commit_artifacts.py",
    TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mib.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mib.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mib.DIFF_CHECK_COMMAND

INPUT_BUNDLE_COMMAND = (
    "poetry",
    "run",
    "python",
    CORE_PATH,
    "--execute-input-bundle",
)
PANEL_POINTER_PATH = Path(f"{mib.PANEL_PATH.as_posix()}.dvc")
PANEL_CACHE_PATH = Path(
    ".dvc/cache/files/md5/9a/eaac8466f16cae4ef4164980899059"
)
PANEL_DVC_IDENTITY_CONTRACT: dict[str, Any] = {
    "assignment": {
        "path": mib.ASSIGNMENT_PATH.as_posix(),
        "required_mode": 0o644,
        "required_nlink": 1,
        "sha256": "b090994b9ec9a3cd6af8e3261879872a12efe301e02fe1727ded519b46ebedef",
    },
    "panel": {
        "path": mib.PANEL_PATH.as_posix(),
        "pointer_path": PANEL_POINTER_PATH.as_posix(),
        "required_mode": 0o444,
        "required_nlink": 2,
        "pointer_hash": "md5",
        "pointer_md5": "9aeaac8466f16cae4ef4164980899059",
        "pointer_size": 103469973,
        "pointer_output_path": mib.PANEL_PATH.name,
        "pointer_sha256": "eb34b0b5578c40f1e7984ee0698786efd8eea116ec125d7c7f4507ddfacdad9c",
        "cache_path": PANEL_CACHE_PATH.as_posix(),
        "payload_bytes": 103469973,
        "payload_md5": "9aeaac8466f16cae4ef4164980899059",
        "payload_sha256": "8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62",
    },
    "validation": {
        "descriptor_anchored": True,
        "no_follow": True,
        "payload_cache_same_device_inode": True,
        "payload_cache_bytes_equal": True,
        "stable_reread": True,
        "scientific_rows_decoded": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    },
}

UNPUBLISHED_AUTHORIZATIONS = dict(mib.UNPUBLISHED_AUTHORIZATIONS)


class ClosureLockedEvaluationInputPanelDvcIdentityPatchError(RuntimeError):
    """Raised when the E0-MIC authority or its DVC identity drifts."""


def _error(message: str) -> ClosureLockedEvaluationInputPanelDvcIdentityPatchError:
    return ClosureLockedEvaluationInputPanelDvcIdentityPatchError(message)


def _root(repo_root: Path | None = None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _canonical_json_bytes(value: Any) -> bytes:
    return mib._canonical_json_bytes(value)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _deep_copy(value: Any) -> Any:
    return json.loads(_canonical_json_bytes(value))


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    return mib._git_head(repo_root, ref)


def _path_exists(path: Path, *, repo_root: Path) -> bool:
    return mcal._entry_exists(path, repo_root=repo_root)


def _file_record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
    try:
        return mcal._file_record(path, role=role, repo_root=repo_root)
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIC file record drifted: {path}") from exc


def _artifact_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    commit: str | None,
    expected_mode: str = "100644",
) -> dict[str, Any]:
    try:
        return mcal._git_artifact_record(
            path,
            role=role,
            repo_root=repo_root,
            commit=commit,
            expected_mode=expected_mode,
        )
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIC artifact binding drifted: {path}") from exc


def _git_record_at_commit(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    commit: str,
    expected_mode: str = "100644",
) -> dict[str, Any]:
    try:
        mode, oid = mcal._git_mode_oid(repo_root, commit, path)
        payload = mcal._git_blob_bytes(repo_root, commit, path)
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIC historical Git binding drifted: {path}") from exc
    if mode != expected_mode:
        raise _error(f"E0-MIC historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _read_panel_dvc_bytes_and_metadata(
    *, repo_root: Path
) -> tuple[bytes, os.stat_result]:
    """Read the panel through the audited exact DVC-cache hardlink policy."""

    try:
        payload, metadata = mcal._read_scientific_payload_bytes_and_metadata(
            mib.PANEL_PATH,
            authorized_dvc_pointers=(PANEL_POINTER_PATH,),
            repo_root=repo_root,
        )
    except mcal.FinalCalibrationError as exc:
        raise _error("E0-MIC panel DVC-cache identity validation failed") from exc
    panel = cast(Mapping[str, Any], PANEL_DVC_IDENTITY_CONTRACT["panel"])
    observed = {
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
    }
    expected = {
        "bytes": panel["payload_bytes"],
        "sha256": panel["payload_sha256"],
        "md5": panel["payload_md5"],
        "mode": panel["required_mode"],
        "nlink": panel["required_nlink"],
    }
    if observed != expected:
        raise _error("E0-MIC panel physical identity differs from the sealed contract")
    return payload, metadata


def _source_identity_snapshot(
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Capture exact4 identities from the same reads that prove the contract."""

    root = _root(repo_root)
    try:
        assignment, assignment_metadata = mcal._read_regular_bytes_and_metadata(
            mib.ASSIGNMENT_PATH,
            repo_root=root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        pointer, pointer_metadata = mcal._read_regular_bytes_and_metadata(
            PANEL_POINTER_PATH,
            repo_root=root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        panel, panel_metadata = _read_panel_dvc_bytes_and_metadata(repo_root=root)
        cache, cache_metadata = mcal._read_regular_bytes_and_metadata(
            PANEL_CACHE_PATH,
            repo_root=root,
            expected_mode=0o444,
            require_nlink_one=False,
        )
    except mcal.FinalCalibrationError as exc:
        raise _error("E0-MIC physical source identity validation failed") from exc
    assignment_contract = cast(
        Mapping[str, Any], PANEL_DVC_IDENTITY_CONTRACT["assignment"]
    )
    panel_contract = cast(Mapping[str, Any], PANEL_DVC_IDENTITY_CONTRACT["panel"])
    if (
        _sha256_bytes(assignment) != assignment_contract["sha256"]
        or stat.S_IMODE(assignment_metadata.st_mode)
        != assignment_contract["required_mode"]
        or assignment_metadata.st_nlink != assignment_contract["required_nlink"]
        or _sha256_bytes(pointer) != panel_contract["pointer_sha256"]
        or len(panel) != panel_contract["payload_bytes"]
        or panel != cache
        or (panel_metadata.st_dev, panel_metadata.st_ino)
        != (cache_metadata.st_dev, cache_metadata.st_ino)
        or panel_metadata.st_nlink != 2
        or cache_metadata.st_nlink != 2
        or stat.S_IMODE(panel_metadata.st_mode) != 0o444
        or stat.S_IMODE(cache_metadata.st_mode) != 0o444
        or pointer_metadata.st_nlink != 1
    ):
        raise _error("E0-MIC assignment/panel/cache binding drifted")
    records: list[dict[str, Any]] = []
    for path, payload, metadata in (
        (mib.ASSIGNMENT_PATH, assignment, assignment_metadata),
        (PANEL_POINTER_PATH, pointer, pointer_metadata),
        (mib.PANEL_PATH, panel, panel_metadata),
        (PANEL_CACHE_PATH, cache, cache_metadata),
    ):
        records.append(
            {
                "path": path.as_posix(),
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 4 or len({record["path"] for record in records}) != 4:
        raise _error("E0-MIC source identity snapshot is not exact4")
    return tuple(records)


def _validate_panel_dvc_identity(*, repo_root: Path) -> dict[str, Any]:
    _source_identity_snapshot(repo_root)
    return _deep_copy(PANEL_DVC_IDENTITY_CONTRACT)


def _require_source_identity_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _source_identity_snapshot(repo_root)
    ):
        raise _error(f"E0-MIC source identities changed {context}")


def _base_p_mib_authority(*, repo_root: Path) -> dict[str, Any]:
    expected_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(path.as_posix() for path in P_MIB_PATHS),
    }
    try:
        if (
            mcal._single_parent(repo_root, BASE_P_MIB_COMMIT, context="P-E0-MIB")
            != BASE_H_MIB_COMMIT
            or mcal._git_scope(repo_root, BASE_H_MIB_COMMIT, BASE_P_MIB_COMMIT)
            != expected_scope
        ):
            raise _error("E0-MIC base P-E0-MIB topology drifted")
        lock_bytes = mcal._git_blob_bytes(
            repo_root, BASE_P_MIB_COMMIT, mib.DEFAULT_PATCH_LOCK_PATH
        )
        companion_bytes = mcal._git_blob_bytes(
            repo_root, BASE_P_MIB_COMMIT, mib.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        )
        lock = mcal._parse_json_bytes(lock_bytes, context="historical P-E0-MIB lock")
        companion = mcal._parse_json_bytes(
            companion_bytes, context="historical P-E0-MIB companion"
        )
        if (
            not isinstance(lock, Mapping)
            or not isinstance(companion, Mapping)
            or lock_bytes != _canonical_json_bytes(lock)
            or companion_bytes != _canonical_json_bytes(companion)
            or lock.get("gate") != mib.PATCH_GATE
            or lock.get("schema_version") != mib.LOCK_SCHEMA_VERSION
            or lock.get("authorizations") != mib.UNPUBLISHED_AUTHORIZATIONS
        ):
            raise _error("E0-MIC base P-E0-MIB payload drifted")
        schema_bytes = mcal._git_blob_bytes(
            repo_root, BASE_H_MIB_COMMIT, mib.DEFAULT_PATCH_LOCK_SCHEMA
        )
        schema = mcal._parse_json_bytes(schema_bytes, context="historical MIB schema")
        if not isinstance(schema, Mapping):
            raise _error("E0-MIC historical MIB schema drifted")
        mcal.validate_json_schema(lock, schema)
        lock_record = {
            "role": "locked_evaluation_input_bundle_lock",
            "path": mib.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        if companion_bytes != _canonical_json_bytes(
            mib._expected_companion(lock, lock_record)
        ):
            raise _error("E0-MIC base P-E0-MIB companion drifted")
        components = [
            _artifact_record(
                path,
                role=(
                    "published_p_mib_lock"
                    if path == mib.DEFAULT_PATCH_LOCK_PATH
                    else "published_p_mib_lock_manifest"
                ),
                repo_root=repo_root,
                commit=BASE_P_MIB_COMMIT,
            )
            for path in P_MIB_PATHS
        ]
    except ClosureLockedEvaluationInputPanelDvcIdentityPatchError:
        raise
    except Exception as exc:
        raise _error("E0-MIC base P-E0-MIB authority drifted") from exc
    return {
        "gate": mib.PATCH_GATE,
        "status": "published_p_mib_authority_validated",
        "p_commit": BASE_P_MIB_COMMIT,
        "h_commit": BASE_H_MIB_COMMIT,
        "p_scope": expected_scope,
        "p_components": components,
        "p_components_sha256": mcal._digest_records(components),
        "lock_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "r8_output_count": 8,
        "r8_outputs_sha256": "524928813b26bed6de9feee34eff1e946f9fc214521c3a39171ed905b3faf7a2",
        "scientific_inputs_rehashed": False,
        "outcome_paths_opened": False,
    }


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    if {path for _, path in records} != set(PATCH_PATHS):
        return False
    by_path = {path: code for code, path in records}
    return all(
        by_path[path] in ({" M", "M ", "MM"} if path == PRECOMMIT_PATH else {"??", "A "})
        for path in PATCH_PATHS
    )


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise _error("E0-MIC remote policy must be exact boolean")
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MIC requires branch main")
    head = _git_head(repo_root)
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if head == BASE_P_MIB_COMMIT:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MIC candidate workspace is not exact 1M+5A")
        component_commit: str | None = None
        h_head = BASE_P_MIB_COMMIT
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MIC")
            != BASE_P_MIB_COMMIT
            or mcal._git_scope(repo_root, BASE_P_MIB_COMMIT, head) != expected_scope
            or mcal._workspace_status_records(repo_root)
        ):
            raise _error("E0-MIC published H topology/worktree drifted")
        component_commit = head
        h_head = head
    components = [
        _artifact_record(
            Path(path),
            role="locked_evaluation_input_panel_dvc_identity_patch_h_component",
            repo_root=repo_root,
            commit=component_commit,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = _git_head(repo_root, "origin/main")
    expected_ref = BASE_P_MIB_COMMIT if component_commit is None else head
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != expected_ref or remote != expected_ref:
        raise _error("E0-MIC H refs drifted")
    return (
        {
            "base_p_mib_commit": BASE_P_MIB_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": expected_scope,
        },
        {
            "gate": "H-E0-MIC",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


def _historical_h_mib_records(*, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        {
            **_git_record_at_commit(
                path,
                role="superseded_h_mib_component",
                repo_root=repo_root,
                commit=BASE_H_MIB_COMMIT,
                expected_mode=mib.PATCH_COMPONENT_GIT_MODES[path.as_posix()],
            ),
            "commit": BASE_H_MIB_COMMIT,
        }
        for path in H_MIB_PATHS
    ]
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 6:
        raise _error("E0-MIC historical H-E0-MIB set is not exact6")
    return records


def _current_r_state(*, repo_root: Path) -> str:
    return mib._current_r_state(repo_root=repo_root)


def _require_namespace(
    *,
    repo_root: Path,
    current_lock_state: str,
    r_state: str,
    owned_lock_guard: Any | None = None,
    owned_run_guard: Any | None = None,
) -> dict[str, Any]:
    if current_lock_state not in {"absent", "present"}:
        raise _error("E0-MIC current lock state policy drifted")
    if r_state not in {"absent", "physical_and_light", "complete"}:
        raise _error("E0-MIC R state policy drifted")
    try:
        predecessor = mib._require_namespace(
            repo_root=repo_root,
            current_lock_state="present",
            r_state=r_state,
            owned_run_guard=owned_run_guard,
        )
    except mib.ClosureLockedEvaluationInputBundleError as exc:
        raise _error(str(exc).replace("E0-MIB", "E0-MIC", 1)) from exc
    present = [
        path.as_posix()
        for path in CURRENT_LOCK_PATHS
        if _path_exists(path, repo_root=repo_root)
    ]
    expected = [] if current_lock_state == "absent" else [
        path.as_posix() for path in CURRENT_LOCK_PATHS
    ]
    if present != expected:
        raise _error("E0-MIC current P lock state drifted")
    if current_lock_state == "present":
        for path in CURRENT_LOCK_PATHS:
            try:
                mcal._read_regular_bytes_and_metadata(
                    path,
                    repo_root=repo_root,
                    expected_mode=0o644,
                    require_nlink_one=True,
                )
            except mcal.FinalCalibrationError as exc:
                raise _error(f"E0-MIC current P lock drifted: {path}") from exc
    allowed: set[Path] = set()
    if owned_lock_guard is not None:
        mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(owned_lock_guard)
        allowed.add(LOCKER_GUARD_PATH)
    if owned_run_guard is not None:
        mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(owned_run_guard)
    occupied = [
        path.as_posix()
        for path in (*LOCK_TEMPORARY_PATHS, LOCKER_GUARD_PATH)
        if path not in allowed and _path_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MIC coordination namespace is occupied: {occupied}")
    return {
        "historical_published_lock_count": 24,
        "never_published_lock_present_count": predecessor[
            "never_published_lock_present_count"
        ],
        "current_lock_present_count": len(present),
        "coordination_forbidden_count": predecessor[
            "coordination_forbidden_count"
        ] + len(LOCK_TEMPORARY_PATHS) + 1,
        "coordination_present_count": 0,
        "owned_lock_guard_present": owned_lock_guard is not None,
        "owned_run_guard_present": owned_run_guard is not None,
        "r_state": r_state,
        "formal_e0_m_output_present_count": predecessor[
            "formal_e0_m_output_present_count"
        ],
        "outcome_access_log_absent": predecessor["outcome_access_log_absent"],
    }


def preflight_closure_locked_evaluation_input_panel_dvc_identity_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        raw, _ = mcal._read_regular_bytes_and_metadata(
            DEFAULT_PATCH_LOCK_SCHEMA,
            repo_root=root,
            expected_mode=0o644,
            require_nlink_one=True,
        )

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        schema = json.loads(raw, object_pairs_hook=reject_duplicates)
        validator = getattr(mcal.closure_contract, "_assert_supported_json_schema")
        if not isinstance(schema, dict):
            raise ValueError("schema is not an object")
        validator(schema)
    except (OSError, ValueError, mcal.FinalCalibrationError, mcal.ClosureContractError) as exc:
        raise _error("E0-MIC lock schema is unavailable or open") from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schema_version": LOCK_SCHEMA_VERSION,
        "schemas": [
            _file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role=(
                    "locked_evaluation_input_panel_dvc_identity_patch_lock_schema"
                ),
                repo_root=root,
            )
        ],
        "supported_subset_verified": True,
        "duplicate_keys_rejected": True,
    }


def _input_contract(*, repo_root: Path) -> dict[str, Any]:
    value = _deep_copy(mib._locked_input_contract(repo_root=repo_root))
    value["producer_command"] = list(INPUT_BUNDLE_COMMAND)
    return cast(dict[str, Any], value)


def _r_contract() -> dict[str, Any]:
    return _deep_copy(mib._locked_r_contract())


def collect_closure_locked_evaluation_input_panel_dvc_identity_patch_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    source_snapshot = _source_identity_snapshot(root)
    repository, h_patch = _h_patch_authority(
        repo_root=root, verify_remote=verify_remote
    )
    schema = preflight_closure_locked_evaluation_input_panel_dvc_identity_patch_schema(
        repo_root=root
    )
    base = _base_p_mib_authority(repo_root=root)
    historical = _historical_h_mib_records(repo_root=root)
    panel_contract = _deep_copy(PANEL_DVC_IDENTITY_CONTRACT)
    namespace = _require_namespace(
        repo_root=root, current_lock_state="absent", r_state="absent"
    )
    result = {
        "repository": repository,
        "h_patch": h_patch,
        "base_authority": base,
        "input_contract": _input_contract(repo_root=root),
        "r_contract": _r_contract(),
        "panel_dvc_identity_contract": panel_contract,
        "panel_dvc_identity_verified": True,
        "prelock": {
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "coordination_present_count": 0,
            "component_count": 6,
            "companion_contract": {
                "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
                "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
                "output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
                "script_path": LOCKER_PATH.as_posix(),
                "manifest_written_last": True,
            },
            "scientific_execution_run": False,
            "panel_bytes_opened": True,
            "assignment_bytes_opened": True,
            "panel_rows_decoded": False,
            "assignment_rows_decoded": False,
            "target_namespace_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
        },
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "coordination_namespace": namespace,
        "schema_preflight": schema,
    }
    _require_source_identity_snapshot(
        source_snapshot, repo_root=root, context="during prelock collection"
    )
    return result


def _default_unrun_verification() -> dict[str, Any]:
    return mib._default_unrun_verification()


def build_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "h_patch",
        "base_authority",
        "input_contract",
        "r_contract",
        "panel_dvc_identity_contract",
        "panel_dvc_identity_verified",
        "prelock",
        "historical_inputs",
        "historical_inputs_sha256",
        "coordination_namespace",
        "schema_preflight",
    }
    if not isinstance(prelock, Mapping) or set(prelock) != required:
        raise _error("E0-MIC prelock dialect drifted")
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        **{key: _deep_copy(prelock[key]) for key in required},
        "verification": _deep_copy(
            verification if verification is not None else _default_unrun_verification()
        ),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise _error("E0-MIC generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MIC generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MIC generated timestamp must be timezone-aware")


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if value == _default_unrun_verification():
        return
    keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise _error("E0-MIC verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_closure_locked_evaluation_input_panel_dvc_identity_patch_schema(
            repo_root=repo_root
        )
    ):
        raise _error("E0-MIC schema evidence drifted")
    for key, command in (
        ("full_type_check", TYPE_CHECK_COMMAND),
        ("poetry_check", POETRY_CHECK_COMMAND),
        ("publication_guard", PUBLICATION_GUARD_COMMAND),
        ("git_diff_check", DIFF_CHECK_COMMAND),
    ):
        mcal._validate_command_evidence(value[key], expected_command=command, context=key)
    focused = value["focused_tests"]
    base_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if (
        not isinstance(focused, Mapping)
        or set(focused)
        != base_keys | {"test_count", "skipped_count", "deselected_count"}
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise _error("E0-MIC focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


def validate_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    verify_remote: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MIC lock schema validation failed") from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MIC authorizations drifted")
    state = collect_closure_locked_evaluation_input_panel_dvc_identity_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MIC lock semantic reconstruction drifted")
    return dict(payload)


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    base = cast(Mapping[str, Any], payload["base_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    prior = cast(Sequence[Mapping[str, Any]], base["p_components"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    r8 = [
        {
            "role": "published_immutable_r8_output",
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in R8_OUTPUT_CONTRACT
    ]
    inputs = [_public_record(record) for record in (*prior, *current, *r8)]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(inputs) != EXPECTED_COMPANION_INPUT_COUNT
        or len({record["path"] for record in inputs}) != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise _error("E0-MIC companion physical input set drifted")
    historical = [
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], payload["historical_inputs"])
    ]
    historical.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({record["path"] for record in historical})
        != EXPECTED_HISTORICAL_INPUT_COUNT
    ):
        raise _error("E0-MIC companion historical input set drifted")
    script = next(record for record in inputs if record["path"] == LOCKER_PATH.as_posix())
    return {
        "schema_version": COMPANION_SCHEMA_VERSION,
        "status": "completed",
        "gate": PATCH_GATE,
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical,
        "outputs": [dict(lock_record)],
        "manifest_written_last": True,
        "scientific_execution_run": False,
        "input_bundle_run": False,
        "r_files_touched": False,
        "r_files_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _parse_canonical_json(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        value = mcal._parse_json_bytes(payload, context=path.as_posix())
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIC canonical JSON read failed: {path}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MIC canonical JSON drifted: {path}")
    return value, payload, metadata


def _physical_snapshot(repo_root: Path | None = None) -> tuple[dict[str, Any], ...]:
    root = _root(repo_root)
    records: list[dict[str, Any]] = []
    for path in (*P_MIB_PATHS, *(Path(value) for value in PATCH_PATHS)):
        path_text = path.as_posix()
        expected_mode = PATCH_COMPONENT_GIT_MODES.get(path_text, "100644")
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=root,
                expected_mode=int(expected_mode[-3:], 8),
                require_nlink_one=True,
            )
        except mcal.FinalCalibrationError as exc:
            raise _error(f"E0-MIC physical input drifted: {path_text}") from exc
        records.append(
            {
                "path": path_text,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    for expected in R8_OUTPUT_CONTRACT:
        path_text = cast(str, expected["path"])
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                Path(path_text),
                repo_root=root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
        except mcal.FinalCalibrationError as exc:
            raise _error(f"E0-MIC immutable R8 drifted: {path_text}") from exc
        observed = {
            "path": path_text,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed != expected:
            raise _error(f"E0-MIC immutable R8 content drifted: {path_text}")
        records.append(
            {
                "path": path_text,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": observed["sha256"],
            }
        )
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 16 or len({record["path"] for record in records}) != 16:
        raise _error("E0-MIC physical snapshot is not exact16")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(_physical_snapshot(repo_root)):
        raise _error(f"E0-MIC physical authority changed {context}")


def _p_pair_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path in CURRENT_LOCK_PATHS:
        _value, payload, metadata = _parse_canonical_json(path, repo_root=repo_root)
        records.append(
            {
                "path": path.as_posix(),
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
            }
        )
    return tuple(records)


def _require_repository_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    p_outputs_present: bool,
    context: str,
) -> None:
    expected_status = (
        sorted(("??", path.as_posix()) for path in CURRENT_LOCK_PATHS)
        if p_outputs_present
        else []
    )
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main"
        or _git_head(repo_root) != expected_head
        or _git_head(repo_root, "origin/main") != expected_head
        or sorted(mcal._workspace_status_records(repo_root)) != expected_status
    ):
        raise _error(f"E0-MIC repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MIC live remote changed {context}")


def _require_publication_verification(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise _error("E0-MIC publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def publish_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    source_snapshot = _source_identity_snapshot(root)
    frozen = json.loads(_canonical_json_bytes(payload))
    if not isinstance(frozen, dict):
        raise _error("E0-MIC publication payload must be an object")
    repository = frozen.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIC publication H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    if _git_head(root) != h_head or h_head == BASE_P_MIB_COMMIT:
        raise _error("E0-MIC publication requires published H")
    validate_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_payload(
        frozen, verify_remote=True, repo_root=root
    )
    _require_publication_verification(frozen, repo_root=root)
    _require_repository_checkpoint(
        repo_root=root,
        expected_head=h_head,
        verify_remote=True,
        p_outputs_present=False,
        context="before publication",
    )
    _require_namespace(repo_root=root, current_lock_state="absent", r_state="absent")
    snapshot = _physical_snapshot(root)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MIC panel DVC identity patch lock\n",
            repo_root=root,
        )
        _require_namespace(
            repo_root=root,
            current_lock_state="absent",
            r_state="absent",
            owned_lock_guard=guard,
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after guard")
        _require_source_identity_snapshot(
            source_snapshot, repo_root=root, context="after publication guard"
        )
        lock_bytes = _canonical_json_bytes(frozen)
        lock_output = mcalm.mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "locked_evaluation_input_panel_dvc_identity_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(frozen, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mcalm.mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication = ((lock_output, lock_bytes), (companion_output, companion_bytes))
        for output, expected in publication:
            mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                output, expected, repo_root=root, context="after publication"
            )
        _require_namespace(
            repo_root=root,
            current_lock_state="present",
            r_state="absent",
            owned_lock_guard=guard,
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after companion")
        _require_source_identity_snapshot(
            source_snapshot, repo_root=root, context="after lock companion"
        )
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=h_head,
            verify_remote=True,
            p_outputs_present=True,
            context="during publication",
        )
        mt._release_publication_guard(guard)
        guard = None
        for pass_index in (1, 2):
            _require_namespace(
                repo_root=root, current_lock_state="present", r_state="absent"
            )
            _require_physical_snapshot(
                snapshot,
                repo_root=root,
                context=f"during transfer pass {pass_index}",
            )
            _require_source_identity_snapshot(
                source_snapshot,
                repo_root=root,
                context=f"during transfer pass {pass_index}",
            )
            _require_repository_checkpoint(
                repo_root=root,
                expected_head=h_head,
                verify_remote=True,
                p_outputs_present=True,
                context=f"during transfer pass {pass_index}",
            )
            for output, expected in publication:
                mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"ownership transfer pass {pass_index}",
                )
            mcalm.mcall.mcalk.mcalj.mcali._require_owned_identity_set(
                [output for output, _ in publication],
                context=f"MIC ownership transfer pass {pass_index}",
            )
        committed = True
        return dict(frozen), companion
    except BaseException as exc:
        rollback = mcalm.mcall.mcalk._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureLockedEvaluationInputPanelDvcIdentityPatchError):
            raise
        raise _error("E0-MIC lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    mcalm.mcall.mcalk.mcalj._close_owned_output(output)
                except Exception:
                    pass


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_P_MIB_COMMIT:
        raise _error("E0-MIC published H commit is absent")
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MIC")
        != BASE_P_MIB_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MIB_COMMIT, h_head) != expected_scope
    ):
        raise _error("E0-MIC published H topology drifted")
    components = [
        _artifact_record(
            Path(path),
            role="locked_evaluation_input_panel_dvc_identity_patch_h_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    historical = _historical_h_mib_records(repo_root=repo_root)
    namespace = _require_namespace(
        repo_root=repo_root,
        current_lock_state="present",
        r_state=_current_r_state(repo_root=repo_root),
    )
    prelock_namespace = _deep_copy(namespace)
    prelock_namespace["current_lock_present_count"] = 0
    prelock_namespace["r_state"] = "absent"
    return {
        "repository": {
            "base_p_mib_commit": BASE_P_MIB_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": expected_scope,
        },
        "h_patch": {
            "gate": "H-E0-MIC",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
        "base_authority": _base_p_mib_authority(repo_root=repo_root),
        "input_contract": _input_contract(repo_root=repo_root),
        "r_contract": _r_contract(),
        "panel_dvc_identity_contract": _deep_copy(PANEL_DVC_IDENTITY_CONTRACT),
        "panel_dvc_identity_verified": True,
        "prelock": {
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "coordination_present_count": 0,
            "component_count": 6,
            "companion_contract": {
                "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
                "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
                "output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
                "script_path": LOCKER_PATH.as_posix(),
                "manifest_written_last": True,
            },
            "scientific_execution_run": False,
            "panel_bytes_opened": True,
            "assignment_bytes_opened": True,
            "panel_rows_decoded": False,
            "assignment_rows_decoded": False,
            "target_namespace_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
        },
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "coordination_namespace": prelock_namespace,
        "schema_preflight": (
            preflight_closure_locked_evaluation_input_panel_dvc_identity_patch_schema(
                repo_root=repo_root
            )
        ),
    }


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MIC published lock schema validation failed") from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MIC published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIC published H binding is absent")
    state = _published_h_state(cast(str, repository["h_patch_head"]), repo_root=repo_root)
    expected = build_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MIC published lock reconstruction drifted")


def _validate_unpublished_p_repository(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> str:
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main"
        or _git_head(repo_root) != h_head
        or mcal._single_parent(repo_root, h_head, context="H-E0-MIC")
        != BASE_P_MIB_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MIB_COMMIT, h_head) != expected_scope
    ):
        raise _error("E0-MIC unpublished P requires exact H topology")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("E0-MIC unpublished P refs drifted")
    observed = sorted(mcal._workspace_status_records(repo_root))
    if observed == sorted(("??", path.as_posix()) for path in CURRENT_LOCK_PATHS):
        return "untracked"
    if observed == sorted(("A ", path.as_posix()) for path in CURRENT_LOCK_PATHS):
        return "staged"
    raise _error("E0-MIC unpublished P workspace is not exact P2")


def validate_locked_evaluation_input_panel_dvc_identity_patch_unpublished_lock_bundle(
    *, repo_root: Path | None = None, verify_remote: bool = True
) -> dict[str, Any]:
    root = _root(repo_root)
    source_snapshot = _source_identity_snapshot(root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIC unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="locked_evaluation_input_panel_dvc_identity_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MIC unpublished P companion drifted")
    namespace = _require_namespace(
        repo_root=root, current_lock_state="present", r_state="absent"
    )
    snapshot = _physical_snapshot(root)
    panel_contract = _deep_copy(PANEL_DVC_IDENTITY_CONTRACT)
    recaptured_lock, recaptured_lock_bytes, recaptured_lock_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    )
    identity = mcalm.mcall.mcalk.mcalj._metadata_identity
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_lock_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_lock_metadata) != identity(lock_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
    ):
        raise _error("E0-MIC unpublished P changed during validation")
    _require_physical_snapshot(snapshot, repo_root=root, context="during P validation")
    _require_source_identity_snapshot(
        source_snapshot, repo_root=root, context="during P validation"
    )
    if _require_namespace(
        repo_root=root, current_lock_state="present", r_state="absent"
    ) != namespace:
        raise _error("E0-MIC namespace changed during P validation")
    if _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    ) != stage_state:
        raise _error("E0-MIC P stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_present_count": 0,
        "r_state": "absent",
        "panel_dvc_identity_contract": panel_contract,
        "panel_dvc_identity_verified": True,
        "effective_authority": False,
        "input_bundle_execution_authorized": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def _validate_p_publication_state(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> dict[str, Any]:
    head = _git_head(repo_root)
    parent = mcal._single_parent(repo_root, head, context="P/R-E0-MIC")
    p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(path.as_posix() for path in CURRENT_LOCK_PATHS),
    }
    r_scope = {
        "added": 6,
        "modified": 0,
        "deleted": 0,
        "path_count": 6,
        "paths": [path.as_posix() for path in R_TRACKED_OUTPUT_PATHS],
    }
    if parent == h_head:
        p_head = head
        r_head: str | None = None
        if mcal._git_scope(repo_root, h_head, p_head) != p_scope:
            raise _error("E0-MIC published P scope drifted")
    else:
        r_head = head
        p_head = parent
        if (
            mcal._single_parent(repo_root, p_head, context="P-E0-MIC") != h_head
            or mcal._git_scope(repo_root, h_head, p_head) != p_scope
            or mcal._git_scope(repo_root, p_head, r_head) != r_scope
        ):
            raise _error("E0-MIC published R topology drifted")
    if cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main":
        raise _error("E0-MIC effective authority requires main")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MIC effective refs drifted")
    for path in CURRENT_LOCK_PATHS:
        try:
            physical, _ = mcal._read_regular_bytes_and_metadata(
                path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
            )
            mode, _ = mcal._git_mode_oid(repo_root, p_head, path)
            git_payload = mcal._git_blob_bytes(repo_root, p_head, path)
        except mcal.FinalCalibrationError as exc:
            raise _error(f"E0-MIC published P binding drifted: {path}") from exc
        if mode != "100644" or physical != git_payload:
            raise _error(f"E0-MIC published P binding drifted: {path}")
    r_state = _current_r_state(repo_root=repo_root)
    observed = sorted(mcal._workspace_status_records(repo_root))
    if r_head is not None:
        if r_state != "complete" or observed:
            raise _error("E0-MIC published R worktree drifted")
        r_stage_state = "published"
    elif r_state == "absent":
        if observed:
            raise _error("E0-MIC published P clean worktree drifted")
        r_stage_state = "absent"
    elif r_state == "physical_and_light":
        expected = sorted(("??", path.as_posix()) for path in R_LIGHT_OUTPUT_PATHS)
        if observed != expected:
            raise _error("E0-MIC pre-DVC R workspace drifted")
        r_stage_state = "physical_and_light_untracked"
    else:
        untracked = sorted(("??", path.as_posix()) for path in R_TRACKED_OUTPUT_PATHS)
        staged = sorted(("A ", path.as_posix()) for path in R_TRACKED_OUTPUT_PATHS)
        if observed == untracked:
            r_stage_state = "exact6_untracked"
        elif observed == staged:
            r_stage_state = "exact6_staged"
        else:
            raise _error("E0-MIC complete R workspace drifted")
    return {
        "h_patch_head": h_head,
        "p_patch_head": p_head,
        "r_patch_head": r_head,
        "remote_head": remote,
        "r_state": r_state,
        "r_stage_state": r_stage_state,
    }


@contextmanager
def _patched_mib_panel_reader(*, repo_root: Path) -> Iterator[None]:
    """Temporarily replace only MIB's panel identity and input projections."""

    original_load = mib._load_input_projections
    original_recapture = mib._recapture_scientific_source_snapshots
    source_identity = _source_identity_snapshot(repo_root)

    def recapture(*, repo_root: Path) -> list[dict[str, Any]]:
        _require_source_identity_snapshot(
            source_identity, repo_root=repo_root, context="before source recapture"
        )
        records: list[dict[str, Any]] = []
        with mib._open_pinned_regular_file(mib.ASSIGNMENT_PATH, repo_root=repo_root) as (
            descriptor,
            _parent,
            _name,
            metadata,
        ):
            size, sha256, source_md5 = mib._hash_pinned_descriptor(descriptor)
            records.append(
                mib._source_snapshot(
                    mib.ASSIGNMENT_PATH,
                    role="locked_holdout_assignment",
                    payload_size=size,
                    sha256=sha256,
                    metadata=metadata,
                    md5=source_md5,
                )
            )
        panel, metadata = _read_panel_dvc_bytes_and_metadata(repo_root=repo_root)
        records.append(
            mib._source_snapshot(
                mib.PANEL_PATH,
                role="locked_panel_physical_input",
                payload_size=len(panel),
                sha256=_sha256_bytes(panel),
                metadata=metadata,
                md5=hashlib.md5(panel, usedforsecurity=False).hexdigest(),
            )
        )
        _require_source_identity_snapshot(
            source_identity, repo_root=repo_root, context="after source recapture"
        )
        return records

    def load(
        *, repo_root: Path
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        _require_source_identity_snapshot(
            source_identity, repo_root=repo_root, context="before input projection"
        )
        try:
            import pyarrow.csv as pacsv
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise _error("E0-MIC PyArrow input readers are unavailable") from exc
        with mib._open_pinned_regular_file(mib.ASSIGNMENT_PATH, repo_root=repo_root) as (
            descriptor,
            _parent,
            _name,
            _metadata,
        ):
            with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
                assignment_table = pacsv.read_csv(
                    stream,
                    convert_options=pacsv.ConvertOptions(
                        include_columns=list(mib.ASSIGNMENT_COLUMNS)
                    ),
                )
        if list(assignment_table.column_names) != list(mib.ASSIGNMENT_COLUMNS):
            raise _error("E0-MIC assignment scanner projection drifted")
        assignment_rows = assignment_table.to_pylist()
        holdout_site_ids = sorted(
            {
                str(row["site_id"])
                for row in assignment_rows
                if str(row["source_id"]) == "wqp"
                and str(row["assignment_role"]) == "internal_holdout"
            }
        )
        if len(holdout_site_ids) != mib.HOLDOUT_LOCATION_COUNT:
            raise _error("E0-MIC holdout projection is not exact88")
        panel, _metadata = _read_panel_dvc_bytes_and_metadata(repo_root=repo_root)
        panel_table = pq.read_table(
            io.BytesIO(panel),
            columns=list(mib.PANEL_PROJECTION),
            filters=[
                ("source_id", "=", "wqp"),
                ("site_id", "in", holdout_site_ids),
            ],
        )
        if list(panel_table.column_names) != list(mib.PANEL_PROJECTION):
            raise _error("E0-MIC panel scanner projection drifted")
        result = (
            [cast(dict[str, Any], row) for row in assignment_rows],
            [cast(dict[str, Any], row) for row in panel_table.to_pylist()],
            recapture(repo_root=repo_root),
        )
        _require_source_identity_snapshot(
            source_identity, repo_root=repo_root, context="after input projection"
        )
        return result

    setattr(mib, "_load_input_projections", load)
    setattr(mib, "_recapture_scientific_source_snapshots", recapture)
    try:
        yield
    finally:
        setattr(mib, "_load_input_projections", original_load)
        setattr(mib, "_recapture_scientific_source_snapshots", original_recapture)


@contextmanager
def _patched_mib_contract(
    input_contract: Mapping[str, Any],
    *,
    repo_root: Path,
    authority: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    """Bind inherited MIB row/byte semantics to the effective MIC contract."""

    original_contract = mib._locked_input_contract
    original_require = mib.require_locked_evaluation_input_bundle_authority

    def contract(*, repo_root: Path) -> dict[str, Any]:
        del repo_root
        return cast(dict[str, Any], _deep_copy(input_contract))

    def require(
        *, verify_remote: bool = True, repo_root: Path | None = None
    ) -> dict[str, Any]:
        del verify_remote, repo_root
        if authority is None:
            return original_require(
                verify_remote=True,
                repo_root=PROJECT_ROOT,
            )
        return cast(dict[str, Any], _deep_copy(authority))

    setattr(mib, "_locked_input_contract", contract)
    if authority is not None:
        setattr(mib, "require_locked_evaluation_input_bundle_authority", require)
    try:
        with _patched_mib_panel_reader(repo_root=repo_root):
            yield
    finally:
        setattr(mib, "_locked_input_contract", original_contract)
        setattr(mib, "require_locked_evaluation_input_bundle_authority", original_require)


def _load_base_mib_authority(
    *, repo_root: Path, verify_remote: bool
) -> dict[str, Any]:
    """Reconstruct the published P-MIB authority without its superseded HEAD gate."""

    try:
        with _patched_mib_panel_reader(repo_root=repo_root):
            base = _base_p_mib_authority(repo_root=repo_root)
            lock, _lock_bytes, _lock_metadata = mib._parse_canonical_json(
                mib.DEFAULT_PATCH_LOCK_PATH, repo_root=repo_root
            )
            mib._validate_timestamp(lock.get("generated_at_utc"))
            mib._validate_verification(lock.get("verification"), repo_root=repo_root)
            if lock.get("authorizations") != mib.UNPUBLISHED_AUTHORIZATIONS:
                raise _error("E0-MIC inherited P-E0-MIB authorizations drifted")
            lock_record = mib._file_record(
                mib.DEFAULT_PATCH_LOCK_PATH,
                role="locked_evaluation_input_bundle_lock",
                repo_root=repo_root,
            )
            companion, companion_bytes, _companion_metadata = mib._parse_canonical_json(
                mib.DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=repo_root
            )
            if mib._canonical_json_bytes(companion) != mib._canonical_json_bytes(
                mib._expected_companion(lock, lock_record)
            ):
                raise _error("E0-MIC inherited P-E0-MIB companion drifted")
            if type(verify_remote) is not bool:
                raise _error("E0-MIC inherited remote policy must be exact boolean")
            binding = {
                "h_patch_head": BASE_H_MIB_COMMIT,
                "p_patch_head": BASE_P_MIB_COMMIT,
                "lock": lock_record,
                "companion_sha256": mib._sha256_bytes(companion_bytes),
                "input_contract_sha256": mib._sha256_bytes(
                    mib._canonical_json_bytes(lock["input_contract"])
                ),
            }
            authority_binding_sha256 = mib._sha256_bytes(
                mib._canonical_json_bytes(binding)
            )
            r_state = mib._current_r_state(repo_root=repo_root)
            consumed = r_state != "absent"
            return {
                "gate": mib.PATCH_GATE,
                "status": "effective",
                "h_patch_head": BASE_H_MIB_COMMIT,
                "p_patch_head": BASE_P_MIB_COMMIT,
                "r_patch_head": None,
                "remote_head": (
                    mcal._live_remote_main_head(repo_root)
                    if verify_remote
                    else _git_head(repo_root, "origin/main")
                ),
                "r_state": r_state,
                "r_stage_state": (
                    "absent"
                    if r_state == "absent"
                    else (
                        "physical_and_light_untracked"
                        if r_state == "physical_and_light"
                        else "exact6_staged"
                    )
                ),
                "lock": lock_record,
                "companion": mib._file_record(
                    mib.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
                    role="locked_evaluation_input_bundle_lock_manifest",
                    repo_root=repo_root,
                ),
                "authority_binding_sha256": authority_binding_sha256,
                "input_contract": mib._deep_copy(lock["input_contract"]),
                "base_authority": base,
                "r_physical_output_count": 4 if consumed else 0,
                "r_tracked_output_count": 6 if r_state == "complete" else 0,
                "input_bundle_execution_authorized": not consumed,
                "input_bundle_run_consumed": consumed,
                "r_outputs_published": False,
                "r_outputs_sha256": None,
                "effective_authority": True,
                "evaluation_authorized": False,
                "e0_m_authorized": False,
                "e0_u_authorized": False,
                "outcome_access_authorized": False,
                "holdout_outcome_access_authorized": False,
                "post_2021_outcome_access_authorized": False,
                "training_authorized": False,
                "calibration_authorized": False,
                "dvc_commands_authorized": False,
                "dvc_push_authorized": False,
                "git_commit_authorized": False,
                "git_push_authorized": False,
                "writes_performed": False,
            }
    except mib.ClosureLockedEvaluationInputBundleError as exc:
        raise _error(str(exc).replace("E0-MIB", "E0-MIC/MIB", 1)) from exc


def load_effective_closure_locked_evaluation_input_panel_dvc_identity_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    source_snapshot = _source_identity_snapshot(root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="locked_evaluation_input_panel_dvc_identity_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MIC published companion drifted")
    repository = cast(Mapping[str, Any], lock["repository"])
    publication = _validate_p_publication_state(
        h_head=cast(str, repository["h_patch_head"]),
        verify_remote=verify_remote,
        repo_root=root,
    )
    panel_contract = _deep_copy(PANEL_DVC_IDENTITY_CONTRACT)
    base = _load_base_mib_authority(repo_root=root, verify_remote=verify_remote)
    binding = {
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "lock": lock_record,
        "companion_sha256": _sha256_bytes(companion_bytes),
        "panel_dvc_identity_contract_sha256": _sha256_bytes(
            _canonical_json_bytes(panel_contract)
        ),
        "base_mib_authority_binding_sha256": base["authority_binding_sha256"],
    }
    mic_binding = _sha256_bytes(_canonical_json_bytes(binding))
    r_state = cast(str, publication["r_state"])
    namespace = _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    )
    r_semantics_before: dict[str, Any] | None = None
    r_materialization: dict[str, Any] | None = None
    if r_state != "absent":
        with _patched_mib_contract(
            cast(Mapping[str, Any], lock["input_contract"]), repo_root=root
        ):
            r_materialization = mib._build_expected_r_materialization(
                {
                    "input_contract": lock["input_contract"],
                    "authority_binding_sha256": mic_binding,
                },
                repo_root=root,
            )
            r_semantics_before = mib._validate_r_bundle_semantics(
                repo_root=root, pointers_required=r_state == "complete"
            )
            mib._require_expected_r_materialization(
                r_semantics_before, r_materialization
            )
            if cast(Mapping[str, Any], r_semantics_before["manifest"]).get(
                "authority_binding_sha256"
            ) != mic_binding:
                raise _error("E0-MIC R manifest authority binding drifted")
    snapshot = _physical_snapshot(root)
    p_snapshot = _p_pair_snapshot(root)
    recaptured_lock, recaptured_lock_bytes, recaptured_lock_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    )
    identity = mcalm.mcall.mcalk.mcalj._metadata_identity
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_lock_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_lock_metadata) != identity(lock_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
        or _p_pair_snapshot(root) != p_snapshot
    ):
        raise _error("E0-MIC effective authority changed during loading")
    _require_physical_snapshot(snapshot, repo_root=root, context="during effective loading")
    if _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    ) != namespace:
        raise _error("E0-MIC namespace changed during effective loading")
    if _validate_p_publication_state(
        h_head=cast(str, repository["h_patch_head"]),
        verify_remote=verify_remote,
        repo_root=root,
    ) != publication:
        raise _error("E0-MIC publication changed during effective loading")
    consumed = r_state != "absent"
    r_semantics: dict[str, Any] | None = None
    if consumed:
        if r_semantics_before is None or r_materialization is None:
            raise _error("E0-MIC terminal R reconstruction is absent")
        with _patched_mib_contract(
            cast(Mapping[str, Any], lock["input_contract"]), repo_root=root
        ):
            r_semantics = mib._validate_r_bundle_semantics(
                repo_root=root, pointers_required=r_state == "complete"
            )
            mib._require_expected_r_materialization(r_semantics, r_materialization)
        if _canonical_json_bytes(r_semantics) != _canonical_json_bytes(
            r_semantics_before
        ):
            raise _error("E0-MIC R semantics changed during effective loading")
    _require_source_identity_snapshot(
        source_snapshot, repo_root=root, context="during effective loading"
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": _file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="locked_evaluation_input_panel_dvc_identity_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": mic_binding,
        "base_mib_authority_binding_sha256": base["authority_binding_sha256"],
        "input_contract": _deep_copy(lock["input_contract"]),
        "panel_dvc_identity_contract": panel_contract,
        "panel_dvc_identity_verified": True,
        "coordination_namespace": namespace,
        "r_physical_output_count": 4 if consumed else 0,
        "r_tracked_output_count": 6 if r_state == "complete" else 0,
        "r_stage_state": publication["r_stage_state"],
        "input_bundle_execution_authorized": not consumed,
        "input_bundle_run_consumed": consumed,
        "r_outputs_published": publication["r_patch_head"] is not None,
        "r_outputs_sha256": (
            None if r_semantics is None else r_semantics["r_outputs_sha256"]
        ),
        "effective_authority": True,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "holdout_outcome_access_authorized": False,
        "post_2021_outcome_access_authorized": False,
        "training_authorized": False,
        "calibration_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def require_locked_evaluation_input_panel_dvc_identity_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_closure_locked_evaluation_input_panel_dvc_identity_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


def validate_locked_evaluation_input_panel_dvc_identity_patch(
    *,
    repo_root: Path | None = None,
    require_staged: bool = False,
    verify_remote: bool = True,
) -> dict[str, Any]:
    root = _root(repo_root)
    authority = require_locked_evaluation_input_panel_dvc_identity_patch_authority(
        verify_remote=verify_remote, repo_root=root
    )
    try:
        with _patched_mib_contract(
            cast(Mapping[str, Any], authority["input_contract"]),
            authority=authority,
            repo_root=root,
        ):
            validation = mib.validate_locked_evaluation_input_bundle(
                repo_root=root,
                require_staged=require_staged,
                verify_remote=verify_remote,
            )
    except mib.ClosureLockedEvaluationInputBundleError as exc:
        raise _error(str(exc).replace("E0-MIB", "E0-MIC/MIB", 1)) from exc
    return {
        **validation,
        "gate": PATCH_GATE,
        "panel_dvc_identity_contract": authority["panel_dvc_identity_contract"],
        "panel_dvc_identity_verified": True,
    }


@contextmanager
def _patched_mib_execution_authority(
    authority: Mapping[str, Any], *, repo_root: Path
) -> Iterator[None]:
    original_require = mib.require_locked_evaluation_input_bundle_authority
    original_checkpoint = mib._require_execution_authority_checkpoint
    original_core_path = mib.CORE_PATH
    mic_p_snapshot = _p_pair_snapshot(repo_root)
    mib_p_snapshot = mib._p_pair_snapshot(repo_root)
    physical_snapshot = _physical_snapshot(repo_root)
    source_snapshot = _source_identity_snapshot(repo_root)

    def require(
        *, verify_remote: bool = True, repo_root: Path | None = None
    ) -> dict[str, Any]:
        root = _root(repo_root)
        current = require_locked_evaluation_input_panel_dvc_identity_patch_authority(
            verify_remote=verify_remote, repo_root=root
        )
        if (
            current.get("authority_binding_sha256")
            != authority.get("authority_binding_sha256")
            or current.get("base_mib_authority_binding_sha256")
            != authority.get("base_mib_authority_binding_sha256")
            or _p_pair_snapshot(root) != mic_p_snapshot
            or mib._p_pair_snapshot(root) != mib_p_snapshot
        ):
            raise _error("E0-MIC authority changed inside inherited R execution")
        _require_physical_snapshot(
            physical_snapshot,
            repo_root=root,
            context="inside inherited R execution",
        )
        _require_source_identity_snapshot(
            source_snapshot,
            repo_root=root,
            context="inside inherited R execution",
        )
        return {
            **current,
            "authority_binding_sha256": current["authority_binding_sha256"],
            "input_contract": current["input_contract"],
        }

    def checkpoint(
        expected: Mapping[str, Any],
        p_snapshot: Sequence[Mapping[str, Any]],
        *,
        owned_run_guard: Any,
        repo_root: Path,
    ) -> dict[str, Any]:
        mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(owned_run_guard)
        if (
            _p_pair_snapshot(repo_root) != mic_p_snapshot
            or _canonical_json_bytes(p_snapshot)
            != _canonical_json_bytes(mib_p_snapshot)
            or mib._p_pair_snapshot(repo_root) != mib_p_snapshot
        ):
            raise _error("E0-MIC/MIB P identity changed under the run guard")
        _require_source_identity_snapshot(
            source_snapshot, repo_root=repo_root, context="under the run guard"
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=repo_root, context="under the run guard"
        )
        lock, _lock_bytes, _lock_metadata = _parse_canonical_json(
            DEFAULT_PATCH_LOCK_PATH, repo_root=repo_root
        )
        lock_repository = cast(Mapping[str, Any], lock["repository"])
        publication = _validate_p_publication_state(
            h_head=cast(str, lock_repository["h_patch_head"]),
            verify_remote=True,
            repo_root=repo_root,
        )
        _require_namespace(
            repo_root=repo_root,
            current_lock_state="present",
            r_state=cast(str, publication["r_state"]),
            owned_run_guard=owned_run_guard,
        )
        if (
            authority.get("authority_binding_sha256")
            != expected.get("authority_binding_sha256")
            or authority.get("input_contract") != expected.get("input_contract")
            or lock.get("input_contract") != authority.get("input_contract")
            or _validate_panel_dvc_identity(repo_root=repo_root)
            != authority.get("panel_dvc_identity_contract")
        ):
            raise _error("E0-MIC execution authority changed under the run guard")
        return publication

    setattr(mib, "require_locked_evaluation_input_bundle_authority", require)
    setattr(mib, "_require_execution_authority_checkpoint", checkpoint)
    setattr(mib, "CORE_PATH", CORE_PATH)
    try:
        with _patched_mib_contract(
            cast(Mapping[str, Any], authority["input_contract"]),
            repo_root=repo_root,
        ):
            yield
    finally:
        setattr(mib, "CORE_PATH", original_core_path)
        setattr(mib, "_require_execution_authority_checkpoint", original_checkpoint)
        setattr(
            mib,
            "require_locked_evaluation_input_bundle_authority",
            original_require,
        )


def execute_locked_evaluation_input_panel_dvc_identity_patch(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    authority = require_locked_evaluation_input_panel_dvc_identity_patch_authority(
        verify_remote=True, repo_root=root
    )
    if (
        authority.get("input_bundle_execution_authorized") is not True
        or authority.get("input_bundle_run_consumed") is not False
        or tuple(sys.argv) != (str(Path(sys.argv[0])), "--execute-input-bundle")
        or Path(sys.argv[0]).resolve() != (root / CORE_PATH).resolve()
    ):
        raise _error("E0-MIC input-bundle command/one-shot authority drifted")
    panel_contract = _deep_copy(PANEL_DVC_IDENTITY_CONTRACT)
    try:
        with _patched_mib_execution_authority(authority, repo_root=root):
            result = mib.execute_locked_evaluation_input_bundle(repo_root=root)
    except mib.ClosureLockedEvaluationInputBundleError as exc:
        raise _error(str(exc).replace("E0-MIB", "E0-MIC/MIB", 1)) from exc
    return {
        **result,
        "gate": "R-E0-MI",
        "authority_gate": PATCH_GATE,
        "panel_dvc_identity_contract": panel_contract,
        "panel_dvc_identity_verified": True,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-input-bundle", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(argv)
    try:
        payload = execute_locked_evaluation_input_panel_dvc_identity_patch()
    except ClosureLockedEvaluationInputPanelDvcIdentityPatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
