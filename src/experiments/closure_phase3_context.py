#!/usr/bin/env python
"""Materialize the authenticated, in-memory Closure V1 Phase 3 context.

This module is loaded from source bytes already bound by the E0-U authority.
It never writes.  Model scoring is completed from input-only artifacts before
the first target table is joined, and no fitting, calibration, threshold
selection, conformal recomputation, or unavailable-model substitution occurs.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import stat
import zipfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator, cast

import joblib
import numpy as np
import pandas as pd

from src.mifal.closure_panel_adapter import (
    panel_row_to_closure_mifal_payload,
    payload_is_eligible,
)
from src.mifal.ed_t2 import MIFALEDT2
from src.experiments.build_closure_e10_source_evidence import (
    load_closure_e10_software_evidence,
)


RNG_SEED = 1729
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
HORIZONS = (1, 2, 3)
MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1")
UNAVAILABLE_MODEL_IDS = ("P0", "P1", "A2")
DETERMINISTIC_MODEL_IDS = ("B0", "F0", "M0")
ENDPOINTS = ("bloom", "continuous", "uncertainty", "ordinal")
ENDPOINT_AVAILABILITY = {
    "B0": {"bloom": True, "continuous": False, "uncertainty": False, "ordinal": False},
    "B1": {"bloom": True, "continuous": True, "uncertainty": False, "ordinal": True},
    "B2": {"bloom": True, "continuous": False, "uncertainty": False, "ordinal": True},
    "F0": {"bloom": False, "continuous": True, "uncertainty": False, "ordinal": False},
    "F1": {"bloom": False, "continuous": True, "uncertainty": False, "ordinal": False},
    "P0": {"bloom": False, "continuous": False, "uncertainty": False, "ordinal": False},
    "P1": {"bloom": False, "continuous": False, "uncertainty": False, "ordinal": False},
    "M0": {"bloom": True, "continuous": True, "uncertainty": False, "ordinal": False},
    "A0": {"bloom": True, "continuous": True, "uncertainty": True, "ordinal": False},
    "A1": {"bloom": True, "continuous": True, "uncertainty": True, "ordinal": False},
}
MODEL_AVAILABILITY = {
    "B0": "available", "B1": "available", "B2": "available",
    "F0": "available", "F1": "available", "P0": "unavailable",
    "P1": "unavailable", "M0": "available", "A0": "available",
    "A1": "available", "A2": "unavailable",
}

INTENT_PATH = Path("data/closure_v1/locked_evaluation/intent_origins.parquet")
HISTORY_PATH = Path("data/closure_v1/locked_evaluation/input_history.parquet")
ORIGIN_FEATURES_PATH = Path("data/closure_v1/locked_evaluation/origin_features.parquet")
R10_MANIFEST_PATH = Path("reports/closure_v1/01_surface/locked_evaluation_input_manifest.json")
WEIGHTS_PATH = Path("data/closure_v1/locked_evaluation/phase3_runtime_weights.npz")
WARMUP_PATH = Path("data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet")
OVERLAY_MANIFEST_PATH = Path("reports/closure_v1/01_surface/phase3_input_overlay_manifest.json")
CALIBRATOR_SPECS_PATH = Path("reports/closure_v1/03_calibration/calibrator_specs.json")
THRESHOLDS_PATH = Path("reports/closure_v1/03_calibration/alert_thresholds.csv")
CUTPOINTS_PATH = Path("reports/closure_v1/03_calibration/ordinal_cutpoints.csv")
HOLDOUT_ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
HYPOTHESIS_REGISTRY_PATH = Path("reports/closure_v1/00_protocol/hypothesis_registry.csv")
TARGET_PATH = Path("data/targets/monthly_targets_model_v0.parquet")
TARGET_SHA256 = "c93ee8dbf424828c8dc11bc5da236d5c505e5f6ba7478eb689cca12a88c7e799"
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
PANEL_SHA256 = "8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62"

EVIDENCE_ROOT = Path("reports/closure_v1/00_protocol/software_evidence_source")
EVIDENCE_MANIFEST_PATH = EVIDENCE_ROOT / "software_evidence_source_manifest.json"
EVIDENCE_KEYS = (
    "public_tests_xml",
    "test_report",
    "openapi",
    "openapi_contract_report",
    "end_to_end_report",
    "environment",
)
EVIDENCE_SOURCE_PATHS = (
    EVIDENCE_ROOT / "public_tests.xml",
    EVIDENCE_ROOT / "test_report.md",
    EVIDENCE_ROOT / "openapi.json",
    EVIDENCE_ROOT / "openapi_contract_report.md",
    EVIDENCE_ROOT / "end_to_end_report.md",
    EVIDENCE_ROOT / "environment.json",
    EVIDENCE_MANIFEST_PATH,
)

R10_INTENT_COLUMNS = (
    "origin_id", "source_id", "site_id", "holdout_group_id", "assignment_role",
    "origin_year_month", "base_input_status", "base_input_reason",
    "history_start_year_month", "history_end_year_month", "history_length_months",
    "history_row_count", "missing_history_row_count",
)
PHYSICAL_COLUMNS = (
    "mean_TP_ugL", "std_TP_ugL", "n_obs_TP_ugL", "n_bad_TP_ugL", "qc_ok_rate_TP_ugL",
    "mean_TN_ugL", "std_TN_ugL", "n_obs_TN_ugL", "n_bad_TN_ugL", "qc_ok_rate_TN_ugL",
    "mean_temperature_C", "std_temperature_C", "n_obs_temperature_C", "n_bad_temperature_C", "qc_ok_rate_temperature_C",
    "mean_secchi_depth_m", "std_secchi_depth_m", "n_obs_secchi_depth_m", "n_bad_secchi_depth_m", "qc_ok_rate_secchi_depth_m",
    "mean_turbidity_NTU", "std_turbidity_NTU", "n_obs_turbidity_NTU", "n_bad_turbidity_NTU", "qc_ok_rate_turbidity_NTU",
    "mean_DO_mgL", "std_DO_mgL", "n_obs_DO_mgL", "n_bad_DO_mgL", "qc_ok_rate_DO_mgL",
    "mean_pH", "std_pH", "n_obs_pH", "n_bad_pH", "qc_ok_rate_pH",
    "log_TP", "log_TN", "TN_TP_ratio",
    "season_sin_annual", "season_cos_annual", "season_sin_semiannual", "season_cos_semiannual",
)
HISTORY_COLUMNS = (
    "origin_id", "source_id", "site_id", "holdout_group_id", "assignment_role",
    "origin_year_month", "base_input_status", "base_input_reason",
    "history_year_month", "history_offset_months", "row_present", *PHYSICAL_COLUMNS,
)
ORIGIN_FEATURE_COLUMNS = (
    "origin_id", "source_id", "site_id", "holdout_group_id", "assignment_role",
    "origin_year_month", "base_input_status", "base_input_reason", "row_present",
    *PHYSICAL_COLUMNS,
)
RAW_MEAN_COLUMNS = (
    "mean_TP_ugL", "mean_TN_ugL", "mean_DO_mgL", "mean_pH",
    "mean_turbidity_NTU", "mean_secchi_depth_m", "mean_temperature_C",
)
RAW_N_OBS_COLUMNS = tuple(column.replace("mean_", "n_obs_") for column in RAW_MEAN_COLUMNS)
SEASON_COLUMNS = (
    "season_sin_annual", "season_cos_annual", "season_sin_semiannual", "season_cos_semiannual",
)
ANFIS_FEATURES = {
    "N": ("tp_pressure", "tn_pressure", "ratio_imbalance_pressure"),
    "F": ("do_good", "ph_good", "turbidity_good", "secchi_good"),
    "T": ("temp_favorable",),
}
ANFIS_RULE_COUNTS = {"N": 27, "F": 81, "T": 3}
A0_INPUT_COLUMNS = (
    *(f"x_{column}" for column in RAW_MEAN_COLUMNS),
    *(f"mask_{column}" for column in RAW_MEAN_COLUMNS),
    *SEASON_COLUMNS,
)
A1_STATE_COLUMNS = (
    "x_yN", "x_yF", "x_yT", "x_sigma_N", "x_sigma_F", "x_sigma_T",
    "x_delta_yN", "x_delta_yF", "x_delta_yT",
)
A1_INPUT_COLUMNS = (*A0_INPUT_COLUMNS, *A1_STATE_COLUMNS)
E1_PREDICTION_COLUMNS = (
    "source_id", "site_id", "common_origin_id", "origin_year_month",
    "target_year_month", "horizon_months", "model_id", "model_seed", "seed_slot",
    "terminal_status", "bloom_status", "continuous_status", "uncertainty_status",
    "ordinal_status", "bloom_probability", "alert_threshold", "predicted_value",
    "predicted_sigma", "predicted_lower", "predicted_upper", "continuous_score",
    "ordinal_score", "cutpoint_1", "cutpoint_2", "cutpoint_3",
)
E1_INTENT_COLUMNS = (
    "source_id", "site_id", "holdout_group_id", "common_origin_id",
    "origin_year_month", "target_year_month", "horizon_months",
    "evaluation_cohort", "evaluation_role", "time_role",
)
E1_TARGET_COLUMNS = (
    "source_id", "site_id", "common_origin_id", "target_year_month",
    "horizon_months", "actual_bloom", "actual_value", "actual_chla_ug_l",
    "actual_trophic_state", "target_status",
)
E2_SITE_STRATA_COLUMNS = (
    "source_id",
    "site_id",
    "series_length_band",
    "historical_bloom_present",
    "coverage_band",
)
FUTURE_TROPHIC_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
    "future_TP_ugL",
    "future_secchi_depth_m",
    "future_chlorophyll_a_ugL",
)
HYPOTHESIS_COLUMNS = (
    "hypothesis_id",
    "multiplicity_family",
    "comparison_id",
    "endpoints",
    "estimand",
    "alternative",
    "evaluation_cohort",
    "horizons_months",
    "multiplicity_universe_size",
    "correction_method",
    "family_wise_alpha",
    "availability_condition",
    "status",
    "availability_reason",
    "p_value",
    "effect_estimate",
    "confidence_interval",
    "holm_universe_retained",
)
E7_PREDICTION_COLUMNS = (
    "model_id",
    "seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_cohort",
    "evaluation_role",
    "horizon_months",
    "target_year_month",
    "status",
    "y_true",
    "y_prob",
)
E8_EVALUATION_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
    "model_id",
    "model_seed",
    "seed_slot",
    "status",
    "y_true",
    "prediction",
    "sigma",
)
EXPECTED_CONTEXT_TABLES = frozenset(
    {
        "predictions_long",
        "intent_origins",
        "target_outcomes",
        "e2_site_strata",
        "future_trophic_indicators",
        "hypothesis_registry",
        "e7_predictions",
        "locked_conformal_factors",
        "uncertainty_evaluation",
    }
)


class ClosurePhase3ContextError(RuntimeError):
    """Raised when a sealed Phase 3 input or inference binding drifts."""


_ACTIVE_ANCHORED_INPUT_RECORDS: list[dict[str, Any]] | None = None
_PREFLIGHT_ANCHORED_INPUT_RECORDS: tuple[tuple[str, int, str], ...] | None = None


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while chunk := os.read(descriptor, 1024 * 1024):
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _canonical_relative_path(relative_path: Path) -> Path:
    path = Path(relative_path)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ClosurePhase3ContextError(
            f"sealed input path is not repository-relative and canonical: {path.as_posix()}"
        )
    return path


@contextmanager
def _anchored_regular_stream(
    repo_root: Path,
    relative_path: Path,
    *,
    label: str,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_nlink: int | None = None,
) -> Iterator[tuple[BinaryIO, dict[str, Any]]]:
    """Yield one no-follow stream whose bytes and name stay bound to one inode.

    Authentication, decoding, and the post-decode recapture all use the same
    opened descriptor.  Every ancestor is traversed through a directory FD, so
    a symlink or namespace replacement cannot redirect a sealed scientific
    input between the digest check and the decoder.
    """

    path = _canonical_relative_path(relative_path)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directories: list[int] = []
    directory_bindings: list[tuple[int, str, int, tuple[int, ...]]] = []
    descriptor: int | None = None
    root_path = Path(repo_root)
    root_identity: tuple[int, ...] | None = None
    try:
        named_root = os.lstat(root_path)
        current = os.open(root_path, directory_flags)
        opened_root = os.fstat(current)
        if (
            not stat.S_ISDIR(named_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or _file_identity(named_root) != _file_identity(opened_root)
        ):
            os.close(current)
            raise ClosurePhase3ContextError(
                f"{label} repository root is not one anchored directory"
            )
        root_identity = _file_identity(opened_root)
        directories.append(current)
        for component in path.parts[:-1]:
            parent = current
            named_directory = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            current = os.open(component, directory_flags, dir_fd=parent)
            opened_directory = os.fstat(current)
            if (
                not stat.S_ISDIR(named_directory.st_mode)
                or not stat.S_ISDIR(opened_directory.st_mode)
                or _file_identity(named_directory)
                != _file_identity(opened_directory)
            ):
                raise ClosurePhase3ContextError(
                    f"{label} ancestor is not one anchored directory: {path.as_posix()}"
                )
            directories.append(current)
            directory_bindings.append(
                (
                    parent,
                    component,
                    current,
                    _file_identity(opened_directory),
                )
            )
        named_before = os.stat(path.name, dir_fd=current, follow_symlinks=False)
        descriptor = os.open(path.name, file_flags, dir_fd=current)
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or stat.S_IMODE(opened_before.st_mode) not in {0o444, 0o644}
            or _file_identity(named_before) != _file_identity(opened_before)
            or (expected_nlink is not None and opened_before.st_nlink != expected_nlink)
        ):
            raise ClosurePhase3ContextError(
                f"{label} is not one anchored regular file: {path.as_posix()}"
            )
        digest_before = _sha256_descriptor(descriptor)
        if (
            (expected_bytes is not None and opened_before.st_size != expected_bytes)
            or (expected_sha256 is not None and digest_before != expected_sha256)
        ):
            raise ClosurePhase3ContextError(
                f"{label} physical binding drifted: {path.as_posix()}"
            )
        record = {
            "path": path.as_posix(),
            "bytes": opened_before.st_size,
            "sha256": digest_before,
        }
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            stream.seek(0)
            try:
                yield stream, record
            finally:
                opened_after = os.fstat(descriptor)
                try:
                    named_after = os.stat(
                        path.name,
                        dir_fd=current,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise ClosurePhase3ContextError(
                        f"{label} changed during anchored read: {path.as_posix()}"
                    ) from exc
                digest_after = _sha256_descriptor(descriptor)
                if (
                    _file_identity(opened_after) != _file_identity(opened_before)
                    or _file_identity(named_after) != _file_identity(opened_before)
                    or digest_after != digest_before
                ):
                    raise ClosurePhase3ContextError(
                        f"{label} changed during anchored read: {path.as_posix()}"
                    )
                for parent, component, opened_directory, identity_before in (
                    directory_bindings
                ):
                    try:
                        named_directory_after = os.stat(
                            component,
                            dir_fd=parent,
                            follow_symlinks=False,
                        )
                    except OSError as exc:
                        raise ClosurePhase3ContextError(
                            f"{label} ancestor changed during anchored read: "
                            f"{path.as_posix()}"
                        ) from exc
                    if (
                        _file_identity(os.fstat(opened_directory)) != identity_before
                        or _file_identity(named_directory_after) != identity_before
                    ):
                        raise ClosurePhase3ContextError(
                            f"{label} ancestor changed during anchored read: "
                            f"{path.as_posix()}"
                        )
                try:
                    named_root_after = os.lstat(root_path)
                except OSError as exc:
                    raise ClosurePhase3ContextError(
                        f"{label} repository root changed during anchored read"
                    ) from exc
                if (
                    root_identity is None
                    or _file_identity(os.fstat(directories[0])) != root_identity
                    or _file_identity(named_root_after) != root_identity
                ):
                    raise ClosurePhase3ContextError(
                        f"{label} repository root changed during anchored read"
                    )
                if _ACTIVE_ANCHORED_INPUT_RECORDS is not None:
                    _ACTIVE_ANCHORED_INPUT_RECORDS.append(dict(record))
    except ClosurePhase3ContextError:
        raise
    except OSError as exc:
        raise ClosurePhase3ContextError(
            f"{label} cannot be opened without following names: {path.as_posix()}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory in reversed(directories):
            os.close(directory)


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _load_e10_source_evidence(
    *,
    repo_root: Path,
    authority: Mapping[str, Any],
    require_git_publication: bool,
) -> Mapping[str, Any]:
    """Load E10 evidence and bind its seven-file read into the input snapshot."""

    loaded = load_closure_e10_software_evidence(
        repo_root=repo_root,
        expected_h_commit=cast(str, authority["phase3_code_commit"]),
        require_git_publication=require_git_publication,
        include_source_snapshot=True,
    )
    if not isinstance(loaded, Mapping) or set(loaded) != {
        "software_evidence",
        "source_snapshot",
    }:
        raise ClosurePhase3ContextError(
            "E10 source loader did not return evidence and its sealed snapshot"
        )
    evidence = loaded["software_evidence"]
    snapshot = loaded["source_snapshot"]
    if not isinstance(evidence, Mapping) or tuple(evidence) != EVIDENCE_KEYS:
        raise ClosurePhase3ContextError("E10 software-evidence scope drifted")
    expected_snapshot_keys = {
        "schema_version",
        "source_directory",
        "file_count",
        "files",
        "bundle_sha256",
        "directory_chain_anchored_no_follow",
        "single_fd_per_file",
        "ancestor_and_entries_recaptured",
        "repository_commit",
    }
    if not isinstance(snapshot, Mapping) or set(snapshot) != expected_snapshot_keys:
        raise ClosurePhase3ContextError("E10 source snapshot dialect drifted")
    if (
        snapshot["schema_version"] != "closure_e10_source_bundle_snapshot_v1"
        or snapshot["source_directory"] != EVIDENCE_ROOT.as_posix()
        or snapshot["file_count"] != 7
        or snapshot["directory_chain_anchored_no_follow"] is not True
        or snapshot["single_fd_per_file"] is not True
        or snapshot["ancestor_and_entries_recaptured"] is not True
        or snapshot["repository_commit"] != authority["phase3_code_commit"]
    ):
        raise ClosurePhase3ContextError("E10 source snapshot authority drifted")
    records_value = snapshot["files"]
    if not isinstance(records_value, list) or len(records_value) != 7:
        raise ClosurePhase3ContextError("E10 source snapshot file count drifted")
    records: list[dict[str, Any]] = []
    for expected_path, value in zip(EVIDENCE_SOURCE_PATHS, records_value, strict=True):
        if not isinstance(value, Mapping) or set(value) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise ClosurePhase3ContextError("E10 source snapshot record drifted")
        record_value = cast(Mapping[str, Any], value)
        byte_count = record_value["bytes"]
        digest = record_value["sha256"]
        if (
            record_value["path"] != expected_path.as_posix()
            or type(byte_count) is not int
            or byte_count <= 0
            or type(digest) is not str
            or len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ClosurePhase3ContextError("E10 source snapshot binding drifted")
        records.append(
            {
                "path": expected_path.as_posix(),
                "bytes": byte_count,
                "sha256": digest,
            }
        )
    bundle_digest = snapshot["bundle_sha256"]
    expected_bundle_digest = hashlib.sha256(_canonical_json_bytes(records)).hexdigest()
    if bundle_digest != expected_bundle_digest:
        raise ClosurePhase3ContextError("E10 source snapshot bundle digest drifted")
    if _ACTIVE_ANCHORED_INPUT_RECORDS is None:
        raise ClosurePhase3ContextError(
            "E10 source evidence was loaded outside an anchored context snapshot"
        )
    _ACTIVE_ANCHORED_INPUT_RECORDS.extend(dict(record) for record in records)
    return cast(Mapping[str, Any], evidence)


def _load_json_with_record(
    repo_root: Path,
    relative_path: Path,
    *,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_nlink: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        with _anchored_regular_stream(
            repo_root,
            relative_path,
            label="sealed JSON",
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            expected_nlink=expected_nlink,
        ) as (stream, record):
            value = json.loads(stream.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClosurePhase3ContextError(
            f"sealed JSON cannot be decoded: {relative_path.as_posix()}"
        ) from exc
    if type(value) is not dict:
        raise ClosurePhase3ContextError(
            f"sealed JSON is not an object: {relative_path.as_posix()}"
        )
    return cast(dict[str, Any], value), dict(record)


def _load_json(
    repo_root: Path,
    relative_path: Path,
    *,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_nlink: int | None = None,
) -> dict[str, Any]:
    value, _ = _load_json_with_record(
        repo_root,
        relative_path,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha256,
        expected_nlink=expected_nlink,
    )
    return value


def _require_exact_columns(frame: pd.DataFrame, columns: Sequence[str], *, label: str) -> None:
    if tuple(frame.columns) != tuple(columns):
        raise ClosurePhase3ContextError(f"{label} columns drifted")


def _require_manifest_output(
    manifest: Mapping[str, Any],
    *,
    relative_path: Path,
    label: str,
) -> tuple[int, str]:
    raw = manifest.get("physical_outputs")
    if not isinstance(raw, list):
        raise ClosurePhase3ContextError(f"{label} physical_outputs is absent")
    matches = [
        record
        for record in raw
        if isinstance(record, Mapping)
        and record.get("path") == relative_path.as_posix()
    ]
    if len(matches) != 1:
        raise ClosurePhase3ContextError(
            f"{label} does not bind {relative_path.as_posix()}"
        )
    record = matches[0]
    expected_bytes = record.get("bytes")
    expected_sha256 = record.get("sha256")
    if (
        type(expected_bytes) is not int
        or expected_bytes < 0
        or type(expected_sha256) is not str
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
    ):
        raise ClosurePhase3ContextError(
            f"{label} physical binding is malformed: {relative_path.as_posix()}"
        )
    return expected_bytes, expected_sha256


def _read_parquet_anchored(
    repo_root: Path,
    relative_path: Path,
    *,
    label: str,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_nlink: int | None = None,
    columns: Sequence[str] | None = None,
    filters: list[tuple[str, str, Any]] | None = None,
) -> pd.DataFrame:
    with _anchored_regular_stream(
        repo_root,
        relative_path,
        label=label,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha256,
        expected_nlink=expected_nlink,
    ) as (stream, _):
        return pd.read_parquet(
            stream,
            columns=None if columns is None else list(columns),
            filters=filters,
        )


def _read_csv_anchored(
    repo_root: Path,
    relative_path: Path,
    *,
    label: str,
    keep_default_na: bool = True,
    dtype: Any = None,
) -> pd.DataFrame:
    with _anchored_regular_stream(
        repo_root,
        relative_path,
        label=label,
    ) as (stream, _):
        return pd.read_csv(
            stream,
            keep_default_na=keep_default_na,
            dtype=dtype,
        )


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _finite(values: Any) -> np.ndarray:
    return pd.to_numeric(values, errors="coerce").to_numpy(dtype="float64")


def _period_add(values: pd.Series, months: int | np.ndarray) -> pd.Series:
    periods = pd.PeriodIndex(values.astype(str), freq="M")
    if isinstance(months, np.ndarray):
        result = [period + int(delta) for period, delta in zip(periods, months, strict=True)]
    else:
        result = [period + int(months) for period in periods]
    return pd.Series([str(value) for value in result], index=values.index, dtype="string")


def _validate_boundary(
    authority: Mapping[str, Any], contract: Mapping[str, Any], execution_id: str
) -> None:
    flags = {
        "gate": "E0-U", "effective_authority": True,
        "sealed_batch_execution_authorized": True, "e0_m_authorized": True,
        "e0_u_authorized": True, "evaluation_authorized": True,
        "outcome_access_authorized": True, "writes_performed": False,
    }
    if any(type(authority.get(key)) is not type(value) or authority.get(key) != value for key, value in flags.items()):
        raise ClosurePhase3ContextError("effective E0-U authority drifted")
    if (
        contract.get("schema_version") != "closure_sealed_evaluation_batch_v1"
        or contract.get("experiment_id") != "closure_v1"
        or contract.get("evaluation_refit") != "forbidden"
        or contract.get("one_batch_only") is not True
        or contract.get("model_availability") != MODEL_AVAILABILITY
        or type(authority.get("phase3_code_commit")) is not str
        or len(cast(str, authority.get("phase3_code_commit"))) != 40
        or any(
            character not in "0123456789abcdef"
            for character in cast(str, authority.get("phase3_code_commit"))
        )
        or type(execution_id) is not str
        or not execution_id
    ):
        raise ClosurePhase3ContextError("sealed batch contract drifted")


def _load_input_frames(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    r10 = _load_json(repo_root, R10_MANIFEST_PATH)
    records = {
        path: _require_manifest_output(
            r10,
            relative_path=path,
            label="R10 manifest",
        )
        for path in (INTENT_PATH, HISTORY_PATH, ORIGIN_FEATURES_PATH)
    }
    intents = _read_parquet_anchored(
        repo_root,
        INTENT_PATH,
        label="R10 intent",
        expected_bytes=records[INTENT_PATH][0],
        expected_sha256=records[INTENT_PATH][1],
        expected_nlink=1,
    )
    history = _read_parquet_anchored(
        repo_root,
        HISTORY_PATH,
        label="R10 history",
        expected_bytes=records[HISTORY_PATH][0],
        expected_sha256=records[HISTORY_PATH][1],
        expected_nlink=1,
    )
    origins = _read_parquet_anchored(
        repo_root,
        ORIGIN_FEATURES_PATH,
        label="R10 origin features",
        expected_bytes=records[ORIGIN_FEATURES_PATH][0],
        expected_sha256=records[ORIGIN_FEATURES_PATH][1],
        expected_nlink=1,
    )
    _require_exact_columns(intents, R10_INTENT_COLUMNS, label="R10 intent")
    _require_exact_columns(history, HISTORY_COLUMNS, label="R10 history")
    _require_exact_columns(origins, ORIGIN_FEATURE_COLUMNS, label="R10 origin features")
    if (
        len(intents) != 4488
        or len(history) != 53856
        or len(origins) != 4488
        or intents["origin_id"].nunique() != 4488
        or origins["origin_id"].nunique() != 4488
        or intents[["source_id", "site_id"]].drop_duplicates().shape[0] != 88
        or not intents["source_id"].eq("wqp").all()
        or not intents["assignment_role"].eq("internal_holdout").all()
        or intents["base_input_status"].value_counts().to_dict()
        != {"ineligible": 3684, "eligible": 804}
        or not intents.loc[
            intents["base_input_status"].eq("eligible"), "base_input_reason"
        ].eq("complete_input_history").all()
        or not intents.loc[
            intents["base_input_status"].eq("ineligible"), "base_input_reason"
        ].eq("insufficient_input_history").all()
        or not intents["origin_id"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all()
        or not history.groupby("origin_id", sort=False).size().eq(12).all()
        or set(history["history_offset_months"].astype(int)) != set(range(-11, 1))
    ):
        raise ClosurePhase3ContextError("R10 locked input denominator drifted")
    identity = ["origin_id", "source_id", "site_id", "holdout_group_id", "origin_year_month"]
    if not intents[identity].sort_values(identity, kind="mergesort").reset_index(drop=True).equals(
        origins[identity].sort_values(identity, kind="mergesort").reset_index(drop=True)
    ):
        raise ClosurePhase3ContextError("R10 origin identity frames disagree")
    return (
        intents.sort_values(["source_id", "site_id", "origin_year_month", "origin_id"], kind="mergesort").reset_index(drop=True),
        history.sort_values(["source_id", "site_id", "origin_year_month", "history_offset_months"], kind="mergesort").reset_index(drop=True),
        origins.sort_values(["source_id", "site_id", "origin_year_month", "origin_id"], kind="mergesort").reset_index(drop=True),
    )


def _load_overlay(
    repo_root: Path,
) -> tuple[dict[str, np.ndarray], pd.DataFrame, dict[str, Any], Mapping[str, Any]]:
    manifest, manifest_record = _load_json_with_record(
        repo_root,
        OVERLAY_MANIFEST_PATH,
        expected_nlink=1,
    )
    records = {
        path: _require_manifest_output(
            manifest,
            relative_path=path,
            label="Phase 3 input overlay",
        )
        for path in (WEIGHTS_PATH, WARMUP_PATH)
    }
    numpy_export = manifest.get("numpy_export")
    if not isinstance(numpy_export, Mapping):
        raise ClosurePhase3ContextError("runtime NPZ export registry is absent")
    arrays: dict[str, np.ndarray] = {}
    with _anchored_regular_stream(
        repo_root,
        WEIGHTS_PATH,
        label="Phase 3 runtime NPZ",
        expected_bytes=records[WEIGHTS_PATH][0],
        expected_sha256=records[WEIGHTS_PATH][1],
        expected_nlink=None,
    ) as (stream, _):
        npz_payload = stream.read()
    try:
        zipped = zipfile.ZipFile(io.BytesIO(npz_payload), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ClosurePhase3ContextError("runtime NPZ archive is malformed") from exc
    with zipped, np.load(io.BytesIO(npz_payload), allow_pickle=False) as archive:
        if "__manifest_json__" not in archive.files:
            raise ClosurePhase3ContextError("runtime NPZ internal manifest is absent")
        raw_manifest = np.asarray(archive["__manifest_json__"], dtype="uint8").tobytes()
        try:
            internal = json.loads(raw_manifest.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClosurePhase3ContextError("runtime NPZ internal manifest is malformed") from exc
        if not isinstance(internal, Mapping):
            raise ClosurePhase3ContextError("runtime NPZ internal manifest is not an object")
        export_arrays = numpy_export.get("arrays")
        export_checkpoints = numpy_export.get("checkpoints")
        if not isinstance(export_arrays, list) or not isinstance(
            export_checkpoints, list
        ):
            raise ClosurePhase3ContextError("runtime NPZ export registries are malformed")
        expected_internal = {
            "format_version": numpy_export.get("format_version"),
            "key_dialect": numpy_export.get("key_dialect"),
            "checkpoint_count": numpy_export.get("checkpoint_count"),
            "state_dict_array_count": numpy_export.get("state_dict_array_count"),
            "array_keys": [
                record.get("npz_key")
                for record in export_arrays
                if isinstance(record, Mapping)
            ],
            "arrays": export_arrays,
            "checkpoints": export_checkpoints,
        }
        canonical_internal = _canonical_json_bytes(expected_internal)[:-1]
        if (
            dict(internal) != expected_internal
            or raw_manifest != canonical_internal
            or numpy_export.get("internal_manifest_key") != "__manifest_json__"
            or numpy_export.get("internal_manifest_encoding")
            != "uint8_utf8_canonical_json"
            or numpy_export.get("internal_manifest_bytes") != len(raw_manifest)
            or numpy_export.get("internal_manifest_sha256")
            != hashlib.sha256(raw_manifest).hexdigest()
        ):
            raise ClosurePhase3ContextError(
                "runtime NPZ internal/outer manifest binding drifted"
            )
        expected_names = sorted(name for name in archive.files if name != "__manifest_json__")
        declared = internal.get("arrays")
        declared_names = sorted(
            str(record.get("npz_key"))
            for record in declared
            if isinstance(record, Mapping)
        ) if isinstance(declared, list) else []
        archive_keys = numpy_export.get("archive_keys")
        expected_archive_names = sorted(["__manifest_json__", *expected_names])
        zip_names = [member.filename for member in zipped.infolist()]
        if (
            declared_names != expected_names
            or archive.files != expected_archive_names
            or archive_keys != expected_archive_names
            or numpy_export.get("archive_array_count") != len(expected_archive_names)
            or zip_names != [name + ".npy" for name in expected_archive_names]
            or len(set(zip_names)) != len(zip_names)
        ):
            raise ClosurePhase3ContextError("runtime NPZ array registry drifted")
        declared_by_name = {
            str(record["npz_key"]): record
            for record in cast(list[Mapping[str, Any]], declared)
        }
        for name in expected_names:
            array = np.asarray(archive[name])
            record = declared_by_name[name]
            try:
                npy_payload = zipped.read(name + ".npy")
            except (KeyError, OSError, RuntimeError) as exc:
                raise ClosurePhase3ContextError(
                    f"runtime NPZ member cannot be authenticated: {name}"
                ) from exc
            if (
                array.dtype.kind not in "fiu"
                or not np.isfinite(array.astype("float64")).all()
                or record.get("dtype") != array.dtype.str
                or record.get("shape") != list(array.shape)
                or record.get("element_count") != int(array.size)
                or record.get("data_sha256")
                != hashlib.sha256(array.tobytes(order="C")).hexdigest()
                or record.get("npy_sha256")
                != hashlib.sha256(npy_payload).hexdigest()
            ):
                raise ClosurePhase3ContextError(f"runtime NPZ array is invalid: {name}")
            arrays[name] = array.copy()
    warmup = _read_parquet_anchored(
        repo_root,
        WARMUP_PATH,
        label="Phase 3 adaptive-state warmup",
        expected_bytes=records[WARMUP_PATH][0],
        expected_sha256=records[WARMUP_PATH][1],
        expected_nlink=None,
    )
    warmup_matches = [
        record
        for record in cast(list[Any], manifest.get("physical_outputs", []))
        if isinstance(record, Mapping)
        and record.get("path") == WARMUP_PATH.as_posix()
    ]
    warmup_record = warmup_matches[0] if len(warmup_matches) == 1 else None
    if (
        len(warmup) != 88
        or warmup[["source_id", "site_id"]].duplicated().any()
        or not isinstance(warmup_record, Mapping)
        or warmup_record.get("row_count") != len(warmup)
        or warmup_record.get("site_count") != 88
        or warmup_record.get("columns") != list(warmup.columns)
    ):
        raise ClosurePhase3ContextError("adaptive-state warmup denominator drifted")
    if "mean_chlorophyll_a_ugL" in warmup.columns or "risk_chla" in warmup.columns:
        raise ClosurePhase3ContextError("adaptive-state warmup contains forbidden Chl lineage")
    warmup_summary = manifest.get("warmup")
    if not isinstance(warmup_summary, Mapping):
        raise ClosurePhase3ContextError("adaptive-state warmup summary is absent")
    overlay_record = {
        "manifest": manifest_record,
        "physical_outputs": [
            {
                "path": path.as_posix(),
                "bytes": records[path][0],
                "sha256": records[path][1],
            }
            for path in (WEIGHTS_PATH, WARMUP_PATH)
        ],
    }
    return arrays, warmup, overlay_record, dict(warmup_summary)


def _validate_warmup_against_history(
    warmup: pd.DataFrame,
    history: pd.DataFrame,
    summary: Mapping[str, Any],
) -> None:
    """Bind the warm-up rows and declared counts to the sealed R10 history."""

    _require_exact_columns(
        warmup,
        ("source_id", "site_id", "year_month", "row_present", *PHYSICAL_COLUMNS),
        label="warmup",
    )
    identity = history.loc[
        :, ["source_id", "site_id", "holdout_group_id", "history_year_month"]
    ].copy()
    if identity.empty or identity[["source_id", "site_id", "holdout_group_id"]].isna().any().any():
        raise ClosurePhase3ContextError("warmup R10 identity is incomplete")
    group_counts = identity.groupby(
        ["source_id", "site_id"], sort=True
    )["holdout_group_id"].nunique()
    if not group_counts.eq(1).all():
        raise ClosurePhase3ContextError("warmup R10 holdout group drifted")
    first = (
        identity.groupby(["source_id", "site_id"], sort=True, as_index=False)
        .agg(
            holdout_group_id=("holdout_group_id", "first"),
            first_history_year_month=("history_year_month", "min"),
        )
        .sort_values(["source_id", "site_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    try:
        first_period = pd.PeriodIndex(first["first_history_year_month"], freq="M")
        first["warmup_year_month"] = (first_period - 1).astype(str)
    except (TypeError, ValueError) as exc:
        raise ClosurePhase3ContextError("warmup R10 month identity drifted") from exc
    expected_keys = first.loc[
        :, ["source_id", "site_id", "warmup_year_month"]
    ].rename(columns={"warmup_year_month": "year_month"})
    observed_keys = warmup.loc[:, ["source_id", "site_id", "year_month"]].copy()
    expected_keys = expected_keys.sort_values(
        ["source_id", "site_id", "year_month"], kind="mergesort"
    ).reset_index(drop=True)
    observed_keys = observed_keys.sort_values(
        ["source_id", "site_id", "year_month"], kind="mergesort"
    ).reset_index(drop=True)
    if (
        len(first) != 88
        or not first["source_id"].eq("wqp").all()
        or not observed_keys.equals(expected_keys)
        or not pd.api.types.is_bool_dtype(warmup["row_present"].dtype)
        or warmup["row_present"].isna().any()
    ):
        raise ClosurePhase3ContextError("warmup keys do not match sealed R10 history")

    raw_physical = tuple(
        column for column in PHYSICAL_COLUMNS if column not in SEASON_COLUMNS
    )
    absent = ~warmup["row_present"].astype(bool)
    if not warmup.loc[absent, list(raw_physical)].isna().all().all():
        raise ClosurePhase3ContextError(
            "warmup missing-row physical nullability drifted"
        )
    periods = pd.PeriodIndex(warmup["year_month"], freq="M")
    zero_based_month = (
        pd.Series(periods.astype(str), dtype="string")
        .str.slice(5, 7)
        .astype("int64")
        .to_numpy(dtype="float64")
        - 1.0
    )
    annual = 2.0 * math.pi * zero_based_month / 12.0
    expected_calendar = {
        "season_sin_annual": np.sin(annual),
        "season_cos_annual": np.cos(annual),
        "season_sin_semiannual": np.sin(2.0 * annual),
        "season_cos_semiannual": np.cos(2.0 * annual),
    }
    for column, expected in expected_calendar.items():
        observed = pd.to_numeric(warmup[column], errors="coerce").to_numpy(
            dtype="float64"
        )
        if not np.isfinite(observed).all() or not np.allclose(
            observed, expected, rtol=0.0, atol=1.0e-15
        ):
            raise ClosurePhase3ContextError("warmup calendar derivation drifted")

    first_records = [
        {
            "source_id": str(row.source_id),
            "site_id": str(row.site_id),
            "holdout_group_id": str(row.holdout_group_id),
            "first_history_year_month": str(row.first_history_year_month),
            "warmup_year_month": str(row.warmup_year_month),
        }
        for row in first.itertuples(index=False)
    ]
    expected_first_digest = hashlib.sha256(
        _canonical_json_bytes(first_records)[:-1]
    ).hexdigest()
    present_count = int(warmup["row_present"].sum())
    physical_missing = {
        column: int(warmup[column].isna().sum()) for column in raw_physical
    }
    calendar_missing = {
        column: int(warmup[column].isna().sum()) for column in SEASON_COLUMNS
    }
    if (
        summary.get("site_count") != 88
        or summary.get("row_count") != 88
        or summary.get("row_present_count") != present_count
        or summary.get("row_missing_count") != 88 - present_count
        or summary.get("source_ids") != ["wqp"]
        or summary.get("assignment_roles") != ["internal_holdout"]
        or summary.get("holdout_group_count")
        != int(first["holdout_group_id"].nunique())
        or summary.get("first_history_months_sha256") != expected_first_digest
        or summary.get("physical_missing_counts") != physical_missing
        or summary.get("calendar_missing_counts") != calendar_missing
    ):
        raise ClosurePhase3ContextError(
            "warmup physical rows disagree with their sealed summary"
        )


def _clip_unit(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0.0, 1.0)


def _ramp_up(values: np.ndarray, low: float, high: float) -> np.ndarray:
    out = (values - low) / (high - low)
    return _clip_unit(out)


def _ramp_down(values: np.ndarray, low: float, high: float) -> np.ndarray:
    return _clip_unit(1.0 - (values - low) / (high - low))


def _trapezoid(values: np.ndarray, a: float, b: float, c: float, d: float) -> np.ndarray:
    out = np.minimum(_ramp_up(values, a, b), _ramp_down(values, c, d))
    out[(values >= b) & (values <= c)] = 1.0
    out[~np.isfinite(values)] = np.nan
    return out


def _log_ramp(values: np.ndarray, low: float, high: float) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype="float64")
    valid = np.isfinite(values) & (values >= 0.0)
    out[valid] = _ramp_up(
        np.log(values[valid] + 0.1), math.log(low + 0.1), math.log(high + 0.1)
    )
    return out


def _weighted_signal(signals: Sequence[np.ndarray], weights: Sequence[float]) -> np.ndarray:
    matrix = np.column_stack(signals)
    weight = np.asarray(weights, dtype="float64")
    present = np.isfinite(matrix)
    numerator = np.nansum(matrix * weight[None, :], axis=1)
    denominator = (present * weight[None, :]).sum(axis=1)
    return np.clip(
        np.divide(numerator, denominator, out=np.full(len(matrix), 0.5), where=denominator > 0.0),
        0.0,
        1.0,
    )


def _expert_no_chla_scores(frame: pd.DataFrame) -> np.ndarray:
    tp = _finite(frame["mean_TP_ugL"])
    tn = _finite(frame["mean_TN_ugL"])
    ratio = _finite(frame["TN_TP_ratio"])
    ratio_pressure = np.maximum(_ramp_down(ratio, 8.0, 16.0), _ramp_up(ratio, 50.0, 100.0))
    ratio_pressure[~np.isfinite(ratio)] = np.nan
    y_n = _weighted_signal(
        (_log_ramp(tp, 10.0, 100.0), _log_ramp(tn, 300.0, 1500.0), ratio_pressure),
        (0.45, 0.35, 0.20),
    )
    dissolved = _finite(frame["mean_DO_mgL"])
    ph = _finite(frame["mean_pH"])
    turbidity = _finite(frame["mean_turbidity_NTU"])
    secchi = _finite(frame["mean_secchi_depth_m"])
    turbidity_good = _ramp_down(turbidity, 5.0, 50.0)
    turbidity_good[~np.isfinite(turbidity)] = np.nan
    secchi_good = _ramp_up(secchi, 0.5, 3.0)
    secchi_good[~np.isfinite(secchi)] = np.nan
    y_f = _weighted_signal(
        (_trapezoid(dissolved, 5.0, 7.0, 12.0, 15.0), _trapezoid(ph, 6.5, 7.0, 8.6, 9.5), turbidity_good, secchi_good),
        (0.30, 0.30, 0.20, 0.20),
    )
    temperature = _finite(frame["mean_temperature_C"])
    y_t = _trapezoid(temperature, 15.0, 22.0, 30.0, 35.0)
    y_t[~np.isfinite(y_t)] = 0.5
    return np.clip((y_n + (1.0 - y_f) + y_t) / 3.0, 0.0, 1.0)


def _anfis_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    tp = _finite(frame["mean_TP_ugL"])
    tn = _finite(frame["mean_TN_ugL"])
    ratio = _finite(frame["TN_TP_ratio"])
    ratio_pressure = np.maximum(_ramp_down(ratio, 8.0, 16.0), _ramp_up(ratio, 50.0, 100.0))
    ratio_pressure[~np.isfinite(ratio)] = np.nan
    dissolved = _finite(frame["mean_DO_mgL"])
    ph = _finite(frame["mean_pH"])
    turbidity = _finite(frame["mean_turbidity_NTU"])
    secchi = _finite(frame["mean_secchi_depth_m"])
    temperature = _finite(frame["mean_temperature_C"])
    turbidity_good = _ramp_down(turbidity, 5.0, 50.0)
    secchi_good = _ramp_up(secchi, 0.5, 3.0)
    turbidity_good[~np.isfinite(turbidity)] = np.nan
    secchi_good[~np.isfinite(secchi)] = np.nan
    return pd.DataFrame(
        {
            "tp_pressure": _log_ramp(tp, 10.0, 100.0),
            "tn_pressure": _log_ramp(tn, 300.0, 1500.0),
            "ratio_imbalance_pressure": ratio_pressure,
            "do_good": _trapezoid(dissolved, 5.0, 7.0, 12.0, 15.0),
            "ph_good": _trapezoid(ph, 6.5, 7.0, 8.6, 9.5),
            "turbidity_good": turbidity_good,
            "secchi_good": secchi_good,
            "temp_favorable": _trapezoid(temperature, 15.0, 22.0, 30.0, 35.0),
        },
        index=frame.index,
    )


def _softplus(values: np.ndarray) -> np.ndarray:
    values = values.astype("float32", copy=False)
    return (
        np.maximum(values, np.float32(0.0))
        + np.log1p(np.exp(-np.abs(values))).astype("float32")
    ).astype("float32")


def _anfis_forward(
    arrays: Mapping[str, np.ndarray], *, seed: int, module: str, features: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    prefix = f"anfis/{seed}/{module}/"
    required = (
        "raw_center_gaps", "raw_widths", "consequent_weights",
        "consequent_bias", "rule_indices",
    )
    if any(prefix + key not in arrays for key in required):
        raise ClosurePhase3ContextError(f"runtime ANFIS weights are incomplete: {seed}:{module}")
    raw = features.loc[:, list(ANFIS_FEATURES[module])].to_numpy(dtype="float64")
    missing = (~np.isfinite(raw)).mean(axis=1, dtype="float64")
    x = np.clip(np.nan_to_num(raw, nan=0.5, posinf=0.5, neginf=0.5), 0.0, 1.0).astype("float32")
    center_gaps = arrays[prefix + "raw_center_gaps"].astype("float32")
    shifted = center_gaps - center_gaps.max(axis=1, keepdims=True)
    exp_gap = np.exp(shifted).astype("float32")
    proportions = exp_gap / exp_gap.sum(axis=1, keepdims=True, dtype="float32")
    residual = np.float32(1.0 - 0.0001 * 4.0)
    gaps = np.float32(0.0001) + residual * proportions
    centers = np.cumsum(gaps[:, :-1], axis=1, dtype="float32")
    widths = _softplus(arrays[prefix + "raw_widths"]) + np.float32(0.03)
    rule_indices = arrays[prefix + "rule_indices"].astype("int64")
    weights = arrays[prefix + "consequent_weights"].astype("float32")
    bias = arrays[prefix + "consequent_bias"].astype("float32")
    if rule_indices.shape != (ANFIS_RULE_COUNTS[module], x.shape[1]):
        raise ClosurePhase3ContextError("runtime ANFIS rule registry drifted")
    predictions: list[np.ndarray] = []
    sigmas: list[np.ndarray] = []
    for start in range(0, len(x), 32768):
        part = x[start : start + 32768]
        scaled = (part[:, :, None] - centers[None, :, :]) / widths[None, :, :]
        memberships = np.exp(np.float32(-0.5) * scaled**np.float32(2.0)).astype("float32")
        firing = np.ones((len(part), len(rule_indices)), dtype="float32")
        for feature_index in range(part.shape[1]):
            firing *= memberships[:, feature_index, rule_indices[:, feature_index]]
        denominator = np.maximum(
            firing.sum(axis=1, keepdims=True, dtype="float32"), np.float32(1e-12)
        )
        normalized = firing / denominator
        rule_outputs = part @ weights.T + bias
        raw_output = (normalized * rule_outputs).sum(axis=1, dtype="float32")
        predictions.append(_sigmoid(raw_output.astype("float64")))
        quantized = firing.astype("float32").astype("float64")
        total = np.maximum(quantized.sum(axis=1, keepdims=True), 1e-12)
        probability = quantized / total
        entropy = -(probability * np.log(np.clip(probability, 1e-12, 1.0))).sum(axis=1)
        entropy /= math.log(ANFIS_RULE_COUNTS[module])
        sigmas.append(np.clip(0.10 + 0.45 * entropy + 0.35 * missing[start : start + len(part)], 0.0, 1.0))
    return np.concatenate(predictions), np.concatenate(sigmas)


def _deduplicated_month_surface(history: pd.DataFrame, warmup: pd.DataFrame) -> pd.DataFrame:
    monthly = history.loc[:, ["source_id", "site_id", "history_year_month", "row_present", *PHYSICAL_COLUMNS]].rename(
        columns={"history_year_month": "year_month"}
    )
    comparison = monthly.copy()
    comparison["_row_digest"] = pd.util.hash_pandas_object(
        comparison[["row_present", *PHYSICAL_COLUMNS]], index=False
    ).astype("uint64")
    if comparison.groupby(["source_id", "site_id", "year_month"], sort=False)["_row_digest"].nunique().gt(1).any():
        raise ClosurePhase3ContextError("overlapping R10 history rows disagree")
    monthly = monthly.drop_duplicates(["source_id", "site_id", "year_month"], keep="first")
    _require_exact_columns(warmup, ("source_id", "site_id", "year_month", "row_present", *PHYSICAL_COLUMNS), label="warmup")
    combined = pd.concat([warmup, monthly], ignore_index=True)
    if combined.duplicated(["source_id", "site_id", "year_month"]).any():
        raise ClosurePhase3ContextError("warmup overlaps the R10 month surface")
    return combined.sort_values(["source_id", "site_id", "year_month"], kind="mergesort").reset_index(drop=True)


def _adaptive_states(
    arrays: Mapping[str, np.ndarray], month_surface: pd.DataFrame
) -> dict[int, pd.DataFrame]:
    features = _anfis_feature_frame(month_surface)
    result: dict[int, pd.DataFrame] = {}
    for seed in REGISTERED_SEEDS:
        y_n, sigma_n = _anfis_forward(arrays, seed=seed, module="N", features=features)
        y_f, sigma_f = _anfis_forward(arrays, seed=seed, module="F", features=features)
        y_t, sigma_t = _anfis_forward(arrays, seed=seed, module="T", features=features)
        state = month_surface.loc[:, ["source_id", "site_id", "year_month", "row_present"]].copy()
        state["yN"] = y_n
        state["yF"] = y_f
        state["yT"] = y_t
        state["sigma_N"] = sigma_n
        state["sigma_F"] = sigma_f
        state["sigma_T"] = sigma_t
        state = state.sort_values(["source_id", "site_id", "year_month"], kind="mergesort").reset_index(drop=True)
        prior = state.groupby(["source_id", "site_id"], sort=False)[
            ["year_month", "row_present", "yN", "yF", "yT"]
        ].shift(1)
        current_period = pd.PeriodIndex(state["year_month"], freq="M")
        prior_period = pd.PeriodIndex(prior["year_month"].fillna("1900-01"), freq="M")
        exact_previous = (
            ((current_period.asi8 - prior_period.asi8) == 1)
            & state["row_present"].astype(bool).to_numpy()
            & prior["row_present"].fillna(False).astype(bool).to_numpy()
        )
        for channel in ("yN", "yF", "yT"):
            delta = state[channel].to_numpy(dtype="float64") - pd.to_numeric(prior[channel], errors="coerce").to_numpy(dtype="float64")
            # The sealed state-export contract assigns zero when the exact
            # preceding physical month is absent; it never substitutes a
            # synthetic missing-row ANFIS state.
            delta[~exact_previous] = 0.0
            state[f"delta_{channel}"] = delta
        result[seed] = state
    return result


def _load_calibration(
    repo_root: Path,
) -> tuple[dict[tuple[str, int, int], Mapping[str, Any]], dict[tuple[str, int, int], float], dict[tuple[str, int, int], tuple[float, float, float]], pd.DataFrame]:
    specs = _load_json(repo_root, CALIBRATOR_SPECS_PATH)
    raw_calibrators = specs.get("bloom_calibrators")
    raw_factors = specs.get("split_conformal_q_c")
    if not isinstance(raw_calibrators, list) or len(raw_calibrators) != 66 or not isinstance(raw_factors, list) or len(raw_factors) != 90:
        raise ClosurePhase3ContextError("locked calibration registry drifted")
    calibrators: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for record in raw_calibrators:
        if not isinstance(record, Mapping):
            raise ClosurePhase3ContextError("locked bloom calibrator is malformed")
        key = (str(record["model_id"]), int(record["model_seed"]), int(record["horizon_months"]))
        if key in calibrators:
            raise ClosurePhase3ContextError("locked bloom calibrator is duplicated")
        calibrators[key] = record
    thresholds_frame = _read_csv_anchored(
        repo_root,
        THRESHOLDS_PATH,
        label="locked alert thresholds",
    )
    thresholds = {
        (str(model_id), int(model_seed), int(horizon)): float(threshold)
        for model_id, model_seed, horizon, threshold in thresholds_frame.loc[
            :, ["model_id", "model_seed", "horizon_months", "threshold"]
        ].itertuples(index=False, name=None)
    }
    cutpoint_frame = _read_csv_anchored(
        repo_root,
        CUTPOINTS_PATH,
        label="locked ordinal cutpoints",
        keep_default_na=False,
    )
    cutpoints: dict[tuple[str, int, int], tuple[float, float, float]] = {}
    for model_id, model_seed, horizon, status, serialized in cutpoint_frame.loc[
        :,
        [
            "model_id",
            "model_seed",
            "horizon_months",
            "status",
            "cutpoints",
        ],
    ].itertuples(index=False, name=None):
        if str(status) != "completed":
            continue
        values = json.loads(str(serialized))
        if not isinstance(values, list) or len(values) != 3:
            raise ClosurePhase3ContextError("locked ordinal cutpoints are malformed")
        cutpoints[(str(model_id), int(model_seed), int(horizon))] = cast(
            tuple[float, float, float], tuple(float(value) for value in values)
        )
    factor_columns = (
        "model_id", "model_seed", "horizon_months", "coverage_level",
        "calibration_year", "finite_rows", "order_statistic_rank", "q_c", "status",
    )
    factors = pd.DataFrame(raw_factors).loc[:, list(factor_columns)]
    return calibrators, thresholds, cutpoints, factors


def _apply_calibrator(raw: np.ndarray, spec: Mapping[str, Any]) -> np.ndarray:
    refit = spec.get("refit_spec")
    if not isinstance(refit, Mapping):
        raise ClosurePhase3ContextError("locked calibrator refit_spec is absent")
    method = refit.get("method")
    parameters = refit.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ClosurePhase3ContextError("locked calibrator parameters are malformed")
    if method == "identity":
        calibrated = raw.astype("float64", copy=True)
    elif method == "platt_logistic":
        calibrated = _sigmoid(
            float(parameters["coefficient"]) * raw.astype("float64")
            + float(parameters["intercept"])
        )
    elif method == "isotonic_regression":
        calibrated = np.interp(
            raw.astype("float64"),
            np.asarray(parameters["x_thresholds"], dtype="float64"),
            np.asarray(parameters["y_thresholds"], dtype="float64"),
        )
    else:
        raise ClosurePhase3ContextError(f"unknown locked calibrator: {method}")
    if not np.isfinite(calibrated).all():
        raise ClosurePhase3ContextError("locked calibrator produced a nonfinite value")
    return np.clip(calibrated, 0.0, 1.0)


def _preprocess_gru_tensor(
    tensor: np.ndarray, preprocessor: Mapping[str, Any], expected_columns: Sequence[str]
) -> np.ndarray:
    if preprocessor.get("input_columns") != list(expected_columns):
        raise ClosurePhase3ContextError("GRU preprocessor input order drifted")
    records = preprocessor.get("columns")
    if not isinstance(records, list) or len(records) != 7:
        raise ClosurePhase3ContextError("GRU raw standardizer drifted")
    out = tensor.astype("float64", copy=True)
    masks = out[:, :, 7:14]
    if not np.isin(masks, (0.0, 1.0)).all():
        raise ClosurePhase3ContextError("GRU observed masks are not binary")
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ClosurePhase3ContextError("GRU raw standardizer record drifted")
        typed_record = cast(Mapping[str, Any], record)
        if typed_record.get("column") != expected_columns[index]:
            raise ClosurePhase3ContextError("GRU raw standardizer column drifted")
        observed = masks[:, :, index] == 1.0
        raw = out[:, :, index]
        if not np.isfinite(raw[observed]).all():
            raise ClosurePhase3ContextError("GRU observed raw value is nonfinite")
        raw[observed] = (raw[observed] - float(typed_record["mean"])) / max(
            float(typed_record["standard_deviation"]), 1e-12
        )
        raw[~observed] = 0.0
    if not np.isfinite(out).all():
        raise ClosurePhase3ContextError("GRU preprocessed tensor is nonfinite")
    return out.astype("float32")


def _gru_forward(
    arrays: Mapping[str, np.ndarray], *, model_id: str, seed: int, tensor: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    prefix = f"gru/{model_id}/{seed}/"
    names = (
        "gru.weight_ih_l0", "gru.weight_hh_l0", "gru.bias_ih_l0", "gru.bias_hh_l0",
        "bloom_delta.weight", "bloom_delta.bias", "risk_delta.weight", "risk_delta.bias",
        "risk_logvar.weight", "risk_logvar.bias", "bloom_prior_logits", "risk_prior_logits",
    )
    if any(prefix + name not in arrays for name in names):
        raise ClosurePhase3ContextError(f"runtime GRU weights are incomplete: {model_id}:{seed}")
    w_ih = arrays[prefix + "gru.weight_ih_l0"].astype("float32")
    w_hh = arrays[prefix + "gru.weight_hh_l0"].astype("float32")
    b_ih = arrays[prefix + "gru.bias_ih_l0"].astype("float32")
    b_hh = arrays[prefix + "gru.bias_hh_l0"].astype("float32")
    if w_ih.shape != (288, tensor.shape[2]) or w_hh.shape != (288, 96):
        raise ClosurePhase3ContextError("runtime GRU architecture drifted")
    outputs: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for start in range(0, len(tensor), 2048):
        part = tensor[start : start + 2048].astype("float32", copy=False)
        hidden = np.zeros((len(part), 96), dtype="float32")
        for step in range(12):
            input_gates = part[:, step, :] @ w_ih.T + b_ih
            hidden_gates = hidden @ w_hh.T + b_hh
            i_r, i_z, i_n = np.split(input_gates, 3, axis=1)
            h_r, h_z, h_n = np.split(hidden_gates, 3, axis=1)
            reset = _sigmoid((i_r + h_r).astype("float64")).astype("float32")
            update = _sigmoid((i_z + h_z).astype("float64")).astype("float32")
            candidate = np.tanh(i_n + reset * h_n).astype("float32")
            hidden = ((np.float32(1.0) - update) * candidate + update * hidden).astype("float32")
        bloom_logits = (
            hidden @ arrays[prefix + "bloom_delta.weight"].astype("float32").T
            + arrays[prefix + "bloom_delta.bias"].astype("float32")
            + arrays[prefix + "bloom_prior_logits"].astype("float32")
        )
        risk_logits = (
            hidden @ arrays[prefix + "risk_delta.weight"].astype("float32").T
            + arrays[prefix + "risk_delta.bias"].astype("float32")
            + arrays[prefix + "risk_prior_logits"].astype("float32")
        )
        logvar = (
            hidden @ arrays[prefix + "risk_logvar.weight"].astype("float32").T
            + arrays[prefix + "risk_logvar.bias"].astype("float32")
        )
        outputs.append(
            (
                _sigmoid(bloom_logits.astype("float64")),
                _sigmoid(risk_logits.astype("float64")),
                np.clip(logvar.astype("float64"), -10.0, 2.0),
            )
        )
    return (
        np.concatenate([part[0] for part in outputs], axis=0),
        np.concatenate([part[1] for part in outputs], axis=0),
        np.concatenate([part[2] for part in outputs], axis=0),
    )


def _sequence_tensors(
    history: pd.DataFrame,
    intents: pd.DataFrame,
    adaptive: Mapping[int, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray], dict[int, np.ndarray]]:
    if len(history) != len(intents) * 12:
        raise ClosurePhase3ContextError("R10 sequence reshape denominator drifted")
    origin_matrix = history["origin_id"].astype(str).to_numpy().reshape(len(intents), 12)
    if not np.all(origin_matrix == intents["origin_id"].astype(str).to_numpy()[:, None]):
        raise ClosurePhase3ContextError("R10 sequence order does not match intents")
    row_present = history["row_present"].astype(bool).to_numpy().reshape(len(intents), 12)
    raw = np.empty((len(intents), 12, 7), dtype="float32")
    masks = np.empty_like(raw)
    for index, (mean_column, n_obs_column) in enumerate(zip(RAW_MEAN_COLUMNS, RAW_N_OBS_COLUMNS, strict=True)):
        values = pd.to_numeric(history[mean_column], errors="coerce").to_numpy(dtype="float64").reshape(len(intents), 12)
        observations = pd.to_numeric(history[n_obs_column], errors="coerce").to_numpy(dtype="float64").reshape(len(intents), 12)
        observed = row_present & np.isfinite(values) & np.isfinite(observations) & (observations > 0.0)
        raw[:, :, index] = np.where(observed, values, 0.0).astype("float32")
        masks[:, :, index] = observed.astype("float32")
    seasons = np.stack(
        [
            pd.to_numeric(history[column], errors="coerce").to_numpy(dtype="float64").reshape(len(intents), 12)
            for column in SEASON_COLUMNS
        ],
        axis=2,
    )
    a0_valid = (
        intents["base_input_status"].astype(str).eq("eligible").to_numpy()
        & row_present.all(axis=1)
        & np.isfinite(seasons).all(axis=(1, 2))
    )
    a0 = np.concatenate([raw, masks, np.nan_to_num(seasons, nan=0.0).astype("float32")], axis=2)
    a1_tensors: dict[int, np.ndarray] = {}
    a1_valid: dict[int, np.ndarray] = {}
    history_keys = history.loc[:, ["source_id", "site_id", "history_year_month"]].rename(
        columns={"history_year_month": "year_month"}
    )
    for seed in REGISTERED_SEEDS:
        state_columns = [
            "yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T",
            "delta_yN", "delta_yF", "delta_yT",
        ]
        joined = history_keys.merge(
            adaptive[seed].loc[:, ["source_id", "site_id", "year_month", *state_columns]],
            on=["source_id", "site_id", "year_month"],
            how="left",
            validate="many_to_one",
            sort=False,
        )
        values = joined[state_columns].to_numpy(dtype="float64").reshape(len(intents), 12, 9)
        valid = a0_valid & np.isfinite(values).all(axis=(1, 2))
        a1_tensors[seed] = np.concatenate(
            [a0, np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0).astype("float32")],
            axis=2,
        )
        a1_valid[seed] = valid
    return a0, a0_valid, a1_tensors, a1_valid


def _load_gru_predictions(
    repo_root: Path,
    arrays: Mapping[str, np.ndarray],
    a0: np.ndarray,
    a0_valid: np.ndarray,
    a1: Mapping[int, np.ndarray],
    a1_valid: Mapping[int, np.ndarray],
) -> dict[tuple[str, int], dict[str, np.ndarray]]:
    outputs: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    for model_id in ("A0", "A1"):
        for seed in REGISTERED_SEEDS:
            preprocessor_path = Path(
                f"reports/closure_v1/02_models/{model_id}/seed_{seed}_preprocessor.json"
            )
            preprocessor = _load_json(repo_root, preprocessor_path)
            raw_tensor = a0 if model_id == "A0" else a1[seed]
            valid = a0_valid if model_id == "A0" else a1_valid[seed]
            transformed = _preprocess_gru_tensor(
                raw_tensor,
                preprocessor,
                A0_INPUT_COLUMNS if model_id == "A0" else A1_INPUT_COLUMNS,
            )
            bloom, risk, logvar = _gru_forward(
                arrays, model_id=model_id, seed=seed, tensor=transformed
            )
            sigma = np.sqrt(np.exp(logvar))
            if bloom.shape != (len(a0), 3) or risk.shape != bloom.shape or sigma.shape != bloom.shape:
                raise ClosurePhase3ContextError("GRU direct horizon output shape drifted")
            outputs[(model_id, seed)] = {
                "bloom_raw": bloom,
                "continuous": risk,
                "sigma": sigma,
                "valid": np.repeat(valid[:, None], 3, axis=1),
            }
    return outputs


def _load_b2_predictions(
    repo_root: Path, origins: pd.DataFrame
) -> dict[tuple[str, int], dict[str, np.ndarray]]:
    specs = _load_json(
        repo_root,
        Path("reports/closure_v1/02_models/baselines/model_specs.json"),
    )
    b2 = specs.get("B2")
    if not isinstance(b2, Mapping) or b2.get("model_seeds") != list(REGISTERED_SEEDS):
        raise ClosurePhase3ContextError("B2 model registry drifted")
    feature_order = b2.get("feature_order")
    if not isinstance(feature_order, list) or feature_order != list(PHYSICAL_COLUMNS):
        raise ClosurePhase3ContextError("B2 feature order drifted")
    records = {
        str(record["path"]): record
        for field in ("pipeline_records", "preprocessor_records")
        for record in cast(Sequence[Mapping[str, Any]], b2[field])
    }
    valid = origins["row_present"].astype(bool).to_numpy()
    outputs: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    for seed in REGISTERED_SEEDS:
        raw = np.empty((len(origins), 3), dtype="float64")
        for horizon in HORIZONS:
            stem = f"models/closure_v1/baselines/B2/seed_{seed}/hist_gradient_boosting_classifier_h{horizon}"
            model_relative = f"{stem}_pipeline.joblib"
            preprocessor_relative = f"{stem}_preprocessor.json"
            for relative in (model_relative, preprocessor_relative):
                record = records.get(relative)
                if (
                    not isinstance(record, Mapping)
                    or type(record.get("bytes")) is not int
                    or type(record.get("sha256")) is not str
                ):
                    raise ClosurePhase3ContextError(f"B2 artifact binding drifted: {relative}")
            preprocessor_record = records[preprocessor_relative]
            preprocessor = _load_json(
                repo_root,
                Path(preprocessor_relative),
                expected_bytes=cast(int, preprocessor_record["bytes"]),
                expected_sha256=cast(str, preprocessor_record["sha256"]),
            )
            if preprocessor.get("feature_order") != feature_order or preprocessor.get("scaling") != "none":
                raise ClosurePhase3ContextError("B2 preprocessor drifted")
            matrix = origins.loc[:, feature_order].apply(
                pd.to_numeric, errors="coerce"
            ).to_numpy(dtype="float64", copy=True)
            medians = np.asarray(preprocessor.get("medians_float64"), dtype="float64")
            missing = ~np.isfinite(matrix)
            matrix[missing] = np.take(medians, np.nonzero(missing)[1])
            model_record = records[model_relative]
            with _anchored_regular_stream(
                repo_root,
                Path(model_relative),
                label="B2 pipeline bundle",
                expected_bytes=cast(int, model_record["bytes"]),
                expected_sha256=cast(str, model_record["sha256"]),
            ) as (stream, _):
                model_bundle = joblib.load(stream)
            if (
                not isinstance(model_bundle, Mapping)
                or set(model_bundle) != {
                    "model",
                    "preprocessor",
                    "model_seed",
                    "candidate",
                    "horizon_months",
                }
                or model_bundle.get("model_seed") != seed
                or model_bundle.get("candidate") != "hist_gradient_boosting_classifier"
                or model_bundle.get("horizon_months") != horizon
            ):
                raise ClosurePhase3ContextError("B2 pipeline bundle drifted")
            bundled_preprocessor = model_bundle.get("preprocessor")
            if not isinstance(bundled_preprocessor, Mapping) or any(
                bundled_preprocessor.get(key) != preprocessor.get(key)
                for key in bundled_preprocessor
            ):
                raise ClosurePhase3ContextError("B2 bundled preprocessor drifted")
            model = model_bundle.get("model")
            if not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
                raise ClosurePhase3ContextError("B2 pipeline model drifted")
            probabilities = np.asarray(model.predict_proba(matrix), dtype="float64")
            classes = list(model.classes_)
            if 1 not in classes or probabilities.shape[0] != len(origins):
                raise ClosurePhase3ContextError("B2 classifier output drifted")
            raw[:, horizon - 1] = np.clip(probabilities[:, classes.index(1)], 0.0, 1.0)
        outputs[("B2", seed)] = {
            "bloom_raw": raw,
            "ordinal": raw.copy(),
            "valid": np.repeat(valid[:, None], 3, axis=1),
        }
    return outputs


def _load_m0_predictions(origins: pd.DataFrame) -> dict[tuple[str, int], dict[str, np.ndarray]]:
    raw = np.full((len(origins), 3), np.nan, dtype="float64")
    valid = np.zeros((len(origins), 3), dtype=bool)
    model = MIFALEDT2()
    if model.current_state() != (0.05, 0.35):
        raise ClosurePhase3ContextError("M0 initial state drifted")
    columns = tuple(origins.columns)
    for index, values in enumerate(origins.itertuples(index=False, name=None)):
        row = dict(zip(columns, values, strict=True))
        payload = panel_row_to_closure_mifal_payload(row)
        if not payload_is_eligible(payload):
            continue
        for horizon in HORIZONS:
            result = model.step(
                payload,
                dt_days=float(horizon) * 30.4375,
                assimilate=False,
                update_state=False,
                compute_voi=False,
            )
            fused = cast(Mapping[str, Any], result["fused"])
            if fused["Chl"].available or fused["Chl_prev"].available or result["observation_interval"] is not None:
                raise ClosurePhase3ContextError("M0 observed forbidden biological memory")
            score = float(cast(Any, result["risk_conservative"]))
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise ClosurePhase3ContextError("M0 score drifted")
            raw[index, horizon - 1] = score
            valid[index, horizon - 1] = True
    return {
        ("M0", RNG_SEED): {
            "bloom_raw": raw,
            "continuous": raw.copy(),
            "valid": valid,
        }
    }


def _score_models_before_targets(
    repo_root: Path,
    intents: pd.DataFrame,
    history: pd.DataFrame,
    origins: pd.DataFrame,
    arrays: Mapping[str, np.ndarray],
    warmup: pd.DataFrame,
) -> tuple[dict[tuple[str, int], dict[str, np.ndarray]], pd.DataFrame]:
    monthly = _deduplicated_month_surface(history, warmup)
    adaptive = _adaptive_states(arrays, monthly)
    a0, a0_valid, a1, a1_valid = _sequence_tensors(history, intents, adaptive)
    scored = _load_gru_predictions(repo_root, arrays, a0, a0_valid, a1, a1_valid)
    scored.update(_load_b2_predictions(repo_root, origins))
    scored.update(_load_m0_predictions(origins))
    f0 = _expert_no_chla_scores(origins)
    f0_valid = origins["row_present"].astype(bool).to_numpy()
    scored[("F0", RNG_SEED)] = {
        "continuous": np.repeat(f0[:, None], 3, axis=1),
        "valid": np.repeat(f0_valid[:, None], 3, axis=1),
    }
    for seed in REGISTERED_SEEDS:
        state = adaptive[seed]
        origin_state = origins.loc[:, ["source_id", "site_id", "origin_year_month"]].rename(
            columns={"origin_year_month": "year_month"}
        ).merge(
            state.loc[:, ["source_id", "site_id", "year_month", "row_present", "yN", "yF", "yT"]],
            on=["source_id", "site_id", "year_month"],
            how="left",
            validate="one_to_one",
            sort=False,
        )
        irc = np.clip(
            (
                origin_state["yN"].to_numpy(dtype="float64")
                + 1.0
                - origin_state["yF"].to_numpy(dtype="float64")
                + origin_state["yT"].to_numpy(dtype="float64")
            )
            / 3.0,
            0.0,
            1.0,
        )
        valid = (
            origins["row_present"].astype(bool).to_numpy()
            & origin_state["row_present"].fillna(False).astype(bool).to_numpy()
            & np.isfinite(irc)
        )
        surface = np.repeat(irc[:, None], 3, axis=1)
        applicability = np.repeat(valid[:, None], 3, axis=1)
        scored[("F1", seed)] = {"continuous": surface, "valid": applicability}
        scored[("B1", seed)] = {
            "bloom_raw": surface.copy(),
            "continuous": surface.copy(),
            "ordinal": surface.copy(),
            "valid": applicability,
        }
    prevalence = np.asarray(
        [0.3004045853000674, 0.30377612946729604, 0.3105192178017532],
        dtype="float64",
    )
    scored[("B0", RNG_SEED)] = {
        "bloom_raw": np.repeat(prevalence[None, :], len(intents), axis=0),
        "valid": np.ones((len(intents), 3), dtype=bool),
    }
    return scored, monthly


def _build_intent_table(base: pd.DataFrame) -> pd.DataFrame:
    repeated = base.loc[
        :, ["source_id", "site_id", "holdout_group_id", "origin_id", "origin_year_month"]
    ].loc[base.index.repeat(3)].reset_index(drop=True)
    repeated["horizon_months"] = np.tile(np.asarray(HORIZONS, dtype="int64"), len(base))
    repeated["target_year_month"] = _period_add(
        repeated["origin_year_month"], repeated["horizon_months"].to_numpy(dtype="int64")
    )
    repeated = repeated.rename(columns={"origin_id": "common_origin_id"})
    repeated["evaluation_cohort"] = "location_holdout"
    repeated["evaluation_role"] = "test"
    repeated["time_role"] = "post_2021_evaluation"
    out = repeated.loc[:, list(E1_INTENT_COLUMNS)]
    if (
        len(out) != 13464
        or out["common_origin_id"].nunique() != 4488
        or out[["source_id", "site_id"]].drop_duplicates().shape[0] != 88
        or out.duplicated(list(E1_INTENT_COLUMNS[:7])).any()
    ):
        raise ClosurePhase3ContextError("expanded intent denominator drifted")
    return out


def _factor_lookup(
    factors: pd.DataFrame, *, model_id: str, seed: int, horizon: int, coverage: float
) -> float:
    selected = factors.loc[
        factors["model_id"].astype(str).eq(model_id)
        & pd.to_numeric(factors["model_seed"], errors="coerce").eq(seed)
        & pd.to_numeric(factors["horizon_months"], errors="coerce").eq(horizon)
        & np.isclose(pd.to_numeric(factors["coverage_level"], errors="coerce"), coverage, rtol=0.0, atol=1e-12)
    ]
    if len(selected) != 1 or str(selected.iloc[0]["status"]) != "completed":
        raise ClosurePhase3ContextError("locked conformal q_c lookup drifted")
    value = float(selected.iloc[0]["q_c"])
    if not math.isfinite(value) or value <= 0.0:
        raise ClosurePhase3ContextError("locked conformal q_c is invalid")
    return value


def _prediction_rows_for_model(
    intents: pd.DataFrame,
    scored: Mapping[tuple[str, int], Mapping[str, np.ndarray]],
    calibrators: Mapping[tuple[str, int, int], Mapping[str, Any]],
    thresholds: Mapping[tuple[str, int, int], float],
    cutpoints: Mapping[tuple[str, int, int], tuple[float, float, float]],
    factors: pd.DataFrame,
    *,
    model_id: str,
    seed_slot: int,
) -> pd.DataFrame:
    model_seed = RNG_SEED if model_id in DETERMINISTIC_MODEL_IDS else seed_slot
    out = intents.loc[
        :, ["source_id", "site_id", "common_origin_id", "origin_year_month", "target_year_month", "horizon_months"]
    ].copy()
    out["model_id"] = model_id
    out["model_seed"] = model_seed
    out["seed_slot"] = seed_slot
    numeric_columns = (
        "bloom_probability", "alert_threshold", "predicted_value", "predicted_sigma",
        "predicted_lower", "predicted_upper", "continuous_score", "ordinal_score",
        "cutpoint_1", "cutpoint_2", "cutpoint_3",
    )
    for column in numeric_columns:
        out[column] = np.nan
    if model_id in ("P0", "P1"):
        out["terminal_status"] = "model_unavailable"
        for endpoint in ENDPOINTS:
            out[f"{endpoint}_status"] = "model_unavailable"
        return out.loc[:, list(E1_PREDICTION_COLUMNS)]
    payload = scored.get((model_id, model_seed))
    if not isinstance(payload, Mapping):
        raise ClosurePhase3ContextError(f"scored surface is absent: {model_id}:{model_seed}")
    valid_matrix = np.asarray(payload.get("valid"), dtype=bool)
    if valid_matrix.shape != (4488, 3):
        raise ClosurePhase3ContextError("scored model input status shape drifted")
    valid = valid_matrix.reshape(-1)
    for endpoint in ENDPOINTS:
        if ENDPOINT_AVAILABILITY[model_id][endpoint]:
            out[f"{endpoint}_status"] = np.where(valid, "success", "input_ineligible")
        else:
            out[f"{endpoint}_status"] = "not_applicable"
    out["terminal_status"] = np.where(valid, "success", "input_ineligible")
    if ENDPOINT_AVAILABILITY[model_id]["bloom"]:
        raw = np.asarray(payload["bloom_raw"], dtype="float64")
        if raw.shape != (4488, 3):
            raise ClosurePhase3ContextError("raw bloom surface shape drifted")
        probability = np.full(raw.shape, np.nan, dtype="float64")
        threshold_values = np.full(raw.shape, np.nan, dtype="float64")
        for horizon in HORIZONS:
            key = (model_id, model_seed, horizon)
            if key not in calibrators or key not in thresholds:
                raise ClosurePhase3ContextError(f"locked bloom calibration is absent: {key}")
            selected = valid_matrix[:, horizon - 1]
            if selected.any():
                probability[selected, horizon - 1] = _apply_calibrator(
                    raw[selected, horizon - 1], calibrators[key]
                )
                threshold_values[selected, horizon - 1] = float(thresholds[key])
        out["bloom_probability"] = probability.reshape(-1)
        out["alert_threshold"] = threshold_values.reshape(-1)
    if ENDPOINT_AVAILABILITY[model_id]["continuous"]:
        continuous = np.asarray(payload["continuous"], dtype="float64")
        if continuous.shape != (4488, 3):
            raise ClosurePhase3ContextError("continuous surface shape drifted")
        values = np.where(valid_matrix, continuous, np.nan)
        out["predicted_value"] = values.reshape(-1)
        out["continuous_score"] = values.reshape(-1)
    if ENDPOINT_AVAILABILITY[model_id]["uncertainty"]:
        sigma = np.asarray(payload["sigma"], dtype="float64")
        continuous = np.asarray(payload["continuous"], dtype="float64")
        if sigma.shape != (4488, 3) or continuous.shape != sigma.shape:
            raise ClosurePhase3ContextError("uncertainty surface shape drifted")
        lower = np.full(sigma.shape, np.nan, dtype="float64")
        upper = np.full(sigma.shape, np.nan, dtype="float64")
        sigma_out = np.where(valid_matrix, sigma, np.nan)
        for horizon in HORIZONS:
            selected = valid_matrix[:, horizon - 1]
            q_c = _factor_lookup(
                factors, model_id=model_id, seed=model_seed, horizon=horizon, coverage=0.90
            )
            lower[selected, horizon - 1] = continuous[selected, horizon - 1] - q_c * sigma[selected, horizon - 1]
            upper[selected, horizon - 1] = continuous[selected, horizon - 1] + q_c * sigma[selected, horizon - 1]
        out["predicted_sigma"] = sigma_out.reshape(-1)
        out["predicted_lower"] = lower.reshape(-1)
        out["predicted_upper"] = upper.reshape(-1)
    if ENDPOINT_AVAILABILITY[model_id]["ordinal"]:
        ordinal = np.asarray(payload["ordinal"], dtype="float64")
        if ordinal.shape != (4488, 3):
            raise ClosurePhase3ContextError("ordinal surface shape drifted")
        ordinal_out = np.where(valid_matrix, ordinal, np.nan)
        cp = [np.full(ordinal.shape, np.nan, dtype="float64") for _ in range(3)]
        for horizon in HORIZONS:
            key = (model_id, model_seed, horizon)
            if key not in cutpoints:
                raise ClosurePhase3ContextError(f"locked ordinal cutpoints are absent: {key}")
            selected = valid_matrix[:, horizon - 1]
            for index, value in enumerate(cutpoints[key]):
                cp[index][selected, horizon - 1] = value
        out["ordinal_score"] = ordinal_out.reshape(-1)
        out["cutpoint_1"] = cp[0].reshape(-1)
        out["cutpoint_2"] = cp[1].reshape(-1)
        out["cutpoint_3"] = cp[2].reshape(-1)
    return out.loc[:, list(E1_PREDICTION_COLUMNS)]


def _build_prediction_surface(
    intents: pd.DataFrame,
    scored: Mapping[tuple[str, int], Mapping[str, np.ndarray]],
    calibrators: Mapping[tuple[str, int, int], Mapping[str, Any]],
    thresholds: Mapping[tuple[str, int, int], float],
    cutpoints: Mapping[tuple[str, int, int], tuple[float, float, float]],
    factors: pd.DataFrame,
) -> pd.DataFrame:
    parts = [
        _prediction_rows_for_model(
            intents, scored, calibrators, thresholds, cutpoints, factors,
            model_id=model_id, seed_slot=seed,
        )
        for model_id in MODEL_IDS
        for seed in REGISTERED_SEEDS
    ]
    surface = pd.concat(parts, ignore_index=True)
    if len(surface) != 673200:
        raise ClosurePhase3ContextError("pre-target prediction denominator drifted")
    return surface.sort_values(
        ["source_id", "site_id", "origin_year_month", "horizon_months", "model_id", "seed_slot"],
        kind="mergesort",
    ).reset_index(drop=True)


def _open_target_outcomes(repo_root: Path, intents: pd.DataFrame) -> pd.DataFrame:
    columns = (
        "source_id", "site_id", "origin_year_month", "target_year_month", "horizon_months",
        "target_month_exists", "has_target", "future_chlorophyll_a_ugL", "bloom_h",
        "target_risk_chla_h", "target_trophic_state_h",
    )
    sites = sorted(intents["site_id"].astype(str).unique())
    target = _read_parquet_anchored(
        repo_root,
        TARGET_PATH,
        label="physical target table",
        expected_sha256=TARGET_SHA256,
        columns=columns,
        filters=[("source_id", "==", "wqp"), ("site_id", "in", sites)],
    )
    target["horizon_months"] = pd.to_numeric(target["horizon_months"], errors="raise").astype("int64")
    target = target.loc[target["horizon_months"].isin(HORIZONS)].copy()
    join_keys = ["source_id", "site_id", "origin_year_month", "target_year_month", "horizon_months"]
    if target.duplicated(join_keys).any():
        raise ClosurePhase3ContextError("physical target keys are duplicated")
    base = intents.loc[:, [*join_keys[:2], "common_origin_id", *join_keys[2:]]]
    merged = base.merge(target, on=join_keys, how="left", validate="one_to_one", sort=False)
    chla = pd.to_numeric(merged["future_chlorophyll_a_ugL"], errors="coerce")
    bloom = pd.to_numeric(merged["bloom_h"], errors="coerce")
    risk = pd.to_numeric(merged["target_risk_chla_h"], errors="coerce")
    trophic = merged["target_trophic_state_h"].astype("string").str.lower()
    valid = (
        merged["target_month_exists"].fillna(False).astype(bool)
        & merged["has_target"].fillna(False).astype(bool)
        & chla.notna() & np.isfinite(chla) & chla.ge(0.0)
        & bloom.isin([0.0, 1.0])
        & risk.notna() & np.isfinite(risk) & risk.between(0.0, 1.0)
        & trophic.isin(["oligotrophic", "mesotrophic", "eutrophic", "hypereutrophic"])
    )
    if not bloom.loc[valid].eq(chla.loc[valid].gt(30.0).astype(float)).all():
        raise ClosurePhase3ContextError("physical bloom label disagrees with Chl-a > 30")
    out = merged.loc[:, ["source_id", "site_id", "common_origin_id", "target_year_month", "horizon_months"]].copy()
    out["actual_bloom"] = bloom.where(valid)
    out["actual_value"] = risk.where(valid)
    out["actual_chla_ug_l"] = chla.where(valid)
    out["actual_trophic_state"] = trophic.where(valid, pd.NA)
    out["target_status"] = np.where(valid, "available", "target_unavailable")
    return out.loc[:, list(E1_TARGET_COLUMNS)]


def _apply_target_precedence(
    predictions: pd.DataFrame, targets: pd.DataFrame
) -> pd.DataFrame:
    target_keys = ["source_id", "site_id", "common_origin_id", "target_year_month", "horizon_months"]
    status = targets.loc[:, [*target_keys, "target_status"]]
    merged = predictions.merge(status, on=target_keys, how="left", validate="many_to_one", sort=False)
    if merged["target_status"].isna().any():
        raise ClosurePhase3ContextError("prediction target-status join is incomplete")
    missing = merged["target_status"].eq("target_unavailable") & ~merged["model_id"].isin(("P0", "P1"))
    numeric = [column for column in E1_PREDICTION_COLUMNS if column.startswith(("bloom_", "alert_", "predicted_", "continuous_", "ordinal_", "cutpoint_")) and not column.endswith("status")]
    merged.loc[missing, numeric] = np.nan
    for endpoint in ENDPOINTS:
        applicable = merged["model_id"].map(lambda model: ENDPOINT_AVAILABILITY[str(model)][endpoint])
        merged.loc[missing & applicable, f"{endpoint}_status"] = "target_unavailable"
    merged.loc[missing, "terminal_status"] = "target_unavailable"
    return merged.loc[:, list(E1_PREDICTION_COLUMNS)]


def _load_e2_site_strata(repo_root: Path, intents: pd.DataFrame) -> pd.DataFrame:
    assignment = _read_csv_anchored(
        repo_root,
        HOLDOUT_ASSIGNMENT_PATH,
        label="holdout assignment",
        keep_default_na=False,
        dtype=str,
    )
    expected_source_columns = (
        "source_id",
        "site_id",
        "holdout_group_id",
        "assignment_role",
        "stratum_id",
        "historical_bloom_presence",
        "precursor_coverage_fraction",
        "precursor_coverage_band",
        "series_length_months",
        "series_length_band",
        "deterministic_rank_sha256",
    )
    _require_exact_columns(
        assignment, expected_source_columns, label="holdout assignment"
    )
    assignment = assignment.loc[
        assignment["source_id"].eq("wqp")
        & assignment["assignment_role"].eq("internal_holdout")
    ].copy()
    expected_sites = set(
        map(
            tuple,
            intents[["source_id", "site_id", "holdout_group_id"]]
            .drop_duplicates()
            .itertuples(index=False, name=None),
        )
    )
    observed_sites = set(
        map(
            tuple,
            assignment[["source_id", "site_id", "holdout_group_id"]]
            .itertuples(index=False, name=None),
        )
    )
    if (
        len(assignment) != 88
        or assignment[["source_id", "site_id"]].duplicated().any()
        or observed_sites != expected_sites
        or not assignment["historical_bloom_presence"].str.lower().isin(
            ["true", "false"]
        ).all()
        or assignment[[
            "series_length_band",
            "precursor_coverage_band",
        ]].eq("").any().any()
    ):
        raise ClosurePhase3ContextError("E2 frozen site-strata universe drifted")
    out = assignment.loc[
        :,
        [
            "source_id",
            "site_id",
            "series_length_band",
            "historical_bloom_presence",
            "precursor_coverage_band",
        ],
    ].rename(
        columns={
            "historical_bloom_presence": "historical_bloom_present",
            "precursor_coverage_band": "coverage_band",
        }
    )
    out["historical_bloom_present"] = (
        out["historical_bloom_present"].str.lower()
    )
    return out.loc[:, list(E2_SITE_STRATA_COLUMNS)].sort_values(
        ["source_id", "site_id"], kind="mergesort"
    ).reset_index(drop=True)


def _load_hypothesis_registry(repo_root: Path) -> pd.DataFrame:
    registry = _read_csv_anchored(
        repo_root,
        HYPOTHESIS_REGISTRY_PATH,
        label="hypothesis registry",
        keep_default_na=False,
        dtype=str,
    )
    _require_exact_columns(registry, HYPOTHESIS_COLUMNS, label="hypothesis registry")
    counts = registry["multiplicity_family"].value_counts().to_dict()
    universes = {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}
    observed_universes = pd.to_numeric(
        registry["multiplicity_universe_size"], errors="raise"
    ).astype("int64")
    if (
        len(registry) != 27
        or registry["hypothesis_id"].duplicated().any()
        or counts != {"B": 13, "D": 9, "A": 3, "C": 1, "E": 1}
        or any(
            not observed_universes.loc[
                registry["multiplicity_family"].eq(family)
            ].eq(size).all()
            for family, size in universes.items()
        )
        or not registry["status"].eq(
            "not_estimable_model_unavailable"
        ).all()
        or not registry["holm_universe_retained"].str.lower().eq("true").all()
    ):
        raise ClosurePhase3ContextError("frozen confirmatory registry drifted")
    return registry.sort_values("hypothesis_id", kind="mergesort").reset_index(
        drop=True
    )


def _future_trophic_indicators(
    repo_root: Path,
    intents: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    sites = sorted(intents["site_id"].astype(str).unique())
    panel = _read_parquet_anchored(
        repo_root,
        PANEL_PATH,
        label="physical monthly panel",
        columns=[
            "source_id",
            "site_id",
            "year_month",
            "mean_TP_ugL",
            "mean_secchi_depth_m",
        ],
        expected_sha256=PANEL_SHA256,
        filters=[("source_id", "==", "wqp"), ("site_id", "in", sites)],
    )
    if panel.duplicated(["source_id", "site_id", "year_month"]).any():
        raise ClosurePhase3ContextError("physical panel month keys are duplicated")
    panel = panel.rename(
        columns={
            "year_month": "target_year_month",
            "mean_TP_ugL": "future_TP_ugL",
            "mean_secchi_depth_m": "future_secchi_depth_m",
        }
    )
    identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "evaluation_cohort",
        "evaluation_role",
    ]
    out = intents.loc[:, identity].merge(
        panel,
        on=["source_id", "site_id", "target_year_month"],
        how="left",
        validate="many_to_one",
        sort=False,
    )
    target_keys = [
        "source_id",
        "site_id",
        "common_origin_id",
        "target_year_month",
        "horizon_months",
    ]
    out = out.merge(
        targets.loc[:, [*target_keys, "actual_chla_ug_l"]],
        on=target_keys,
        how="left",
        validate="one_to_one",
        sort=False,
    ).rename(columns={"actual_chla_ug_l": "future_chlorophyll_a_ugL"})
    for column in (
        "future_TP_ugL",
        "future_secchi_depth_m",
        "future_chlorophyll_a_ugL",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if (
        len(out) != len(intents)
        or out.duplicated(identity).any()
        or not out["source_id"].eq("wqp").all()
        or not out["evaluation_cohort"].eq("location_holdout").all()
        or not out["evaluation_role"].eq("test").all()
    ):
        raise ClosurePhase3ContextError("E4 future-indicator universe drifted")
    return out.loc[:, list(FUTURE_TROPHIC_COLUMNS)].sort_values(
        identity, kind="mergesort"
    ).reset_index(drop=True)


def _merge_intents_and_targets(
    predictions: pd.DataFrame,
    intents: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    intent_keys = [
        "source_id",
        "site_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    ]
    target_keys = [
        "source_id",
        "site_id",
        "common_origin_id",
        "target_year_month",
        "horizon_months",
    ]
    merged = predictions.merge(
        intents,
        on=intent_keys,
        how="left",
        validate="many_to_one",
        sort=False,
    ).merge(
        targets,
        on=target_keys,
        how="left",
        validate="many_to_one",
        sort=False,
    )
    if merged[["evaluation_cohort", "evaluation_role", "target_status"]].isna().any().any():
        raise ClosurePhase3ContextError("derived evaluation join is incomplete")
    return merged


def _derive_e7_predictions(
    predictions: pd.DataFrame,
    intents: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    merged = _merge_intents_and_targets(
        predictions.loc[predictions["model_id"].isin(("A0", "P0", "P1", "A1"))].copy(),
        intents,
        targets,
    )
    out = pd.DataFrame(
        {
            "model_id": merged["model_id"].astype(str),
            "seed": merged["model_seed"].astype("int64"),
            "source_id": merged["source_id"].astype(str),
            "site_id": merged["site_id"].astype(str),
            "common_origin_id": merged["common_origin_id"].astype(str),
            "evaluation_cohort": merged["evaluation_cohort"].astype(str),
            "evaluation_role": merged["evaluation_role"].astype(str),
            "horizon_months": merged["horizon_months"].astype("int64"),
            "target_year_month": merged["target_year_month"].astype(str),
            "status": merged["bloom_status"].astype(str),
            "y_true": pd.to_numeric(merged["actual_bloom"], errors="coerce"),
            "y_prob": pd.to_numeric(merged["bloom_probability"], errors="coerce"),
        }
    )
    out.loc[~out["status"].eq("success"), "y_prob"] = np.nan
    if len(out) != 269280:
        raise ClosurePhase3ContextError("E7 prediction denominator drifted")
    return out.loc[:, list(E7_PREDICTION_COLUMNS)].sort_values(
        [
            "model_id",
            "seed",
            "source_id",
            "site_id",
            "common_origin_id",
            "horizon_months",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _derive_e8_evaluation(
    predictions: pd.DataFrame,
    intents: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    merged = _merge_intents_and_targets(
        predictions.loc[predictions["model_id"].isin(("A0", "A1"))].copy(),
        intents,
        targets,
    )
    out = pd.DataFrame(
        {
            "source_id": merged["source_id"].astype(str),
            "site_id": merged["site_id"].astype(str),
            "holdout_group_id": merged["holdout_group_id"].astype(str),
            "common_origin_id": merged["common_origin_id"].astype(str),
            "origin_year_month": merged["origin_year_month"].astype(str),
            "target_year_month": merged["target_year_month"].astype(str),
            "horizon_months": merged["horizon_months"].astype("int64"),
            "evaluation_cohort": merged["evaluation_cohort"].astype(str),
            "evaluation_role": merged["evaluation_role"].astype(str),
            "model_id": merged["model_id"].astype(str),
            "model_seed": merged["model_seed"].astype("int64"),
            "seed_slot": merged["seed_slot"].astype("int64"),
            "status": merged["uncertainty_status"].astype(str),
            "y_true": pd.to_numeric(merged["actual_value"], errors="coerce"),
            "prediction": pd.to_numeric(merged["predicted_value"], errors="coerce"),
            "sigma": pd.to_numeric(merged["predicted_sigma"], errors="coerce"),
        }
    )
    not_success = ~out["status"].eq("success")
    out.loc[not_success, ["prediction", "sigma"]] = np.nan
    if len(out) != 134640:
        raise ClosurePhase3ContextError("E8 evaluation denominator drifted")
    return out.loc[:, list(E8_EVALUATION_COLUMNS)].sort_values(
        [
            "source_id",
            "site_id",
            "common_origin_id",
            "horizon_months",
            "model_id",
            "seed_slot",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _materialize_pretarget_context(
    *,
    authority: Mapping[str, Any],
    repo_root: Path,
    require_git_publication: bool,
) -> dict[str, Any]:
    """Authenticate and score every input-only Phase 3 dependency."""

    base_intents, history, origins = _load_input_frames(repo_root)
    arrays, warmup, overlay_record, warmup_summary = _load_overlay(repo_root)
    _validate_warmup_against_history(warmup, history, warmup_summary)
    calibrators, thresholds, cutpoints, factors = _load_calibration(repo_root)
    e2_site_strata = _load_e2_site_strata(repo_root, base_intents)
    hypothesis_registry = _load_hypothesis_registry(repo_root)
    software_evidence = _load_e10_source_evidence(
        repo_root=repo_root,
        authority=authority,
        require_git_publication=require_git_publication,
    )
    scored, monthly = _score_models_before_targets(
        repo_root,
        base_intents,
        history,
        origins,
        arrays,
        warmup,
    )
    intents = _build_intent_table(base_intents)
    prediction_surface = _build_prediction_surface(
        intents,
        scored,
        calibrators,
        thresholds,
        cutpoints,
        factors,
    )
    return {
        "base_intents": base_intents,
        "history": history,
        "origins": origins,
        "arrays": arrays,
        "warmup": warmup,
        "phase3_overlay_record": overlay_record,
        "calibrators": calibrators,
        "thresholds": thresholds,
        "cutpoints": cutpoints,
        "factors": factors,
        "e2_site_strata": e2_site_strata,
        "hypothesis_registry": hypothesis_registry,
        "software_evidence": software_evidence,
        "scored": scored,
        "monthly": monthly,
        "intents": intents,
        "prediction_surface": prediction_surface,
    }


def _closed_input_snapshot(
    records: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, int, str], ...]:
    snapshot = tuple(
        sorted(
            (
                cast(str, record["path"]),
                cast(int, record["bytes"]),
                cast(str, record["sha256"]),
            )
            for record in records
        )
    )
    if any(
        type(path) is not str
        or not path
        or type(byte_count) is not int
        or byte_count < 0
        or type(digest) is not str
        or len(digest) != 64
        for path, byte_count, digest in snapshot
    ):
        raise ClosurePhase3ContextError("anchored input snapshot is malformed")
    return snapshot


def _input_snapshot_sha256(
    snapshot: Sequence[tuple[str, int, str]],
) -> str:
    payload = [
        {"path": path, "bytes": byte_count, "sha256": digest}
        for path, byte_count, digest in snapshot
    ]
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def preflight_sealed_phase3_context_inputs(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Validate and score sealed Phase 3 inputs without outcomes or writes.

    The returned diagnosis is deliberately not a reusable capability.  After
    the durable one-shot access append, the materializer reopens, rehashes, and
    decodes all of these inputs through fresh anchored descriptors before it
    opens either the target table or the monthly panel.
    """

    global _ACTIVE_ANCHORED_INPUT_RECORDS
    global _PREFLIGHT_ANCHORED_INPUT_RECORDS

    root = Path(repo_root).resolve(strict=True)
    _validate_boundary(
        authority,
        sealed_batch_contract,
        "sealed-phase3-context-input-preflight",
    )
    if (
        _ACTIVE_ANCHORED_INPUT_RECORDS is not None
        or _PREFLIGHT_ANCHORED_INPUT_RECORDS is not None
    ):
        raise ClosurePhase3ContextError(
            "sealed Phase 3 context input preflight is not one-shot"
        )
    _ACTIVE_ANCHORED_INPUT_RECORDS = []
    try:
        prepared = _materialize_pretarget_context(
            authority=authority,
            repo_root=root,
            require_git_publication=True,
        )
        captured = tuple(_ACTIVE_ANCHORED_INPUT_RECORDS)
    finally:
        _ACTIVE_ANCHORED_INPUT_RECORDS = None
    input_snapshot = _closed_input_snapshot(captured)
    _PREFLIGHT_ANCHORED_INPUT_RECORDS = input_snapshot
    base_intents = cast(pd.DataFrame, prepared["base_intents"])
    history = cast(pd.DataFrame, prepared["history"])
    origins = cast(pd.DataFrame, prepared["origins"])
    arrays = cast(Mapping[str, np.ndarray], prepared["arrays"])
    warmup = cast(pd.DataFrame, prepared["warmup"])
    calibrators = cast(Mapping[Any, Any], prepared["calibrators"])
    thresholds = cast(Mapping[Any, Any], prepared["thresholds"])
    cutpoints = cast(Mapping[Any, Any], prepared["cutpoints"])
    factors = cast(pd.DataFrame, prepared["factors"])
    strata = cast(pd.DataFrame, prepared["e2_site_strata"])
    hypotheses = cast(pd.DataFrame, prepared["hypothesis_registry"])
    evidence = cast(Mapping[str, Any], prepared["software_evidence"])
    scored = cast(Mapping[Any, Any], prepared["scored"])
    intents = cast(pd.DataFrame, prepared["intents"])
    predictions = cast(pd.DataFrame, prepared["prediction_surface"])
    overlay_record = cast(Mapping[str, Any], prepared["phase3_overlay_record"])
    return {
        "status": "sealed_phase3_context_inputs_ready",
        "gate": "E0-U",
        "input_only": True,
        "outcome_access_performed": False,
        "writes_performed": False,
        "refit_performed": False,
        "snapshot_reuse_authorized": False,
        "post_append_revalidation_required": True,
        "anchored_input_read_count": len(input_snapshot),
        "input_snapshot_sha256": _input_snapshot_sha256(input_snapshot),
        "phase3_overlay_record": {
            "manifest": dict(cast(Mapping[str, Any], overlay_record["manifest"])),
            "physical_outputs": [
                dict(cast(Mapping[str, Any], record))
                for record in cast(Sequence[Any], overlay_record["physical_outputs"])
            ],
        },
        "holdout_site_count": int(
            base_intents[["source_id", "site_id"]].drop_duplicates().shape[0]
        ),
        "origin_count": len(base_intents),
        "history_row_count": len(history),
        "origin_feature_row_count": len(origins),
        "eligible_origin_count": int(base_intents["base_input_status"].eq("eligible").sum()),
        "ineligible_origin_count": int(base_intents["base_input_status"].eq("ineligible").sum()),
        "expanded_intent_count": len(intents),
        "pretarget_prediction_count": len(predictions),
        "overlay_array_count": len(arrays),
        "warmup_site_count": len(warmup),
        "calibrator_count": len(calibrators),
        "threshold_count": len(thresholds),
        "cutpoint_count": len(cutpoints),
        "conformal_factor_count": len(factors),
        "site_strata_count": len(strata),
        "hypothesis_count": len(hypotheses),
        "software_evidence_artifact_count": len(evidence),
        "scored_model_slot_count": len(scored),
        "registered_seed_count": len(REGISTERED_SEEDS),
        "outcome_bearing_paths_opened": [],
    }


def materialize_sealed_batch_context(
    *,
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
    execution_id: str,
) -> dict[str, Any]:
    """Build the exact E1--E10 in-memory context after durable E0-U logging."""

    global _ACTIVE_ANCHORED_INPUT_RECORDS
    global _PREFLIGHT_ANCHORED_INPUT_RECORDS

    root = Path(repo_root).resolve(strict=True)
    _validate_boundary(authority, sealed_batch_contract, execution_id)

    # Repeat the complete input-only preflight after the durable append.  This
    # deliberately trades duplicate scoring for fresh anchored authentication;
    # no pre-append object or namespace snapshot is trusted across the boundary.
    expected_input_snapshot = _PREFLIGHT_ANCHORED_INPUT_RECORDS
    _PREFLIGHT_ANCHORED_INPUT_RECORDS = None
    if expected_input_snapshot is None or _ACTIVE_ANCHORED_INPUT_RECORDS is not None:
        raise ClosurePhase3ContextError(
            "successful sealed Phase 3 context input preflight is required"
        )
    _ACTIVE_ANCHORED_INPUT_RECORDS = []
    try:
        prepared = _materialize_pretarget_context(
            authority=authority,
            repo_root=root,
            require_git_publication=False,
        )
        observed_input_records = tuple(_ACTIVE_ANCHORED_INPUT_RECORDS)
    finally:
        _ACTIVE_ANCHORED_INPUT_RECORDS = None
    observed_input_snapshot = _closed_input_snapshot(observed_input_records)
    if observed_input_snapshot != expected_input_snapshot:
        raise ClosurePhase3ContextError(
            "sealed Phase 3 inputs changed across the durable outcome log"
        )
    intents = cast(pd.DataFrame, prepared["intents"])
    prediction_surface = cast(pd.DataFrame, prepared["prediction_surface"])
    factors = cast(pd.DataFrame, prepared["factors"])
    e2_site_strata = cast(pd.DataFrame, prepared["e2_site_strata"])
    hypothesis_registry = cast(pd.DataFrame, prepared["hypothesis_registry"])
    software_evidence = cast(Mapping[str, Any], prepared["software_evidence"])

    # This is the first outcome-bearing read in the context builder.  The
    # authority has already appended and fsynced the one-shot access record.
    targets = _open_target_outcomes(root, intents)
    predictions = _apply_target_precedence(prediction_surface, targets)
    future_indicators = _future_trophic_indicators(root, intents, targets)
    e7_predictions = _derive_e7_predictions(predictions, intents, targets)
    uncertainty_evaluation = _derive_e8_evaluation(
        predictions, intents, targets
    )
    tables = {
        "predictions_long": predictions,
        "intent_origins": intents,
        "target_outcomes": targets,
        "e2_site_strata": e2_site_strata,
        "future_trophic_indicators": future_indicators,
        "hypothesis_registry": hypothesis_registry,
        "e7_predictions": e7_predictions,
        "locked_conformal_factors": factors,
        "uncertainty_evaluation": uncertainty_evaluation,
    }
    if set(tables) != EXPECTED_CONTEXT_TABLES or any(
        type(frame) is not pd.DataFrame for frame in tables.values()
    ):
        raise ClosurePhase3ContextError("materialized context table scope drifted")
    return {
        "execution_id": execution_id,
        "rng_seed": RNG_SEED,
        "tables": tables,
        "stage_results": {},
        "model_availability": dict(MODEL_AVAILABILITY),
        "software_evidence": software_evidence,
    }


__all__ = [
    "ClosurePhase3ContextError",
    "EXPECTED_CONTEXT_TABLES",
    "materialize_sealed_batch_context",
    "preflight_sealed_phase3_context_inputs",
]
