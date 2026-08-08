#!/usr/bin/env python
"""Build the input-only Closure V1 A0/A1 ANFIS-ablation tensors.

The builder deliberately has no target projection.  It serializes one retained
row per common origin, using the twelve calendar months ending at the origin.
The command-line entry point is fail-closed behind the published E0-MS
authority before it resolves output paths or opens any scientific artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.experiments.closure_runtime_contract import closure_seasonality


SEQUENCE_VERSION = "closure_anfis_ablation_input_sequence_v1"
MANIFEST_VERSION = "closure_anfis_ablation_sequence_manifest_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
HISTORY_LENGTH = 12
HORIZONS = (1, 2, 3)
MODEL_IDS = ("A0", "A1")
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
BUNDLE_SLOTS = (("A0", None), *(("A1", seed) for seed in REGISTERED_SEEDS))
EXPECTED_INTENT_ORIGINS = 9_732
EXPECTED_COMMON_ROWS = 29_196
EXPECTED_DEVELOPMENT_LOCATIONS = 353
EXPECTED_ROLE_COUNTS = {
    "training": 8_352,
    "model_selection": 1_061,
    "calibration_threshold": 319,
}

# E6 is the ordering authority.  Do not substitute the B2 feature order.
RAW_MEAN_COLUMNS = (
    "mean_TP_ugL",
    "mean_TN_ugL",
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
    "mean_temperature_C",
)
RAW_N_OBS_COLUMNS = (
    "n_obs_TP_ugL",
    "n_obs_TN_ugL",
    "n_obs_DO_mgL",
    "n_obs_pH",
    "n_obs_turbidity_NTU",
    "n_obs_secchi_depth_m",
    "n_obs_temperature_C",
)
RAW_VALUE_COLUMNS = tuple(f"x_{column}" for column in RAW_MEAN_COLUMNS)
RAW_MASK_COLUMNS = tuple(f"mask_{column}" for column in RAW_MEAN_COLUMNS)
SEASON_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
ADAPTIVE_STATE_SOURCE_MAPPING = {
    "x_yN": "yN_adaptive",
    "x_yF": "yF_adaptive",
    "x_yT": "yT_no_chla_adaptive",
    "x_sigma_N": "sigma_N_adaptive",
    "x_sigma_F": "sigma_F_adaptive",
    "x_sigma_T": "sigma_T_no_chla_adaptive",
    "x_delta_yN": "delta_yN_adaptive",
    "x_delta_yF": "delta_yF_adaptive",
    "x_delta_yT": "delta_yT_no_chla_adaptive",
}
ADAPTIVE_STATE_COLUMNS = tuple(ADAPTIVE_STATE_SOURCE_MAPPING)
A0_INPUT_COLUMNS = RAW_VALUE_COLUMNS + RAW_MASK_COLUMNS + SEASON_COLUMNS
A1_INPUT_COLUMNS = A0_INPUT_COLUMNS + ADAPTIVE_STATE_COLUMNS

IDENTITY_COLUMNS = (
    "sequence_version",
    "surface_id",
    "model_id",
    "base_seed",
    "upstream_state_seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
    "sequence_status",
    "failure_reason",
)
ROW_STATUS_VALUES = (
    "success",
    "input_history_unavailable",
    "model_slot_unavailable",
)
COMMON_REQUIRED_COLUMNS = (
    "surface_id",
    "source_id",
    "site_id",
    "common_origin_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
    "horizon_months",
)
COMMON_ORIGIN_INVARIANTS = (
    "surface_id",
    "source_id",
    "site_id",
    "common_origin_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
)
PANEL_REQUIRED_COLUMNS = (
    "source_id",
    "site_id",
    "year_month",
    *RAW_MEAN_COLUMNS,
    *RAW_N_OBS_COLUMNS,
)
STATE_REQUIRED_COLUMNS = (
    "source_id",
    "site_id",
    "year_month",
    *ADAPTIVE_STATE_SOURCE_MAPPING.values(),
)

DEFAULT_COMMON_ORIGINS = Path("data/closure_v1/common_origin_manifest.parquet")
DEFAULT_COMMON_POINTER = Path("data/closure_v1/common_origin_manifest.parquet.dvc")
DEFAULT_COMMON_MANIFEST = Path("reports/closure_v1/01_surface/common_origin_manifest.json")
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_PANEL_POINTER = Path("data/panel/panel_monthly_v0.parquet.dvc")
DEFAULT_RUNTIME = Path("configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml")
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")


class AnfisAblationSequenceBuildError(ValueError):
    """Raised when an A0/A1 input-only bundle cannot be certified."""


@dataclass(frozen=True)
class SequenceBuildAudit:
    common_rows: int
    intent_origins: int
    development_locations: int
    source_ids: list[str]
    successful_origins: int
    failed_origins: int
    role_counts: dict[str, int]
    status_counts: dict[str, int]
    failure_reason_counts: dict[str, int]
    observed_raw_value_counts: dict[str, int]
    masked_raw_value_counts: dict[str, int]


@dataclass(frozen=True)
class BundlePaths:
    parquet: Path
    summary: Path
    manifest: Path
    pointer: Path
    guard: Path

    @property
    def finals(self) -> tuple[Path, Path, Path]:
        return (self.parquet, self.summary, self.manifest)


@dataclass(frozen=True)
class OwnedOutput:
    path: Path
    device: int
    inode: int
    bytes: int
    sha256: str
    directory_descriptor: int


@dataclass(frozen=True)
class OwnedGuard:
    path: Path
    device: int
    inode: int
    file_descriptor: int
    directory_descriptor: int


def input_columns(model_id: str) -> tuple[str, ...]:
    if model_id == "A0":
        return A0_INPUT_COLUMNS
    if model_id == "A1":
        return A1_INPUT_COLUMNS
    raise AnfisAblationSequenceBuildError(f"Unknown ANFIS-ablation model: {model_id!r}")


def validate_model_seed(model_id: str, base_seed: int | None) -> None:
    if model_id not in MODEL_IDS:
        raise AnfisAblationSequenceBuildError(f"Unregistered model_id: {model_id!r}")
    if model_id == "A0":
        if base_seed is not None:
            raise AnfisAblationSequenceBuildError("A0 is shared and must not carry a seed")
        return
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise AnfisAblationSequenceBuildError(f"Unregistered A1 seed: {base_seed!r}")


def _canonical_month(value: Any, *, label: str) -> pd.Period:
    if not isinstance(value, str) or len(value) != 7:
        raise AnfisAblationSequenceBuildError(f"{label} is not canonical YYYY-MM")
    try:
        period = pd.Period(value, freq="M")
    except (TypeError, ValueError) as exc:
        raise AnfisAblationSequenceBuildError(f"{label} is not canonical YYYY-MM") from exc
    if not isinstance(period, pd.Period) or str(period) != value:
        raise AnfisAblationSequenceBuildError(f"{label} is not canonical YYYY-MM")
    return period


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], *, label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise AnfisAblationSequenceBuildError(f"{label} is missing columns: {missing}")


def collapse_common_origins(common: pd.DataFrame) -> pd.DataFrame:
    """Collapse the 3-horizon common table to one input-only origin row."""

    _require_columns(common, COMMON_REQUIRED_COLUMNS, label="common-origin table")
    frame = common.loc[:, COMMON_REQUIRED_COLUMNS].copy()
    if frame[list(COMMON_REQUIRED_COLUMNS)].isna().any().any():
        raise AnfisAblationSequenceBuildError("Common-origin identity/geometry contains nulls")
    frame["horizon_months"] = pd.to_numeric(frame["horizon_months"], errors="raise").astype("int64")
    if frame.duplicated(["common_origin_id", "horizon_months"]).any():
        raise AnfisAblationSequenceBuildError("Common-origin horizon keys are duplicated")

    rows: list[pd.Series] = []
    for common_origin_id, group in frame.groupby("common_origin_id", sort=False, dropna=False):
        if len(group) != 3 or set(group["horizon_months"].tolist()) != set(HORIZONS):
            raise AnfisAblationSequenceBuildError(
                f"Common origin {common_origin_id!r} does not have exact h1-h3 geometry"
            )
        for column in COMMON_ORIGIN_INVARIANTS:
            if group[column].nunique(dropna=False) != 1:
                raise AnfisAblationSequenceBuildError(
                    f"Common origin {common_origin_id!r} drifts across horizons: {column}"
                )
        row = group.loc[group["horizon_months"].eq(1)].iloc[0].copy()
        origin = _canonical_month(row["origin_year_month"], label="origin_year_month")
        start = _canonical_month(row["history_start_year_month"], label="history_start_year_month")
        end = _canonical_month(row["history_end_year_month"], label="history_end_year_month")
        if start != origin - 11 or end != origin or int(row["history_length_months"]) != HISTORY_LENGTH:
            raise AnfisAblationSequenceBuildError("Common-origin 12-month history geometry drifted")
        rows.append(row.loc[list(COMMON_ORIGIN_INVARIANTS)])

    out = pd.DataFrame(rows, columns=COMMON_ORIGIN_INVARIANTS)
    if out["common_origin_id"].duplicated().any():
        raise AnfisAblationSequenceBuildError("Collapsed common-origin identifiers are duplicated")
    if set(out["surface_id"].astype(str)) != {SURFACE_ID}:
        raise AnfisAblationSequenceBuildError("Common-origin surface drifted")
    if set(out["assignment_role"].astype(str)) != {"development"}:
        raise AnfisAblationSequenceBuildError("Common-origin assignment is not development-only")
    if not set(out["time_role"].astype(str)).issubset(EXPECTED_ROLE_COUNTS):
        raise AnfisAblationSequenceBuildError("Common-origin temporal role drifted")
    return out.reset_index(drop=True)


def _canonical_order(frame: pd.DataFrame) -> list[int]:
    keys = ("source_id", "site_id", "origin_year_month", "common_origin_id")
    return sorted(
        range(len(frame)),
        key=lambda index: tuple(str(frame.iloc[index][column]).encode("utf-8") for column in keys),
    )


def _indexed_frame(frame: pd.DataFrame, required: Sequence[str], *, label: str) -> pd.DataFrame:
    _require_columns(frame, required, label=label)
    out = frame.loc[:, required].copy()
    for column in ("source_id", "site_id", "year_month"):
        if out[column].isna().any():
            raise AnfisAblationSequenceBuildError(f"{label} contains null key values")
        out[column] = out[column].astype(str)
    key = ["source_id", "site_id", "year_month"]
    if out.duplicated(key).any():
        raise AnfisAblationSequenceBuildError(f"{label} contains duplicate site-month keys")
    indexed = out.set_index(key)
    if not indexed.index.is_unique:
        raise AnfisAblationSequenceBuildError(f"{label} contains duplicate site-month keys")
    return indexed.sort_index()


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_anfis_ablation_sequences(
    common: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    model_id: str,
    base_seed: int | None,
    adaptive_state: pd.DataFrame | None = None,
    expected_common_rows: int | None = None,
    expected_intent_origins: int | None = None,
    expected_development_locations: int | None = None,
    expected_source_ids: set[str] | None = None,
    expected_role_counts: Mapping[str, int] | None = None,
) -> tuple[pd.DataFrame, SequenceBuildAudit]:
    """Build one retained input-only row per exact common origin."""

    validate_model_seed(model_id, base_seed)
    if expected_common_rows is not None and len(common) != expected_common_rows:
        raise AnfisAblationSequenceBuildError("Common-origin row denominator drifted")
    origins = collapse_common_origins(common)
    if expected_intent_origins is not None and len(origins) != expected_intent_origins:
        raise AnfisAblationSequenceBuildError("Common-origin denominator drifted")
    roles = {str(key): int(value) for key, value in origins["time_role"].value_counts().items()}
    if expected_role_counts is not None and roles != dict(expected_role_counts):
        raise AnfisAblationSequenceBuildError("Common-origin role denominators drifted")
    source_ids = sorted(set(origins["source_id"].astype(str)))
    if expected_source_ids is not None and set(source_ids) != set(expected_source_ids):
        raise AnfisAblationSequenceBuildError("Common-origin source denominator drifted")
    development_locations = int(
        origins[["source_id", "site_id"]].drop_duplicates().shape[0]
    )
    if (
        expected_development_locations is not None
        and development_locations != expected_development_locations
    ):
        raise AnfisAblationSequenceBuildError("Development-location denominator drifted")

    indexed_panel = _indexed_frame(panel, PANEL_REQUIRED_COLUMNS, label="panel")
    indexed_state: pd.DataFrame | None = None
    if model_id == "A1" and adaptive_state is not None:
        indexed_state = _indexed_frame(adaptive_state, STATE_REQUIRED_COLUMNS, label="adaptive state")

    tensor_columns = input_columns(model_id)
    observed_counts = {column: 0 for column in RAW_MEAN_COLUMNS}
    masked_counts = {column: 0 for column in RAW_MEAN_COLUMNS}
    output_rows: list[dict[str, Any]] = []

    origin_records = [
        {str(key): value for key, value in record.items()}
        for record in origins.to_dict(orient="records")
    ]
    for origin_row in origin_records:
        origin = _canonical_month(origin_row["origin_year_month"], label="origin_year_month")
        months = [str(origin - offset) for offset in range(11, -1, -1)]
        keys = [
            (str(origin_row["source_id"]), str(origin_row["site_id"]), month)
            for month in months
        ]
        status = "success"
        reason = ""
        tensors: dict[str, list[np.float32] | None] = {column: None for column in tensor_columns}
        state_tensors: dict[str, list[np.float32]] = {}

        missing_panel = [key for key in keys if key not in indexed_panel.index]
        if missing_panel:
            status = "input_history_unavailable"
            reason = "missing_panel_history_month"
        elif model_id == "A1":
            state_index = indexed_state
            if state_index is None:
                status = "model_slot_unavailable"
                reason = "adaptive_state_slot_unavailable"
            elif any(key not in state_index.index for key in keys):
                status = "model_slot_unavailable"
                reason = "missing_adaptive_state_history_month"
            else:
                state_history = state_index.loc[keys]
                for output_column, source_column in ADAPTIVE_STATE_SOURCE_MAPPING.items():
                    state_values = [
                        _finite_number(value)
                        for value in state_history[source_column].tolist()
                    ]
                    if any(value is None for value in state_values):
                        status = "model_slot_unavailable"
                        reason = "invalid_adaptive_state_history"
                        break
                    state_tensors[output_column] = [
                        np.float32(value) for value in state_values if value is not None
                    ]

        if status == "success":
            history = indexed_panel.loc[keys]
            for mean_column, n_obs_column, value_column, mask_column in zip(
                RAW_MEAN_COLUMNS,
                RAW_N_OBS_COLUMNS,
                RAW_VALUE_COLUMNS,
                RAW_MASK_COLUMNS,
                strict=True,
            ):
                values: list[np.float32] = []
                masks: list[np.float32] = []
                for mean_value, n_obs_value in zip(
                    history[mean_column].tolist(), history[n_obs_column].tolist(), strict=True
                ):
                    mean_number = _finite_number(mean_value)
                    n_obs_number = _finite_number(n_obs_value)
                    observed = mean_number is not None and n_obs_number is not None and n_obs_number > 0.0
                    values.append(np.float32(mean_number if observed else 0.0))
                    masks.append(np.float32(1.0 if observed else 0.0))
                    if observed:
                        observed_counts[mean_column] += 1
                    else:
                        masked_counts[mean_column] += 1
                tensors[value_column] = values
                tensors[mask_column] = masks

            seasonal: dict[str, list[np.float32]] = {column: [] for column in SEASON_COLUMNS}
            for month in months:
                calendar_month = int(_canonical_month(month, label="history month").month)
                season_values = closure_seasonality(calendar_month)
                for column in SEASON_COLUMNS:
                    seasonal[column].append(np.float32(season_values[column]))
            tensors.update(seasonal)

            if model_id == "A1":
                tensors.update(state_tensors)

        output_rows.append(
            {
                "sequence_version": SEQUENCE_VERSION,
                "surface_id": SURFACE_ID,
                "model_id": model_id,
                "base_seed": base_seed if model_id == "A1" else None,
                "upstream_state_seed": base_seed if model_id == "A1" else None,
                "source_id": str(origin_row["source_id"]),
                "site_id": str(origin_row["site_id"]),
                "common_origin_id": str(origin_row["common_origin_id"]),
                "holdout_group_id": str(origin_row["holdout_group_id"]),
                "assignment_role": str(origin_row["assignment_role"]),
                "time_role": str(origin_row["time_role"]),
                "origin_year_month": str(origin_row["origin_year_month"]),
                "history_start_year_month": str(origin_row["history_start_year_month"]),
                "history_end_year_month": str(origin_row["history_end_year_month"]),
                "history_length_months": HISTORY_LENGTH,
                "sequence_status": status,
                "failure_reason": reason,
                **tensors,
            }
        )

    columns = list(IDENTITY_COLUMNS + tensor_columns)
    output = pd.DataFrame(output_rows, columns=columns)
    output = output.iloc[_canonical_order(output)].reset_index(drop=True)
    if output.duplicated(["common_origin_id"]).any():
        raise AnfisAblationSequenceBuildError("Output contains duplicate common origins")
    if not set(output["sequence_status"]).issubset(ROW_STATUS_VALUES):
        raise AnfisAblationSequenceBuildError("Output row status drifted")
    success = output["sequence_status"].eq("success")
    for column in tensor_columns:
        if output.loc[success, column].isna().any() or output.loc[~success, column].notna().any():
            raise AnfisAblationSequenceBuildError("Tensor null-parent policy drifted")
    status_counts = {
        str(key): int(value) for key, value in output["sequence_status"].value_counts().items()
    }
    failure_counts = {
        str(key): int(value)
        for key, value in output.loc[~success, "failure_reason"].value_counts().items()
    }
    audit = SequenceBuildAudit(
        common_rows=len(common),
        intent_origins=len(output),
        development_locations=development_locations,
        source_ids=source_ids,
        successful_origins=int(success.sum()),
        failed_origins=int((~success).sum()),
        role_counts=roles,
        status_counts=status_counts,
        failure_reason_counts=failure_counts,
        observed_raw_value_counts=observed_counts,
        masked_raw_value_counts=masked_counts,
    )
    return output, audit


def _fixed_size_list_array(values: Sequence[Any]) -> pa.FixedSizeListArray:
    flat: list[np.float32] = []
    nulls: list[bool] = []
    for value in values:
        if value is None:
            flat.extend(np.float32(0.0) for _ in range(HISTORY_LENGTH))
            nulls.append(True)
            continue
        if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != HISTORY_LENGTH:
            raise AnfisAblationSequenceBuildError("Tensor does not have exactly 12 values")
        numbers = np.asarray(value, dtype=np.float32)
        if not np.isfinite(numbers).all():
            raise AnfisAblationSequenceBuildError("Successful tensor contains nonfinite values")
        flat.extend(numbers.tolist())
        nulls.append(False)
    array = pa.FixedSizeListArray.from_arrays(
        pa.array(flat, type=pa.float32()),
        list_size=HISTORY_LENGTH,
        mask=pa.array(nulls, type=pa.bool_()),
    )
    expected_type = pa.list_(pa.field("element", pa.float32(), nullable=False), HISTORY_LENGTH)
    return array.cast(expected_type)


def sequence_arrow_table(frame: pd.DataFrame, *, model_id: str) -> pa.Table:
    tensor_columns = input_columns(model_id)
    expected_columns = list(IDENTITY_COLUMNS + tensor_columns)
    if frame.columns.tolist() != expected_columns:
        raise AnfisAblationSequenceBuildError("Sequence DataFrame column order drifted")
    arrays: list[pa.Array] = []
    fields: list[pa.Field] = []
    nullable_ints = {"base_seed", "upstream_state_seed"}
    for column in expected_columns:
        if column in tensor_columns:
            array = _fixed_size_list_array(frame[column].tolist())
            field = pa.field(
                column,
                pa.list_(pa.field("element", pa.float32(), nullable=False), HISTORY_LENGTH),
                nullable=True,
            )
        elif column in nullable_ints:
            array = pa.array(frame[column].tolist(), type=pa.int64())
            field = pa.field(column, pa.int64(), nullable=True)
        elif column == "history_length_months":
            array = pa.array(frame[column].tolist(), type=pa.int16())
            field = pa.field(column, pa.int16(), nullable=False)
        else:
            array = pa.array(frame[column].astype(str).tolist(), type=pa.string())
            field = pa.field(column, pa.string(), nullable=False)
        arrays.append(array)
        fields.append(field)
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def summary_frame(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ("time_role", "sequence_status", "failure_reason")
    counts: dict[tuple[str, str, str], int] = {}
    for values in frame.loc[:, list(keys)].itertuples(index=False, name=None):
        key = (str(values[0]), str(values[1]), str(values[2]))
        counts[key] = counts.get(key, 0) + 1
    records = [
        {
            "horizons_months": "1,2,3",
            "time_role": key[0],
            "sequence_status": key[1],
            "failure_reason": key[2],
            "rows": count,
        }
        for key, count in sorted(counts.items())
    ]
    return pd.DataFrame(
        records,
        columns=(
            "horizons_months",
            "time_role",
            "sequence_status",
            "failure_reason",
            "rows",
        ),
    )


def _summary_bytes(frame: pd.DataFrame) -> bytes:
    handle = io.StringIO(newline="")
    summary_frame(frame).to_csv(handle, index=False, lineterminator="\n")
    return handle.getvalue().encode("utf-8")


def _audit_counts(audit: SequenceBuildAudit) -> dict[str, Any]:
    return {
        "common_rows": audit.common_rows,
        "intent_origins": audit.intent_origins,
        "development_locations": audit.development_locations,
        "source_ids": audit.source_ids,
        "successful_origins": audit.successful_origins,
        "failed_origins": audit.failed_origins,
        "role_counts": audit.role_counts,
        "status_counts": audit.status_counts,
        "failure_reason_counts": audit.failure_reason_counts,
        "observed_raw_value_counts": audit.observed_raw_value_counts,
        "masked_raw_value_counts": audit.masked_raw_value_counts,
    }


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise AnfisAblationSequenceBuildError(f"Path escapes repository: {path}") from exc


def bundle_paths(model_id: str, base_seed: int | None, *, repo_root: Path = PROJECT_ROOT) -> BundlePaths:
    validate_model_seed(model_id, base_seed)
    if model_id == "A0":
        parquet = repo_root / "data/closure_v1/development/sequences/A0/raw_no_current.parquet"
        stem = repo_root / "reports/closure_v1/01_surface/sequences/A0/raw_no_current"
        guard = repo_root / "tmp/closure_v1_anfis_ablation_sequences/A0_raw_no_current.guard"
    else:
        parquet = repo_root / f"data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet"
        stem = repo_root / f"reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}"
        guard = repo_root / f"tmp/closure_v1_anfis_ablation_sequences/A1_seed_{base_seed}.guard"
    return BundlePaths(
        parquet=parquet,
        summary=Path(f"{stem.as_posix()}_summary.csv"),
        manifest=Path(f"{stem.as_posix()}_manifest.json"),
        pointer=Path(f"{parquet.as_posix()}.dvc"),
        guard=guard,
    )


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _open_real_repository_parent(
    path: Path, *, repo_root: Path, create: bool, directory_mode: int = 0o755
) -> tuple[int, Path]:
    try:
        root = repo_root.resolve(strict=True)
        lexical = Path(os.path.abspath(path if path.is_absolute() else root / path))
        relative_parent = lexical.parent.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise AnfisAblationSequenceBuildError(f"Path escapes repository: {path}") from exc
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in relative_parent.parts:
            try:
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise AnfisAblationSequenceBuildError(f"Missing parent: {lexical.parent}")
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                except FileExistsError:
                    pass
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(named.st_mode):
                raise AnfisAblationSequenceBuildError(f"Non-directory ancestor: {lexical.parent}")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                os.close(child)
                raise AnfisAblationSequenceBuildError("Repository ancestor identity drifted")
            previous = descriptor
            descriptor = child
            os.close(previous)
        lexical_parent = lexical.parent.lstat()
        opened_parent = os.fstat(descriptor)
        if not stat.S_ISDIR(lexical_parent.st_mode) or (
            lexical_parent.st_dev,
            lexical_parent.st_ino,
        ) != (opened_parent.st_dev, opened_parent.st_ino):
            raise AnfisAblationSequenceBuildError("Repository parent identity drifted")
        return descriptor, lexical
    except BaseException:
        os.close(descriptor)
        raise


def _unlink_name_if_owned(directory_descriptor: int, name: str, *, device: int, inode: int) -> bool:
    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISREG(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == (device, inode):
        os.unlink(name, dir_fd=directory_descriptor)
        return True
    return False


def _hash_owned_name(owned: OwnedOutput) -> tuple[int, str]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(owned.path.name, flags, dir_fd=owned.directory_descriptor)
    try:
        before = os.fstat(descriptor)
        named = os.stat(owned.path.name, dir_fd=owned.directory_descriptor, follow_symlinks=False)
        expected = (owned.device, owned.inode)
        if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(named.st_mode) or (
            before.st_dev,
            before.st_ino,
        ) != expected or (named.st_dev, named.st_ino) != expected:
            raise AnfisAblationSequenceBuildError("Owned output identity drifted")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or size != after.st_size:
            raise AnfisAblationSequenceBuildError("Owned output changed while hashing")
        return size, digest.hexdigest()
    finally:
        os.close(descriptor)


def _publish_owned(
    path: Path,
    writer: Callable[[Any], None],
    *,
    repo_root: Path,
    binary: bool,
) -> OwnedOutput:
    parent_fd, lexical = _open_real_repository_parent(path, repo_root=repo_root, create=True)
    temporary_name = f"{lexical.name}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    committed = False
    try:
        try:
            descriptor = os.open(temporary_name, flags, 0o644, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise AnfisAblationSequenceBuildError(f"Refusing to overwrite {path}.tmp") from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AnfisAblationSequenceBuildError("Temporary output is not regular")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        duplicate = os.dup(descriptor)
        handle = os.fdopen(duplicate, "wb") if binary else os.fdopen(duplicate, "w", encoding="utf-8", newline="")
        with handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary = os.stat(temporary_name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(temporary.st_mode) or (temporary.st_dev, temporary.st_ino) != (device, inode):
            raise AnfisAblationSequenceBuildError("Temporary output identity drifted")
        try:
            os.link(
                temporary_name,
                lexical.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise AnfisAblationSequenceBuildError(f"Refusing to overwrite {path}") from exc
        final = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(final.st_mode) or (final.st_dev, final.st_ino) != (device, inode):
            _unlink_name_if_owned(parent_fd, lexical.name, device=device, inode=inode)
            raise AnfisAblationSequenceBuildError("Final output identity drifted")
        if not _unlink_name_if_owned(parent_fd, temporary_name, device=device, inode=inode):
            _unlink_name_if_owned(parent_fd, lexical.name, device=device, inode=inode)
            raise AnfisAblationSequenceBuildError("Temporary output changed before publication")
        os.fsync(parent_fd)
        os.close(descriptor)
        descriptor = None
        provisional = OwnedOutput(lexical, device, inode, 0, "", parent_fd)
        size, sha256 = _hash_owned_name(provisional)
        committed = True
        return OwnedOutput(lexical, device, inode, size, sha256, parent_fd)
    finally:
        active_error = sys.exc_info()[1]
        cleanup_errors: list[Exception] = []
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if not committed:
            if device is not None and inode is not None:
                for name in (lexical.name, temporary_name):
                    try:
                        _unlink_name_if_owned(parent_fd, name, device=device, inode=inode)
                    except OSError as exc:
                        cleanup_errors.append(exc)
            try:
                os.close(parent_fd)
            except OSError as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            error = AnfisAblationSequenceBuildError("Output cleanup failed")
            if active_error is not None:
                raise error from active_error
            raise error from cleanup_errors[0]


class OutputTransaction:
    """Own all published inodes until the manifest-last bundle commits."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._owned: list[OwnedOutput] = []

    def __enter__(self) -> "OutputTransaction":
        return self

    def publish_bytes(self, payload: bytes, path: Path) -> OwnedOutput:
        owned = _publish_owned(path, lambda handle: handle.write(payload), repo_root=self.repo_root, binary=True)
        self._owned.append(owned)
        return owned

    def publish_table(self, table: pa.Table, path: Path) -> OwnedOutput:
        owned = _publish_owned(
            path,
            lambda handle: pq.write_table(table, handle, compression="zstd", use_dictionary=False),
            repo_root=self.repo_root,
            binary=True,
        )
        self._owned.append(owned)
        return owned

    def record(self, owned: OwnedOutput) -> dict[str, Any]:
        if owned not in self._owned:
            raise AnfisAblationSequenceBuildError("Output is not owned by transaction")
        size, sha256 = _hash_owned_name(owned)
        if (size, sha256) != (owned.bytes, owned.sha256):
            raise AnfisAblationSequenceBuildError("Owned output content drifted")
        return {
            "path": _repo_relative(owned.path, self.repo_root),
            "bytes": size,
            "sha256": sha256,
        }

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        commit_error: AnfisAblationSequenceBuildError | None = None
        rollback_errors: list[Exception] = []
        if exc_type is None:
            for owned in self._owned:
                try:
                    self.record(owned)
                    opened_parent = os.fstat(owned.directory_descriptor)
                    lexical_parent = owned.path.parent.lstat()
                except (AnfisAblationSequenceBuildError, FileNotFoundError, OSError) as error:
                    commit_error = AnfisAblationSequenceBuildError(
                        f"Bundle output disappeared before commit: {owned.path}"
                    )
                    commit_error.add_note(str(error))
                    break
                if not stat.S_ISDIR(lexical_parent.st_mode) or (
                    opened_parent.st_dev,
                    opened_parent.st_ino,
                ) != (lexical_parent.st_dev, lexical_parent.st_ino):
                    commit_error = AnfisAblationSequenceBuildError(
                        f"Bundle output parent drifted: {owned.path.parent}"
                    )
                    break
        if exc_type is not None or commit_error is not None:
            for owned in reversed(self._owned):
                try:
                    if _unlink_name_if_owned(
                        owned.directory_descriptor,
                        owned.path.name,
                        device=owned.device,
                        inode=owned.inode,
                    ):
                        os.fsync(owned.directory_descriptor)
                except OSError as error:
                    rollback_errors.append(error)
        for owned in self._owned:
            try:
                os.close(owned.directory_descriptor)
            except OSError as error:
                if exc_type is not None or commit_error is not None:
                    rollback_errors.append(error)
        self._owned.clear()
        if rollback_errors:
            error = AnfisAblationSequenceBuildError("Bundle output rollback failed")
            if exc is not None:
                raise error from exc
            if commit_error is not None:
                raise error from commit_error
            raise error from rollback_errors[0]
        if commit_error is not None:
            raise commit_error
        return False


def _acquire_guard(path: Path, *, repo_root: Path) -> OwnedGuard:
    parent_fd, lexical = _open_real_repository_parent(path, repo_root=repo_root, create=True, directory_mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    try:
        descriptor = os.open(lexical.name, flags, 0o600, dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AnfisAblationSequenceBuildError("Bundle guard is not regular")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        os.fsync(descriptor)
        os.fsync(parent_fd)
        return OwnedGuard(lexical, device, inode, descriptor, parent_fd)
    except BaseException:
        if device is not None and inode is not None:
            _unlink_name_if_owned(parent_fd, lexical.name, device=device, inode=inode)
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)
        raise


def _release_guard(guard: OwnedGuard) -> None:
    errors: list[Exception] = []
    try:
        opened_parent = os.fstat(guard.directory_descriptor)
        lexical_parent = guard.path.parent.lstat()
        named = os.stat(
            guard.path.name,
            dir_fd=guard.directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(named.st_mode)
            or (named.st_dev, named.st_ino) != (guard.device, guard.inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise AnfisAblationSequenceBuildError("Bundle guard identity drifted")
        if not _unlink_name_if_owned(
            guard.directory_descriptor,
            guard.path.name,
            device=guard.device,
            inode=guard.inode,
        ):
            raise AnfisAblationSequenceBuildError("Owned bundle guard disappeared")
        os.fsync(guard.directory_descriptor)
    except Exception as error:
        errors.append(error)
    for descriptor in (guard.file_descriptor, guard.directory_descriptor):
        try:
            os.close(descriptor)
        except OSError as error:
            errors.append(error)
    if errors:
        error = AnfisAblationSequenceBuildError("Bundle guard cleanup failed")
        error.add_note(
            "Cleanup failures: "
            + "; ".join(f"{type(item).__name__}: {item}" for item in errors)
        )
        raise error from errors[0]


def _assert_namespace_absent(paths: BundlePaths, *, allow_guard: bool = False) -> None:
    candidates = [*paths.finals, paths.pointer, paths.guard]
    candidates.extend(Path(f"{path.as_posix()}.tmp") for path in (*paths.finals, paths.pointer))
    present = [
        path.as_posix()
        for path in candidates
        if _lexists(path) and not (allow_guard and path == paths.guard)
    ]
    if present:
        raise AnfisAblationSequenceBuildError(f"Bundle namespace is not empty: {present}")


def _assert_published_namespace(paths: BundlePaths, *, repo_root: Path) -> None:
    """Fail closed on any side effect beyond three owned finals plus guard."""

    missing_or_nonregular: list[str] = []
    for path in (*paths.finals, paths.guard):
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            missing_or_nonregular.append(path.as_posix())
            continue
        if not stat.S_ISREG(metadata.st_mode):
            missing_or_nonregular.append(path.as_posix())
    if missing_or_nonregular:
        raise AnfisAblationSequenceBuildError(
            f"Published bundle/guard namespace drifted: {missing_or_nonregular}"
        )
    forbidden = (
        paths.pointer,
        *(Path(f"{path.as_posix()}.tmp") for path in (*paths.finals, paths.pointer)),
        repo_root / OUTCOME_ACCESS_LOG,
    )
    present = [path.as_posix() for path in forbidden if _lexists(path)]
    if present:
        raise AnfisAblationSequenceBuildError(
            f"Forbidden side effect appeared during one-shot: {present}"
        )


def _stable_file_record(path: Path, *, repo_root: Path) -> dict[str, Any]:
    parent_fd, lexical = _open_real_repository_parent(path, repo_root=repo_root, create=False)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        named = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(lexical.name, flags, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(named.st_mode) or not stat.S_ISREG(opened.st_mode) or (
            named.st_dev,
            named.st_ino,
        ) != (opened.st_dev, opened.st_ino):
            raise AnfisAblationSequenceBuildError(f"Input is not a stable regular file: {path}")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        before_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        if (
            before_identity
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            or before_identity
            != (
                named_after.st_dev,
                named_after.st_ino,
                named_after.st_size,
                named_after.st_mtime_ns,
                named_after.st_ctime_ns,
            )
            or size != after.st_size
        ):
            raise AnfisAblationSequenceBuildError(f"Input changed while hashing: {path}")
        return {"path": _repo_relative(lexical, repo_root), "bytes": size, "sha256": digest.hexdigest()}
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def _manifest_payload(
    *,
    model_id: str,
    base_seed: int | None,
    audit: SequenceBuildAudit,
    authority: Mapping[str, Any],
    inputs: Sequence[Mapping[str, Any]],
    source_code: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": model_id,
        "base_seed": base_seed if model_id == "A1" else None,
        "upstream_state_seed": base_seed if model_id == "A1" else None,
        "future_outcomes_accessed": False,
        "targets_read": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_command_executed": False,
        "horizons_months": list(HORIZONS),
        "tensor_contract": {
            "history_length_months": HISTORY_LENGTH,
            "input_only": True,
            "target_columns": [],
            "input_columns": list(input_columns(model_id)),
            "input_dimension": len(input_columns(model_id)),
            "physical_type": "fixed_size_list<float32>[12]",
            "raw_mean_columns": list(RAW_MEAN_COLUMNS),
            "raw_n_obs_columns": list(RAW_N_OBS_COLUMNS),
            "raw_value_columns": list(RAW_VALUE_COLUMNS),
            "raw_mask_columns": list(RAW_MASK_COLUMNS),
            "raw_observed_rule": "finite_mean_and_finite_n_obs_greater_than_zero",
            "raw_missing_transport_value": 0.0,
            "raw_missing_transport_semantics": "transport_only_not_imputation",
            "raw_mask_values": [0.0, 1.0],
            "adaptive_state_source_mapping": ADAPTIVE_STATE_SOURCE_MAPPING if model_id == "A1" else {},
            "adaptive_state_fallback": "forbidden",
            "failed_row_tensor_parent": "null",
        },
        "identity_columns": list(IDENTITY_COLUMNS),
        "canonical_sort": ["source_id", "site_id", "origin_year_month", "common_origin_id"],
        "counts": _audit_counts(audit),
        "authority": dict(authority),
        "script": dict(source_code[0]),
        "inputs": [dict(record) for record in inputs],
        "source_code": [dict(record) for record in source_code],
        "outputs": [dict(record) for record in outputs],
        "completion_marker_written_last": True,
    }


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _require_effective_authority(
    repo_root: Path,
    *,
    model_id: str,
    base_seed: int | None,
) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_sequence_development_patch import (
        require_anfis_ablation_sequence_development_authority,
    )

    authority = require_anfis_ablation_sequence_development_authority(
        model_id,
        base_seed,
        repo_root=repo_root,
    )
    if authority.get("gate") != "E0-MS" or authority.get("status") != "effective_preflight_passed":
        raise AnfisAblationSequenceBuildError("Effective E0-MS authority drifted")
    required_true = (
        "a0_sequence_build_authorized",
        "a1_sequence_build_authorized",
    )
    if any(authority.get(key) is not True for key in required_true):
        raise AnfisAblationSequenceBuildError("E0-MS build authority is incomplete")
    forbidden_true = (
        "temporal_fit_authorized",
        "target_access_authorized",
        "calibration_authorized",
        "metrics_authorized",
        "rollout_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "dvc_commands_authorized",
        "scientific_network_authorized",
        "outcome_access_authorized",
        "future_outcomes_accessed",
        "sequence_bundle_audit_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden_true):
        raise AnfisAblationSequenceBuildError("E0-MS authority broadened a forbidden operation")
    if (
        authority.get("authorized_model_id") != model_id
        or authority.get("authorized_base_seed") != base_seed
        or type(authority.get("completed_prefix_count")) is not int
        or type(authority.get("slot_creation_prefix_count")) is not int
        or (model_id, base_seed) not in BUNDLE_SLOTS
        or int(authority["completed_prefix_count"])
        != BUNDLE_SLOTS.index((model_id, base_seed))
        or int(authority["slot_creation_prefix_count"])
        != BUNDLE_SLOTS.index((model_id, base_seed))
    ):
        raise AnfisAblationSequenceBuildError("E0-MS target-slot authority drifted")
    return authority


def _authority_manifest_binding(authority: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "gate",
        "status",
        "h_patch_head",
        "p_patch_head",
        "runtime",
        "lock",
        "companion",
        "h_components_sha256",
        "physical_inputs_sha256",
        "builder_sha256",
        "auditor_sha256",
        "authorized_model_id",
        "authorized_base_seed",
        "completed_prefix_count",
    )
    missing = [key for key in required if key not in authority]
    if missing:
        raise AnfisAblationSequenceBuildError(f"E0-MS authority binding is incomplete: {missing}")
    for key in ("runtime", "lock", "companion"):
        record = authority[key]
        if not isinstance(record, Mapping) or set(record) != {"path", "role", "bytes", "sha256"}:
            raise AnfisAblationSequenceBuildError(f"E0-MS authority record drifted: {key}")
    return {key: authority[key] for key in required}


def _load_runtime_after_gate(repo_root: Path) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_sequence_development_patch import (
        load_and_validate_anfis_ablation_sequence_development_runtime,
    )

    runtime = load_and_validate_anfis_ablation_sequence_development_runtime(
        repo_root=repo_root,
        verify_physical_pins=True,
    )
    _validate_runtime_alignment(runtime)
    return runtime


def _validate_runtime_alignment(runtime: Mapping[str, Any]) -> None:
    """Bind implementation constants to the validated E0-MS runtime."""

    features = runtime.get("features")
    bundles = runtime.get("bundles")
    outputs = runtime.get("outputs")
    if not isinstance(features, Mapping) or not isinstance(bundles, Mapping) or not isinstance(outputs, Mapping):
        raise AnfisAblationSequenceBuildError("E0-MS runtime sections are absent")
    raw = features.get("raw_no_current")
    adaptive = features.get("adaptive_state")
    parquet = bundles.get("parquet_contract")
    if not isinstance(raw, Mapping) or not isinstance(adaptive, Mapping) or not isinstance(parquet, Mapping):
        raise AnfisAblationSequenceBuildError("E0-MS feature/Parquet contract is absent")
    expected_pairs = (
        (raw.get("mean_columns"), list(RAW_MEAN_COLUMNS)),
        (raw.get("n_obs_columns"), list(RAW_N_OBS_COLUMNS)),
        (raw.get("serialized_value_columns"), list(RAW_VALUE_COLUMNS)),
        (raw.get("observed_mask_columns"), list(RAW_MASK_COLUMNS)),
        (raw.get("exact_input_order"), list(A0_INPUT_COLUMNS)),
        (adaptive.get("state_source_mapping"), ADAPTIVE_STATE_SOURCE_MAPPING),
        (adaptive.get("exact_state_order"), list(ADAPTIVE_STATE_COLUMNS)),
        (bundles.get("identity_columns"), list(IDENTITY_COLUMNS)),
        (bundles.get("row_status_values"), list(ROW_STATUS_VALUES)),
        (parquet.get("model_channel_order", {}).get("A0"), list(A0_INPUT_COLUMNS)),
        (parquet.get("model_channel_order", {}).get("A1"), list(A1_INPUT_COLUMNS)),
        (parquet.get("forbidden_row_columns"), ["evaluation_unit_id", "target_year_month", "horizon_months"]),
        (parquet.get("horizons_manifest_only"), list(HORIZONS)),
    )
    if any(observed != expected for observed, expected in expected_pairs):
        raise AnfisAblationSequenceBuildError("E0-MS runtime tensor/identity contract drifted")
    if (
        parquet.get("exact_rows_per_bundle") != EXPECTED_INTENT_ORIGINS
        or parquet.get("channel_arrow_type") != "fixed_size_list_float32_length_12"
        or parquet.get("channel_parent_nullable") is not True
        or parquet.get("channel_child_nullable") is not False
    ):
        raise AnfisAblationSequenceBuildError("E0-MS runtime physical contract drifted")
    expected_outputs = {
        "A0": {
            "sequence": "data/closure_v1/development/sequences/A0/raw_no_current.parquet",
            "summary": "reports/closure_v1/01_surface/sequences/A0/raw_no_current_summary.csv",
            "manifest": "reports/closure_v1/01_surface/sequences/A0/raw_no_current_manifest.json",
            "pointer": "data/closure_v1/development/sequences/A0/raw_no_current.parquet.dvc",
            "guard": "tmp/closure_v1_anfis_ablation_sequences/A0_raw_no_current.guard",
        },
        "A1": {
            "sequence_template": "data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet",
            "summary_template": "reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}_summary.csv",
            "manifest_template": "reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}_manifest.json",
            "pointer_template": "data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet.dvc",
            "guard_template": "tmp/closure_v1_anfis_ablation_sequences/A1_seed_{base_seed}.guard",
        },
    }
    if outputs.get("A0") != expected_outputs["A0"] or outputs.get("A1") != expected_outputs["A1"]:
        raise AnfisAblationSequenceBuildError("E0-MS output namespace drifted")


def _read_regular_parquet(
    path: Path,
    *,
    columns: Sequence[str],
    repo_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read one Parquet projection from a pinned O_NOFOLLOW descriptor."""

    parent_fd, lexical = _open_real_repository_parent(path, repo_root=repo_root, create=False)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        named_before = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(lexical.name, flags, dir_fd=parent_fd)
        opened_before = os.fstat(descriptor)
        if not stat.S_ISREG(named_before.st_mode) or not stat.S_ISREG(opened_before.st_mode) or (
            named_before.st_dev,
            named_before.st_ino,
        ) != (opened_before.st_dev, opened_before.st_ino):
            raise AnfisAblationSequenceBuildError(f"Parquet is not a stable regular file: {path}")
        before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        duplicate = os.dup(descriptor)
        with os.fdopen(duplicate, "rb") as handle:
            table = pq.read_table(handle, columns=list(columns))
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        after_open = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before != after_open or before != after_name or size != opened_after.st_size:
            raise AnfisAblationSequenceBuildError(f"Parquet changed while reading: {path}")
        return table.to_pandas(), {
            "path": _repo_relative(lexical, repo_root),
            "bytes": size,
            "sha256": digest.hexdigest(),
        }
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def _read_input_frames(
    *, model_id: str, base_seed: int | None, repo_root: Path
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame | None,
    list[dict[str, Any]],
    list[Path],
]:
    common_path = repo_root / DEFAULT_COMMON_ORIGINS
    panel_path = repo_root / DEFAULT_PANEL
    common, common_record = _read_regular_parquet(
        common_path, columns=COMMON_REQUIRED_COLUMNS, repo_root=repo_root
    )
    panel, panel_record = _read_regular_parquet(
        panel_path, columns=PANEL_REQUIRED_COLUMNS, repo_root=repo_root
    )
    input_paths = [
        common_path,
        repo_root / DEFAULT_COMMON_POINTER,
        repo_root / DEFAULT_COMMON_MANIFEST,
        panel_path,
        repo_root / DEFAULT_PANEL_POINTER,
    ]
    input_records = [
        common_record,
        _stable_file_record(input_paths[1], repo_root=repo_root),
        _stable_file_record(input_paths[2], repo_root=repo_root),
        panel_record,
        _stable_file_record(input_paths[4], repo_root=repo_root),
    ]
    state: pd.DataFrame | None = None
    if model_id == "A1":
        assert base_seed is not None
        state_path = repo_root / (
            f"data/closure_v1/development/anfis/seed_{base_seed}/adaptive_no_current_state.parquet"
        )
        state_pointer = repo_root / (
            f"data/closure_v1/development/anfis/seed_{base_seed}/"
            "adaptive_no_current_state.parquet.dvc"
        )
        state_manifest = repo_root / f"reports/closure_v1/01_surface/anfis/seed_{base_seed}/manifest.json"
        state, state_record = _read_regular_parquet(
            state_path, columns=STATE_REQUIRED_COLUMNS, repo_root=repo_root
        )
        input_paths.extend((state_path, state_pointer, state_manifest))
        input_records.extend(
            (
                state_record,
                _stable_file_record(state_pointer, repo_root=repo_root),
                _stable_file_record(state_manifest, repo_root=repo_root),
            )
        )
    return common, panel, state, input_records, input_paths


def materialize_anfis_ablation_sequence_bundle(
    *,
    model_id: str,
    base_seed: int | None,
    repo_root: Path = PROJECT_ROOT,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Consume one authorized one-shot and publish exactly three finals."""

    # Never permit an injected mapping to bypass the effective loader.  Tests
    # may supply a captured mapping, but it must equal the live result.
    effective = _require_effective_authority(
        repo_root,
        model_id=model_id,
        base_seed=base_seed,
    )
    if authority is not None and dict(authority) != effective:
        raise AnfisAblationSequenceBuildError("Injected E0-MS authority differs from live authority")
    _load_runtime_after_gate(repo_root)
    authority_binding = _authority_manifest_binding(effective)
    validate_model_seed(model_id, base_seed)
    paths = bundle_paths(model_id, base_seed, repo_root=repo_root)
    _assert_namespace_absent(paths)
    if _lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationSequenceBuildError("Outcome access log must remain absent before E0-M")

    guard = _acquire_guard(paths.guard, repo_root=repo_root)
    guard_active = True
    try:
        _assert_namespace_absent(paths, allow_guard=True)
        common, panel, state, input_records, input_paths = _read_input_frames(
            model_id=model_id, base_seed=base_seed, repo_root=repo_root
        )
        frame, audit = build_anfis_ablation_sequences(
            common,
            panel,
            model_id=model_id,
            base_seed=base_seed,
            adaptive_state=state,
            expected_common_rows=EXPECTED_COMMON_ROWS,
            expected_intent_origins=EXPECTED_INTENT_ORIGINS,
            expected_development_locations=EXPECTED_DEVELOPMENT_LOCATIONS,
            expected_source_ids={"wqp"},
            expected_role_counts=EXPECTED_ROLE_COUNTS,
        )
        table = sequence_arrow_table(frame, model_id=model_id)
        source_record = _stable_file_record(Path(__file__), repo_root=repo_root)
        with OutputTransaction(repo_root) as transaction:
            parquet_owned = transaction.publish_table(table, paths.parquet)
            summary_owned = transaction.publish_bytes(_summary_bytes(frame), paths.summary)
            output_records = [transaction.record(parquet_owned), transaction.record(summary_owned)]
            post_input_records = [
                _stable_file_record(path, repo_root=repo_root) for path in input_paths
            ]
            post_source_record = _stable_file_record(Path(__file__), repo_root=repo_root)
            if post_input_records != input_records or post_source_record != source_record:
                raise AnfisAblationSequenceBuildError("Inputs/source changed during bundle build")
            manifest = _manifest_payload(
                model_id=model_id,
                base_seed=base_seed,
                audit=audit,
                authority=authority_binding,
                inputs=input_records,
                source_code=[source_record],
                outputs=output_records,
            )
            manifest_owned = transaction.publish_bytes(_json_bytes(manifest), paths.manifest)
            manifest_record = transaction.record(manifest_owned)
            final_input_records = [
                _stable_file_record(path, repo_root=repo_root) for path in input_paths
            ]
            final_source_record = _stable_file_record(Path(__file__), repo_root=repo_root)
            if final_input_records != input_records or final_source_record != source_record:
                raise AnfisAblationSequenceBuildError(
                    "Inputs/source changed after manifest publication"
                )
            _assert_published_namespace(paths, repo_root=repo_root)
            # Release while outputs are still transaction-owned.  A release
            # failure therefore rolls back every final by its owned inode.
            try:
                _release_guard(guard)
            finally:
                guard_active = False
        return {
            "status": "sequence_bundle_written_unpublished",
            "model_id": model_id,
            "base_seed": base_seed,
            "counts": _audit_counts(audit),
            "outputs": [*output_records, manifest_record],
            "dvc_command_executed": False,
            "targets_read": False,
            "future_outcomes_accessed": False,
        }
    except BaseException:
        if guard_active:
            guard_active = False
            _release_guard(guard)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", choices=MODEL_IDS, required=True)
    parser.add_argument("--base-seed", type=int)
    parser.add_argument("--execute-one-shot", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # This must remain the first operation after argument parsing.  In
    # particular, no output path is resolved and no scientific input is opened
    # before the published gate passes.
    authority = _require_effective_authority(
        PROJECT_ROOT,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    result = materialize_anfis_ablation_sequence_bundle(
        model_id=args.model_id,
        base_seed=args.base_seed,
        repo_root=PROJECT_ROOT,
        authority=authority,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
