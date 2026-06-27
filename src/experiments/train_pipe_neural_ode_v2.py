#!/usr/bin/env python
"""Train a continuous-time multi-gap PIPE Neural ODE v2 state model."""

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

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, SEASON_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import (
    STATE_TARGET_NAMES,
    TARGET_WEIGHTS,
    _blend_weight_tensor,
    _elapsed,
    _file_record,
    _format_float,
    _format_int,
    _parse_float_grid,
    _require_torch,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
    make_loss_weights,
    prepare_window_frame,
    set_reproducible_seed,
    training_loss,
)
from src.experiments.train_pipe_neural_ode import (
    STATE_INPUT_COLUMNS,
    _bound_state_tensor,
    _require_torchdiffeq,
    synthetic_sequence_frame,
)
from src.experiments.train_pipe_neural_ode_v1 import (
    CONTEXT_FILL_VALUES,
    context_columns_label,
    input_columns_for_context,
    load_history_sequences,
    resolve_context_columns,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_SEQUENCE_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json")
DEFAULT_MODELS_DIR = Path("models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2")
DEFAULT_REPORT_DIR = Path("reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2")
DEFAULT_MODEL = DEFAULT_MODELS_DIR / "pipe_neural_ode_continuous_model_v2.pt"
DEFAULT_CHECKPOINT = DEFAULT_MODELS_DIR / "pipe_neural_ode_continuous_checkpoint_v2.pt"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_metrics.csv"
DEFAULT_PERSISTENCE_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_persistence_metrics.csv"
DEFAULT_COMPARISON = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_persistence_comparison.csv"
DEFAULT_BLEND_WEIGHTS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_output_blend_weights.csv"
DEFAULT_BLEND_SEARCH = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_output_blend_search.csv"
DEFAULT_TRAINING_CURVE = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_training_curve.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_prediction_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_manifest.json"

MODEL_VERSION = "pipe_neural_ode_continuous_v2"


def parse_horizons(value: str) -> list[int]:
    horizons = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    if not horizons or horizons[0] < 1:
        raise ValueError("Forecast horizons must be positive integers")
    return horizons


def _origin_month_positions(frame: pd.DataFrame) -> np.ndarray:
    periods = pd.PeriodIndex(frame["origin_year_month"].astype(str), freq="M")
    months = np.asarray([period.month for period in periods], dtype="float32")
    return (months - 1.0).astype("float32")


def _torch_season_features(month_position: Any) -> Any:
    torch = _require_torch()
    radians = 2.0 * math.pi * month_position / 12.0
    return torch.stack(
        [
            torch.sin(radians),
            torch.cos(radians),
            torch.sin(2.0 * radians),
            torch.cos(2.0 * radians),
        ],
        dim=1,
    )


def add_synthetic_context_columns(frame: pd.DataFrame, context_columns: list[str]) -> pd.DataFrame:
    if not context_columns:
        return frame
    out = frame.copy()
    for column in context_columns:
        out[column] = float(CONTEXT_FILL_VALUES.get(column, 0.0))
    return out


def eligible_continuous_time_examples(
    frame: pd.DataFrame,
    *,
    split: str,
    history_length: int,
    horizons: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    if history_length < 1:
        raise ValueError("history_length must be >= 1")
    if not horizons:
        raise ValueError("At least one forecast horizon is required")
    mask = (frame["split"] == split) & (frame["window_position"] >= history_length - 1)
    candidates = frame.index[mask].to_numpy(dtype="int64")
    run_ids = frame["window_run_id"].to_numpy(dtype="int64")
    positions = frame["window_position"].to_numpy(dtype="int64")
    last_frame_index = len(frame) - 1
    end_indices: list[int] = []
    gaps: list[int] = []
    for index in candidates:
        index_int = int(index)
        for horizon in horizons:
            target_index = index_int + int(horizon) - 1
            if target_index > last_frame_index:
                continue
            if run_ids[target_index] != run_ids[index_int]:
                continue
            if positions[target_index] != positions[index_int] + int(horizon) - 1:
                continue
            end_indices.append(index_int)
            gaps.append(int(horizon))
    return np.asarray(end_indices, dtype="int64"), np.asarray(gaps, dtype="int64")


def sample_examples(
    end_indices: np.ndarray,
    gaps: np.ndarray,
    max_examples: int | None,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if len(end_indices) != len(gaps):
        raise ValueError("end_indices and gaps must have the same length")
    if max_examples is None or max_examples <= 0 or len(end_indices) <= max_examples:
        return end_indices, gaps
    rng = np.random.default_rng(seed)
    selected = np.sort(rng.choice(np.arange(len(end_indices)), size=int(max_examples), replace=False))
    return end_indices[selected].astype("int64"), gaps[selected].astype("int64")


class ContinuousTimeWindowDataset:
    def __init__(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        origin_month_values: np.ndarray,
        end_indices: np.ndarray,
        gaps: np.ndarray,
        history_length: int,
    ) -> None:
        if len(end_indices) != len(gaps):
            raise ValueError("end_indices and gaps must have the same length")
        self.x_values = x_values
        self.y_values = y_values
        self.origin_month_values = origin_month_values
        self.end_indices = end_indices.astype("int64")
        self.gaps = gaps.astype("int64")
        self.history_length = int(history_length)

    def __len__(self) -> int:
        return int(len(self.end_indices))

    def __getitem__(self, item: int) -> tuple[Any, Any, Any, Any, Any]:
        torch = _require_torch()
        end_index = int(self.end_indices[item])
        gap = int(self.gaps[item])
        start_index = end_index - self.history_length + 1
        target_index = end_index + gap - 1
        x_window = self.x_values[start_index : end_index + 1]
        y_target = self.y_values[target_index]
        dt = np.asarray(float(gap), dtype="float32")
        origin_month = np.asarray(float(self.origin_month_values[end_index]), dtype="float32")
        return (
            torch.from_numpy(x_window),
            torch.from_numpy(y_target),
            torch.from_numpy(dt),
            torch.from_numpy(origin_month),
            torch.tensor(gap, dtype=torch.int64),
        )


def continuous_time_data_loader(
    dataset: ContinuousTimeWindowDataset,
    *,
    batch_size: int,
    shuffle: bool,
    seed: int,
) -> Any:
    torch = _require_torch()
    generator = torch.Generator()
    generator.manual_seed(seed)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, generator=generator)


def make_continuous_time_neural_ode_model(
    *,
    input_dim: int,
    state_dim: int,
    season_dim: int,
    context_dim: int,
    history_hidden_dim: int,
    history_layers: int,
    latent_dim: int,
    dynamics_hidden_dim: int,
    dynamics_depth: int,
    dropout: float,
    derivative_scale: float,
    state_delta_scale: float,
    ode_method: str,
    ode_step_size: float,
    rtol: float,
    atol: float,
) -> Any:
    torch = _require_torch()

    class ContinuousLatentDynamics(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers: list[Any] = []
            dynamic_context_dim = history_hidden_dim + context_dim + season_dim + 1
            layer_input_dim = latent_dim + dynamic_context_dim
            for layer_index in range(dynamics_depth):
                in_dim = layer_input_dim if layer_index == 0 else dynamics_hidden_dim
                layers.append(torch.nn.Linear(in_dim, dynamics_hidden_dim))
                layers.append(torch.nn.SiLU())
                if dropout > 0:
                    layers.append(torch.nn.Dropout(dropout))
            layers.append(torch.nn.Linear(dynamics_hidden_dim if dynamics_depth > 0 else layer_input_dim, latent_dim))
            self.net = torch.nn.Sequential(*layers)
            self.history_context: Any | None = None
            self.extra_context: Any | None = None
            self.origin_month: Any | None = None

        def set_context(self, *, history_context: Any, extra_context: Any, origin_month: Any) -> None:
            self.history_context = history_context
            self.extra_context = extra_context
            self.origin_month = origin_month

        def forward(self, t: Any, latent: Any) -> Any:
            if self.history_context is None or self.extra_context is None or self.origin_month is None:
                raise RuntimeError("Continuous Neural ODE context was not set before integration")
            t_value = torch.as_tensor(t, device=latent.device, dtype=latent.dtype)
            t_column = torch.ones((latent.shape[0], 1), device=latent.device, dtype=latent.dtype) * t_value
            season = _torch_season_features(self.origin_month + t_value)
            raw_derivative = self.net(
                torch.cat([latent, self.history_context, self.extra_context, season, t_column], dim=1)
            )
            return float(derivative_scale) * torch.tanh(raw_derivative)

    class PipeContinuousTimeNeuralODEModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = torch.nn.GRU(
                input_size=input_dim,
                hidden_size=history_hidden_dim,
                num_layers=history_layers,
                batch_first=True,
                dropout=dropout if history_layers > 1 else 0.0,
            )
            self.latent_initial = torch.nn.Sequential(
                torch.nn.Linear(history_hidden_dim + state_dim + season_dim + context_dim, latent_dim),
                torch.nn.Tanh(),
            )
            self.dynamics = ContinuousLatentDynamics()
            decoder_input_dim = latent_dim + history_hidden_dim + state_dim + season_dim + context_dim + 1
            self.delta_head = torch.nn.Sequential(
                torch.nn.Linear(decoder_input_dim, dynamics_hidden_dim),
                torch.nn.SiLU(),
                torch.nn.Linear(dynamics_hidden_dim, state_dim),
            )
            self.logvar_head = torch.nn.Sequential(
                torch.nn.Linear(decoder_input_dim, dynamics_hidden_dim),
                torch.nn.SiLU(),
                torch.nn.Linear(dynamics_hidden_dim, state_dim),
            )

        def _ode_options(self) -> dict[str, float] | None:
            if ode_step_size <= 0:
                return None
            if ode_method in {"euler", "midpoint", "rk4", "explicit_adams", "implicit_adams"}:
                return {"step_size": float(ode_step_size)}
            return None

        def forward(self, x_window: Any, dt: Any, origin_month: Any) -> tuple[Any, Any]:
            _, hidden = self.encoder(x_window)
            history_context = hidden[-1]
            last_input = x_window[:, -1, :]
            last_state = _bound_state_tensor(last_input[:, :state_dim])
            origin_season = last_input[:, state_dim : state_dim + season_dim]
            if context_dim > 0:
                extra_context = last_input[:, state_dim + season_dim : state_dim + season_dim + context_dim]
            else:
                extra_context = last_input.new_zeros((last_input.shape[0], 0))
            latent0 = self.latent_initial(torch.cat([history_context, last_state, origin_season, extra_context], dim=1))

            mu = last_state.new_zeros(last_state.shape)
            logvar = last_state.new_zeros(last_state.shape)
            dt = dt.to(device=x_window.device, dtype=x_window.dtype).view(-1)
            origin_month = origin_month.to(device=x_window.device, dtype=x_window.dtype).view(-1)
            for dt_value in torch.unique(dt):
                mask = dt == dt_value
                if not bool(mask.any()):
                    continue
                latent0_subset = latent0[mask]
                history_subset = history_context[mask]
                context_subset = extra_context[mask]
                month_subset = origin_month[mask]
                self.dynamics.set_context(
                    history_context=history_subset,
                    extra_context=context_subset,
                    origin_month=month_subset,
                )
                times = torch.stack(
                    [
                        torch.zeros((), device=x_window.device, dtype=x_window.dtype),
                        dt_value.to(device=x_window.device, dtype=x_window.dtype),
                    ]
                )
                trajectory = _require_torchdiffeq().odeint(
                    self.dynamics,
                    latent0_subset,
                    times,
                    method=ode_method,
                    rtol=float(rtol),
                    atol=float(atol),
                    options=self._ode_options(),
                )
                latent_dt = trajectory[-1]
                target_season = _torch_season_features(month_subset + dt_value)
                dt_column = torch.ones((latent_dt.shape[0], 1), device=x_window.device, dtype=x_window.dtype) * dt_value
                decoder_input = torch.cat(
                    [latent_dt, history_subset, last_state[mask], target_season, context_subset, dt_column],
                    dim=1,
                )
                delta = float(state_delta_scale) * dt_column * torch.tanh(self.delta_head(decoder_input))
                mu[mask] = _bound_state_tensor(last_state[mask] + delta)
                logvar[mask] = torch.clamp(self.logvar_head(decoder_input), min=-10.0, max=2.0)
            return mu, logvar

    return PipeContinuousTimeNeuralODEModel()


def differentiable_irc(state: Any, *, alpha: float, beta: float, gamma: float) -> Any:
    return (float(alpha) * state[:, 0] + float(beta) * (1.0 - state[:, 1]) + float(gamma) * state[:, 2]) / (
        float(alpha) + float(beta) + float(gamma)
    )


def continuous_time_training_loss(mu: Any, logvar: Any, target: Any, weights: Any, args: argparse.Namespace) -> Any:
    loss = training_loss(mu, logvar, target, weights, args.mse_weight)
    if args.irc_loss_weight <= 0:
        return loss
    predicted_irc = differentiable_irc(mu, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
    target_irc = differentiable_irc(target, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
    return loss + float(args.irc_loss_weight) * ((predicted_irc - target_irc) ** 2).mean()


def apply_output_blend_v2(mu: Any, x_batch: Any, blend_weights: Any | None) -> Any:
    if blend_weights is None:
        return mu
    persistence = x_batch[:, -1, : len(TARGET_COLUMNS)]
    return persistence + blend_weights * (mu - persistence)


def _metric_rows_from_accumulators(
    *,
    horizon: int,
    total_rows: int,
    sum_squared: np.ndarray,
    sum_abs: np.ndarray,
    sum_nll: np.ndarray,
    sum_width: np.ndarray,
    coverage: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(TARGET_COLUMNS):
        rows.append(
            {
                "horizon_months": int(horizon),
                "target": target.removeprefix("target_"),
                "rows": int(total_rows),
                "rmse": math.sqrt(sum_squared[index] / max(total_rows, 1)),
                "mae": sum_abs[index] / max(total_rows, 1),
                "nll": sum_nll[index] / max(total_rows, 1),
                "interval_90_coverage": coverage[index] / max(total_rows, 1),
                "interval_90_mean_width": sum_width[index] / max(total_rows, 1),
            }
        )
    target_rows = pd.DataFrame(rows)
    rows.insert(
        0,
        {
            "horizon_months": int(horizon),
            "target": "all",
            "rows": int(total_rows),
            "rmse": float(target_rows["rmse"].mean()),
            "mae": float(target_rows["mae"].mean()),
            "nll": float(target_rows["nll"].mean()),
            "interval_90_coverage": float(target_rows["interval_90_coverage"].mean()),
            "interval_90_mean_width": float(target_rows["interval_90_mean_width"].mean()),
        },
    )
    return rows


def evaluate_continuous_time_model(
    model: Any,
    dataset: ContinuousTimeWindowDataset,
    *,
    batch_size: int,
    weights: Any,
    device: Any,
    args: argparse.Namespace,
    blend_weights: Any | None = None,
) -> tuple[pd.DataFrame, float]:
    torch = _require_torch()
    model.eval()
    target_dim = len(TARGET_COLUMNS)
    accumulators: dict[int, dict[str, Any]] = {}
    total_loss = 0.0
    total_rows = 0
    loader = continuous_time_data_loader(dataset, batch_size=batch_size, shuffle=False, seed=0)
    with torch.no_grad():
        for x_batch, y_batch, dt_batch, origin_month_batch, gap_batch in loader:
            x_batch = x_batch.to(device=device, dtype=weights.dtype)
            y_batch = y_batch.to(device=device, dtype=weights.dtype)
            dt_batch = dt_batch.to(device=device, dtype=weights.dtype)
            origin_month_batch = origin_month_batch.to(device=device, dtype=weights.dtype)
            mu, logvar = model(x_batch, dt_batch, origin_month_batch)
            mu = apply_output_blend_v2(mu, x_batch, blend_weights)
            loss = continuous_time_training_loss(mu, logvar, y_batch, weights, args)
            variance = torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))
            sigma = torch.sqrt(variance)
            lower = mu - 1.6448536269514722 * sigma
            upper = mu + 1.6448536269514722 * sigma
            error = mu - y_batch
            nll_by_value = 0.5 * (torch.clamp(logvar, min=-10.0, max=2.0) + (error**2) / variance)
            rows = int(len(y_batch))
            total_loss += float(loss.item()) * rows
            total_rows += rows
            gap_np = gap_batch.detach().cpu().numpy().astype("int64")
            error_np = error.detach().cpu().numpy()
            abs_np = np.abs(error_np)
            nll_np = nll_by_value.detach().cpu().numpy()
            width_np = (upper - lower).detach().cpu().numpy()
            coverage_np = ((y_batch >= lower) & (y_batch <= upper)).detach().cpu().numpy()
            for horizon in sorted(set(gap_np.tolist())):
                mask = gap_np == horizon
                if int(mask.sum()) == 0:
                    continue
                acc = accumulators.setdefault(
                    int(horizon),
                    {
                        "rows": 0,
                        "sum_squared": np.zeros(target_dim, dtype="float64"),
                        "sum_abs": np.zeros(target_dim, dtype="float64"),
                        "sum_nll": np.zeros(target_dim, dtype="float64"),
                        "sum_width": np.zeros(target_dim, dtype="float64"),
                        "coverage": np.zeros(target_dim, dtype="float64"),
                    },
                )
                acc["rows"] += int(mask.sum())
                acc["sum_squared"] += (error_np[mask] ** 2).sum(axis=0)
                acc["sum_abs"] += abs_np[mask].sum(axis=0)
                acc["sum_nll"] += nll_np[mask].sum(axis=0)
                acc["sum_width"] += width_np[mask].sum(axis=0)
                acc["coverage"] += coverage_np[mask].sum(axis=0)

    rows_out: list[dict[str, Any]] = []
    aggregate = {
        "rows": 0,
        "sum_squared": np.zeros(target_dim, dtype="float64"),
        "sum_abs": np.zeros(target_dim, dtype="float64"),
        "sum_nll": np.zeros(target_dim, dtype="float64"),
        "sum_width": np.zeros(target_dim, dtype="float64"),
        "coverage": np.zeros(target_dim, dtype="float64"),
    }
    for horizon, acc in sorted(accumulators.items()):
        rows_out.extend(
            _metric_rows_from_accumulators(
                horizon=horizon,
                total_rows=int(acc["rows"]),
                sum_squared=acc["sum_squared"],
                sum_abs=acc["sum_abs"],
                sum_nll=acc["sum_nll"],
                sum_width=acc["sum_width"],
                coverage=acc["coverage"],
            )
        )
        for key in ["sum_squared", "sum_abs", "sum_nll", "sum_width", "coverage"]:
            aggregate[key] += acc[key]
        aggregate["rows"] += int(acc["rows"])
    rows_out.extend(
        _metric_rows_from_accumulators(
            horizon=0,
            total_rows=int(aggregate["rows"]),
            sum_squared=aggregate["sum_squared"],
            sum_abs=aggregate["sum_abs"],
            sum_nll=aggregate["sum_nll"],
            sum_width=aggregate["sum_width"],
            coverage=aggregate["coverage"],
        )
    )
    return pd.DataFrame(rows_out), total_loss / max(total_rows, 1)


def evaluate_persistence(dataset: ContinuousTimeWindowDataset) -> pd.DataFrame:
    target_dim = len(TARGET_COLUMNS)
    rows_out: list[dict[str, Any]] = []
    accumulators: dict[int, dict[str, Any]] = {}
    for end_index, gap in zip(dataset.end_indices, dataset.gaps, strict=True):
        target_index = int(end_index) + int(gap) - 1
        prediction = dataset.x_values[int(end_index), :target_dim].astype("float64")
        target = dataset.y_values[target_index].astype("float64")
        error = prediction - target
        acc = accumulators.setdefault(
            int(gap),
            {
                "rows": 0,
                "sum_squared": np.zeros(target_dim, dtype="float64"),
                "sum_abs": np.zeros(target_dim, dtype="float64"),
            },
        )
        acc["rows"] += 1
        acc["sum_squared"] += error**2
        acc["sum_abs"] += np.abs(error)
    aggregate = {
        "rows": 0,
        "sum_squared": np.zeros(target_dim, dtype="float64"),
        "sum_abs": np.zeros(target_dim, dtype="float64"),
    }
    for horizon, acc in sorted(accumulators.items()):
        rmse_values = np.sqrt(acc["sum_squared"] / max(int(acc["rows"]), 1))
        mae_values = acc["sum_abs"] / max(int(acc["rows"]), 1)
        rows_out.append(
            {
                "horizon_months": int(horizon),
                "target": "all",
                "rows": int(acc["rows"]),
                "rmse": float(rmse_values.mean()),
                "mae": float(mae_values.mean()),
            }
        )
        for index, target_name in enumerate(STATE_TARGET_NAMES):
            rows_out.append(
                {
                    "horizon_months": int(horizon),
                    "target": target_name,
                    "rows": int(acc["rows"]),
                    "rmse": float(rmse_values[index]),
                    "mae": float(mae_values[index]),
                }
            )
        aggregate["rows"] += int(acc["rows"])
        aggregate["sum_squared"] += acc["sum_squared"]
        aggregate["sum_abs"] += acc["sum_abs"]
    rmse_values = np.sqrt(aggregate["sum_squared"] / max(int(aggregate["rows"]), 1))
    mae_values = aggregate["sum_abs"] / max(int(aggregate["rows"]), 1)
    rows_out.append(
        {
            "horizon_months": 0,
            "target": "all",
            "rows": int(aggregate["rows"]),
            "rmse": float(rmse_values.mean()),
            "mae": float(mae_values.mean()),
        }
    )
    for index, target_name in enumerate(STATE_TARGET_NAMES):
        rows_out.append(
            {
                "horizon_months": 0,
                "target": target_name,
                "rows": int(aggregate["rows"]),
                "rmse": float(rmse_values[index]),
                "mae": float(mae_values[index]),
            }
        )
    return pd.DataFrame(rows_out)


def compare_to_persistence(pipe_metrics: pd.DataFrame, persistence_metrics: pd.DataFrame) -> pd.DataFrame:
    pipe = pipe_metrics[["split", "horizon_months", "target", "rows", "rmse", "mae"]].rename(
        columns={"rows": "pipe_rows", "rmse": "pipe_rmse", "mae": "pipe_mae"}
    )
    persistence = persistence_metrics.rename(
        columns={"rows": "persistence_rows", "rmse": "persistence_rmse", "mae": "persistence_mae"}
    )
    out = pipe.merge(persistence, on=["split", "horizon_months", "target"], how="inner")
    out["rmse_delta_pipe_minus_persistence"] = out["pipe_rmse"] - out["persistence_rmse"]
    out["mae_delta_pipe_minus_persistence"] = out["pipe_mae"] - out["persistence_mae"]
    out["rmse_relative_improvement"] = np.where(
        out["persistence_rmse"] > 0,
        (out["persistence_rmse"] - out["pipe_rmse"]) / out["persistence_rmse"],
        0.0,
    )
    out["mae_relative_improvement"] = np.where(
        out["persistence_mae"] > 0,
        (out["persistence_mae"] - out["pipe_mae"]) / out["persistence_mae"],
        0.0,
    )
    return out.sort_values(["split", "horizon_months", "target"]).reset_index(drop=True)


def selection_objective(
    *,
    validation_metrics: pd.DataFrame,
    validation_loss: float,
    persistence_metrics: pd.DataFrame,
    selection_metric: str,
) -> float:
    if selection_metric == "nll":
        return float(validation_loss)
    current = validation_metrics[
        (validation_metrics["horizon_months"] == 0) & (validation_metrics["target"] == "all")
    ].iloc[0]
    if selection_metric == "rmse":
        return float(current.rmse)
    if selection_metric == "mae":
        return float(current.mae)
    if selection_metric != "balanced":
        raise ValueError(f"Unsupported checkpoint selection metric: {selection_metric}")
    persistence = persistence_metrics[
        (persistence_metrics["horizon_months"] == 0) & (persistence_metrics["target"] == "all")
    ].iloc[0]
    rmse_scale = max(float(persistence.rmse), 1e-12)
    mae_scale = max(float(persistence.mae), 1e-12)
    return 0.5 * (float(current.rmse) / rmse_scale) + 0.5 * (float(current.mae) / mae_scale)


def select_output_blend_weights(
    model: Any,
    dataset: ContinuousTimeWindowDataset,
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
    loader = continuous_time_data_loader(dataset, batch_size=batch_size, shuffle=False, seed=0)
    with torch.no_grad():
        for x_batch, y_batch, dt_batch, origin_month_batch, _gap_batch in loader:
            x_batch = x_batch.to(device=device, dtype=torch.float32)
            y_batch = y_batch.to(device=device, dtype=torch.float32)
            dt_batch = dt_batch.to(device=device, dtype=torch.float32)
            origin_month_batch = origin_month_batch.to(device=device, dtype=torch.float32)
            mu, _ = model(x_batch, dt_batch, origin_month_batch)
            persistence = x_batch[:, -1, :target_dim]
            candidates = persistence[:, :, None] + (mu - persistence)[:, :, None] * grid_tensor[None, None, :]
            error = candidates - y_batch[:, :, None]
            sum_abs += error.abs().sum(dim=0).double()
            sum_squared += (error**2).sum(dim=0).double()
            total_rows += int(len(y_batch))
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


def prediction_examples(
    model: Any,
    frame: pd.DataFrame,
    dataset: ContinuousTimeWindowDataset,
    *,
    batch_size: int,
    max_examples: int,
    device: Any,
    blend_weights: Any | None = None,
) -> pd.DataFrame:
    if max_examples <= 0 or len(dataset) == 0:
        return pd.DataFrame()
    torch = _require_torch()
    selected_positions = np.arange(min(max_examples, len(dataset)), dtype="int64")
    selected_dataset = ContinuousTimeWindowDataset(
        dataset.x_values,
        dataset.y_values,
        dataset.origin_month_values,
        dataset.end_indices[selected_positions],
        dataset.gaps[selected_positions],
        dataset.history_length,
    )
    loader = continuous_time_data_loader(selected_dataset, batch_size=batch_size, shuffle=False, seed=0)
    rows = []
    offset = 0
    model.eval()
    with torch.no_grad():
        for x_batch, y_batch, dt_batch, origin_month_batch, gap_batch in loader:
            x_batch = x_batch.to(device=device, dtype=torch.float32)
            dt_batch = dt_batch.to(device=device, dtype=torch.float32)
            origin_month_batch = origin_month_batch.to(device=device, dtype=torch.float32)
            mu, logvar = model(x_batch, dt_batch, origin_month_batch)
            mu = apply_output_blend_v2(mu, x_batch, blend_weights)
            sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))).detach().cpu().numpy()
            mu_np = mu.detach().cpu().numpy()
            y_np = y_batch.detach().cpu().numpy()
            gap_np = gap_batch.detach().cpu().numpy().astype("int64")
            for batch_row in range(len(y_np)):
                dataset_position = int(selected_positions[offset + batch_row])
                end_index = int(dataset.end_indices[dataset_position])
                gap = int(gap_np[batch_row])
                target_index = end_index + gap - 1
                origin_row = frame.loc[end_index]
                target_row = frame.loc[target_index]
                record: dict[str, Any] = {
                    "source_id": origin_row["source_id"],
                    "site_id": origin_row["site_id"],
                    "split": origin_row["split"],
                    "origin_year_month": origin_row["origin_year_month"],
                    "target_year_month": target_row["target_year_month"],
                    "horizon_months": gap,
                }
                for target_index_col, target in enumerate(STATE_TARGET_NAMES):
                    record[f"actual_{target}"] = float(y_np[batch_row, target_index_col])
                    record[f"predicted_mu_{target}"] = float(mu_np[batch_row, target_index_col])
                    record[f"predicted_sigma_{target}"] = float(sigma[batch_row, target_index_col])
                rows.append(record)
            offset += len(y_np)
    return pd.DataFrame(rows)


def train_epoch(
    model: Any,
    dataset: ContinuousTimeWindowDataset,
    args: argparse.Namespace,
    optimizer: Any,
    weights: Any,
    device: Any,
    epoch: int,
) -> float:
    torch = _require_torch()
    model.train()
    loader = continuous_time_data_loader(dataset, batch_size=args.batch_size, shuffle=True, seed=args.random_seed + epoch)
    total_loss = 0.0
    total_rows = 0
    for batch_index, (x_batch, y_batch, dt_batch, origin_month_batch, _gap_batch) in enumerate(loader, start=1):
        x_batch = x_batch.to(device=device, dtype=weights.dtype)
        y_batch = y_batch.to(device=device, dtype=weights.dtype)
        dt_batch = dt_batch.to(device=device, dtype=weights.dtype)
        origin_month_batch = origin_month_batch.to(device=device, dtype=weights.dtype)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(x_batch, dt_batch, origin_month_batch)
        loss = continuous_time_training_loss(mu, logvar, y_batch, weights, args)
        loss.backward()
        if args.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(args.grad_clip))
        optimizer.step()
        rows = int(len(y_batch))
        total_loss += float(loss.item()) * rows
        total_rows += rows
        if args.progress_every_batches and batch_index % args.progress_every_batches == 0:
            print(f"  batch {batch_index}: loss={float(loss.item()):.5f}", flush=True)
    return total_loss / max(total_rows, 1)


def model_config(args: argparse.Namespace) -> dict[str, Any]:
    horizons = parse_horizons(args.forecast_horizons)
    context_columns = resolve_context_columns(args.context_columns)
    input_columns = input_columns_for_context(context_columns)
    return {
        "architecture": "history_encoder_continuous_time_latent_ode",
        "history_length": int(args.history_length),
        "forecast_horizons": horizons,
        "input_dim": len(input_columns),
        "state_dim": len(STATE_INPUT_COLUMNS),
        "season_dim": len(SEASON_COLUMNS),
        "context_dim": len(context_columns),
        "context_columns": context_columns,
        "history_hidden_dim": int(args.history_hidden_dim),
        "history_layers": int(args.history_layers),
        "latent_dim": int(args.latent_dim),
        "dynamics_hidden_dim": int(args.dynamics_hidden_dim),
        "dynamics_depth": int(args.dynamics_depth),
        "dropout": float(args.dropout),
        "derivative_scale": float(args.derivative_scale),
        "state_delta_scale": float(args.state_delta_scale),
        "ode_method": args.ode_method,
        "ode_step_size": float(args.ode_step_size),
        "rtol": float(args.rtol),
        "atol": float(args.atol),
        "mse_weight": float(args.mse_weight),
        "irc_loss_weight": float(args.irc_loss_weight),
        "irc_alpha": float(args.irc_alpha),
        "irc_beta": float(args.irc_beta),
        "irc_gamma": float(args.irc_gamma),
        "checkpoint_selection_metric": args.checkpoint_selection_metric,
        "checkpoint_selection_uses_output_blend": True,
        "blend_selection_metric": args.blend_selection_metric,
        "blend_grid": _parse_float_grid(args.blend_grid),
        "target_weights": TARGET_WEIGHTS,
        "input_columns": input_columns,
        "state_input_columns": STATE_INPUT_COLUMNS,
        "season_columns": SEASON_COLUMNS,
        "target_columns": TARGET_COLUMNS,
    }


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
            "input_columns": list(config.get("input_columns", INPUT_COLUMNS)),
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


def write_report(
    *,
    args: argparse.Namespace,
    status: str,
    metrics: pd.DataFrame,
    blend_weights: pd.DataFrame,
    comparison: pd.DataFrame,
    history: pd.DataFrame,
    available_examples: dict[str, int],
    sampled_examples: dict[str, int],
    started_at: datetime,
) -> None:
    best_sort_column = "validation_selection_objective" if "validation_selection_objective" in history.columns else "validation_loss"
    best_row = history.sort_values([best_sort_column, "epoch"]).iloc[0] if not history.empty else None
    lines = [
        "# PIPE Neural ODE Continuous-Time Training Report v2",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This step trains a structurally separate continuous-time Neural ODE v2.",
        "It encodes PIPE history once, then trains direct h-month targets by integrating the latent ODE for the requested `dt`.",
        "Seasonal forcing is evaluated as a continuous function of integration time rather than fixed to one monthly step.",
        f"Synthetic smoke mode: `{bool(args.synthetic_smoke)}`.",
        "",
        "## Configuration",
        "",
        f"- History length: `{args.history_length}`",
        f"- Forecast horizons: `{parse_horizons(args.forecast_horizons)}`",
        f"- Context columns: `{context_columns_label(resolve_context_columns(args.context_columns))}`",
        f"- History hidden dimension: `{args.history_hidden_dim}`",
        f"- History layers: `{args.history_layers}`",
        f"- Latent dimension: `{args.latent_dim}`",
        f"- Dynamics hidden dimension: `{args.dynamics_hidden_dim}`",
        f"- Dynamics depth: `{args.dynamics_depth}`",
        f"- Dropout: `{args.dropout}`",
        f"- Derivative scale: `{args.derivative_scale}`",
        f"- State delta scale per month: `{args.state_delta_scale}`",
        f"- ODE method: `{args.ode_method}`",
        f"- ODE step size: `{args.ode_step_size}`",
        f"- Auxiliary MSE weight: `{args.mse_weight}`",
        f"- Auxiliary IRC loss weight: `{args.irc_loss_weight}`",
        f"- Checkpoint selection metric: `{args.checkpoint_selection_metric}`",
        f"- Output blend selection metric: `{args.blend_selection_metric}`",
        f"- Epochs requested: `{args.epochs}`",
        f"- Batch size: `{args.batch_size}`",
        f"- Learning rate: `{args.learning_rate}`",
        f"- Device: `{args.device}`",
        "",
        "## Examples",
        "",
        "| split | available | sampled/used |",
        "|---|---:|---:|",
    ]
    for split in ["train", "validation", "test"]:
        lines.append(
            f"| `{split}` | {_format_int(int(available_examples.get(split, 0)))} | "
            f"{_format_int(int(sampled_examples.get(split, 0)))} |"
        )
    if best_row is not None:
        lines.extend(
            [
                "",
                "## Best Epoch",
                "",
                f"- Epoch: `{int(best_row.epoch)}`",
                f"- Selection objective: `{_format_float(float(getattr(best_row, best_sort_column)))}`",
                f"- Validation loss: `{_format_float(float(best_row.validation_loss))}`",
                f"- Validation RMSE all horizons: `{_format_float(float(best_row.validation_rmse_all_horizons))}`",
                f"- Validation MAE all horizons: `{_format_float(float(best_row.validation_mae_all_horizons))}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "`horizon_months = 0` is the aggregate over all requested direct horizons.",
            "",
            "| split | horizon | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(metrics.sort_values(["split", "horizon_months", "target"])):
        lines.append(
            f"| `{row.split}` | {int(row.horizon_months)} | `{row.target}` | {_format_int(int(row.rows))} | "
            f"{_format_float(float(row.rmse))} | {_format_float(float(row.mae))} | "
            f"{_format_float(float(row.nll))} | {_format_float(float(row.interval_90_coverage))} | "
            f"{_format_float(float(row.interval_90_mean_width))} |"
        )
    lines.extend(
        [
            "",
            "## Persistence Comparison",
            "",
            "| split | horizon | target | Neural ODE v2 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v2 MAE | persistence MAE | MAE rel improvement |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    comparison_rows = comparison[(comparison["target"] == "all") & (comparison["horizon_months"] == 0)]
    if comparison_rows.empty:
        lines.append("| `NA` | 0 | `NA` | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(comparison_rows.sort_values(["split", "horizon_months"])):
            lines.append(
                f"| `{row.split}` | {int(row.horizon_months)} | `{row.target}` | "
                f"{_format_float(float(row.pipe_rmse))} | {_format_float(float(row.persistence_rmse))} | "
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
    available_examples: dict[str, int],
    sampled_examples: dict[str, int],
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
            "max_train_examples": args.max_train_examples,
            "max_eval_examples": args.max_eval_examples,
            "synthetic_sites": int(args.synthetic_sites),
            "synthetic_months_per_split": int(args.synthetic_months_per_split),
        },
        "row_counts": {
            "available_examples": available_examples,
            "sampled_examples": sampled_examples,
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
            "best_validation_rmse_all_horizons": (
                float(best_row.get("validation_rmse_all_horizons", np.nan)) if best_row else None
            ),
            "best_validation_mae_all_horizons": (
                float(best_row.get("validation_mae_all_horizons", np.nan)) if best_row else None
            ),
            "best_validation_objective": float(best_row.get(best_sort_column, np.nan)) if best_row else None,
        },
        "inputs": input_records,
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--history-length", type=int, default=12)
    parser.add_argument("--forecast-horizons", default="1,2,3")
    parser.add_argument("--context-columns", default="none")
    parser.add_argument("--history-hidden-dim", type=int, default=128)
    parser.add_argument("--history-layers", type=int, default=1)
    parser.add_argument("--latent-dim", type=int, default=96)
    parser.add_argument("--dynamics-hidden-dim", type=int, default=128)
    parser.add_argument("--dynamics-depth", type=int, default=3)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--derivative-scale", type=float, default=0.5)
    parser.add_argument("--state-delta-scale", type=float, default=0.35)
    parser.add_argument(
        "--ode-method",
        choices=["euler", "midpoint", "rk4", "dopri5", "explicit_adams", "implicit_adams"],
        default="rk4",
    )
    parser.add_argument("--ode-step-size", type=float, default=0.25)
    parser.add_argument("--rtol", type=float, default=1e-3)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--mse-weight", type=float, default=0.5)
    parser.add_argument("--irc-loss-weight", type=float, default=0.0)
    parser.add_argument("--irc-alpha", type=float, default=0.5)
    parser.add_argument("--irc-beta", type=float, default=0.5)
    parser.add_argument("--irc-gamma", type=float, default=2.0)
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
    parser.add_argument("--max-train-examples", type=int, default=300_000)
    parser.add_argument("--max-eval-examples", type=int, default=150_000)
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--progress-every-batches", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons = parse_horizons(args.forecast_horizons)
    if args.history_length < 1:
        raise ValueError("--history-length must be >= 1")
    if args.history_layers < 1:
        raise ValueError("--history-layers must be >= 1")
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    if args.dynamics_depth < 0:
        raise ValueError("--dynamics-depth must be >= 0")
    if args.derivative_scale <= 0:
        raise ValueError("--derivative-scale must be > 0")
    if args.state_delta_scale <= 0:
        raise ValueError("--state-delta-scale must be > 0")
    if args.irc_loss_weight < 0:
        raise ValueError("--irc-loss-weight must be >= 0")
    if args.irc_alpha < 0 or args.irc_beta < 0 or args.irc_gamma < 0:
        raise ValueError("--irc-alpha, --irc-beta, and --irc-gamma must be >= 0")
    if args.irc_alpha + args.irc_beta + args.irc_gamma <= 0:
        raise ValueError("At least one IRC weight must be positive")
    context_columns = resolve_context_columns(args.context_columns)
    selected_input_columns = input_columns_for_context(context_columns)
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
        print("building synthetic Neural ODE v2 smoke dataset", flush=True)
        frame = synthetic_sequence_frame(
            sites_per_split=args.synthetic_sites,
            months_per_split=args.synthetic_months_per_split,
            seed=args.random_seed,
        )
        frame = add_synthetic_context_columns(frame, context_columns)
    else:
        print(f"loading sequences {args.sequences}", flush=True)
        frame = load_history_sequences(args.sequences, max_rows=args.max_rows, input_columns=selected_input_columns)
    frame = prepare_window_frame(frame)
    print(f"sequence rows={len(frame):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    x_values = frame[selected_input_columns].to_numpy(dtype="float32")
    y_values = frame[TARGET_COLUMNS].to_numpy(dtype="float32")
    origin_month_values = _origin_month_positions(frame)

    available_pairs = {
        split: eligible_continuous_time_examples(
            frame,
            split=split,
            history_length=args.history_length,
            horizons=horizons,
        )
        for split in ["train", "validation", "test"]
    }
    sampled_pairs = {
        "train": sample_examples(
            available_pairs["train"][0], available_pairs["train"][1], args.max_train_examples, args.random_seed
        ),
        "validation": sample_examples(
            available_pairs["validation"][0],
            available_pairs["validation"][1],
            args.max_eval_examples,
            args.random_seed + 1,
        ),
        "test": sample_examples(
            available_pairs["test"][0], available_pairs["test"][1], args.max_eval_examples, args.random_seed + 2
        ),
    }
    available_examples = {split: int(len(pairs[0])) for split, pairs in available_pairs.items()}
    sampled_examples = {split: int(len(pairs[0])) for split, pairs in sampled_pairs.items()}
    print(f"available examples={available_examples}", flush=True)
    print(f"sampled examples={sampled_examples}", flush=True)
    if sampled_examples["train"] == 0 or sampled_examples["validation"] == 0:
        raise ValueError("Training and validation splits must each have at least one eligible continuous-time example")

    datasets = {
        split: ContinuousTimeWindowDataset(
            x_values,
            y_values,
            origin_month_values,
            pairs[0],
            pairs[1],
            args.history_length,
        )
        for split, pairs in sampled_pairs.items()
    }
    persistence_frames = []
    for split in ["train", "validation", "test"]:
        persistence = evaluate_persistence(datasets[split])
        persistence.insert(0, "split", split)
        persistence_frames.append(persistence)
    persistence_metrics = pd.concat(persistence_frames, ignore_index=True)

    model = make_continuous_time_neural_ode_model(
        input_dim=len(selected_input_columns),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        context_dim=len(context_columns),
        history_hidden_dim=args.history_hidden_dim,
        history_layers=args.history_layers,
        latent_dim=args.latent_dim,
        dynamics_hidden_dim=args.dynamics_hidden_dim,
        dynamics_depth=args.dynamics_depth,
        dropout=args.dropout,
        derivative_scale=args.derivative_scale,
        state_delta_scale=args.state_delta_scale,
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
            validation_metrics, validation_loss = evaluate_continuous_time_model(
                model,
                datasets["validation"],
                batch_size=args.batch_size,
                weights=weights,
                device=device,
                args=args,
                blend_weights=epoch_blend_tensor,
            )
            validation_persistence = persistence_metrics[persistence_metrics["split"] == "validation"].drop(
                columns=["split"]
            )
            validation_objective = selection_objective(
                validation_metrics=validation_metrics,
                validation_loss=validation_loss,
                persistence_metrics=validation_persistence,
                selection_metric=args.checkpoint_selection_metric,
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
            validation_all = validation_metrics[
                (validation_metrics["horizon_months"] == 0) & (validation_metrics["target"] == "all")
            ].iloc[0]
            row = {
                "epoch": int(epoch),
                "train_loss": float(train_loss),
                "validation_loss": float(validation_loss),
                "validation_rmse_all_horizons": float(validation_all.rmse),
                "validation_mae_all_horizons": float(validation_all.mae),
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
        metrics, _ = evaluate_continuous_time_model(
            model,
            datasets[split],
            batch_size=args.batch_size,
            weights=weights,
            device=device,
            args=args,
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
        available_examples=available_examples,
        sampled_examples=sampled_examples,
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
        available_examples=available_examples,
        sampled_examples=sampled_examples,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}", flush=True)
    print(f"done; elapsed={_elapsed(started_monotonic)}", flush=True)


if __name__ == "__main__":
    main()
