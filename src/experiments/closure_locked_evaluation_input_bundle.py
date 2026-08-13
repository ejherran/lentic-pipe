#!/usr/bin/env python
"""Lock and materialize the outcome-blind Closure V1 evaluation inputs.

E0-MIB is an additive authority over the published P-E0-MCALM commit.  Its
H/P path is metadata-only.  The separately authorized R producer reads only
the holdout assignment identifiers and an explicit no-Chl-a panel projection;
it never opens the target namespace or derives an origin from target
availability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import io
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (
    closure_final_calibration_r8_post_publication_authority_patch as mcalm,
)


mcal = mcalm.mcal
mt = mcalm.mt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_P_MCALM_COMMIT = "81c1fc485902d484264fccc53cf88888c359930d"
BASE_H_MCALM_COMMIT = "a7dc955d6c565779a4ddd0df16bb83f1c89f687b"
BASE_R_MCALL_COMMIT = mcalm.BASE_R_MCALL_COMMIT
PATCH_GATE = "E0-MIB"
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = "closure_locked_evaluation_input_bundle_lock_v1"
COMPANION_SCHEMA_VERSION = (
    "closure_locked_evaluation_input_bundle_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/locked_evaluation_input_bundle_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "configs/closure_v1/locked_evaluation_input_bundle_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "configs/closure_v1/locked_evaluation_input_bundle_lock_manifest.json"
)
LOCKER_PATH = Path(
    "src/experiments/lock_closure_locked_evaluation_input_bundle.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mib/locked_evaluation_input_bundle_lock.guard"
)
INPUT_RUN_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mib/locked_evaluation_input_bundle_run.guard"
)

PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = "src/experiments/closure_locked_evaluation_input_bundle.py"
TEST_PATH = "tests/test_closure_locked_evaluation_input_bundle.py"
DOCUMENTATION_PATH = "docs/closure_v1/E0_M_LOCKED_EVALUATION_INPUT_BUNDLE.md"
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
LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE = {
    path: ("M" if path == PRECOMMIT_PATH else "A") for path in PATCH_PATHS
}
LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}

R_PHYSICAL_OUTPUT_PATHS = (
    Path("data/closure_v1/locked_evaluation/input_history.parquet"),
    Path("data/closure_v1/locked_evaluation/intent_origins.parquet"),
    Path("data/closure_v1/locked_evaluation/origin_features.parquet"),
    Path("data/closure_v1/locked_evaluation/sequence_features.parquet"),
)
R_POINTER_PATHS = tuple(Path(f"{path.as_posix()}.dvc") for path in R_PHYSICAL_OUTPUT_PATHS)
R_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/locked_evaluation_input_summary.json"
)
R_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json"
)
R_LIGHT_OUTPUT_PATHS = (R_SUMMARY_PATH, R_MANIFEST_PATH)
R_PUBLICATION_ORDER = (
    *R_PHYSICAL_OUTPUT_PATHS,
    R_SUMMARY_PATH,
    R_MANIFEST_PATH,
)
R_TRACKED_OUTPUT_PATHS = tuple(
    sorted((*R_POINTER_PATHS, *R_LIGHT_OUTPUT_PATHS), key=lambda path: path.as_posix())
)
LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE = {
    path.as_posix(): "A" for path in R_TRACKED_OUTPUT_PATHS
}

ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
RUNTIME_CONFIG_PATH = Path("configs/closure_v1/baseline_development_runtime.yaml")
MODEL_BENCHMARK_PATH = Path("configs/closure_v1/model_benchmark.yaml")
LOCKED_EVALUATION_START = "2022-01"
HOLDOUT_LOCATION_COUNT = 88
HISTORY_LENGTH = 12
HORIZONS = (1, 2, 3)
INPUT_BUNDLE_COMMAND = (
    "poetry",
    "run",
    "python",
    "src/experiments/closure_locked_evaluation_input_bundle.py",
    "--execute-input-bundle",
)
ASSIGNMENT_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "assignment_role",
)
PHYSICAL_FEATURE_COLUMNS = (
    "mean_TP_ugL", "std_TP_ugL", "n_obs_TP_ugL", "n_bad_TP_ugL", "qc_ok_rate_TP_ugL",
    "mean_TN_ugL", "std_TN_ugL", "n_obs_TN_ugL", "n_bad_TN_ugL", "qc_ok_rate_TN_ugL",
    "mean_temperature_C", "std_temperature_C", "n_obs_temperature_C", "n_bad_temperature_C", "qc_ok_rate_temperature_C",
    "mean_secchi_depth_m", "std_secchi_depth_m", "n_obs_secchi_depth_m", "n_bad_secchi_depth_m", "qc_ok_rate_secchi_depth_m",
    "mean_turbidity_NTU", "std_turbidity_NTU", "n_obs_turbidity_NTU", "n_bad_turbidity_NTU", "qc_ok_rate_turbidity_NTU",
    "mean_DO_mgL", "std_DO_mgL", "n_obs_DO_mgL", "n_bad_DO_mgL", "qc_ok_rate_DO_mgL",
    "mean_pH", "std_pH", "n_obs_pH", "n_bad_pH", "qc_ok_rate_pH",
    "log_TP", "log_TN", "TN_TP_ratio",
)
DERIVED_CALENDAR_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
PANEL_PROJECTION = ("source_id", "site_id", "year_month", *PHYSICAL_FEATURE_COLUMNS)
ORIGIN_COMMON_COLUMNS = (
    "origin_id", "source_id", "site_id", "holdout_group_id", "assignment_role",
    "origin_year_month", "base_input_status", "base_input_reason",
)
INTENT_ORIGIN_COLUMNS = (
    *ORIGIN_COMMON_COLUMNS,
    "history_start_year_month", "history_end_year_month", "history_length_months",
    "history_row_count", "missing_history_row_count",
)
INPUT_HISTORY_COLUMNS = (
    *ORIGIN_COMMON_COLUMNS,
    "history_year_month", "history_offset_months", "row_present",
    *PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS,
)
ORIGIN_FEATURE_COLUMNS = (
    *ORIGIN_COMMON_COLUMNS, "row_present",
    *PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS,
)
SEQUENCE_FEATURE_COLUMNS = (
    *ORIGIN_COMMON_COLUMNS, "sequence_length", "sequence_row_present",
    *(f"sequence_{column}" for column in (*PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS)),
)
R_PARQUET_COLUMN_CONTRACT = {
    R_PHYSICAL_OUTPUT_PATHS[0].as_posix(): INPUT_HISTORY_COLUMNS,
    R_PHYSICAL_OUTPUT_PATHS[1].as_posix(): INTENT_ORIGIN_COLUMNS,
    R_PHYSICAL_OUTPUT_PATHS[2].as_posix(): ORIGIN_FEATURE_COLUMNS,
    R_PHYSICAL_OUTPUT_PATHS[3].as_posix(): SEQUENCE_FEATURE_COLUMNS,
}
FORBIDDEN_SCIENTIFIC_PATH_PREFIXES = (
    "data/targets/",
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
)
FORBIDDEN_BUNDLE_COLUMN_TOKENS = (
    "target",
    "chlorophyll",
    "chla",
    "outcome",
    "availability",
    "evaluable",
    "prediction",
    "metric",
    "horizon",
    "evaluation_unit",
    "chl_a",
)

E0_M_OUTPUT_PATHS = (
    Path("reports/closure_v1/00_protocol/model_lock.yaml"),
    Path("reports/closure_v1/00_protocol/calibration_lock.yaml"),
    Path("reports/closure_v1/00_protocol/hypothesis_registry.csv"),
    Path("reports/closure_v1/00_protocol/locked_batch_command.txt"),
    Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl"),
)
CURRENT_LOCK_PATHS = (
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_MANIFEST_PATH,
)
P_MCALM_PATHS = tuple(mcalm.CURRENT_LOCK_PATHS)
R8_OUTPUT_CONTRACT = tuple(mcalm.R8_OUTPUT_CONTRACT)
R8_OUTPUT_PATHS = tuple(mcalm.R_OUTPUT_PATHS)
H_MCALM_PATHS = tuple(mcalm.PATCH_PATHS)
LOCK_TEMPORARY_PATHS = tuple(
    mcal._temporary_path(path) for path in CURRENT_LOCK_PATHS
)
R_TEMPORARY_PATHS = tuple(
    mcal._temporary_path(path)
    for path in (*R_PHYSICAL_OUTPUT_PATHS, *R_LIGHT_OUTPUT_PATHS)
)
COORDINATION_NAMESPACE_PATHS = tuple(
    sorted(
        (
            *LOCK_TEMPORARY_PATHS,
            LOCKER_GUARD_PATH,
            INPUT_RUN_GUARD_PATH,
            *R_TEMPORARY_PATHS,
        ),
        key=lambda path: path.as_posix(),
    )
)

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 6
EXPECTED_COMPANION_OUTPUT_COUNT = 1
TYPE_CHECK_COMMAND = mcalm.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry", "run", "pytest", "-q",
    "tests/test_prepare_commit_artifacts.py", TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcalm.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcalm.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcalm.DIFF_CHECK_COMMAND

UNPUBLISHED_AUTHORIZATIONS = {
    "input_bundle_execution_authorized": False,
    "input_bundle_run_consumed": False,
    "evaluation_authorized": False,
    "e0_m_authorized": False,
    "e0_u_authorized": False,
    "outcome_access_authorized": False,
    "holdout_outcome_access_authorized": False,
    "post_2021_outcome_access_authorized": False,
    "training_authorized": False,
    "calibration_authorized": False,
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_authorized": False,
    "git_push_authorized": False,
}


class ClosureLockedEvaluationInputBundleError(RuntimeError):
    """Raised when any E0-MIB authority or bundle invariant drifts."""


def _error(message: str) -> ClosureLockedEvaluationInputBundleError:
    return ClosureLockedEvaluationInputBundleError(message)


def _root(repo_root: Path | None = None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _deep_copy(value: Any) -> Any:
    return json.loads(_canonical_json_bytes(value))


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    return mcal._git_head(repo_root, ref)


def _path_exists(path: Path, *, repo_root: Path) -> bool:
    return mcal._entry_exists(path, repo_root=repo_root)


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
        raise _error(f"E0-MIB artifact binding drifted: {path.as_posix()}") from exc


def _git_record_at_commit(
    path: Path,
    *,
    role: str,
    commit: str,
    repo_root: Path,
    expected_mode: str = "100644",
) -> dict[str, Any]:
    try:
        mode, oid = mcal._git_mode_oid(repo_root, commit, path)
        payload = mcal._git_blob_bytes(repo_root, commit, path)
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIB historical Git binding drifted: {path}") from exc
    if mode != expected_mode:
        raise _error(f"E0-MIB historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _file_record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
    try:
        return mcal._file_record(path, role=role, repo_root=repo_root)
    except mcal.FinalCalibrationError as exc:
        raise _error(f"E0-MIB file record drifted: {path.as_posix()}") from exc


@contextmanager
def _open_pinned_regular_file(
    path: Path, *, repo_root: Path, expected_mode: int = 0o644
) -> Iterator[tuple[int, int, str, os.stat_result]]:
    parent: int | None = None
    descriptor: int | None = None
    try:
        parent, name = mcal._open_anchored_parent(path, repo_root=repo_root)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=parent)
        metadata = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (named.st_dev, named.st_ino)
            or stat.S_IMODE(metadata.st_mode) != expected_mode
            or stat.S_IMODE(named.st_mode) != expected_mode
            or metadata.st_nlink != 1
            or named.st_nlink != 1
        ):
            raise _error(f"E0-MIB source is not one stable regular file: {path}")
        yield descriptor, parent, name, metadata
        after = os.fstat(descriptor)
        named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        identity = lambda value: (
            int(value.st_dev),
            int(value.st_ino),
            int(value.st_mode),
            int(value.st_nlink),
            int(value.st_size),
            int(value.st_mtime_ns),
            int(value.st_ctime_ns),
        )
        if identity(after) != identity(metadata) or identity(named_after) != identity(
            metadata
        ):
            raise _error(f"E0-MIB source changed while pinned: {path}")
    except ClosureLockedEvaluationInputBundleError:
        raise
    except (OSError, mcal.FinalCalibrationError) as exc:
        raise _error(f"E0-MIB could not pin source: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def _hash_pinned_descriptor(descriptor: int) -> tuple[int, str, str]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        sha256.update(chunk)
        md5.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return size, sha256.hexdigest(), md5.hexdigest()


def _source_snapshot(
    path: Path,
    *,
    role: str,
    payload_size: int,
    sha256: str,
    metadata: os.stat_result,
    md5: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "role": role,
        "path": path.as_posix(),
        "bytes": payload_size,
        "sha256": sha256,
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
    }
    if md5 is not None:
        record["md5"] = md5
    return record


def _public_source_snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key] for key in ("role", "path", "bytes", "sha256")
    }


def _input_source_records(*, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _git_record_at_commit(
            ASSIGNMENT_PATH,
            role="locked_holdout_assignment",
            repo_root=repo_root,
            commit=BASE_P_MCALM_COMMIT,
        ),
        _git_record_at_commit(
            Path(f"{PANEL_PATH.as_posix()}.dvc"),
            role="locked_panel_dvc_pointer",
            repo_root=repo_root,
            commit=BASE_P_MCALM_COMMIT,
        ),
        _git_record_at_commit(
            RUNTIME_CONFIG_PATH,
            role="baseline_runtime_feature_contract",
            repo_root=repo_root,
            commit=BASE_P_MCALM_COMMIT,
        ),
        _git_record_at_commit(
            MODEL_BENCHMARK_PATH,
            role="model_benchmark_contract",
            repo_root=repo_root,
            commit=BASE_P_MCALM_COMMIT,
        ),
    ]
    records.sort(key=lambda record: cast(str, record["path"]))
    return records


def _base_p_mcalm_authority(*, repo_root: Path) -> dict[str, Any]:
    """Validate published P-MCALM and R8 without its clean-worktree loader."""
    try:
        parent = mcal._single_parent(
            repo_root, BASE_P_MCALM_COMMIT, context="P-E0-MCALM"
        )
        if parent != BASE_H_MCALM_COMMIT:
            raise _error("E0-MIB base P-E0-MCALM parent drifted")
        scope = mcal._git_scope(repo_root, parent, BASE_P_MCALM_COMMIT)
        expected_scope = {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(path.as_posix() for path in P_MCALM_PATHS),
        }
        if scope != expected_scope:
            raise _error("E0-MIB base P-E0-MCALM scope drifted")
        lock_bytes = mcal._git_blob_bytes(
            repo_root, BASE_P_MCALM_COMMIT, mcalm.DEFAULT_PATCH_LOCK_PATH
        )
        companion_bytes = mcal._git_blob_bytes(
            repo_root, BASE_P_MCALM_COMMIT, mcalm.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        )
        lock = mcal._parse_json_bytes(lock_bytes, context="historical P-MCALM lock")
        companion = mcal._parse_json_bytes(
            companion_bytes, context="historical P-MCALM companion"
        )
        if (
            not isinstance(lock, Mapping)
            or not isinstance(companion, Mapping)
            or lock_bytes != mcalm._canonical_json_bytes(lock)
            or companion_bytes != mcalm._canonical_json_bytes(companion)
            or lock.get("gate") != mcalm.PATCH_GATE
            or lock.get("schema_version") != mcalm.LOCK_SCHEMA_VERSION
            or lock.get("authorizations") != mcalm.UNPUBLISHED_AUTHORIZATIONS
        ):
            raise _error("E0-MIB historical P-MCALM canonical payload drifted")
        schema_bytes = mcal._git_blob_bytes(
            repo_root, BASE_H_MCALM_COMMIT, mcalm.DEFAULT_PATCH_LOCK_SCHEMA
        )
        schema = mcal._parse_json_bytes(schema_bytes, context="historical H-MCALM schema")
        if not isinstance(schema, Mapping):
            raise _error("E0-MIB historical H-MCALM schema drifted")
        try:
            mcal.validate_json_schema(lock, schema)
        except mcal.ClosureContractError as exc:
            raise _error("E0-MIB historical P-MCALM schema validation drifted") from exc
        mcalm._validate_timestamp(lock.get("generated_at_utc"))
        mcalm._validate_verification(lock.get("verification"), repo_root=repo_root)
        lock_record = {
            "role": "final_calibration_r8_post_publication_authority_patch_lock",
            "path": mcalm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        if companion_bytes != mcalm._canonical_json_bytes(
            mcalm._expected_companion(lock, lock_record)
        ):
            raise _error("E0-MIB base P-E0-MCALM companion drifted")
        physical = [
            _artifact_record(
                path,
                role=(
                    "published_p_mcalm_lock"
                    if path == mcalm.DEFAULT_PATCH_LOCK_PATH
                    else "published_p_mcalm_lock_manifest"
                ),
                repo_root=repo_root,
                commit=BASE_P_MCALM_COMMIT,
            )
            for path in P_MCALM_PATHS
        ]
        r8 = mcalm._validate_r8_bundle_post_publication(repo_root=repo_root)
    except ClosureLockedEvaluationInputBundleError:
        raise
    except Exception as exc:
        raise _error("E0-MIB base P-E0-MCALM authority drifted") from exc
    return {
        "gate": mcalm.PATCH_GATE,
        "status": "published_p_mcalm_authority_validated",
        "p_commit": BASE_P_MCALM_COMMIT,
        "h_commit": BASE_H_MCALM_COMMIT,
        "r_commit": BASE_R_MCALL_COMMIT,
        "p_scope": scope,
        "p_components": physical,
        "p_components_sha256": mcal._digest_records(physical),
        "lock_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "r8_output_count": 8,
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
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
        raise _error("E0-MIB remote policy must be exact boolean")
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MIB requires branch main")
    head = _git_head(repo_root)
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if head == BASE_P_MCALM_COMMIT:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MIB candidate workspace is not exact 1M+5A")
        component_commit: str | None = None
        h_head = BASE_P_MCALM_COMMIT
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MIB")
            != BASE_P_MCALM_COMMIT
            or mcal._git_scope(repo_root, BASE_P_MCALM_COMMIT, head)
            != expected_scope
            or mcal._workspace_status_records(repo_root)
        ):
            raise _error("E0-MIB published H topology/worktree drifted")
        component_commit = head
        h_head = head
    components = [
        _artifact_record(
            Path(path),
            role="locked_evaluation_input_bundle_h_component",
            repo_root=repo_root,
            commit=component_commit,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = _git_head(repo_root, "origin/main")
    expected_ref = BASE_P_MCALM_COMMIT if component_commit is None else head
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != expected_ref or remote != expected_ref:
        raise _error("E0-MIB H refs drifted")
    return (
        {
            "base_p_mcalm_commit": BASE_P_MCALM_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": expected_scope,
        },
        {
            "gate": "H-E0-MIB",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


def _historical_h_mcalm_records(*, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        {
            **_git_record_at_commit(
                Path(path),
                role="superseded_h_mcalm_component",
                repo_root=repo_root,
                commit=BASE_H_MCALM_COMMIT,
                expected_mode=mcalm.PATCH_COMPONENT_GIT_MODES[path],
            ),
            "commit": BASE_H_MCALM_COMMIT,
        }
        for path in H_MCALM_PATHS
    ]
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 6:
        raise _error("E0-MIB historical H-MCALM set is not exact6")
    return records


def _current_r_state(*, repo_root: Path) -> str:
    physical = [_path_exists(path, repo_root=repo_root) for path in R_PHYSICAL_OUTPUT_PATHS]
    light = [_path_exists(path, repo_root=repo_root) for path in R_LIGHT_OUTPUT_PATHS]
    pointers = [_path_exists(path, repo_root=repo_root) for path in R_POINTER_PATHS]
    if not any((*physical, *light, *pointers)):
        return "absent"
    if all(physical) and all(light) and not any(pointers):
        return "physical_and_light"
    if all(physical) and all(light) and all(pointers):
        return "complete"
    raise _error("E0-MIB R namespace is partial")


def _require_namespace(
    *,
    repo_root: Path,
    current_lock_state: str,
    r_state: str,
    owned_lock_guard: Any | None = None,
    owned_run_guard: Any | None = None,
) -> dict[str, Any]:
    if current_lock_state not in {"absent", "present"}:
        raise _error("E0-MIB current lock state policy drifted")
    if r_state not in {"absent", "physical_and_light", "complete"}:
        raise _error("E0-MIB R state policy drifted")
    predecessor = mcalm._require_coordination_namespace(
        repo_root=repo_root, current_outputs_state="present"
    )
    current_present = [
        path.as_posix() for path in CURRENT_LOCK_PATHS if _path_exists(path, repo_root=repo_root)
    ]
    expected_current = [] if current_lock_state == "absent" else [
        path.as_posix() for path in CURRENT_LOCK_PATHS
    ]
    if current_present != expected_current:
        raise _error("E0-MIB current P lock state drifted")
    if current_lock_state == "present":
        for path in CURRENT_LOCK_PATHS:
            mcal._read_regular_bytes_and_metadata(
                path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
            )
    observed_r = _current_r_state(repo_root=repo_root)
    if observed_r != r_state:
        raise _error(f"E0-MIB R state drifted: expected {r_state}, observed {observed_r}")
    allowed: set[Path] = set()
    if owned_lock_guard is not None:
        mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(owned_lock_guard)
        allowed.add(LOCKER_GUARD_PATH)
    if owned_run_guard is not None:
        mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(owned_run_guard)
        allowed.add(INPUT_RUN_GUARD_PATH)
    occupied = [
        path.as_posix()
        for path in COORDINATION_NAMESPACE_PATHS
        if path not in allowed and _path_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MIB coordination namespace is occupied: {occupied}")
    formal = [
        path.as_posix() for path in E0_M_OUTPUT_PATHS if _path_exists(path, repo_root=repo_root)
    ]
    if formal:
        raise _error(f"E0-MIB formal E0-M/outcome paths appeared: {formal}")
    return {
        "historical_published_lock_count": 22,
        "never_published_lock_present_count": predecessor[
            "never_published_lock_present_count"
        ],
        "current_lock_present_count": len(current_present),
        "coordination_forbidden_count": len(mcalm.COORDINATION_NAMESPACE_PATHS)
        + len(COORDINATION_NAMESPACE_PATHS),
        "coordination_present_count": 0,
        "owned_lock_guard_present": owned_lock_guard is not None,
        "owned_run_guard_present": owned_run_guard is not None,
        "r_state": r_state,
        "formal_e0_m_output_present_count": 0,
        "outcome_access_log_absent": True,
    }


def preflight_closure_locked_evaluation_input_bundle_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Validate the closed schema without importing scientific libraries."""
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
    except (OSError, ValueError, mcal.FinalCalibrationError) as exc:
        raise _error("E0-MIB lock schema is unavailable") from exc
    if not isinstance(schema, dict):
        raise _error("E0-MIB lock schema must be an object")
    validator = getattr(mcal.closure_contract, "_assert_supported_json_schema", None)
    if validator is None:
        raise _error("E0-MIB closed schema preflight is unavailable")
    try:
        validator(schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MIB schema leaves the supported closed subset") from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schema_version": LOCK_SCHEMA_VERSION,
        "schemas": [
            _file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role="locked_evaluation_input_bundle_lock_schema",
                repo_root=root,
            )
        ],
        "supported_subset_verified": True,
        "duplicate_keys_rejected": True,
    }


def _locked_input_contract(*, repo_root: Path) -> dict[str, Any]:
    source_records = _input_source_records(repo_root=repo_root)
    return {
        "assignment_path": ASSIGNMENT_PATH.as_posix(),
        "assignment_columns": list(ASSIGNMENT_COLUMNS),
        "assignment_role": "internal_holdout",
        "producer_command": list(INPUT_BUNDLE_COMMAND),
        "panel_path": PANEL_PATH.as_posix(),
        "panel_projection": list(PANEL_PROJECTION),
        "panel_projection_count": len(PANEL_PROJECTION),
        "physical_feature_columns": list(PHYSICAL_FEATURE_COLUMNS),
        "physical_feature_count": len(PHYSICAL_FEATURE_COLUMNS),
        "derived_calendar_columns": list(DERIVED_CALENDAR_COLUMNS),
        "derived_calendar_count": len(DERIVED_CALENDAR_COLUMNS),
        "locked_evaluation_origin_start": LOCKED_EVALUATION_START,
        "locked_evaluation_origin_end_rule": (
            "last_panel_month_with_required_input_projection"
        ),
        "history_length_months": HISTORY_LENGTH,
        "horizons_deferred_to_evaluation": list(HORIZONS),
        "target_months_materialized": False,
        "target_availability_inspected": False,
        "target_namespace_opened": False,
        "outcome_access_log_opened": False,
        "forbidden_path_prefixes": list(FORBIDDEN_SCIENTIFIC_PATH_PREFIXES),
        "source_records": source_records,
        "source_records_sha256": mcal._digest_records(source_records),
    }


def _locked_r_contract() -> dict[str, Any]:
    return {
        "gate": "R-E0-MI",
        "physical_output_count": len(R_PHYSICAL_OUTPUT_PATHS),
        "physical_output_paths": [
            path.as_posix() for path in R_PHYSICAL_OUTPUT_PATHS
        ],
        "pointer_output_count": len(R_POINTER_PATHS),
        "pointer_output_paths": [path.as_posix() for path in R_POINTER_PATHS],
        "light_output_count": len(R_LIGHT_OUTPUT_PATHS),
        "light_output_paths": [path.as_posix() for path in R_LIGHT_OUTPUT_PATHS],
        "tracked_output_count": len(R_TRACKED_OUTPUT_PATHS),
        "tracked_output_paths": [path.as_posix() for path in R_TRACKED_OUTPUT_PATHS],
        "publication_order": [path.as_posix() for path in R_PUBLICATION_ORDER],
        "manifest_written_last": True,
        "dvc_registration_is_separate": True,
    }


def collect_closure_locked_evaluation_input_bundle_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    repository, h_patch = _h_patch_authority(
        repo_root=root, verify_remote=verify_remote
    )
    schema = preflight_closure_locked_evaluation_input_bundle_schema(repo_root=root)
    base = _base_p_mcalm_authority(repo_root=root)
    historical = _historical_h_mcalm_records(repo_root=root)
    namespace = _require_namespace(
        repo_root=root, current_lock_state="absent", r_state="absent"
    )
    return {
        "repository": repository,
        "h_patch": h_patch,
        "base_authority": base,
        "input_contract": _locked_input_contract(repo_root=root),
        "r_contract": _locked_r_contract(),
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
            "panel_opened": False,
            "assignment_opened": False,
            "target_namespace_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
        },
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "coordination_namespace": namespace,
        "schema_preflight": schema,
    }


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "input_bundle_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def build_closure_locked_evaluation_input_bundle_lock_payload(
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
        "prelock",
        "historical_inputs",
        "historical_inputs_sha256",
        "coordination_namespace",
        "schema_preflight",
    }
    if not isinstance(prelock, Mapping) or set(prelock) != required:
        raise _error("E0-MIB prelock dialect drifted")
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
        raise _error("E0-MIB generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MIB generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MIB generated timestamp must be timezone-aware")


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
        raise _error("E0-MIB verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_closure_locked_evaluation_input_bundle_schema(repo_root=repo_root)
    ):
        raise _error("E0-MIB schema verification evidence drifted")
    for key, command in (
        ("full_type_check", TYPE_CHECK_COMMAND),
        ("poetry_check", POETRY_CHECK_COMMAND),
        ("publication_guard", PUBLICATION_GUARD_COMMAND),
        ("git_diff_check", DIFF_CHECK_COMMAND),
    ):
        mcal._validate_command_evidence(value[key], expected_command=command, context=key)
    focused = value["focused_tests"]
    base_keys = {
        "command", "returncode", "stdout_sha256", "stderr_sha256",
        "stdout_line_count", "stderr_line_count",
    }
    if (
        not isinstance(focused, Mapping)
        or set(focused) != base_keys | {"test_count", "skipped_count", "deselected_count"}
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise _error("E0-MIB focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


def validate_closure_locked_evaluation_input_bundle_lock_payload(
    payload: Mapping[str, Any],
    *,
    verify_remote: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MIB lock payload must be an object")
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MIB lock schema validation failed") from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MIB authorizations drifted")
    state = collect_closure_locked_evaluation_input_bundle_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_closure_locked_evaluation_input_bundle_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MIB lock semantic reconstruction drifted")
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
        raise _error("E0-MIB companion physical input set drifted")
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
        raise _error("E0-MIB companion historical input set drifted")
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


def _require_publication_verification(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise _error("E0-MIB publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(repo_root: Path | None = None) -> tuple[dict[str, Any], ...]:
    root = _root(repo_root)
    records: list[dict[str, Any]] = []
    for path in (*P_MCALM_PATHS, *(Path(value) for value in PATCH_PATHS)):
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
            raise _error(f"E0-MIB physical input drifted: {path_text}") from exc
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
            raise _error(f"E0-MIB immutable R8 drifted: {path_text}") from exc
        observed = {
            "path": path_text,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed != expected:
            raise _error(f"E0-MIB immutable R8 content drifted: {path_text}")
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
        raise _error("E0-MIB physical snapshot is not exact16")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root)
    ):
        raise _error(f"E0-MIB physical authority changed {context}")


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
        raise _error(f"E0-MIB canonical JSON read failed: {path}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MIB canonical JSON drifted: {path}")
    return value, payload, metadata


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
        raise _error(f"E0-MIB repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MIB live remote changed {context}")


def publish_closure_locked_evaluation_input_bundle_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    try:
        lock_bytes = _canonical_json_bytes(payload)
        frozen = json.loads(lock_bytes)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _error("E0-MIB publication payload is not canonical JSON") from exc
    if not isinstance(frozen, dict) or _canonical_json_bytes(frozen) != lock_bytes:
        raise _error("E0-MIB publication payload must be a canonical object")
    repository = frozen.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIB publication H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    if _git_head(root) != h_head or h_head == BASE_P_MCALM_COMMIT:
        raise _error("E0-MIB publication requires published H")
    validate_closure_locked_evaluation_input_bundle_lock_payload(
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
            b"E0-MIB locked evaluation input bundle lock\n",
            repo_root=root,
        )
        _require_namespace(
            repo_root=root,
            current_lock_state="absent",
            r_state="absent",
            owned_lock_guard=guard,
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after guard")
        lock_output = mcalm.mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "locked_evaluation_input_bundle_lock",
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
        _require_physical_snapshot(
            snapshot, repo_root=root, context="after companion publication"
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
                context=f"during ownership transfer pass {pass_index}",
            )
            _require_repository_checkpoint(
                repo_root=root,
                expected_head=h_head,
                verify_remote=True,
                p_outputs_present=True,
                context=f"during ownership transfer pass {pass_index}",
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
                context=f"MIB ownership transfer pass {pass_index}",
            )
        committed = True
        return dict(frozen), companion
    except BaseException as exc:
        rollback = mcalm.mcall.mcalk._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureLockedEvaluationInputBundleError):
            raise
        raise _error("E0-MIB lock bundle publication failed") from exc
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
    if h_head == BASE_P_MCALM_COMMIT or re.fullmatch(r"[0-9a-f]{40}", h_head) is None:
        raise _error("E0-MIB published H commit is absent")
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MIB")
        != BASE_P_MCALM_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MCALM_COMMIT, h_head)
        != expected_scope
    ):
        raise _error("E0-MIB published H topology drifted")
    components = [
        _artifact_record(
            Path(path),
            role="locked_evaluation_input_bundle_h_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    historical = _historical_h_mcalm_records(repo_root=repo_root)
    actual_r_state = _current_r_state(repo_root=repo_root)
    actual_namespace = _require_namespace(
        repo_root=repo_root,
        current_lock_state="present",
        r_state=actual_r_state,
    )
    prelock_namespace = _deep_copy(actual_namespace)
    prelock_namespace["current_lock_present_count"] = 0
    prelock_namespace["r_state"] = "absent"
    return {
        "repository": {
            "base_p_mcalm_commit": BASE_P_MCALM_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": expected_scope,
        },
        "h_patch": {
            "gate": "H-E0-MIB",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
        "base_authority": _base_p_mcalm_authority(repo_root=repo_root),
        "input_contract": _locked_input_contract(repo_root=repo_root),
        "r_contract": _locked_r_contract(),
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
            "panel_opened": False,
            "assignment_opened": False,
            "target_namespace_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
        },
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "coordination_namespace": prelock_namespace,
        "schema_preflight": preflight_closure_locked_evaluation_input_bundle_schema(
            repo_root=repo_root
        ),
    }


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MIB published lock schema validation failed") from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MIB published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIB published H binding is absent")
    state = _published_h_state(
        cast(str, repository["h_patch_head"]), repo_root=repo_root
    )
    expected = build_closure_locked_evaluation_input_bundle_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MIB published lock reconstruction drifted")


def _validate_unpublished_p_repository(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> str:
    if type(verify_remote) is not bool:
        raise _error("E0-MIB unpublished P remote policy must be exact boolean")
    expected_h_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or _git_head(repo_root) != h_head
        or mcal._single_parent(repo_root, h_head, context="H-E0-MIB")
        != BASE_P_MCALM_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MCALM_COMMIT, h_head)
        != expected_h_scope
    ):
        raise _error("E0-MIB unpublished P requires exact published H topology")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("E0-MIB unpublished P H refs drifted")
    observed = sorted(mcal._workspace_status_records(repo_root))
    untracked = sorted(("??", path.as_posix()) for path in CURRENT_LOCK_PATHS)
    staged = sorted(("A ", path.as_posix()) for path in CURRENT_LOCK_PATHS)
    if observed == untracked:
        return "untracked"
    if observed == staged:
        return "staged"
    raise _error("E0-MIB unpublished P workspace is not exact P2")


def validate_locked_evaluation_input_bundle_unpublished_lock_bundle(
    *, repo_root: Path | None = None, verify_remote: bool = True
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MIB unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="locked_evaluation_input_bundle_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MIB unpublished P companion drifted")
    namespace = _require_namespace(
        repo_root=root, current_lock_state="present", r_state="absent"
    )
    snapshot = _physical_snapshot(root)
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
        raise _error("E0-MIB unpublished P changed during validation")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during unpublished P validation"
    )
    if _require_namespace(
        repo_root=root, current_lock_state="present", r_state="absent"
    ) != namespace:
        raise _error("E0-MIB namespace changed during unpublished P validation")
    if _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    ) != stage_state:
        raise _error("E0-MIB unpublished P stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "companion_output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
        "coordination_forbidden_count": namespace["coordination_forbidden_count"],
        "coordination_present_count": 0,
        "r_state": "absent",
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
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, Any]:
    if type(verify_remote) is not bool:
        raise _error("E0-MIB effective remote policy must be exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = _git_head(repo_root)
    parent = mcal._single_parent(repo_root, head, context="P/R-E0-MIB")
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
            raise _error("E0-MIB published P scope drifted")
    else:
        r_head = head
        p_head = parent
        if (
            mcal._single_parent(repo_root, p_head, context="P-E0-MIB") != h_head
            or mcal._git_scope(repo_root, h_head, p_head) != p_scope
            or mcal._git_scope(repo_root, p_head, r_head) != r_scope
        ):
            raise _error("E0-MIB published R topology drifted")
    if cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main":
        raise _error("E0-MIB effective authority requires branch main")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MIB effective refs drifted")
    for path in CURRENT_LOCK_PATHS:
        try:
            physical, _ = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
            mode, _ = mcal._git_mode_oid(repo_root, p_head, path)
            git_bytes = mcal._git_blob_bytes(repo_root, p_head, path)
        except mcal.FinalCalibrationError as exc:
            raise _error(f"E0-MIB published P binding drifted: {path}") from exc
        if mode != "100644" or physical != git_bytes:
            raise _error(f"E0-MIB published P binding drifted: {path}")
    if r_head is not None:
        for path in R_TRACKED_OUTPUT_PATHS:
            try:
                tracked_payload, _ = mcal._read_regular_bytes_and_metadata(
                    path,
                    repo_root=repo_root,
                    expected_mode=0o644,
                    require_nlink_one=True,
                )
                mode, _ = mcal._git_mode_oid(repo_root, r_head, path)
                git_payload = mcal._git_blob_bytes(repo_root, r_head, path)
            except mcal.FinalCalibrationError as exc:
                raise _error(f"E0-MIB published R binding drifted: {path}") from exc
            if mode != "100644" or tracked_payload != git_payload:
                raise _error(f"E0-MIB published R binding drifted: {path}")
    r_state = _current_r_state(repo_root=repo_root)
    observed = sorted(mcal._workspace_status_records(repo_root))
    if r_head is not None:
        if r_state != "complete" or observed:
            raise _error("E0-MIB published R worktree drifted")
        r_stage_state = "published"
    elif r_state == "absent":
        if observed:
            raise _error("E0-MIB published P clean worktree drifted")
        r_stage_state = "absent"
    elif r_state == "physical_and_light":
        expected = sorted(("??", path.as_posix()) for path in R_LIGHT_OUTPUT_PATHS)
        if observed != expected:
            raise _error("E0-MIB pre-DVC R workspace drifted")
        r_stage_state = "physical_and_light_untracked"
    else:
        untracked = sorted(("??", path.as_posix()) for path in R_TRACKED_OUTPUT_PATHS)
        staged = sorted(("A ", path.as_posix()) for path in R_TRACKED_OUTPUT_PATHS)
        if observed == untracked:
            r_stage_state = "exact6_untracked"
        elif observed == staged:
            r_stage_state = "exact6_staged"
        else:
            raise _error("E0-MIB complete R workspace drifted")
    return {
        "h_patch_head": h_head,
        "p_patch_head": p_head,
        "r_patch_head": r_head,
        "remote_head": remote,
        "r_state": r_state,
        "r_stage_state": r_stage_state,
    }


def load_effective_closure_locked_evaluation_input_bundle_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="locked_evaluation_input_bundle_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MIB published companion drifted")
    publication = _validate_p_publication_state(
        lock, verify_remote=verify_remote, repo_root=root
    )
    binding = {
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "lock": lock_record,
        "companion_sha256": _sha256_bytes(companion_bytes),
        "input_contract_sha256": _sha256_bytes(
            _canonical_json_bytes(lock["input_contract"])
        ),
    }
    authority_binding_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    r_state = cast(str, publication["r_state"])
    namespace = _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    )
    r_semantics_before: dict[str, Any] | None = None
    r_sources_before: list[dict[str, Any]] | None = None
    r_materialization: dict[str, Any] | None = None
    if r_state != "absent":
        r_sources_before = _recapture_scientific_source_snapshots(repo_root=root)
        _validate_scientific_source_bindings(
            {"input_contract": lock["input_contract"]},
            r_sources_before,
            repo_root=root,
        )
        r_semantics_before = _validate_r_bundle_semantics(
            repo_root=root,
            pointers_required=r_state == "complete",
        )
        r_materialization = _build_expected_r_materialization(
            {
                "input_contract": lock["input_contract"],
                "authority_binding_sha256": authority_binding_sha256,
            },
            repo_root=root,
        )
        _require_expected_r_materialization(
            r_semantics_before, r_materialization
        )
    snapshot = _physical_snapshot(root)
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
        raise _error("E0-MIB P authority changed during effective loading")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during effective loading"
    )
    if _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    ) != namespace:
        raise _error("E0-MIB namespace changed during effective loading")
    if _validate_p_publication_state(
        lock, verify_remote=verify_remote, repo_root=root
    ) != publication:
        raise _error("E0-MIB publication changed during effective loading")
    consumed = r_state != "absent"
    r_semantics: dict[str, Any] | None = None
    if r_state != "absent":
        r_semantics = _validate_r_bundle_semantics(
            repo_root=root,
            pointers_required=r_state == "complete",
        )
        if (
            r_semantics_before is None
            or _canonical_json_bytes(r_semantics_before)
            != _canonical_json_bytes(r_semantics)
        ):
            raise _error("E0-MIB R semantics changed during effective loading")
        if r_materialization is None:
            raise _error("E0-MIB terminal R reconstruction is absent")
        _require_expected_r_materialization(r_semantics, r_materialization)
        r_sources_after = _recapture_scientific_source_snapshots(repo_root=root)
        if r_sources_before != r_sources_after:
            raise _error("E0-MIB scientific sources changed during effective loading")
        _validate_scientific_source_bindings(
            {"input_contract": lock["input_contract"]},
            r_sources_after,
            repo_root=root,
        )
        manifest = cast(Mapping[str, Any], r_semantics["manifest"])
        if manifest.get("authority_binding_sha256") != authority_binding_sha256:
            raise _error("E0-MIB R manifest authority binding drifted")
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": _file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="locked_evaluation_input_bundle_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": authority_binding_sha256,
        "input_contract": _deep_copy(lock["input_contract"]),
        "coordination_namespace": namespace,
        "r_physical_output_count": (
            len(R_PHYSICAL_OUTPUT_PATHS) if consumed else 0
        ),
        "r_tracked_output_count": (
            len(R_TRACKED_OUTPUT_PATHS) if r_state == "complete" else 0
        ),
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


def require_locked_evaluation_input_bundle_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_closure_locked_evaluation_input_bundle_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


def _validate_bundle_columns(columns: Sequence[str], *, context: str) -> None:
    if not columns or len(set(columns)) != len(columns):
        raise _error(f"E0-MIB {context} columns are empty or duplicated")
    for column in columns:
        normalized = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_")
        tokens = set(normalized.split("_"))
        if any(
            forbidden in tokens or forbidden in normalized
            for forbidden in FORBIDDEN_BUNDLE_COLUMN_TOKENS
        ):
            raise _error(f"E0-MIB {context} exposes a forbidden column: {column}")


def _read_parquet_contract(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment contract
        raise _error("E0-MIB PyArrow is unavailable for Parquet validation") from exc
    with _open_pinned_regular_file(path, repo_root=repo_root) as (
        descriptor,
        _parent,
        _name,
        metadata,
    ):
        size, sha256, md5 = _hash_pinned_descriptor(descriptor)
        try:
            with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
                parquet = pq.ParquetFile(stream)
                columns = list(parquet.schema_arrow.names)
                arrow_schema = [
                    {
                        "name": field.name,
                        "type": str(field.type),
                        "nullable": bool(field.nullable),
                    }
                    for field in parquet.schema_arrow
                ]
                row_count = int(parquet.metadata.num_rows)
                row_group_count = int(parquet.metadata.num_row_groups)
                rows = [cast(dict[str, Any], row) for row in parquet.read().to_pylist()]
        except Exception as exc:
            raise _error(f"E0-MIB Parquet is malformed: {path}") from exc
    _validate_bundle_columns(columns, context=path.name)
    expected_columns = R_PARQUET_COLUMN_CONTRACT.get(path.as_posix())
    if expected_columns is None or columns != list(expected_columns):
        raise _error(f"E0-MIB Parquet column contract drifted: {path}")
    if arrow_schema != _expected_arrow_schema(columns):
        raise _error(f"E0-MIB Parquet Arrow schema drifted: {path}")
    if row_count <= 0 or row_group_count <= 0:
        raise _error(f"E0-MIB Parquet is empty: {path}")
    return (
        {
            "path": path.as_posix(),
            "columns": columns,
            "arrow_schema": arrow_schema,
            "column_count": len(columns),
            "row_count": row_count,
            "row_group_count": row_group_count,
            "bytes": size,
            "sha256": sha256,
            "md5": md5,
            "device": int(metadata.st_dev),
            "inode": int(metadata.st_ino),
            "mode": stat.S_IMODE(metadata.st_mode),
            "nlink": int(metadata.st_nlink),
            "mtime_ns": int(metadata.st_mtime_ns),
            "ctime_ns": int(metadata.st_ctime_ns),
        },
        rows,
    )


def _validate_dvc_pointer_binding(
    pointer_path: Path,
    physical: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        import yaml

        payload, metadata = mcal._read_regular_bytes_and_metadata(
            pointer_path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        value = yaml.load(payload, Loader=mcal._UniqueKeyLoader)
    except Exception as exc:
        raise _error(f"E0-MIB DVC pointer is malformed: {pointer_path}") from exc
    if not isinstance(value, Mapping) or set(value) != {"outs"}:
        raise _error(f"E0-MIB DVC pointer dialect drifted: {pointer_path}")
    outputs = value.get("outs")
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise _error(f"E0-MIB DVC pointer output set drifted: {pointer_path}")
    output = outputs[0]
    if (
        not isinstance(output, Mapping)
        or set(output) != {"md5", "size", "hash", "path"}
        or output.get("md5") != physical["md5"]
        or output.get("size") != physical["bytes"]
        or output.get("hash") != "md5"
        or output.get("path") != Path(cast(str, physical["path"])).name
    ):
        raise _error(f"E0-MIB DVC pointer binding drifted: {pointer_path}")
    return {
        "role": "locked_evaluation_input_dvc_pointer",
        "path": pointer_path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "physical_path": cast(str, physical["path"]),
        "physical_md5": cast(str, physical["md5"]),
        "physical_bytes": cast(int, physical["bytes"]),
    }


def _validate_scientific_source_bindings(
    authority: Mapping[str, Any],
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> None:
    input_contract = authority.get("input_contract")
    if not isinstance(input_contract, Mapping):
        raise _error("E0-MIB effective input contract is absent")
    records = input_contract.get("source_records")
    if not isinstance(records, list) or len(records) != 4:
        raise _error("E0-MIB effective source record set drifted")
    by_path = {
        cast(str, record["path"]): record
        for record in records
        if isinstance(record, Mapping) and isinstance(record.get("path"), str)
    }
    observed = {
        cast(str, record["path"]): record for record in source_snapshots
    }
    assignment_record = by_path.get(ASSIGNMENT_PATH.as_posix())
    assignment_observed = observed.get(ASSIGNMENT_PATH.as_posix())
    pointer_path = Path(f"{PANEL_PATH.as_posix()}.dvc")
    pointer_record = by_path.get(pointer_path.as_posix())
    panel_observed = observed.get(PANEL_PATH.as_posix())
    if any(
        value is None
        for value in (
            assignment_record,
            assignment_observed,
            pointer_record,
            panel_observed,
        )
    ):
        raise _error("E0-MIB source binding paths drifted")
    assert assignment_record is not None
    assert assignment_observed is not None
    assert pointer_record is not None
    assert panel_observed is not None
    if {
        "bytes": assignment_observed["bytes"],
        "sha256": assignment_observed["sha256"],
    } != {
        "bytes": assignment_record["bytes"],
        "sha256": assignment_record["sha256"],
    }:
        raise _error("E0-MIB physical assignment differs from its Git authority")
    try:
        import yaml

        pointer_bytes, _ = mcal._read_regular_bytes_and_metadata(
            pointer_path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        pointer = yaml.load(pointer_bytes, Loader=mcal._UniqueKeyLoader)
    except Exception as exc:
        raise _error("E0-MIB panel DVC pointer is malformed") from exc
    if {
        "bytes": len(pointer_bytes),
        "sha256": _sha256_bytes(pointer_bytes),
    } != {
        "bytes": pointer_record["bytes"],
        "sha256": pointer_record["sha256"],
    }:
        raise _error("E0-MIB panel pointer differs from its Git authority")
    if not isinstance(pointer, Mapping) or set(pointer) != {"outs"}:
        raise _error("E0-MIB panel pointer dialect drifted")
    outs = pointer.get("outs")
    if not isinstance(outs, list) or len(outs) != 1:
        raise _error("E0-MIB panel pointer output set drifted")
    output = outs[0]
    if (
        not isinstance(output, Mapping)
        or set(output) != {"md5", "size", "hash", "path"}
        or output.get("md5") != panel_observed.get("md5")
        or output.get("size") != panel_observed.get("bytes")
        or output.get("hash") != "md5"
        or output.get("path") != PANEL_PATH.name
    ):
        raise _error("E0-MIB panel physical/pointer binding drifted")


def _validate_r_repository_state(
    *, repo_root: Path, require_staged: bool, verify_remote: bool
) -> str:
    if type(require_staged) is not bool or type(verify_remote) is not bool:
        raise _error("E0-MIB R validation policy must be exact boolean")
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MIB R validation refs drifted")
    observed = sorted(mcal._workspace_status_records(repo_root))
    if require_staged:
        expected = sorted(("A ", path.as_posix()) for path in R_TRACKED_OUTPUT_PATHS)
        if observed != expected:
            raise _error("E0-MIB R staged scope is not exact6")
        return "exact6_staged"
    expected = sorted(("??", path.as_posix()) for path in R_LIGHT_OUTPUT_PATHS)
    if observed != expected:
        raise _error("E0-MIB pre-DVC R scope is not exact light2")
    return "physical_and_light_untracked"


def _month_index(value: Any) -> int:
    if hasattr(value, "strftime"):
        text = cast(Any, value).strftime("%Y-%m")
    else:
        text = str(value)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}", text) is None:
        raise _error(f"E0-MIB year_month is malformed: {text!r}")
    year, month = (int(part) for part in text.split("-"))
    if year < 1900 or month < 1 or month > 12:
        raise _error(f"E0-MIB year_month is out of range: {text!r}")
    return year * 12 + month - 1


def _month_text(index: int) -> str:
    if type(index) is not int:
        raise _error("E0-MIB month index must be exact integer")
    year, zero_based_month = divmod(index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _calendar_features(month_index: int) -> dict[str, float]:
    month = month_index % 12
    annual = 2.0 * math.pi * month / 12.0
    semiannual = 2.0 * annual
    return {
        "season_sin_annual": math.sin(annual),
        "season_cos_annual": math.cos(annual),
        "season_sin_semiannual": math.sin(semiannual),
        "season_cos_semiannual": math.cos(semiannual),
    }


def _feature_value(value: Any, *, column: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _error(f"E0-MIB physical feature is boolean: {column}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(f"E0-MIB physical feature is non-numeric: {column}") from exc
    return number if math.isfinite(number) else None


def _origin_identifier(
    *, source_id: str, site_id: str, holdout_group_id: str, origin_month: str
) -> str:
    payload = "\x00".join((source_id, site_id, holdout_group_id, origin_month))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_locked_evaluation_input_bundle_records(
    assignment_rows: Sequence[Mapping[str, Any]],
    panel_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build deterministic input-only records from two explicit projections."""

    assignments: list[dict[str, str]] = []
    assignment_keys: set[tuple[str, str]] = set()
    for raw in assignment_rows:
        if not isinstance(raw, Mapping) or set(raw) != set(ASSIGNMENT_COLUMNS):
            raise _error("E0-MIB assignment projection dialect drifted")
        role = str(raw["assignment_role"])
        source_id = str(raw["source_id"])
        if role != "internal_holdout" or source_id != "wqp":
            continue
        row = {
            "source_id": source_id,
            "site_id": str(raw["site_id"]),
            "holdout_group_id": str(raw["holdout_group_id"]),
            "assignment_role": role,
        }
        if any(not value for value in row.values()):
            raise _error("E0-MIB assignment contains an empty identifier")
        key = (row["source_id"], row["site_id"])
        if key in assignment_keys:
            raise _error("E0-MIB holdout assignment is not unique by source/site")
        assignment_keys.add(key)
        assignments.append(row)
    assignments.sort(
        key=lambda row: (
            row["source_id"], row["site_id"], row["holdout_group_id"]
        )
    )
    if len(assignments) != HOLDOUT_LOCATION_COUNT:
        raise _error(
            "E0-MIB internal holdout location count drifted: "
            f"{len(assignments)}"
        )

    panel_by_key: dict[tuple[str, str, int], dict[str, float | None]] = {}
    upper_month: int | None = None
    for raw in panel_rows:
        if not isinstance(raw, Mapping) or set(raw) != set(PANEL_PROJECTION):
            raise _error("E0-MIB panel projection dialect drifted")
        source_id = str(raw["source_id"])
        site_id = str(raw["site_id"])
        if (source_id, site_id) not in assignment_keys:
            continue
        month = _month_index(raw["year_month"])
        key = (source_id, site_id, month)
        if key in panel_by_key:
            raise _error("E0-MIB panel projection has duplicate source/site/month")
        features = {
            column: _feature_value(raw[column], column=column)
            for column in PHYSICAL_FEATURE_COLUMNS
        }
        panel_by_key[key] = features
        upper_month = month if upper_month is None else max(upper_month, month)
    start_month = _month_index(LOCKED_EVALUATION_START)
    if upper_month is None or upper_month < start_month:
        raise _error("E0-MIB panel projection has no locked-evaluation calendar")

    intents: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    origins: list[dict[str, Any]] = []
    sequences: list[dict[str, Any]] = []
    for assignment in assignments:
        source_id = assignment["source_id"]
        site_id = assignment["site_id"]
        group_id = assignment["holdout_group_id"]
        for origin_month_index in range(start_month, upper_month + 1):
            origin_month = _month_text(origin_month_index)
            origin_id = _origin_identifier(
                source_id=source_id,
                site_id=site_id,
                holdout_group_id=group_id,
                origin_month=origin_month,
            )
            month_indices = list(
                range(origin_month_index - HISTORY_LENGTH + 1, origin_month_index + 1)
            )
            present = [
                (source_id, site_id, month) in panel_by_key for month in month_indices
            ]
            present_count = sum(present)
            status = "eligible" if present_count == HISTORY_LENGTH else "ineligible"
            reason = (
                "complete_input_history"
                if status == "eligible"
                else "insufficient_input_history"
            )
            common: dict[str, Any] = {
                "origin_id": origin_id,
                "source_id": source_id,
                "site_id": site_id,
                "holdout_group_id": group_id,
                "assignment_role": assignment["assignment_role"],
                "origin_year_month": origin_month,
                "base_input_status": status,
                "base_input_reason": reason,
            }
            intents.append(
                {
                    **common,
                    "history_start_year_month": _month_text(month_indices[0]),
                    "history_end_year_month": _month_text(month_indices[-1]),
                    "history_length_months": HISTORY_LENGTH,
                    "history_row_count": present_count,
                    "missing_history_row_count": HISTORY_LENGTH - present_count,
                }
            )
            current_features = panel_by_key.get(
                (source_id, site_id, origin_month_index)
            )
            origins.append(
                {
                    **common,
                    "row_present": current_features is not None,
                    **{
                        column: (
                            None if current_features is None else current_features[column]
                        )
                        for column in PHYSICAL_FEATURE_COLUMNS
                    },
                    **_calendar_features(origin_month_index),
                }
            )
            sequence: dict[str, Any] = {
                **common,
                "sequence_length": HISTORY_LENGTH,
                "sequence_row_present": present,
            }
            for column in (*PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS):
                sequence[f"sequence_{column}"] = []
            for offset, month_index in enumerate(month_indices):
                row_features = panel_by_key.get((source_id, site_id, month_index))
                calendar = _calendar_features(month_index)
                history.append(
                    {
                        **common,
                        "history_year_month": _month_text(month_index),
                        "history_offset_months": offset - HISTORY_LENGTH + 1,
                        "row_present": row_features is not None,
                        **{
                            column: (
                                None if row_features is None else row_features[column]
                            )
                            for column in PHYSICAL_FEATURE_COLUMNS
                        },
                        **calendar,
                    }
                )
                for column in PHYSICAL_FEATURE_COLUMNS:
                    cast(list[Any], sequence[f"sequence_{column}"]).append(
                        None if row_features is None else row_features[column]
                    )
                for column in DERIVED_CALENDAR_COLUMNS:
                    cast(list[Any], sequence[f"sequence_{column}"]).append(
                        calendar[column]
                    )
            sequences.append(sequence)
    origin_count = len(intents)
    eligible_count = sum(
        row["base_input_status"] == "eligible" for row in intents
    )
    if not (
        len(origins) == origin_count
        and len(sequences) == origin_count
        and len(history) == origin_count * HISTORY_LENGTH
    ):
        raise _error("E0-MIB constructed input table cardinality drifted")
    return {
        "intent_origins": intents,
        "input_history": history,
        "origin_features": origins,
        "sequence_features": sequences,
        "summary": {
            "holdout_location_count": len(assignments),
            "origin_count": origin_count,
            "eligible_origin_count": eligible_count,
            "ineligible_origin_count": origin_count - eligible_count,
            "history_row_count": len(history),
            "origin_start": LOCKED_EVALUATION_START,
            "origin_end": _month_text(upper_month),
        },
    }


def _validate_r_bundle_semantics(
    *, repo_root: Path, pointers_required: bool
) -> dict[str, Any]:
    physical_with_rows = [
        _read_parquet_contract(path, repo_root=repo_root)
        for path in R_PHYSICAL_OUTPUT_PATHS
    ]
    physical = [record for record, _rows in physical_with_rows]
    table_rows = [rows for _record, rows in physical_with_rows]
    public_physical = [
        {
            key: record[key]
            for key in (
                "path", "columns", "arrow_schema", "column_count", "row_count",
                "bytes", "sha256", "md5",
            )
        }
        for record in physical
    ]
    summary, summary_bytes, summary_metadata = _parse_canonical_json(
        R_SUMMARY_PATH, repo_root=repo_root
    )
    manifest, manifest_bytes, manifest_metadata = _parse_canonical_json(
        R_MANIFEST_PATH, repo_root=repo_root
    )
    expected_summary_keys = {
        "schema_version", "gate", "status", "input_only", "origin_start",
        "origin_end", "holdout_location_count", "origin_count",
        "eligible_origin_count", "ineligible_origin_count", "history_row_count",
        "target_months_materialized", "target_availability_inspected",
        "target_paths_opened", "outcome_paths_opened",
    }
    if (
        set(summary) != expected_summary_keys
        or summary.get("schema_version") != "closure_locked_evaluation_input_summary_v1"
        or summary.get("gate") != "R-E0-MI"
        or summary.get("status") != "completed_unpublished"
        or summary.get("input_only") is not True
        or summary.get("origin_start") != LOCKED_EVALUATION_START
        or summary.get("holdout_location_count") != HOLDOUT_LOCATION_COUNT
        or any(
            summary.get(key) is not False
            for key in (
                "target_months_materialized", "target_availability_inspected",
                "target_paths_opened", "outcome_paths_opened",
            )
        )
    ):
        raise _error("E0-MIB R summary dialect drifted")
    counts = (
        summary.get("origin_count"), summary.get("eligible_origin_count"),
        summary.get("ineligible_origin_count"), summary.get("history_row_count"),
    )
    if (
        any(type(value) is not int for value in counts)
        or cast(int, counts[0]) <= 0
        or cast(int, counts[1]) + cast(int, counts[2]) != counts[0]
        or cast(int, counts[3]) != cast(int, counts[0]) * HISTORY_LENGTH
        or not isinstance(summary.get("origin_end"), str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}", cast(str, summary["origin_end"])) is None
    ):
        raise _error("E0-MIB R summary cardinality drifted")
    expected_rows = (
        cast(int, summary["history_row_count"]),
        cast(int, summary["origin_count"]),
        cast(int, summary["origin_count"]),
        cast(int, summary["origin_count"]),
    )
    if tuple(record["row_count"] for record in physical) != expected_rows:
        raise _error("E0-MIB R Parquet cardinality drifted")
    history_rows, intent_rows, origin_rows, sequence_rows = table_rows
    intent_ids = [row.get("origin_id") for row in intent_rows]
    if (
        len(set(intent_ids)) != len(intent_ids)
        or intent_rows != sorted(
            intent_rows,
            key=lambda row: (
                row["source_id"], row["site_id"], row["origin_year_month"]
            ),
        )
        or any(
            not isinstance(origin_id, str)
            or re.fullmatch(r"[0-9a-f]{64}", origin_id) is None
            for origin_id in intent_ids
        )
    ):
        raise _error("E0-MIB intent-origin keys/order drifted")
    intent_by_id = {cast(str, row["origin_id"]): row for row in intent_rows}
    expected_origin_end = cast(str, summary["origin_end"])
    expected_month_count = (
        _month_index(expected_origin_end) - _month_index(LOCKED_EVALUATION_START) + 1
    )
    site_keys = {
        (cast(str, row["source_id"]), cast(str, row["site_id"]))
        for row in intent_rows
    }
    if (
        expected_month_count <= 0
        or len(site_keys) != HOLDOUT_LOCATION_COUNT
        or len(intent_rows) != HOLDOUT_LOCATION_COUNT * expected_month_count
        or any(
            row.get("source_id") != "wqp"
            or row.get("assignment_role") != "internal_holdout"
            or not isinstance(row.get("origin_year_month"), str)
            or cast(str, row["origin_year_month"]) > expected_origin_end
            for row in intent_rows
        )
        or sum(row["base_input_status"] == "eligible" for row in intent_rows)
        != summary["eligible_origin_count"]
    ):
        raise _error("E0-MIB intent universe/summary drifted")
    if (
        [row.get("origin_id") for row in origin_rows] != intent_ids
        or [row.get("origin_id") for row in sequence_rows] != intent_ids
    ):
        raise _error("E0-MIB origin/sequence foreign-key order drifted")
    history_by_id: dict[str, list[dict[str, Any]]] = {
        cast(str, origin_id): [] for origin_id in intent_ids
    }
    previous_history_key: tuple[str, str, str, int] | None = None
    for row in history_rows:
        origin_id = row.get("origin_id")
        if not isinstance(origin_id, str) or origin_id not in history_by_id:
            raise _error("E0-MIB history foreign key drifted")
        key = (
            cast(str, row["source_id"]),
            cast(str, row["site_id"]),
            cast(str, row["origin_year_month"]),
            cast(int, row["history_offset_months"]),
        )
        if previous_history_key is not None and key <= previous_history_key:
            raise _error("E0-MIB history order/uniqueness drifted")
        previous_history_key = key
        history_by_id[origin_id].append(row)
    common_keys = set(ORIGIN_COMMON_COLUMNS)
    for intent, origin, sequence in zip(
        intent_rows, origin_rows, sequence_rows, strict=True
    ):
        origin_id = cast(str, intent["origin_id"])
        histories = history_by_id[origin_id]
        expected_common = {key: intent[key] for key in common_keys}
        expected_origin_id = _origin_identifier(
            source_id=cast(str, intent["source_id"]),
            site_id=cast(str, intent["site_id"]),
            holdout_group_id=cast(str, intent["holdout_group_id"]),
            origin_month=cast(str, intent["origin_year_month"]),
        )
        if (
            origin_id != expected_origin_id
            or
            len(histories) != HISTORY_LENGTH
            or [row["history_offset_months"] for row in histories]
            != list(range(-HISTORY_LENGTH + 1, 1))
            or any({key: row[key] for key in common_keys} != expected_common for row in histories)
            or {key: origin[key] for key in common_keys} != expected_common
            or {key: sequence[key] for key in common_keys} != expected_common
            or intent["history_length_months"] != HISTORY_LENGTH
            or intent["history_row_count"]
            != sum(bool(row["row_present"]) for row in histories)
            or intent["missing_history_row_count"]
            != HISTORY_LENGTH - intent["history_row_count"]
            or sequence["sequence_length"] != HISTORY_LENGTH
            or sequence["sequence_row_present"]
            != [row["row_present"] for row in histories]
            or any(
                _month_index(row["history_year_month"])
                != _month_index(cast(str, intent["origin_year_month"]))
                + cast(int, row["history_offset_months"])
                for row in histories
            )
        ):
            raise _error("E0-MIB cross-table intent/history contract drifted")
        expected_status = (
            "eligible"
            if intent["history_row_count"] == HISTORY_LENGTH
            else "ineligible"
        )
        expected_reason = (
            "complete_input_history"
            if expected_status == "eligible"
            else "insufficient_input_history"
        )
        if (
            intent["base_input_status"] != expected_status
            or intent["base_input_reason"] != expected_reason
            or intent["origin_year_month"] < LOCKED_EVALUATION_START
            or intent["history_start_year_month"] != histories[0]["history_year_month"]
            or intent["history_end_year_month"] != histories[-1]["history_year_month"]
        ):
            raise _error("E0-MIB intent eligibility/calendar drifted")
        origin_current = histories[-1]
        if origin["row_present"] != origin_current["row_present"]:
            raise _error("E0-MIB origin current-row flag drifted")
        for column in (*PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS):
            if origin[column] != origin_current[column]:
                raise _error("E0-MIB origin feature/history binding drifted")
            if sequence[f"sequence_{column}"] != [
                row[column] for row in histories
            ]:
                raise _error("E0-MIB sequence/history binding drifted")
    expected_manifest_keys = {
        "schema_version", "gate", "status", "input_only",
        "authority_binding_sha256", "input_contract", "physical_outputs",
        "source_inputs", "summary", "manifest_written_last", "target_months_materialized",
        "target_availability_inspected", "target_paths_opened",
        "outcome_paths_opened", "future_outcomes_accessed",
        "evaluation_authorized", "e0_m_authorized", "e0_u_authorized",
    }
    if (
        set(manifest) != expected_manifest_keys
        or manifest.get("schema_version") != "closure_locked_evaluation_input_manifest_v1"
        or manifest.get("gate") != "R-E0-MI"
        or manifest.get("status") != "completed_unpublished"
        or manifest.get("input_only") is not True
        or manifest.get("input_contract") != _locked_input_contract(repo_root=repo_root)
        or manifest.get("physical_outputs") != public_physical
        or manifest.get("source_inputs") != [
            _public_source_snapshot(record)
            for record in _recapture_scientific_source_snapshots(repo_root=repo_root)
        ]
        or manifest.get("summary") != {
            "path": R_SUMMARY_PATH.as_posix(),
            "bytes": len(summary_bytes),
            "sha256": _sha256_bytes(summary_bytes),
        }
        or manifest.get("manifest_written_last") is not True
        or any(
            manifest.get(key) is not False
            for key in (
                "target_months_materialized", "target_availability_inspected",
                "target_paths_opened", "outcome_paths_opened",
                "future_outcomes_accessed", "evaluation_authorized",
                "e0_m_authorized", "e0_u_authorized",
            )
        )
    ):
        raise _error("E0-MIB R manifest dialect drifted")
    pointer_records: list[dict[str, Any]] = []
    if pointers_required:
        pointer_records = [
            _validate_dvc_pointer_binding(pointer, record, repo_root=repo_root)
            for pointer, record in zip(R_POINTER_PATHS, physical, strict=True)
        ]
    if int(manifest_metadata.st_mtime_ns) <= max(
        int(summary_metadata.st_mtime_ns),
        *(int(cast(int, record["mtime_ns"])) for record in physical),
    ):
        raise _error("E0-MIB R manifest was not written last")
    digest_records = [
        {"path": record["path"], "bytes": record["bytes"], "sha256": record["sha256"]}
        for record in physical
    ] + [
        {"path": R_SUMMARY_PATH.as_posix(), "bytes": len(summary_bytes), "sha256": _sha256_bytes(summary_bytes)},
        {"path": R_MANIFEST_PATH.as_posix(), "bytes": len(manifest_bytes), "sha256": _sha256_bytes(manifest_bytes)},
    ]
    return {
        "summary": summary,
        "manifest": manifest,
        "physical_outputs": public_physical,
        "pointer_outputs": pointer_records,
        "r_outputs_sha256": mcal._digest_records(digest_records),
    }


def validate_locked_evaluation_input_bundle(
    *, repo_root: Path | None = None, require_staged: bool = False,
    verify_remote: bool = True,
) -> dict[str, Any]:
    root = _root(repo_root)
    authority = require_locked_evaluation_input_bundle_authority(
        verify_remote=verify_remote, repo_root=root
    )
    if authority.get("input_bundle_run_consumed") is not True:
        raise _error("E0-MIB R validation requires consumed one-shot state")
    stage_state = _validate_r_repository_state(
        repo_root=root, require_staged=require_staged, verify_remote=verify_remote
    )
    r_state = "complete" if require_staged else "physical_and_light"
    namespace = _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    )
    materialization = _build_expected_r_materialization(
        authority, repo_root=root
    )
    source_before = cast(
        list[dict[str, Any]], materialization["source_snapshots"]
    )
    before = _validate_r_bundle_semantics(
        repo_root=root, pointers_required=require_staged
    )
    _require_expected_r_materialization(before, materialization)
    after = _validate_r_bundle_semantics(
        repo_root=root, pointers_required=require_staged
    )
    _require_expected_r_materialization(after, materialization)
    if cast(Mapping[str, Any], before["manifest"]).get(
        "authority_binding_sha256"
    ) != authority.get("authority_binding_sha256"):
        raise _error("E0-MIB R authority binding drifted")
    if _canonical_json_bytes(before) != _canonical_json_bytes(after):
        raise _error("E0-MIB R semantics changed during validation")
    source_after = _recapture_scientific_source_snapshots(repo_root=root)
    if source_after != source_before:
        raise _error("E0-MIB scientific sources changed during R validation")
    _validate_scientific_source_bindings(
        authority, source_after, repo_root=root
    )
    if _require_namespace(
        repo_root=root, current_lock_state="present", r_state=r_state
    ) != namespace:
        raise _error("E0-MIB R namespace changed during validation")
    if _validate_r_repository_state(
        repo_root=root, require_staged=require_staged, verify_remote=verify_remote
    ) != stage_state:
        raise _error("E0-MIB R stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "input_bundle_validated",
        "r_stage_state": stage_state,
        "physical_output_count": 4,
        "tracked_output_count": 6,
        "pointer_count": 4,
        "summary_count": 1,
        "manifest_count": 1,
        "manifest_written_last": True,
        "input_only": True,
        "r_outputs_sha256": before["r_outputs_sha256"],
        "authority_binding_sha256": authority["authority_binding_sha256"],
        "target_paths_opened": False,
        "target_availability_inspected": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "writes_performed": False,
    }


def _arrow_type_name(column: str) -> str:
    common_strings = set(ORIGIN_COMMON_COLUMNS)
    string_columns = common_strings | {
        "history_start_year_month", "history_end_year_month", "history_year_month",
    }
    integer_columns = {
        "history_length_months", "history_row_count", "missing_history_row_count",
        "history_offset_months", "sequence_length",
    }
    if column in string_columns:
        return "string"
    if column in integer_columns:
        return "int64"
    if column == "row_present":
        return "bool"
    if column == "sequence_row_present":
        return "list<element: bool>"
    if column.startswith("sequence_"):
        return "list<element: double>"
    if column in (*PHYSICAL_FEATURE_COLUMNS, *DERIVED_CALENDAR_COLUMNS):
        return "double"
    raise _error(f"E0-MIB Arrow type contract is absent: {column}")


def _expected_arrow_schema(columns: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {"name": column, "type": _arrow_type_name(column), "nullable": True}
        for column in columns
    ]


def _table_from_records(records: Sequence[Mapping[str, Any]]) -> Any:
    try:
        import pyarrow as pa
    except ImportError as exc:  # pragma: no cover - environment contract
        raise _error("E0-MIB PyArrow is unavailable for bundle construction") from exc
    if not records:
        raise _error("E0-MIB refuses to serialize an empty table")
    columns = list(records[0])
    if any(list(record) != columns for record in records):
        raise _error("E0-MIB record column order drifted")
    _validate_bundle_columns(columns, context="constructed table")
    fields: list[Any] = []
    for column in columns:
        type_name = _arrow_type_name(column)
        if type_name == "string":
            data_type = pa.string()
        elif type_name == "int64":
            data_type = pa.int64()
        elif type_name == "bool":
            data_type = pa.bool_()
        elif type_name == "list<element: bool>":
            data_type = pa.list_(pa.bool_())
        elif type_name == "list<element: double>":
            data_type = pa.list_(pa.float64())
        elif type_name == "double":
            data_type = pa.float64()
        else:
            raise _error(f"E0-MIB Arrow type contract is absent: {column}")
        fields.append(pa.field(column, data_type, nullable=True))
    schema = pa.schema(fields)
    return pa.Table.from_pylist([dict(record) for record in records], schema=schema)


def _parquet_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment contract
        raise _error("E0-MIB PyArrow is unavailable for bundle construction") from exc
    buffer = io.BytesIO()
    pq.write_table(
        _table_from_records(records),
        buffer,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    return buffer.getvalue()


def _public_parquet_record(path: Path, payload: bytes, row_count: int) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(io.BytesIO(payload))
        columns = list(parquet.schema_arrow.names)
        arrow_schema = [
            {
                "name": field.name,
                "type": str(field.type),
                "nullable": bool(field.nullable),
            }
            for field in parquet.schema_arrow
        ]
    except Exception as exc:
        raise _error(f"E0-MIB constructed Parquet is malformed: {path}") from exc
    _validate_bundle_columns(columns, context=path.name)
    if parquet.metadata.num_rows != row_count:
        raise _error(f"E0-MIB constructed Parquet row count drifted: {path}")
    return {
        "path": path.as_posix(),
        "columns": columns,
        "arrow_schema": arrow_schema,
        "column_count": len(columns),
        "row_count": row_count,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


def _load_input_projections(*, repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment contract
        raise _error("E0-MIB PyArrow input readers are unavailable") from exc
    source_snapshots: list[dict[str, Any]] = []
    with _open_pinned_regular_file(ASSIGNMENT_PATH, repo_root=repo_root) as (
        descriptor, _parent, _name, metadata,
    ):
        size, sha256, source_md5 = _hash_pinned_descriptor(descriptor)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            assignment_table = pacsv.read_csv(
                stream,
                convert_options=pacsv.ConvertOptions(
                    include_columns=list(ASSIGNMENT_COLUMNS)
                ),
            )
        if list(assignment_table.column_names) != list(ASSIGNMENT_COLUMNS):
            raise _error("E0-MIB assignment scanner projection drifted")
        assignment_rows = assignment_table.to_pylist()
        source_snapshots.append(
            _source_snapshot(
                ASSIGNMENT_PATH, role="locked_holdout_assignment",
                payload_size=size, sha256=sha256, metadata=metadata,
                md5=source_md5,
            )
        )
    with _open_pinned_regular_file(PANEL_PATH, repo_root=repo_root) as (
        descriptor, _parent, _name, metadata,
    ):
        size, sha256, source_md5 = _hash_pinned_descriptor(descriptor)
        holdout_site_ids = sorted(
            {
                str(row["site_id"])
                for row in assignment_rows
                if str(row["source_id"]) == "wqp"
                and str(row["assignment_role"]) == "internal_holdout"
            }
        )
        if len(holdout_site_ids) != HOLDOUT_LOCATION_COUNT:
            raise _error("E0-MIB holdout projection is not exact88")
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            panel_table = pq.read_table(
                stream,
                columns=list(PANEL_PROJECTION),
                filters=[
                    ("source_id", "=", "wqp"),
                    ("site_id", "in", holdout_site_ids),
                ],
            )
        if list(panel_table.column_names) != list(PANEL_PROJECTION):
            raise _error("E0-MIB panel scanner projection drifted")
        panel_rows = panel_table.to_pylist()
        source_snapshots.append(
            _source_snapshot(
                PANEL_PATH, role="locked_panel_physical_input",
                payload_size=size, sha256=sha256, metadata=metadata,
                md5=source_md5,
            )
        )
    return (
        [cast(dict[str, Any], row) for row in assignment_rows],
        [cast(dict[str, Any], row) for row in panel_rows],
        source_snapshots,
    )


def _recapture_scientific_source_snapshots(
    *, repo_root: Path
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path, role in (
        (ASSIGNMENT_PATH, "locked_holdout_assignment"),
        (PANEL_PATH, "locked_panel_physical_input"),
    ):
        with _open_pinned_regular_file(path, repo_root=repo_root) as (
            descriptor, _parent, _name, metadata,
        ):
            size, sha256, source_md5 = _hash_pinned_descriptor(descriptor)
            records.append(
                _source_snapshot(
                    path, role=role, payload_size=size, sha256=sha256,
                    metadata=metadata, md5=source_md5,
                )
            )
    return records


def _build_expected_r_materialization(
    authority: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    """Rebuild the complete R bundle from the two permitted projections."""

    assignment_rows, panel_rows, source_snapshots = _load_input_projections(
        repo_root=repo_root
    )
    _validate_scientific_source_bindings(
        authority, source_snapshots, repo_root=repo_root
    )
    built = build_locked_evaluation_input_bundle_records(
        assignment_rows, panel_rows
    )
    if _recapture_scientific_source_snapshots(repo_root=repo_root) != source_snapshots:
        raise _error("E0-MIB scientific inputs changed during reconstruction")
    table_keys = (
        "input_history",
        "intent_origins",
        "origin_features",
        "sequence_features",
    )
    payloads = tuple(
        _parquet_bytes(cast(Sequence[Mapping[str, Any]], built[key]))
        for key in table_keys
    )
    public_records = [
        _public_parquet_record(
            path,
            payload,
            len(cast(Sequence[Any], built[key])),
        )
        for path, payload, key in zip(
            R_PHYSICAL_OUTPUT_PATHS, payloads, table_keys, strict=True
        )
    ]
    summary = {
        "schema_version": "closure_locked_evaluation_input_summary_v1",
        "gate": "R-E0-MI",
        "status": "completed_unpublished",
        "input_only": True,
        **cast(Mapping[str, Any], built["summary"]),
        "target_months_materialized": False,
        "target_availability_inspected": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    }
    summary_bytes = _canonical_json_bytes(summary)
    manifest = {
        "schema_version": "closure_locked_evaluation_input_manifest_v1",
        "gate": "R-E0-MI",
        "status": "completed_unpublished",
        "input_only": True,
        "authority_binding_sha256": authority["authority_binding_sha256"],
        "input_contract": _locked_input_contract(repo_root=repo_root),
        "physical_outputs": public_records,
        "source_inputs": [
            _public_source_snapshot(record) for record in source_snapshots
        ],
        "summary": {
            "path": R_SUMMARY_PATH.as_posix(),
            "bytes": len(summary_bytes),
            "sha256": _sha256_bytes(summary_bytes),
        },
        "manifest_written_last": True,
        "target_months_materialized": False,
        "target_availability_inspected": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    return {
        "built": built,
        "source_snapshots": source_snapshots,
        "payloads": payloads,
        "public_records": public_records,
        "summary": summary,
        "summary_bytes": summary_bytes,
        "manifest": manifest,
        "manifest_bytes": manifest_bytes,
    }


def _require_expected_r_materialization(
    semantic: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    """Bind parsed R bytes and rows to an independent source reconstruction."""

    if (
        semantic.get("physical_outputs") != expected.get("public_records")
        or semantic.get("summary") != expected.get("summary")
        or semantic.get("manifest") != expected.get("manifest")
    ):
        raise _error("E0-MIB R bundle differs from its source reconstruction")


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


def _require_execution_authority_checkpoint(
    expected: Mapping[str, Any],
    p_snapshot: Sequence[Mapping[str, Any]],
    *,
    owned_run_guard: Any,
    repo_root: Path,
) -> dict[str, Any]:
    """Recapture P bytes, refs, topology, and namespace while R owns its guard."""

    lock, _lock_bytes, _lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=repo_root
    )
    _validate_published_lock_payload(lock, repo_root=repo_root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="locked_evaluation_input_bundle_lock",
        repo_root=repo_root,
    )
    companion, companion_bytes, _companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=repo_root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MIB execution companion drifted")
    publication = _validate_p_publication_state(
        lock, verify_remote=True, repo_root=repo_root
    )
    r_state = cast(str, publication["r_state"])
    _require_namespace(
        repo_root=repo_root,
        current_lock_state="present",
        r_state=r_state,
        owned_run_guard=owned_run_guard,
    )
    binding = {
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "lock": lock_record,
        "companion_sha256": _sha256_bytes(companion_bytes),
        "input_contract_sha256": _sha256_bytes(
            _canonical_json_bytes(lock["input_contract"])
        ),
    }
    if (
        _canonical_json_bytes(_p_pair_snapshot(repo_root))
        != _canonical_json_bytes(list(p_snapshot))
        or _sha256_bytes(_canonical_json_bytes(binding))
        != expected.get("authority_binding_sha256")
        or publication.get("h_patch_head") != expected.get("h_patch_head")
        or publication.get("p_patch_head") != expected.get("p_patch_head")
        or publication.get("r_patch_head") is not None
        or lock.get("input_contract") != expected.get("input_contract")
    ):
        raise _error("E0-MIB execution authority changed under the run guard")
    return publication


def _rollback_owned_outputs(outputs: Sequence[Any]) -> BaseException | None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            mcalm.mcall.mcalk.mcalj._rollback_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if not errors:
        return None
    error = _error("E0-MIB input-bundle rollback was incomplete")
    for nested in errors:
        error.add_note(str(nested))
    return error


def execute_locked_evaluation_input_bundle(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Execute the one-shot input-only producer and publish manifest last."""

    root = _root(repo_root)
    authority = require_locked_evaluation_input_bundle_authority(
        verify_remote=True, repo_root=root
    )
    if (
        authority.get("input_bundle_execution_authorized") is not True
        or authority.get("input_bundle_run_consumed") is not False
        or len(sys.argv) != 2
        or Path(sys.argv[0]).resolve() != (root / CORE_PATH).resolve()
        or sys.argv[1] != "--execute-input-bundle"
    ):
        raise _error("E0-MIB input-bundle command/one-shot authority drifted")
    _require_namespace(repo_root=root, current_lock_state="present", r_state="absent")
    physical_snapshot = _physical_snapshot(root)
    p_snapshot = _p_pair_snapshot(root)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            INPUT_RUN_GUARD_PATH,
            b"R-E0-MI locked evaluation input bundle\n",
            repo_root=root,
        )
        _require_namespace(
            repo_root=root, current_lock_state="present", r_state="absent",
            owned_run_guard=guard,
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=root, context="before scientific input scan"
        )
        _require_execution_authority_checkpoint(
            authority,
            p_snapshot,
            owned_run_guard=guard,
            repo_root=root,
        )
        materialization = _build_expected_r_materialization(
            authority, repo_root=root
        )
        source_snapshots = cast(
            list[dict[str, Any]], materialization["source_snapshots"]
        )
        payloads = cast(tuple[bytes, ...], materialization["payloads"])
        summary_bytes = cast(bytes, materialization["summary_bytes"])
        manifest_bytes = cast(bytes, materialization["manifest_bytes"])
        for path, payload in zip(R_PHYSICAL_OUTPUT_PATHS, payloads, strict=True):
            published.append(
                mcalm.mcall.mcalk._publish_bytes_no_clobber(
                    path, payload, repo_root=root
                )
            )
        published.append(
            mcalm.mcall.mcalk._publish_bytes_no_clobber(
                R_SUMMARY_PATH, summary_bytes, repo_root=root
            )
        )
        published.append(
            mcalm.mcall.mcalk._publish_bytes_no_clobber(
                R_MANIFEST_PATH, manifest_bytes, repo_root=root
            )
        )
        _require_namespace(
            repo_root=root, current_lock_state="present", r_state="physical_and_light",
            owned_run_guard=guard,
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=root, context="after input-bundle publication"
        )
        if _recapture_scientific_source_snapshots(repo_root=root) != source_snapshots:
            raise _error("E0-MIB scientific inputs changed during publication")
        if _current_r_state(repo_root=root) != "physical_and_light":
            raise _error("E0-MIB one-shot was not consumed after publication")
        guarded_semantic = _validate_r_bundle_semantics(
            repo_root=root, pointers_required=False
        )
        _require_expected_r_materialization(guarded_semantic, materialization)
        member_payloads = (*payloads, summary_bytes, manifest_bytes)
        for output, expected in zip(published, member_payloads, strict=True):
            mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="R active-guard ownership validation",
            )
        mcalm.mcall.mcalk.mcalj.mcali._require_owned_identity_set(
            published,
            context="MIB R active-guard ownership validation",
        )
        _require_execution_authority_checkpoint(
            authority,
            p_snapshot,
            owned_run_guard=guard,
            repo_root=root,
        )
        mt._release_publication_guard(guard)
        guard = None
        _require_namespace(
            repo_root=root, current_lock_state="present", r_state="physical_and_light"
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=root, context="after run guard release"
        )
        post_release_authority = require_locked_evaluation_input_bundle_authority(
            verify_remote=True, repo_root=root
        )
        if (
            post_release_authority.get("input_bundle_run_consumed") is not True
            or post_release_authority.get("authority_binding_sha256")
            != authority.get("authority_binding_sha256")
            or post_release_authority.get("r_outputs_sha256")
            != guarded_semantic.get("r_outputs_sha256")
        ):
            raise _error("E0-MIB effective authority drifted after guard release")
        semantic = _validate_r_bundle_semantics(
            repo_root=root, pointers_required=False
        )
        _require_expected_r_materialization(semantic, materialization)
        for pass_index in (1, 2):
            _require_namespace(
                repo_root=root,
                current_lock_state="present",
                r_state="physical_and_light",
            )
            _require_physical_snapshot(
                physical_snapshot,
                repo_root=root,
                context=f"during R ownership transfer pass {pass_index}",
            )
            if _recapture_scientific_source_snapshots(repo_root=root) != source_snapshots:
                raise _error("E0-MIB scientific inputs changed after guard release")
            if (
                _canonical_json_bytes(_p_pair_snapshot(root))
                != _canonical_json_bytes(list(p_snapshot))
            ):
                raise _error("E0-MIB P authority identity changed after guard release")
            transfer_authority = require_locked_evaluation_input_bundle_authority(
                verify_remote=True, repo_root=root
            )
            if (
                transfer_authority.get("input_bundle_run_consumed") is not True
                or transfer_authority.get("authority_binding_sha256")
                != authority.get("authority_binding_sha256")
                or transfer_authority.get("r_outputs_sha256")
                != semantic.get("r_outputs_sha256")
            ):
                raise _error(
                    "E0-MIB effective authority drifted during ownership transfer"
                )
            for output, expected in zip(published, member_payloads, strict=True):
                mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"R ownership transfer pass {pass_index}",
                )
            mcalm.mcall.mcalk.mcalj.mcali._require_owned_identity_set(
                published,
                context=f"MIB R ownership transfer pass {pass_index}",
            )
            recaptured_semantic = _validate_r_bundle_semantics(
                repo_root=root, pointers_required=False
            )
            _require_expected_r_materialization(
                recaptured_semantic, materialization
            )
            if _canonical_json_bytes(recaptured_semantic) != _canonical_json_bytes(
                semantic
            ):
                raise _error("E0-MIB R semantics changed after guard release")
        committed = True
        return {
            "gate": "R-E0-MI",
            "status": "input_bundle_written_unpublished_pre_dvc",
            "physical_output_count": 4,
            "light_output_count": 2,
            "source_snapshot_count": len(source_snapshots),
            "r_outputs_sha256": semantic["r_outputs_sha256"],
            "input_only": True,
            "target_paths_opened": False,
            "target_availability_inspected": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
            "writes_performed": True,
        }
    except BaseException as exc:
        rollback = _rollback_owned_outputs(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureLockedEvaluationInputBundleError):
            raise
        raise _error("E0-MIB input-bundle execution failed") from exc
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-input-bundle", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(argv)
    try:
        payload = execute_locked_evaluation_input_bundle()
    except ClosureLockedEvaluationInputBundleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
