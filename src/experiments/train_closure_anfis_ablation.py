#!/usr/bin/env python
"""Fit one development-only Closure V1 A0/A1 ANFIS-ablation slot.

The public entry points are fail-closed behind the published E0-MX authority.
Only the frozen development targets through 2020-12 are projected.  Calibration,
holdout, E0-M, E0-U, DVC and network operations are outside this module.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import random
import stat
import subprocess
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
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits

from src.experiments.build_closure_anfis_ablation_sequences import (
    A0_INPUT_COLUMNS,
    A1_INPUT_COLUMNS,
    IDENTITY_COLUMNS as SEQUENCE_IDENTITY_COLUMNS,
    REGISTERED_SEEDS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    input_columns,
)


MODEL_VERSION = "closure_anfis_ablation_direct_multitask_v1"
MANIFEST_VERSION = "closure_anfis_ablation_model_manifest_v1"
MODEL_IDS = ("A0", "A1")
HORIZONS = (1, 2, 3)
HISTORY_LENGTH = 12
RAW_DIMENSION = 7
MASK_OFFSET = 7
MASK_DIMENSION = 7
HIDDEN_DIMENSION = 96
RECURRENT_LAYERS = 1
DROPOUT = 0.0
RESIDUAL_MODE = "training_horizon_priors"
LOCKED_DEVICE = "cpu"
BATCH_SIZE = 2_048
LEARNING_RATE = 0.001
WEIGHT_DECAY = 0.00001
GRADIENT_CLIP_NORM = 1.0
MAXIMUM_EPOCHS = 20
EARLY_STOPPING_PATIENCE = 5
EARLY_STOPPING_MINIMUM_DELTA = 0.0
LOGVAR_MIN = -10.0
LOGVAR_MAX = 2.0
PREPROCESSOR_EPSILON = 1e-12
PRIOR_EPSILON = 1e-6
INTERVAL_Z90 = 1.6448536269514722

EXPECTED_TRAINING_ORIGINS = 5_932
EXPECTED_SELECTION_ORIGINS = 658
EXPECTED_FIT_ORIGINS = EXPECTED_TRAINING_ORIGINS + EXPECTED_SELECTION_ORIGINS
EXPECTED_SEQUENCE_TRAINING_ORIGINS = 8_352
EXPECTED_SEQUENCE_SELECTION_ORIGINS = 1_061
EXPECTED_SEQUENCE_CALIBRATION_ORIGINS = 319
EXPECTED_TRAINING_TARGET_ROWS = EXPECTED_TRAINING_ORIGINS * len(HORIZONS)
EXPECTED_SELECTION_TARGET_ROWS = EXPECTED_SELECTION_ORIGINS * len(HORIZONS)
EXPECTED_CALIBRATION_TARGET_ROWS_READ = 0
EXPECTED_TRAINING_BLOOM_POSITIVES = (1_782, 1_802, 1_842)
EXPECTED_SELECTION_BLOOM_POSITIVES = (136, 136, 132)
EXPECTED_TRAINING_BLOOM_PRIORS = (
    0.3004045853000674,
    0.30377612946729604,
    0.3105192178017532,
)
EXPECTED_TRAINING_RISK_PRIORS = (
    0.5889835052483097,
    0.5918203351433461,
    0.5957344105135742,
)
EXPECTED_SELECTION_RISK_MEANS = (
    0.45999017515648927,
    0.4637243379090403,
    0.4593456887025464,
)

RAW_STANDARDIZATION_COLUMNS = tuple(A0_INPUT_COLUMNS[:RAW_DIMENSION])
RAW_MASK_COLUMNS = tuple(A0_INPUT_COLUMNS[MASK_OFFSET : MASK_OFFSET + MASK_DIMENSION])
EXPECTED_RAW_STANDARDIZATION = {
    "x_mean_TP_ugL": (80_271, 102.19372735397918, 249.83330218123442),
    "x_mean_TN_ugL": (32_025, 1419.5765952402869, 1225.5516584420247),
    "x_mean_DO_mgL": (99_243, 8.122428498098321, 2.5490422614540891),
    "x_mean_pH": (98_507, 7.6414948057072856, 0.74813434503824494),
    "x_mean_turbidity_NTU": (50_202, 10.181264076249539, 12.316825628634959),
    "x_mean_secchi_depth_m": (71_310, 1.005517772835204, 0.9782501366160937),
    "x_mean_temperature_C": (100_224, 20.878958889975785, 7.80482185246841),
}

TARGET_ARTIFACT = Path("data/targets/monthly_targets_model_v0.parquet")
TARGET_MANIFEST = Path("data/targets/target_manifest_v0.json")
TARGET_ARTIFACT_SHA256 = "c93ee8dbf424828c8dc11bc5da236d5c505e5f6ba7478eb689cca12a88c7e799"
TARGET_MANIFEST_SHA256 = "5c082cf12aa4f9c6350f4e44eb2b41c7f0dc52cb041c3a67c09cd8e286f17ca4"
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
AUTHORITY_RECORD_SPECS = (
    (
        "runtime",
        "anfis_ablation_training_runtime_contract",
        Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
    ),
    (
        "lock",
        "anfis_ablation_model_publication_adoption_patch_lock",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_model_publication_adoption_patch_lock.json"
        ),
    ),
    (
        "companion",
        "anfis_ablation_model_publication_adoption_patch_lock_manifest",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
        ),
    ),
)
TARGET_JOIN_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)
TARGET_PROJECTION = (*TARGET_JOIN_COLUMNS, "bloom_h", "target_risk_chla_h")
FIT_ROLES = ("training", "model_selection")
SUPERVISED_ORIGIN_COLUMNS = (
    "source_id",
    "site_id",
    "common_origin_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
)

PREDICTION_COLUMNS = (
    "surface_id",
    "model_id",
    "base_seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "observed_bloom",
    "observed_risk",
    "predicted_bloom_probability",
    "predicted_risk",
    "predicted_risk_sigma",
    "availability_status",
    "failure_reason",
    "score_semantics",
)
MODEL_OUTPUT_NAMES = (
    "model",
    "checkpoint",
    "preprocessor",
    "training_curve",
    "selection_predictions",
    "selection_metrics",
    "report",
)


class AnfisAblationTrainingError(RuntimeError):
    """Raised when the closed A0/A1 development-fit contract drifts."""


@dataclass(frozen=True)
class SlotPaths:
    model: Path
    checkpoint: Path
    preprocessor: Path
    training_curve: Path
    selection_predictions: Path
    selection_metrics: Path
    report: Path
    manifest: Path
    pointer: Path
    guard: Path

    @property
    def finals(self) -> tuple[Path, ...]:
        return (
            self.model,
            self.checkpoint,
            self.preprocessor,
            self.training_curve,
            self.selection_predictions,
            self.selection_metrics,
            self.report,
            self.manifest,
        )

    @property
    def temporaries(self) -> tuple[Path, ...]:
        return tuple(Path(f"{path}.tmp") for path in self.finals)


@dataclass(frozen=True)
class RawStandardizer:
    columns: tuple[str, ...]
    counts: np.ndarray
    means: np.ndarray
    standard_deviations: np.ndarray
    epsilon: float = PREPROCESSOR_EPSILON

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": "closure_mask_aware_training_standardization_v1",
            "fit_role": "training",
            "calculation_dtype": "float64",
            "serialization_dtype": "float32",
            "variance_ddof": 0,
            "epsilon": self.epsilon,
            "missing_transport_after_transform": 0.0,
            "columns": [
                {
                    "column": column,
                    "observed_count": int(self.counts[index]),
                    "mean": float(self.means[index]),
                    "standard_deviation": float(self.standard_deviations[index]),
                }
                for index, column in enumerate(self.columns)
            ],
        }


@dataclass(frozen=True)
class TrainingBundle:
    metadata: pd.DataFrame
    x: np.ndarray
    bloom: np.ndarray
    risk: np.ndarray

    def subset(self, role: str) -> "TrainingBundle":
        mask = self.metadata["time_role"].eq(role).to_numpy(dtype=bool)
        return TrainingBundle(
            metadata=self.metadata.loc[mask].reset_index(drop=True),
            x=self.x[mask],
            bloom=self.bloom[mask],
            risk=self.risk[mask],
        )


@dataclass(frozen=True)
class EarlyStoppingState:
    best_objective: float = math.inf
    best_epoch: int = 0
    epochs_without_improvement: int = 0
    should_stop: bool = False


@dataclass(frozen=True)
class FitResult:
    model: Any
    best_state_dict: dict[str, Any]
    best_epoch: int
    best_objective: float
    history: pd.DataFrame
    selection_predictions: pd.DataFrame
    selection_metrics: pd.DataFrame
    bloom_priors: np.ndarray
    risk_priors: np.ndarray


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


def validate_model_seed(model_id: str, base_seed: int) -> None:
    if model_id not in MODEL_IDS:
        raise AnfisAblationTrainingError(f"Unregistered model_id: {model_id!r}")
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise AnfisAblationTrainingError(f"Unregistered base_seed: {base_seed!r}")


def slot_paths(model_id: str, base_seed: int, *, repo_root: Path = PROJECT_ROOT) -> SlotPaths:
    validate_model_seed(model_id, base_seed)
    model_root = repo_root / f"models/closure_v1/anfis_ablation/{model_id}"
    report_root = repo_root / f"reports/closure_v1/02_models/{model_id}"
    return SlotPaths(
        model=model_root / f"seed_{base_seed}.pt",
        checkpoint=model_root / f"seed_{base_seed}.checkpoint.pt",
        preprocessor=report_root / f"seed_{base_seed}_preprocessor.json",
        training_curve=report_root / f"seed_{base_seed}_training_curve.csv",
        selection_predictions=repo_root
        / f"data/closure_v1/development/anfis_ablation/{model_id}/seed_{base_seed}_selection_predictions.parquet",
        selection_metrics=report_root / f"seed_{base_seed}_selection_metrics.csv",
        report=report_root / f"seed_{base_seed}_report.md",
        manifest=report_root / f"seed_{base_seed}_manifest.json",
        pointer=repo_root
        / f"data/closure_v1/development/anfis_ablation/{model_id}/seed_{base_seed}_selection_predictions.parquet.dvc",
        guard=repo_root / f"tmp/closure_v1_anfis_ablation_training/{model_id}_seed_{base_seed}.guard",
    )


def sequence_paths(model_id: str, base_seed: int, *, repo_root: Path = PROJECT_ROOT) -> tuple[Path, Path, Path, Path]:
    validate_model_seed(model_id, base_seed)
    if model_id == "A0":
        return (
            repo_root / "data/closure_v1/development/sequences/A0/raw_no_current.parquet",
            repo_root / "data/closure_v1/development/sequences/A0/raw_no_current.parquet.dvc",
            repo_root / "reports/closure_v1/01_surface/sequences/A0/raw_no_current_summary.csv",
            repo_root / "reports/closure_v1/01_surface/sequences/A0/raw_no_current_manifest.json",
        )
    return (
        repo_root / f"data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet",
        repo_root / f"data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet.dvc",
        repo_root / f"reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}_summary.csv",
        repo_root / f"reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}_manifest.json",
    )


def fit_mask_aware_standardizer(x_training: np.ndarray) -> RawStandardizer:
    if x_training.ndim != 3 or x_training.shape[1] != HISTORY_LENGTH or x_training.shape[2] < len(A0_INPUT_COLUMNS):
        raise AnfisAblationTrainingError("Training tensor shape cannot fit the raw preprocessor")
    values = x_training[:, :, :RAW_DIMENSION].astype(np.float64, copy=False)
    masks = x_training[:, :, MASK_OFFSET : MASK_OFFSET + MASK_DIMENSION].astype(np.float64, copy=False)
    if not np.isfinite(masks).all() or not np.isin(masks, (0.0, 1.0)).all():
        raise AnfisAblationTrainingError("Raw observed masks must be finite binary values")
    counts = np.empty(RAW_DIMENSION, dtype=np.int64)
    means = np.empty(RAW_DIMENSION, dtype=np.float64)
    stds = np.empty(RAW_DIMENSION, dtype=np.float64)
    for index in range(RAW_DIMENSION):
        observed = masks[:, :, index] == 1.0
        selected = values[:, :, index][observed]
        if selected.size == 0 or not np.isfinite(selected).all():
            raise AnfisAblationTrainingError("Every raw channel needs finite observed training values")
        counts[index] = selected.size
        means[index] = selected.mean(dtype=np.float64)
        stds[index] = selected.std(dtype=np.float64, ddof=0)
        if not math.isfinite(float(stds[index])) or float(stds[index]) <= PREPROCESSOR_EPSILON:
            raise AnfisAblationTrainingError("Raw training standard deviation is degenerate")
    return RawStandardizer(
        columns=RAW_STANDARDIZATION_COLUMNS,
        counts=counts,
        means=means,
        standard_deviations=stds,
    )


def validate_physical_standardizer(standardizer: RawStandardizer) -> None:
    if standardizer.columns != RAW_STANDARDIZATION_COLUMNS:
        raise AnfisAblationTrainingError("Raw standardizer column order drifted")
    for index, column in enumerate(standardizer.columns):
        expected_count, expected_mean, expected_std = EXPECTED_RAW_STANDARDIZATION[column]
        if int(standardizer.counts[index]) != expected_count:
            raise AnfisAblationTrainingError(f"Raw observed count drifted for {column}")
        if not math.isclose(float(standardizer.means[index]), expected_mean, rel_tol=0.0, abs_tol=1e-12):
            raise AnfisAblationTrainingError(f"Raw training mean drifted for {column}")
        if not math.isclose(float(standardizer.standard_deviations[index]), expected_std, rel_tol=0.0, abs_tol=1e-12):
            raise AnfisAblationTrainingError(f"Raw training std drifted for {column}")


def apply_mask_aware_standardizer(x: np.ndarray, standardizer: RawStandardizer) -> np.ndarray:
    if x.ndim != 3 or x.shape[1] != HISTORY_LENGTH or x.shape[2] not in {len(A0_INPUT_COLUMNS), len(A1_INPUT_COLUMNS)}:
        raise AnfisAblationTrainingError("A0/A1 tensor shape drifted before preprocessing")
    transformed = x.astype(np.float64, copy=True)
    masks = transformed[:, :, MASK_OFFSET : MASK_OFFSET + MASK_DIMENSION]
    if not np.isfinite(masks).all() or not np.isin(masks, (0.0, 1.0)).all():
        raise AnfisAblationTrainingError("Raw masks drifted before preprocessing")
    for index in range(RAW_DIMENSION):
        observed = masks[:, :, index] == 1.0
        raw = transformed[:, :, index]
        if not np.isfinite(raw[observed]).all():
            raise AnfisAblationTrainingError("Observed raw inputs contain nonfinite values")
        raw[observed] = (raw[observed] - standardizer.means[index]) / max(
            float(standardizer.standard_deviations[index]), standardizer.epsilon
        )
        raw[~observed] = 0.0
    if not np.isfinite(transformed).all():
        raise AnfisAblationTrainingError("Preprocessed tensor contains nonfinite values")
    return transformed.astype(np.float32)


def training_priors(bundle: TrainingBundle) -> tuple[np.ndarray, np.ndarray]:
    training = bundle.subset("training")
    if training.bloom.shape != (len(training.metadata), len(HORIZONS)) or training.risk.shape != training.bloom.shape:
        raise AnfisAblationTrainingError("Direct target tensor shape drifted")
    bloom = training.bloom.astype(np.float64)
    risk = training.risk.astype(np.float64)
    if not np.isin(bloom, (0.0, 1.0)).all() or not np.isfinite(risk).all():
        raise AnfisAblationTrainingError("Direct training targets are invalid")
    if bool(((risk < 0.0) | (risk > 1.0)).any()):
        raise AnfisAblationTrainingError("Direct risk targets leave [0, 1]")
    return bloom.mean(axis=0), risk.mean(axis=0)


def validate_physical_priors(bloom_priors: np.ndarray, risk_priors: np.ndarray) -> None:
    if bloom_priors.shape != (3,) or risk_priors.shape != (3,):
        raise AnfisAblationTrainingError("Training priors must retain three horizons")
    if not np.allclose(bloom_priors, EXPECTED_TRAINING_BLOOM_PRIORS, rtol=0.0, atol=1e-15):
        raise AnfisAblationTrainingError("Training bloom priors drifted")
    if not np.allclose(risk_priors, EXPECTED_TRAINING_RISK_PRIORS, rtol=0.0, atol=1e-15):
        raise AnfisAblationTrainingError("Training risk priors drifted")


def _logit(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values.astype(np.float64), PRIOR_EPSILON, 1.0 - PRIOR_EPSILON)
    return np.log(clipped / (1.0 - clipped))


def _require_torch() -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - repository dependency
        raise AnfisAblationTrainingError("Torch is required for A0/A1 fitting") from exc
    return torch


def make_anfis_ablation_model(
    *, input_dimension: int, bloom_priors: np.ndarray, risk_priors: np.ndarray
) -> Any:
    if input_dimension not in {len(A0_INPUT_COLUMNS), len(A1_INPUT_COLUMNS)}:
        raise AnfisAblationTrainingError("A0/A1 model input dimension drifted")
    if bloom_priors.shape != (3,) or risk_priors.shape != (3,):
        raise AnfisAblationTrainingError("A0/A1 model priors must have three horizons")
    torch = _require_torch()
    bloom_logits = torch.tensor(_logit(bloom_priors), dtype=torch.float32)
    risk_logits = torch.tensor(_logit(risk_priors), dtype=torch.float32)

    class DirectPriorResidualGRU(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gru = torch.nn.GRU(
                input_size=input_dimension,
                hidden_size=HIDDEN_DIMENSION,
                num_layers=RECURRENT_LAYERS,
                batch_first=True,
                dropout=0.0,
            )
            self.bloom_delta = torch.nn.Linear(HIDDEN_DIMENSION, len(HORIZONS))
            self.risk_delta = torch.nn.Linear(HIDDEN_DIMENSION, len(HORIZONS))
            self.risk_logvar = torch.nn.Linear(HIDDEN_DIMENSION, len(HORIZONS))
            self.register_buffer("bloom_prior_logits", bloom_logits.clone())
            self.register_buffer("risk_prior_logits", risk_logits.clone())

        def forward(self, x: Any) -> tuple[Any, Any, Any]:
            _, hidden = self.gru(x)
            last = hidden[-1]
            bloom = self.bloom_prior_logits + self.bloom_delta(last)
            risk_mu = torch.sigmoid(self.risk_prior_logits + self.risk_delta(last))
            logvar = torch.clamp(self.risk_logvar(last), min=LOGVAR_MIN, max=LOGVAR_MAX)
            return bloom, risk_mu, logvar

    return DirectPriorResidualGRU()


def direct_multitask_loss(
    bloom_logits: Any,
    risk_mu: Any,
    risk_logvar: Any,
    bloom_target: Any,
    risk_target: Any,
) -> Any:
    torch = _require_torch()
    if bloom_logits.shape != bloom_target.shape or risk_mu.shape != risk_target.shape or risk_logvar.shape != risk_target.shape:
        raise AnfisAblationTrainingError("Direct head/target shapes differ")
    bce = torch.nn.functional.binary_cross_entropy_with_logits(
        bloom_logits, bloom_target, reduction="mean"
    )
    clipped_logvar = torch.clamp(risk_logvar, min=LOGVAR_MIN, max=LOGVAR_MAX)
    squared = (risk_target - risk_mu) ** 2
    gaussian_nll = 0.5 * (clipped_logvar + squared / torch.exp(clipped_logvar))
    return bce + gaussian_nll.mean() + squared.mean()


def configure_deterministic_cpu(base_seed: int) -> Any:
    validate_model_seed("A0", base_seed)
    random.seed(base_seed)
    np.random.seed(base_seed)
    torch = _require_torch()
    torch.manual_seed(base_seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError as exc:
            raise AnfisAblationTrainingError(
                "Torch interop threads were initialized before the CPU contract"
            ) from exc
    return torch.device("cpu")


def canonical_epoch_batches(
    metadata: pd.DataFrame, *, base_seed: int, epoch: int, batch_size: int = BATCH_SIZE
) -> tuple[list[np.ndarray], str]:
    if type(epoch) is not int or not 1 <= epoch <= MAXIMUM_EPOCHS:
        raise AnfisAblationTrainingError("Epoch must be in [1, 20]")
    if type(batch_size) is not int or batch_size < 1:
        raise AnfisAblationTrainingError("Batch size must be positive")
    required = ["source_id", "site_id", "origin_year_month", "common_origin_id"]
    if any(column not in metadata.columns for column in required) or metadata[required].isna().any().any():
        raise AnfisAblationTrainingError("Canonical training identity drifted")
    keys = metadata[required].astype(str).values.tolist()
    torch = _require_torch()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(base_seed + epoch)
    order = torch.randperm(len(keys), generator=generator).numpy().astype(np.int64)
    batches = [order[start : start + batch_size] for start in range(0, len(order), batch_size)]
    digest = hashlib.sha256()
    for number, indices in enumerate(batches, start=1):
        record = [epoch, number, [keys[int(index)] for index in indices]]
        digest.update(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
    return batches, digest.hexdigest()


def advance_early_stopping(state: EarlyStoppingState, *, epoch: int, objective: float) -> EarlyStoppingState:
    if not math.isfinite(objective):
        raise AnfisAblationTrainingError("Selection objective must be finite")
    if objective < state.best_objective - EARLY_STOPPING_MINIMUM_DELTA:
        return EarlyStoppingState(float(objective), epoch, 0, False)
    stale = state.epochs_without_improvement + 1
    return EarlyStoppingState(
        state.best_objective,
        state.best_epoch,
        stale,
        stale >= EARLY_STOPPING_PATIENCE,
    )


def prediction_arrow_schema() -> pa.Schema:
    fields: list[pa.Field] = []
    for name in PREDICTION_COLUMNS:
        if name in {
            "surface_id",
            "model_id",
            "source_id",
            "site_id",
            "common_origin_id",
            "time_role",
            "origin_year_month",
            "target_year_month",
            "availability_status",
            "failure_reason",
            "score_semantics",
        }:
            fields.append(pa.field(name, pa.string(), nullable=False))
        elif name == "base_seed":
            fields.append(pa.field(name, pa.int64(), nullable=False))
        elif name == "horizon_months":
            fields.append(pa.field(name, pa.int16(), nullable=False))
        elif name == "observed_bloom":
            fields.append(pa.field(name, pa.int8(), nullable=False))
        else:
            fields.append(pa.field(name, pa.float64(), nullable=False))
    return pa.schema(fields)


def canonical_prediction_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.columns.tolist() != list(PREDICTION_COLUMNS):
        raise AnfisAblationTrainingError("Selection prediction columns/order drifted")
    if frame.empty:
        raise AnfisAblationTrainingError("Selection prediction table cannot be empty")
    model_ids = set(frame["model_id"].astype(str))
    if len(model_ids) != 1 or not model_ids.issubset(MODEL_IDS):
        raise AnfisAblationTrainingError("Selection prediction table must contain one model")
    model_id = next(iter(model_ids))
    if not frame["surface_id"].eq(SURFACE_ID).all() or not frame["source_id"].eq(
        "wqp"
    ).all():
        raise AnfisAblationTrainingError("Selection surface/source identity drifted")
    seeds = set(pd.to_numeric(frame["base_seed"], errors="raise").astype(int))
    if len(seeds) != 1:
        raise AnfisAblationTrainingError("Selection prediction table must contain one seed")
    validate_model_seed(model_id, next(iter(seeds)))
    nullable = frame.columns[frame.isna().any()].tolist()
    if nullable:
        raise AnfisAblationTrainingError("Selection predictions contain unexpected nulls")
    if set(frame["time_role"].astype(str)) != {"model_selection"}:
        raise AnfisAblationTrainingError("Selection prediction table contains another role")
    if not frame["availability_status"].eq("success").all() or not frame[
        "failure_reason"
    ].eq("").all():
        raise AnfisAblationTrainingError("Complete selection rows must be successful")
    if not frame["score_semantics"].eq(
        "direct_bloom_probability_and_risk_distribution"
    ).all():
        raise AnfisAblationTrainingError("Selection score semantics drifted")
    if set(pd.to_numeric(frame["horizon_months"], errors="raise").astype(int)) != set(HORIZONS):
        raise AnfisAblationTrainingError("Selection prediction horizons drifted")
    for origin_value, target_value, horizon_value in frame[
        ["origin_year_month", "target_year_month", "horizon_months"]
    ].itertuples(index=False, name=None):
        try:
            origin = cast(Any, pd.Period(str(origin_value), freq="M"))
            target = cast(Any, pd.Period(str(target_value), freq="M"))
        except (TypeError, ValueError) as exc:
            raise AnfisAblationTrainingError("Selection month identity is malformed") from exc
        if str(origin + int(horizon_value)) != str(target):
            raise AnfisAblationTrainingError("Selection target month does not match horizon")
        if str(origin) > "2020-12" or str(target) > "2020-12":
            raise AnfisAblationTrainingError("Selection prediction crosses the 2020 cutoff")
    numeric_names = (
        "observed_bloom",
        "observed_risk",
        "predicted_bloom_probability",
        "predicted_risk",
        "predicted_risk_sigma",
    )
    numeric = frame[list(numeric_names)].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=np.float64)).all():
        raise AnfisAblationTrainingError("Selection predictions contain nonfinite values")
    bounded = (
        "observed_bloom",
        "observed_risk",
        "predicted_bloom_probability",
        "predicted_risk",
    )
    if any(bool(((numeric[name] < 0.0) | (numeric[name] > 1.0)).any()) for name in bounded):
        raise AnfisAblationTrainingError("Selection targets/predictions leave [0, 1]")
    sigma_min = math.exp(LOGVAR_MIN / 2.0)
    sigma_max = math.exp(LOGVAR_MAX / 2.0)
    if bool(
        (
            (numeric["predicted_risk_sigma"] < sigma_min)
            | (numeric["predicted_risk_sigma"] > sigma_max)
        ).any()
    ):
        raise AnfisAblationTrainingError(
            "Predicted risk sigma leaves the sealed log-variance clamp"
        )
    ordered = frame.sort_values(
        [
            "source_id",
            "site_id",
            "origin_year_month",
            "horizon_months",
            "target_year_month",
            "common_origin_id",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    if ordered.duplicated(["source_id", "site_id", "origin_year_month", "horizon_months"]).any():
        raise AnfisAblationTrainingError("Selection prediction identity is duplicated")
    return ordered


def prediction_arrow_table(frame: pd.DataFrame) -> pa.Table:
    canonical = canonical_prediction_frame(frame)
    arrays = [pa.array(canonical[field.name].tolist(), type=field.type) for field in prediction_arrow_schema()]
    return pa.Table.from_arrays(arrays, schema=prediction_arrow_schema())


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        raise AnfisAblationTrainingError(f"Path escapes repository: {path}") from exc


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
        raise AnfisAblationTrainingError(f"Path escapes repository: {path}") from exc
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in relative_parent.parts:
            try:
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise AnfisAblationTrainingError(f"Missing parent: {lexical.parent}")
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                except FileExistsError:
                    pass
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(named.st_mode):
                raise AnfisAblationTrainingError(f"Non-directory ancestor: {lexical.parent}")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                os.close(child)
                raise AnfisAblationTrainingError("Repository ancestor identity drifted")
            previous = descriptor
            descriptor = child
            os.close(previous)
        lexical_parent = lexical.parent.lstat()
        opened_parent = os.fstat(descriptor)
        if not stat.S_ISDIR(lexical_parent.st_mode) or (
            lexical_parent.st_dev,
            lexical_parent.st_ino,
        ) != (opened_parent.st_dev, opened_parent.st_ino):
            raise AnfisAblationTrainingError("Repository parent identity drifted")
        return descriptor, lexical
    except BaseException:
        os.close(descriptor)
        raise


def _unlink_name_if_owned(
    directory_descriptor: int, name: str, *, device: int, inode: int
) -> bool:
    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISREG(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == (
        device,
        inode,
    ):
        os.unlink(name, dir_fd=directory_descriptor)
        return True
    return False


def _stable_file_fingerprint(path: Path, *, repo_root: Path) -> dict[str, Any]:
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
            raise AnfisAblationTrainingError(f"Input is not a stable regular file: {path}")
        state = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_mode,
            opened_before.st_nlink,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
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
            opened_after.st_mode,
            opened_after.st_nlink,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_nlink,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if state != after_open or state != after_name or size != opened_after.st_size:
            raise AnfisAblationTrainingError(f"Input changed while hashing: {path}")
        return {
            "path": _repo_relative(lexical, repo_root),
            "bytes": size,
            "sha256": digest.hexdigest(),
            "mode": stat.S_IMODE(opened_after.st_mode),
            "device": int(opened_after.st_dev),
            "inode": int(opened_after.st_ino),
            "nlink": int(opened_after.st_nlink),
            "mtime_ns": int(opened_after.st_mtime_ns),
            "ctime_ns": int(opened_after.st_ctime_ns),
        }
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def _stable_file_record(path: Path, *, repo_root: Path) -> dict[str, Any]:
    fingerprint = _stable_file_fingerprint(path, repo_root=repo_root)
    return {
        key: fingerprint[key]
        for key in ("path", "bytes", "sha256")
    }


@contextmanager
def _stable_input_descriptor(path: Path, *, repo_root: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    before = _stable_file_record(path, repo_root=repo_root)
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
            raise AnfisAblationTrainingError(f"Input identity drifted before read: {path}")
        yield descriptor, before
        after = _stable_file_record(path, repo_root=repo_root)
        if after != before:
            raise AnfisAblationTrainingError(f"Input changed during read: {path}")
        final_open = os.fstat(descriptor)
        if (final_open.st_dev, final_open.st_ino) != (opened.st_dev, opened.st_ino):
            raise AnfisAblationTrainingError(f"Opened input identity drifted: {path}")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def _read_parquet_projection(
    path: Path, *, columns: Sequence[str], repo_root: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    with _stable_input_descriptor(path, repo_root=repo_root) as (descriptor, record):
        duplicate = os.dup(descriptor)
        with os.fdopen(duplicate, "rb") as handle:
            table = pq.read_table(handle, columns=list(columns))
        return table.to_pandas(), record


def _read_target_projection(
    path: Path, *, development_site_ids: Sequence[str], repo_root: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not development_site_ids:
        raise AnfisAblationTrainingError("Target scanner requires development sites")
    with _stable_input_descriptor(path, repo_root=repo_root) as (descriptor, record):
        descriptor_path = Path(f"/proc/self/fd/{descriptor}")
        if not descriptor_path.exists():
            raise AnfisAblationTrainingError("Pinned descriptor projection is unavailable")
        dataset = ds.dataset(descriptor_path.as_posix(), format="parquet")
        predicate = (
            (ds.field("source_id") == "wqp")
            & ds.field("site_id").isin(list(development_site_ids))
            & (ds.field("origin_year_month") <= "2020-12")
            & (ds.field("target_year_month") <= "2020-12")
        )
        frame = dataset.scanner(columns=list(TARGET_PROJECTION), filter=predicate).to_table().to_pandas()
    if frame.empty:
        raise AnfisAblationTrainingError("No development targets passed the <=2020 predicate")
    if (frame["origin_year_month"].astype(str) > "2020-12").any() or (
        frame["target_year_month"].astype(str) > "2020-12"
    ).any():
        raise AnfisAblationTrainingError("Target projection materialized a row after 2020-12")
    if frame.duplicated(list(TARGET_JOIN_COLUMNS)).any():
        raise AnfisAblationTrainingError("Target projection contains duplicate exact keys")
    return frame, record


def _sequence_frame(
    *, model_id: str, base_seed: int, repo_root: Path
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[Path]]:
    sequence, pointer, summary, manifest = sequence_paths(
        model_id, base_seed, repo_root=repo_root
    )
    columns = [*SEQUENCE_IDENTITY_COLUMNS, *input_columns(model_id)]
    frame, sequence_record = _read_parquet_projection(
        sequence, columns=columns, repo_root=repo_root
    )
    prefix = model_id.lower()
    records = [
        {"role": f"{prefix}_sequence", **sequence_record},
        {
            "role": f"{prefix}_sequence_pointer",
            **_stable_file_record(pointer, repo_root=repo_root),
        },
        {
            "role": f"{prefix}_sequence_summary",
            **_stable_file_record(summary, repo_root=repo_root),
        },
        {
            "role": f"{prefix}_sequence_manifest",
            **_stable_file_record(manifest, repo_root=repo_root),
        },
    ]
    if len(frame) != 9_732 or frame["common_origin_id"].nunique() != 9_732:
        raise AnfisAblationTrainingError("Input sequence denominator drifted")
    if set(frame["sequence_status"].astype(str)) != {"success"} or not frame[
        "failure_reason"
    ].eq("").all():
        raise AnfisAblationTrainingError("Input sequence is not fully available")
    if set(frame["model_id"].astype(str)) != {model_id} or set(
        frame["sequence_version"].astype(str)
    ) != {SEQUENCE_VERSION}:
        raise AnfisAblationTrainingError("Input sequence identity drifted")
    if model_id == "A0":
        if frame["base_seed"].notna().any() or frame["upstream_state_seed"].notna().any():
            raise AnfisAblationTrainingError("A0 input sequence cannot carry seeds")
    elif not (
        frame["base_seed"].eq(base_seed).all()
        and frame["upstream_state_seed"].eq(base_seed).all()
    ):
        raise AnfisAblationTrainingError("A1 input sequence seed binding drifted")
    if set(frame["assignment_role"].astype(str)) != {"development"} or set(
        frame["source_id"].astype(str)
    ) != {"wqp"}:
        raise AnfisAblationTrainingError("Input sequence crosses the development boundary")
    expected_roles = {
        "training": EXPECTED_SEQUENCE_TRAINING_ORIGINS,
        "model_selection": EXPECTED_SEQUENCE_SELECTION_ORIGINS,
        "calibration_threshold": EXPECTED_SEQUENCE_CALIBRATION_ORIGINS,
    }
    if frame["time_role"].value_counts().to_dict() != expected_roles:
        raise AnfisAblationTrainingError("Input sequence role counts drifted")
    if frame.duplicated(["source_id", "site_id", "origin_year_month"]).any():
        raise AnfisAblationTrainingError("Input sequence keys are duplicated")
    ordered = frame.sort_values(
        ["source_id", "site_id", "origin_year_month", "common_origin_id"], kind="mergesort"
    ).reset_index(drop=True)
    if not frame.reset_index(drop=True).equals(ordered):
        raise AnfisAblationTrainingError("Input sequence canonical order drifted")
    return frame, records, [sequence, pointer, summary, manifest]


def _tensor_from_sequence(frame: pd.DataFrame, *, model_id: str) -> np.ndarray:
    columns = input_columns(model_id)
    tensor = np.empty((len(frame), HISTORY_LENGTH, len(columns)), dtype=np.float32)
    for channel_index, column in enumerate(columns):
        values: list[np.ndarray] = []
        for value in frame[column].tolist():
            array = np.asarray(value, dtype=np.float32)
            if array.shape != (HISTORY_LENGTH,) or not np.isfinite(array).all():
                raise AnfisAblationTrainingError(f"Input tensor channel drifted: {column}")
            values.append(array)
        tensor[:, :, channel_index] = np.stack(values, axis=0)
    masks = tensor[:, :, MASK_OFFSET : MASK_OFFSET + MASK_DIMENSION]
    if not np.isin(masks, (0.0, 1.0)).all():
        raise AnfisAblationTrainingError("Input tensor masks are not binary")
    return tensor


def validate_fit_role_months(frame: pd.DataFrame) -> None:
    required = {"time_role", "origin_year_month", "target_year_month"}
    if not required.issubset(frame.columns):
        raise AnfisAblationTrainingError("Development role-month columns are incomplete")
    training_rows = frame["time_role"].eq("training")
    selection_rows = frame["time_role"].eq("model_selection")
    if (
        not frame.loc[training_rows, "origin_year_month"]
        .astype(str)
        .le("2018-12")
        .all()
        or not frame.loc[training_rows, "target_year_month"]
        .astype(str)
        .le("2018-12")
        .all()
        or not frame.loc[selection_rows, "origin_year_month"]
        .astype(str)
        .between("2019-01", "2020-12")
        .all()
        or not frame.loc[selection_rows, "target_year_month"]
        .astype(str)
        .between("2019-01", "2020-12")
        .all()
    ):
        raise AnfisAblationTrainingError(
            "Development origin/target months do not share the sealed time role"
        )


def collapse_supervised_origins(frame: pd.DataFrame) -> pd.DataFrame:
    """Collapse the three horizon rows to one supervised row per origin.

    ``evaluation_unit_id`` is deliberately excluded: it identifies a
    horizon-specific evaluation row, not a model input origin.  Including it
    would repeat every input tensor and target vector three times.
    """

    required = (
        *SUPERVISED_ORIGIN_COLUMNS,
        "evaluation_unit_id",
        "target_year_month",
        "horizon_months",
    )
    if not set(required).issubset(frame.columns) or frame.loc[:, list(required)].isna().any().any():
        raise AnfisAblationTrainingError("Supervised origin identity is incomplete")
    grouped = frame.groupby("common_origin_id", sort=False)
    if (
        not grouped.size().eq(len(HORIZONS)).all()
        or not grouped["horizon_months"].nunique().eq(len(HORIZONS)).all()
        or set(pd.to_numeric(frame["horizon_months"], errors="coerce").astype(int))
        != set(HORIZONS)
    ):
        raise AnfisAblationTrainingError(
            "Every supervised origin must retain exactly three horizon rows"
        )
    stable_columns = tuple(
        column for column in SUPERVISED_ORIGIN_COLUMNS if column != "common_origin_id"
    )
    if any(not grouped[column].nunique(dropna=False).eq(1).all() for column in stable_columns):
        raise AnfisAblationTrainingError(
            "Supervised origin identity changes across horizons"
        )
    origins = (
        frame.loc[:, list(SUPERVISED_ORIGIN_COLUMNS)]
        .drop_duplicates()
        .sort_values(
            ["source_id", "site_id", "origin_year_month", "common_origin_id"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    if not origins["common_origin_id"].is_unique or len(origins) * len(HORIZONS) != len(frame):
        raise AnfisAblationTrainingError(
            "Supervised rows did not collapse to one row per origin"
        )
    return origins


def fit_sequence_training_standardizer(
    sequence: pd.DataFrame, *, model_id: str
) -> RawStandardizer:
    """Fit input-only raw statistics on every row in the training role."""

    if "time_role" not in sequence.columns or "common_origin_id" not in sequence.columns:
        raise AnfisAblationTrainingError("Sequence training identity is incomplete")
    training = sequence.loc[sequence["time_role"].eq("training")].reset_index(drop=True)
    if training.empty or not training["common_origin_id"].is_unique:
        raise AnfisAblationTrainingError("Sequence training origins are empty or duplicated")
    return fit_mask_aware_standardizer(_tensor_from_sequence(training, model_id=model_id))


def supervised_target_matrices(
    frame: pd.DataFrame, origins: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Materialize the three direct target heads for each unique origin."""

    target_index = frame.set_index(["common_origin_id", "horizon_months"])
    if not target_index.index.is_unique:
        raise AnfisAblationTrainingError("Complete target origin/horizon index is duplicated")
    origin_ids = origins["common_origin_id"].astype(str).tolist()
    bloom = np.asarray(
        [
            [float(target_index.loc[(origin, horizon), "bloom_h"]) for horizon in HORIZONS]
            for origin in origin_ids
        ],
        dtype=np.float64,
    )
    risk = np.asarray(
        [
            [
                float(target_index.loc[(origin, horizon), "target_risk_chla_h"])
                for horizon in HORIZONS
            ]
            for origin in origin_ids
        ],
        dtype=np.float64,
    )
    expected_shape = (len(origins), len(HORIZONS))
    if bloom.shape != expected_shape or risk.shape != expected_shape:
        raise AnfisAblationTrainingError("Direct target matrix shape drifted")
    return bloom, risk


def load_training_bundle(
    *, model_id: str, base_seed: int, repo_root: Path = PROJECT_ROOT
) -> tuple[TrainingBundle, RawStandardizer, list[dict[str, Any]], list[Path]]:
    """Load only fit/selection targets through 2020 and bind them to one input slot."""

    validate_model_seed(model_id, base_seed)
    sequence, records, paths = _sequence_frame(
        model_id=model_id, base_seed=base_seed, repo_root=repo_root
    )
    common_path = repo_root / "data/closure_v1/common_origin_manifest.parquet"
    common_pointer = repo_root / "data/closure_v1/common_origin_manifest.parquet.dvc"
    common_manifest = repo_root / "reports/closure_v1/01_surface/common_origin_manifest.json"
    common_columns = [
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
        "complete_targets_evaluable",
    ]
    common, common_record = _read_parquet_projection(
        common_path, columns=common_columns, repo_root=repo_root
    )
    fit_common = common.loc[
        common["time_role"].isin(FIT_ROLES)
        & common["complete_targets_evaluable"].eq(True)
        & common["origin_year_month"].astype(str).le("2020-12")
        & common["target_year_month"].astype(str).le("2020-12")
    ].copy()
    validate_fit_role_months(fit_common)
    if set(fit_common["assignment_role"].astype(str)) != {"development"}:
        raise AnfisAblationTrainingError("Complete target identity contains a holdout row")
    observed_counts = (
        fit_common.groupby("time_role", sort=False)["common_origin_id"].nunique().to_dict()
    )
    if observed_counts != {
        "training": EXPECTED_TRAINING_ORIGINS,
        "model_selection": EXPECTED_SELECTION_ORIGINS,
    }:
        raise AnfisAblationTrainingError("Complete target origin counts drifted")
    if len(fit_common) != EXPECTED_TRAINING_TARGET_ROWS + EXPECTED_SELECTION_TARGET_ROWS:
        raise AnfisAblationTrainingError("Complete target row count drifted")
    if fit_common.duplicated(list(TARGET_JOIN_COLUMNS)).any():
        raise AnfisAblationTrainingError("Complete target join keys are duplicated")
    targets_path = repo_root / TARGET_ARTIFACT
    targets, target_record = _read_target_projection(
        targets_path,
        development_site_ids=sorted(set(fit_common["site_id"].astype(str))),
        repo_root=repo_root,
    )
    joined = fit_common.merge(
        targets,
        on=list(TARGET_JOIN_COLUMNS),
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if joined[["bloom_h", "target_risk_chla_h"]].isna().any().any():
        raise AnfisAblationTrainingError("A complete development target is unavailable")
    bloom = pd.to_numeric(joined["bloom_h"], errors="coerce")
    risk = pd.to_numeric(joined["target_risk_chla_h"], errors="coerce")
    if not np.isin(bloom.to_numpy(dtype=np.float64), (0.0, 1.0)).all() or not np.isfinite(
        risk.to_numpy(dtype=np.float64)
    ).all() or bool(((risk < 0.0) | (risk > 1.0)).any()):
        raise AnfisAblationTrainingError("Development target values drifted")
    positives = (
        joined.groupby(["time_role", "horizon_months"], sort=False)["bloom_h"].sum().to_dict()
    )
    expected_positives = {
        **{("training", horizon): count for horizon, count in zip(HORIZONS, EXPECTED_TRAINING_BLOOM_POSITIVES, strict=True)},
        **{("model_selection", horizon): count for horizon, count in zip(HORIZONS, EXPECTED_SELECTION_BLOOM_POSITIVES, strict=True)},
    }
    if positives != expected_positives:
        raise AnfisAblationTrainingError("Development bloom-positive counts drifted")
    origins = collapse_supervised_origins(joined)
    origin_counts = origins["time_role"].value_counts().to_dict()
    if origin_counts != {
        "training": EXPECTED_TRAINING_ORIGINS,
        "model_selection": EXPECTED_SELECTION_ORIGINS,
    } or len(origins) != EXPECTED_FIT_ORIGINS:
        raise AnfisAblationTrainingError("Supervised origin denominator drifted")
    sequence_index = sequence.set_index("common_origin_id")
    if not sequence_index.index.is_unique:
        raise AnfisAblationTrainingError("Input sequence origin index is duplicated")
    missing_sequence = sorted(set(origins["common_origin_id"]) - set(sequence_index.index))
    if missing_sequence:
        raise AnfisAblationTrainingError("Complete target origins are missing input sequences")
    selected_sequence = sequence_index.loc[origins["common_origin_id"].tolist()].reset_index()
    for column in ("source_id", "site_id", "time_role", "origin_year_month"):
        if selected_sequence[column].astype(str).tolist() != origins[column].astype(str).tolist():
            raise AnfisAblationTrainingError("Sequence/target origin identity drifted")
    bloom_matrix, risk_matrix = supervised_target_matrices(joined, origins)
    tensor = _tensor_from_sequence(selected_sequence, model_id=model_id)
    unprocessed = TrainingBundle(origins, tensor, bloom_matrix, risk_matrix)
    standardizer = fit_sequence_training_standardizer(sequence, model_id=model_id)
    validate_physical_standardizer(standardizer)
    processed = TrainingBundle(
        origins,
        apply_mask_aware_standardizer(tensor, standardizer),
        bloom_matrix,
        risk_matrix,
    )
    bloom_priors, risk_priors = training_priors(processed)
    validate_physical_priors(bloom_priors, risk_priors)
    target_pointer = repo_root / "data/targets.dvc"
    target_manifest = repo_root / TARGET_MANIFEST
    records.extend(
        [
            {"role": "common_origin", **common_record},
            {
                "role": "common_origin_pointer",
                **_stable_file_record(common_pointer, repo_root=repo_root),
            },
            {
                "role": "common_origin_manifest",
                **_stable_file_record(common_manifest, repo_root=repo_root),
            },
            {"role": "development_targets", **target_record},
            {
                "role": "targets_pointer",
                **_stable_file_record(target_pointer, repo_root=repo_root),
            },
            {
                "role": "target_manifest",
                **_stable_file_record(target_manifest, repo_root=repo_root),
            },
        ]
    )
    paths.extend(
        [common_path, common_pointer, common_manifest, targets_path, target_pointer, target_manifest]
    )
    return processed, standardizer, records, paths


def _predict_arrays(model: Any, bundle: TrainingBundle, *, device: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    torch = _require_torch()
    model.eval()
    bloom_parts: list[np.ndarray] = []
    risk_parts: list[np.ndarray] = []
    logvar_parts: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(bundle.metadata), BATCH_SIZE):
            stop = min(start + BATCH_SIZE, len(bundle.metadata))
            x = torch.from_numpy(bundle.x[start:stop]).to(device=device, dtype=torch.float32)
            bloom_logits, risk_mu, risk_logvar = model(x)
            bloom_parts.append(torch.sigmoid(bloom_logits).cpu().numpy().astype(np.float64))
            risk_parts.append(risk_mu.cpu().numpy().astype(np.float64))
            logvar_parts.append(risk_logvar.cpu().numpy().astype(np.float64))
    if not bloom_parts:
        raise AnfisAblationTrainingError("Prediction bundle cannot be empty")
    return (
        np.concatenate(bloom_parts, axis=0),
        np.concatenate(risk_parts, axis=0),
        np.concatenate(logvar_parts, axis=0),
    )


def _selection_metrics(
    bundle: TrainingBundle,
    *,
    model_id: str,
    base_seed: int,
    bloom_probability: np.ndarray,
    risk_mu: np.ndarray,
    risk_logvar: np.ndarray,
    bloom_priors: np.ndarray,
    risk_priors: np.ndarray,
) -> tuple[pd.DataFrame, float]:
    if len(bundle.metadata) != EXPECTED_SELECTION_ORIGINS:
        raise AnfisAblationTrainingError("Selection origin denominator drifted")
    expected_shape = (len(bundle.metadata), len(HORIZONS))
    if any(array.shape != expected_shape for array in (bloom_probability, risk_mu, risk_logvar)):
        raise AnfisAblationTrainingError("Selection prediction array shape drifted")
    rows: list[dict[str, Any]] = []
    ratios: list[float] = []
    for index, horizon in enumerate(HORIZONS):
        bloom_target = bundle.bloom[:, index].astype(np.float64)
        risk_target = bundle.risk[:, index].astype(np.float64)
        bloom_pred = bloom_probability[:, index]
        risk_pred = risk_mu[:, index]
        logvar = np.clip(risk_logvar[:, index], LOGVAR_MIN, LOGVAR_MAX)
        if not np.isfinite(bloom_pred).all() or not np.isfinite(risk_pred).all() or not np.isfinite(logvar).all():
            raise AnfisAblationTrainingError("Selection predictions contain nonfinite values")
        if bool(((bloom_pred < 0.0) | (bloom_pred > 1.0)).any()) or bool(
            ((risk_pred < 0.0) | (risk_pred > 1.0)).any()
        ):
            raise AnfisAblationTrainingError("Selection predictions leave [0, 1]")
        brier = float(np.mean((bloom_pred - bloom_target) ** 2))
        risk_error = risk_pred - risk_target
        rmse = float(np.sqrt(np.mean(risk_error**2)))
        mae = float(np.mean(np.abs(risk_error)))
        prior_brier = float(np.mean((float(bloom_priors[index]) - bloom_target) ** 2))
        prior_risk_error = float(risk_priors[index]) - risk_target
        prior_rmse = float(np.sqrt(np.mean(prior_risk_error**2)))
        prior_mae = float(np.mean(np.abs(prior_risk_error)))
        component_ratios = (
            brier / max(prior_brier, PREPROCESSOR_EPSILON),
            rmse / max(prior_rmse, PREPROCESSOR_EPSILON),
            mae / max(prior_mae, PREPROCESSOR_EPSILON),
        )
        ratios.extend(component_ratios)
        rows.append(
            {
                "model_id": model_id,
                "base_seed": base_seed,
                "horizon_months": horizon,
                "time_role": "model_selection",
                "rows": len(bundle.metadata),
                "bloom_positive": int(bloom_target.sum()),
                "brier": brier,
                "pr_auc": float(average_precision_score(bloom_target, bloom_pred)),
                "rmse": rmse,
                "mae": mae,
                "prior_brier": prior_brier,
                "prior_rmse": prior_rmse,
                "prior_mae": prior_mae,
                "brier_ratio": component_ratios[0],
                "rmse_ratio": component_ratios[1],
                "mae_ratio": component_ratios[2],
            }
        )
    objective = float(np.mean(ratios))
    if not math.isfinite(objective):
        raise AnfisAblationTrainingError("Selection checkpoint objective is nonfinite")
    metrics = pd.DataFrame(rows).sort_values("horizon_months", kind="mergesort").reset_index(drop=True)
    metrics["checkpoint_objective"] = objective
    expected_columns = [
        "model_id",
        "base_seed",
        "horizon_months",
        "time_role",
        "rows",
        "bloom_positive",
        "brier",
        "pr_auc",
        "rmse",
        "mae",
        "prior_brier",
        "prior_rmse",
        "prior_mae",
        "brier_ratio",
        "rmse_ratio",
        "mae_ratio",
        "checkpoint_objective",
    ]
    metrics = metrics.loc[:, expected_columns]
    return metrics, objective


def _selection_prediction_frame(
    bundle: TrainingBundle,
    *,
    model_id: str,
    base_seed: int,
    bloom_probability: np.ndarray,
    risk_mu: np.ndarray,
    risk_logvar: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for origin_index, metadata in enumerate(bundle.metadata.to_dict(orient="records")):
        origin = cast(Any, pd.Period(str(metadata["origin_year_month"]), freq="M"))
        for horizon_index, horizon in enumerate(HORIZONS):
            risk_prediction = float(risk_mu[origin_index, horizon_index])
            rows.append(
                {
                    "surface_id": SURFACE_ID,
                    "model_id": model_id,
                    "base_seed": base_seed,
                    "source_id": str(metadata["source_id"]),
                    "site_id": str(metadata["site_id"]),
                    "common_origin_id": str(metadata["common_origin_id"]),
                    "time_role": str(metadata["time_role"]),
                    "origin_year_month": str(origin),
                    "target_year_month": str(origin + horizon),
                    "horizon_months": horizon,
                    "observed_bloom": int(bundle.bloom[origin_index, horizon_index]),
                    "observed_risk": float(bundle.risk[origin_index, horizon_index]),
                    "predicted_bloom_probability": float(bloom_probability[origin_index, horizon_index]),
                    "predicted_risk": risk_prediction,
                    "predicted_risk_sigma": math.sqrt(
                        math.exp(
                            float(
                                np.clip(
                                    risk_logvar[origin_index, horizon_index],
                                    LOGVAR_MIN,
                                    LOGVAR_MAX,
                                )
                            )
                        )
                    ),
                    "availability_status": "success",
                    "failure_reason": "",
                    "score_semantics": "direct_bloom_probability_and_risk_distribution",
                }
            )
    return canonical_prediction_frame(pd.DataFrame(rows, columns=PREDICTION_COLUMNS))


def fit_anfis_ablation(
    bundle: TrainingBundle,
    *,
    model_id: str,
    base_seed: int,
    maximum_epochs: int = MAXIMUM_EPOCHS,
) -> FitResult:
    """Fit the fixed paired direct-outcome model on CPU.

    ``maximum_epochs`` exists solely for pure synthetic tests; production calls
    must use the locked value of twenty.
    """

    validate_model_seed(model_id, base_seed)
    if type(maximum_epochs) is not int or not 1 <= maximum_epochs <= MAXIMUM_EPOCHS:
        raise AnfisAblationTrainingError("maximum_epochs must be in [1, 20]")
    training = bundle.subset("training")
    selection = bundle.subset("model_selection")
    if len(training.metadata) == 0 or len(selection.metadata) == 0:
        raise AnfisAblationTrainingError("Training and model_selection origins are required")
    bloom_priors, risk_priors = training_priors(bundle)
    device = configure_deterministic_cpu(base_seed)
    torch = _require_torch()
    model = make_anfis_ablation_model(
        input_dimension=bundle.x.shape[2],
        bloom_priors=bloom_priors,
        risk_priors=risk_priors,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    stopping = EarlyStoppingState()
    best_state_dict: dict[str, Any] | None = None
    history: list[dict[str, Any]] = []
    for epoch in range(1, maximum_epochs + 1):
        batches, batch_digest = canonical_epoch_batches(
            training.metadata, base_seed=base_seed, epoch=epoch
        )
        model.train()
        loss_sum = 0.0
        row_count = 0
        for indices in batches:
            x = torch.from_numpy(training.x[indices]).to(device=device, dtype=torch.float32)
            bloom_target = torch.from_numpy(training.bloom[indices]).to(
                device=device, dtype=torch.float32
            )
            risk_target = torch.from_numpy(training.risk[indices]).to(
                device=device, dtype=torch.float32
            )
            optimizer.zero_grad(set_to_none=True)
            bloom_logits, risk_mu, risk_logvar = model(x)
            loss = direct_multitask_loss(
                bloom_logits, risk_mu, risk_logvar, bloom_target, risk_target
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRADIENT_CLIP_NORM)
            optimizer.step()
            rows = int(len(indices))
            loss_sum += float(loss.detach().cpu()) * rows
            row_count += rows
        selection_bloom, selection_risk, selection_logvar = _predict_arrays(
            model, selection, device=device
        )
        _, objective = _selection_metrics(
            selection,
            model_id=model_id,
            base_seed=base_seed,
            bloom_probability=selection_bloom,
            risk_mu=selection_risk,
            risk_logvar=selection_logvar,
            bloom_priors=bloom_priors,
            risk_priors=risk_priors,
        )
        previous_best = stopping.best_objective
        stopping = advance_early_stopping(stopping, epoch=epoch, objective=objective)
        if objective < previous_best - EARLY_STOPPING_MINIMUM_DELTA:
            best_state_dict = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
        history.append(
            {
                "epoch": epoch,
                "training_loss": loss_sum / max(row_count, 1),
                "model_selection_objective": objective,
                "best_objective": stopping.best_objective,
                "best_epoch": stopping.best_epoch,
                "epochs_without_improvement": stopping.epochs_without_improvement,
                "batch_order_sha256": batch_digest,
            }
        )
        if stopping.should_stop:
            break
    if best_state_dict is None or stopping.best_epoch < 1:
        raise AnfisAblationTrainingError("No finite best checkpoint was selected")
    model.load_state_dict(best_state_dict)
    selection_bloom, selection_risk, selection_logvar = _predict_arrays(
        model, selection, device=device
    )
    metrics, restored_objective = _selection_metrics(
        selection,
        model_id=model_id,
        base_seed=base_seed,
        bloom_probability=selection_bloom,
        risk_mu=selection_risk,
        risk_logvar=selection_logvar,
        bloom_priors=bloom_priors,
        risk_priors=risk_priors,
    )
    if not math.isclose(restored_objective, stopping.best_objective, rel_tol=0.0, abs_tol=1e-7):
        raise AnfisAblationTrainingError("Restored checkpoint objective drifted")
    predictions = _selection_prediction_frame(
        selection,
        model_id=model_id,
        base_seed=base_seed,
        bloom_probability=selection_bloom,
        risk_mu=selection_risk,
        risk_logvar=selection_logvar,
    )
    return FitResult(
        model=model,
        best_state_dict=best_state_dict,
        best_epoch=stopping.best_epoch,
        best_objective=stopping.best_objective,
        history=pd.DataFrame(history),
        selection_predictions=predictions,
        selection_metrics=metrics,
        bloom_priors=bloom_priors,
        risk_priors=risk_priors,
    )


def _hash_owned_name(owned: OwnedOutput) -> tuple[int, str]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(owned.path.name, flags, dir_fd=owned.directory_descriptor)
    try:
        before = os.fstat(descriptor)
        named = os.stat(
            owned.path.name, dir_fd=owned.directory_descriptor, follow_symlinks=False
        )
        expected = (owned.device, owned.inode)
        if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(named.st_mode) or (
            before.st_dev,
            before.st_ino,
        ) != expected or (named.st_dev, named.st_ino) != expected:
            raise AnfisAblationTrainingError("Owned output identity drifted")
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
            raise AnfisAblationTrainingError("Owned output changed while hashing")
        return size, digest.hexdigest()
    finally:
        os.close(descriptor)


def _publish_owned(path: Path, payload: bytes, *, repo_root: Path) -> OwnedOutput:
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
            raise AnfisAblationTrainingError(f"Refusing to overwrite {path}.tmp") from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AnfisAblationTrainingError("Temporary output is not regular")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        view = memoryview(payload)
        written = 0
        while written < len(view):
            progress = os.write(descriptor, view[written:])
            if progress <= 0:
                raise AnfisAblationTrainingError(
                    "Temporary output write made no progress"
                )
            written += progress
        os.fsync(descriptor)
        temporary = os.stat(temporary_name, dir_fd=parent_fd, follow_symlinks=False)
        lexical_parent = lexical.parent.lstat()
        opened_parent = os.fstat(parent_fd)
        if (
            not stat.S_ISREG(temporary.st_mode)
            or (temporary.st_dev, temporary.st_ino) != (device, inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (lexical_parent.st_dev, lexical_parent.st_ino)
            != (opened_parent.st_dev, opened_parent.st_ino)
        ):
            raise AnfisAblationTrainingError("Temporary output identity drifted")
        try:
            os.link(
                temporary_name,
                lexical.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise AnfisAblationTrainingError(f"Refusing to overwrite {path}") from exc
        final = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(final.st_mode) or (final.st_dev, final.st_ino) != (
            device,
            inode,
        ):
            _unlink_name_if_owned(parent_fd, lexical.name, device=device, inode=inode)
            raise AnfisAblationTrainingError("Final output identity drifted")
        if not _unlink_name_if_owned(
            parent_fd, temporary_name, device=device, inode=inode
        ):
            _unlink_name_if_owned(parent_fd, lexical.name, device=device, inode=inode)
            raise AnfisAblationTrainingError("Temporary output changed before publication")
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
            error = AnfisAblationTrainingError("Output cleanup failed")
            if active_error is not None:
                raise error from active_error
            raise error from cleanup_errors[0]


class OutputTransaction:
    """Own every published inode until manifest-last commit succeeds."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._owned: list[OwnedOutput] = []

    def __enter__(self) -> "OutputTransaction":
        return self

    def publish_bytes(self, payload: bytes, path: Path) -> OwnedOutput:
        owned = _publish_owned(path, payload, repo_root=self.repo_root)
        self._owned.append(owned)
        return owned

    def record(self, owned: OwnedOutput) -> dict[str, Any]:
        if owned not in self._owned:
            raise AnfisAblationTrainingError("Output is not transaction-owned")
        size, sha256 = _hash_owned_name(owned)
        if (size, sha256) != (owned.bytes, owned.sha256):
            raise AnfisAblationTrainingError("Owned output content drifted")
        return {
            "path": _repo_relative(owned.path, self.repo_root),
            "bytes": size,
            "sha256": sha256,
        }

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        commit_error: AnfisAblationTrainingError | None = None
        rollback_errors: list[Exception] = []
        if exc_type is None:
            for owned in self._owned:
                try:
                    self.record(owned)
                    opened_parent = os.fstat(owned.directory_descriptor)
                    lexical_parent = owned.path.parent.lstat()
                except (AnfisAblationTrainingError, FileNotFoundError, OSError) as error:
                    commit_error = AnfisAblationTrainingError(
                        f"Bundle output disappeared before commit: {owned.path}"
                    )
                    commit_error.add_note(str(error))
                    break
                if not stat.S_ISDIR(lexical_parent.st_mode) or (
                    opened_parent.st_dev,
                    opened_parent.st_ino,
                ) != (lexical_parent.st_dev, lexical_parent.st_ino):
                    commit_error = AnfisAblationTrainingError(
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
            error = AnfisAblationTrainingError("Bundle output rollback failed")
            if exc is not None:
                raise error from exc
            if commit_error is not None:
                raise error from commit_error
            raise error from rollback_errors[0]
        if commit_error is not None:
            raise commit_error
        return False


def _acquire_guard(path: Path, *, repo_root: Path) -> OwnedGuard:
    parent_fd, lexical = _open_real_repository_parent(
        path, repo_root=repo_root, create=True, directory_mode=0o700
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    try:
        descriptor = os.open(lexical.name, flags, 0o600, dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AnfisAblationTrainingError("Training guard is not regular")
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
            raise AnfisAblationTrainingError("Training guard identity drifted")
        if not _unlink_name_if_owned(
            guard.directory_descriptor,
            guard.path.name,
            device=guard.device,
            inode=guard.inode,
        ):
            raise AnfisAblationTrainingError("Owned training guard disappeared")
        os.fsync(guard.directory_descriptor)
    except Exception as error:
        errors.append(error)
    for descriptor in (guard.file_descriptor, guard.directory_descriptor):
        try:
            os.close(descriptor)
        except OSError as error:
            errors.append(error)
    if errors:
        error = AnfisAblationTrainingError("Training guard cleanup failed")
        error.add_note(
            "Cleanup failures: "
            + "; ".join(f"{type(item).__name__}: {item}" for item in errors)
        )
        raise error from errors[0]


def assert_slot_namespace_absent(paths: SlotPaths, *, allow_guard: bool = False) -> None:
    candidates = [*paths.finals, *paths.temporaries, paths.pointer, Path(f"{paths.pointer}.tmp"), paths.guard]
    present = [
        path.as_posix()
        for path in candidates
        if _lexists(path) and not (allow_guard and path == paths.guard)
    ]
    if present:
        raise AnfisAblationTrainingError(f"Training slot namespace is not empty: {present}")


def _assert_published_namespace(paths: SlotPaths, *, repo_root: Path) -> None:
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
        raise AnfisAblationTrainingError(
            f"Published model/guard namespace drifted: {missing_or_nonregular}"
        )
    forbidden = (
        *paths.temporaries,
        paths.pointer,
        Path(f"{paths.pointer}.tmp"),
        repo_root / OUTCOME_ACCESS_LOG,
    )
    present = [path.as_posix() for path in forbidden if _lexists(path)]
    if present:
        raise AnfisAblationTrainingError(f"Forbidden side effect appeared: {present}")


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd", use_dictionary=False)
    return sink.getvalue().to_pybytes()


def _torch_bytes(payload: Mapping[str, Any]) -> bytes:
    buffer = io.BytesIO()
    _require_torch().save(dict(payload), buffer)
    return buffer.getvalue()


def _refresh_role_records(
    records: Sequence[Mapping[str, Any]], paths: Sequence[Path], *, repo_root: Path
) -> list[dict[str, Any]]:
    if len(records) != len(paths):
        raise AnfisAblationTrainingError("Input record/path cardinality drifted")
    refreshed: list[dict[str, Any]] = []
    for record, path in zip(records, paths, strict=True):
        role = record.get("role")
        if not isinstance(role, str) or not role:
            raise AnfisAblationTrainingError("Input record role is absent")
        physical = _stable_file_record(path, repo_root=repo_root)
        if physical["path"] != record.get("path"):
            raise AnfisAblationTrainingError("Input record/path ordering drifted")
        refreshed.append({"role": role, **physical})
    return refreshed


def _authority_records(
    authority: Mapping[str, Any], *, repo_root: Path
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key, role, path in AUTHORITY_RECORD_SPECS:
        raw = authority.get(key)
        if not isinstance(raw, Mapping) or set(raw) != {
            "role",
            "path",
            "bytes",
            "sha256",
        }:
            raise AnfisAblationTrainingError(
                f"E0-MX authority record is incomplete: {key}"
            )
        physical = {"role": role, **_stable_file_record(repo_root / path, repo_root=repo_root)}
        if dict(raw) != physical:
            raise AnfisAblationTrainingError(
                f"E0-MX authority record differs from disk: {key}"
            )
        records.append(physical)
    return records


def _refresh_authority_records(
    records: Sequence[Mapping[str, Any]], *, repo_root: Path
) -> list[dict[str, Any]]:
    if len(records) != len(AUTHORITY_RECORD_SPECS):
        raise AnfisAblationTrainingError("E0-MX authority record count drifted")
    refreshed: list[dict[str, Any]] = []
    for record, (_, role, path) in zip(records, AUTHORITY_RECORD_SPECS, strict=True):
        if record.get("role") != role or record.get("path") != path.as_posix():
            raise AnfisAblationTrainingError("E0-MX authority record ordering drifted")
        refreshed.append(
            {"role": role, **_stable_file_record(repo_root / path, repo_root=repo_root)}
        )
    return refreshed


def _completed_prefix_snapshot(
    authority: Mapping[str, Any], *, repo_root: Path
) -> tuple[dict[str, Any], ...]:
    completed = authority.get("completed_prefix_count")
    creation = authority.get("slot_creation_prefix_count")
    ordered = authority.get("ordered_slots")
    expected_order = tuple(
        (model_id, seed)
        for seed in REGISTERED_SEEDS
        for model_id in MODEL_IDS
    )
    if (
        type(completed) is not int
        or type(creation) is not int
        or completed != creation
        or not 0 <= completed <= len(expected_order)
        or type(ordered) is not list
        or len(ordered) != len(expected_order)
    ):
        raise AnfisAblationTrainingError(
            "E0-MX completed-prefix authority is incomplete"
        )
    normalized: list[tuple[str, int]] = []
    for raw, (expected_model, expected_seed) in zip(
        ordered, expected_order, strict=True
    ):
        if type(raw) is not dict or set(raw) != {"model_id", "base_seed"}:
            raise AnfisAblationTrainingError(
                "E0-MX completed-prefix slot order drifted"
            )
        slot = cast(dict[str, Any], raw)
        if (
            type(slot.get("model_id")) is not str
            or type(slot.get("base_seed")) is not int
            or slot.get("model_id") != expected_model
            or slot.get("base_seed") != expected_seed
        ):
            raise AnfisAblationTrainingError(
                "E0-MX completed-prefix slot order drifted"
            )
        normalized.append((expected_model, expected_seed))
    snapshot: list[dict[str, Any]] = []
    for model_id, base_seed in normalized[:completed]:
        for path in slot_paths(model_id, base_seed, repo_root=repo_root).finals:
            fingerprint = _stable_file_fingerprint(path, repo_root=repo_root)
            if fingerprint["mode"] != 0o644:
                raise AnfisAblationTrainingError(
                    f"Completed-prefix artifact mode drifted: {fingerprint['path']}"
                )
            if fingerprint["nlink"] != 1:
                raise AnfisAblationTrainingError(
                    "Completed-prefix artifact link count drifted: "
                    f"{fingerprint['path']}"
                )
            snapshot.append(fingerprint)
    if len(snapshot) != 8 * completed:
        raise AnfisAblationTrainingError(
            "E0-MX completed-prefix artifact count drifted"
        )
    return tuple(snapshot)


def _assert_completed_prefix_snapshot(
    baseline: Sequence[Mapping[str, Any]],
    *,
    authority: Mapping[str, Any],
    repo_root: Path,
) -> None:
    current = _completed_prefix_snapshot(authority, repo_root=repo_root)
    if list(current) != [dict(record) for record in baseline]:
        raise AnfisAblationTrainingError(
            "E0-MX completed-prefix artifact changed during fit/publication"
        )


def _local_git_snapshot(repo_root: Path) -> tuple[str, frozenset[str]]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        status_payload = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AnfisAblationTrainingError("Local Git authority snapshot failed") from exc
    try:
        entries = frozenset(
            item.decode("utf-8") for item in status_payload.split(b"\0") if item
        )
    except UnicodeDecodeError as exc:
        raise AnfisAblationTrainingError("Local Git status is not UTF-8") from exc
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise AnfisAblationTrainingError("Local Git HEAD is malformed")
    return head, entries


def _assert_local_git_snapshot(
    baseline: tuple[str, frozenset[str]],
    *,
    authority: Mapping[str, Any],
    repo_root: Path,
    allowed_new_paths: Sequence[Path] = (),
) -> None:
    current_head, current_status = _local_git_snapshot(repo_root)
    baseline_head, baseline_status = baseline
    if (
        current_head != baseline_head
        or current_head != authority.get("p_patch_head")
        or not baseline_status.issubset(current_status)
    ):
        raise AnfisAblationTrainingError("E0-MX Git authority changed during fit")
    allowed = {
        _repo_relative(path, repo_root)
        for path in allowed_new_paths
    }
    for entry in current_status - baseline_status:
        if len(entry) < 4 or entry[:2] != "??" or entry[3:] not in allowed:
            raise AnfisAblationTrainingError(
                "E0-MX worktree scope changed during fit"
            )


def _require_effective_authority(
    *, repo_root: Path, model_id: str, base_seed: int
) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_model_publication_adoption_patch import (
        require_anfis_ablation_model_publication_authority,
    )

    authority = require_anfis_ablation_model_publication_authority(
        model_id,
        base_seed,
        repo_root=repo_root,
        audit_current_unpublished=False,
    )
    if not isinstance(authority, Mapping) or authority.get("gate") != "E0-MX":
        raise AnfisAblationTrainingError("E0-MX authority must be an exact mapping")
    return dict(authority)


def _load_runtime_after_gate(repo_root: Path) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_training_development_patch import (
        load_anfis_ablation_training_runtime,
    )

    runtime = load_anfis_ablation_training_runtime(
        repo_root=repo_root,
        verify_physical_pins=True,
    )
    if not isinstance(runtime, Mapping):
        raise AnfisAblationTrainingError("E0-MT runtime must be a mapping")
    result = dict(runtime)
    _validate_runtime_alignment(result)
    return result


def _validate_runtime_alignment(runtime: Mapping[str, Any]) -> None:
    if runtime.get("gate") != "E0-MT" or runtime.get("status") != "ready_to_lock":
        raise AnfisAblationTrainingError("E0-MT runtime gate/status drifted")
    targets = runtime.get("targets")
    inputs = runtime.get("inputs")
    preprocessing = runtime.get("preprocessing")
    model = runtime.get("model")
    slots = runtime.get("slots")
    outputs = runtime.get("outputs")
    if not all(
        isinstance(section, Mapping)
        for section in (targets, inputs, preprocessing, model, slots, outputs)
    ):
        raise AnfisAblationTrainingError("E0-MT runtime sections are incomplete")
    assert isinstance(targets, Mapping)
    assert isinstance(inputs, Mapping)
    assert isinstance(preprocessing, Mapping)
    assert isinstance(model, Mapping)
    assert isinstance(slots, Mapping)
    assert isinstance(outputs, Mapping)
    if (
        targets.get("join_columns") != list(TARGET_JOIN_COLUMNS)
        or targets.get("exact_projection") != list(TARGET_PROJECTION)
        or targets.get("horizons_months") != list(HORIZONS)
        or targets.get("training")
        != {"origins": EXPECTED_TRAINING_ORIGINS, "rows": EXPECTED_TRAINING_TARGET_ROWS}
        or targets.get("model_selection")
        != {"origins": EXPECTED_SELECTION_ORIGINS, "rows": EXPECTED_SELECTION_TARGET_ROWS}
    ):
        raise AnfisAblationTrainingError("E0-MT direct target contract drifted")
    if (
        inputs.get("raw_value_columns") != list(RAW_STANDARDIZATION_COLUMNS)
        or inputs.get("raw_mask_columns") != list(RAW_MASK_COLUMNS)
        or inputs.get("A0") != {"input_dimension": 18, "sequence_slot_base_seed": None}
        or inputs.get("A1")
        != {"input_dimension": 27, "sequence_slot_base_seed": "same_as_model_seed"}
    ):
        raise AnfisAblationTrainingError("E0-MT input contract drifted")
    if (
        preprocessing.get("fit_role") != "training"
        or preprocessing.get("raw_values")
        != "mask_aware_training_standard_scaler_ddof0"
        or preprocessing.get("fit_outside_training") != "forbidden"
        or preprocessing.get("shared_raw_statistics_required_across_all_slots") is not True
    ):
        raise AnfisAblationTrainingError("E0-MT preprocessing contract drifted")
    architecture = model.get("common_architecture")
    optimization = model.get("optimization")
    loss = model.get("loss")
    selection = model.get("selection")
    if not all(
        isinstance(section, Mapping)
        for section in (architecture, optimization, loss, selection)
    ):
        raise AnfisAblationTrainingError("E0-MT model contract is incomplete")
    assert isinstance(architecture, Mapping)
    assert isinstance(optimization, Mapping)
    assert isinstance(loss, Mapping)
    assert isinstance(selection, Mapping)
    if (
        architecture.get("hidden_dimension") != HIDDEN_DIMENSION
        or architecture.get("recurrent_layers") != RECURRENT_LAYERS
        or architecture.get("dropout") != DROPOUT
        or architecture.get("add_last") is not False
        or architecture.get("residual_mode") != "training_only_horizon_priors"
        or architecture.get("risk_logvar_clamp") != [LOGVAR_MIN, LOGVAR_MAX]
    ):
        raise AnfisAblationTrainingError("E0-MT architecture contract drifted")
    if optimization != {
        "optimizer": "AdamW",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_clip_norm": GRADIENT_CLIP_NORM,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAXIMUM_EPOCHS,
        "early_stopping_patience_epochs": EARLY_STOPPING_PATIENCE,
        "early_stopping_minimum_delta": EARLY_STOPPING_MINIMUM_DELTA,
    }:
        raise AnfisAblationTrainingError("E0-MT optimization contract drifted")
    ordered_slots = [
        {"model_id": model_id, "base_seed": seed}
        for seed in REGISTERED_SEEDS
        for model_id in MODEL_IDS
    ]
    if slots.get("ordered_slots") != ordered_slots or slots.get("exact_slot_count") != 10:
        raise AnfisAblationTrainingError("E0-MT paired slot order drifted")
    expected_output_templates = {
        "model_template": "models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.pt",
        "checkpoint_template": "models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.checkpoint.pt",
        "preprocessor_template": "reports/closure_v1/02_models/{model_id}/seed_{base_seed}_preprocessor.json",
        "training_curve_template": "reports/closure_v1/02_models/{model_id}/seed_{base_seed}_training_curve.csv",
        "selection_predictions_template": "data/closure_v1/development/anfis_ablation/{model_id}/seed_{base_seed}_selection_predictions.parquet",
        "selection_prediction_pointer_template": "data/closure_v1/development/anfis_ablation/{model_id}/seed_{base_seed}_selection_predictions.parquet.dvc",
        "selection_metrics_template": "reports/closure_v1/02_models/{model_id}/seed_{base_seed}_selection_metrics.csv",
        "report_template": "reports/closure_v1/02_models/{model_id}/seed_{base_seed}_report.md",
        "manifest_template": "reports/closure_v1/02_models/{model_id}/seed_{base_seed}_manifest.json",
        "guard_template": "tmp/closure_v1_anfis_ablation_training/{model_id}_seed_{base_seed}.guard",
    }
    if any(outputs.get(key) != value for key, value in expected_output_templates.items()):
        raise AnfisAblationTrainingError("E0-MT output namespace drifted")


def _authority_binding(authority: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "gate",
        "status",
        "authorized_model_id",
        "authorized_base_seed",
        "completed_prefix_count",
        "slot_creation_prefix_count",
        "h_patch_head",
        "p_patch_head",
        "h_components_sha256",
        "physical_inputs_sha256",
        "runtime_sha256",
        "lock_sha256",
        "companion_sha256",
    )
    raw = authority.get("slot_manifest_authority")
    if not isinstance(raw, Mapping) or set(raw) != set(required):
        raise AnfisAblationTrainingError(
            "E0-MX slot-manifest authority binding is incomplete"
        )
    normalized = {key: raw[key] for key in required}
    if (
        normalized.get("gate") != "E0-MX"
        or normalized.get("status") != "effective_preflight_passed"
        or normalized.get("authorized_model_id")
        != authority.get("authorized_model_id")
        or normalized.get("authorized_base_seed")
        != authority.get("authorized_base_seed")
        or type(normalized.get("slot_creation_prefix_count")) is not int
        or normalized.get("completed_prefix_count")
        != normalized.get("slot_creation_prefix_count")
    ):
        raise AnfisAblationTrainingError(
            "E0-MX slot-manifest authority binding drifted"
        )
    try:
        json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AnfisAblationTrainingError("E0-MX authority binding is not JSON-safe") from exc
    return normalized


def _model_config(model_id: str) -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "family": "direct_multitask_probabilistic_gru",
        "model_id": model_id,
        "history_length_months": HISTORY_LENGTH,
        "input_columns": list(input_columns(model_id)),
        "input_dimension": len(input_columns(model_id)),
        "hidden_dimension": HIDDEN_DIMENSION,
        "recurrent_layers": RECURRENT_LAYERS,
        "dropout": DROPOUT,
        "add_last": False,
        "residual_mode": RESIDUAL_MODE,
        "horizons_months": list(HORIZONS),
        "heads": ["bloom_logit", "risk_mean", "risk_log_variance"],
        "risk_logvar_clamp": [LOGVAR_MIN, LOGVAR_MAX],
        "loss": "equal_bce_plus_gaussian_nll_plus_mse",
        "optimizer": "AdamW",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_clip_norm": GRADIENT_CLIP_NORM,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAXIMUM_EPOCHS,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "early_stopping_minimum_delta": EARLY_STOPPING_MINIMUM_DELTA,
        "device": LOCKED_DEVICE,
    }


def _manifest_contract_sections(
    runtime: Mapping[str, Any], *, model_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    def section(name: str) -> Mapping[str, Any]:
        value = runtime.get(name)
        if not isinstance(value, Mapping):
            raise AnfisAblationTrainingError(f"Runtime section is absent: {name}")
        return value

    targets = section("targets")
    inputs = section("inputs")
    preprocessing = section("preprocessing")
    model = section("model")
    roles = section("roles")
    model_inputs = inputs.get(model_id)
    if not isinstance(model_inputs, Mapping):
        raise AnfisAblationTrainingError("Runtime model input section is absent")
    target_contract = {
        "join_columns": list(targets["join_columns"]),
        "exact_projection": list(targets["exact_projection"]),
        "horizons_months": list(targets["horizons_months"]),
        "development_target_access_end": str(roles["model_selection_end"]),
        "calibration_target_values_opened": False,
        "raw_chlorophyll_projection": "forbidden",
    }
    role_counts = {
        "training": dict(cast(Mapping[str, Any], targets["training"])),
        "model_selection": dict(cast(Mapping[str, Any], targets["model_selection"])),
        "calibration_threshold_metadata_only": dict(
            cast(Mapping[str, Any], targets["calibration_threshold_closed"])
        ),
        "calibration_target_rows_read": 0,
        "test_target_rows_read": 0,
        "holdout_target_rows_read": 0,
        "post_2020_target_rows_read": 0,
    }
    architecture = {
        "history_length_months": int(inputs["history_length_months"]),
        "input_dimension": int(model_inputs["input_dimension"]),
        "family": model["family"],
        "common_architecture": dict(
            cast(Mapping[str, Any], model["common_architecture"])
        ),
        "loss": dict(cast(Mapping[str, Any], model["loss"])),
        "selection": dict(cast(Mapping[str, Any], model["selection"])),
        "optimization": dict(cast(Mapping[str, Any], model["optimization"])),
        "execution": dict(cast(Mapping[str, Any], model["execution"])),
    }
    return target_contract, role_counts, architecture, dict(preprocessing)


def _digest_rows(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for values in frame.loc[:, list(columns)].itertuples(index=False, name=None):
        digest.update(
            json.dumps(
                list(values),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    return digest.hexdigest()


def _pairing_record(
    *,
    bundle: TrainingBundle,
    selection_predictions: pd.DataFrame,
    model_id: str,
    base_seed: int,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    training = bundle.subset("training").metadata.sort_values(
        ["source_id", "site_id", "origin_year_month", "common_origin_id"],
        kind="mergesort",
    )
    training_identity = _digest_rows(
        training,
        ("source_id", "site_id", "common_origin_id", "time_role", "origin_year_month"),
    )
    identity_columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    )
    selection_identity = _digest_rows(selection_predictions, identity_columns)
    selection_targets = _digest_rows(
        selection_predictions,
        (*identity_columns, "observed_bloom", "observed_risk"),
    )
    slots = runtime.get("slots")
    if not isinstance(slots, Mapping):
        raise AnfisAblationTrainingError("Runtime slot contract is absent")
    return {
        "policy": slots.get("pairing_policy"),
        "paired_model_ids": list(MODEL_IDS),
        "base_seed": base_seed,
        "training_identity_sha256": training_identity,
        "selection_identity_sha256": selection_identity,
        "selection_target_sha256": selection_targets,
    }


def check_only(
    *, model_id: str, base_seed: int, repo_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Perform the cutoff-safe physical preflight without fitting or writing."""

    authority = _require_effective_authority(
        repo_root=repo_root, model_id=model_id, base_seed=base_seed
    )
    runtime = _load_runtime_after_gate(repo_root)
    paths = slot_paths(model_id, base_seed, repo_root=repo_root)
    assert_slot_namespace_absent(paths)
    bundle, standardizer, input_records, _ = load_training_bundle(
        model_id=model_id, base_seed=base_seed, repo_root=repo_root
    )
    return {
        "status": "ready_to_execute_one_shot",
        "model_id": model_id,
        "base_seed": base_seed,
        "training_origins": len(bundle.subset("training").metadata),
        "model_selection_origins": len(bundle.subset("model_selection").metadata),
        "input_record_count": len(input_records),
        "raw_standardizer": standardizer.as_dict(),
        "authority": _authority_binding(authority),
        "writes_performed": False,
        "fit_performed": False,
        "calibration_targets_read": False,
        "dvc_command_executed": False,
        "future_outcomes_accessed": False,
    }


def execute_one_shot(
    *,
    model_id: str,
    base_seed: int,
    repo_root: Path = PROJECT_ROOT,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Consume one E0-MX slot authorization and publish eight finals atomically."""

    effective = _require_effective_authority(
        repo_root=repo_root, model_id=model_id, base_seed=base_seed
    )
    if authority is not None and dict(authority) != effective:
        raise AnfisAblationTrainingError("Injected E0-MX authority differs from live authority")
    authority_records = _authority_records(effective, repo_root=repo_root)
    git_snapshot = _local_git_snapshot(repo_root)
    _assert_local_git_snapshot(
        git_snapshot, authority=effective, repo_root=repo_root
    )
    completed_prefix_snapshot = _completed_prefix_snapshot(
        effective, repo_root=repo_root
    )
    runtime = _load_runtime_after_gate(repo_root)
    validate_model_seed(model_id, base_seed)
    paths = slot_paths(model_id, base_seed, repo_root=repo_root)
    assert_slot_namespace_absent(paths)
    if _lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationTrainingError("Outcome access log must remain absent before E0-M")
    guard = _acquire_guard(paths.guard, repo_root=repo_root)
    guard_active = True
    try:
        assert_slot_namespace_absent(paths, allow_guard=True)
        bundle, standardizer, input_records, input_paths = load_training_bundle(
            model_id=model_id, base_seed=base_seed, repo_root=repo_root
        )
        before_inputs = [dict(record) for record in input_records]
        source_record = {
            "role": "trainer",
            **_stable_file_record(Path(__file__), repo_root=repo_root),
        }
        with threadpool_limits(limits=1):
            result = fit_anfis_ablation(
                bundle,
                model_id=model_id,
                base_seed=base_seed,
                maximum_epochs=MAXIMUM_EPOCHS,
            )
        after_inputs = _refresh_role_records(
            before_inputs, input_paths, repo_root=repo_root
        )
        if (
            after_inputs != before_inputs
            or _refresh_authority_records(authority_records, repo_root=repo_root)
            != authority_records
            or {
            "role": "trainer",
            **_stable_file_record(Path(__file__), repo_root=repo_root),
            }
            != source_record
        ):
            raise AnfisAblationTrainingError("Trainer inputs/source changed during fit")
        _assert_completed_prefix_snapshot(
            completed_prefix_snapshot,
            authority=effective,
            repo_root=repo_root,
        )
        _assert_local_git_snapshot(
            git_snapshot, authority=effective, repo_root=repo_root
        )
        config = _model_config(model_id)
        artifact_base = {
            "model_version": MODEL_VERSION,
            "experiment_id": "closure_v1",
            "surface_id": SURFACE_ID,
            "gate": "E0-MT",
            "model_id": model_id,
            "base_seed": base_seed,
            "upstream_state_seed": base_seed if model_id == "A1" else None,
            "device": LOCKED_DEVICE,
            "config": config,
            "bloom_training_priors": result.bloom_priors.tolist(),
            "risk_training_priors": result.risk_priors.tolist(),
            "best_epoch": result.best_epoch,
            "best_model_selection_objective": result.best_objective,
            "model_state_dict": result.best_state_dict,
        }
        preprocessor = {
            **standardizer.as_dict(),
            "model_id": model_id,
            "base_seed": base_seed,
            "input_columns": list(input_columns(model_id)),
            "identity_channels": list(input_columns(model_id)[RAW_DIMENSION:]),
            "bloom_training_priors": result.bloom_priors.tolist(),
            "risk_training_priors": result.risk_priors.tolist(),
            "calibration_used": False,
        }
        report_text = "\n".join(
            [
                f"# Closure V1 ANFIS ablation {model_id} seed {base_seed}",
                "",
                "Status: `completed`",
                "",
                f"Best epoch: `{result.best_epoch}`",
                f"Best model-selection objective: `{result.best_objective:.12g}`",
                f"Training origins: `{EXPECTED_TRAINING_ORIGINS}`",
                f"Model-selection origins: `{EXPECTED_SELECTION_ORIGINS}`",
                "",
                "Targets are limited to development rows through 2020-12.",
                "Calibration 2021, holdout, E0-M, E0-U and final E7 claims were not accessed.",
                "",
            ]
        ).encode("utf-8")
        prediction_table = prediction_arrow_table(result.selection_predictions)
        output_payloads = {
            "model": _torch_bytes(
                {**artifact_base, "artifact_role": "final_restored_model"}
            ),
            "checkpoint": _torch_bytes(
                {**artifact_base, "artifact_role": "raw_best_checkpoint"}
            ),
            "preprocessor": _json_bytes(preprocessor),
            "training_curve": _csv_bytes(result.history),
            "selection_predictions": _parquet_bytes(prediction_table),
            "selection_metrics": _csv_bytes(result.selection_metrics),
            "report": report_text,
        }
        with OutputTransaction(repo_root) as transaction:
            owned: dict[str, OwnedOutput] = {}
            for name in MODEL_OUTPUT_NAMES:
                owned[name] = transaction.publish_bytes(
                    output_payloads[name], getattr(paths, name)
                )
            output_records = [
                {"role": name, **transaction.record(owned[name])}
                for name in MODEL_OUTPUT_NAMES
            ]
            _assert_completed_prefix_snapshot(
                completed_prefix_snapshot,
                authority=effective,
                repo_root=repo_root,
            )
            if _refresh_role_records(
                before_inputs, input_paths, repo_root=repo_root
            ) != before_inputs or _refresh_authority_records(
                authority_records, repo_root=repo_root
            ) != authority_records or {
                "role": "trainer",
                **_stable_file_record(Path(__file__), repo_root=repo_root),
            } != source_record:
                raise AnfisAblationTrainingError(
                    "Trainer inputs/source changed before manifest publication"
                )
            _assert_local_git_snapshot(
                git_snapshot,
                authority=effective,
                repo_root=repo_root,
                allowed_new_paths=tuple(
                    getattr(paths, name) for name in MODEL_OUTPUT_NAMES
                ),
            )
            target_contract, role_counts, architecture, runtime_preprocessing = (
                _manifest_contract_sections(runtime, model_id=model_id)
            )
            pairing = _pairing_record(
                bundle=bundle,
                selection_predictions=result.selection_predictions,
                model_id=model_id,
                base_seed=base_seed,
                runtime=runtime,
            )
            manifest = {
                "manifest_version": MANIFEST_VERSION,
                "status": "completed",
                "slot_status": "available",
                "fit_status": "passed",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "experiment_id": "closure_v1",
                "surface_id": SURFACE_ID,
                "model_id": model_id,
                "base_seed": base_seed,
                "device": LOCKED_DEVICE,
                "future_outcomes_accessed": False,
                "calibration_authorized": False,
                "calibration_target_accessed": False,
                "evaluation_authorized": False,
                "e0_m_authorized": False,
                "e0_u_authorized": False,
                "dvc_command_executed": False,
                "target_contract": target_contract,
                "role_counts": role_counts,
                "architecture": architecture,
                "preprocessing": runtime_preprocessing,
                "pairing": pairing,
                "authority": _authority_binding(effective),
                "authority_records": authority_records,
                "script": source_record,
                "inputs": before_inputs,
                "source_code": [source_record],
                "outputs": output_records,
                "completion_marker_written_last": True,
            }
            manifest_owned = transaction.publish_bytes(
                _json_bytes(manifest), paths.manifest
            )
            manifest_record = transaction.record(manifest_owned)
            _assert_completed_prefix_snapshot(
                completed_prefix_snapshot,
                authority=effective,
                repo_root=repo_root,
            )
            if _refresh_role_records(
                before_inputs, input_paths, repo_root=repo_root
            ) != before_inputs or _refresh_authority_records(
                authority_records, repo_root=repo_root
            ) != authority_records or {
                "role": "trainer",
                **_stable_file_record(Path(__file__), repo_root=repo_root),
            } != source_record:
                raise AnfisAblationTrainingError(
                    "Trainer inputs/source changed after manifest publication"
                )
            _assert_local_git_snapshot(
                git_snapshot,
                authority=effective,
                repo_root=repo_root,
                allowed_new_paths=paths.finals,
            )
            _assert_published_namespace(paths, repo_root=repo_root)
            _assert_completed_prefix_snapshot(
                completed_prefix_snapshot,
                authority=effective,
                repo_root=repo_root,
            )
            try:
                _release_guard(guard)
            finally:
                guard_active = False
        return {
            "status": "anfis_ablation_model_bundle_written_unpublished",
            "model_id": model_id,
            "base_seed": base_seed,
            "training_origins": EXPECTED_TRAINING_ORIGINS,
            "model_selection_origins": EXPECTED_SELECTION_ORIGINS,
            "best_epoch": result.best_epoch,
            "best_model_selection_objective": result.best_objective,
            "outputs": [*output_records, manifest_record],
            "calibration_targets_read": False,
            "dvc_command_executed": False,
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
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--device", choices=[LOCKED_DEVICE], default=LOCKED_DEVICE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-one-shot", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # First operation after parsing: published target-slot authority.  No
    # output path, sequence, target or runtime is resolved before this gate.
    authority = _require_effective_authority(
        repo_root=PROJECT_ROOT,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    result = (
        check_only(
            model_id=args.model_id,
            base_seed=args.base_seed,
            repo_root=PROJECT_ROOT,
        )
        if args.check_only
        else execute_one_shot(
            model_id=args.model_id,
            base_seed=args.base_seed,
            repo_root=PROJECT_ROOT,
            authority=authority,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
