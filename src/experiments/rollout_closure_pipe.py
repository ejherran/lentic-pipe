#!/usr/bin/env python
"""Generate strict development-only Closure V1 P0/P1 state rollouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.experiments.build_closure_pipe_sequences import (
    COMMON_ORIGIN_REQUIRED_COLUMNS,
    DEFAULT_COMMON_ORIGINS,
    DEFAULT_RUNTIME_CONFIG,
    EXPECTED_INTENT_ORIGINS,
    EXPECTED_INTENT_ORIGINS_BY_ROLE,
    HISTORY_LENGTH,
    INPUT_COLUMNS,
    MODEL_IDS,
    MODEL_STATE_MAPPINGS,
    REGISTERED_SEEDS,
    SEQUENCE_COLUMNS,
    SEQUENCE_STATUS_VALUES,
    SEQUENCE_VERSION,
    STATE_CHANNELS,
    SURFACE_ID,
    TARGET_COLUMNS,
    TARGET_TO_NEXT_INPUT_MAPPING,
    _file_record,
    _paths as sequence_paths,
    _typed_scalar_equal,
    _write_json_atomic,
    expected_cpu_execution_policy_record,
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_runtime_contract import (
    EXPECTED_CPU_EXECUTION_POLICY,
    closure_seasonality,
    configure_torch_cpu_execution_policy,
    rollout_origin_seed,
    rollout_predraw_sha256,
    rollout_standard_normal_predraw,
)
from src.experiments.train_closure_pipe import (
    BLEND_GRID,
    DROPOUT,
    FitAvailability,
    HIDDEN_DIMENSION,
    MODEL_ARTIFACT_OUTPUT_NAMES,
    MODEL_VERSION,
    RECURRENT_LAYERS,
    RESIDUAL_MODE,
    LOCKED_DEVICE,
    _paths as model_paths,
    _require_torch,
    assert_temporal_model_input_contract_unchanged,
    collect_sequence_input_contract,
    collect_temporal_model_input_contract,
    configure_deterministic_runtime,
    fixed_profile,
    inspect_fit_availability,
    validate_sequence_common_origin_identity,
    validate_sequence_completion_manifest,
    validate_sequence_physical_schema,
    validate_temporal_seed,
)
from src.experiments.train_pipe_grud import make_model


ROLLOUT_VERSION = "closure_pipe_rollout_v1"
ROLLOUT_HORIZONS = (1, 2, 3)
SAMPLES_PER_ORIGIN = 128
ROLLOUT_BATCH_SIZE = 512
EXPECTED_EVALUATION_UNITS = 29_196
EXPECTED_PREDRAW_GOLDEN = "2ca072ae692d490fe43974edd9bb87fc71ddc57140d8bc0779fa13df75028a20"
PREDICTION_STATUS_VALUES = (
    "success",
    "sequence_unavailable",
    "model_unavailable",
    "rollout_failed",
)

SAMPLE_COLUMNS = tuple(f"sample_{channel}" for channel in STATE_CHANNELS)
ROLLOUT_ID_COLUMNS = (
    "rollout_version",
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
    "horizon_months",
    "target_evaluable",
    "prediction_status",
    "failure_reason",
    "origin_seed_hex",
    "predraw_sha256",
    "samples_per_origin",
    "raw_bloom_score",
)
ROLLOUT_COLUMNS = ROLLOUT_ID_COLUMNS + SAMPLE_COLUMNS + ("irc_samples",)


class ClosurePipeRolloutError(ValueError):
    """Raised when a Closure rollout violates its locked execution contract."""


@dataclass(frozen=True)
class OriginRollout:
    state_samples: np.ndarray
    irc_samples: np.ndarray
    raw_bloom_scores: np.ndarray
    origin_seed_hex: str
    predraw_sha256: str


def _runtime_section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosurePipeRolloutError(f"Runtime contract is missing mapping {key!r}")
    return value


def validate_rollout_runtime_contract(runtime: Mapping[str, Any]) -> None:
    """Bind rollout constants and physical names to the authoritative YAML."""
    temporal = _runtime_section(runtime, "temporal_models")
    rollout = _runtime_section(temporal, "rollout")
    output = _runtime_section(rollout, "output_table")
    if tuple(rollout.get("horizons_months", ())) != ROLLOUT_HORIZONS:
        raise ClosurePipeRolloutError("Runtime rollout horizons drifted")
    if rollout.get("samples_per_origin") != SAMPLES_PER_ORIGIN:
        raise ClosurePipeRolloutError("Runtime rollout sample count drifted")
    if rollout.get("batch_size") != ROLLOUT_BATCH_SIZE:
        raise ClosurePipeRolloutError("Runtime rollout batch size drifted")
    if output.get("schema_version") != ROLLOUT_VERSION:
        raise ClosurePipeRolloutError("Runtime rollout schema version drifted")
    if output.get("expected_rows_per_model_seed") != EXPECTED_EVALUATION_UNITS:
        raise ClosurePipeRolloutError("Runtime rollout denominator drifted")
    if tuple(output.get("prediction_status_values", ())) != PREDICTION_STATUS_VALUES:
        raise ClosurePipeRolloutError("Runtime rollout status dialect drifted")
    if tuple(output.get("state_sample_columns", ())) != SAMPLE_COLUMNS:
        raise ClosurePipeRolloutError("Runtime rollout sample column names drifted")
    if output.get("irc_sample_column") != "irc_samples":
        raise ClosurePipeRolloutError("Runtime rollout IRC column drifted")
    golden = _runtime_section(_runtime_section(rollout, "rng"), "golden_predraw")
    if golden.get("sha256") != EXPECTED_PREDRAW_GOLDEN:
        raise ClosurePipeRolloutError("Runtime rollout predraw golden drifted")
    if not _typed_scalar_equal(
        runtime.get("cpu_execution_policy"),
        EXPECTED_CPU_EXECUTION_POLICY,
    ):
        raise ClosurePipeRolloutError("Runtime CPU execution policy drifted")


def _state_clip(samples: np.ndarray) -> np.ndarray:
    if samples.ndim < 2 or samples.shape[-1] != len(STATE_CHANNELS):
        raise ClosurePipeRolloutError("A rollout state block has an unexpected shape")
    clipped = np.asarray(samples, dtype=np.float64).copy()
    clipped[..., :6] = np.clip(clipped[..., :6], 0.0, 1.0)
    clipped[..., 6:] = np.clip(clipped[..., 6:], -1.0, 1.0)
    return clipped.astype(np.float32)


def _irc_samples(state_samples: np.ndarray) -> np.ndarray:
    state = np.asarray(state_samples, dtype=np.float64)
    values = (state[:, 0] + (1.0 - state[:, 1]) + state[:, 2]) / 3.0
    return np.clip(values, 0.0, 1.0).astype(np.float64)


def _validated_blend_weights(blend_weights: Sequence[float]) -> np.ndarray:
    weights = np.asarray(blend_weights, dtype=np.float64)
    if weights.shape != (len(STATE_CHANNELS),) or not np.isfinite(weights).all():
        raise ClosurePipeRolloutError("Rollout blend weights must contain nine finite values")
    if not bool(((weights >= 0.0) & (weights <= 1.0)).all()):
        raise ClosurePipeRolloutError("Rollout blend weights must lie in [0, 1]")
    return weights


def _origin_rng_material(
    base_seed: int,
    *,
    source_id: str,
    site_id: str,
    origin_year_month: str,
) -> tuple[np.ndarray, str, str]:
    predraw = rollout_standard_normal_predraw(
        base_seed,
        source_id=source_id,
        site_id=site_id,
        origin_year_month=origin_year_month,
    )
    seed = rollout_origin_seed(
        base_seed,
        source_id=source_id,
        site_id=site_id,
        origin_year_month=origin_year_month,
    )
    return predraw, f"{seed:032x}", rollout_predraw_sha256(predraw)


def rollout_origin_batch(
    model: Any,
    x_windows: np.ndarray,
    *,
    blend_weights: Sequence[float],
    base_seed: int,
    origin_keys: Sequence[tuple[str, str, str]],
    device: Any,
) -> list[OriginRollout]:
    """Roll up to 512 origins together while keeping per-origin PCG64 streams."""
    windows = np.asarray(x_windows)
    batch_origins = len(origin_keys)
    if not 1 <= batch_origins <= ROLLOUT_BATCH_SIZE:
        raise ClosurePipeRolloutError("A rollout batch must contain between 1 and 512 origins")
    expected_shape = (batch_origins, HISTORY_LENGTH, len(INPUT_COLUMNS))
    if windows.shape != expected_shape:
        raise ClosurePipeRolloutError(f"Origin batch must have shape {expected_shape}")
    if windows.dtype != np.float32:
        raise ClosurePipeRolloutError("Origin windows must already be float32")
    if not np.isfinite(windows).all():
        raise ClosurePipeRolloutError("Origin windows contain nonfinite values")
    weights = _validated_blend_weights(blend_weights)

    rng_material = [
        _origin_rng_material(
            base_seed,
            source_id=source_id,
            site_id=site_id,
            origin_year_month=origin_year_month,
        )
        for source_id, site_id, origin_year_month in origin_keys
    ]
    predraw = np.stack([item[0] for item in rng_material]).astype(np.float64, copy=False)
    trajectories = np.repeat(windows[:, None, :, :], SAMPLES_PER_ORIGIN, axis=1).astype(
        np.float32,
        copy=False,
    )
    states = np.empty(
        (batch_origins, len(ROLLOUT_HORIZONS), SAMPLES_PER_ORIGIN, len(STATE_CHANNELS)),
        dtype=np.float32,
    )
    origin_periods: list[Any] = [pd.Period(key[2], freq="M") for key in origin_keys]
    torch = _require_torch()
    model.eval()
    with torch.no_grad():
        for horizon_index, horizon in enumerate(ROLLOUT_HORIZONS):
            flattened = trajectories.reshape(
                batch_origins * SAMPLES_PER_ORIGIN,
                HISTORY_LENGTH,
                len(INPUT_COLUMNS),
            )
            x_tensor = torch.from_numpy(flattened).to(device=device, dtype=torch.float32)
            mu_tensor, logvar_tensor = model(x_tensor)
            expected_output_shape = (
                batch_origins * SAMPLES_PER_ORIGIN,
                len(STATE_CHANNELS),
            )
            if mu_tensor.dtype != torch.float32 or logvar_tensor.dtype != torch.float32:
                raise ClosurePipeRolloutError("Closure model outputs must be float32")
            if tuple(mu_tensor.shape) != expected_output_shape or tuple(logvar_tensor.shape) != expected_output_shape:
                raise ClosurePipeRolloutError("Closure model output shape drifted")
            if not bool(torch.isfinite(mu_tensor).all()) or not bool(
                torch.isfinite(logvar_tensor).all()
            ):
                raise ClosurePipeRolloutError(
                    "Closure model outputs contain nonfinite mu/logvar values"
                )
            mu = (
                mu_tensor.detach()
                .cpu()
                .numpy()
                .astype(np.float32, copy=False)
                .reshape(batch_origins, SAMPLES_PER_ORIGIN, len(STATE_CHANNELS))
                .astype(np.float64)
            )
            logvar = (
                logvar_tensor.detach()
                .cpu()
                .numpy()
                .astype(np.float32, copy=False)
                .reshape(batch_origins, SAMPLES_PER_ORIGIN, len(STATE_CHANNELS))
                .astype(np.float64)
            )
            persistence = (
                trajectories[..., -1, : len(STATE_CHANNELS)]
                .astype(np.float32, copy=False)
                .astype(np.float64)
            )
            blended = persistence + weights[None, None, :] * (mu - persistence)
            sigma = np.exp(0.5 * np.clip(logvar, -10.0, 2.0))
            recycled = _state_clip(blended + sigma * predraw[:, horizon_index])
            states[:, horizon_index] = recycled

            seasonal = np.asarray(
                [
                    [
                        closure_seasonality((origin_period + horizon).month)[column]
                        for column in INPUT_COLUMNS[len(STATE_CHANNELS) :]
                    ]
                    for origin_period in origin_periods
                ],
                dtype=np.float64,
            ).astype(np.float32)
            seasonal_rows = np.repeat(seasonal[:, None, :], SAMPLES_PER_ORIGIN, axis=1)
            next_input = np.concatenate([recycled, seasonal_rows], axis=2).astype(
                np.float32,
                copy=False,
            )
            trajectories = np.concatenate(
                [trajectories[:, :, 1:, :], next_input[:, :, None, :]],
                axis=2,
            ).astype(np.float32, copy=False)

    results: list[OriginRollout] = []
    for index in range(batch_origins):
        state_by_horizon = states[index]
        irc = np.stack([_irc_samples(item) for item in state_by_horizon]).astype(np.float64)
        results.append(
            OriginRollout(
                state_samples=state_by_horizon,
                irc_samples=irc,
                raw_bloom_scores=np.mean(irc, axis=1, dtype=np.float64),
                origin_seed_hex=rng_material[index][1],
                predraw_sha256=rng_material[index][2],
            )
        )
    return results


def rollout_origin_samples(
    model: Any,
    x_window: np.ndarray,
    *,
    blend_weights: Sequence[float],
    base_seed: int,
    source_id: str,
    site_id: str,
    origin_year_month: str,
    device: Any,
) -> OriginRollout:
    """Roll one origin with PCG64 CRN and exact float32 recycle points."""
    window_array = np.asarray(x_window)
    if window_array.shape != (HISTORY_LENGTH, len(INPUT_COLUMNS)):
        raise ClosurePipeRolloutError("Origin window must have shape (12, 13)")
    if window_array.dtype != np.float32:
        raise ClosurePipeRolloutError("Origin window must already be float32")
    if not np.isfinite(window_array).all():
        raise ClosurePipeRolloutError("Origin window contains nonfinite values")
    return rollout_origin_batch(
        model,
        window_array[None, :, :],
        blend_weights=blend_weights,
        base_seed=base_seed,
        origin_keys=[(source_id, site_id, origin_year_month)],
        device=device,
    )[0]


def _validate_evaluation_units(
    common_origins: pd.DataFrame,
    *,
    expected_evaluation_units: int | None,
) -> pd.DataFrame:
    required = set(COMMON_ORIGIN_REQUIRED_COLUMNS)
    missing = sorted(required.difference(common_origins.columns))
    if missing:
        raise ClosurePipeRolloutError(f"Common-origin evaluation rows are missing columns: {missing}")
    if common_origins.empty:
        raise ClosurePipeRolloutError("Common-origin evaluation rows cannot be empty")
    columns = list(COMMON_ORIGIN_REQUIRED_COLUMNS)
    if "target_evaluable" in common_origins.columns:
        columns.append("target_evaluable")
    frame = common_origins.loc[:, columns].copy()
    if "target_evaluable" not in frame.columns:
        frame["target_evaluable"] = False
    if set(frame["surface_id"].astype(str)) != {SURFACE_ID}:
        raise ClosurePipeRolloutError("Evaluation rows use an unexpected surface")
    if set(frame["source_id"].astype(str)) != {"wqp"} or set(
        frame["assignment_role"].astype(str)
    ) != {"development"}:
        raise ClosurePipeRolloutError("Evaluation rows must be WQP development rows")
    horizons = pd.to_numeric(frame["horizon_months"], errors="coerce")
    if bool(horizons.isna().any()) or not bool(horizons.isin(ROLLOUT_HORIZONS).all()):
        raise ClosurePipeRolloutError("Evaluation rows contain invalid horizons")
    frame["horizon_months"] = horizons.astype("int8")
    if bool(frame["evaluation_unit_id"].astype(str).duplicated(keep=False).any()):
        raise ClosurePipeRolloutError("Evaluation-unit IDs must be unique")
    if not bool(frame["target_evaluable"].map(type).eq(bool).all()):
        raise ClosurePipeRolloutError("target_evaluable must contain strict booleans")
    for _, group in frame.groupby(["source_id", "site_id", "origin_year_month"], sort=False):
        if len(group) != 3 or set(group["horizon_months"].astype(int)) != set(ROLLOUT_HORIZONS):
            raise ClosurePipeRolloutError("Every intent origin must retain all three horizons")
        origin: Any = pd.Period(str(group.iloc[0]["origin_year_month"]), freq="M")
        for row in group.to_dict(orient="records"):
            if str(origin + int(row["horizon_months"])) != str(row["target_year_month"]):
                raise ClosurePipeRolloutError("Evaluation-unit target arithmetic drifted")
            target_period: Any = pd.Period(str(row["target_year_month"]), freq="M")
            cutoff: Any = pd.Period("2021-12", freq="M")
            if target_period > cutoff:
                raise ClosurePipeRolloutError("Development rollout reaches a post-2021 target month")
    ordered = sorted(
        range(len(frame)),
        key=lambda index: (
            str(frame.iloc[index]["source_id"]).encode("utf-8"),
            str(frame.iloc[index]["site_id"]).encode("utf-8"),
            str(frame.iloc[index]["origin_year_month"]).encode("utf-8"),
            int(frame.iloc[index]["horizon_months"]),
        ),
    )
    frame = frame.iloc[ordered].reset_index(drop=True)
    if expected_evaluation_units is not None and len(frame) != expected_evaluation_units:
        raise ClosurePipeRolloutError(
            "Evaluation-unit count differs from the locked intent denominator: "
            f"{len(frame)} != {expected_evaluation_units}"
        )
    return frame


def _sequence_window(row: pd.Series) -> np.ndarray:
    columns: list[np.ndarray] = []
    for column in INPUT_COLUMNS:
        values = np.asarray(row[column])
        if values.shape != (HISTORY_LENGTH,):
            raise ClosurePipeRolloutError(f"{column} is not a fixed 12-value list")
        columns.append(values.astype(np.float32))
    window = np.column_stack(columns).astype(np.float32, copy=False)
    if not np.isfinite(window).all():
        raise ClosurePipeRolloutError("A successful sequence contains nonfinite inputs")
    return window


def _failure_samples() -> tuple[dict[str, None], None]:
    return {column: None for column in SAMPLE_COLUMNS}, None


def build_closure_rollouts(
    sequences: pd.DataFrame,
    common_origins: pd.DataFrame,
    *,
    model: Any | None,
    blend_weights: Sequence[float] | None,
    model_id: str,
    base_seed: int,
    device: Any,
    model_unavailable_reason: str | None = None,
    expected_evaluation_units: int | None = EXPECTED_EVALUATION_UNITS,
    rollout_batch_size: int = ROLLOUT_BATCH_SIZE,
) -> pd.DataFrame:
    """Left-preserve every common evaluation unit, including failures."""
    validate_temporal_seed(model_id, base_seed)
    if type(rollout_batch_size) is not int or not 1 <= rollout_batch_size <= ROLLOUT_BATCH_SIZE:
        raise ClosurePipeRolloutError("rollout_batch_size must be an integer in [1, 512]")
    missing = sorted(set(SEQUENCE_COLUMNS).difference(sequences.columns))
    if missing:
        raise ClosurePipeRolloutError(f"Sequence rows are missing closed columns: {missing}")
    if not sequences.empty:
        if set(sequences["sequence_version"].astype(str)) != {SEQUENCE_VERSION}:
            raise ClosurePipeRolloutError("Sequence version differs from the Closure contract")
        if set(sequences["surface_id"].astype(str)) != {SURFACE_ID}:
            raise ClosurePipeRolloutError("Sequence surface differs from the Closure contract")
        if set(sequences["assignment_role"].astype(str)) != {"development"}:
            raise ClosurePipeRolloutError("Sequence rows must be development only")
        if not set(sequences["sequence_status"].astype(str)).issubset(SEQUENCE_STATUS_VALUES):
            raise ClosurePipeRolloutError("Sequence rows contain an unknown status")
    if bool(sequences.duplicated(["source_id", "site_id", "origin_year_month"], keep=False).any()):
        raise ClosurePipeRolloutError("Sequence rows contain duplicate common origins")
    evaluation = _validate_evaluation_units(
        common_origins,
        expected_evaluation_units=expected_evaluation_units,
    )
    sequence_index = sequences.set_index(["source_id", "site_id", "origin_year_month"])

    outcomes: dict[tuple[str, str, str], tuple[str, str, OriginRollout | None]] = {}
    pending_keys: list[tuple[str, str, str]] = []
    pending_windows: list[np.ndarray] = []
    if model is None and not model_unavailable_reason:
        raise ClosurePipeRolloutError(
            "An unavailable temporal model requires its explicit manifest failure reason"
        )
    for key, units in evaluation.groupby(["source_id", "site_id", "origin_year_month"], sort=False):
        first_unit = units.iloc[0]
        canonical_key = (
            str(first_unit["source_id"]),
            str(first_unit["site_id"]),
            str(first_unit["origin_year_month"]),
        )
        if key not in sequence_index.index:
            outcomes[canonical_key] = ("sequence_unavailable", "missing_sequence_origin", None)
            continue
        sequence_row = sequence_index.loc[key]
        if str(sequence_row["model_id"]) != model_id:
            outcomes[canonical_key] = ("sequence_unavailable", "sequence_model_mismatch", None)
            continue
        if model_id == "P0" and not pd.isna(sequence_row["base_seed"]):
            outcomes[canonical_key] = ("sequence_unavailable", "shared_p0_sequence_has_seed", None)
            continue
        if model_id == "P1" and int(sequence_row["base_seed"]) != base_seed:
            outcomes[canonical_key] = ("sequence_unavailable", "sequence_seed_mismatch", None)
            continue
        sequence_status = str(sequence_row["sequence_status"])
        if sequence_status == "model_slot_unavailable":
            outcomes[canonical_key] = (
                "model_unavailable",
                str(sequence_row["failure_reason"]),
                None,
            )
            continue
        if sequence_status != "success":
            outcomes[canonical_key] = (
                "sequence_unavailable",
                f"sequence_{sequence_status}_{sequence_row['failure_reason']}",
                None,
            )
            continue
        if model is None:
            outcomes[canonical_key] = (
                "model_unavailable",
                str(model_unavailable_reason),
                None,
            )
            continue
        for column in ("common_origin_id", "holdout_group_id", "time_role"):
            if str(sequence_row[column]) != str(first_unit[column]):
                raise ClosurePipeRolloutError(f"Sequence/common-origin identity drifted for {column}")
        pending_keys.append(canonical_key)
        pending_windows.append(_sequence_window(sequence_row))

    if model is not None:
        if blend_weights is None:
            raise ClosurePipeRolloutError("An available temporal model requires final blend weights")
        for start in range(0, len(pending_keys), rollout_batch_size):
            batch_keys = pending_keys[start : start + rollout_batch_size]
            batch_windows = np.stack(pending_windows[start : start + rollout_batch_size]).astype(
                np.float32,
                copy=False,
            )
            batch_results = rollout_origin_batch(
                model,
                batch_windows,
                blend_weights=blend_weights,
                base_seed=base_seed,
                origin_keys=batch_keys,
                device=device,
            )
            for key, result in zip(batch_keys, batch_results, strict=True):
                outcomes[key] = ("success", "", result)

    records: list[dict[str, Any]] = []
    for key, units in evaluation.groupby(["source_id", "site_id", "origin_year_month"], sort=False):
        first_unit = units.iloc[0]
        canonical_key = (
            str(first_unit["source_id"]),
            str(first_unit["site_id"]),
            str(first_unit["origin_year_month"]),
        )
        status, failure_reason, origin_rollout = outcomes[canonical_key]
        if origin_rollout is None:
            _, origin_seed_hex, predraw_digest = _origin_rng_material(
                base_seed,
                source_id=canonical_key[0],
                site_id=canonical_key[1],
                origin_year_month=canonical_key[2],
            )
        else:
            origin_seed_hex = origin_rollout.origin_seed_hex
            predraw_digest = origin_rollout.predraw_sha256

        for unit in units.sort_values("horizon_months", kind="mergesort").to_dict(
            orient="records"
        ):
            horizon_index = int(unit["horizon_months"]) - 1
            if origin_rollout is None:
                sample_payload, irc_payload = _failure_samples()
                raw_score = None
            else:
                sample_payload = {
                    f"sample_{channel}": origin_rollout.state_samples[horizon_index, :, index]
                    .astype(np.float32)
                    .tolist()
                    for index, channel in enumerate(STATE_CHANNELS)
                }
                irc_payload = origin_rollout.irc_samples[horizon_index].astype(np.float64).tolist()
                raw_score = float(origin_rollout.raw_bloom_scores[horizon_index])
            records.append(
                {
                    "rollout_version": ROLLOUT_VERSION,
                    "surface_id": unit["surface_id"],
                    "model_id": model_id,
                    "base_seed": base_seed,
                    "source_id": unit["source_id"],
                    "site_id": unit["site_id"],
                    "common_origin_id": unit["common_origin_id"],
                    "evaluation_unit_id": unit["evaluation_unit_id"],
                    "holdout_group_id": unit["holdout_group_id"],
                    "assignment_role": unit["assignment_role"],
                    "time_role": unit["time_role"],
                    "origin_year_month": unit["origin_year_month"],
                    "target_year_month": unit["target_year_month"],
                    "horizon_months": int(unit["horizon_months"]),
                    "target_evaluable": bool(unit["target_evaluable"]),
                    "prediction_status": status,
                    "failure_reason": failure_reason,
                    "origin_seed_hex": origin_seed_hex,
                    "predraw_sha256": predraw_digest,
                    "samples_per_origin": SAMPLES_PER_ORIGIN,
                    "raw_bloom_score": raw_score,
                    **sample_payload,
                    "irc_samples": irc_payload,
                }
            )

    output = pd.DataFrame(records, columns=ROLLOUT_COLUMNS)
    ordered = sorted(
        range(len(output)),
        key=lambda index: (
            str(output.iloc[index]["source_id"]).encode("utf-8"),
            str(output.iloc[index]["site_id"]).encode("utf-8"),
            str(output.iloc[index]["origin_year_month"]).encode("utf-8"),
            int(output.iloc[index]["horizon_months"]),
        ),
    )
    output = output.iloc[ordered].reset_index(drop=True)
    if len(output) != len(evaluation) or bool(output["evaluation_unit_id"].duplicated(keep=False).any()):
        raise ClosurePipeRolloutError("Rollout output failed intent-to-predict row conservation")
    if not set(output["prediction_status"]).issubset(PREDICTION_STATUS_VALUES):
        raise ClosurePipeRolloutError("Rollout output contains an unknown status")
    return output


def _fixed_size_array(values: Sequence[Any], *, value_type: pa.DataType) -> pa.Array:
    normalized: list[list[float] | None] = []
    for value in values:
        if value is None:
            normalized.append(None)
            continue
        array = np.asarray(value)
        if array.shape != (SAMPLES_PER_ORIGIN,):
            raise ClosurePipeRolloutError("Sample arrays must have exactly 128 values")
        normalized.append(array.tolist())
    return pa.array(normalized, type=pa.list_(value_type, SAMPLES_PER_ORIGIN))


def rollout_arrow_table(frame: pd.DataFrame) -> pa.Table:
    if frame.columns.tolist() != list(ROLLOUT_COLUMNS):
        raise ClosurePipeRolloutError("Rollout columns or order differ from the closed schema")
    arrays: list[pa.Array] = []
    fields: list[pa.Field] = []
    success = frame["prediction_status"].eq("success").tolist()
    for column in ROLLOUT_COLUMNS:
        if column in SAMPLE_COLUMNS:
            values = [value if row_success else None for value, row_success in zip(frame[column], success, strict=True)]
            arrays.append(_fixed_size_array(values, value_type=pa.float32()))
            fields.append(pa.field(column, pa.list_(pa.float32(), SAMPLES_PER_ORIGIN), nullable=True))
        elif column == "irc_samples":
            values = [value if row_success else None for value, row_success in zip(frame[column], success, strict=True)]
            arrays.append(_fixed_size_array(values, value_type=pa.float64()))
            fields.append(pa.field(column, pa.list_(pa.float64(), SAMPLES_PER_ORIGIN), nullable=True))
        elif column in {"base_seed"}:
            arrays.append(pa.array(frame[column].tolist(), type=pa.int64()))
            fields.append(pa.field(column, pa.int64(), nullable=False))
        elif column in {"horizon_months"}:
            arrays.append(pa.array(frame[column].tolist(), type=pa.int8()))
            fields.append(pa.field(column, pa.int8(), nullable=False))
        elif column == "samples_per_origin":
            arrays.append(pa.array(frame[column].tolist(), type=pa.int16()))
            fields.append(pa.field(column, pa.int16(), nullable=False))
        elif column == "target_evaluable":
            arrays.append(pa.array(frame[column].tolist(), type=pa.bool_()))
            fields.append(pa.field(column, pa.bool_(), nullable=False))
        elif column == "raw_bloom_score":
            values = [value if row_success else None for value, row_success in zip(frame[column], success, strict=True)]
            arrays.append(pa.array(values, type=pa.float64()))
            fields.append(pa.field(column, pa.float64(), nullable=True))
        else:
            arrays.append(pa.array(frame[column].astype(str).tolist(), type=pa.string()))
            fields.append(pa.field(column, pa.string(), nullable=False))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def write_rollout_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise ClosurePipeRolloutError(f"Refusing to overwrite temporary artifact: {temporary}")
    try:
        pq.write_table(rollout_arrow_table(frame), temporary, compression="zstd", use_dictionary=False)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def assert_rollout_outputs_absent(paths: Sequence[Path]) -> None:
    """Keep rollout completion bundles one-shot and fail on partial evidence."""
    if len(paths) != 2 or len(set(paths)) != 2:
        raise ClosurePipeRolloutError("Rollout output path set must contain two unique paths")
    candidates = [
        candidate
        for path in paths
        for candidate in (path, path.with_suffix(path.suffix + ".tmp"))
    ]
    parquet_paths = [path for path in paths if path.suffix == ".parquet"]
    if len(parquet_paths) != 1:
        raise ClosurePipeRolloutError("Rollout bundle must contain one Parquet output")
    pointer = Path(f"{parquet_paths[0].as_posix()}.dvc")
    candidates.extend((pointer, pointer.with_suffix(pointer.suffix + ".tmp")))
    existing = [path.as_posix() for path in candidates if path.exists()]
    if existing:
        raise ClosurePipeRolloutError(
            "Rollout overwrite is forbidden; existing bundle artifacts require "
            f"explicit review and cleanup: {existing}"
        )


def origin_rng_records_sha256(frame: pd.DataFrame) -> tuple[int, str]:
    origins = frame.loc[
        :,
        ["source_id", "site_id", "origin_year_month", "origin_seed_hex", "predraw_sha256"],
    ].drop_duplicates()
    if bool(origins.duplicated(["source_id", "site_id", "origin_year_month"], keep=False).any()):
        raise ClosurePipeRolloutError("An intent origin has conflicting RNG identity records")
    ordered = sorted(
        range(len(origins)),
        key=lambda index: tuple(
            str(origins.iloc[index][column]).encode("utf-8")
            for column in ("source_id", "site_id", "origin_year_month")
        ),
    )
    origins = origins.iloc[ordered].reset_index(drop=True)
    digest = hashlib.sha256()
    for row in origins.itertuples(index=False):
        if not row.origin_seed_hex or not row.predraw_sha256:
            raise ClosurePipeRolloutError("Every intent origin must retain its RNG identity")
        record = [
            str(row.source_id),
            str(row.site_id),
            str(row.origin_year_month),
            str(row.origin_seed_hex),
            str(row.predraw_sha256),
        ]
        digest.update(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
    return int(len(origins)), digest.hexdigest()


def _validate_temporal_record_array(
    raw_records: Any,
    *,
    expected_records: Sequence[Mapping[str, Any]],
    label: str,
) -> None:
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise ClosurePipeRolloutError(f"Temporal model manifest {label} must be an array")
    records: list[dict[str, Any]] = []
    paths: set[str] = set()
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping):
            raise ClosurePipeRolloutError(f"Temporal model {label} record dialect drifted")
        raw_path = raw_record.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ClosurePipeRolloutError(f"Temporal model {label} path is invalid")
        logical = Path(raw_path)
        if logical.is_absolute() or ".." in logical.parts or logical.as_posix() != raw_path:
            raise ClosurePipeRolloutError(
                f"Temporal model {label} paths must be canonical repository-relative"
            )
        physical = PROJECT_ROOT / logical
        try:
            physical.resolve().relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ClosurePipeRolloutError(
                f"Temporal model {label} path escapes the repository"
            ) from exc
        if not physical.is_file():
            raise ClosurePipeRolloutError(f"Temporal model {label} file is missing: {raw_path}")
        physical_record = _file_record(physical)
        if any(
            not _typed_scalar_equal(raw_record.get(key), physical_record[key])
            for key in ("path", "bytes", "sha256")
        ):
            raise ClosurePipeRolloutError(
                f"Temporal model {label} record differs from physical bytes: {raw_path}"
            )
        if raw_path in paths:
            raise ClosurePipeRolloutError(f"Temporal model {label} paths must be unique")
        paths.add(raw_path)
        records.append(dict(raw_record))
    expected = [dict(record) for record in expected_records]
    if records != expected:
        raise ClosurePipeRolloutError(f"Temporal model manifest {label} set/order drifted")


def _is_sha256_text(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value).issubset(
        set("0123456789abcdef")
    )


def validate_temporal_model_manifest(
    payload: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    artifact_paths: Mapping[str, Path],
    expected_input_records: Sequence[Mapping[str, Any]],
    expected_source_code_records: Sequence[Mapping[str, Any]],
    fit_availability: FitAvailability,
) -> bool:
    """Validate an available or explicitly retained unavailable temporal slot."""
    slot_status = payload.get("slot_status")
    common_keys = {
        "manifest_version",
        "status",
        "slot_status",
        "fit_status",
        "failure_reason",
        "generated_at_utc",
        "experiment_id",
        "surface_id",
        "model_id",
        "base_seed",
        "device",
        "future_outcomes_accessed",
        "evaluation_authorized",
        "e0_u_authorized",
        "failed_slot_replaced",
        "replacement_used",
        "model_artifact_emitted",
        "script",
        "cpu_execution_policy",
        "config",
        "input_state_mapping",
        "target_state_mapping",
        "target_to_next_input_mapping",
        "inputs",
        "source_code",
        "outputs",
        "completion_marker_written_last",
    }
    if slot_status == "available":
        expected_keys = common_keys.union({"selection", "batch_order", "row_counts"})
    elif slot_status == "model_unavailable":
        expected_keys = common_keys.union({"fit_status_counts", "failure_reason_counts"})
    else:
        raise ClosurePipeRolloutError("Temporal model manifest has an unknown slot_status")
    if set(payload) != expected_keys:
        raise ClosurePipeRolloutError("Temporal model manifest top-level dialect drifted")
    expected = {
        "manifest_version": "closure_pipe_model_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": model_id,
        "base_seed": base_seed,
        "device": LOCKED_DEVICE,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected.items():
        if type(payload.get(field)) is not type(value) or payload.get(field) != value:
            raise ClosurePipeRolloutError(f"Temporal model manifest field {field!r} drifted")
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise ClosurePipeRolloutError("Temporal model generated_at_utc drifted")
    try:
        datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ClosurePipeRolloutError("Temporal model generated_at_utc drifted") from exc
    missing_paths = sorted(set((*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest")).difference(artifact_paths))
    if missing_paths:
        raise ClosurePipeRolloutError(f"Temporal artifact paths are incomplete: {missing_paths}")
    expected_script = _file_record(PROJECT_ROOT / "src/experiments/train_closure_pipe.py")
    if payload.get("script") != expected_script:
        raise ClosurePipeRolloutError("Temporal model manifest script drifted")
    _validate_temporal_record_array(
        payload.get("source_code"),
        expected_records=expected_source_code_records,
        label="source_code",
    )
    _validate_temporal_record_array(
        payload.get("inputs"),
        expected_records=expected_input_records,
        label="inputs",
    )
    exact_sections = {
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "config": fixed_profile(),
        "input_state_mapping": MODEL_STATE_MAPPINGS[model_id],
        "target_state_mapping": MODEL_STATE_MAPPINGS[model_id],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
    }
    for field, value in exact_sections.items():
        if not _typed_scalar_equal(payload.get(field), value):
            raise ClosurePipeRolloutError(f"Temporal manifest section {field!r} drifted")
    if slot_status == "available":
        if (
            payload.get("fit_status") != "passed"
            or payload.get("failure_reason") != ""
            or payload.get("model_artifact_emitted") is not True
        ):
            raise ClosurePipeRolloutError("Available temporal manifest has inconsistent fit flags")
        if not fit_availability.available:
            raise ClosurePipeRolloutError("Available temporal model contradicts sequence fit rows")
        selection = payload.get("selection")
        if (
            not isinstance(selection, Mapping)
            or set(selection)
            != {
                "best_epoch",
                "best_model_selection_objective",
                "checkpoint_role",
                "final_blend_stage",
            }
            or type(selection.get("best_epoch")) is not int
            or not 1 <= int(selection["best_epoch"]) <= 20
            or not isinstance(selection.get("best_model_selection_objective"), (int, float))
            or not np.isfinite(float(selection["best_model_selection_objective"]))
            or selection.get("checkpoint_role") != "raw_best_unblended_model_state"
            or selection.get("final_blend_stage") != "once_after_raw_best_restore"
        ):
            raise ClosurePipeRolloutError("Available temporal selection evidence drifted")
        batch_order = payload.get("batch_order")
        if (
            not isinstance(batch_order, Mapping)
            or set(batch_order)
            != {"algorithm", "epoch_seed", "record_serialization", "records"}
            or batch_order.get("algorithm") != "torch_randperm_cpu_generator"
            or batch_order.get("epoch_seed") != "base_seed_plus_one_based_epoch"
            or batch_order.get("record_serialization") != "compact_json_utf8_lf_per_batch"
            or not isinstance(batch_order.get("records"), Sequence)
            or isinstance(batch_order.get("records"), (str, bytes))
        ):
            raise ClosurePipeRolloutError("Available temporal batch-order evidence drifted")
        batch_records = cast(Sequence[Any], batch_order["records"])
        expected_epochs = list(range(1, len(batch_records) + 1))
        if [record.get("epoch") if isinstance(record, Mapping) else None for record in batch_records] != expected_epochs or any(
            not isinstance(record, Mapping)
            or set(record) != {"epoch", "batch_order_sha256"}
            or not _is_sha256_text(record.get("batch_order_sha256"))
            for record in batch_records
        ):
            raise ClosurePipeRolloutError("Available temporal batch-order records drifted")
        expected_row_counts = {
            "training_windows": EXPECTED_INTENT_ORIGINS_BY_ROLE["training"],
            "model_selection_windows": EXPECTED_INTENT_ORIGINS_BY_ROLE["model_selection"],
            "calibration_windows_not_used_for_fit": EXPECTED_INTENT_ORIGINS_BY_ROLE[
                "calibration_threshold"
            ],
            "test_windows": 0,
            "holdout_windows": 0,
        }
        if payload.get("row_counts") != expected_row_counts:
            raise ClosurePipeRolloutError("Available temporal manifest row counts drifted")
        expected_outputs: list[dict[str, Any]] = []
        for name in MODEL_ARTIFACT_OUTPUT_NAMES:
            record = _file_record(artifact_paths[name])
            if name == "model":
                record["artifact_role"] = "final_model_with_locked_output_blend"
            elif name == "checkpoint":
                record["artifact_role"] = "raw_best_checkpoint"
            expected_outputs.append(record)
        _validate_temporal_record_array(
            payload.get("outputs"),
            expected_records=expected_outputs,
            label="outputs",
        )
        return True
    expected_unavailable = {
        "fit_status": "not_attempted",
        "failure_reason": "sequence_fit_rows_unavailable",
        "model_artifact_emitted": False,
    }
    for field, value in expected_unavailable.items():
        if type(payload.get(field)) is not type(value) or payload.get(field) != value:
            raise ClosurePipeRolloutError(f"Unavailable temporal field {field!r} drifted")
    if fit_availability.available:
        raise ClosurePipeRolloutError("Unavailable temporal model contradicts successful fit rows")
    if payload.get("fit_status_counts") != fit_availability.fit_status_counts or payload.get(
        "failure_reason_counts"
    ) != fit_availability.failure_reason_counts:
        raise ClosurePipeRolloutError("Unavailable temporal sequence failure evidence drifted")
    stale = [
        artifact_paths[name]
        for name in MODEL_ARTIFACT_OUTPUT_NAMES
        if name != "report" and artifact_paths[name].exists()
    ]
    if stale:
        raise ClosurePipeRolloutError("Unavailable temporal slot retains stale fit outputs")
    expected_report = {
        **_file_record(artifact_paths["report"]),
        "artifact_role": "report",
    }
    _validate_temporal_record_array(
        payload.get("outputs"),
        expected_records=[expected_report],
        label="outputs",
    )
    return False


def _load_model(
    path: Path,
    *,
    checkpoint_path: Path,
    blend_weights_path: Path,
    model_id: str,
    base_seed: int,
    device: Any,
) -> tuple[Any, list[float]]:
    torch = _require_torch()
    payload = torch.load(path, map_location=device, weights_only=False)
    if not isinstance(payload, Mapping):
        raise ClosurePipeRolloutError("Model artifact must contain a mapping")
    if payload.get("model_version") != MODEL_VERSION:
        raise ClosurePipeRolloutError("Model artifact has an unexpected version")
    if payload.get("artifact_role") != "final_model_with_locked_output_blend":
        raise ClosurePipeRolloutError("Model artifact is not the locked final blended model")
    if payload.get("experiment_id") != "closure_v1" or payload.get("surface_id") != SURFACE_ID:
        raise ClosurePipeRolloutError("Model artifact experiment/surface identity drifted")
    if (
        payload.get("model_id") != model_id
        or type(payload.get("base_seed")) is not int
        or payload.get("base_seed") != base_seed
    ):
        raise ClosurePipeRolloutError("Model artifact identity differs from the requested slot")
    if payload.get("device") != LOCKED_DEVICE or str(device) != LOCKED_DEVICE:
        raise ClosurePipeRolloutError("Model artifact device differs from the locked CPU runtime")
    if list(payload.get("input_columns", [])) != list(INPUT_COLUMNS) or list(
        payload.get("target_columns", [])
    ) != list(TARGET_COLUMNS):
        raise ClosurePipeRolloutError("Model artifact columns differ from the Closure schema")
    config = payload.get("config")
    if not isinstance(config, Mapping) or not _typed_scalar_equal(
        dict(config),
        fixed_profile(),
    ):
        raise ClosurePipeRolloutError("Model artifact fixed config drifted")
    expected_mappings = {
        "input_state_mapping": MODEL_STATE_MAPPINGS[model_id],
        "target_state_mapping": MODEL_STATE_MAPPINGS[model_id],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
    }
    for field, value in expected_mappings.items():
        if not _typed_scalar_equal(payload.get(field), value):
            raise ClosurePipeRolloutError(f"Model artifact mapping {field!r} drifted")
    mapping = payload.get("output_blend_weights")
    target_names = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    if not isinstance(mapping, Mapping) or set(mapping) != set(target_names):
        raise ClosurePipeRolloutError("Model artifact lacks nine exact final blend weights")
    weights = [float(mapping[target]) for target in target_names]
    if not np.isfinite(np.asarray(weights, dtype=np.float64)).all() or any(
        weight not in BLEND_GRID for weight in weights
    ):
        raise ClosurePipeRolloutError("Model artifact blend weights leave the locked grid")
    blend_frame = pd.read_csv(blend_weights_path)
    expected_blend_columns = [
        "target",
        "blend_weight",
        "validation_rows",
        "validation_mae",
        "validation_rmse",
        "selection_metric",
        "selection_objective",
    ]
    if blend_frame.columns.tolist() != expected_blend_columns or len(blend_frame) != len(
        target_names
    ):
        raise ClosurePipeRolloutError("Blend-weight CSV schema/row count drifted")
    if bool(blend_frame["target"].astype(str).duplicated(keep=False).any()):
        raise ClosurePipeRolloutError("Blend-weight CSV targets must be unique")
    csv_mapping = dict(
        zip(
            blend_frame["target"].astype(str),
            pd.to_numeric(blend_frame["blend_weight"], errors="coerce"),
            strict=True,
        )
    )
    if set(csv_mapping) != set(target_names):
        raise ClosurePipeRolloutError("Blend-weight CSV targets drifted")
    csv_weights = [float(csv_mapping[target]) for target in target_names]
    if not np.isfinite(np.asarray(csv_weights, dtype=np.float64)).all() or any(
        weight not in BLEND_GRID for weight in csv_weights
    ):
        raise ClosurePipeRolloutError("Blend-weight CSV leaves the locked grid")
    if csv_weights != weights:
        raise ClosurePipeRolloutError("Model artifact blend weights differ from the CSV")
    artifact_base_keys = {
        "model_version",
        "experiment_id",
        "surface_id",
        "model_id",
        "base_seed",
        "device",
        "config",
        "input_columns",
        "target_columns",
        "input_state_mapping",
        "target_state_mapping",
        "target_to_next_input_mapping",
        "best_epoch",
        "best_model_selection_objective",
        "model_state_dict",
    }
    if set(payload) != artifact_base_keys.union(
        {"artifact_role", "output_blend_weights"}
    ):
        raise ClosurePipeRolloutError("Final model artifact dialect drifted")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ClosurePipeRolloutError("Raw checkpoint artifact must contain a mapping")
    if set(checkpoint) != artifact_base_keys.union({"artifact_role"}):
        raise ClosurePipeRolloutError(
            "Raw checkpoint dialect drifted or contains forbidden blend state"
        )
    if checkpoint.get("artifact_role") != "raw_best_checkpoint":
        raise ClosurePipeRolloutError("Raw checkpoint artifact role drifted")
    for field in artifact_base_keys.difference({"model_state_dict"}):
        if not _typed_scalar_equal(checkpoint.get(field), payload.get(field)):
            raise ClosurePipeRolloutError(
                f"Raw checkpoint metadata {field!r} differs from the final model"
            )
    final_state = payload.get("model_state_dict")
    raw_state = checkpoint.get("model_state_dict")
    if not isinstance(final_state, Mapping) or not isinstance(raw_state, Mapping):
        raise ClosurePipeRolloutError("Temporal artifacts must contain state-dict mappings")
    if list(final_state) != list(raw_state):
        raise ClosurePipeRolloutError("Raw checkpoint state keys differ from the final model")
    for name in final_state:
        final_tensor = final_state[name]
        raw_tensor = raw_state[name]
        if not isinstance(final_tensor, torch.Tensor) or not isinstance(raw_tensor, torch.Tensor):
            raise ClosurePipeRolloutError("Temporal state dictionaries must contain tensors")
        if not torch.equal(final_tensor.detach().cpu(), raw_tensor.detach().cpu()):
            raise ClosurePipeRolloutError(
                f"Raw checkpoint tensor {name!r} differs from the final model"
            )
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=HIDDEN_DIMENSION,
        num_layers=RECURRENT_LAYERS,
        dropout=DROPOUT,
        residual_mode=RESIDUAL_MODE,
    ).to(device)
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate strict Closure V1 P0/P1 rollouts.")
    parser.add_argument("--model-id", choices=MODEL_IDS, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--device", choices=[LOCKED_DEVICE], required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # The gate precedes model, sequence, common-origin, and output I/O.
    from src.experiments.closure_development_runtime_lock import require_development_fit_authorized

    require_development_fit_authorized(device=args.device)
    runtime = load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
    validate_rollout_runtime_contract(runtime)
    cpu_execution_policy = configure_torch_cpu_execution_policy(runtime)
    if cpu_execution_policy != expected_cpu_execution_policy_record():
        raise ClosurePipeRolloutError("Applied CPU execution policy drifted")
    validate_temporal_seed(args.model_id, args.base_seed)
    device = configure_deterministic_runtime(args.base_seed, args.device)

    sequence_info = sequence_paths(args.model_id, None if args.model_id == "P0" else args.base_seed)
    sequence_path = PROJECT_ROOT / sequence_info["sequence"]
    sequence_summary_path = PROJECT_ROOT / sequence_info["summary"]
    sequence_manifest_path = PROJECT_ROOT / sequence_info["manifest"]
    model_info = model_paths(args.model_id, args.base_seed)
    artifact_paths = {name: PROJECT_ROOT / path for name, path in model_info.items()}
    model_path = artifact_paths["model"]
    model_manifest_path = artifact_paths["manifest"]
    common_path = PROJECT_ROOT / DEFAULT_COMMON_ORIGINS
    output_path = PROJECT_ROOT / Path(
        f"data/closure_v1/development/rollouts/{args.model_id}/seed_{args.base_seed}.parquet"
    )
    manifest_path = PROJECT_ROOT / Path(
        f"reports/closure_v1/02_models/{args.model_id}/seed_{args.base_seed}_rollout_manifest.json"
    )
    assert_rollout_outputs_absent((output_path, manifest_path))
    sequence_input_contract = collect_sequence_input_contract(
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    model_input_contract = collect_temporal_model_input_contract(
        model_id=args.model_id,
        base_seed=args.base_seed,
        sequence_contract=sequence_input_contract,
    )
    if not sequence_path.is_file() or not sequence_manifest_path.is_file():
        raise ClosurePipeRolloutError("Rollout requires a completed retained sequence artifact")
    if not model_manifest_path.is_file():
        raise ClosurePipeRolloutError("Rollout requires explicit temporal slot evidence")
    before = {str(record["path"]): dict(record) for record in model_input_contract.records}
    for path in (model_manifest_path, Path(__file__)):
        record = _file_record(path)
        if record["path"] in before:
            raise ClosurePipeRolloutError(
                f"Rollout dependency path is duplicated: {record['path']}"
            )
        before[record["path"]] = record
    for name in MODEL_ARTIFACT_OUTPUT_NAMES:
        artifact_path = artifact_paths[name]
        if artifact_path.is_file():
            record = _file_record(artifact_path)
            before[record["path"]] = record
    sequence_record = before[_file_record(sequence_path)["path"]]
    summary_record = before[_file_record(sequence_summary_path)["path"]]
    with sequence_manifest_path.open(encoding="utf-8") as handle:
        sequence_manifest = json.load(handle)
    if not isinstance(sequence_manifest, Mapping):
        raise ClosurePipeRolloutError("Sequence manifest must contain a JSON object")
    validate_sequence_completion_manifest(
        sequence_manifest,
        sequence_record=sequence_record,
        summary_record=summary_record,
        expected_input_records=sequence_input_contract.records,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    validate_sequence_physical_schema(pq.read_schema(sequence_path))
    sequences = pd.read_parquet(sequence_path, columns=list(SEQUENCE_COLUMNS))
    fit_availability = inspect_fit_availability(
        sequences,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    common_columns = list(COMMON_ORIGIN_REQUIRED_COLUMNS) + ["target_evaluable"]
    common = pd.read_parquet(common_path, columns=common_columns)
    validate_sequence_common_origin_identity(sequences, common)
    with model_manifest_path.open(encoding="utf-8") as handle:
        model_manifest = json.load(handle)
    if not isinstance(model_manifest, Mapping):
        raise ClosurePipeRolloutError("Temporal model manifest must contain a JSON object")
    model_available = validate_temporal_model_manifest(
        model_manifest,
        model_id=args.model_id,
        base_seed=args.base_seed,
        artifact_paths=artifact_paths,
        expected_input_records=model_input_contract.records,
        expected_source_code_records=model_input_contract.source_code_records,
        fit_availability=fit_availability,
    )
    model: Any | None = None
    blend_weights: list[float] | None = None
    if model_available:
        model, blend_weights = _load_model(
            model_path,
            checkpoint_path=artifact_paths["checkpoint"],
            blend_weights_path=artifact_paths["blend_weights"],
            model_id=args.model_id,
            base_seed=args.base_seed,
            device=device,
        )

    rollouts = build_closure_rollouts(
        sequences,
        common,
        model=model,
        blend_weights=blend_weights,
        model_id=args.model_id,
        base_seed=args.base_seed,
        device=device,
        model_unavailable_reason=(
            None if model_available else str(model_manifest["failure_reason"])
        ),
    )
    assert_temporal_model_input_contract_unchanged(model_input_contract)
    after = {
        name: _file_record(PROJECT_ROOT / record["path"])
        for name, record in before.items()
    }
    if before != after:
        raise ClosurePipeRolloutError("A rollout dependency changed during calculation")
    rng_count, rng_digest = origin_rng_records_sha256(rollouts)
    if rng_count != EXPECTED_INTENT_ORIGINS:
        raise ClosurePipeRolloutError(
            f"Rollout RNG origin count drifted: {rng_count} != {EXPECTED_INTENT_ORIGINS}"
        )
    golden_observed = rollout_predraw_sha256(
        rollout_standard_normal_predraw(
            1729,
            source_id="wqp",
            site_id="A",
            origin_year_month="2020-01",
        )
    )
    if golden_observed != EXPECTED_PREDRAW_GOLDEN:
        raise ClosurePipeRolloutError("Runtime PCG64 golden predraw drifted")
    status_counts = rollouts["prediction_status"].value_counts()
    failure_counts = rollouts.loc[
        ~rollouts["prediction_status"].eq("success"), "failure_reason"
    ].value_counts()
    write_rollout_parquet(rollouts, output_path)
    manifest = {
        "manifest_version": "closure_pipe_rollout_manifest_v1",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": args.model_id,
        "base_seed": args.base_seed,
        "device": args.device,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "script": _file_record(Path(__file__)),
        "cpu_execution_policy": cpu_execution_policy,
        "model_available": model is not None,
        "horizons_months": list(ROLLOUT_HORIZONS),
        "samples_per_origin": SAMPLES_PER_ORIGIN,
        "raw_bloom_score": "arithmetic_mean_of_128_equal_weight_irc_samples",
        "irc_weights": {"yN": 1.0, "one_minus_yF": 1.0, "yT_no_chla": 1.0},
        "rng": {
            "algorithm": "numpy.random.PCG64",
            "scope": "one_generator_per_origin",
            "common_random_numbers": "P0_P1_within_paired_seed",
            "model_id_in_seed_payload": False,
            "origin_record_scope": "all_intent_origins_including_failures",
            "origin_record_count": rng_count,
            "origin_records_sha256": rng_digest,
            "golden_predraw_sha256": golden_observed,
        },
        "serialization": {
            "rows_per_evaluation_unit": 1,
            "state_samples": "nine_fixed_size_list<float32>[128]",
            "irc_samples": "fixed_size_list<float64>[128]",
            "failure_rows_retained": True,
        },
        "counts": {
            "intent_evaluation_units": int(len(rollouts)),
            "successful_evaluation_units": int(rollouts["prediction_status"].eq("success").sum()),
            "failed_evaluation_units": int((~rollouts["prediction_status"].eq("success")).sum()),
            "metric_evaluable_intent_units": int(rollouts["target_evaluable"].sum()),
            "status_counts": {str(key): int(value) for key, value in status_counts.items()},
            "failure_reason_counts": {str(key): int(value) for key, value in failure_counts.items()},
            "holdout_overlap": 0,
            "post_2021_rows": 0,
        },
        "inputs": [*before.values()],
        "source_code": [_file_record(Path(__file__))],
        "outputs": [_file_record(output_path)],
        "completion_marker_written_last": True,
    }
    _write_json_atomic(manifest, manifest_path)


if __name__ == "__main__":
    main()
