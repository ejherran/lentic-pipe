#!/usr/bin/env python
"""Train a probabilistic PIPE Neural ODE one-step state model."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, SEASON_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import (
    STATE_TARGET_NAMES,
    TARGET_WEIGHTS,
    _elapsed,
    _file_record,
    _format_float,
    _format_int,
    _parse_float_grid,
    _require_torch,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
    compare_to_persistence,
    evaluate_persistence,
    gaussian_nll,
    load_sequences,
    make_loss_weights,
    sample_indices,
    set_reproducible_seed,
    validation_selection_objective,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_SEQUENCE_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json")
DEFAULT_MODELS_DIR = Path("models/pipe_neural_ode/adaptive_wqp_focused")
DEFAULT_REPORT_DIR = Path("reports/pipe_neural_ode/adaptive_wqp_focused")
DEFAULT_MODEL = DEFAULT_MODELS_DIR / "pipe_neural_ode_model_v0.pt"
DEFAULT_CHECKPOINT = DEFAULT_MODELS_DIR / "pipe_neural_ode_checkpoint_v0.pt"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_metrics.csv"
DEFAULT_PERSISTENCE_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_persistence_metrics.csv"
DEFAULT_COMPARISON = DEFAULT_REPORT_DIR / "pipe_neural_ode_persistence_comparison.csv"
DEFAULT_BLEND_WEIGHTS = DEFAULT_REPORT_DIR / "pipe_neural_ode_output_blend_weights.csv"
DEFAULT_BLEND_SEARCH = DEFAULT_REPORT_DIR / "pipe_neural_ode_output_blend_search.csv"
DEFAULT_TRAINING_CURVE = DEFAULT_REPORT_DIR / "pipe_neural_ode_training_curve.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_neural_ode_prediction_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_neural_ode_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_neural_ode_manifest.json"

MODEL_VERSION = "pipe_neural_ode_v0"
STATE_INPUT_COLUMNS = [f"x_{column}" for column in PIPE_STATE_COLUMNS]
ID_COLUMNS = ["source_id", "site_id", "sequence_step", "origin_year_month", "target_year_month", "split"]
BOUNDED_01_COUNT = 6


class TransitionDataset:
    def __init__(
        self,
        state_values: np.ndarray,
        season_values: np.ndarray,
        target_values: np.ndarray,
        indices: np.ndarray,
    ) -> None:
        self.state_values = state_values
        self.season_values = season_values
        self.target_values = target_values
        self.indices = indices.astype("int64")

    def __len__(self) -> int:
        return int(len(self.indices))

    def __getitem__(self, item: int) -> tuple[Any, Any, Any]:
        torch = _require_torch()
        index = int(self.indices[item])
        return (
            torch.from_numpy(self.state_values[index]),
            torch.from_numpy(self.season_values[index]),
            torch.from_numpy(self.target_values[index]),
        )


def _require_torchdiffeq() -> Any:
    try:
        import torchdiffeq
    except ImportError as exc:
        raise RuntimeError(
            "torchdiffeq is required for PIPE Neural ODE training. "
            "Install the modeling group with Poetry before running this script."
        ) from exc
    return torchdiffeq


def _data_loader(dataset: TransitionDataset, *, batch_size: int, shuffle: bool, seed: int) -> Any:
    torch = _require_torch()
    generator = torch.Generator()
    generator.manual_seed(seed)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, generator=generator)


def _bound_state_tensor(state: Any) -> Any:
    torch = _require_torch()
    bounded_01 = torch.clamp(state[:, :BOUNDED_01_COUNT], min=0.0, max=1.0)
    bounded_delta = torch.clamp(state[:, BOUNDED_01_COUNT:], min=-1.0, max=1.0)
    return torch.cat([bounded_01, bounded_delta], dim=1)


def make_neural_ode_model(
    *,
    state_dim: int,
    season_dim: int,
    hidden_dim: int,
    depth: int,
    dropout: float,
    derivative_scale: float,
    integration_time: float,
    ode_method: str,
    ode_step_size: float,
    rtol: float,
    atol: float,
) -> Any:
    torch = _require_torch()

    class NeuralODEDynamics(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers: list[Any] = []
            input_dim = state_dim + season_dim + 1
            for layer_index in range(depth):
                layers.append(torch.nn.Linear(input_dim if layer_index == 0 else hidden_dim, hidden_dim))
                layers.append(torch.nn.SiLU())
                if dropout > 0:
                    layers.append(torch.nn.Dropout(dropout))
            layers.append(torch.nn.Linear(hidden_dim if depth > 0 else input_dim, state_dim))
            self.net = torch.nn.Sequential(*layers)
            self.context: Any | None = None

        def set_context(self, context: Any) -> None:
            self.context = context

        def forward(self, t: Any, state: Any) -> Any:
            if self.context is None:
                raise RuntimeError("Neural ODE context was not set before integration")
            t_value = torch.as_tensor(t, device=state.device, dtype=state.dtype)
            t_column = torch.ones((state.shape[0], 1), device=state.device, dtype=state.dtype) * t_value
            raw_derivative = self.net(torch.cat([state, self.context, t_column], dim=1))
            return float(derivative_scale) * torch.tanh(raw_derivative)

    class PipeNeuralODEModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.dynamics = NeuralODEDynamics()
            self.logvar_head = torch.nn.Sequential(
                torch.nn.Linear(state_dim + season_dim, hidden_dim),
                torch.nn.SiLU(),
                torch.nn.Linear(hidden_dim, state_dim),
            )

        def _ode_options(self) -> dict[str, float] | None:
            if ode_step_size <= 0:
                return None
            if ode_method in {"euler", "midpoint", "rk4", "explicit_adams", "implicit_adams"}:
                return {"step_size": float(ode_step_size)}
            return None

        def forward(self, state: Any, season: Any) -> tuple[Any, Any]:
            odeint = _require_torchdiffeq().odeint
            initial_state = _bound_state_tensor(state)
            self.dynamics.set_context(season)
            times = torch.tensor([0.0, float(integration_time)], device=state.device, dtype=state.dtype)
            trajectory = odeint(
                self.dynamics,
                initial_state,
                times,
                method=ode_method,
                rtol=float(rtol),
                atol=float(atol),
                options=self._ode_options(),
            )
            mu = _bound_state_tensor(trajectory[-1])
            logvar = torch.clamp(self.logvar_head(torch.cat([mu, season], dim=1)), min=-10.0, max=2.0)
            return mu, logvar

    return PipeNeuralODEModel()


def prepare_transition_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ID_COLUMNS + INPUT_COLUMNS + TARGET_COLUMNS
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Sequence frame is missing required columns: {missing}")
    out = frame[columns].copy()
    for column in ["source_id", "site_id", "origin_year_month", "target_year_month", "split"]:
        out[column] = out[column].astype(str)
    numeric_columns = ["sequence_step"] + INPUT_COLUMNS + TARGET_COLUMNS
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    out[INPUT_COLUMNS] = out[INPUT_COLUMNS].fillna(0.0)
    out[TARGET_COLUMNS] = out[TARGET_COLUMNS].fillna(0.0)
    out["sequence_step"] = out["sequence_step"].astype("int64")
    return out.sort_values(["source_id", "site_id", "split", "sequence_step"]).reset_index(drop=True)


def eligible_transition_indices(frame: pd.DataFrame, split: str) -> np.ndarray:
    return frame.index[frame["split"] == split].to_numpy(dtype="int64")


def _season_features(month: int) -> dict[str, float]:
    radians = 2.0 * np.pi * (float(month) - 1.0) / 12.0
    return {
        "season_sin_annual": float(np.sin(radians)),
        "season_cos_annual": float(np.cos(radians)),
        "season_sin_semiannual": float(np.sin(2.0 * radians)),
        "season_cos_semiannual": float(np.cos(2.0 * radians)),
    }


def _advance_synthetic_state(state: np.ndarray, season: dict[str, float]) -> np.ndarray:
    seasonal_push = 0.025 * season["season_sin_annual"] - 0.015 * season["season_cos_semiannual"]
    derivative = np.zeros_like(state)
    derivative[0] = 0.08 * (0.55 - state[0]) + seasonal_push
    derivative[1] = 0.05 * (0.50 - state[1]) - 0.02 * state[0]
    derivative[2] = 0.10 * state[0] + 0.07 * (1.0 - state[1]) - 0.08 * state[2] + seasonal_push
    derivative[3] = 0.03 * (0.18 - state[3])
    derivative[4] = 0.03 * (0.16 - state[4])
    derivative[5] = 0.03 * (0.20 - state[5])
    derivative[6] = derivative[0]
    derivative[7] = derivative[1]
    derivative[8] = derivative[2]
    next_state = state + derivative
    next_state[:BOUNDED_01_COUNT] = np.clip(next_state[:BOUNDED_01_COUNT], 0.0, 1.0)
    next_state[BOUNDED_01_COUNT:] = np.clip(next_state[BOUNDED_01_COUNT:], -1.0, 1.0)
    return next_state.astype("float32")


def synthetic_sequence_frame(*, sites_per_split: int, months_per_split: int, seed: int) -> pd.DataFrame:
    if sites_per_split < 1:
        raise ValueError("--synthetic-sites must be >= 1")
    if months_per_split < 3:
        raise ValueError("--synthetic-months-per-split must be >= 3")
    rng = np.random.default_rng(seed)
    split_starts: dict[str, Any] = {
        "train": pd.Period("2010-01", freq="M"),
        "validation": pd.Period("2018-01", freq="M"),
        "test": pd.Period("2022-01", freq="M"),
    }
    rows: list[dict[str, Any]] = []
    for split, start_period in split_starts.items():
        for site_index in range(sites_per_split):
            state = rng.uniform(0.15, 0.75, size=len(PIPE_STATE_COLUMNS)).astype("float32")
            state[3:6] = rng.uniform(0.08, 0.28, size=3).astype("float32")
            state[6:] = rng.uniform(-0.08, 0.08, size=3).astype("float32")
            for step in range(months_per_split):
                origin_period = start_period + step
                target_period = origin_period + 1
                season = _season_features(origin_period.month)
                target = _advance_synthetic_state(state, season)
                record: dict[str, Any] = {
                    "source_id": "synthetic",
                    "site_id": f"{split}_site_{site_index:03d}",
                    "sequence_step": step,
                    "origin_year_month": str(origin_period),
                    "target_year_month": str(target_period),
                    "split": split,
                }
                for column_index, column in enumerate(PIPE_STATE_COLUMNS):
                    record[f"x_{column}"] = float(state[column_index])
                    record[f"target_{column}"] = float(target[column_index])
                record.update(season)
                rows.append(record)
                state = target
    return prepare_transition_frame(pd.DataFrame(rows))


def apply_output_blend(mu: Any, state_batch: Any, blend_weights: Any | None) -> Any:
    if blend_weights is None:
        return mu
    return state_batch + blend_weights * (mu - state_batch)


def training_loss(mu: Any, logvar: Any, target: Any, weights: Any, mse_weight: float) -> Any:
    nll = gaussian_nll(mu, logvar, target, weights)
    if mse_weight <= 0:
        return nll
    mse = (((target - mu) ** 2) * weights).mean()
    return nll + float(mse_weight) * mse


def train_epoch(
    model: Any,
    dataset: TransitionDataset,
    args: argparse.Namespace,
    optimizer: Any,
    weights: Any,
    device: Any,
    epoch: int,
) -> float:
    torch = _require_torch()
    model.train()
    total_loss = 0.0
    total_rows = 0
    loader = _data_loader(dataset, batch_size=args.batch_size, shuffle=True, seed=args.random_seed + epoch)
    for batch_index, (state_batch, season_batch, target_batch) in enumerate(loader, start=1):
        state_batch = state_batch.to(device=device, dtype=weights.dtype)
        season_batch = season_batch.to(device=device, dtype=weights.dtype)
        target_batch = target_batch.to(device=device, dtype=weights.dtype)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(state_batch, season_batch)
        loss = training_loss(mu, logvar, target_batch, weights, args.mse_weight)
        loss.backward()
        if args.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()
        rows = int(len(target_batch))
        total_loss += float(loss.item()) * rows
        total_rows += rows
        if args.progress_every_batches and batch_index % args.progress_every_batches == 0:
            print(f"epoch {epoch}: batch {batch_index}; rows={total_rows:,}; loss={total_loss / total_rows:.5f}", flush=True)
    return total_loss / max(total_rows, 1)


def select_output_blend_weights(
    model: Any,
    dataset: TransitionDataset,
    *,
    batch_size: int,
    grid: list[float],
    selection_metric: str,
    device: Any,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    torch = _require_torch()
    model.eval()
    grid_tensor = torch.tensor(grid, device=device, dtype=torch.float32)
    target_dim = len(TARGET_COLUMNS)
    sum_abs = torch.zeros((target_dim, len(grid)), device=device, dtype=torch.float64)
    sum_squared = torch.zeros((target_dim, len(grid)), device=device, dtype=torch.float64)
    total_rows = 0
    loader = _data_loader(dataset, batch_size=batch_size, shuffle=False, seed=0)
    with torch.no_grad():
        for state_batch, season_batch, target_batch in loader:
            state_batch = state_batch.to(device=device, dtype=torch.float32)
            season_batch = season_batch.to(device=device, dtype=torch.float32)
            target_batch = target_batch.to(device=device, dtype=torch.float32)
            mu, _ = model(state_batch, season_batch)
            candidates = state_batch[:, :, None] + (mu - state_batch)[:, :, None] * grid_tensor[None, None, :]
            error = candidates - target_batch[:, :, None]
            sum_abs += error.abs().sum(dim=0).double()
            sum_squared += (error**2).sum(dim=0).double()
            total_rows += int(len(target_batch))
    search_rows = []
    for target_index, target in enumerate(STATE_TARGET_NAMES):
        mae_values = (sum_abs[target_index] / max(total_rows, 1)).detach().cpu().numpy()
        rmse_values = torch.sqrt(sum_squared[target_index] / max(total_rows, 1)).detach().cpu().numpy()
        mae_min = max(float(np.min(mae_values)), 1e-12)
        rmse_min = max(float(np.min(rmse_values)), 1e-12)
        objective_values = {
            "mae": mae_values,
            "rmse": rmse_values,
            "balanced": 0.5 * (mae_values / mae_min) + 0.5 * (rmse_values / rmse_min),
        }[selection_metric]
        for grid_index, blend_weight in enumerate(grid):
            search_rows.append(
                {
                    "target": target,
                    "blend_weight": float(blend_weight),
                    "validation_rows": int(total_rows),
                    "validation_mae": float(mae_values[grid_index]),
                    "validation_rmse": float(rmse_values[grid_index]),
                    "selection_metric": selection_metric,
                    "selection_objective": float(objective_values[grid_index]),
                }
            )
    search = pd.DataFrame(search_rows)
    selected_rows = []
    for target, group in search.groupby("target", sort=False):
        best = group.sort_values(
            ["selection_objective", "validation_mae", "validation_rmse", "blend_weight"],
            ascending=[True, True, True, True],
        ).iloc[0]
        selected_rows.append(
            {
                "target": target,
                "blend_weight": float(best.blend_weight),
                "validation_rows": int(best.validation_rows),
                "validation_mae": float(best.validation_mae),
                "validation_rmse": float(best.validation_rmse),
                "selection_metric": selection_metric,
                "selection_objective": float(best.selection_objective),
            }
        )
    selected = pd.DataFrame(selected_rows)
    return selected, search.sort_values(["target", "blend_weight"]).reset_index(drop=True)


def _blend_weight_tensor(blend_weights: pd.DataFrame | None, device: Any) -> Any | None:
    if blend_weights is None or blend_weights.empty:
        return None
    torch = _require_torch()
    mapping = dict(zip(blend_weights["target"], blend_weights["blend_weight"], strict=True))
    values = [float(mapping[target]) for target in STATE_TARGET_NAMES]
    return torch.tensor(values, device=device, dtype=torch.float32)


def evaluate_model(
    model: Any,
    dataset: TransitionDataset,
    *,
    batch_size: int,
    weights: Any,
    device: Any,
    blend_weights: Any | None = None,
) -> tuple[pd.DataFrame, float]:
    torch = _require_torch()
    model.eval()
    target_dim = len(TARGET_COLUMNS)
    sum_squared = np.zeros(target_dim, dtype="float64")
    sum_abs = np.zeros(target_dim, dtype="float64")
    sum_nll = np.zeros(target_dim, dtype="float64")
    sum_width = np.zeros(target_dim, dtype="float64")
    coverage = np.zeros(target_dim, dtype="float64")
    total_rows = 0
    total_loss = 0.0
    loader = _data_loader(dataset, batch_size=batch_size, shuffle=False, seed=0)
    with torch.no_grad():
        for state_batch, season_batch, target_batch in loader:
            state_batch = state_batch.to(device=device, dtype=weights.dtype)
            season_batch = season_batch.to(device=device, dtype=weights.dtype)
            target_batch = target_batch.to(device=device, dtype=weights.dtype)
            mu, logvar = model(state_batch, season_batch)
            mu = apply_output_blend(mu, state_batch, blend_weights)
            loss = gaussian_nll(mu, logvar, target_batch, weights)
            variance = torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))
            sigma = torch.sqrt(variance)
            lower = mu - 1.6448536269514722 * sigma
            upper = mu + 1.6448536269514722 * sigma
            error = mu - target_batch
            nll_by_value = 0.5 * (torch.clamp(logvar, min=-10.0, max=2.0) + (error**2) / variance)
            rows = int(len(target_batch))
            total_loss += float(loss.item()) * rows
            total_rows += rows
            sum_squared += (error.detach().cpu().numpy() ** 2).sum(axis=0)
            sum_abs += np.abs(error.detach().cpu().numpy()).sum(axis=0)
            sum_nll += nll_by_value.detach().cpu().numpy().sum(axis=0)
            sum_width += (upper - lower).detach().cpu().numpy().sum(axis=0)
            coverage += ((target_batch >= lower) & (target_batch <= upper)).detach().cpu().numpy().sum(axis=0)

    rows = []
    for index, target in enumerate(TARGET_COLUMNS):
        rows.append(
            {
                "target": target.removeprefix("target_"),
                "rows": int(total_rows),
                "rmse": math.sqrt(sum_squared[index] / max(total_rows, 1)),
                "mae": sum_abs[index] / max(total_rows, 1),
                "nll": sum_nll[index] / max(total_rows, 1),
                "interval_90_coverage": coverage[index] / max(total_rows, 1),
                "interval_90_mean_width": sum_width[index] / max(total_rows, 1),
            }
        )
    metrics = pd.DataFrame(rows)
    overall = {
        "target": "all",
        "rows": int(total_rows),
        "rmse": float(metrics["rmse"].mean()),
        "mae": float(metrics["mae"].mean()),
        "nll": float(metrics["nll"].mean()),
        "interval_90_coverage": float(metrics["interval_90_coverage"].mean()),
        "interval_90_mean_width": float(metrics["interval_90_mean_width"].mean()),
    }
    metrics = pd.concat([pd.DataFrame([overall]), metrics], ignore_index=True)
    return metrics, total_loss / max(total_rows, 1)


def prediction_examples(
    model: Any,
    frame: pd.DataFrame,
    dataset: TransitionDataset,
    indices: np.ndarray,
    *,
    batch_size: int,
    max_examples: int,
    device: Any,
    blend_weights: Any | None = None,
) -> pd.DataFrame:
    if max_examples <= 0 or len(indices) == 0:
        return pd.DataFrame()
    torch = _require_torch()
    selected = indices[:max_examples]
    subset_dataset = TransitionDataset(dataset.state_values, dataset.season_values, dataset.target_values, selected)
    loader = _data_loader(subset_dataset, batch_size=batch_size, shuffle=False, seed=0)
    rows = []
    offset = 0
    model.eval()
    with torch.no_grad():
        for state_batch, season_batch, target_batch in loader:
            state_batch = state_batch.to(device=device, dtype=torch.float32)
            season_batch = season_batch.to(device=device, dtype=torch.float32)
            mu, logvar = model(state_batch, season_batch)
            mu = apply_output_blend(mu, state_batch, blend_weights)
            sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))).detach().cpu().numpy()
            mu_np = mu.detach().cpu().numpy()
            y_np = target_batch.detach().cpu().numpy()
            for batch_row in range(len(y_np)):
                frame_row = frame.loc[int(selected[offset + batch_row])]
                record: dict[str, Any] = {
                    "source_id": frame_row["source_id"],
                    "site_id": frame_row["site_id"],
                    "split": frame_row["split"],
                    "origin_year_month": frame_row["origin_year_month"],
                    "target_year_month": frame_row["target_year_month"],
                }
                for target_index, target in enumerate(STATE_TARGET_NAMES):
                    record[f"actual_{target}"] = float(y_np[batch_row, target_index])
                    record[f"predicted_mu_{target}"] = float(mu_np[batch_row, target_index])
                    record[f"predicted_sigma_{target}"] = float(sigma[batch_row, target_index])
                rows.append(record)
            offset += len(y_np)
    return pd.DataFrame(rows)


def save_checkpoint(
    *,
    args: argparse.Namespace,
    model: Any,
    optimizer: Any,
    epoch: int,
    best_validation_loss: float,
    best_validation_objective: float,
    history: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    torch = _require_torch()
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = args.checkpoint.with_suffix(args.checkpoint.suffix + ".tmp")
    torch.save(
        {
            "model_version": MODEL_VERSION,
            "epoch": int(epoch),
            "best_validation_loss": float(best_validation_loss),
            "best_validation_objective": float(best_validation_objective),
            "history": history,
            "config": config,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        tmp_path,
    )
    tmp_path.replace(args.checkpoint)


def save_model_artifact(
    *,
    args: argparse.Namespace,
    model: Any,
    best_epoch: int,
    best_validation_loss: float,
    best_validation_objective: float,
    config: dict[str, Any],
    output_blend_weights: dict[str, float] | None = None,
) -> None:
    torch = _require_torch()
    args.model.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = args.model.with_suffix(args.model.suffix + ".tmp")
    torch.save(
        {
            "model_version": MODEL_VERSION,
            "best_epoch": int(best_epoch),
            "best_validation_loss": float(best_validation_loss),
            "best_validation_objective": float(best_validation_objective),
            "config": config,
            "input_columns": INPUT_COLUMNS,
            "state_input_columns": STATE_INPUT_COLUMNS,
            "season_columns": SEASON_COLUMNS,
            "target_columns": TARGET_COLUMNS,
            "target_weights": TARGET_WEIGHTS,
            "output_blend_weights": output_blend_weights or {},
            "model_state_dict": model.state_dict(),
        },
        tmp_path,
    )
    tmp_path.replace(args.model)


def load_checkpoint_if_requested(
    args: argparse.Namespace, model: Any, optimizer: Any
) -> tuple[int, float, float, list[dict[str, Any]]]:
    if not args.resume:
        return 0, float("inf"), float("inf"), []
    if not args.checkpoint.exists():
        print(f"resume requested but checkpoint does not exist: {args.checkpoint}", flush=True)
        return 0, float("inf"), float("inf"), []
    torch = _require_torch()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    checkpoint_config = checkpoint.get("config", {})
    expected_config = model_config(args)
    mismatches = [
        key
        for key, expected in expected_config.items()
        if key not in checkpoint_config or checkpoint_config[key] != expected
    ]
    if mismatches:
        raise ValueError(
            "Checkpoint config is incompatible with current arguments; "
            f"mismatched keys: {mismatches}. Run without --resume to start a fresh training run."
        )
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    start_epoch = int(checkpoint["epoch"])
    best_validation_loss = float(checkpoint.get("best_validation_loss", float("inf")))
    best_validation_objective = float(checkpoint.get("best_validation_objective", best_validation_loss))
    history = list(checkpoint.get("history", []))
    print(
        f"resuming from epoch {start_epoch}; best_validation_loss={best_validation_loss:.5f}; "
        f"best_validation_objective={best_validation_objective:.5f}",
        flush=True,
    )
    return start_epoch, best_validation_loss, best_validation_objective, history


def model_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "state_dim": len(STATE_INPUT_COLUMNS),
        "season_dim": len(SEASON_COLUMNS),
        "hidden_dim": int(args.hidden_dim),
        "depth": int(args.depth),
        "dropout": float(args.dropout),
        "derivative_scale": float(args.derivative_scale),
        "integration_time": float(args.integration_time),
        "ode_method": args.ode_method,
        "ode_step_size": float(args.ode_step_size),
        "rtol": float(args.rtol),
        "atol": float(args.atol),
        "mse_weight": float(args.mse_weight),
        "checkpoint_selection_metric": args.checkpoint_selection_metric,
        "checkpoint_selection_uses_output_blend": True,
        "blend_selection_metric": args.blend_selection_metric,
        "blend_grid": _parse_float_grid(args.blend_grid),
        "target_weights": TARGET_WEIGHTS,
        "input_columns": INPUT_COLUMNS,
        "target_columns": TARGET_COLUMNS,
    }


def write_report(
    *,
    args: argparse.Namespace,
    status: str,
    metrics: pd.DataFrame,
    blend_weights: pd.DataFrame,
    comparison: pd.DataFrame,
    history: pd.DataFrame,
    available_windows: dict[str, int],
    sampled_windows: dict[str, int],
    started_at: datetime,
) -> None:
    best_sort_column = "validation_selection_objective" if "validation_selection_objective" in history.columns else "validation_loss"
    best_row = history.sort_values([best_sort_column, "epoch"]).iloc[0] if not history.empty else None
    lines = [
        "# PIPE Neural ODE Training Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This step trains a probabilistic Neural ODE variant over the frozen PIPE sequence schema.",
        "It models the monthly transition with a learned continuous-time derivative `dS/dt = f_theta(S, season, t)`.",
        "The v0 runner is one-step only; recursive rollouts and alert calibration are downstream gates.",
        f"Synthetic smoke mode: `{bool(args.synthetic_smoke)}`.",
        "",
        "## Configuration",
        "",
        f"- Hidden dimension: `{args.hidden_dim}`",
        f"- Dynamics depth: `{args.depth}`",
        f"- Dropout: `{args.dropout}`",
        f"- Derivative scale: `{args.derivative_scale}`",
        f"- Integration time: `{args.integration_time}`",
        f"- ODE method: `{args.ode_method}`",
        f"- ODE step size: `{args.ode_step_size}`",
        f"- Auxiliary MSE weight: `{args.mse_weight}`",
        f"- Checkpoint selection metric: `{args.checkpoint_selection_metric}`",
        f"- Output blend selection metric: `{args.blend_selection_metric}`",
        f"- Epochs requested: `{args.epochs}`",
        f"- Batch size: `{args.batch_size}`",
        f"- Learning rate: `{args.learning_rate}`",
        f"- Device: `{args.device}`",
        "",
        "## Transitions",
        "",
        "| split | available | sampled/used |",
        "|---|---:|---:|",
    ]
    for split in ["train", "validation", "test"]:
        lines.append(
            f"| `{split}` | {_format_int(int(available_windows.get(split, 0)))} | "
            f"{_format_int(int(sampled_windows.get(split, 0)))} |"
        )
    if best_row is not None:
        lines.extend(
            [
                "",
                "## Best Epoch",
                "",
                f"- Epoch: `{int(best_row.epoch)}`",
                f"- Selection metric: `{args.checkpoint_selection_metric}`",
                f"- Selection objective: `{_format_float(float(getattr(best_row, best_sort_column)))}`",
                f"- Validation loss: `{_format_float(float(best_row.validation_loss))}`",
                f"- Validation RMSE all: `{_format_float(float(best_row.validation_rmse_all))}`",
                f"- Validation MAE all: `{_format_float(float(best_row.validation_mae_all))}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(metrics):
        lines.append(
            f"| `{row.split}` | `{row.target}` | {_format_int(int(row.rows))} | "
            f"{_format_float(float(row.rmse))} | {_format_float(float(row.mae))} | "
            f"{_format_float(float(row.nll))} | {_format_float(float(row.interval_90_coverage))} | "
            f"{_format_float(float(row.interval_90_mean_width))} |"
        )
    lines.extend(
        [
            "",
            "## Output Blend Weights",
            "",
            "`blend_weight = 0` means pure persistence; `1` means pure Neural ODE prediction.",
            f"Weights are selected on validation `{args.blend_selection_metric}` per target.",
            "",
            "| target | blend weight | validation MAE | validation RMSE | objective |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    if blend_weights.empty:
        lines.append("| `NA` | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(blend_weights):
            lines.append(
                f"| `{row.target}` | {_format_float(float(row.blend_weight))} | "
                f"{_format_float(float(row.validation_mae))} | {_format_float(float(row.validation_rmse))} | "
                f"{_format_float(float(row.selection_objective))} |"
            )
    lines.extend(
        [
            "",
            "## Persistence Comparison",
            "",
            "Positive relative improvement means PIPE Neural ODE beats the one-step persistence baseline.",
            "",
            "| split | target | Neural ODE RMSE | persistence RMSE | RMSE rel improvement | Neural ODE MAE | persistence MAE | MAE rel improvement |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    comparison_rows = comparison[comparison["target"] == "all"] if not comparison.empty else comparison
    if comparison_rows.empty:
        lines.append("| `NA` | `NA` | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(comparison_rows):
            lines.append(
                f"| `{row.split}` | `{row.target}` | {_format_float(float(row.pipe_rmse))} | "
                f"{_format_float(float(row.persistence_rmse))} | "
                f"{_format_float(float(row.rmse_relative_improvement))} | "
                f"{_format_float(float(row.pipe_mae))} | {_format_float(float(row.persistence_mae))} | "
                f"{_format_float(float(row.mae_relative_improvement))} |"
            )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Model: `{args.model}`",
            f"- Checkpoint: `{args.checkpoint}`",
            f"- Metrics: `{args.metrics}`",
            f"- Persistence metrics: `{args.persistence_metrics}`",
            f"- Persistence comparison: `{args.comparison}`",
            f"- Output blend weights: `{args.blend_weights}`",
            f"- Output blend search: `{args.blend_search}`",
            f"- Training curve: `{args.training_curve}`",
            f"- Prediction examples: `{args.examples}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    status: str,
    metrics: pd.DataFrame,
    blend_weights: pd.DataFrame,
    blend_search: pd.DataFrame,
    persistence_metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    history: pd.DataFrame,
    available_windows: dict[str, int],
    sampled_windows: dict[str, int],
    started_at: datetime,
) -> dict[str, Any]:
    best_sort_column = "validation_selection_objective" if "validation_selection_objective" in history.columns else "validation_loss"
    best_row = history.sort_values([best_sort_column, "epoch"]).iloc[0].to_dict() if not history.empty else {}
    outputs = [
        args.model,
        args.checkpoint,
        args.metrics,
        args.persistence_metrics,
        args.comparison,
        args.blend_weights,
        args.blend_search,
        args.training_curve,
        args.examples,
        args.report,
    ]
    output_records = [_file_record(path) for path in outputs if path.exists()]
    input_records = []
    if args.synthetic_smoke:
        input_scope = {"synthetic_smoke": True}
    else:
        input_records.append(_file_record(args.sequences))
        if args.sequence_manifest.exists():
            input_records.append(_file_record(args.sequence_manifest))
        input_scope = {"synthetic_smoke": False}
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "model_version": MODEL_VERSION,
        "status": status,
        "scope": input_scope,
        "config": model_config(args)
        | {
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "learning_rate": float(args.learning_rate),
            "weight_decay": float(args.weight_decay),
            "random_seed": int(args.random_seed),
            "max_rows": args.max_rows,
            "max_train_windows": args.max_train_windows,
            "max_eval_windows": args.max_eval_windows,
            "synthetic_sites": int(args.synthetic_sites),
            "synthetic_months_per_split": int(args.synthetic_months_per_split),
        },
        "row_counts": {
            "available_transitions": available_windows,
            "sampled_transitions": sampled_windows,
            "metric_rows": int(len(metrics)),
            "blend_weight_rows": int(len(blend_weights)),
            "blend_search_rows": int(len(blend_search)),
            "persistence_metric_rows": int(len(persistence_metrics)),
            "comparison_rows": int(len(comparison)),
            "training_curve_rows": int(len(history)),
        },
        "selection": {
            "checkpoint_selection_metric": args.checkpoint_selection_metric,
            "best_epoch": int(best_row["epoch"]) if best_row else None,
            "best_validation_loss": float(best_row["validation_loss"]) if best_row else None,
            "best_validation_rmse_all": float(best_row.get("validation_rmse_all", np.nan)) if best_row else None,
            "best_validation_mae_all": float(best_row.get("validation_mae_all", np.nan)) if best_row else None,
            "best_validation_objective": float(best_row.get(best_sort_column, np.nan)) if best_row else None,
        },
        "inputs": input_records,
        "outputs": output_records,
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train probabilistic PIPE Neural ODE one-step model.")
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--sequence-manifest", type=Path, default=DEFAULT_SEQUENCE_MANIFEST)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--persistence-metrics", type=Path, default=DEFAULT_PERSISTENCE_METRICS)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--blend-weights", type=Path, default=DEFAULT_BLEND_WEIGHTS)
    parser.add_argument("--blend-search", type=Path, default=DEFAULT_BLEND_SEARCH)
    parser.add_argument("--training-curve", type=Path, default=DEFAULT_TRAINING_CURVE)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--synthetic-smoke", action="store_true")
    parser.add_argument("--synthetic-sites", type=int, default=16)
    parser.add_argument("--synthetic-months-per-split", type=int, default=24)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--derivative-scale", type=float, default=0.25)
    parser.add_argument("--integration-time", type=float, default=1.0)
    parser.add_argument("--ode-method", choices=["euler", "midpoint", "rk4", "dopri5", "explicit_adams", "implicit_adams"], default="rk4")
    parser.add_argument("--ode-step-size", type=float, default=0.25)
    parser.add_argument("--rtol", type=float, default=1e-3)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--mse-weight", type=float, default=0.5)
    parser.add_argument("--checkpoint-selection-metric", choices=["nll", "rmse", "mae", "balanced"], default="balanced")
    parser.add_argument("--blend-selection-metric", choices=["mae", "rmse", "balanced"], default="balanced")
    parser.add_argument("--blend-grid", default="0,0.1,0.2,0.35,0.5,0.65,0.8,0.9,1")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--max-train-windows", type=int, default=300_000)
    parser.add_argument("--max-eval-windows", type=int, default=150_000)
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--progress-every-batches", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    if args.depth < 0:
        raise ValueError("--depth must be >= 0")
    if args.derivative_scale <= 0:
        raise ValueError("--derivative-scale must be > 0")
    if args.integration_time <= 0:
        raise ValueError("--integration-time must be > 0")
    blend_grid = _parse_float_grid(args.blend_grid)

    _require_torchdiffeq()
    torch = _require_torch()
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    set_reproducible_seed(args.random_seed)
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)

    if args.synthetic_smoke:
        print("building synthetic Neural ODE smoke dataset", flush=True)
        frame = synthetic_sequence_frame(
            sites_per_split=args.synthetic_sites,
            months_per_split=args.synthetic_months_per_split,
            seed=args.random_seed,
        )
    else:
        print(f"loading sequences {args.sequences}", flush=True)
        frame = load_sequences(args.sequences, max_rows=args.max_rows)
        frame = prepare_transition_frame(frame)
    print(f"transition rows={len(frame):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    state_values = frame[STATE_INPUT_COLUMNS].to_numpy(dtype="float32")
    season_values = frame[SEASON_COLUMNS].to_numpy(dtype="float32")
    target_values = frame[TARGET_COLUMNS].to_numpy(dtype="float32")

    available_indices = {split: eligible_transition_indices(frame, split) for split in ["train", "validation", "test"]}
    sampled_indices = {
        "train": sample_indices(available_indices["train"], args.max_train_windows, args.random_seed),
        "validation": sample_indices(available_indices["validation"], args.max_eval_windows, args.random_seed + 1),
        "test": sample_indices(available_indices["test"], args.max_eval_windows, args.random_seed + 2),
    }
    available_windows = {split: int(len(indices)) for split, indices in available_indices.items()}
    sampled_windows = {split: int(len(indices)) for split, indices in sampled_indices.items()}
    print(f"available transitions={available_windows}", flush=True)
    print(f"sampled transitions={sampled_windows}", flush=True)
    if sampled_windows["train"] == 0 or sampled_windows["validation"] == 0:
        raise ValueError("Training and validation splits must each have at least one eligible transition")
    persistence_metrics = evaluate_persistence(frame, sampled_indices)

    datasets = {
        split: TransitionDataset(state_values, season_values, target_values, indices)
        for split, indices in sampled_indices.items()
    }
    model = make_neural_ode_model(
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        hidden_dim=args.hidden_dim,
        depth=args.depth,
        dropout=args.dropout,
        derivative_scale=args.derivative_scale,
        integration_time=args.integration_time,
        ode_method=args.ode_method,
        ode_step_size=args.ode_step_size,
        rtol=args.rtol,
        atol=args.atol,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    weights = torch.from_numpy(make_loss_weights()).to(device=device, dtype=torch.float32)
    config = model_config(args)

    start_epoch, best_validation_loss, best_validation_objective, history_rows = load_checkpoint_if_requested(
        args, model, optimizer
    )
    best_epoch = start_epoch
    if history_rows:
        best_history_row = min(
            history_rows,
            key=lambda row: float(row.get("validation_selection_objective", row.get("validation_loss", float("inf")))),
        )
        best_epoch = int(best_history_row.get("epoch", start_epoch))
    status = "completed"
    try:
        for epoch in range(start_epoch + 1, args.epochs + 1):
            epoch_started = time.monotonic()
            print(f"epoch {epoch}/{args.epochs}: training", flush=True)
            train_loss = train_epoch(model, datasets["train"], args, optimizer, weights, device, epoch)
            epoch_blend_weights, _ = select_output_blend_weights(
                model,
                datasets["validation"],
                batch_size=args.batch_size,
                grid=blend_grid,
                selection_metric=args.blend_selection_metric,
                device=device,
            )
            epoch_blend_tensor = _blend_weight_tensor(epoch_blend_weights, device)
            validation_metrics, validation_loss = evaluate_model(
                model,
                datasets["validation"],
                batch_size=args.batch_size,
                weights=weights,
                device=device,
                blend_weights=epoch_blend_tensor,
            )
            validation_objective = validation_selection_objective(
                validation_metrics,
                validation_loss,
                persistence_metrics,
                args.checkpoint_selection_metric,
            )
            if validation_objective < best_validation_objective:
                best_validation_loss = validation_loss
                best_validation_objective = validation_objective
                best_epoch = epoch
                save_model_artifact(
                    args=args,
                    model=model,
                    best_epoch=best_epoch,
                    best_validation_loss=best_validation_loss,
                    best_validation_objective=best_validation_objective,
                    config=config,
                )
            validation_all = validation_metrics[validation_metrics["target"] == "all"].iloc[0]
            row = {
                "epoch": int(epoch),
                "train_loss": float(train_loss),
                "validation_loss": float(validation_loss),
                "validation_rmse_all": float(validation_all.rmse),
                "validation_mae_all": float(validation_all.mae),
                "validation_selection_objective": float(validation_objective),
                "validation_blend_selection_metric": args.blend_selection_metric,
                "epoch_seconds": float(time.monotonic() - epoch_started),
                "best_validation_loss": float(best_validation_loss),
                "best_validation_objective": float(best_validation_objective),
            }
            history_rows.append(row)
            save_checkpoint(
                args=args,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                best_validation_loss=best_validation_loss,
                best_validation_objective=best_validation_objective,
                history=history_rows,
                config=config,
            )
            print(
                f"epoch {epoch}: train_loss={train_loss:.5f}; validation_loss={validation_loss:.5f}; "
                f"selection_objective={validation_objective:.5f}; elapsed={_elapsed(started_monotonic)}",
                flush=True,
            )
    except KeyboardInterrupt:
        status = "interrupted"
        print("interrupted; last completed epoch checkpoint is preserved", flush=True)

    if not args.model.exists():
        save_model_artifact(
            args=args,
            model=model,
            best_epoch=best_epoch,
            best_validation_loss=best_validation_loss,
            best_validation_objective=best_validation_objective,
            config=config,
        )
    else:
        best_artifact = torch.load(args.model, map_location=device, weights_only=False)
        model.load_state_dict(best_artifact["model_state_dict"])

    print("selecting output blend weights on validation", flush=True)
    blend_weights_frame, blend_search_frame = select_output_blend_weights(
        model,
        datasets["validation"],
        batch_size=args.batch_size,
        grid=blend_grid,
        selection_metric=args.blend_selection_metric,
        device=device,
    )
    blend_weight_values = dict(zip(blend_weights_frame["target"], blend_weights_frame["blend_weight"], strict=True))
    save_model_artifact(
        args=args,
        model=model,
        best_epoch=best_epoch,
        best_validation_loss=best_validation_loss,
        best_validation_objective=best_validation_objective,
        config=config,
        output_blend_weights={key: float(value) for key, value in blend_weight_values.items()},
    )
    blend_weight_tensor = _blend_weight_tensor(blend_weights_frame, device)
    metrics_frames = []
    for split in ["train", "validation", "test"]:
        if len(datasets[split]) == 0:
            continue
        print(f"evaluating {split}", flush=True)
        metrics, _ = evaluate_model(
            model,
            datasets[split],
            batch_size=args.batch_size,
            weights=weights,
            device=device,
            blend_weights=blend_weight_tensor,
        )
        metrics.insert(0, "split", split)
        metrics_frames.append(metrics)
    metrics_frame = pd.concat(metrics_frames, ignore_index=True) if metrics_frames else pd.DataFrame()
    comparison = compare_to_persistence(metrics_frame, persistence_metrics)
    history_frame = pd.DataFrame(history_rows)
    examples = prediction_examples(
        model,
        frame,
        datasets["test"] if len(datasets["test"]) else datasets["validation"],
        sampled_indices["test"] if len(sampled_indices["test"]) else sampled_indices["validation"],
        batch_size=args.batch_size,
        max_examples=args.max_examples,
        device=device,
        blend_weights=blend_weight_tensor,
    )

    _write_csv_atomic(metrics_frame, args.metrics)
    print(f"wrote {args.metrics}", flush=True)
    _write_csv_atomic(blend_weights_frame, args.blend_weights)
    print(f"wrote {args.blend_weights}", flush=True)
    _write_csv_atomic(blend_search_frame, args.blend_search)
    print(f"wrote {args.blend_search}", flush=True)
    _write_csv_atomic(persistence_metrics, args.persistence_metrics)
    print(f"wrote {args.persistence_metrics}", flush=True)
    _write_csv_atomic(comparison, args.comparison)
    print(f"wrote {args.comparison}", flush=True)
    _write_csv_atomic(history_frame, args.training_curve)
    print(f"wrote {args.training_curve}", flush=True)
    _write_csv_atomic(examples, args.examples)
    print(f"wrote {args.examples}", flush=True)
    write_report(
        args=args,
        status=status,
        metrics=metrics_frame,
        blend_weights=blend_weights_frame,
        comparison=comparison,
        history=history_frame,
        available_windows=available_windows,
        sampled_windows=sampled_windows,
        started_at=started_at,
    )
    print(f"wrote {args.report}", flush=True)
    manifest = manifest_payload(
        args=args,
        status=status,
        metrics=metrics_frame,
        blend_weights=blend_weights_frame,
        blend_search=blend_search_frame,
        persistence_metrics=persistence_metrics,
        comparison=comparison,
        history=history_frame,
        available_windows=available_windows,
        sampled_windows=sampled_windows,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}", flush=True)
    print(f"done; elapsed={_elapsed(started_monotonic)}", flush=True)


if __name__ == "__main__":
    main()
