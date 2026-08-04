#!/usr/bin/env python
"""Build strict Closure V1 P0/P1 recurrent windows.

The historical PIPE sequence builder intentionally remains unchanged.  This
adapter consumes the externally locked Closure development state artifacts and
serializes one complete 12-month window per common origin.  Scientific outcome
columns are neither read nor written here.
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
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.experiments.closure_development_guard import (
    DEFAULT_ASSIGNMENT,
    DEFAULT_HOLDOUT_MANIFEST,
    DEFAULT_PROTOCOL_LOCK,
    ROLE_CALIBRATION_THRESHOLD,
    ROLE_MODEL_SELECTION,
    ROLE_TRAINING,
    assert_development_frame,
    load_development_gate,
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_runtime_contract import (
    EXPECTED_CPU_EXECUTION_POLICY,
    anfis_module_substreams,
    closure_seasonality,
    configure_torch_cpu_execution_policy,
)


SEQUENCE_VERSION = "closure_pipe_sequence_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
HISTORY_LENGTH = 12
HORIZONS = (1, 2, 3)
EXPECTED_INTENT_ORIGINS = 9_732
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
MODEL_IDS = ("P0", "P1")
SEQUENCE_STATUS_VALUES = (
    "success",
    "input_history_unavailable",
    "autoregressive_target_unavailable",
    "model_slot_unavailable",
)
EXPECTED_INTENT_ORIGINS_BY_ROLE = {
    ROLE_TRAINING: 8_352,
    ROLE_MODEL_SELECTION: 1_061,
    ROLE_CALIBRATION_THRESHOLD: 319,
}

STATE_CHANNELS = (
    "yN",
    "yF",
    "yT",
    "sigma_N",
    "sigma_F",
    "sigma_T",
    "delta_yN",
    "delta_yF",
    "delta_yT",
)
SEASON_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
INPUT_COLUMNS = tuple(f"x_{column}" for column in STATE_CHANNELS) + SEASON_COLUMNS
TARGET_COLUMNS = tuple(f"target_{column}" for column in STATE_CHANNELS)
TARGET_TO_NEXT_INPUT_MAPPING = dict(
    zip(TARGET_COLUMNS, (f"x_{column}" for column in STATE_CHANNELS), strict=True)
)

MODEL_STATE_MAPPINGS: dict[str, dict[str, str]] = {
    "P0": {
        "yN": "yN",
        "yF": "yF",
        "yT": "yT_no_chla",
        "sigma_N": "sigma_N",
        "sigma_F": "sigma_F",
        "sigma_T": "sigma_T_no_chla",
        "delta_yN": "delta_yN",
        "delta_yF": "delta_yF",
        "delta_yT": "delta_yT_no_chla",
    },
    "P1": {
        "yN": "yN_adaptive",
        "yF": "yF_adaptive",
        "yT": "yT_no_chla_adaptive",
        "sigma_N": "sigma_N_adaptive",
        "sigma_F": "sigma_F_adaptive",
        "sigma_T": "sigma_T_no_chla_adaptive",
        "delta_yN": "delta_yN_adaptive",
        "delta_yF": "delta_yF_adaptive",
        "delta_yT": "delta_yT_no_chla_adaptive",
    },
}

COMMON_ORIGIN_REQUIRED_COLUMNS = (
    "surface_id",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_unit_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
)

SEQUENCE_ID_COLUMNS = (
    "sequence_version",
    "surface_id",
    "model_id",
    "base_seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_unit_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
    "sequence_status",
    "failure_reason",
)
SEQUENCE_COLUMNS = SEQUENCE_ID_COLUMNS + INPUT_COLUMNS + TARGET_COLUMNS

DEFAULT_COMMON_ORIGINS = Path("data/closure_v1/common_origin_manifest.parquet")
DEFAULT_RUNTIME_CONFIG = Path("configs/closure_v1/development_runtime.yaml")
DEFAULT_RUNTIME_SCHEMA = Path("configs/closure_v1/development_runtime.schema.json")
DEFAULT_RUNTIME_LOCK = Path("reports/closure_v1/00_protocol/development_runtime_lock.json")
DEFAULT_COMMON_COMPLETION = Path("reports/closure_v1/01_surface/common_origin_manifest.json")


class ClosurePipeSequenceError(ValueError):
    """Raised when strict Closure sequence construction cannot be certified."""


@dataclass(frozen=True)
class SequenceBuildAudit:
    intent_origins: int
    successful_origins: int
    failed_origins: int
    role_counts: dict[str, int]
    status_counts: dict[str, int]
    failure_reason_counts: dict[str, int]
    delta_previous_month_missing_history_values: int
    delta_previous_month_missing_target_values: int


def validate_model_seed(model_id: str, base_seed: int | None) -> None:
    if model_id not in MODEL_IDS:
        raise ClosurePipeSequenceError(f"Unknown Closure temporal model: {model_id!r}")
    if model_id == "P0" and base_seed is not None:
        raise ClosurePipeSequenceError("The deterministic P0 sequence is shared and has no base seed")
    if model_id == "P1" and base_seed not in REGISTERED_SEEDS:
        raise ClosurePipeSequenceError(f"P1 requires one registered base seed: {base_seed!r}")


def state_projection_columns(model_id: str) -> list[str]:
    if model_id not in MODEL_STATE_MAPPINGS:
        raise ClosurePipeSequenceError(f"Unknown Closure temporal model: {model_id!r}")
    return [
        "source_id",
        "site_id",
        "year_month",
        "time_role",
        *MODEL_STATE_MAPPINGS[model_id].values(),
        "delta_previous_month_missing",
    ]


def _runtime_section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosurePipeSequenceError(f"Runtime contract is missing mapping {key!r}")
    return value


def validate_sequence_runtime_contract(runtime: Mapping[str, Any]) -> None:
    """Bind adapter constants to the authoritative runtime dialect."""
    state = _runtime_section(runtime, "primary_autoregressive_state")
    sequence = _runtime_section(state, "sequence_table")
    mappings = _runtime_section(state, "model_state_mappings")
    expected = {
        "surface_id": SURFACE_ID,
        "history_length_months": HISTORY_LENGTH,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise ClosurePipeSequenceError(f"Runtime primary_autoregressive_state.{key} drifted")
    if sequence.get("schema_version") != SEQUENCE_VERSION:
        raise ClosurePipeSequenceError("Runtime sequence schema version drifted")
    if sequence.get("expected_intent_rows") != EXPECTED_INTENT_ORIGINS:
        raise ClosurePipeSequenceError("Runtime sequence intent denominator drifted")
    if sequence.get("expected_intent_rows_by_role") != EXPECTED_INTENT_ORIGINS_BY_ROLE:
        raise ClosurePipeSequenceError("Runtime sequence role denominators drifted")
    if tuple(sequence.get("status_values", ())) != SEQUENCE_STATUS_VALUES:
        raise ClosurePipeSequenceError("Runtime sequence status dialect drifted")
    if sequence.get("input_physical_type") != "fixed_size_list_float32_length_12":
        raise ClosurePipeSequenceError("Runtime sequence input physical type drifted")
    if sequence.get("target_physical_type") != "float32_scalar":
        raise ClosurePipeSequenceError("Runtime sequence target physical type drifted")
    for model_id in MODEL_IDS:
        model_mapping = _runtime_section(mappings, model_id)
        if model_mapping.get("input_state_mapping") != MODEL_STATE_MAPPINGS[model_id]:
            raise ClosurePipeSequenceError(f"Runtime {model_id} input mapping drifted")
        if model_mapping.get("target_state_mapping") != MODEL_STATE_MAPPINGS[model_id]:
            raise ClosurePipeSequenceError(f"Runtime {model_id} target mapping drifted")
        if model_mapping.get("target_to_next_input_mapping") != TARGET_TO_NEXT_INPUT_MAPPING:
            raise ClosurePipeSequenceError(f"Runtime {model_id} recycle mapping drifted")
    if not _typed_scalar_equal(
        runtime.get("cpu_execution_policy"),
        EXPECTED_CPU_EXECUTION_POLICY,
    ):
        raise ClosurePipeSequenceError("Runtime CPU execution policy drifted")


def expected_cpu_execution_policy_record() -> dict[str, Any]:
    """Return the exact applied CPU policy recorded by Closure artifacts."""
    return {
        **EXPECTED_CPU_EXECUTION_POLICY,
        "torch_num_threads_observed": 1,
        "torch_num_interop_threads_observed": 1,
    }


def _utf8_order(frame: pd.DataFrame, columns: Sequence[str]) -> list[int]:
    keyed: list[tuple[tuple[bytes, ...], int]] = []
    for index, row in enumerate(frame.reset_index(drop=True).to_dict(orient="records")):
        values: list[bytes] = []
        for column in columns:
            value = row[column]
            if not isinstance(value, str) or not value or value != value.strip():
                raise ClosurePipeSequenceError(f"Canonical order key {column} is invalid")
            values.append(value.encode("utf-8"))
        keyed.append((tuple(values), index))
    return [index for _, index in sorted(keyed)]


def _canonical_month(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ClosurePipeSequenceError(f"{label} must be a YYYY-MM string")
    try:
        period = pd.Period(value, freq="M")
    except ValueError as exc:
        raise ClosurePipeSequenceError(f"{label} is not a valid calendar month: {value!r}") from exc
    if str(period) != value:
        raise ClosurePipeSequenceError(f"{label} must use canonical YYYY-MM serialization")
    return value


def _validate_common_origins(
    common_origins: pd.DataFrame,
    *,
    expected_origin_count: int | None,
) -> pd.DataFrame:
    missing = sorted(set(COMMON_ORIGIN_REQUIRED_COLUMNS).difference(common_origins.columns))
    if missing:
        raise ClosurePipeSequenceError(f"Common-origin rows are missing columns: {missing}")
    if common_origins.empty:
        raise ClosurePipeSequenceError("Common-origin rows cannot be empty")

    frame = common_origins.loc[:, COMMON_ORIGIN_REQUIRED_COLUMNS].copy()
    for column in (
        "surface_id",
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_unit_id",
        "holdout_group_id",
        "assignment_role",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "history_start_year_month",
        "history_end_year_month",
    ):
        if bool(frame[column].isna().any()):
            raise ClosurePipeSequenceError(f"Common-origin rows contain null {column}")
        frame[column] = frame[column].astype(str)

    if set(frame["surface_id"]) != {SURFACE_ID}:
        raise ClosurePipeSequenceError("Common-origin surface differs from the Closure primary surface")
    if set(frame["source_id"]) != {"wqp"}:
        raise ClosurePipeSequenceError("Common-origin rows must be WQP only")
    if set(frame["assignment_role"]) != {"development"}:
        raise ClosurePipeSequenceError("Common-origin rows must be development only")
    permitted_roles = {ROLE_TRAINING, ROLE_MODEL_SELECTION, ROLE_CALIBRATION_THRESHOLD}
    if not set(frame["time_role"]).issubset(permitted_roles):
        raise ClosurePipeSequenceError("Common-origin rows contain a forbidden temporal role")

    horizons = pd.to_numeric(frame["horizon_months"], errors="coerce")
    if bool(horizons.isna().any()) or not bool(horizons.isin(HORIZONS).all()):
        raise ClosurePipeSequenceError("Common-origin rows contain invalid horizons")
    frame["horizon_months"] = horizons.astype("int8")
    if bool(
        frame.duplicated(
            ["source_id", "site_id", "origin_year_month", "target_year_month", "horizon_months"],
            keep=False,
        ).any()
    ):
        raise ClosurePipeSequenceError("Common-origin rows contain duplicate evaluation keys")

    records: list[pd.Series] = []
    grouped = frame.groupby(["source_id", "site_id", "origin_year_month"], sort=False)
    for _, group in grouped:
        if len(group) != 3 or set(group["horizon_months"].astype(int)) != set(HORIZONS):
            raise ClosurePipeSequenceError("Every common origin must contain exactly h1, h2, and h3")
        for column in (
            "surface_id",
            "common_origin_id",
            "holdout_group_id",
            "assignment_role",
            "time_role",
            "history_start_year_month",
            "history_end_year_month",
            "history_length_months",
        ):
            if group[column].nunique(dropna=False) != 1:
                raise ClosurePipeSequenceError(f"A common origin has conflicting {column}")
        origin: Any = pd.Period(
            _canonical_month(group.iloc[0]["origin_year_month"], label="origin_year_month"),
            freq="M",
        )
        for row in group.to_dict(orient="records"):
            target = _canonical_month(row["target_year_month"], label="target_year_month")
            if str(origin + int(row["horizon_months"])) != target:
                raise ClosurePipeSequenceError("Common-origin target arithmetic is invalid")
            target_period: Any = pd.Period(target, freq="M")
            cutoff: Any = pd.Period("2021-12", freq="M")
            if target_period > cutoff:
                raise ClosurePipeSequenceError("A development common origin reaches beyond 2021-12")
        h1 = group.loc[group["horizon_months"].eq(1)].iloc[0]
        expected_start = str(origin - (HISTORY_LENGTH - 1))
        if h1["history_start_year_month"] != expected_start:
            raise ClosurePipeSequenceError("Common-origin history start is not origin minus 11 months")
        if h1["history_end_year_month"] != str(origin):
            raise ClosurePipeSequenceError("Common-origin history end differs from its origin")
        if int(h1["history_length_months"]) != HISTORY_LENGTH:
            raise ClosurePipeSequenceError("Common-origin history length must equal 12")
        records.append(h1)

    origins = pd.DataFrame(records).reset_index(drop=True)
    origins = origins.iloc[
        _utf8_order(origins, ("source_id", "site_id", "origin_year_month"))
    ].reset_index(drop=True)
    if expected_origin_count is not None and len(origins) != expected_origin_count:
        raise ClosurePipeSequenceError(
            f"Common-origin count differs from the locked intent denominator: {len(origins)} != {expected_origin_count}"
        )
    return origins


def _validate_state_frame(state: pd.DataFrame, model_id: str) -> pd.DataFrame:
    required = state_projection_columns(model_id)
    missing = sorted(set(required).difference(state.columns))
    if missing:
        raise ClosurePipeSequenceError(f"Closure state rows are missing projected columns: {missing}")
    if state.empty:
        raise ClosurePipeSequenceError("Closure state rows cannot be empty")
    frame = state.loc[:, required].copy()
    for column in ("source_id", "site_id", "year_month", "time_role"):
        if bool(frame[column].isna().any()):
            raise ClosurePipeSequenceError(f"Closure state rows contain null {column}")
        frame[column] = frame[column].astype(str)
    if set(frame["source_id"]) != {"wqp"}:
        raise ClosurePipeSequenceError("Closure state rows must be WQP only")
    if bool(frame.duplicated(["source_id", "site_id", "year_month"], keep=False).any()):
        raise ClosurePipeSequenceError("Closure state rows contain duplicate site-month keys")
    if not bool(frame["delta_previous_month_missing"].map(type).eq(bool).all()):
        raise ClosurePipeSequenceError("delta_previous_month_missing must contain strict booleans")
    permitted_roles = {ROLE_TRAINING, ROLE_MODEL_SELECTION, ROLE_CALIBRATION_THRESHOLD}
    if not set(frame["time_role"]).issubset(permitted_roles):
        raise ClosurePipeSequenceError("Closure state rows contain a forbidden temporal role")
    for month in frame["year_month"]:
        _canonical_month(month, label="state.year_month")
    if max(pd.PeriodIndex(frame["year_month"], freq="M")) > pd.Period("2021-12", freq="M"):
        raise ClosurePipeSequenceError("Closure state rows materialize a month after 2021-12")
    return frame.sort_values(["source_id", "site_id", "year_month"], kind="mergesort").reset_index(drop=True)


def _channel_values_are_valid(values: np.ndarray) -> bool:
    if values.shape != (HISTORY_LENGTH, len(STATE_CHANNELS)) or not np.isfinite(values).all():
        return False
    return bool(
        ((values[:, :6] >= 0.0) & (values[:, :6] <= 1.0)).all()
        and ((values[:, 6:] >= -1.0) & (values[:, 6:] <= 1.0)).all()
    )


def _target_values_are_valid(values: np.ndarray) -> bool:
    if values.shape != (len(STATE_CHANNELS),) or not np.isfinite(values).all():
        return False
    return bool(
        ((values[:6] >= 0.0) & (values[:6] <= 1.0)).all()
        and ((values[6:] >= -1.0) & (values[6:] <= 1.0)).all()
    )


def _failed_payload() -> tuple[dict[str, None], dict[str, None]]:
    inputs: dict[str, None] = {column: None for column in INPUT_COLUMNS}
    targets: dict[str, None] = {column: None for column in TARGET_COLUMNS}
    return inputs, targets


def build_closure_pipe_sequences(
    state: pd.DataFrame | None,
    common_origins: pd.DataFrame,
    *,
    model_id: str,
    base_seed: int | None,
    expected_origin_count: int | None = EXPECTED_INTENT_ORIGINS,
    expected_role_counts: Mapping[str, int] | None = None,
    model_slot_failure_reason: str = "state_model_slot_unavailable",
) -> tuple[pd.DataFrame, SequenceBuildAudit]:
    """Build one fixed 12-month tensor row for each locked common origin.

    A state-availability or numeric failure is retained as a row with nullable
    tensors and an explicit closed status/reason.  Contract/identity violations
    fail the whole build instead of being converted into model failures.
    """
    validate_model_seed(model_id, base_seed)
    origins = _validate_common_origins(common_origins, expected_origin_count=expected_origin_count)
    role_counts = origins["time_role"].value_counts().to_dict()
    if expected_role_counts is not None and role_counts != dict(expected_role_counts):
        raise ClosurePipeSequenceError(
            f"Common-origin role counts differ from the locked denominators: {role_counts}"
        )
    states = _validate_state_frame(state, model_id) if state is not None else None
    mapping = MODEL_STATE_MAPPINGS[model_id]
    indexed = (
        states.set_index(["source_id", "site_id", "year_month"])
        if states is not None
        else None
    )

    output_rows: list[dict[str, Any]] = []
    delta_history_values = 0
    delta_target_values = 0
    for origin_row in origins.to_dict(orient="records"):
        origin: Any = pd.Period(str(origin_row["origin_year_month"]), freq="M")
        history_months = [str(origin - offset) for offset in range(HISTORY_LENGTH - 1, -1, -1)]
        target_month = str(origin + 1)
        history_keys = [
            (str(origin_row["source_id"]), str(origin_row["site_id"]), month)
            for month in history_months
        ]
        target_key = (
            str(origin_row["source_id"]),
            str(origin_row["site_id"]),
            target_month,
        )
        status = "success"
        reason = ""
        input_payload: dict[str, Any]
        target_payload: dict[str, Any]

        if indexed is None:
            status, reason = "model_slot_unavailable", model_slot_failure_reason
            input_payload, target_payload = _failed_payload()
        else:
            missing_history = [key for key in history_keys if key not in indexed.index]
            if missing_history:
                status, reason = "input_history_unavailable", "missing_history_state"
                input_payload, target_payload = _failed_payload()
            elif target_key not in indexed.index:
                status, reason = "autoregressive_target_unavailable", "missing_target_state"
                input_payload, target_payload = _failed_payload()
            else:
                history = indexed.loc[history_keys]
                target = indexed.loc[target_key]
                if (
                    str(history.iloc[-1]["time_role"]) != str(origin_row["time_role"])
                    or str(target["time_role"]) != str(origin_row["time_role"])
                ):
                    raise ClosurePipeSequenceError(
                        "A supervised origin and adjacent target must share the locked endpoint role"
                    )
                history_values = history[list(mapping.values())].to_numpy(dtype=np.float32)
                target_values = target[list(mapping.values())].to_numpy(dtype=np.float32)
                if not _channel_values_are_valid(history_values):
                    status, reason = (
                        "input_history_unavailable",
                        "invalid_or_nonfinite_history_state",
                    )
                    input_payload, target_payload = _failed_payload()
                elif not _target_values_are_valid(target_values):
                    status, reason = (
                        "autoregressive_target_unavailable",
                        "invalid_or_nonfinite_target_state",
                    )
                    input_payload, target_payload = _failed_payload()
                else:
                    input_payload = {
                        f"x_{channel}": history_values[:, index].astype(np.float32).tolist()
                        for index, channel in enumerate(STATE_CHANNELS)
                    }
                    seasonal: dict[str, list[float]] = {column: [] for column in SEASON_COLUMNS}
                    for month in history_months:
                        period: Any = pd.Period(month, freq="M")
                        values = closure_seasonality(int(period.month))
                        for column in SEASON_COLUMNS:
                            seasonal[column].append(float(np.float32(values[column])))
                    input_payload.update(seasonal)
                    target_payload = {
                        f"target_{channel}": float(np.float32(target_values[index]))
                        for index, channel in enumerate(STATE_CHANNELS)
                    }
                    delta_history_values += int(
                        history["delta_previous_month_missing"].astype(bool).sum()
                    )
                    delta_target_values += int(bool(target["delta_previous_month_missing"]))

        output_rows.append(
            {
                "sequence_version": SEQUENCE_VERSION,
                "surface_id": origin_row["surface_id"],
                "model_id": model_id,
                "base_seed": base_seed,
                "source_id": origin_row["source_id"],
                "site_id": origin_row["site_id"],
                "common_origin_id": origin_row["common_origin_id"],
                "evaluation_unit_id": origin_row["evaluation_unit_id"],
                "holdout_group_id": origin_row["holdout_group_id"],
                "assignment_role": origin_row["assignment_role"],
                "time_role": origin_row["time_role"],
                "origin_year_month": origin_row["origin_year_month"],
                "target_year_month": target_month,
                "history_start_year_month": history_months[0],
                "history_end_year_month": history_months[-1],
                "history_length_months": HISTORY_LENGTH,
                "sequence_status": status,
                "failure_reason": reason,
                **input_payload,
                **target_payload,
            }
        )

    output = pd.DataFrame(output_rows, columns=SEQUENCE_COLUMNS)
    output = output.iloc[
        _utf8_order(
            output,
            ("source_id", "site_id", "origin_year_month", "target_year_month"),
        )
    ].reset_index(drop=True)
    if len(output) != len(origins) or bool(
        output.duplicated(["source_id", "site_id", "origin_year_month"], keep=False).any()
    ):
        raise ClosurePipeSequenceError("Sequence output does not conserve one row per common origin")

    roles = output["time_role"].value_counts()
    if not set(output["sequence_status"]).issubset(SEQUENCE_STATUS_VALUES):
        raise ClosurePipeSequenceError("Sequence output contains an unknown closed status")
    statuses = output["sequence_status"].value_counts()
    failures = output.loc[~output["sequence_status"].eq("success"), "failure_reason"].value_counts()
    audit = SequenceBuildAudit(
        intent_origins=int(len(output)),
        successful_origins=int(output["sequence_status"].eq("success").sum()),
        failed_origins=int((~output["sequence_status"].eq("success")).sum()),
        role_counts={str(key): int(value) for key, value in roles.items()},
        status_counts={str(key): int(value) for key, value in statuses.items()},
        failure_reason_counts={str(key): int(value) for key, value in failures.items()},
        delta_previous_month_missing_history_values=delta_history_values,
        delta_previous_month_missing_target_values=delta_target_values,
    )
    return output, audit


def _fixed_size_array(
    values: Sequence[Any],
    *,
    size: int,
    value_type: pa.DataType,
) -> pa.Array:
    normalized: list[list[float | None]] = []
    for value in values:
        if value is None:
            # Parquet cannot encode a parent-null FixedSizeList because every
            # slot still owns ``size`` physical children (Apache Arrow #24425).
            # Keep the closed fixed-size schema and represent a logically null
            # tensor with an outer-valid list whose children are all null.
            normalized.append([None] * size)
            continue
        array = np.asarray(value)
        if array.shape != (size,):
            raise ClosurePipeSequenceError(f"Fixed-size list payload must have shape ({size},)")
        normalized.append(array.astype(np.float32).tolist())
    return pa.array(normalized, type=pa.list_(value_type, size))


def _path_entry_exists(path: Path) -> bool:
    """Return true for every lexical entry, including a broken symlink."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _open_real_output_parent(path: Path) -> int:
    try:
        repository_root = PROJECT_ROOT.resolve(strict=True)
        lexical_parent = Path(os.path.abspath(path.parent))
        relative_parent = lexical_parent.relative_to(repository_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ClosurePipeSequenceError(f"Output parent escapes the repository: {path}") from exc
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(repository_root, directory_flags)
    except OSError as exc:
        raise ClosurePipeSequenceError("Repository root cannot be opened safely") from exc
    try:
        for part in relative_parent.parts:
            try:
                metadata = os.stat(
                    part,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
                metadata = os.stat(
                    part,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosurePipeSequenceError(
                    f"Output ancestor is not a real directory: {path}"
                )
            child = os.open(part, directory_flags, dir_fd=descriptor)
            opened_child = os.fstat(child)
            if (opened_child.st_dev, opened_child.st_ino) != (
                metadata.st_dev,
                metadata.st_ino,
            ):
                os.close(child)
                raise ClosurePipeSequenceError(f"Output ancestor identity drifted: {path}")
            os.close(descriptor)
            descriptor = child
        opened = os.fstat(descriptor)
        lexical = lexical_parent.lstat()
        if (
            not stat.S_ISDIR(lexical.st_mode)
            or (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            raise ClosurePipeSequenceError(f"Output parent identity drifted: {path}")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _unlink_name_if_owned(
    directory_descriptor: int,
    name: str,
    *,
    device: int,
    inode: int,
) -> None:
    try:
        metadata = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except (FileNotFoundError, OSError):
        return
    if (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == (device, inode)
    ):
        os.unlink(name, dir_fd=directory_descriptor)


def _write_output_no_clobber(
    path: Path,
    writer: Any,
    *,
    binary: bool,
) -> None:
    """Write through an exclusive temporary inode and hard-link it once."""
    directory_descriptor = _open_real_output_parent(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    committed = False
    try:
        try:
            descriptor = os.open(
                temporary.name,
                flags,
                0o644,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise ClosurePipeSequenceError(
                f"Refusing to overwrite temporary artifact: {temporary}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ClosurePipeSequenceError(f"Temporary artifact is not regular: {temporary}")
        device, inode = metadata.st_dev, metadata.st_ino
        if binary:
            with os.fdopen(os.dup(descriptor), "wb") as handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())
        else:
            with os.fdopen(
                os.dup(descriptor),
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())
        temporary_metadata = os.stat(
            temporary.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        parent_opened = os.fstat(directory_descriptor)
        parent_lexical = path.parent.lstat()
        if (
            not stat.S_ISREG(temporary_metadata.st_mode)
            or (temporary_metadata.st_dev, temporary_metadata.st_ino) != (device, inode)
            or not stat.S_ISDIR(parent_lexical.st_mode)
            or (parent_lexical.st_dev, parent_lexical.st_ino)
            != (parent_opened.st_dev, parent_opened.st_ino)
        ):
            raise ClosurePipeSequenceError(f"Temporary artifact identity drifted: {temporary}")
        try:
            os.link(
                temporary.name,
                path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ClosurePipeSequenceError(
                f"Refusing to overwrite final artifact: {path}"
            ) from exc
        final_metadata = os.stat(
            path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        final_lexical = path.lstat()
        parent_lexical = path.parent.lstat()
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or not stat.S_ISREG(final_lexical.st_mode)
            or (final_metadata.st_dev, final_metadata.st_ino) != (device, inode)
            or (final_lexical.st_dev, final_lexical.st_ino) != (device, inode)
            or (parent_lexical.st_dev, parent_lexical.st_ino)
            != (parent_opened.st_dev, parent_opened.st_ino)
        ):
            _unlink_name_if_owned(
                directory_descriptor,
                path.name,
                device=device,
                inode=inode,
            )
            raise ClosurePipeSequenceError(f"Final artifact identity drifted: {path}")
        _unlink_name_if_owned(
            directory_descriptor,
            temporary.name,
            device=device,
            inode=inode,
        )
        os.fsync(directory_descriptor)
        committed = True
    finally:
        if device is not None and inode is not None:
            if not committed:
                _unlink_name_if_owned(
                    directory_descriptor,
                    path.name,
                    device=device,
                    inode=inode,
                )
            _unlink_name_if_owned(
                directory_descriptor,
                temporary.name,
                device=device,
                inode=inode,
            )
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def sequence_arrow_table(frame: pd.DataFrame) -> pa.Table:
    if frame.columns.tolist() != list(SEQUENCE_COLUMNS):
        raise ClosurePipeSequenceError("Sequence output columns or order differ from the closed schema")
    arrays: list[pa.Array] = []
    fields: list[pa.Field] = []
    success = frame["sequence_status"].eq("success").tolist()
    for column in SEQUENCE_COLUMNS:
        if column in INPUT_COLUMNS:
            values = [value if row_success else None for value, row_success in zip(frame[column], success, strict=True)]
            arrays.append(_fixed_size_array(values, size=HISTORY_LENGTH, value_type=pa.float32()))
            fields.append(pa.field(column, pa.list_(pa.float32(), HISTORY_LENGTH), nullable=True))
        elif column in TARGET_COLUMNS:
            values = [value if row_success else None for value, row_success in zip(frame[column], success, strict=True)]
            arrays.append(pa.array(values, type=pa.float32()))
            fields.append(pa.field(column, pa.float32(), nullable=True))
        elif column == "base_seed":
            arrays.append(pa.array(frame[column].tolist(), type=pa.int64()))
            fields.append(pa.field(column, pa.int64(), nullable=True))
        elif column == "history_length_months":
            arrays.append(pa.array(frame[column].tolist(), type=pa.int16()))
            fields.append(pa.field(column, pa.int16(), nullable=False))
        else:
            arrays.append(pa.array(frame[column].astype(str).tolist(), type=pa.string()))
            fields.append(pa.field(column, pa.string(), nullable=False))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def write_sequence_parquet(frame: pd.DataFrame, path: Path) -> None:
    table = sequence_arrow_table(frame)
    _write_output_no_clobber(
        path,
        lambda handle: pq.write_table(
            table,
            handle,
            compression="zstd",
            use_dictionary=False,
        ),
        binary=True,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": _repo_path(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _output_record_for_path(
    payload: Mapping[str, Any],
    path: Path,
    *,
    role: str,
) -> Mapping[str, Any]:
    raw_outputs = payload.get("outputs")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise ClosurePipeSequenceError("State manifest outputs must be an array")
    expected_path = _repo_path(path)
    matches = [
        record
        for record in raw_outputs
        if isinstance(record, Mapping)
        and record.get("path") == expected_path
        and record.get("role") == role
    ]
    if len(matches) != 1:
        raise ClosurePipeSequenceError(
            f"State manifest must contain one {role!r} record for {expected_path}"
        )
    return matches[0]


ANFIS_MODULES = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
ANFIS_MODULE_ARTIFACT_TOKENS = {
    "ANFIS-N": "anfis_n",
    "ANFIS-F": "anfis_f",
    "ANFIS-T-no-current": "anfis_t_no_current",
}
ANFIS_FITTED_MODULE_METRIC_COLUMNS = (
    "module",
    "status",
    "base_seed",
    "module_seed",
    "train_rows",
    "prediction_rows",
    "input_dimension",
    "rule_count",
    "epochs",
    "curve_initial_pre_update_loss",
    "curve_last_pre_update_loss",
    "minimum_curve_pre_update_loss",
    "final_checkpoint_loss",
    "quality_gate_output_standard_deviation",
    "quality_gate_output_scope",
    "materialized_surface_output_standard_deviation",
    "maximum_parameter_delta",
    "centers_ordered",
    "centers_in_unit_interval",
)
ANFIS_UNAVAILABLE_MODULE_METRIC_COLUMNS = (
    "module",
    "status",
    "failure_reason",
    "base_seed",
    "module_seed",
    "input_rows",
    "excluded_nonfinite_target_rows",
    "excluded_missingness_rows",
    "eligible_universe_rows",
    "selected_rows",
    "required_rows",
    "replacement_used",
    "fit_attempted",
)
ANFIS_REQUIRED_SOURCE_PATHS = (
    "src/experiments/fit_closure_anfis_state.py",
    "src/experiments/build_closure_expert_state.py",
    "src/experiments/closure_development_runtime_lock.py",
    "src/experiments/closure_runtime_contract.py",
    "src/experiments/closure_development_guard.py",
    "src/experiments/closure_contract.py",
    "src/fuzzy/adaptive_anfis.py",
)
ANFIS_DEPENDENCY_ROLES = (
    "development_runtime_config",
    "development_runtime_schema",
    "development_runtime_lock",
    "development_runtime_lock_schema",
    "common_origin",
    "common_origin_completion_manifest",
    "restored_panel",
    "restored_expert_anchor",
    "holdout_assignment",
    "holdout_manifest",
    "protocol_lock",
    "strict_anfis_state_adapter",
    "strict_expert_state_adapter",
    "runtime_lock_validator",
    "runtime_contract_validator",
    "closure_development_guard",
    "closure_contract",
    "adaptive_anfis_implementation",
)
ANFIS_SOURCE_ROLE_PATHS = dict(
    zip(
        ANFIS_DEPENDENCY_ROLES[11:],
        ANFIS_REQUIRED_SOURCE_PATHS,
        strict=True,
    )
)
ANFIS_AUTHORIZATION_KEYS = {
    "lock_path",
    "lock_sha256",
    "lock_version",
    "status",
    "locked_repository_head",
    "execution_head",
    "published_ref",
    "published_head",
    "remote_main_oid",
    "locked_head_is_ancestor",
    "locked_parent_published_at_lock",
    "publication_verified",
    "tracking_ref_publication_verified",
    "remote_publication_verified",
    "canonical_origin_identity_verified",
    "component_count",
    "planned_artifact_path_count",
    "planned_artifact_paths_sha256",
    "device",
    "metadata_verified",
    "physical_artifacts_required",
    "physical_artifacts_verified",
    "common_origin_output_verified",
    "expert_state_output_verified",
    "restored_development_sources_verified",
    "dvc_remote_verified_at_lock",
    "dvc_remote_verified",
    "fit_authorization_predicates",
    "payload_development_fit_authorized",
    "payload_evaluation_authorized",
    "payload_e0_u_authorized",
    "development_fit_authorized",
    "evaluation_authorized",
    "e0_u_authorized",
    "fit_authorized",
    "future_outcomes_accessed",
}
ANFIS_AUTHORIZATION_PREDICATE_KEYS = {
    "payload_authorization_verified",
    "locked_parent_published_at_lock",
    "physical_artifacts_verified",
    "publication_verified",
    "live_git_remote_verified",
    "canonical_origin_identity_verified",
    "common_origin_output_verified",
    "expert_state_output_verified",
    "restored_development_sources_verified",
    "dvc_remote_verified_at_lock",
    "locked_head_is_ancestor",
}


def _physical_manifest_record(
    record: Mapping[str, Any],
    *,
    context: str,
    historical_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ClosurePipeSequenceError(f"{context} path is invalid")
    logical = Path(raw_path)
    if logical.is_absolute() or ".." in logical.parts or logical.as_posix() != raw_path:
        raise ClosurePipeSequenceError(f"{context} path must be canonical repository-relative")
    physical = PROJECT_ROOT / logical
    try:
        physical.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ClosurePipeSequenceError(f"{context} path escapes the repository") from exc
    historical = (historical_records or {}).get(str(record.get("role", "")))
    if historical is not None:
        if historical.get("path") != raw_path or dict(record) != dict(historical):
            raise ClosurePipeSequenceError(
                f"{context} historical record differs from the closed E0-DLP exception"
            )
        return {
            "path": historical["path"],
            "bytes": historical["bytes"],
            "sha256": historical["sha256"],
        }
    if not physical.is_file():
        raise ClosurePipeSequenceError(f"{context} file is missing: {raw_path}")
    expected = _file_record(physical)
    if any(
        not _typed_scalar_equal(record.get(key), expected[key])
        for key in ("path", "bytes", "sha256")
    ):
        raise ClosurePipeSequenceError(f"{context} record differs from physical bytes")
    return expected


def _historical_anfis_consumer_context(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    from src.experiments.closure_development_runtime_patch import (  # noqa: PLC0415
        DevelopmentRuntimePatchError,
        require_adopted_seed_1729_consumer_context,
    )

    try:
        context = require_adopted_seed_1729_consumer_context(payload)
    except DevelopmentRuntimePatchError as exc:
        raise ClosurePipeSequenceError(
            "ANFIS historical dependency lacks valid published E0-DLP authority"
        ) from exc
    if context is None:
        return None
    records = context.get("historical_source_records")
    if not isinstance(records, Mapping) or set(records) != {
        "generating_script",
        "strict_anfis_state_adapter",
        "runtime_lock_validator",
    }:
        raise ClosurePipeSequenceError(
            "E0-DLP historical dependency context drifted"
        )
    if context.get("historical_uppercase_artifact_paths") is not True:
        raise ClosurePipeSequenceError("E0-DLP historical artifact-path context drifted")
    return context


def _expected_anfis_source_record(
    path: str,
    role: str,
    historical_records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    historical = historical_records.get(role)
    if historical is not None:
        expected = dict(historical)
        if expected.get("role") != role or expected.get("path") != path:
            raise ClosurePipeSequenceError(
                f"E0-DLP historical ANFIS role {role!r} drifted"
            )
        return expected
    return {**_file_record(PROJECT_ROOT / path), "role": role}


def _validate_anfis_provenance(
    payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any] | None]:
    if payload.get("development_fit_authorized") is not True:
        raise ClosurePipeSequenceError("ANFIS manifest lacks development-fit authorization")
    historical_context = _historical_anfis_consumer_context(payload)
    historical_records = cast(
        Mapping[str, Mapping[str, Any]],
        historical_context.get("historical_source_records", {})
        if historical_context is not None
        else {},
    )
    expected_script = _expected_anfis_source_record(
        ANFIS_REQUIRED_SOURCE_PATHS[0],
        "generating_script",
        historical_records,
    )
    if payload.get("script") != expected_script:
        raise ClosurePipeSequenceError("ANFIS manifest script differs from the current fitter")
    dependencies = payload.get("dependencies")
    inputs = payload.get("inputs")
    if (
        not isinstance(dependencies, Sequence)
        or isinstance(dependencies, (str, bytes))
        or not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
    ):
        raise ClosurePipeSequenceError("ANFIS manifest inputs/dependencies must be arrays")
    dependency_records: dict[str, Mapping[str, Any]] = {}
    observed_roles: list[str] = []
    for record in dependencies:
        if not isinstance(record, Mapping) or set(record) != {
            "path",
            "bytes",
            "sha256",
            "role",
        }:
            raise ClosurePipeSequenceError("ANFIS dependency record dialect drifted")
        physical = _physical_manifest_record(
            record,
            context="ANFIS dependency",
            historical_records=historical_records,
        )
        path = str(physical["path"])
        if path in dependency_records:
            raise ClosurePipeSequenceError("ANFIS dependency paths must be unique")
        dependency_records[path] = record
        observed_roles.append(str(record.get("role")))
    if tuple(observed_roles) != ANFIS_DEPENDENCY_ROLES:
        raise ClosurePipeSequenceError("ANFIS dependency role order drifted")
    input_records: dict[str, Mapping[str, Any]] = {}
    for record in inputs:
        if not isinstance(record, Mapping) or set(record) != {
            "path",
            "bytes",
            "sha256",
            "role",
        }:
            raise ClosurePipeSequenceError("ANFIS input record dialect drifted")
        physical = _physical_manifest_record(
            record,
            context="ANFIS input",
            historical_records=historical_records,
        )
        path = str(physical["path"])
        if path in input_records:
            raise ClosurePipeSequenceError("ANFIS input paths must be unique")
        input_records[path] = record
    script_path = str(expected_script["path"])
    fitter_dependency = dependency_records.get(script_path)
    expected_fitter_dependency = _expected_anfis_source_record(
        ANFIS_REQUIRED_SOURCE_PATHS[0],
        "strict_anfis_state_adapter",
        historical_records,
    )
    if fitter_dependency != expected_fitter_dependency:
        raise ClosurePipeSequenceError("ANFIS dependencies omit the exact fitter script")
    if set(input_records) != set(dependency_records).difference({script_path}):
        raise ClosurePipeSequenceError("ANFIS inputs differ from dependencies minus script")
    for path in input_records:
        if dict(input_records[path]) != dict(dependency_records[path]):
            raise ClosurePipeSequenceError(f"ANFIS input/dependency record drifted: {path}")
    records_by_role = {str(record["role"]): record for record in dependency_records.values()}
    if len(records_by_role) != len(ANFIS_DEPENDENCY_ROLES):
        raise ClosurePipeSequenceError("ANFIS dependency roles must be unique")
    for role, path in ANFIS_SOURCE_ROLE_PATHS.items():
        expected_record = _expected_anfis_source_record(
            path,
            role,
            historical_records,
        )
        if records_by_role.get(role) != expected_record:
            raise ClosurePipeSequenceError(f"ANFIS source dependency role {role!r} drifted")

    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ClosurePipeSequenceError("ANFIS runtime provenance is missing")
    for prefix in ("config", "schema"):
        path = runtime.get(f"{prefix}_path")
        digest = runtime.get(f"{prefix}_sha256")
        if (
            not isinstance(path, str)
            or records_by_role.get(f"development_runtime_{prefix}", {}).get("path") != path
            or path not in input_records
            or input_records[path].get("sha256") != digest
        ):
            raise ClosurePipeSequenceError(f"ANFIS runtime {prefix} provenance drifted")
    runtime_config_path = str(runtime["config_path"])
    runtime_config_physical = PROJECT_ROOT / runtime_config_path
    try:
        with runtime_config_physical.open(encoding="utf-8") as handle:
            runtime_payload_raw = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ClosurePipeSequenceError("ANFIS runtime config is not valid YAML") from exc
    if not isinstance(runtime_payload_raw, Mapping):
        raise ClosurePipeSequenceError("ANFIS runtime config must contain a mapping")
    runtime_payload = runtime_payload_raw
    implementation = _runtime_section(runtime_payload, "implementation_lock")
    authority = _runtime_section(runtime_payload, "authority")
    anfis = _runtime_section(runtime_payload, "anfis")
    projection = _runtime_section(anfis, "source_projection")
    expected_role_paths = {
        "development_runtime_config": runtime_config_path,
        "development_runtime_schema": str(runtime["schema_path"]),
        "development_runtime_lock": str(implementation["lock_manifest_path"]),
        "development_runtime_lock_schema": str(implementation["lock_schema_path"]),
        "common_origin": str(authority["common_origin_manifest_path"]),
        "common_origin_completion_manifest": str(
            authority["common_origin_completion_manifest_path"]
        ),
        "restored_panel": str(projection["panel_path"]),
        "restored_expert_anchor": str(projection["expert_anchor_path"]),
        "holdout_assignment": DEFAULT_ASSIGNMENT.as_posix(),
        "holdout_manifest": DEFAULT_HOLDOUT_MANIFEST.as_posix(),
        "protocol_lock": DEFAULT_PROTOCOL_LOCK.as_posix(),
        **ANFIS_SOURCE_ROLE_PATHS,
    }
    for role, path in expected_role_paths.items():
        expected_record = _expected_anfis_source_record(
            path,
            role,
            historical_records,
        )
        if records_by_role.get(role) != expected_record:
            raise ClosurePipeSequenceError(f"ANFIS dependency role/path {role!r} drifted")

    authorization = payload.get("authorization")
    if not isinstance(authorization, Mapping):
        raise ClosurePipeSequenceError("ANFIS development authorization is missing")
    if set(authorization) != ANFIS_AUTHORIZATION_KEYS:
        raise ClosurePipeSequenceError("ANFIS development authorization dialect drifted")
    expected_authorization: dict[str, Any] = {
        "status": "locked",
        "device": "cpu",
        "fit_authorized": True,
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    expected_authorization.update(
        {
            field: True
            for field in (
                "locked_head_is_ancestor",
                "locked_parent_published_at_lock",
                "publication_verified",
                "tracking_ref_publication_verified",
                "remote_publication_verified",
                "canonical_origin_identity_verified",
                "metadata_verified",
                "physical_artifacts_required",
                "physical_artifacts_verified",
                "common_origin_output_verified",
                "expert_state_output_verified",
                "restored_development_sources_verified",
                "dvc_remote_verified_at_lock",
                "dvc_remote_verified",
                "payload_development_fit_authorized",
            )
        }
    )
    expected_authorization.update(
        {
            field: False
            for field in (
                "payload_evaluation_authorized",
                "payload_e0_u_authorized",
            )
        }
    )
    for field, value in expected_authorization.items():
        if not _typed_scalar_equal(authorization.get(field), value):
            raise ClosurePipeSequenceError(f"ANFIS authorization field {field!r} drifted")
    for field in (
        "locked_repository_head",
        "execution_head",
        "published_head",
        "remote_main_oid",
    ):
        value = authorization.get(field)
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{40}", value) is None
        ):
            raise ClosurePipeSequenceError(f"ANFIS authorization field {field!r} is invalid")
    if authorization.get("lock_version") != "closure_development_runtime_lock_v1":
        raise ClosurePipeSequenceError("ANFIS authorization lock_version drifted")
    published_ref = authorization.get("published_ref")
    if published_ref != "origin/main":
        raise ClosurePipeSequenceError("ANFIS authorization published_ref drifted")
    for field in ("component_count", "planned_artifact_path_count"):
        value = authorization.get(field)
        if type(value) is not int or value <= 0:
            raise ClosurePipeSequenceError(f"ANFIS authorization count {field!r} drifted")
    if not _is_sha256_text(authorization.get("planned_artifact_paths_sha256")):
        raise ClosurePipeSequenceError("ANFIS authorization planned-artifact digest drifted")
    predicates = authorization.get("fit_authorization_predicates")
    if (
        not isinstance(predicates, Mapping)
        or set(predicates) != ANFIS_AUTHORIZATION_PREDICATE_KEYS
        or any(value is not True for value in predicates.values())
    ):
        raise ClosurePipeSequenceError("ANFIS authorization predicate dialect drifted")
    lock_path = authorization.get("lock_path")
    if (
        not isinstance(lock_path, str)
        or records_by_role["development_runtime_lock"].get("path") != lock_path
        or lock_path not in input_records
        or input_records[lock_path].get("sha256") != authorization.get("lock_sha256")
    ):
        raise ClosurePipeSequenceError("ANFIS authorization lock provenance drifted")
    return runtime_payload, historical_context


def _is_sha256_text(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value).issubset(
        set("0123456789abcdef")
    )


def _typed_scalar_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _typed_scalar_equal(observed[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _typed_scalar_equal(observed_value, expected_value)
            for observed_value, expected_value in zip(observed, expected, strict=True)
        )
    return observed == expected


def _validate_anfis_scientific_manifest(
    payload: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    base_seed: int,
    dialect: str,
) -> None:
    common_keys = {
        "manifest_version",
        "generated_at_utc",
        "experiment_id",
        "surface_id",
        "model_id",
        "consumer_model_id",
        "base_seed",
        "module_substreams",
        "future_outcomes_accessed",
        "development_fit_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "authorization",
        "runtime",
        "cpu_execution_policy",
        "script",
        "inputs",
        "panel_anchor_joins",
        "dependencies",
        "completion_marker_written_last",
        "counts",
    }
    dialect_keys = {
        "status",
        "slot_status",
        "fit_status",
        "failure_reason",
        "retain_failed_seed_slot",
        "replacement_used",
        "failed_slot_replaced",
        "model_construction_attempted",
        "fit_attempted",
        "state_output_materialized",
        "state_artifact_emitted",
        "checkpoint_outputs_materialized",
        "module_metrics",
        "sampling",
        "failed_modules",
        "planned_unmaterialized_heavy_outputs",
        "outputs",
    }
    if set(payload) != common_keys.union(dialect_keys):
        raise ClosurePipeSequenceError("ANFIS top-level manifest dialect drifted")
    generated = payload.get("generated_at_utc")
    if not isinstance(generated, str):
        raise ClosurePipeSequenceError("ANFIS generated_at_utc is invalid")
    try:
        datetime.fromisoformat(generated)
    except ValueError as exc:
        raise ClosurePipeSequenceError("ANFIS generated_at_utc is invalid") from exc
    expected_substreams = anfis_module_substreams(base_seed)
    if payload.get("module_substreams") != expected_substreams:
        raise ClosurePipeSequenceError("ANFIS module substreams drifted")
    if not _typed_scalar_equal(
        payload.get("cpu_execution_policy"),
        expected_cpu_execution_policy_record(),
    ):
        raise ClosurePipeSequenceError("ANFIS CPU execution policy drifted")

    joins = payload.get("panel_anchor_joins")
    expected_join_scopes = {"training_candidates", "full_development"}
    if not isinstance(joins, Mapping) or set(joins) != expected_join_scopes:
        raise ClosurePipeSequenceError("ANFIS panel-anchor join scopes drifted")
    expected_join_keys = {
        "filtered_anchor_rows",
        "filtered_panel_rows",
        "matched_rows",
        "unmatched_anchor_rows",
        "unmatched_panel_rows",
        "anchor_keys_sha256",
        "panel_keys_sha256",
        "matched_keys_sha256",
        "unmatched_anchor_keys_sha256",
        "unmatched_panel_keys_sha256",
    }
    join_count_fields = {
        "filtered_anchor_rows",
        "filtered_panel_rows",
        "matched_rows",
        "unmatched_anchor_rows",
        "unmatched_panel_rows",
    }
    for scope in ("training_candidates", "full_development"):
        join = joins[scope]
        if not isinstance(join, Mapping) or set(join) != expected_join_keys:
            raise ClosurePipeSequenceError(
                f"ANFIS panel-anchor join audit dialect drifted: {scope}"
            )
        for field in join_count_fields:
            if type(join.get(field)) is not int or int(join[field]) < 0:
                raise ClosurePipeSequenceError(
                    f"ANFIS panel-anchor count {scope}.{field} drifted"
                )
        if int(join["filtered_anchor_rows"]) != int(join["matched_rows"]) + int(
            join["unmatched_anchor_rows"]
        ) or int(join["filtered_panel_rows"]) != int(join["matched_rows"]) + int(
            join["unmatched_panel_rows"]
        ):
            raise ClosurePipeSequenceError(
                f"ANFIS panel-anchor conservation drifted: {scope}"
            )
        if any(
            not _is_sha256_text(join[field])
            for field in expected_join_keys.difference(join_count_fields)
        ):
            raise ClosurePipeSequenceError(
                f"ANFIS panel-anchor digest drifted: {scope}"
            )

    sampling = payload.get("sampling")
    if not isinstance(sampling, Mapping) or set(sampling) != set(ANFIS_MODULES):
        raise ClosurePipeSequenceError("ANFIS sampling modules drifted")
    anfis_runtime = _runtime_section(runtime, "anfis")
    fixed_configuration = _runtime_section(anfis_runtime, "fixed_configuration")
    module_features = _runtime_section(anfis_runtime, "primary_module_features")
    uncertainty_proxy = _runtime_section(anfis_runtime, "uncertainty_proxy")
    rule_counts = _runtime_section(uncertainty_proxy, "rule_count_by_module")
    expected_dimensions = {
        module: len(cast(Sequence[Any], module_features[module])) for module in ANFIS_MODULES
    }
    zero_selected_modules: set[str] = set()
    for module in ANFIS_MODULES:
        audit = sampling[module]
        if not isinstance(audit, Mapping):
            raise ClosurePipeSequenceError(f"ANFIS sampling audit {module!r} is missing")
        required_keys = {
            "input_rows",
            "excluded_nonfinite_target_rows",
            "excluded_missingness_rows",
            "eligible_universe_rows",
            "eligible_universe_sha256",
            "selected_rows",
            "selected_keys_sha256",
            "module",
            "base_seed",
            "module_seed",
        }
        optional_unavailable = {"required_rows", "replacement_used", "failure_reason"}
        if set(audit) not in (required_keys, required_keys.union(optional_unavailable)):
            raise ClosurePipeSequenceError(f"ANFIS sampling audit {module!r} dialect drifted")
        if (
            audit.get("module") != module
            or type(audit.get("base_seed")) is not int
            or audit.get("base_seed") != base_seed
            or type(audit.get("module_seed")) is not int
            or audit.get("module_seed") != expected_substreams[module]
        ):
            raise ClosurePipeSequenceError(f"ANFIS sampling identity {module!r} drifted")
        for field in (
            "input_rows",
            "excluded_nonfinite_target_rows",
            "excluded_missingness_rows",
            "eligible_universe_rows",
            "selected_rows",
        ):
            if type(audit.get(field)) is not int or int(audit[field]) < 0:
                raise ClosurePipeSequenceError(f"ANFIS sampling count {module}.{field} drifted")
        selected_rows = int(audit["selected_rows"])
        if (
            audit["input_rows"] != joins["training_candidates"]["matched_rows"]
            or audit["input_rows"]
            != audit["excluded_nonfinite_target_rows"]
            + audit["excluded_missingness_rows"]
            + audit["eligible_universe_rows"]
        ):
            raise ClosurePipeSequenceError(
                f"ANFIS sampling conservation {module!r} drifted"
            )
        if selected_rows not in {0, 4096} or int(audit["eligible_universe_rows"]) < selected_rows:
            raise ClosurePipeSequenceError(f"ANFIS selected-row contract {module!r} drifted")
        if dialect != "unavailable_not_attempted" and selected_rows != 4096:
            raise ClosurePipeSequenceError(f"Fitted ANFIS module {module!r} lacks 4096 keys")
        if selected_rows == 0:
            zero_selected_modules.add(module)
            if (
                set(audit) != required_keys.union(optional_unavailable)
                or audit.get("required_rows") != 4096
                or audit.get("replacement_used") is not False
                or audit.get("failure_reason") != "insufficient_eligible_training_rows"
            ):
                raise ClosurePipeSequenceError(
                    f"Unavailable ANFIS sampling evidence {module!r} drifted"
                )
        elif set(audit) != required_keys:
            raise ClosurePipeSequenceError(f"Available ANFIS sampling evidence {module!r} drifted")
        if not _is_sha256_text(audit.get("eligible_universe_sha256")) or not _is_sha256_text(
            audit.get("selected_keys_sha256")
        ):
            raise ClosurePipeSequenceError(f"ANFIS sampling digest {module!r} drifted")
    if dialect == "unavailable_not_attempted" and not zero_selected_modules:
        raise ClosurePipeSequenceError("Unavailable ANFIS slot has no insufficient module")

    metrics = payload.get("module_metrics")
    if not isinstance(metrics, Sequence) or isinstance(metrics, (str, bytes)) or len(metrics) != 3:
        raise ClosurePipeSequenceError("ANFIS module metrics must contain three records")
    metric_by_module = {
        str(record.get("module")): record for record in metrics if isinstance(record, Mapping)
    }
    if set(metric_by_module) != set(ANFIS_MODULES) or len(metric_by_module) != len(metrics):
        raise ClosurePipeSequenceError("ANFIS module metric identities drifted")
    for module, metric in metric_by_module.items():
        if (
            type(metric.get("base_seed")) is not int
            or metric.get("base_seed") != base_seed
            or type(metric.get("module_seed")) is not int
            or metric.get("module_seed") != expected_substreams[module]
        ):
            raise ClosurePipeSequenceError(f"ANFIS module metric seed {module!r} drifted")
        if dialect == "unavailable_not_attempted":
            expected_metric_keys = {
                "module",
                "status",
                "failure_reason",
                "base_seed",
                "module_seed",
                "input_rows",
                "excluded_nonfinite_target_rows",
                "excluded_missingness_rows",
                "eligible_universe_rows",
                "selected_rows",
                "required_rows",
                "replacement_used",
                "fit_attempted",
            }
            if (
                set(metric) != expected_metric_keys
                or metric.get("fit_attempted") is not False
                or type(metric.get("selected_rows")) is not int
                or type(metric.get("required_rows")) is not int
                or metric.get("replacement_used") is not False
            ):
                raise ClosurePipeSequenceError(f"Unavailable ANFIS metric {module!r} drifted")
            sampling_audit = sampling[module]
            unavailable_count_fields = (
                    "input_rows",
                    "excluded_nonfinite_target_rows",
                    "excluded_missingness_rows",
                    "eligible_universe_rows",
                    "selected_rows",
            )
            if any(
                type(metric.get(field)) is not int
                or metric.get(field) != sampling_audit.get(field)
                for field in unavailable_count_fields
            ) or metric.get("required_rows") != 4096:
                raise ClosurePipeSequenceError(
                    f"ANFIS unavailable metric/sampling evidence {module!r} drifted"
                )
            expected_unavailable_status = (
                ("model_unavailable", "insufficient_eligible_training_rows")
                if sampling_audit.get("selected_rows") == 0
                else ("not_fitted_due_to_slot_unavailable", "paired_slot_unavailable")
            )
            if (
                metric.get("status"),
                metric.get("failure_reason"),
            ) != expected_unavailable_status:
                raise ClosurePipeSequenceError(
                    f"ANFIS unavailable metric status {module!r} drifted"
                )
        else:
            expected_metric_keys = {
                "module",
                "status",
                "base_seed",
                "module_seed",
                "train_rows",
                "prediction_rows",
                "input_dimension",
                "rule_count",
                "epochs",
                "curve_initial_pre_update_loss",
                "curve_last_pre_update_loss",
                "minimum_curve_pre_update_loss",
                "final_checkpoint_loss",
                "quality_gate_output_standard_deviation",
                "quality_gate_output_scope",
                "materialized_surface_output_standard_deviation",
                "maximum_parameter_delta",
                "centers_ordered",
                "centers_in_unit_interval",
            }
            if (
                set(metric) != expected_metric_keys
                or type(metric.get("train_rows")) is not int
                or metric.get("train_rows") != 4096
                or type(metric.get("prediction_rows")) is not int
                or type(metric.get("input_dimension")) is not int
                or type(metric.get("rule_count")) is not int
                or type(metric.get("epochs")) is not int
                or type(metric.get("centers_ordered")) is not bool
                or type(metric.get("centers_in_unit_interval")) is not bool
                or metric.get("input_dimension") != expected_dimensions[module]
                or metric.get("rule_count") != rule_counts[module]
                or metric.get("epochs") != fixed_configuration["epochs"]
                or metric.get("prediction_rows")
                != joins["full_development"]["matched_rows"]
                or metric.get("quality_gate_output_scope")
                != "locked_hash_ranked_training_sample_4096"
            ):
                raise ClosurePipeSequenceError(f"Fitted ANFIS metric {module!r} drifted")
            numeric_metrics = (
                "curve_initial_pre_update_loss",
                "curve_last_pre_update_loss",
                "minimum_curve_pre_update_loss",
                "final_checkpoint_loss",
                "quality_gate_output_standard_deviation",
                "materialized_surface_output_standard_deviation",
                "maximum_parameter_delta",
            )
            if any(
                isinstance(metric.get(field), bool)
                or not isinstance(metric.get(field), (int, float))
                or not math.isfinite(float(metric[field]))
                or float(metric[field]) < 0.0
                for field in numeric_metrics
            ):
                raise ClosurePipeSequenceError(
                    f"ANFIS metric numeric evidence {module!r} drifted"
                )
            expected_status = (
                "passed"
                if float(metric["quality_gate_output_standard_deviation"])
                >= float(fixed_configuration["min_output_standard_deviation"])
                and float(metric["maximum_parameter_delta"]) > 0.0
                and metric["centers_ordered"] is True
                and metric["centers_in_unit_interval"] is True
                else "failed"
            )
            if metric.get("status") != expected_status:
                raise ClosurePipeSequenceError(
                    f"ANFIS metric quality-gate status {module!r} drifted"
                )
            if metric.get("status") == "passed" and (
                metric.get("centers_ordered") is not True
                or metric.get("centers_in_unit_interval") is not True
            ):
                raise ClosurePipeSequenceError(
                    f"Passed ANFIS metric quality flags {module!r} drifted"
                )
    statuses = {str(metric["status"]) for metric in metric_by_module.values()}
    if dialect == "available" and statuses != {"passed"}:
        raise ClosurePipeSequenceError("Available ANFIS module statuses drifted")
    if dialect == "unavailable_failed" and "failed" not in statuses:
        raise ClosurePipeSequenceError("Failed ANFIS slot has no failed module")
    failed_modules = payload.get("failed_modules")
    if not isinstance(failed_modules, Sequence) or isinstance(
        failed_modules, (str, bytes)
    ):
        raise ClosurePipeSequenceError("ANFIS failed_modules must be an array")
    expected_failed_modules = {
        module for module, metric in metric_by_module.items() if metric.get("status") != "passed"
    }
    if len(failed_modules) != len(set(failed_modules)) or set(failed_modules) != (
        zero_selected_modules
        if dialect == "unavailable_not_attempted"
        else expected_failed_modules
    ):
        raise ClosurePipeSequenceError("ANFIS failed_modules drifted")

    counts = payload.get("counts")
    if not isinstance(counts, Mapping):
        raise ClosurePipeSequenceError("ANFIS counts are missing")
    if dialect == "unavailable_not_attempted":
        expected_count_keys = {
            "state_rows",
            "joined_development_rows",
            "joined_training_candidate_rows",
            "development_locations",
            "unavailable_modules",
        }
        if (
            set(counts) != expected_count_keys
            or type(counts.get("state_rows")) is not int
            or counts.get("state_rows") != 0
            or type(counts.get("development_locations")) is not int
            or type(counts.get("unavailable_modules")) is not int
            or counts.get("unavailable_modules") != len(zero_selected_modules)
        ):
            raise ClosurePipeSequenceError("Unavailable ANFIS counts/failed modules drifted")
        planned = payload.get("planned_unmaterialized_heavy_outputs")
        slot_paths = _expected_anfis_slot_paths(runtime, base_seed=base_seed)
        expected_planned = [
            slot_paths["anfis_state_template"],
            *(slot_paths["models"][module] for module in ANFIS_MODULES),
        ]
        if (
            not isinstance(planned, Sequence)
            or isinstance(planned, (str, bytes))
            or list(planned) != expected_planned
        ):
            raise ClosurePipeSequenceError("Unavailable ANFIS planned heavy outputs drifted")
    else:
        expected_count_keys = {
            "state_rows",
            "joined_development_rows",
            "joined_training_candidate_rows",
            "development_locations",
            "delta_previous_month_missing",
        }
        if (
            set(counts) != expected_count_keys
            or type(counts.get("state_rows")) is not int
            or int(counts["state_rows"]) <= 0
            or type(counts.get("development_locations")) is not int
            or int(counts["development_locations"]) <= 0
            or type(counts.get("delta_previous_month_missing")) is not int
            or not 0 <= int(counts["delta_previous_month_missing"]) <= int(counts["state_rows"])
            or counts.get("state_rows") != joins["full_development"]["matched_rows"]
        ):
            raise ClosurePipeSequenceError("Fitted ANFIS counts drifted")
    if (
        type(counts.get("joined_development_rows")) is not int
        or type(counts.get("joined_training_candidate_rows")) is not int
        or counts["joined_development_rows"] != joins["full_development"]["matched_rows"]
        or counts["joined_training_candidate_rows"]
        != joins["training_candidates"]["matched_rows"]
    ):
        raise ClosurePipeSequenceError("ANFIS counts differ from panel-anchor joins")
    planned = payload.get("planned_unmaterialized_heavy_outputs")
    if dialect != "unavailable_not_attempted" and planned != []:
        raise ClosurePipeSequenceError("Fitted ANFIS slot has planned unmaterialized outputs")


def _format_anfis_artifact_path(
    runtime: Mapping[str, Any],
    field: str,
    *,
    base_seed: int,
    module: str | None = None,
) -> str:
    artifacts = _runtime_section(runtime, "artifacts")
    template = artifacts.get(field)
    if not isinstance(template, str):
        raise ClosurePipeSequenceError(f"ANFIS artifact template {field!r} is missing")
    try:
        raw = template.format(base_seed=base_seed, module=module)
    except (KeyError, ValueError) as exc:
        raise ClosurePipeSequenceError(f"ANFIS artifact template {field!r} is invalid") from exc
    logical = Path(raw)
    if logical.is_absolute() or ".." in logical.parts or logical.as_posix() != raw:
        raise ClosurePipeSequenceError(f"ANFIS artifact template {field!r} is not canonical")
    return raw


def _expected_anfis_slot_paths(
    runtime: Mapping[str, Any],
    *,
    base_seed: int,
    historical_uppercase_artifact_paths: bool = False,
) -> dict[str, Any]:
    paths: dict[str, Any] = {
        field: _format_anfis_artifact_path(runtime, field, base_seed=base_seed)
        for field in (
            "anfis_state_template",
            "anfis_metrics_template",
            "anfis_training_curve_template",
            "anfis_memberships_initial_template",
            "anfis_memberships_final_template",
            "anfis_report_template",
            "anfis_lineage_audit_template",
        )
    }
    paths["models"] = {
        module: _format_anfis_artifact_path(
            runtime,
            "anfis_model_template",
            base_seed=base_seed,
            module=(
                module
                if historical_uppercase_artifact_paths
                else ANFIS_MODULE_ARTIFACT_TOKENS[module]
            ),
        )
        for module in ANFIS_MODULES
    }
    paths["samples"] = {
        module: _format_anfis_artifact_path(
            runtime,
            "anfis_sample_keys_template",
            base_seed=base_seed,
            module=(
                module
                if historical_uppercase_artifact_paths
                else ANFIS_MODULE_ARTIFACT_TOKENS[module]
            ),
        )
        for module in ANFIS_MODULES
    }
    return paths


def _anfis_key_digest(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    keys = list(
        zip(
            frame["source_id"].astype(str),
            frame["site_id"].astype(str),
            frame["year_month"].astype(str),
            strict=True,
        )
    )
    for key in keys:
        key_bytes = json.dumps(
            list(key),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(key_bytes)
        digest.update(b"\n")
    return digest.hexdigest()


def _csv_scalar_matches(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return isinstance(observed, (bool, np.bool_)) and bool(observed) is expected
    if isinstance(expected, int) and not isinstance(expected, bool):
        return (
            isinstance(observed, (int, np.integer))
            and not isinstance(observed, (bool, np.bool_))
            and int(observed) == expected
        )
    if isinstance(expected, float):
        try:
            numeric = float(observed)
        except (TypeError, ValueError):
            return False
        return math.isfinite(numeric) and math.isclose(
            numeric,
            expected,
            rel_tol=1e-12,
            abs_tol=1e-15,
        )
    return observed == expected


def _validate_anfis_csv_evidence(
    payload: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    paths: Mapping[str, Any],
) -> None:
    sampling = cast(Mapping[str, Mapping[str, Any]], payload["sampling"])
    persisted = _runtime_section(_runtime_section(runtime, "anfis"), "sampling").get(
        "persisted_sample_columns"
    )
    if not isinstance(persisted, Sequence) or isinstance(persisted, (str, bytes)):
        raise ClosurePipeSequenceError("ANFIS persisted sample-column contract is invalid")
    expected_columns = [str(value) for value in persisted]
    for module in ANFIS_MODULES:
        frame = pd.read_csv(
            PROJECT_ROOT / str(paths["samples"][module]),
            dtype=str,
        )
        audit = sampling[module]
        if frame.columns.tolist() != expected_columns or len(frame) != audit["selected_rows"]:
            raise ClosurePipeSequenceError(f"ANFIS sample CSV schema/count drifted: {module}")
        if bool(frame.duplicated(["source_id", "site_id", "year_month"], keep=False).any()):
            raise ClosurePipeSequenceError(f"ANFIS sample CSV keys are duplicated: {module}")
        if len(frame):
            seeds = pd.to_numeric(frame["module_seed"], errors="coerce")
            seed_values = seeds.to_numpy(dtype=np.float64)
            for column in ("source_id", "site_id", "year_month", "module", "rank_sha256"):
                values = frame[column].tolist()
                if any(
                    not isinstance(value, str)
                    or not value
                    or value != value.strip()
                    or value != unicodedata.normalize("NFC", value)
                    for value in values
                ):
                    raise ClosurePipeSequenceError(
                        f"ANFIS sample CSV string identity drifted: {module}.{column}"
                    )
            if set(frame["source_id"]) != {"wqp"} or any(
                re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value) is None
                or value > "2018-12"
                for value in frame["year_month"]
            ):
                raise ClosurePipeSequenceError(
                    f"ANFIS sample CSV development key scope drifted: {module}"
                )
            ranked: list[tuple[str, bytes, bytes, str]] = []
            observed_rank = frame["rank_sha256"].astype(str).tolist()
            for row in frame.to_dict(orient="records"):
                key = (
                    str(row["source_id"]),
                    str(row["site_id"]),
                    str(row["year_month"]),
                )
                rank_payload = json.dumps(
                    [int(audit["module_seed"]), *key],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                rank = hashlib.sha256(rank_payload).hexdigest()
                if str(row["rank_sha256"]) != rank:
                    raise ClosurePipeSequenceError(
                        f"ANFIS sample CSV rank digest drifted: {module}"
                    )
                ranked.append(
                    (rank, key[0].encode("utf-8"), key[1].encode("utf-8"), key[2])
                )
            if (
                set(frame["module"].astype(str)) != {module}
                or bool(seeds.isna().any())
                or not np.isfinite(seed_values).all()
                or not np.equal(seed_values, np.floor(seed_values)).all()
                or not bool(seeds.eq(audit["module_seed"]).all())
                or not frame["rank_sha256"].map(_is_sha256_text).all()
                or ranked != sorted(ranked)
                or observed_rank != [record[0] for record in ranked]
            ):
                raise ClosurePipeSequenceError(f"ANFIS sample CSV identity drifted: {module}")
        if _anfis_key_digest(frame) != audit["selected_keys_sha256"]:
            raise ClosurePipeSequenceError(f"ANFIS sample CSV digest drifted: {module}")

    metrics = cast(Sequence[Mapping[str, Any]], payload["module_metrics"])
    metrics_path = PROJECT_ROOT / str(paths["anfis_metrics_template"])
    frame = pd.read_csv(metrics_path)
    metric_columns = (
        ANFIS_FITTED_MODULE_METRIC_COLUMNS
        if payload.get("fit_attempted") is True
        else ANFIS_UNAVAILABLE_MODULE_METRIC_COLUMNS
    )
    if frame.columns.tolist() != list(metric_columns) or len(frame) != len(ANFIS_MODULES):
        raise ClosurePipeSequenceError("ANFIS module-metrics CSV schema/count drifted")
    records = frame.to_dict(orient="records")
    for observed, expected, module in zip(records, metrics, ANFIS_MODULES, strict=True):
        if expected.get("module") != module or any(
            not _csv_scalar_matches(observed.get(field), value)
            for field, value in expected.items()
        ):
            raise ClosurePipeSequenceError(
                f"ANFIS module-metrics CSV differs from manifest: {module}"
            )


def _validate_anfis_outputs(
    payload: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    base_seed: int,
    state_path: Path,
    fitted_outputs_expected: bool,
    historical_uppercase_artifact_paths: bool = False,
) -> None:
    slot_paths = _expected_anfis_slot_paths(
        runtime,
        base_seed=base_seed,
        historical_uppercase_artifact_paths=historical_uppercase_artifact_paths,
    )
    if _repo_path(state_path) != slot_paths["anfis_state_template"]:
        raise ClosurePipeSequenceError("ANFIS state path differs from its runtime template")
    raw_outputs = payload.get("outputs")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise ClosurePipeSequenceError("ANFIS outputs must be an array")
    records: list[Mapping[str, Any]] = []
    paths: set[str] = set()
    for record in raw_outputs:
        if not isinstance(record, Mapping):
            raise ClosurePipeSequenceError("ANFIS output record dialect drifted")
        role = str(record.get("role"))
        expected_keys = {"path", "bytes", "sha256", "role"}
        if role in {"anfis_checkpoint", "sample_keys"}:
            expected_keys.add("module")
        if set(record) != expected_keys:
            raise ClosurePipeSequenceError("ANFIS output record keys drifted")
        physical = _physical_manifest_record(record, context="ANFIS output")
        path = str(physical["path"])
        if path in paths:
            raise ClosurePipeSequenceError("ANFIS output paths must be unique")
        paths.add(path)
        records.append(record)
    role_records: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        role_records.setdefault(str(record.get("role")), []).append(record)
    module_roles = ("anfis_checkpoint", "sample_keys")
    for role in module_roles:
        modules = {str(record.get("module")) for record in role_records.get(role, [])}
        expected_modules = set(ANFIS_MODULES) if fitted_outputs_expected or role == "sample_keys" else set()
        if len(role_records.get(role, [])) != len(expected_modules) or modules != expected_modules:
            raise ClosurePipeSequenceError(f"ANFIS outputs have invalid {role} module records")
    singleton_roles = {"module_metrics", "report", "lineage_audit"}
    if fitted_outputs_expected:
        singleton_roles.update(
            {"adaptive_no_current_state", "training_curve", "memberships_initial", "memberships_final"}
        )
    expected_roles = singleton_roles.union({"sample_keys"})
    if fitted_outputs_expected:
        expected_roles.add("anfis_checkpoint")
    if set(role_records) != expected_roles:
        raise ClosurePipeSequenceError("ANFIS output role dialect drifted")
    for role in singleton_roles:
        if len(role_records.get(role, [])) != 1:
            raise ClosurePipeSequenceError(f"ANFIS output role {role!r} must occur exactly once")
    if fitted_outputs_expected:
        state_record = role_records["adaptive_no_current_state"][0]
        if state_record.get("path") != _repo_path(state_path):
            raise ClosurePipeSequenceError("ANFIS state output path drifted")
    expected_records: list[dict[str, Any]] = []
    if fitted_outputs_expected:
        expected_records.append(
            {
                **_file_record(PROJECT_ROOT / slot_paths["anfis_state_template"]),
                "role": "adaptive_no_current_state",
            }
        )
        for module in ANFIS_MODULES:
            expected_records.extend(
                [
                    {
                        **_file_record(PROJECT_ROOT / slot_paths["models"][module]),
                        "role": "anfis_checkpoint",
                        "module": module,
                    },
                    {
                        **_file_record(PROJECT_ROOT / slot_paths["samples"][module]),
                        "role": "sample_keys",
                        "module": module,
                    },
                ]
            )
    else:
        for module in ANFIS_MODULES:
            expected_records.append(
                {
                    **_file_record(PROJECT_ROOT / slot_paths["samples"][module]),
                    "role": "sample_keys",
                    "module": module,
                }
            )
    singleton_fields = [
        ("anfis_metrics_template", "module_metrics"),
        *(
            [
                ("anfis_training_curve_template", "training_curve"),
                ("anfis_memberships_initial_template", "memberships_initial"),
                ("anfis_memberships_final_template", "memberships_final"),
            ]
            if fitted_outputs_expected
            else []
        ),
        ("anfis_report_template", "report"),
        ("anfis_lineage_audit_template", "lineage_audit"),
    ]
    expected_records.extend(
        {
            **_file_record(PROJECT_ROOT / slot_paths[field]),
            "role": role,
        }
        for field, role in singleton_fields
    )
    if [dict(record) for record in records] != expected_records:
        raise ClosurePipeSequenceError("ANFIS output paths/order differ from runtime templates")
    _validate_anfis_csv_evidence(payload, runtime=runtime, paths=slot_paths)


def validate_state_slot_manifest(
    payload: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int | None,
    state_path: Path,
) -> tuple[bool, str, bool]:
    """Validate upstream P0/F1 completion and its physical state linkage."""
    common_expected = {
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, expected in common_expected.items():
        if not _typed_scalar_equal(payload.get(field), expected):
            raise ClosurePipeSequenceError(f"State manifest field {field!r} drifted")
    if model_id == "P0":
        if payload.get("model_id") != "P0":
            raise ClosurePipeSequenceError("Expert-state manifest model_id must be P0")
        if not state_path.is_file():
            raise ClosurePipeSequenceError("Completed P0 state manifest has no state Parquet")
        record = _output_record_for_path(payload, state_path, role="expert_no_current_state")
        if any(record.get(key) != value for key, value in _file_record(state_path).items()):
            raise ClosurePipeSequenceError("P0 state record differs from the physical Parquet")
        return True, "", False

    if model_id != "P1" or base_seed not in REGISTERED_SEEDS:
        raise ClosurePipeSequenceError("State-slot validation received an invalid P1 seed")
    expected_identity = {
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": base_seed,
        "failed_slot_replaced": False,
    }
    for field, expected in expected_identity.items():
        if not _typed_scalar_equal(payload.get(field), expected):
            raise ClosurePipeSequenceError(f"ANFIS state manifest field {field!r} drifted")
    runtime, historical_context = _validate_anfis_provenance(payload)
    historical_uppercase_artifact_paths = historical_context is not None
    slot_status = payload.get("slot_status")
    if slot_status == "available":
        expected_available = {
            "fit_status": "passed",
            "failure_reason": "",
            "state_artifact_emitted": True,
            "state_output_materialized": True,
            "checkpoint_outputs_materialized": True,
            "model_construction_attempted": True,
            "fit_attempted": True,
            "replacement_used": False,
            "retain_failed_seed_slot": False,
        }
        if any(
            not _typed_scalar_equal(payload.get(field), value)
            for field, value in expected_available.items()
        ):
            raise ClosurePipeSequenceError("Available ANFIS slot has inconsistent fit/artifact flags")
        _validate_anfis_scientific_manifest(
            payload,
            runtime=runtime,
            base_seed=base_seed,
            dialect="available",
        )
        if not state_path.is_file():
            raise ClosurePipeSequenceError("Available ANFIS slot has no state Parquet")
        _validate_anfis_outputs(
            payload,
            runtime=runtime,
            base_seed=base_seed,
            state_path=state_path,
            fitted_outputs_expected=True,
            historical_uppercase_artifact_paths=historical_uppercase_artifact_paths,
        )
        return True, "", False
    if slot_status != "model_unavailable":
        raise ClosurePipeSequenceError("ANFIS state manifest has an unknown slot_status")
    fit_status = payload.get("fit_status")
    if fit_status == "not_attempted":
        expected_unavailable = {
            "failure_reason": "insufficient_eligible_training_rows",
            "state_artifact_emitted": False,
            "replacement_used": False,
            "state_output_materialized": False,
            "checkpoint_outputs_materialized": False,
            "model_construction_attempted": False,
            "fit_attempted": False,
            "retain_failed_seed_slot": True,
        }
        diagnostic_state_declared = False
    elif fit_status == "failed":
        expected_unavailable = {
            "failure_reason": "module_fit_quality_gate_failed",
            "state_artifact_emitted": True,
            "replacement_used": False,
            "state_output_materialized": True,
            "checkpoint_outputs_materialized": True,
            "model_construction_attempted": True,
            "fit_attempted": True,
            "retain_failed_seed_slot": True,
        }
        diagnostic_state_declared = True
    else:
        raise ClosurePipeSequenceError("Unavailable ANFIS slot has an unknown fit_status")
    for field, expected in expected_unavailable.items():
        if not _typed_scalar_equal(payload.get(field), expected):
            raise ClosurePipeSequenceError(f"Unavailable ANFIS field {field!r} drifted")
    _validate_anfis_scientific_manifest(
        payload,
        runtime=runtime,
        base_seed=base_seed,
        dialect=(
            "unavailable_not_attempted"
            if fit_status == "not_attempted"
            else "unavailable_failed"
        ),
    )
    outputs = payload.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise ClosurePipeSequenceError("Unavailable ANFIS outputs must be an array")
    if diagnostic_state_declared:
        if not state_path.is_file():
            raise ClosurePipeSequenceError("Failed ANFIS quality slot lacks its diagnostic state")
        _validate_anfis_outputs(
            payload,
            runtime=runtime,
            base_seed=base_seed,
            state_path=state_path,
            fitted_outputs_expected=True,
            historical_uppercase_artifact_paths=historical_uppercase_artifact_paths,
        )
    else:
        heavy = [
            record
            for record in outputs
            if isinstance(record, Mapping)
            and (
                record.get("path") == _repo_path(state_path)
                or str(record.get("path", "")).endswith(".pt")
            )
        ]
        if state_path.exists() or heavy:
            raise ClosurePipeSequenceError(
                "Pre-fit unavailable ANFIS slot retains a state/checkpoint artifact"
            )
        _validate_anfis_outputs(
            payload,
            runtime=runtime,
            base_seed=base_seed,
            state_path=state_path,
            fitted_outputs_expected=False,
            historical_uppercase_artifact_paths=historical_uppercase_artifact_paths,
        )
    return False, str(payload["failure_reason"]), diagnostic_state_declared


def _write_json_atomic(payload: Mapping[str, Any], path: Path) -> None:
    def write(handle: Any) -> None:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    _write_output_no_clobber(path, write, binary=False)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    _write_output_no_clobber(
        path,
        lambda handle: frame.to_csv(handle, index=False),
        binary=False,
    )


def _paths(model_id: str, base_seed: int | None) -> dict[str, Path]:
    if model_id == "P0":
        return {
            "state": Path("data/closure_v1/development/expert/expert_no_current_state.parquet"),
            "state_manifest": Path(
                "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"
            ),
            "sequence": Path("data/closure_v1/development/sequences/P0/expert_no_current.parquet"),
            "summary": Path("reports/closure_v1/01_surface/sequences/P0/expert_no_current_summary.csv"),
            "manifest": Path("reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"),
        }
    assert base_seed is not None
    return {
        "state": Path(f"data/closure_v1/development/anfis/seed_{base_seed}/adaptive_no_current_state.parquet"),
        "state_manifest": Path(
            f"reports/closure_v1/01_surface/anfis/seed_{base_seed}/manifest.json"
        ),
        "sequence": Path(f"data/closure_v1/development/sequences/P1/seed_{base_seed}.parquet"),
        "summary": Path(f"reports/closure_v1/01_surface/sequences/P1/seed_{base_seed}_summary.csv"),
        "manifest": Path(f"reports/closure_v1/01_surface/sequences/P1/seed_{base_seed}_manifest.json"),
    }


def _sequence_guard_directory() -> Path:
    tmp_root = PROJECT_ROOT / "tmp"
    guard_directory = tmp_root / "closure_v1_sequence_builder"
    for directory in (tmp_root, guard_directory):
        directory.mkdir(mode=0o700, exist_ok=True)
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise ClosurePipeSequenceError(
                f"Sequence coordination path is not a real directory: {directory}"
            )
    try:
        guard_directory.resolve(strict=True).relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ClosurePipeSequenceError("Sequence coordination path escapes the repository") from exc
    return guard_directory


@contextmanager
def _sequence_bundle_guard(
    model_id: str,
    base_seed: int | None,
) -> Iterator[None]:
    guard_directory = _sequence_guard_directory()
    guard_name = "P0.guard" if model_id == "P0" else f"P1_seed_{base_seed}.guard"
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_descriptor = os.open(guard_directory, directory_flags)
    descriptor: int | None = None
    owned_device: int | None = None
    owned_inode: int | None = None
    try:
        opened_directory = os.fstat(directory_descriptor)
        lexical_directory = guard_directory.lstat()
        if (
            (opened_directory.st_dev, opened_directory.st_ino)
            != (lexical_directory.st_dev, lexical_directory.st_ino)
        ):
            raise ClosurePipeSequenceError("Sequence coordination directory identity drifted")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                guard_name,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise ClosurePipeSequenceError(
                f"A sequence bundle build is already reserved: {guard_name}"
            ) from exc
        owned = os.fstat(descriptor)
        if not stat.S_ISREG(owned.st_mode):
            raise ClosurePipeSequenceError("Sequence bundle guard is not a regular file")
        owned_device, owned_inode = owned.st_dev, owned.st_ino
        yield
        current = os.stat(
            guard_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        lexical_directory = guard_directory.lstat()
        if (
            not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino) != (owned_device, owned_inode)
            or (lexical_directory.st_dev, lexical_directory.st_ino)
            != (opened_directory.st_dev, opened_directory.st_ino)
        ):
            raise ClosurePipeSequenceError("Sequence bundle guard changed during construction")
    finally:
        if owned_device is not None and owned_inode is not None:
            _unlink_name_if_owned(
                directory_descriptor,
                guard_name,
                device=owned_device,
                inode=owned_inode,
            )
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def assert_sequence_outputs_absent(paths: Mapping[str, Path]) -> None:
    """Keep sequence completion bundles one-shot and fail on partial evidence."""
    output_names = ("sequence", "summary", "manifest")
    if not set(output_names).issubset(paths):
        raise ClosurePipeSequenceError("Sequence output path set is incomplete")
    candidates = [
        candidate
        for name in output_names
        for path in (PROJECT_ROOT / paths[name],)
        for candidate in (path, path.with_suffix(path.suffix + ".tmp"))
    ]
    sequence_path = PROJECT_ROOT / paths["sequence"]
    pointer = Path(f"{sequence_path.as_posix()}.dvc")
    candidates.extend((pointer, pointer.with_suffix(pointer.suffix + ".tmp")))
    existing = [path.as_posix() for path in candidates if _path_entry_exists(path)]
    if existing:
        raise ClosurePipeSequenceError(
            "Sequence overwrite is forbidden; existing bundle artifacts require "
            f"explicit review and cleanup: {existing}"
        )


def assert_sequence_pointer_absent(paths: Mapping[str, Path]) -> None:
    """Forbid concurrent DVC registration while a sequence bundle is built."""
    if "sequence" not in paths:
        raise ClosurePipeSequenceError("Sequence path set is incomplete")
    sequence_path = PROJECT_ROOT / paths["sequence"]
    pointer = Path(f"{sequence_path.as_posix()}.dvc")
    candidates = (pointer, pointer.with_suffix(pointer.suffix + ".tmp"))
    existing = [path.as_posix() for path in candidates if _path_entry_exists(path)]
    if existing:
        raise ClosurePipeSequenceError(
            f"Concurrent DVC registration is forbidden during sequence build: {existing}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict Closure V1 P0/P1 sequence windows.")
    parser.add_argument("--model-id", choices=MODEL_IDS, required=True)
    parser.add_argument("--base-seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # The external authorization check is deliberately the first operation in
    # main that may read repository artifacts.  There is no unlocked CLI mode.
    from src.experiments.closure_development_runtime_temporal_consumer_patch import (
        require_development_fit_authorized_with_temporal_consumer_patch,
    )

    require_development_fit_authorized_with_temporal_consumer_patch()
    runtime = load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
    validate_sequence_runtime_contract(runtime)
    cpu_execution_policy = configure_torch_cpu_execution_policy(runtime)
    if cpu_execution_policy != expected_cpu_execution_policy_record():
        raise ClosurePipeSequenceError("Applied CPU execution policy drifted")
    validate_model_seed(args.model_id, args.base_seed)
    paths = _paths(args.model_id, args.base_seed)
    with _sequence_bundle_guard(args.model_id, args.base_seed):
        assert_sequence_outputs_absent(paths)
        _materialize_sequence_bundle(
            args,
            runtime=runtime,
            cpu_execution_policy=cpu_execution_policy,
            paths=paths,
        )


def _materialize_sequence_bundle(
    args: argparse.Namespace,
    *,
    runtime: Mapping[str, Any],
    cpu_execution_policy: Mapping[str, Any],
    paths: Mapping[str, Path],
) -> None:
    gate = load_development_gate()

    state_path = PROJECT_ROOT / paths["state"]
    state_manifest_path = PROJECT_ROOT / paths["state_manifest"]
    common_path = PROJECT_ROOT / DEFAULT_COMMON_ORIGINS
    if not state_manifest_path.is_file():
        raise ClosurePipeSequenceError("A state slot requires its completion manifest")
    dependency_paths = [
        common_path,
        PROJECT_ROOT / DEFAULT_COMMON_COMPLETION,
        PROJECT_ROOT / DEFAULT_RUNTIME_CONFIG,
        PROJECT_ROOT / DEFAULT_RUNTIME_SCHEMA,
        PROJECT_ROOT / DEFAULT_RUNTIME_LOCK,
        gate.assignment_path,
        gate.holdout_manifest_path,
        gate.protocol_lock_path,
        Path(__file__),
        state_manifest_path,
    ]
    before = {_repo_path(path): _file_record(path) for path in dependency_paths}
    with state_manifest_path.open(encoding="utf-8") as handle:
        state_manifest = json.load(handle)
    if not isinstance(state_manifest, Mapping):
        raise ClosurePipeSequenceError("State manifest must contain a JSON object")
    state_available, model_slot_failure_reason, diagnostic_state_declared = (
        validate_state_slot_manifest(
        state_manifest,
        model_id=args.model_id,
        base_seed=args.base_seed,
        state_path=state_path,
        )
    )
    state: pd.DataFrame | None = None
    if state_available or diagnostic_state_declared:
        before[_repo_path(state_path)] = _file_record(state_path)
    if state_available:
        state = pd.read_parquet(state_path, columns=state_projection_columns(args.model_id))
    common = pd.read_parquet(common_path, columns=list(COMMON_ORIGIN_REQUIRED_COLUMNS))
    if state is not None:
        assert_development_frame(state, gate, role_column="time_role")
    assert_development_frame(common, gate, role_column="time_role")

    sequences, audit = build_closure_pipe_sequences(
        state,
        common,
        model_id=args.model_id,
        base_seed=args.base_seed,
        expected_role_counts=EXPECTED_INTENT_ORIGINS_BY_ROLE,
        model_slot_failure_reason=model_slot_failure_reason,
    )
    after = {
        name: _file_record(PROJECT_ROOT / record["path"])
        for name, record in before.items()
    }
    if before != after or (
        not state_available and not diagnostic_state_declared and state_path.exists()
    ):
        raise ClosurePipeSequenceError("A sequence dependency changed during construction")
    if validate_state_slot_manifest(
        state_manifest,
        model_id=args.model_id,
        base_seed=args.base_seed,
        state_path=state_path,
    ) != (state_available, model_slot_failure_reason, diagnostic_state_declared):
        raise ClosurePipeSequenceError("State-slot manifest interpretation changed during construction")
    sequence_path = PROJECT_ROOT / paths["sequence"]
    summary_path = PROJECT_ROOT / paths["summary"]
    manifest_path = PROJECT_ROOT / paths["manifest"]
    assert_sequence_pointer_absent(paths)
    write_sequence_parquet(sequences, sequence_path)
    summary = cast(
        pd.DataFrame,
        sequences.groupby(
            ["time_role", "sequence_status", "failure_reason"],
            dropna=False,
            as_index=False,
        ).size(),
    )
    summary = summary.rename(columns={"size": "rows"}).sort_values(
        ["time_role", "sequence_status", "failure_reason"],
        kind="mergesort",
    )
    _write_csv_atomic(summary, summary_path)

    manifest = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": args.model_id,
        "base_seed": args.base_seed,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "script": _file_record(Path(__file__)),
        "cpu_execution_policy": cpu_execution_policy,
        "input_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
        "target_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "optional_context_columns": [],
        "serialization": {
            "rows_per_common_origin": 1,
            "input_physical_type": "fixed_size_list<float32>[12]",
            "target_physical_type": "float32",
            "canonical_order": ["source_id", "site_id", "origin_year_month", "target_year_month"],
        },
        "counts": {
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
            "holdout_overlap": 0,
            "post_2021_rows": 0,
        },
        "inputs": [
            *before.values(),
        ],
        "source_code": [_file_record(Path(__file__))],
        "outputs": [_file_record(sequence_path), _file_record(summary_path)],
        "completion_marker_written_last": True,
    }
    assert_sequence_pointer_absent(paths)
    _write_json_atomic(manifest, manifest_path)


if __name__ == "__main__":
    main()
