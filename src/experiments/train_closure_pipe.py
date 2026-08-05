#!/usr/bin/env python
"""Fit the fixed Closure V1 residual probabilistic GRU profile.

This module exposes synthetic-testable functional kernels, while its CLI is
unconditionally guarded by the published additive E0-DLTV development
authorization.  It never reads calibration outcomes, locked evaluation rows,
or holdout rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import stat
import sys
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

from src.experiments.build_closure_pipe_sequences import (
    COMMON_ORIGIN_REQUIRED_COLUMNS,
    DEFAULT_COMMON_COMPLETION,
    DEFAULT_COMMON_ORIGINS,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_LOCK,
    DEFAULT_RUNTIME_SCHEMA,
    EXPECTED_INTENT_ORIGINS,
    EXPECTED_INTENT_ORIGINS_BY_ROLE,
    INPUT_COLUMNS,
    MODEL_IDS,
    MODEL_STATE_MAPPINGS,
    REGISTERED_SEEDS,
    SEQUENCE_COLUMNS,
    SEQUENCE_STATUS_VALUES,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    TARGET_TO_NEXT_INPUT_MAPPING,
    _file_record,
    _paths as sequence_paths,
    _sha256,
    _typed_scalar_equal,
    _validate_common_origins,
    expected_cpu_execution_policy_record,
    validate_sequence_runtime_contract,
    validate_state_slot_manifest,
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_development_guard import (
    DEFAULT_ASSIGNMENT,
    DEFAULT_HOLDOUT_MANIFEST,
    DEFAULT_PROTOCOL_LOCK,
)
from src.experiments.closure_runtime_contract import (
    EXPECTED_CPU_EXECUTION_POLICY,
    configure_torch_cpu_execution_policy,
)
from src.experiments.train_pipe_grud import (
    TARGET_WEIGHTS,
    _blend_weight_tensor,
    _require_torch,
    evaluate_model,
    make_loss_weights,
    make_model,
    select_output_blend_weights,
    training_loss,
)


MODEL_VERSION = "closure_pipe_temporal_v1"
HISTORY_LENGTH = 12
HIDDEN_DIMENSION = 96
RECURRENT_LAYERS = 1
DROPOUT = 0.0
RESIDUAL_MODE = "add_last"
BATCH_SIZE = 2048
LEARNING_RATE = 0.001
WEIGHT_DECAY = 0.00001
GRADIENT_CLIP_NORM = 1.0
MAXIMUM_EPOCHS = 20
EARLY_STOPPING_PATIENCE = 5
EARLY_STOPPING_MINIMUM_DELTA = 0.0
MSE_WEIGHT = 1.0
BLEND_GRID = (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0)
PERMITTED_SEQUENCE_ROLES = ("training", "model_selection", "calibration_threshold")
FIT_ROLES = ("training", "model_selection")
LOCKED_DEVICE = "cpu"
MODEL_ARTIFACT_OUTPUT_NAMES = (
    "model",
    "checkpoint",
    "preprocessor",
    "metrics",
    "training_curve",
    "blend_weights",
    "blend_search",
    "report",
)
SEQUENCE_BUILDER_PATH = Path("src/experiments/build_closure_pipe_sequences.py")
P0_ARTIFACT_BUILDER_RECORD = {
    "path": SEQUENCE_BUILDER_PATH.as_posix(),
    "bytes": 110_034,
    "sha256": "dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6",
}


class ClosurePipeTrainingError(ValueError):
    """Raised when a Closure temporal fit would violate its locked profile."""


@dataclass(frozen=True)
class WindowBundle:
    metadata: pd.DataFrame
    x: np.ndarray
    y: np.ndarray

    def subset(self, role: str) -> WindowBundle:
        mask = self.metadata["time_role"].eq(role).to_numpy()
        return WindowBundle(
            metadata=self.metadata.loc[mask].reset_index(drop=True),
            x=self.x[mask],
            y=self.y[mask],
        )


@dataclass(frozen=True)
class FitAvailability:
    available: bool
    failure_reason: str
    fit_status_counts: dict[str, int]
    failure_reason_counts: dict[str, int]


@dataclass(frozen=True)
class SequenceInputContract:
    manifest_input_records: tuple[dict[str, Any], ...]
    live_physical_records: tuple[dict[str, Any], ...]
    state_path: Path
    state_artifact_required: bool


@dataclass(frozen=True)
class TemporalModelInputContract:
    records: tuple[dict[str, Any], ...]
    source_code_records: tuple[dict[str, Any], ...]
    sequence_contract: SequenceInputContract


@dataclass(frozen=True)
class EarlyStoppingState:
    best_objective: float = float("inf")
    best_epoch: int = 0
    epochs_without_improvement: int = 0
    should_stop: bool = False


@dataclass
class ClosureFitResult:
    model: Any
    best_state_dict: dict[str, Any]
    best_epoch: int
    best_objective: float
    history: pd.DataFrame
    provisional_blends: pd.DataFrame
    provisional_blend_searches: pd.DataFrame
    final_blend_weights: pd.DataFrame
    final_blend_search: pd.DataFrame
    metrics: pd.DataFrame


class TensorWindowDataset:
    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        self.x = np.asarray(x, dtype=np.float32)
        self.y = np.asarray(y, dtype=np.float32)

    def __len__(self) -> int:
        return int(len(self.x))

    def __getitem__(self, item: int) -> tuple[Any, Any]:
        torch = _require_torch()
        return torch.from_numpy(self.x[item]), torch.from_numpy(self.y[item])


def validate_temporal_seed(model_id: str, base_seed: int) -> None:
    if model_id not in MODEL_IDS:
        raise ClosurePipeTrainingError(f"Unknown Closure temporal model: {model_id!r}")
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise ClosurePipeTrainingError(f"Unregistered Closure temporal seed: {base_seed!r}")


def _runtime_section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosurePipeTrainingError(f"Runtime contract is missing mapping {key!r}")
    return value


def validate_temporal_runtime_contract(runtime: Mapping[str, Any]) -> None:
    """Bind the trainer's fixed constants to the authoritative YAML fields."""
    validate_sequence_runtime_contract(runtime)
    temporal = _runtime_section(runtime, "temporal_models")
    randomness = _runtime_section(temporal, "training_randomness")
    dataloader = _runtime_section(randomness, "dataloader")
    architecture = _runtime_section(temporal, "common_architecture")
    optimization = _runtime_section(temporal, "optimization")
    loss = _runtime_section(temporal, "loss")
    blend = _runtime_section(temporal, "output_blend")
    expected_architecture = {
        "history_length_months": HISTORY_LENGTH,
        "input_dimension": len(INPUT_COLUMNS),
        "target_dimension": len(TARGET_COLUMNS),
        "hidden_dimension": HIDDEN_DIMENSION,
        "recurrent_layers": RECURRENT_LAYERS,
        "dropout": DROPOUT,
        "residual_mode": RESIDUAL_MODE,
    }
    for key, value in expected_architecture.items():
        if architecture.get(key) != value:
            raise ClosurePipeTrainingError(f"Runtime temporal architecture {key} drifted")
    expected_optimization = {
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_clip_norm": GRADIENT_CLIP_NORM,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAXIMUM_EPOCHS,
        "early_stopping_patience_epochs": EARLY_STOPPING_PATIENCE,
        "early_stopping_minimum_delta": EARLY_STOPPING_MINIMUM_DELTA,
    }
    for key, value in expected_optimization.items():
        if optimization.get(key) != value:
            raise ClosurePipeTrainingError(f"Runtime temporal optimization {key} drifted")
    if loss.get("mse_weight") != MSE_WEIGHT or loss.get("target_weights") != TARGET_WEIGHTS:
        raise ClosurePipeTrainingError("Runtime temporal loss profile drifted")
    if tuple(blend.get("grid", ())) != BLEND_GRID:
        raise ClosurePipeTrainingError("Runtime temporal blend grid drifted")
    expected_randomness = {
        "seed_source": "paired_model_seed",
        "seed_before_model_construction": True,
        "python_random_seed": "base_seed",
        "numpy_legacy_random_seed": "base_seed",
        "torch_manual_seed": "base_seed",
        "torch_cuda_manual_seed_all_if_available": "base_seed",
        "torch_deterministic_algorithms": True,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
        "cublas_workspace_config_if_cuda": "not_applicable_cpu_only_e0_dl_v1",
        "device_policy": "cpu_only_locked_by_e0_dl_v1",
        "automatic_device_selection": "forbidden",
    }
    for key, value in expected_randomness.items():
        if randomness.get(key) != value:
            raise ClosurePipeTrainingError(f"Runtime temporal randomness {key} drifted")
    expected_loader = {
        "shuffle_training": True,
        "epoch_seed_formula": "base_seed_plus_one_based_epoch",
        "generator_scope": "new_torch_generator_per_epoch",
        "num_workers": 0,
        "drop_last": False,
        "evaluation_shuffle": False,
        "batch_order_sha256_in_manifest": "required",
    }
    for key, value in expected_loader.items():
        if dataloader.get(key) != value:
            raise ClosurePipeTrainingError(f"Runtime temporal dataloader {key} drifted")


def inspect_fit_availability(
    frame: pd.DataFrame,
    *,
    model_id: str,
    base_seed: int,
    enforce_locked_denominators: bool = True,
) -> FitAvailability:
    """Validate slot identity and expose retained fit-row failures without tensorizing."""
    validate_temporal_seed(model_id, base_seed)
    missing = sorted(set(SEQUENCE_COLUMNS).difference(frame.columns))
    if missing:
        raise ClosurePipeTrainingError(f"Sequence rows are missing closed columns: {missing}")
    if frame.empty:
        raise ClosurePipeTrainingError("Sequence rows cannot be empty")
    working = frame.loc[:, SEQUENCE_COLUMNS]
    if set(working["sequence_version"].astype(str)) != {SEQUENCE_VERSION}:
        raise ClosurePipeTrainingError("Sequence version differs from the Closure contract")
    if set(working["model_id"].astype(str)) != {model_id}:
        raise ClosurePipeTrainingError("Sequence model_id differs from the requested model")
    if model_id == "P0":
        if not bool(working["base_seed"].isna().all()):
            raise ClosurePipeTrainingError("The shared P0 sequence must not contain a seed")
    else:
        observed_seeds = pd.to_numeric(working["base_seed"], errors="coerce")
        seed_values = observed_seeds.to_numpy(dtype=np.float64)
        if (
            bool(observed_seeds.isna().any())
            or not np.isfinite(seed_values).all()
            or not np.equal(seed_values, np.floor(seed_values)).all()
            or set(seed_values.astype(np.int64)) != {base_seed}
        ):
            raise ClosurePipeTrainingError("P1 sequence seed differs from the paired temporal seed")
    if set(working["assignment_role"].astype(str)) != {"development"}:
        raise ClosurePipeTrainingError("Temporal fit received a non-development sequence")
    if set(working["surface_id"].astype(str)) != {"closure_v1_wqp_adaptive_no_current_chla"}:
        raise ClosurePipeTrainingError("Temporal fit received an unexpected surface")
    if set(working["source_id"].astype(str)) != {"wqp"}:
        raise ClosurePipeTrainingError("Temporal fit must use WQP rows only")
    observed_roles = set(working["time_role"].astype(str))
    if not observed_roles.issubset(PERMITTED_SEQUENCE_ROLES):
        raise ClosurePipeTrainingError("Temporal fit received a forbidden role")
    if not set(FIT_ROLES).issubset(observed_roles):
        raise ClosurePipeTrainingError("Training and model_selection must both contain windows")
    observed_statuses = set(working["sequence_status"].astype(str))
    if not observed_statuses.issubset(SEQUENCE_STATUS_VALUES):
        raise ClosurePipeTrainingError("Temporal fit received an unknown sequence status")
    if bool(working.duplicated(["source_id", "site_id", "origin_year_month"], keep=False).any()):
        raise ClosurePipeTrainingError("Sequence rows contain duplicate common origins")
    if bool(working["common_origin_id"].astype(str).duplicated(keep=False).any()):
        raise ClosurePipeTrainingError("Sequence common_origin_id values must be unique")
    lengths = pd.to_numeric(working["history_length_months"], errors="coerce")
    length_values = lengths.to_numpy(dtype=np.float64)
    if (
        bool(lengths.isna().any())
        or not np.isfinite(length_values).all()
        or not np.equal(length_values, np.floor(length_values)).all()
        or set(length_values.astype(np.int64)) != {HISTORY_LENGTH}
    ):
        raise ClosurePipeTrainingError("Sequence history length must equal 12")
    for row in working.to_dict(orient="records"):
        origin: Any = pd.Period(str(row["origin_year_month"]), freq="M")
        target: Any = pd.Period(str(row["target_year_month"]), freq="M")
        if str(origin + 1) != str(target):
            raise ClosurePipeTrainingError("Sequence target month must equal origin plus one")
        if str(origin - (HISTORY_LENGTH - 1)) != str(row["history_start_year_month"]):
            raise ClosurePipeTrainingError("Sequence history start geometry drifted")
        if str(row["history_end_year_month"]) != str(origin):
            raise ClosurePipeTrainingError("Sequence history end geometry drifted")
        if target > cast(Any, pd.Period("2021-12", freq="M")):
            raise ClosurePipeTrainingError("Sequence contains a post-2021 target")
        status = str(row["sequence_status"])
        reason = str(row["failure_reason"])
        if status == "success" and reason:
            raise ClosurePipeTrainingError("Successful sequence rows must have no failure reason")
        if status != "success" and not reason:
            raise ClosurePipeTrainingError("Unavailable sequence rows require a failure reason")
        if status != "success":
            nonnull_inputs = [
                column
                for column in INPUT_COLUMNS
                if not _is_logically_null_input_tensor(row[column])
            ]
            nonnull_targets = [column for column in TARGET_COLUMNS if not pd.isna(row[column])]
            if nonnull_inputs or nonnull_targets:
                raise ClosurePipeTrainingError(
                    "Unavailable sequence rows must retain nullable tensors only"
                )
    role_counts = {
        str(key): int(value) for key, value in working["time_role"].value_counts().items()
    }
    if enforce_locked_denominators:
        if len(working) != EXPECTED_INTENT_ORIGINS:
            raise ClosurePipeTrainingError(
                f"Sequence denominator drifted: {len(working)} != {EXPECTED_INTENT_ORIGINS}"
            )
        if role_counts != EXPECTED_INTENT_ORIGINS_BY_ROLE:
            raise ClosurePipeTrainingError(f"Sequence role denominators drifted: {role_counts}")
    fit = working.loc[working["time_role"].isin(FIT_ROLES)]
    counts = {str(key): int(value) for key, value in fit["sequence_status"].value_counts().items()}
    failure_counts = {
        str(key): int(value)
        for key, value in fit.loc[
            ~fit["sequence_status"].eq("success"), "failure_reason"
        ].value_counts().items()
    }
    available = bool(fit["sequence_status"].eq("success").all())
    return FitAvailability(
        available=available,
        failure_reason="" if available else "sequence_fit_rows_unavailable",
        fit_status_counts=counts,
        failure_reason_counts=failure_counts,
    )


def _is_logically_null_input_tensor(value: Any) -> bool:
    """Recognize logical nulls before and after FixedSizeList Parquet I/O."""
    if value is None:
        return True
    array = np.asarray(value)
    return array.shape == (HISTORY_LENGTH,) and bool(pd.isna(array).all())


def _canonical_order(frame: pd.DataFrame) -> list[int]:
    required = ["source_id", "site_id", "origin_year_month", "target_year_month"]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ClosurePipeTrainingError(f"Sequence metadata is missing canonical keys: {missing}")
    keys: list[tuple[bytes, bytes, bytes, bytes, int]] = []
    for index, row in enumerate(frame.reset_index(drop=True).to_dict(orient="records")):
        values: list[bytes] = []
        for column in required:
            value = row[column]
            if not isinstance(value, str) or not value or value != value.strip():
                raise ClosurePipeTrainingError(f"Sequence key {column} is not a canonical string")
            values.append(value.encode("utf-8"))
        keys.append((values[0], values[1], values[2], values[3], index))
    return [item[-1] for item in sorted(keys)]


def _list_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows: list[np.ndarray] = []
    for row in frame.to_dict(orient="records"):
        if str(row["sequence_status"]) != "success":
            rows.append(np.full((HISTORY_LENGTH, len(INPUT_COLUMNS)), np.nan, dtype=np.float32))
            continue
        columns: list[np.ndarray] = []
        for column in INPUT_COLUMNS:
            value = row[column]
            array = np.asarray(value)
            if array.shape != (HISTORY_LENGTH,):
                raise ClosurePipeTrainingError(
                    f"{column} must be a fixed-size list with length {HISTORY_LENGTH}"
                )
            if array.dtype != np.float32:
                array = array.astype(np.float32)
            columns.append(array)
        rows.append(np.column_stack(columns).astype(np.float32, copy=False))
    return np.stack(rows).astype(np.float32, copy=False)


def load_window_bundle(
    frame: pd.DataFrame,
    *,
    model_id: str,
    base_seed: int,
    enforce_locked_denominators: bool = True,
) -> WindowBundle:
    """Validate and tensorize Closure windows without dropping fit failures."""
    availability = inspect_fit_availability(
        frame,
        model_id=model_id,
        base_seed=base_seed,
        enforce_locked_denominators=enforce_locked_denominators,
    )
    missing = sorted(set(SEQUENCE_COLUMNS).difference(frame.columns))
    if missing:
        raise ClosurePipeTrainingError(f"Sequence rows are missing closed columns: {missing}")
    if frame.empty:
        raise ClosurePipeTrainingError("Sequence rows cannot be empty")
    working = frame.loc[:, SEQUENCE_COLUMNS].copy()
    if set(working["sequence_version"].astype(str)) != {SEQUENCE_VERSION}:
        raise ClosurePipeTrainingError("Sequence version differs from the Closure contract")
    if set(working["model_id"].astype(str)) != {model_id}:
        raise ClosurePipeTrainingError("Sequence model_id differs from the requested model")
    if model_id == "P0":
        if not bool(working["base_seed"].isna().all()):
            raise ClosurePipeTrainingError("The shared P0 sequence must not contain a seed")
    else:
        observed_seeds = pd.to_numeric(working["base_seed"], errors="coerce")
        if bool(observed_seeds.isna().any()) or set(observed_seeds.astype(int)) != {base_seed}:
            raise ClosurePipeTrainingError("P1 sequence seed differs from the paired temporal seed")
    if set(working["assignment_role"].astype(str)) != {"development"}:
        raise ClosurePipeTrainingError("Temporal fit received a non-development sequence")
    observed_roles = set(working["time_role"].astype(str))
    if not observed_roles.issubset(PERMITTED_SEQUENCE_ROLES):
        raise ClosurePipeTrainingError("Temporal fit received a forbidden role")
    if bool(working.duplicated(["source_id", "site_id", "origin_year_month"], keep=False).any()):
        raise ClosurePipeTrainingError("Sequence rows contain duplicate common origins")

    fit_mask = working["time_role"].isin(FIT_ROLES)
    if not availability.available:
        raise ClosurePipeTrainingError(
            "Training/model-selection intent rows contain retained failures: "
            f"{availability.fit_status_counts}"
        )
    if not bool(working.loc[fit_mask, "sequence_status"].eq("success").all()):
        raise ClosurePipeTrainingError("Fit roles contain an unknown sequence status")

    order = _canonical_order(working)
    working = working.iloc[order].reset_index(drop=True)
    x = _list_matrix(working)
    y = working.loc[:, TARGET_COLUMNS].to_numpy(dtype=np.float32)
    fit_positions = working["time_role"].isin(FIT_ROLES).to_numpy()
    if not np.isfinite(x[fit_positions]).all() or not np.isfinite(y[fit_positions]).all():
        raise ClosurePipeTrainingError("Fit tensors contain nonfinite values; replacement is forbidden")
    if not set(FIT_ROLES).issubset(set(working["time_role"])):
        raise ClosurePipeTrainingError("Training and model_selection must both contain windows")
    return WindowBundle(metadata=working, x=x, y=y)


def configure_deterministic_runtime(base_seed: int, device: str) -> Any:
    """Configure the exact seeded Torch runtime on an explicit device."""
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise ClosurePipeTrainingError(f"Unregistered Closure temporal seed: {base_seed!r}")
    if device != LOCKED_DEVICE:
        raise ClosurePipeTrainingError(f"Closure V1 E0-DL device must be {LOCKED_DEVICE!r}")
    random.seed(base_seed)
    np.random.seed(base_seed)
    torch = _require_torch()
    torch.manual_seed(base_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(base_seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    return torch.device(device)


def canonical_window_keys(metadata: pd.DataFrame) -> list[list[str]]:
    return [
        [
            str(row["source_id"]),
            str(row["site_id"]),
            str(row["origin_year_month"]),
            str(row["target_year_month"]),
        ]
        for row in metadata.to_dict(orient="records")
    ]


def canonical_epoch_batches(
    keys: Sequence[Sequence[str]],
    *,
    base_seed: int,
    epoch: int,
    batch_size: int = BATCH_SIZE,
) -> tuple[list[np.ndarray], str]:
    """Return the locked epoch permutation and its compact-JSON batch digest.

    Each LF-terminated record is exactly
    ``[E,B,[[source,site,origin,target],...]]``.
    Epoch and batch are one-based.  The key list preserves the Torch randperm
    order and therefore also locks the final partial batch.
    """
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise ClosurePipeTrainingError(f"Unregistered Closure temporal seed: {base_seed!r}")
    if type(epoch) is not int or not 1 <= epoch <= MAXIMUM_EPOCHS:
        raise ClosurePipeTrainingError("Epoch must be an integer in [1, 20]")
    if type(batch_size) is not int or batch_size < 1:
        raise ClosurePipeTrainingError("Batch size must be a positive integer")
    normalized: list[list[str]] = []
    for key in keys:
        if len(key) != 4 or any(not isinstance(value, str) for value in key):
            raise ClosurePipeTrainingError("Canonical batch keys must contain four strings")
        normalized.append(list(key))
    torch = _require_torch()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(base_seed + epoch)
    permutation = torch.randperm(len(normalized), generator=generator).cpu().numpy().astype("int64")
    batches = [permutation[start : start + batch_size] for start in range(0, len(permutation), batch_size)]
    digest = hashlib.sha256()
    for batch_number, indices in enumerate(batches, start=1):
        record = [
            epoch,
            batch_number,
            [normalized[int(index)] for index in indices],
        ]
        digest.update(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        )
    return batches, digest.hexdigest()


def closure_training_loss(mu: Any, logvar: Any, target: Any, weights: Any) -> Any:
    """Apply the locked weighted Gaussian NLL plus unit-weight MSE."""
    return training_loss(mu, logvar, target, weights, MSE_WEIGHT)


def advance_early_stopping(
    state: EarlyStoppingState,
    *,
    epoch: int,
    objective: float,
) -> EarlyStoppingState:
    if not np.isfinite(objective):
        raise ClosurePipeTrainingError("Checkpoint objective must be finite")
    if objective < state.best_objective - EARLY_STOPPING_MINIMUM_DELTA:
        return EarlyStoppingState(
            best_objective=float(objective),
            best_epoch=int(epoch),
            epochs_without_improvement=0,
            should_stop=False,
        )
    without_improvement = state.epochs_without_improvement + 1
    return EarlyStoppingState(
        best_objective=state.best_objective,
        best_epoch=state.best_epoch,
        epochs_without_improvement=without_improvement,
        should_stop=without_improvement >= EARLY_STOPPING_PATIENCE,
    )


def _persistence_scales(bundle: WindowBundle) -> tuple[np.ndarray, np.ndarray]:
    persistence = bundle.x[:, -1, : len(TARGET_COLUMNS)].astype(np.float64)
    target = bundle.y.astype(np.float64)
    error = persistence - target
    rmse = np.sqrt(np.mean(error**2, axis=0))
    mae = np.mean(np.abs(error), axis=0)
    return np.maximum(rmse, 1e-12), np.maximum(mae, 1e-12)


def _checkpoint_objective(
    metrics: pd.DataFrame,
    persistence_scales: tuple[np.ndarray, np.ndarray],
) -> float:
    targets = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    indexed = metrics.loc[metrics["target"].isin(targets)].set_index("target")
    if len(indexed) != len(targets) or set(indexed.index.astype(str)) != set(targets):
        raise ClosurePipeTrainingError("Model-selection metrics lack nine unique target rows")
    current_rmse = indexed.loc[targets, "rmse"].to_numpy(dtype=np.float64)
    current_mae = indexed.loc[targets, "mae"].to_numpy(dtype=np.float64)
    rmse_scale, mae_scale = persistence_scales
    if rmse_scale.shape != (len(targets),) or mae_scale.shape != (len(targets),):
        raise ClosurePipeTrainingError("Persistence scales must retain all nine targets")
    per_target = 0.5 * current_rmse / rmse_scale + 0.5 * current_mae / mae_scale
    if not np.isfinite(per_target).all():
        raise ClosurePipeTrainingError("Checkpoint objective contains nonfinite target ratios")
    return float(np.mean(per_target))


def _train_epoch(
    model: Any,
    bundle: WindowBundle,
    batches: Sequence[np.ndarray],
    *,
    optimizer: Any,
    weights: Any,
    device: Any,
) -> float:
    torch = _require_torch()
    model.train()
    total_loss = 0.0
    total_rows = 0
    for indices in batches:
        x_batch = torch.from_numpy(bundle.x[indices]).to(device=device, dtype=torch.float32)
        y_batch = torch.from_numpy(bundle.y[indices]).to(device=device, dtype=torch.float32)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(x_batch)
        loss = closure_training_loss(mu, logvar, y_batch, weights)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRADIENT_CLIP_NORM)
        optimizer.step()
        rows = int(len(indices))
        total_loss += float(loss.item()) * rows
        total_rows += rows
    return total_loss / max(total_rows, 1)


def fit_closure_pipe(
    bundle: WindowBundle,
    *,
    model_id: str,
    base_seed: int,
    device: str,
) -> ClosureFitResult:
    """Run the non-configurable P0/P1 fit after an external gate authorizes it."""
    validate_temporal_seed(model_id, base_seed)
    torch_device = configure_deterministic_runtime(base_seed, device)
    training = bundle.subset("training")
    selection = bundle.subset("model_selection")
    if len(training.metadata) == 0 or len(selection.metadata) == 0:
        raise ClosurePipeTrainingError("Training and model_selection windows are both required")

    torch = _require_torch()
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=HIDDEN_DIMENSION,
        num_layers=RECURRENT_LAYERS,
        dropout=DROPOUT,
        residual_mode=RESIDUAL_MODE,
    ).to(torch_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    weights = torch.from_numpy(make_loss_weights()).to(device=torch_device, dtype=torch.float32)
    selection_dataset = TensorWindowDataset(selection.x, selection.y)
    selection_scales = _persistence_scales(selection)
    training_keys = canonical_window_keys(training.metadata)

    stopping = EarlyStoppingState()
    best_state_dict: dict[str, Any] | None = None
    history_rows: list[dict[str, Any]] = []
    provisional_parts: list[pd.DataFrame] = []
    provisional_search_parts: list[pd.DataFrame] = []
    for epoch in range(1, MAXIMUM_EPOCHS + 1):
        batches, batch_digest = canonical_epoch_batches(
            training_keys,
            base_seed=base_seed,
            epoch=epoch,
        )
        train_loss = _train_epoch(
            model,
            training,
            batches,
            optimizer=optimizer,
            weights=weights,
            device=torch_device,
        )
        provisional, provisional_search = select_output_blend_weights(
            model,
            cast(Any, selection_dataset),
            batch_size=BATCH_SIZE,
            grid=list(BLEND_GRID),
            selection_metric="balanced",
            device=torch_device,
        )
        provisional = provisional.copy()
        provisional.insert(0, "epoch", epoch)
        provisional.insert(1, "blend_stage", "provisional")
        provisional_parts.append(provisional)
        provisional_search = provisional_search.copy()
        provisional_search.insert(0, "epoch", epoch)
        provisional_search.insert(1, "blend_stage", "provisional_search")
        provisional_search_parts.append(provisional_search)
        blend_tensor = _blend_weight_tensor(provisional, torch_device)
        selection_metrics, _ = evaluate_model(
            model,
            cast(Any, selection_dataset),
            batch_size=BATCH_SIZE,
            weights=weights,
            device=torch_device,
            blend_weights=blend_tensor,
        )
        objective = _checkpoint_objective(selection_metrics, selection_scales)
        previous_best = stopping.best_objective
        stopping = advance_early_stopping(stopping, epoch=epoch, objective=objective)
        if objective < previous_best:
            best_state_dict = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
        history_rows.append(
            {
                "epoch": epoch,
                "training_loss": float(train_loss),
                "model_selection_objective": float(objective),
                "best_objective": float(stopping.best_objective),
                "best_epoch": int(stopping.best_epoch),
                "epochs_without_improvement": int(stopping.epochs_without_improvement),
                "batch_order_sha256": batch_digest,
            }
        )
        if stopping.should_stop:
            break

    if best_state_dict is None or stopping.best_epoch < 1:
        raise ClosurePipeTrainingError("No finite raw checkpoint was selected")
    model.load_state_dict(best_state_dict)

    final_weights, final_search = select_output_blend_weights(
        model,
        cast(Any, selection_dataset),
        batch_size=BATCH_SIZE,
        grid=list(BLEND_GRID),
        selection_metric="balanced",
        device=torch_device,
    )
    final_weights = final_weights.copy()
    final_weights.insert(0, "blend_stage", "final_after_raw_best_restore")
    final_search = final_search.copy()
    final_search.insert(0, "blend_stage", "final_after_raw_best_restore")
    final_tensor = _blend_weight_tensor(final_weights, torch_device)

    metric_parts: list[pd.DataFrame] = []
    for role, role_bundle in (("training", training), ("model_selection", selection)):
        metrics, _ = evaluate_model(
            model,
            cast(Any, TensorWindowDataset(role_bundle.x, role_bundle.y)),
            batch_size=BATCH_SIZE,
            weights=weights,
            device=torch_device,
            blend_weights=final_tensor,
        )
        metrics.insert(0, "time_role", role)
        metric_parts.append(metrics)
    metrics = pd.concat(metric_parts, ignore_index=True)
    return ClosureFitResult(
        model=model,
        best_state_dict=best_state_dict,
        best_epoch=stopping.best_epoch,
        best_objective=stopping.best_objective,
        history=pd.DataFrame(history_rows),
        provisional_blends=pd.concat(provisional_parts, ignore_index=True),
        provisional_blend_searches=pd.concat(provisional_search_parts, ignore_index=True),
        final_blend_weights=final_weights,
        final_blend_search=final_search,
        metrics=metrics,
    )


def fit_available_slot(
    bundle: WindowBundle,
    *,
    model_id: str,
    base_seed: int,
    device: str,
) -> ClosureFitResult:
    """Invoke an available fit without translating technical failures into slot evidence."""
    return fit_closure_pipe(
        bundle,
        model_id=model_id,
        base_seed=base_seed,
        device=device,
    )


def fixed_profile() -> dict[str, Any]:
    return {
        "history_length": HISTORY_LENGTH,
        "input_dimension": len(INPUT_COLUMNS),
        "target_dimension": len(TARGET_COLUMNS),
        "hidden_dimension": HIDDEN_DIMENSION,
        "recurrent_layers": RECURRENT_LAYERS,
        "dropout": DROPOUT,
        "residual_mode": RESIDUAL_MODE,
        "optimizer": "AdamW",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_clip_norm": GRADIENT_CLIP_NORM,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAXIMUM_EPOCHS,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "early_stopping_minimum_delta": EARLY_STOPPING_MINIMUM_DELTA,
        "mse_weight": MSE_WEIGHT,
        "target_weights": TARGET_WEIGHTS,
        "blend_grid": list(BLEND_GRID),
        "cpu_execution_policy": dict(EXPECTED_CPU_EXECUTION_POLICY),
    }


def validate_sequence_physical_schema(schema: pa.Schema) -> None:
    if schema.names != list(SEQUENCE_COLUMNS):
        raise ClosurePipeTrainingError("Sequence Parquet columns/order differ from the closed schema")
    string_columns = set(SEQUENCE_COLUMNS).difference(
        {"base_seed", "history_length_months", *INPUT_COLUMNS, *TARGET_COLUMNS}
    )
    for column in string_columns:
        field = schema.field(column)
        if field.type != pa.string() or field.nullable:
            raise ClosurePipeTrainingError(f"Sequence physical identity field drifted: {column}")
    base_seed_field = schema.field("base_seed")
    if base_seed_field.type != pa.int64() or not base_seed_field.nullable:
        raise ClosurePipeTrainingError("Sequence physical base_seed field drifted")
    history_length_field = schema.field("history_length_months")
    if history_length_field.type != pa.int16() or history_length_field.nullable:
        raise ClosurePipeTrainingError("Sequence physical history_length_months field drifted")
    for column in INPUT_COLUMNS:
        field = schema.field(column)
        if (
            not pa.types.is_fixed_size_list(field.type)
            or field.type.list_size != HISTORY_LENGTH
            or field.type.value_type != pa.float32()
            or not field.nullable
        ):
            raise ClosurePipeTrainingError(f"Sequence physical input field drifted: {column}")
    for column in TARGET_COLUMNS:
        field = schema.field(column)
        if field.type != pa.float32() or not field.nullable:
            raise ClosurePipeTrainingError(f"Sequence physical target field drifted: {column}")


def _authority_file_record(
    payload: object,
    *,
    field: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ClosurePipeTrainingError(f"Temporal validation authority field {field!r} drifted")
    record = dict(cast(Mapping[str, Any], payload))
    if set(record) != {"path", "bytes", "sha256"}:
        raise ClosurePipeTrainingError(f"Temporal validation authority field {field!r} drifted")
    path = record.get("path")
    size = record.get("bytes")
    digest = record.get("sha256")
    if (
        path != SEQUENCE_BUILDER_PATH.as_posix()
        or type(size) is not int
        or size < 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ClosurePipeTrainingError(f"Temporal validation authority field {field!r} drifted")
    return {"path": path, "bytes": size, "sha256": digest}


def builder_records_from_temporal_validation_authority(
    authority: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve sealed artifact provenance separately from the live runtime source."""
    p0_artifact = _authority_file_record(
        authority.get("p0_artifact_builder_record"),
        field="p0_artifact_builder_record",
    )
    if p0_artifact != P0_ARTIFACT_BUILDER_RECORD:
        raise ClosurePipeTrainingError("P0 artifact builder authority drifted")
    current_runtime = _authority_file_record(
        authority.get("current_runtime_builder_record"),
        field="current_runtime_builder_record",
    )
    observed_runtime = _file_record(PROJECT_ROOT / SEQUENCE_BUILDER_PATH)
    if current_runtime != observed_runtime:
        raise ClosurePipeTrainingError("Current runtime builder differs from E0-DLTV authority")
    return p0_artifact, current_runtime


def collect_sequence_input_contract(
    *,
    model_id: str,
    base_seed: int,
    artifact_builder_record: Mapping[str, Any],
    current_runtime_builder_record: Mapping[str, Any],
) -> SequenceInputContract:
    """Snapshot immutable manifest provenance and live runtime inputs separately."""
    validate_temporal_seed(model_id, base_seed)
    artifact_builder = _authority_file_record(
        artifact_builder_record,
        field="artifact_builder_record",
    )
    current_runtime_builder = _authority_file_record(
        current_runtime_builder_record,
        field="current_runtime_builder_record",
    )
    observed_runtime_builder = _file_record(PROJECT_ROOT / SEQUENCE_BUILDER_PATH)
    if current_runtime_builder != observed_runtime_builder:
        raise ClosurePipeTrainingError("Current runtime builder differs from E0-DLTV authority")
    if model_id == "P0":
        if artifact_builder != P0_ARTIFACT_BUILDER_RECORD:
            raise ClosurePipeTrainingError("P0 artifact builder authority drifted")
    elif artifact_builder != current_runtime_builder:
        raise ClosurePipeTrainingError("P1 sequence builder must match the current runtime builder")
    sequence_seed: int | None = None if model_id == "P0" else base_seed
    paths = sequence_paths(model_id, sequence_seed)
    state_path = PROJECT_ROOT / paths["state"]
    state_manifest_path = PROJECT_ROOT / paths["state_manifest"]
    state_manifest_before = _file_record(state_manifest_path)
    state_before = _file_record(state_path) if state_path.is_file() else None
    with state_manifest_path.open(encoding="utf-8") as handle:
        state_manifest = json.load(handle)
    if not isinstance(state_manifest, Mapping):
        raise ClosurePipeTrainingError("Sequence state manifest must contain a JSON object")
    state_available, _, diagnostic_state_declared = validate_state_slot_manifest(
        state_manifest,
        model_id=model_id,
        base_seed=sequence_seed,
        state_path=state_path,
    )
    state_required = state_available or diagnostic_state_declared
    if _file_record(state_manifest_path) != state_manifest_before:
        raise ClosurePipeTrainingError("Sequence state manifest changed during validation")
    if state_required:
        if state_before is None or _file_record(state_path) != state_before:
            raise ClosurePipeTrainingError("Sequence state artifact changed during validation")
    elif state_path.exists():
        raise ClosurePipeTrainingError(
            "Unavailable pre-fit sequence slot retains an unexpected state artifact"
        )
    fixed_paths = (
        PROJECT_ROOT / DEFAULT_COMMON_ORIGINS,
        PROJECT_ROOT / DEFAULT_COMMON_COMPLETION,
        PROJECT_ROOT / DEFAULT_RUNTIME_CONFIG,
        PROJECT_ROOT / DEFAULT_RUNTIME_SCHEMA,
        PROJECT_ROOT / DEFAULT_RUNTIME_LOCK,
        PROJECT_ROOT / DEFAULT_ASSIGNMENT,
        PROJECT_ROOT / DEFAULT_HOLDOUT_MANIFEST,
        PROJECT_ROOT / DEFAULT_PROTOCOL_LOCK,
        PROJECT_ROOT / SEQUENCE_BUILDER_PATH,
    )
    live_records = [*(_file_record(path) for path in fixed_paths), state_manifest_before]
    if state_required:
        assert state_before is not None
        live_records.append(state_before)
    live_paths = [str(record["path"]) for record in live_records]
    if len(live_paths) != len(set(live_paths)):
        raise ClosurePipeTrainingError("Live sequence input contract contains duplicate paths")
    manifest_records = [
        dict(artifact_builder)
        if record["path"] == SEQUENCE_BUILDER_PATH.as_posix()
        else dict(record)
        for record in live_records
    ]
    manifest_paths = [str(record["path"]) for record in manifest_records]
    if manifest_paths != live_paths:
        raise ClosurePipeTrainingError("Sequence manifest/live input path ordering drifted")
    return SequenceInputContract(
        manifest_input_records=tuple(manifest_records),
        live_physical_records=tuple(live_records),
        state_path=state_path,
        state_artifact_required=state_required,
    )


def assert_sequence_input_contract_unchanged(contract: SequenceInputContract) -> None:
    for record in contract.live_physical_records:
        path = PROJECT_ROOT / str(record["path"])
        if _file_record(path) != record:
            raise ClosurePipeTrainingError(
                f"Sequence upstream input changed during execution: {record['path']}"
            )
    if not contract.state_artifact_required and contract.state_path.exists():
        raise ClosurePipeTrainingError(
            "Unavailable pre-fit sequence state appeared during execution"
        )


def collect_temporal_model_input_contract(
    *,
    model_id: str,
    base_seed: int,
    sequence_contract: SequenceInputContract,
) -> TemporalModelInputContract:
    sequence_seed: int | None = None if model_id == "P0" else base_seed
    sequence_info = sequence_paths(model_id, sequence_seed)
    source_paths = (
        PROJECT_ROOT / "src/experiments/train_closure_pipe.py",
        PROJECT_ROOT / "src/experiments/build_closure_pipe_sequences.py",
        PROJECT_ROOT / "src/experiments/closure_contract.py",
        PROJECT_ROOT / "src/experiments/closure_development_guard.py",
        PROJECT_ROOT / "src/experiments/closure_development_runtime_lock.py",
        PROJECT_ROOT
        / "src/experiments/closure_development_runtime_temporal_consumer_patch.py",
        PROJECT_ROOT
        / "src/experiments/closure_development_runtime_temporal_validation_patch.py",
        PROJECT_ROOT / "src/experiments/closure_runtime_contract.py",
        PROJECT_ROOT / "src/experiments/train_pipe_grud.py",
    )
    dependency_paths = (
        PROJECT_ROOT / sequence_info["sequence"],
        PROJECT_ROOT / sequence_info["summary"],
        PROJECT_ROOT / sequence_info["manifest"],
        *source_paths,
    )
    records = {
        str(record["path"]): dict(record)
        for record in sequence_contract.live_physical_records
    }
    for path in dependency_paths:
        record = _file_record(path)
        existing = records.get(str(record["path"]))
        if existing is not None and existing != record:
            raise ClosurePipeTrainingError(
                f"Temporal model input record conflicts at {record['path']}"
            )
        records[str(record["path"])] = record
    source_records = tuple(_file_record(path) for path in source_paths)
    if len(records) != len({str(record["path"]) for record in records.values()}):
        raise ClosurePipeTrainingError("Temporal model input paths must be unique")
    return TemporalModelInputContract(
        records=tuple(records.values()),
        source_code_records=source_records,
        sequence_contract=sequence_contract,
    )


def assert_temporal_model_input_contract_unchanged(
    contract: TemporalModelInputContract,
) -> None:
    assert_sequence_input_contract_unchanged(contract.sequence_contract)
    for record in contract.records:
        path = PROJECT_ROOT / str(record["path"])
        if _file_record(path) != record:
            raise ClosurePipeTrainingError(
                f"Temporal model input changed during execution: {record['path']}"
            )


def validate_sequence_manifest_builder_binding(
    payload: Mapping[str, Any],
    *,
    artifact_builder_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind immutable sequence provenance without conflating it with live source bytes."""
    expected = _authority_file_record(
        artifact_builder_record,
        field="artifact_builder_record",
    )
    if payload.get("script") != expected or payload.get("source_code") != [expected]:
        raise ClosurePipeTrainingError("Sequence manifest is not bound to its exact builder code")
    return expected


def validate_sequence_completion_manifest(
    payload: Mapping[str, Any],
    *,
    sequence_record: Mapping[str, Any],
    summary_record: Mapping[str, Any],
    expected_input_records: Sequence[Mapping[str, Any]],
    artifact_builder_record: Mapping[str, Any],
    model_id: str,
    base_seed: int,
) -> None:
    expected_top_level = {
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
    if set(payload) != expected_top_level:
        raise ClosurePipeTrainingError("Sequence manifest top-level dialect drifted")
    expected = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": model_id,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected.items():
        if type(payload.get(field)) is not type(value) or payload.get(field) != value:
            raise ClosurePipeTrainingError(f"Sequence manifest field {field!r} drifted")
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise ClosurePipeTrainingError("Sequence manifest generated_at_utc drifted")
    try:
        datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ClosurePipeTrainingError("Sequence manifest generated_at_utc drifted") from exc
    expected_sequence_seed: int | None = None if model_id == "P0" else base_seed
    if type(payload.get("base_seed")) is not type(expected_sequence_seed) or payload.get(
        "base_seed"
    ) != expected_sequence_seed:
        raise ClosurePipeTrainingError("Sequence manifest seed differs from its model slot")
    exact_sections = {
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "input_state_mapping": MODEL_STATE_MAPPINGS[model_id],
        "target_state_mapping": MODEL_STATE_MAPPINGS[model_id],
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
    }
    for field, value in exact_sections.items():
        if not _typed_scalar_equal(payload.get(field), value):
            raise ClosurePipeTrainingError(f"Sequence manifest section {field!r} drifted")
    expected_script = validate_sequence_manifest_builder_binding(
        payload,
        artifact_builder_record=artifact_builder_record,
    )
    counts = payload.get("counts")
    if not isinstance(counts, Mapping):
        raise ClosurePipeTrainingError("Sequence manifest counts are missing")
    if counts.get("intent_origins") != EXPECTED_INTENT_ORIGINS:
        raise ClosurePipeTrainingError("Sequence manifest intent denominator drifted")
    if counts.get("role_counts") != EXPECTED_INTENT_ORIGINS_BY_ROLE:
        raise ClosurePipeTrainingError("Sequence manifest role denominators drifted")
    inputs = payload.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)):
        raise ClosurePipeTrainingError("Sequence manifest inputs must be an array")
    actual_inputs: dict[str, Mapping[str, Any]] = {}
    for record in inputs:
        if not isinstance(record, Mapping) or set(record) != {"path", "bytes", "sha256"}:
            raise ClosurePipeTrainingError("Sequence manifest input record dialect drifted")
        raw_path = record.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ClosurePipeTrainingError("Sequence manifest input path is invalid")
        logical_path = Path(raw_path)
        if (
            logical_path.is_absolute()
            or ".." in logical_path.parts
            or logical_path.as_posix() != raw_path
        ):
            raise ClosurePipeTrainingError(
                "Sequence manifest input paths must be canonical repository-relative paths"
            )
        if raw_path in actual_inputs:
            raise ClosurePipeTrainingError("Sequence manifest input paths must be unique")
        if raw_path == expected_script["path"]:
            if not _typed_scalar_equal(dict(record), expected_script):
                raise ClosurePipeTrainingError(
                    "Sequence manifest builder input differs from sealed artifact provenance"
                )
        else:
            physical_path = PROJECT_ROOT / logical_path
            try:
                physical_path.resolve().relative_to(PROJECT_ROOT.resolve())
            except ValueError as exc:
                raise ClosurePipeTrainingError(
                    "Sequence manifest input path escapes the repository root"
                ) from exc
            if not physical_path.is_file() or not _typed_scalar_equal(
                dict(record),
                _file_record(physical_path),
            ):
                raise ClosurePipeTrainingError(
                    f"Sequence manifest input record differs from physical bytes: {raw_path}"
                )
        actual_inputs[raw_path] = record
    expected_inputs = {str(record.get("path")): record for record in expected_input_records}
    if len(expected_inputs) != len(expected_input_records):
        raise ClosurePipeTrainingError("Expected sequence input records must be unique")
    if expected_script["path"] not in expected_inputs:
        raise ClosurePipeTrainingError("Expected sequence inputs omit the exact builder code")
    if set(actual_inputs) != set(expected_inputs):
        raise ClosurePipeTrainingError("Sequence manifest input path set drifted")
    for path, expected_record in expected_inputs.items():
        if any(
            not _typed_scalar_equal(actual_inputs[path].get(key), expected_record.get(key))
            for key in ("path", "bytes", "sha256")
        ):
            raise ClosurePipeTrainingError(f"Sequence manifest input record drifted: {path}")
    outputs = payload.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise ClosurePipeTrainingError("Sequence manifest outputs must be an array")
    output_paths = [
        str(record.get("path")) for record in outputs if isinstance(record, Mapping)
    ]
    if len(output_paths) != len(set(output_paths)) or len(outputs) != 2:
        raise ClosurePipeTrainingError("Sequence manifest must bind two unique outputs")
    for label, expected_record in (("Parquet", sequence_record), ("summary", summary_record)):
        matches = [
            record
            for record in outputs
            if isinstance(record, Mapping) and record.get("path") == expected_record.get("path")
        ]
        if len(matches) != 1 or any(
            not _typed_scalar_equal(matches[0].get(key), expected_record.get(key))
            for key in ("path", "bytes", "sha256")
        ):
            raise ClosurePipeTrainingError(f"Sequence manifest {label} hash/bytes drifted")


def validate_sequence_common_origin_identity(
    sequences: pd.DataFrame,
    common_origins: pd.DataFrame,
    *,
    expected_origin_count: int | None = EXPECTED_INTENT_ORIGINS,
) -> None:
    """Require a one-to-one identity match with the h1 common-origin contract."""
    origins = _validate_common_origins(
        common_origins,
        expected_origin_count=expected_origin_count,
    )
    identity_columns = (
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
        "history_length_months",
    )
    missing = sorted(set(identity_columns).difference(sequences.columns))
    if missing:
        raise ClosurePipeTrainingError(f"Sequence identity columns are missing: {missing}")
    sequence_identity = sequences.loc[:, identity_columns].copy()
    common_identity = origins.loc[:, identity_columns].copy()
    sequence_order = _canonical_order(sequence_identity)
    common_order = _canonical_order(common_identity)
    sequence_records = sequence_identity.iloc[sequence_order].reset_index(drop=True).to_dict(
        orient="records"
    )
    common_records = common_identity.iloc[common_order].reset_index(drop=True).to_dict(
        orient="records"
    )
    if sequence_records != common_records:
        raise ClosurePipeTrainingError(
            "Sequence identities differ from the locked common-origin h1 identities"
        )


def _paths(model_id: str, base_seed: int) -> dict[str, Path]:
    root = Path(f"reports/closure_v1/02_models/{model_id}")
    model_root = Path(f"models/closure_v1/pipe/{model_id}")
    return {
        "model": model_root / f"seed_{base_seed}.pt",
        "checkpoint": model_root / f"seed_{base_seed}.checkpoint.pt",
        "preprocessor": root / f"seed_{base_seed}_preprocessor.json",
        "metrics": root / f"seed_{base_seed}_metrics.csv",
        "training_curve": root / f"seed_{base_seed}_training_curve.csv",
        "blend_weights": root / f"seed_{base_seed}_blend_weights.csv",
        "blend_search": root / f"seed_{base_seed}_blend_search.csv",
        "report": root / f"seed_{base_seed}_report.md",
        "manifest": root / f"seed_{base_seed}_manifest.json",
    }


@dataclass(frozen=True)
class _OwnedOutput:
    path: Path
    device: int
    inode: int
    directory_descriptor: int


def _path_entry_exists(path: Path) -> bool:
    """Return true for every lexical entry, including a broken symlink."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _open_real_output_parent(path: Path, *, directory_mode: int = 0o755) -> int:
    """Open an anchored real-directory parent without following symlinks."""
    try:
        repository_root = PROJECT_ROOT.resolve(strict=True)
        lexical_parent = Path(os.path.abspath(path.parent))
        relative_parent = lexical_parent.relative_to(repository_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ClosurePipeTrainingError(f"Output parent escapes the repository: {path}") from exc
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(repository_root, directory_flags)
    except OSError as exc:
        raise ClosurePipeTrainingError("Repository root cannot be opened safely") from exc
    try:
        for part in relative_parent.parts:
            try:
                metadata = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                except FileExistsError:
                    pass
                metadata = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosurePipeTrainingError(
                    f"Output ancestor is not a real directory: {path}"
                )
            child = os.open(part, directory_flags, dir_fd=descriptor)
            try:
                opened_child = os.fstat(child)
            except BaseException:
                os.close(child)
                raise
            if (opened_child.st_dev, opened_child.st_ino) != (
                metadata.st_dev,
                metadata.st_ino,
            ):
                os.close(child)
                raise ClosurePipeTrainingError(f"Output ancestor identity drifted: {path}")
            parent_descriptor = descriptor
            descriptor = child
            os.close(parent_descriptor)
        opened = os.fstat(descriptor)
        lexical = lexical_parent.lstat()
        if (
            not stat.S_ISDIR(lexical.st_mode)
            or (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            raise ClosurePipeTrainingError(f"Output parent identity drifted: {path}")
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
) -> bool:
    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ClosurePipeTrainingError(
            f"Cannot inspect owned temporal artifact during cleanup: {name}"
        ) from exc
    if (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == (device, inode)
    ):
        try:
            os.unlink(name, dir_fd=directory_descriptor)
        except OSError as exc:
            raise ClosurePipeTrainingError(
                f"Cannot remove owned temporal artifact during cleanup: {name}"
            ) from exc
        return True
    return False


def _write_output_no_clobber_owned(
    path: Path,
    writer: Any,
    *,
    binary: bool,
) -> _OwnedOutput:
    """Publish one regular file through an exclusive inode and hard link."""
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
            descriptor = os.open(temporary.name, flags, 0o644, dir_fd=directory_descriptor)
        except FileExistsError as exc:
            raise ClosurePipeTrainingError(
                f"Refusing to overwrite temporary artifact: {temporary}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ClosurePipeTrainingError(f"Temporary artifact is not regular: {temporary}")
        device, inode = metadata.st_dev, metadata.st_ino
        duplicate = os.dup(descriptor)
        if binary:
            try:
                binary_handle = os.fdopen(duplicate, "wb")
            except BaseException:
                os.close(duplicate)
                raise
            with binary_handle as handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())
        else:
            try:
                text_handle = os.fdopen(
                    duplicate,
                    "w",
                    encoding="utf-8",
                    newline="",
                )
            except BaseException:
                os.close(duplicate)
                raise
            with text_handle as handle:
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
            raise ClosurePipeTrainingError(f"Temporary artifact identity drifted: {temporary}")
        try:
            os.link(
                temporary.name,
                path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ClosurePipeTrainingError(
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
            raise ClosurePipeTrainingError(f"Final artifact identity drifted: {path}")
        temporary_removed = _unlink_name_if_owned(
            directory_descriptor,
            temporary.name,
            device=device,
            inode=inode,
        )
        if not temporary_removed:
            _unlink_name_if_owned(
                directory_descriptor,
                path.name,
                device=device,
                inode=inode,
            )
            raise ClosurePipeTrainingError(
                f"Temporary artifact changed before cleanup: {temporary}"
        )
        os.fsync(directory_descriptor)
        closing_descriptor = descriptor
        descriptor = None
        os.close(closing_descriptor)
        committed = True
        return _OwnedOutput(
            path=path,
            device=device,
            inode=inode,
            directory_descriptor=directory_descriptor,
        )
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
                for name in (path.name, temporary.name):
                    try:
                        _unlink_name_if_owned(
                            directory_descriptor,
                            name,
                            device=device,
                            inode=inode,
                        )
                    except (ClosurePipeTrainingError, OSError) as exc:
                        cleanup_errors.append(exc)
                try:
                    os.fsync(directory_descriptor)
                except OSError as exc:
                    cleanup_errors.append(exc)
            try:
                os.close(directory_descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = ClosurePipeTrainingError(
                "Temporal artifact cleanup could not be completed safely"
            )
            cleanup_error.add_note(
                "Cleanup failures: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in cleanup_errors)
            )
            if active_error is not None:
                raise cleanup_error from active_error
            raise cleanup_error from cleanup_errors[0]


class _TemporalOutputTransaction:
    """Own and roll back every final inode until the manifest is published."""

    def __init__(self) -> None:
        self._owned: list[_OwnedOutput] = []

    def __enter__(self) -> _TemporalOutputTransaction:
        return self

    def _publish(self, path: Path, writer: Any, *, binary: bool) -> None:
        self._owned.append(
            _write_output_no_clobber_owned(path, writer, binary=binary)
        )

    def publish_text(self, text: str, path: Path) -> None:
        self._publish(path, lambda handle: handle.write(text), binary=False)

    def publish_json(self, payload: Mapping[str, Any], path: Path) -> None:
        def write(handle: Any) -> None:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        self._publish(path, write, binary=False)

    def publish_csv(self, frame: pd.DataFrame, path: Path) -> None:
        self._publish(path, lambda handle: frame.to_csv(handle, index=False), binary=False)

    def publish_torch(self, payload: Mapping[str, Any], path: Path) -> None:
        torch = _require_torch()
        self._publish(path, lambda handle: torch.save(dict(payload), handle), binary=True)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        commit_error: ClosurePipeTrainingError | None = None
        rollback_errors: list[Exception] = []
        if exc_type is None:
            for owned in self._owned:
                try:
                    current = os.stat(
                        owned.path.name,
                        dir_fd=owned.directory_descriptor,
                        follow_symlinks=False,
                    )
                    parent_opened = os.fstat(owned.directory_descriptor)
                    parent_lexical = owned.path.parent.lstat()
                except (FileNotFoundError, OSError):
                    commit_error = ClosurePipeTrainingError(
                        f"Temporal output disappeared before commit: {owned.path}"
                    )
                    break
                if (
                    not stat.S_ISREG(current.st_mode)
                    or (current.st_dev, current.st_ino)
                    != (owned.device, owned.inode)
                    or not stat.S_ISDIR(parent_lexical.st_mode)
                    or (parent_lexical.st_dev, parent_lexical.st_ino)
                    != (parent_opened.st_dev, parent_opened.st_ino)
                ):
                    commit_error = ClosurePipeTrainingError(
                        f"Temporal output identity drifted before commit: {owned.path}"
                    )
                    break
        if exc_type is not None or commit_error is not None:
            for owned in reversed(self._owned):
                try:
                    removed = _unlink_name_if_owned(
                        owned.directory_descriptor,
                        owned.path.name,
                        device=owned.device,
                        inode=owned.inode,
                    )
                    if removed:
                        os.fsync(owned.directory_descriptor)
                except (ClosurePipeTrainingError, OSError) as cleanup_error:
                    rollback_errors.append(cleanup_error)
        for owned in self._owned:
            try:
                os.close(owned.directory_descriptor)
            except OSError as cleanup_error:
                # Every file and parent was already fsynced and ownership was
                # revalidated.  A directory-handle close error must not turn a
                # durable manifest-last commit into an unretryable partial slot.
                if exc_type is not None or commit_error is not None:
                    rollback_errors.append(cleanup_error)
        self._owned.clear()
        if rollback_errors:
            rollback_error = ClosurePipeTrainingError(
                "Temporal output rollback could not be completed safely"
            )
            rollback_error.add_note(
                "Rollback failures: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in rollback_errors)
            )
            if exc is not None:
                raise rollback_error from exc
            if commit_error is not None:
                raise rollback_error from commit_error
            raise rollback_error from rollback_errors[0]
        if commit_error is not None:
            raise commit_error
        return False


def assert_temporal_slot_outputs_absent(paths: Mapping[str, Path]) -> None:
    """Refuse implicit resume or overwrite of any retained slot artifact."""
    expected = {*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest"}
    if set(paths) != expected:
        raise ClosurePipeTrainingError("Temporal slot output path set is incomplete")
    candidates = [
        candidate
        for path in paths.values()
        for candidate in (path, path.with_suffix(path.suffix + ".tmp"))
    ]
    existing = [path.as_posix() for path in candidates if _path_entry_exists(path)]
    if existing:
        raise ClosurePipeTrainingError(
            "Temporal resume/overwrite is forbidden; existing slot artifacts require "
            f"explicit review and cleanup: {existing}"
        )


def _write_model_unavailable_evidence(
    *,
    model_id: str,
    base_seed: int,
    device: str,
    paths: Mapping[str, Path],
    input_records: Sequence[Mapping[str, Any]],
    source_code_records: Sequence[Mapping[str, Any]],
    cpu_execution_policy: Mapping[str, Any],
    failure_reason: str,
    fit_status_counts: Mapping[str, int],
    failure_reason_counts: Mapping[str, int],
) -> None:
    report = paths["report"]
    manifest = paths["manifest"]
    stale_fields = tuple(name for name in MODEL_ARTIFACT_OUTPUT_NAMES if name != "report")
    stale = [paths[field] for field in stale_fields if _path_entry_exists(paths[field])]
    if stale:
        raise ClosurePipeTrainingError(
            "Unavailable temporal slot has stale fit outputs: "
            f"{[path.as_posix() for path in stale]}"
        )
    assert_temporal_slot_outputs_absent(paths)
    with _TemporalOutputTransaction() as transaction:
        transaction.publish_text(
            "\n".join(
                [
                    f"# Closure V1 {model_id} seed {base_seed}",
                    "",
                    "Status: `model_unavailable`",
                    f"Failure reason: `{failure_reason}`",
                    "",
                    "No model/checkpoint was emitted and the failed slot was not replaced.",
                    "",
                ]
            ),
            report,
        )
        payload = {
            "manifest_version": "closure_pipe_model_manifest_v1",
            "status": "completed",
            "slot_status": "model_unavailable",
            "fit_status": "not_attempted",
            "failure_reason": failure_reason,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_id": "closure_v1",
            "surface_id": SURFACE_ID,
            "model_id": model_id,
            "base_seed": base_seed,
            "device": device,
            "future_outcomes_accessed": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "failed_slot_replaced": False,
            "replacement_used": False,
            "model_artifact_emitted": False,
            "fit_status_counts": dict(fit_status_counts),
            "failure_reason_counts": dict(failure_reason_counts),
            "script": _file_record(Path(__file__)),
            "cpu_execution_policy": dict(cpu_execution_policy),
            "config": fixed_profile(),
            "input_state_mapping": MODEL_STATE_MAPPINGS[model_id],
            "target_state_mapping": MODEL_STATE_MAPPINGS[model_id],
            "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
            "inputs": [dict(record) for record in input_records],
            "source_code": [dict(record) for record in source_code_records],
            "outputs": [{**_file_record(report), "artifact_role": "report"}],
            "completion_marker_written_last": True,
        }
        transaction.publish_json(payload, manifest)


def _temporal_consumer_guard_directory() -> Path:
    return PROJECT_ROOT / "tmp" / "closure_v1_temporal_consumer"


@contextmanager
def _temporal_slot_guard(model_id: str, base_seed: int) -> Iterator[None]:
    """Reserve exactly one temporal model/seed slot until publication ends."""
    guard_directory = _temporal_consumer_guard_directory()
    guard_name = f"{model_id}_seed_{base_seed}.guard"
    directory_descriptor = _open_real_output_parent(
        guard_directory / guard_name,
        directory_mode=0o700,
    )
    descriptor: int | None = None
    owned_device: int | None = None
    owned_inode: int | None = None
    try:
        opened_directory = os.fstat(directory_descriptor)
        lexical_directory = guard_directory.lstat()
        if (
            not stat.S_ISDIR(lexical_directory.st_mode)
            or (opened_directory.st_dev, opened_directory.st_ino)
            != (lexical_directory.st_dev, lexical_directory.st_ino)
        ):
            raise ClosurePipeTrainingError(
                "Temporal consumer coordination directory identity drifted"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(guard_name, flags, 0o600, dir_fd=directory_descriptor)
        except FileExistsError as exc:
            raise ClosurePipeTrainingError(
                f"A temporal consumer slot is already reserved: {guard_name}"
            ) from exc
        owned = os.fstat(descriptor)
        if not stat.S_ISREG(owned.st_mode):
            raise ClosurePipeTrainingError("Temporal consumer guard is not a regular file")
        owned_device, owned_inode = owned.st_dev, owned.st_ino
        os.fsync(descriptor)
        os.fsync(directory_descriptor)
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
            raise ClosurePipeTrainingError("Temporal consumer guard changed during execution")
    finally:
        active_error = sys.exc_info()[1]
        cleanup_errors: list[Exception] = []
        if owned_device is not None and owned_inode is not None:
            try:
                removed = _unlink_name_if_owned(
                    directory_descriptor,
                    guard_name,
                    device=owned_device,
                    inode=owned_inode,
                )
                if removed:
                    os.fsync(directory_descriptor)
            except (ClosurePipeTrainingError, OSError) as exc:
                cleanup_errors.append(exc)
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        try:
            os.close(directory_descriptor)
        except OSError as exc:
            cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = ClosurePipeTrainingError(
                "Temporal consumer guard cleanup could not be completed safely"
            )
            cleanup_error.add_note(
                "Guard cleanup failures: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in cleanup_errors)
            )
            if active_error is not None:
                raise cleanup_error from active_error
            raise cleanup_error from cleanup_errors[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit strict Closure V1 P0/P1 temporal models.")
    parser.add_argument("--model-id", choices=MODEL_IDS, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--device", choices=[LOCKED_DEVICE], required=True)
    return parser.parse_args()


def _run_temporal_slot(
    *,
    args: argparse.Namespace,
    paths: Mapping[str, Path],
    temporal_validation_authority: Mapping[str, Any],
) -> None:
    p0_artifact_builder, current_runtime_builder = (
        builder_records_from_temporal_validation_authority(
            temporal_validation_authority,
        )
    )
    artifact_builder = (
        p0_artifact_builder if args.model_id == "P0" else current_runtime_builder
    )
    runtime = load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
    validate_temporal_runtime_contract(runtime)
    cpu_execution_policy = configure_torch_cpu_execution_policy(runtime)
    if cpu_execution_policy != expected_cpu_execution_policy_record():
        raise ClosurePipeTrainingError("Applied CPU execution policy drifted")
    assert_temporal_slot_outputs_absent(paths)
    sequence_info = sequence_paths(args.model_id, None if args.model_id == "P0" else args.base_seed)
    sequence_path = PROJECT_ROOT / sequence_info["sequence"]
    sequence_summary_path = PROJECT_ROOT / sequence_info["summary"]
    sequence_manifest_path = PROJECT_ROOT / sequence_info["manifest"]
    common_path = PROJECT_ROOT / DEFAULT_COMMON_ORIGINS
    sequence_input_contract = collect_sequence_input_contract(
        model_id=args.model_id,
        base_seed=args.base_seed,
        artifact_builder_record=artifact_builder,
        current_runtime_builder_record=current_runtime_builder,
    )
    model_input_contract = collect_temporal_model_input_contract(
        model_id=args.model_id,
        base_seed=args.base_seed,
        sequence_contract=sequence_input_contract,
    )
    before = {str(record["path"]): dict(record) for record in model_input_contract.records}
    sequence_before = before[_file_record(sequence_path)["path"]]
    summary_before = before[_file_record(sequence_summary_path)["path"]]
    with sequence_manifest_path.open(encoding="utf-8") as handle:
        sequence_manifest = json.load(handle)
    if not isinstance(sequence_manifest, Mapping):
        raise ClosurePipeTrainingError("Sequence completion manifest must be a JSON object")
    validate_sequence_completion_manifest(
        sequence_manifest,
        sequence_record=sequence_before,
        summary_record=summary_before,
        expected_input_records=sequence_input_contract.manifest_input_records,
        artifact_builder_record=artifact_builder,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    validate_sequence_physical_schema(pq.read_schema(sequence_path))
    frame = pd.read_parquet(sequence_path, columns=list(SEQUENCE_COLUMNS))
    common = pd.read_parquet(common_path, columns=list(COMMON_ORIGIN_REQUIRED_COLUMNS))
    validate_sequence_common_origin_identity(frame, common)
    input_records = list(before.values())
    availability = inspect_fit_availability(
        frame,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    if not availability.available:
        assert_temporal_model_input_contract_unchanged(model_input_contract)
        after = {
            name: _file_record(PROJECT_ROOT / record["path"])
            for name, record in before.items()
        }
        if before != after:
            raise ClosurePipeTrainingError(
                "A trainer dependency changed before unavailable-slot evidence"
            )
        _write_model_unavailable_evidence(
            model_id=args.model_id,
            base_seed=args.base_seed,
            device=args.device,
            paths=paths,
            input_records=input_records,
            source_code_records=model_input_contract.source_code_records,
            cpu_execution_policy=cpu_execution_policy,
            failure_reason=availability.failure_reason,
            fit_status_counts=availability.fit_status_counts,
            failure_reason_counts=availability.failure_reason_counts,
        )
        return
    bundle = load_window_bundle(frame, model_id=args.model_id, base_seed=args.base_seed)
    result = fit_available_slot(
        bundle,
        model_id=args.model_id,
        base_seed=args.base_seed,
        device=args.device,
    )
    assert_temporal_model_input_contract_unchanged(model_input_contract)
    after = {
        name: _file_record(PROJECT_ROOT / record["path"])
        for name, record in before.items()
    }
    if before != after:
        raise ClosurePipeTrainingError("A trainer dependency changed during fitting")
    blend_mapping = dict(
        zip(
            result.final_blend_weights["target"].astype(str),
            result.final_blend_weights["blend_weight"].astype(float),
            strict=True,
        )
    )
    artifact_base = {
        "model_version": MODEL_VERSION,
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": args.model_id,
        "base_seed": args.base_seed,
        "device": args.device,
        "config": fixed_profile(),
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "input_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
        "target_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "best_epoch": result.best_epoch,
        "best_model_selection_objective": result.best_objective,
        "model_state_dict": result.best_state_dict,
    }
    blend_evidence = pd.concat(
        [
            result.provisional_blend_searches,
            result.provisional_blends,
            result.final_blend_search,
        ],
        ignore_index=True,
        sort=False,
    )
    with _TemporalOutputTransaction() as transaction:
        transaction.publish_torch(
            {**artifact_base, "artifact_role": "raw_best_checkpoint"},
            paths["checkpoint"],
        )
        transaction.publish_torch(
            {
                **artifact_base,
                "artifact_role": "final_model_with_locked_output_blend",
                "output_blend_weights": blend_mapping,
            },
            paths["model"],
        )
        transaction.publish_json(
            {
                "preprocessor_version": "closure_identity_float32_v1",
                "policy": "identity_fixed_no_fit",
                "dtype": "float32",
                "input_columns": list(INPUT_COLUMNS),
                "target_columns": list(TARGET_COLUMNS),
                "data_dependent_scaling": False,
                "nonfinite_replacement": False,
            },
            paths["preprocessor"],
        )
        transaction.publish_csv(result.metrics, paths["metrics"])
        transaction.publish_csv(result.history, paths["training_curve"])
        transaction.publish_csv(result.final_blend_weights, paths["blend_weights"])
        transaction.publish_csv(blend_evidence, paths["blend_search"])
        transaction.publish_text(
            "\n".join(
                [
                    f"# Closure V1 {args.model_id} seed {args.base_seed}",
                    "",
                    "Status: `completed`",
                    "",
                    f"Best raw epoch: `{result.best_epoch}`",
                    f"Best model-selection objective: `{result.best_objective:.12g}`",
                    "",
                    "No calibration, test, holdout, or locked-evaluation metric was emitted.",
                    "",
                ]
            ),
            paths["report"],
        )
        manifest = {
            "manifest_version": "closure_pipe_model_manifest_v1",
            "status": "completed",
            "slot_status": "available",
            "fit_status": "passed",
            "failure_reason": "",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_id": "closure_v1",
            "surface_id": SURFACE_ID,
            "model_id": args.model_id,
            "base_seed": args.base_seed,
            "device": args.device,
            "future_outcomes_accessed": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "model_artifact_emitted": True,
            "failed_slot_replaced": False,
            "replacement_used": False,
            "script": _file_record(Path(__file__)),
            "cpu_execution_policy": cpu_execution_policy,
            "config": fixed_profile(),
            "input_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
            "target_state_mapping": MODEL_STATE_MAPPINGS[args.model_id],
            "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
            "selection": {
                "best_epoch": result.best_epoch,
                "best_model_selection_objective": result.best_objective,
                "checkpoint_role": "raw_best_unblended_model_state",
                "final_blend_stage": "once_after_raw_best_restore",
            },
            "batch_order": {
                "algorithm": "torch_randperm_cpu_generator",
                "epoch_seed": "base_seed_plus_one_based_epoch",
                "record_serialization": "compact_json_utf8_lf_per_batch",
                "records": result.history[["epoch", "batch_order_sha256"]].to_dict(
                    orient="records"
                ),
            },
            "row_counts": {
                "training_windows": int(
                    bundle.metadata["time_role"].eq("training").sum()
                ),
                "model_selection_windows": int(
                    bundle.metadata["time_role"].eq("model_selection").sum()
                ),
                "calibration_windows_not_used_for_fit": int(
                    bundle.metadata["time_role"].eq("calibration_threshold").sum()
                ),
                "test_windows": 0,
                "holdout_windows": 0,
            },
            "inputs": input_records,
            "source_code": [
                dict(record) for record in model_input_contract.source_code_records
            ],
            "outputs": [
                {
                    **_file_record(paths[name]),
                    **(
                        {"artifact_role": "final_model_with_locked_output_blend"}
                        if name == "model"
                        else {"artifact_role": "raw_best_checkpoint"}
                        if name == "checkpoint"
                        else {}
                    ),
                }
                for name in MODEL_ARTIFACT_OUTPUT_NAMES
            ],
            "completion_marker_written_last": True,
        }
        transaction.publish_json(manifest, paths["manifest"])


def main() -> None:
    args = parse_args()

    # No sequence/model row or output path is touched before this external gate.
    from src.experiments.closure_development_runtime_temporal_validation_patch import (
        require_development_fit_authorized_with_temporal_validation_patch,
    )

    temporal_validation_authority = (
        require_development_fit_authorized_with_temporal_validation_patch(
            device=args.device,
        )
    )
    validate_temporal_seed(args.model_id, args.base_seed)
    paths = {
        name: PROJECT_ROOT / path
        for name, path in _paths(args.model_id, args.base_seed).items()
    }
    with _temporal_slot_guard(args.model_id, args.base_seed):
        _run_temporal_slot(
            args=args,
            paths=paths,
            temporal_validation_authority=temporal_validation_authority,
        )


if __name__ == "__main__":
    main()
