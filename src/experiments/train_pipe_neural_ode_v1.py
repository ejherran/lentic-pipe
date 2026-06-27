#!/usr/bin/env python
"""Train a history-encoded probabilistic PIPE Neural ODE state model."""

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
    ID_COLUMNS,
    STATE_TARGET_NAMES,
    TARGET_WEIGHTS,
    WindowDataset,
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
    compare_to_persistence,
    eligible_window_indices,
    evaluate_persistence,
    load_sequences,
    make_loss_weights,
    prediction_examples,
    prepare_window_frame,
    sample_indices,
    select_output_blend_weights,
    set_reproducible_seed,
    training_loss,
    validation_selection_objective,
)
from src.experiments.train_pipe_neural_ode import (
    STATE_INPUT_COLUMNS,
    _bound_state_tensor,
    _require_torchdiffeq,
    synthetic_sequence_frame,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_SEQUENCE_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json")
DEFAULT_MODELS_DIR = Path("models/pipe_neural_ode/adaptive_wqp_focused_v1")
DEFAULT_REPORT_DIR = Path("reports/pipe_neural_ode/adaptive_wqp_focused_v1")
DEFAULT_MODEL = DEFAULT_MODELS_DIR / "pipe_neural_ode_history_model_v1.pt"
DEFAULT_CHECKPOINT = DEFAULT_MODELS_DIR / "pipe_neural_ode_history_checkpoint_v1.pt"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_metrics.csv"
DEFAULT_PERSISTENCE_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_persistence_metrics.csv"
DEFAULT_COMPARISON = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_persistence_comparison.csv"
DEFAULT_BLEND_WEIGHTS = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_output_blend_weights.csv"
DEFAULT_BLEND_SEARCH = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_output_blend_search.csv"
DEFAULT_TRAINING_CURVE = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_training_curve.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_prediction_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_neural_ode_history_manifest.json"

MODEL_VERSION = "pipe_neural_ode_history_v1"
EVIDENCE_CONTEXT_COLUMNS = [
    "x_evidence_N",
    "x_evidence_F",
    "x_evidence_T",
    "x_evidence_T_no_chla",
]
MISSINGNESS_CONTEXT_COLUMNS = [
    "x_missing_N",
    "x_missing_F",
    "x_missing_T",
    "x_missing_T_no_chla",
]
IRC_CONTEXT_COLUMNS = [
    "x_irc1",
    "x_irc1_no_chla",
]
ALL_CONTEXT_COLUMNS = EVIDENCE_CONTEXT_COLUMNS + MISSINGNESS_CONTEXT_COLUMNS + IRC_CONTEXT_COLUMNS
CONTEXT_COLUMN_GROUPS = {
    "none": [],
    "irc": IRC_CONTEXT_COLUMNS,
    "evidence": EVIDENCE_CONTEXT_COLUMNS,
    "missingness": MISSINGNESS_CONTEXT_COLUMNS,
    "evidence_missingness": EVIDENCE_CONTEXT_COLUMNS + MISSINGNESS_CONTEXT_COLUMNS,
}
CONTEXT_FILL_VALUES = {
    **{column: 1.0 for column in EVIDENCE_CONTEXT_COLUMNS},
    **{column: 0.0 for column in MISSINGNESS_CONTEXT_COLUMNS},
    **{column: 0.0 for column in IRC_CONTEXT_COLUMNS},
}
BACKWARD_COMPAT_CONFIG_DEFAULTS = {
    "context_dim": 0,
    "context_columns": [],
    "input_columns": INPUT_COLUMNS,
    "irc_loss_weight": 0.0,
    "irc_alpha": 0.5,
    "irc_beta": 0.5,
    "irc_gamma": 2.0,
}
MULTI_STEP_CONFIG_KEYS = {
    "training_objective",
    "multi_step_horizon",
    "multi_step_loss_weight",
    "multi_step_checkpoint_objective",
}


def resolve_context_columns(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    raw_tokens = [part.strip() for part in str(value).split(",") if part.strip()]
    if not raw_tokens:
        raw_tokens = ["none"]
    if "none" in raw_tokens and len(raw_tokens) > 1:
        raise ValueError("--context-columns cannot mix 'none' with other context groups")
    columns: list[str] = []
    for token in raw_tokens:
        if token in CONTEXT_COLUMN_GROUPS:
            columns.extend(CONTEXT_COLUMN_GROUPS[token])
        elif token in ALL_CONTEXT_COLUMNS:
            columns.append(token)
        else:
            valid = sorted(set(CONTEXT_COLUMN_GROUPS) | set(ALL_CONTEXT_COLUMNS))
            raise ValueError(f"Unsupported context column group or column {token!r}. Valid values: {valid}")
    return list(dict.fromkeys(columns))


def input_columns_for_context(context_columns: list[str]) -> list[str]:
    return INPUT_COLUMNS + list(context_columns)


def context_columns_label(context_columns: list[str]) -> str:
    if not context_columns:
        return "none"
    if context_columns == CONTEXT_COLUMN_GROUPS["irc"]:
        return "irc"
    if context_columns == CONTEXT_COLUMN_GROUPS["evidence"]:
        return "evidence"
    if context_columns == CONTEXT_COLUMN_GROUPS["missingness"]:
        return "missingness"
    if context_columns == CONTEXT_COLUMN_GROUPS["evidence_missingness"]:
        return "evidence,missingness"
    return ",".join(context_columns)


def _context_start() -> int:
    return len(STATE_INPUT_COLUMNS) + len(SEASON_COLUMNS)


def add_synthetic_context_columns(frame: pd.DataFrame, context_columns: list[str]) -> pd.DataFrame:
    if not context_columns:
        return frame
    out = frame.copy()
    for column in context_columns:
        out[column] = float(CONTEXT_FILL_VALUES[column])
    return out


def load_history_sequences(path: Path, *, max_rows: int | None, input_columns: list[str]) -> pd.DataFrame:
    frame = load_sequences(path, max_rows=max_rows)
    for column in ["source_id", "site_id", "origin_year_month", "target_year_month", "split"]:
        frame[column] = frame[column].astype(str)
    frame["sequence_step"] = pd.to_numeric(frame["sequence_step"], errors="coerce").astype("int64")
    extra_columns = [column for column in input_columns if column not in INPUT_COLUMNS]
    if extra_columns:
        try:
            extras = pd.read_parquet(path, columns=ID_COLUMNS + extra_columns)
        except Exception as exc:
            raise ValueError(
                "Sequence frame is missing one or more requested Neural ODE context columns: "
                f"{extra_columns}. The current adaptive WQP-focused sequence artifact exposes "
                "`x_irc1` and `x_irc1_no_chla`; use `--context-columns irc`, or regenerate the "
                "sequence dataset with evidence/missingness context before requesting those groups."
            ) from exc
        if max_rows:
            extras = extras.head(max_rows).copy()
        for column in ["source_id", "site_id", "origin_year_month", "target_year_month", "split"]:
            extras[column] = extras[column].astype(str)
        extras["sequence_step"] = pd.to_numeric(extras["sequence_step"], errors="coerce").astype("int64")
        frame = frame.merge(extras, on=ID_COLUMNS, how="left", validate="one_to_one")
    missing = [column for column in input_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Sequence frame is missing requested Neural ODE context columns: {missing}")
    for column in input_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        frame[column] = frame[column].fillna(float(CONTEXT_FILL_VALUES.get(column, 0.0)))
    return frame


def make_history_neural_ode_model(
    *,
    input_dim: int,
    state_dim: int,
    season_dim: int,
    context_dim: int = 0,
    history_hidden_dim: int,
    history_layers: int,
    latent_dim: int,
    dynamics_hidden_dim: int,
    dynamics_depth: int,
    dropout: float,
    derivative_scale: float,
    state_delta_scale: float,
    integration_time: float,
    ode_method: str,
    ode_step_size: float,
    rtol: float,
    atol: float,
) -> Any:
    torch = _require_torch()

    class LatentDynamics(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers: list[Any] = []
            ode_context_dim = history_hidden_dim + season_dim + context_dim
            layer_input_dim = latent_dim + ode_context_dim + 1
            for layer_index in range(dynamics_depth):
                in_dim = layer_input_dim if layer_index == 0 else dynamics_hidden_dim
                layers.append(torch.nn.Linear(in_dim, dynamics_hidden_dim))
                layers.append(torch.nn.SiLU())
                if dropout > 0:
                    layers.append(torch.nn.Dropout(dropout))
            layers.append(torch.nn.Linear(dynamics_hidden_dim if dynamics_depth > 0 else layer_input_dim, latent_dim))
            self.net = torch.nn.Sequential(*layers)
            self.context: Any | None = None

        def set_context(self, context: Any) -> None:
            self.context = context

        def forward(self, t: Any, latent: Any) -> Any:
            if self.context is None:
                raise RuntimeError("Latent ODE context was not set before integration")
            t_value = torch.as_tensor(t, device=latent.device, dtype=latent.dtype)
            t_column = torch.ones((latent.shape[0], 1), device=latent.device, dtype=latent.dtype) * t_value
            raw_derivative = self.net(torch.cat([latent, self.context, t_column], dim=1))
            return float(derivative_scale) * torch.tanh(raw_derivative)

    class PipeHistoryNeuralODEModel(torch.nn.Module):
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
            self.dynamics = LatentDynamics()
            decoder_input_dim = latent_dim + history_hidden_dim + state_dim + season_dim + context_dim
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

        def forward(self, x_window: Any) -> tuple[Any, Any]:
            _, hidden = self.encoder(x_window)
            history_context = hidden[-1]
            last_input = x_window[:, -1, :]
            last_state = _bound_state_tensor(last_input[:, :state_dim])
            season = last_input[:, state_dim : state_dim + season_dim]
            if context_dim > 0:
                extra_context = last_input[:, state_dim + season_dim : state_dim + season_dim + context_dim]
            else:
                extra_context = last_input.new_zeros((last_input.shape[0], 0))
            context = torch.cat([history_context, season, extra_context], dim=1)
            latent0 = self.latent_initial(torch.cat([history_context, last_state, season, extra_context], dim=1))
            self.dynamics.set_context(context)
            times = torch.tensor([0.0, float(integration_time)], device=x_window.device, dtype=x_window.dtype)
            trajectory = _require_torchdiffeq().odeint(
                self.dynamics,
                latent0,
                times,
                method=ode_method,
                rtol=float(rtol),
                atol=float(atol),
                options=self._ode_options(),
            )
            latent1 = trajectory[-1]
            decoder_input = torch.cat([latent1, history_context, last_state, season, extra_context], dim=1)
            delta = float(state_delta_scale) * torch.tanh(self.delta_head(decoder_input))
            mu = _bound_state_tensor(last_state + delta)
            logvar = torch.clamp(self.logvar_head(decoder_input), min=-10.0, max=2.0)
            return mu, logvar

    return PipeHistoryNeuralODEModel()


def model_config(args: argparse.Namespace) -> dict[str, Any]:
    context_columns = resolve_context_columns(args.context_columns)
    input_columns = input_columns_for_context(context_columns)
    return {
        "architecture": "history_encoder_latent_ode",
        "history_length": int(args.history_length),
        "training_objective": args.training_objective,
        "multi_step_horizon": int(args.multi_step_horizon),
        "multi_step_loss_weight": float(args.multi_step_loss_weight),
        "multi_step_checkpoint_objective": args.multi_step_checkpoint_objective,
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
        "integration_time": float(args.integration_time),
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


def checkpoint_selection_label(args: argparse.Namespace) -> str:
    if args.training_objective == "multi_step":
        if args.multi_step_checkpoint_objective == "one_step":
            return f"multi_step_one_step_{args.checkpoint_selection_metric}"
        return "multi_step_rollout_loss"
    return str(args.checkpoint_selection_metric)


def checkpoint_selection_objective(
    *,
    args: argparse.Namespace,
    validation_rollout_loss: float,
    validation_one_step_objective: float,
) -> float:
    if args.training_objective != "multi_step":
        return float(validation_one_step_objective)
    if args.multi_step_checkpoint_objective == "one_step":
        return float(validation_one_step_objective)
    return float(validation_rollout_loss)


def differentiable_irc(state: Any, *, alpha: float, beta: float, gamma: float) -> Any:
    return (float(alpha) * state[:, 0] + float(beta) * (1.0 - state[:, 1]) + float(gamma) * state[:, 2]) / (
        float(alpha) + float(beta) + float(gamma)
    )


def history_training_loss(mu: Any, logvar: Any, target: Any, weights: Any, args: argparse.Namespace) -> Any:
    loss = training_loss(mu, logvar, target, weights, args.mse_weight)
    if args.irc_loss_weight <= 0:
        return loss
    predicted_irc = differentiable_irc(mu, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
    target_irc = differentiable_irc(target, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
    return loss + float(args.irc_loss_weight) * ((predicted_irc - target_irc) ** 2).mean()


def numpy_irc(values: np.ndarray, *, alpha: float, beta: float, gamma: float) -> np.ndarray:
    return (float(alpha) * values[:, 0] + float(beta) * (1.0 - values[:, 1]) + float(gamma) * values[:, 2]) / (
        float(alpha) + float(beta) + float(gamma)
    )


def evaluate_irc_persistence(
    frame: pd.DataFrame, indices_by_split: dict[str, np.ndarray], args: argparse.Namespace
) -> pd.DataFrame:
    rows = []
    for split, indices in indices_by_split.items():
        if len(indices) == 0:
            continue
        y_true = frame.loc[indices, TARGET_COLUMNS].to_numpy(dtype="float64")
        y_pred = frame.loc[indices, STATE_INPUT_COLUMNS].to_numpy(dtype="float64")
        error = numpy_irc(y_pred, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma) - numpy_irc(
            y_true,
            alpha=args.irc_alpha,
            beta=args.irc_beta,
            gamma=args.irc_gamma,
        )
        rows.append(
            {
                "split": split,
                "target": "irc1",
                "rows": int(len(indices)),
                "rmse": float(np.sqrt(np.mean(error**2))),
                "mae": float(np.mean(np.abs(error))),
            }
        )
    return pd.DataFrame(rows)


def validation_selection_objective_v1(
    *,
    args: argparse.Namespace,
    validation_metrics: pd.DataFrame,
    validation_loss: float,
    persistence_metrics: pd.DataFrame,
    persistence_irc_metrics: pd.DataFrame,
    validation_irc_rmse: float,
) -> float:
    if args.checkpoint_selection_metric in {"nll", "rmse", "mae", "balanced"}:
        return validation_selection_objective(
            validation_metrics,
            validation_loss,
            persistence_metrics,
            args.checkpoint_selection_metric,
        )
    if args.checkpoint_selection_metric == "irc_rmse":
        return float(validation_irc_rmse)
    if args.checkpoint_selection_metric != "balanced_irc":
        raise ValueError(f"Unsupported checkpoint selection metric: {args.checkpoint_selection_metric}")
    state_objective = validation_selection_objective(
        validation_metrics,
        validation_loss,
        persistence_metrics,
        "balanced",
    )
    persistence = persistence_irc_metrics[persistence_irc_metrics["split"] == "validation"].iloc[0]
    irc_scale = max(float(persistence.rmse), 1e-12)
    return 0.5 * float(state_objective) + 0.5 * (float(validation_irc_rmse) / irc_scale)


def eligible_multistep_window_indices(
    frame: pd.DataFrame, split: str, history_length: int, horizon: int
) -> np.ndarray:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    candidates = eligible_window_indices(frame, split, history_length)
    if horizon == 1 or len(candidates) == 0:
        return candidates
    run_ids = frame["window_run_id"].to_numpy(dtype="int64")
    positions = frame["window_position"].to_numpy(dtype="int64")
    selected: list[int] = []
    last_frame_index = len(frame) - 1
    for index in candidates:
        final_index = int(index) + horizon - 1
        if final_index > last_frame_index:
            continue
        if run_ids[final_index] != run_ids[int(index)]:
            continue
        if positions[final_index] != positions[int(index)] + horizon - 1:
            continue
        selected.append(int(index))
    return np.asarray(selected, dtype="int64")


class MultiStepWindowDataset:
    def __init__(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        end_indices: np.ndarray,
        history_length: int,
        horizon: int,
    ) -> None:
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        self.x_values = x_values
        self.y_values = y_values
        self.end_indices = end_indices.astype("int64")
        self.history_length = int(history_length)
        self.horizon = int(horizon)

    def __len__(self) -> int:
        return int(len(self.end_indices))

    def __getitem__(self, item: int) -> tuple[Any, Any, Any]:
        torch = _require_torch()
        end_index = int(self.end_indices[item])
        start_index = end_index - self.history_length + 1
        x_window = self.x_values[start_index : end_index + 1]
        future_targets = self.y_values[end_index : end_index + self.horizon]
        future_inputs = self.x_values[end_index + 1 : end_index + self.horizon]
        return torch.from_numpy(x_window), torch.from_numpy(future_targets), torch.from_numpy(future_inputs)


def multistep_data_loader(
    dataset: MultiStepWindowDataset, *, batch_size: int, shuffle: bool, seed: int
) -> Any:
    torch = _require_torch()
    generator = torch.Generator()
    generator.manual_seed(seed)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, generator=generator)


def multistep_training_loss(
    model: Any,
    x_batch: Any,
    future_targets: Any,
    future_inputs: Any,
    weights: Any,
    args: argparse.Namespace,
) -> Any:
    torch = _require_torch()
    window = x_batch
    step_losses = []
    horizon = int(future_targets.shape[1])
    context_dim = len(resolve_context_columns(args.context_columns))
    context_start = _context_start()
    for step in range(horizon):
        mu, logvar = model(window)
        target = future_targets[:, step, :]
        step_losses.append(history_training_loss(mu, logvar, target, weights, args))
        if step + 1 < horizon:
            next_input = future_inputs[:, step, :].clone()
            next_input[:, : len(STATE_INPUT_COLUMNS)] = _bound_state_tensor(mu)
            if context_dim > 0:
                next_input[:, context_start : context_start + context_dim] = window[
                    :, -1, context_start : context_start + context_dim
                ]
            window = torch.cat([window[:, 1:, :], next_input[:, None, :]], dim=1)
    if len(step_losses) == 1 or args.multi_step_loss_weight <= 0:
        return step_losses[0]
    rollout_loss = torch.stack(step_losses[1:]).mean()
    weight = float(args.multi_step_loss_weight)
    return (step_losses[0] + weight * rollout_loss) / (1.0 + weight)


def train_multistep_epoch(
    model: Any,
    dataset: MultiStepWindowDataset,
    args: argparse.Namespace,
    optimizer: Any,
    weights: Any,
    device: Any,
    epoch: int,
) -> float:
    torch = _require_torch()
    model.train()
    loader = multistep_data_loader(dataset, batch_size=args.batch_size, shuffle=True, seed=args.random_seed + epoch)
    total_loss = 0.0
    total_rows = 0
    for batch_index, (x_batch, future_targets, future_inputs) in enumerate(loader, start=1):
        x_batch = x_batch.to(device=device, dtype=weights.dtype)
        future_targets = future_targets.to(device=device, dtype=weights.dtype)
        future_inputs = future_inputs.to(device=device, dtype=weights.dtype)
        optimizer.zero_grad(set_to_none=True)
        loss = multistep_training_loss(model, x_batch, future_targets, future_inputs, weights, args)
        loss.backward()
        if args.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(args.grad_clip))
        optimizer.step()
        rows = int(len(x_batch))
        total_loss += float(loss.item()) * rows
        total_rows += rows
        if args.progress_every_batches and batch_index % args.progress_every_batches == 0:
            print(f"  batch {batch_index}: loss={float(loss.item()):.5f}", flush=True)
    return total_loss / max(total_rows, 1)


def train_history_epoch(
    model: Any,
    dataset: WindowDataset,
    args: argparse.Namespace,
    optimizer: Any,
    weights: Any,
    device: Any,
    epoch: int,
) -> float:
    torch = _require_torch()
    model.train()
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(args.random_seed + epoch),
    )
    total_loss = 0.0
    total_rows = 0
    for batch_index, (x_batch, y_batch) in enumerate(loader, start=1):
        x_batch = x_batch.to(device=device, dtype=weights.dtype)
        y_batch = y_batch.to(device=device, dtype=weights.dtype)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(x_batch)
        loss = history_training_loss(mu, logvar, y_batch, weights, args)
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


def evaluate_history_model(
    model: Any,
    dataset: WindowDataset,
    *,
    batch_size: int,
    weights: Any,
    device: Any,
    args: argparse.Namespace,
    blend_weights: Any | None = None,
) -> tuple[pd.DataFrame, float, dict[str, float]]:
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
    irc_squared = 0.0
    irc_abs = 0.0
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False)
    with torch.no_grad():
        for x_batch, y_batch in loader:
            x_batch = x_batch.to(device=device, dtype=weights.dtype)
            y_batch = y_batch.to(device=device, dtype=weights.dtype)
            mu, logvar = model(x_batch)
            if blend_weights is not None:
                persistence = x_batch[:, -1, :target_dim]
                mu = persistence + blend_weights * (mu - persistence)
            loss = history_training_loss(mu, logvar, y_batch, weights, args)
            variance = torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))
            sigma = torch.sqrt(variance)
            lower = mu - 1.6448536269514722 * sigma
            upper = mu + 1.6448536269514722 * sigma
            error = mu - y_batch
            nll_by_value = 0.5 * (torch.clamp(logvar, min=-10.0, max=2.0) + (error**2) / variance)
            irc_error = differentiable_irc(mu, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma) - (
                differentiable_irc(y_batch, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
            )
            rows = int(len(y_batch))
            total_loss += float(loss.item()) * rows
            total_rows += rows
            sum_squared += (error.detach().cpu().numpy() ** 2).sum(axis=0)
            sum_abs += np.abs(error.detach().cpu().numpy()).sum(axis=0)
            sum_nll += nll_by_value.detach().cpu().numpy().sum(axis=0)
            sum_width += (upper - lower).detach().cpu().numpy().sum(axis=0)
            coverage += ((y_batch >= lower) & (y_batch <= upper)).detach().cpu().numpy().sum(axis=0)
            irc_squared += float((irc_error**2).sum().detach().cpu())
            irc_abs += float(irc_error.abs().sum().detach().cpu())

    rows_out = []
    for index, target in enumerate(TARGET_COLUMNS):
        rows_out.append(
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
    metrics = pd.DataFrame(rows_out)
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
    aux = {
        "irc_rmse": math.sqrt(irc_squared / max(total_rows, 1)),
        "irc_mae": irc_abs / max(total_rows, 1),
    }
    return metrics, total_loss / max(total_rows, 1), aux


def evaluate_multistep_loss(
    model: Any,
    dataset: MultiStepWindowDataset,
    *,
    args: argparse.Namespace,
    batch_size: int,
    weights: Any,
    device: Any,
) -> float:
    torch = _require_torch()
    model.eval()
    loader = multistep_data_loader(dataset, batch_size=batch_size, shuffle=False, seed=0)
    total_loss = 0.0
    total_rows = 0
    with torch.no_grad():
        for x_batch, future_targets, future_inputs in loader:
            x_batch = x_batch.to(device=device, dtype=weights.dtype)
            future_targets = future_targets.to(device=device, dtype=weights.dtype)
            future_inputs = future_inputs.to(device=device, dtype=weights.dtype)
            loss = multistep_training_loss(model, x_batch, future_targets, future_inputs, weights, args)
            rows = int(len(x_batch))
            total_loss += float(loss.item()) * rows
            total_rows += rows
    return total_loss / max(total_rows, 1)


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
    mismatches = []
    for key, expected in expected_config.items():
        if args.training_objective == "one_step" and key in MULTI_STEP_CONFIG_KEYS:
            continue
        if key not in checkpoint_config:
            if key in BACKWARD_COMPAT_CONFIG_DEFAULTS and expected == BACKWARD_COMPAT_CONFIG_DEFAULTS[key]:
                continue
            if key == "multi_step_checkpoint_objective" and expected == "rollout_loss":
                continue
            if args.training_objective == "one_step" and key in MULTI_STEP_CONFIG_KEYS:
                continue
            mismatches.append(key)
            continue
        if checkpoint_config[key] != expected:
            mismatches.append(key)
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
    available_windows: dict[str, int],
    sampled_windows: dict[str, int],
    started_at: datetime,
) -> None:
    best_sort_column = "validation_selection_objective" if "validation_selection_objective" in history.columns else "validation_loss"
    best_row = history.sort_values([best_sort_column, "epoch"]).iloc[0] if not history.empty else None
    lines = [
        "# PIPE Neural ODE History Training Report v1",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This step trains a history-encoded Neural ODE variant over the frozen PIPE sequence schema.",
        "A GRU encoder summarizes the recent PIPE history, initializes a latent ODE, and decodes the next fuzzy state.",
        "The default objective remains one-step; optional multi-step training rolls predictions forward through future seasons.",
        "The metrics tables below remain one-step diagnostics so runs stay comparable with earlier v1 artifacts.",
        f"Synthetic smoke mode: `{bool(args.synthetic_smoke)}`.",
        "",
        "## Configuration",
        "",
        f"- History length: `{args.history_length}`",
        f"- Training objective: `{args.training_objective}`",
        f"- Multi-step horizon: `{args.multi_step_horizon}`",
        f"- Multi-step continuation loss weight: `{args.multi_step_loss_weight}`",
        f"- Multi-step checkpoint objective: `{args.multi_step_checkpoint_objective}`",
        f"- Context columns: `{context_columns_label(resolve_context_columns(args.context_columns))}`",
        f"- History hidden dimension: `{args.history_hidden_dim}`",
        f"- History layers: `{args.history_layers}`",
        f"- Latent dimension: `{args.latent_dim}`",
        f"- Dynamics hidden dimension: `{args.dynamics_hidden_dim}`",
        f"- Dynamics depth: `{args.dynamics_depth}`",
        f"- Dropout: `{args.dropout}`",
        f"- Derivative scale: `{args.derivative_scale}`",
        f"- State delta scale: `{args.state_delta_scale}`",
        f"- Integration time: `{args.integration_time}`",
        f"- ODE method: `{args.ode_method}`",
        f"- ODE step size: `{args.ode_step_size}`",
        f"- Auxiliary MSE weight: `{args.mse_weight}`",
        f"- Auxiliary IRC loss weight: `{args.irc_loss_weight}`",
        f"- IRC weights: alpha=`{args.irc_alpha}`, beta=`{args.irc_beta}`, gamma=`{args.irc_gamma}`",
        f"- Checkpoint selection metric: `{checkpoint_selection_label(args)}`",
        f"- One-step checkpoint metric: `{args.checkpoint_selection_metric}`",
        f"- Output blend selection metric: `{args.blend_selection_metric}`",
        f"- Epochs requested: `{args.epochs}`",
        f"- Batch size: `{args.batch_size}`",
        f"- Learning rate: `{args.learning_rate}`",
        f"- Device: `{args.device}`",
        "",
        "## Windows",
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
                f"- Selection metric: `{checkpoint_selection_label(args)}`",
                f"- Selection objective: `{_format_float(float(getattr(best_row, best_sort_column)))}`",
                f"- Validation loss: `{_format_float(float(best_row.validation_loss))}`",
                f"- Validation RMSE all: `{_format_float(float(best_row.validation_rmse_all))}`",
                f"- Validation MAE all: `{_format_float(float(best_row.validation_mae_all))}`",
                f"- Validation IRC RMSE: `{_format_float(float(getattr(best_row, 'validation_irc_rmse', np.nan)))}`",
                f"- Validation IRC MAE: `{_format_float(float(getattr(best_row, 'validation_irc_mae', np.nan)))}`",
            ]
        )
        rollout_loss = getattr(best_row, "validation_rollout_loss", np.nan)
        if pd.notna(rollout_loss):
            lines.append(f"- Validation multi-step rollout loss: `{_format_float(float(rollout_loss))}`")
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
            "`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.",
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
            "Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.",
            "",
            "| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |",
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
            "available_windows": available_windows,
            "sampled_windows": sampled_windows,
            "metric_rows": int(len(metrics)),
            "blend_weight_rows": int(len(blend_weights)),
            "blend_search_rows": int(len(blend_search)),
            "persistence_metric_rows": int(len(persistence_metrics)),
            "comparison_rows": int(len(comparison)),
            "training_curve_rows": int(len(history)),
        },
        "selection": {
            "checkpoint_selection_metric": checkpoint_selection_label(args),
            "one_step_checkpoint_selection_metric": args.checkpoint_selection_metric,
            "best_epoch": int(best_row["epoch"]) if best_row else None,
            "best_validation_loss": float(best_row["validation_loss"]) if best_row else None,
            "best_validation_rmse_all": float(best_row.get("validation_rmse_all", np.nan)) if best_row else None,
            "best_validation_mae_all": float(best_row.get("validation_mae_all", np.nan)) if best_row else None,
            "best_validation_irc_rmse": float(best_row.get("validation_irc_rmse", np.nan)) if best_row else None,
            "best_validation_irc_mae": float(best_row.get("validation_irc_mae", np.nan)) if best_row else None,
            "best_validation_rollout_loss": float(best_row.get("validation_rollout_loss", np.nan)) if best_row else None,
            "best_validation_one_step_selection_objective": (
                float(best_row.get("validation_one_step_selection_objective", np.nan)) if best_row else None
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
    parser.add_argument("--training-objective", choices=["one_step", "multi_step"], default="one_step")
    parser.add_argument("--multi-step-horizon", type=int, default=3)
    parser.add_argument("--multi-step-loss-weight", type=float, default=1.0)
    parser.add_argument(
        "--multi-step-checkpoint-objective",
        choices=["rollout_loss", "one_step"],
        default="rollout_loss",
        help=(
            "Checkpoint selection objective for multi-step training. "
            "Use rollout_loss to optimize the recursive training loss, or one_step to keep the best "
            "validation one-step checkpoint while still training with multi-step continuation loss."
        ),
    )
    parser.add_argument(
        "--context-columns",
        default="none",
        help=(
            "Optional sequence context for the history encoder. Use 'none', 'irc', 'evidence', "
            "'missingness', 'evidence,missingness', or explicit x_* context column names."
        ),
    )
    parser.add_argument("--history-hidden-dim", type=int, default=96)
    parser.add_argument("--history-layers", type=int, default=1)
    parser.add_argument("--latent-dim", type=int, default=64)
    parser.add_argument("--dynamics-hidden-dim", type=int, default=96)
    parser.add_argument("--dynamics-depth", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--derivative-scale", type=float, default=0.5)
    parser.add_argument("--state-delta-scale", type=float, default=0.5)
    parser.add_argument("--integration-time", type=float, default=1.0)
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
    parser.add_argument(
        "--checkpoint-selection-metric",
        choices=["nll", "rmse", "mae", "balanced", "irc_rmse", "balanced_irc"],
        default="balanced",
    )
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
    if args.history_length < 1:
        raise ValueError("--history-length must be >= 1")
    if args.history_layers < 1:
        raise ValueError("--history-layers must be >= 1")
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    if args.multi_step_horizon < 1:
        raise ValueError("--multi-step-horizon must be >= 1")
    if args.multi_step_loss_weight < 0:
        raise ValueError("--multi-step-loss-weight must be >= 0")
    if args.irc_loss_weight < 0:
        raise ValueError("--irc-loss-weight must be >= 0")
    if args.irc_alpha < 0 or args.irc_beta < 0 or args.irc_gamma < 0:
        raise ValueError("--irc-alpha, --irc-beta, and --irc-gamma must be >= 0")
    if args.irc_alpha + args.irc_beta + args.irc_gamma <= 0:
        raise ValueError("At least one IRC weight must be positive")
    if args.dynamics_depth < 0:
        raise ValueError("--dynamics-depth must be >= 0")
    if args.derivative_scale <= 0:
        raise ValueError("--derivative-scale must be > 0")
    if args.state_delta_scale <= 0:
        raise ValueError("--state-delta-scale must be > 0")
    if args.integration_time <= 0:
        raise ValueError("--integration-time must be > 0")
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
        print("building synthetic Neural ODE v1 smoke dataset", flush=True)
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

    if args.training_objective == "multi_step":
        available_indices = {
            split: eligible_multistep_window_indices(frame, split, args.history_length, args.multi_step_horizon)
            for split in ["train", "validation", "test"]
        }
    else:
        available_indices = {
            split: eligible_window_indices(frame, split, args.history_length) for split in ["train", "validation", "test"]
        }
    sampled_indices = {
        "train": sample_indices(available_indices["train"], args.max_train_windows, args.random_seed),
        "validation": sample_indices(available_indices["validation"], args.max_eval_windows, args.random_seed + 1),
        "test": sample_indices(available_indices["test"], args.max_eval_windows, args.random_seed + 2),
    }
    available_windows = {split: int(len(indices)) for split, indices in available_indices.items()}
    sampled_windows = {split: int(len(indices)) for split, indices in sampled_indices.items()}
    print(f"available windows={available_windows}", flush=True)
    print(f"sampled windows={sampled_windows}", flush=True)
    if sampled_windows["train"] == 0 or sampled_windows["validation"] == 0:
        raise ValueError("Training and validation splits must each have at least one eligible window")
    persistence_metrics = evaluate_persistence(frame, sampled_indices)
    persistence_irc_metrics = evaluate_irc_persistence(frame, sampled_indices, args)

    datasets = {
        split: WindowDataset(x_values, y_values, indices, args.history_length) for split, indices in sampled_indices.items()
    }
    multistep_datasets = {
        split: MultiStepWindowDataset(x_values, y_values, indices, args.history_length, args.multi_step_horizon)
        for split, indices in sampled_indices.items()
    }
    model = make_history_neural_ode_model(
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
            if args.training_objective == "multi_step":
                train_loss = train_multistep_epoch(
                    model,
                    multistep_datasets["train"],
                    args,
                    optimizer,
                    weights,
                    device,
                    epoch,
                )
                validation_rollout_loss = evaluate_multistep_loss(
                    model,
                    multistep_datasets["validation"],
                    args=args,
                    batch_size=args.batch_size,
                    weights=weights,
                    device=device,
                )
            else:
                train_loss = train_history_epoch(model, datasets["train"], args, optimizer, weights, device, epoch)
                validation_rollout_loss = np.nan
            epoch_blend_weights, _ = select_output_blend_weights(
                model,
                datasets["validation"],
                batch_size=args.batch_size,
                grid=blend_grid,
                selection_metric=args.blend_selection_metric,
                device=device,
            )
            epoch_blend_tensor = _blend_weight_tensor(epoch_blend_weights, device)
            validation_metrics, validation_loss, validation_aux = evaluate_history_model(
                model,
                datasets["validation"],
                batch_size=args.batch_size,
                weights=weights,
                device=device,
                args=args,
                blend_weights=epoch_blend_tensor,
            )
            validation_one_step_objective = validation_selection_objective_v1(
                args=args,
                validation_metrics=validation_metrics,
                validation_loss=validation_loss,
                persistence_metrics=persistence_metrics,
                persistence_irc_metrics=persistence_irc_metrics,
                validation_irc_rmse=float(validation_aux["irc_rmse"]),
            )
            validation_objective = checkpoint_selection_objective(
                args=args,
                validation_rollout_loss=float(validation_rollout_loss),
                validation_one_step_objective=float(validation_one_step_objective),
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
                "validation_irc_rmse": float(validation_aux["irc_rmse"]),
                "validation_irc_mae": float(validation_aux["irc_mae"]),
                "validation_rollout_loss": float(validation_rollout_loss),
                "validation_one_step_selection_objective": float(validation_one_step_objective),
                "validation_selection_objective": float(validation_objective),
                "validation_blend_selection_metric": args.blend_selection_metric,
                "training_objective": args.training_objective,
                "multi_step_checkpoint_objective": args.multi_step_checkpoint_objective,
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
            message = (
                f"epoch {epoch}: train_loss={train_loss:.5f}; validation_loss={validation_loss:.5f}; "
                f"selection_objective={validation_objective:.5f}"
            )
            if args.training_objective == "multi_step":
                message += f"; validation_rollout_loss={float(validation_rollout_loss):.5f}"
            print(f"{message}; elapsed={_elapsed(started_monotonic)}", flush=True)
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
        metrics, _, _ = evaluate_history_model(
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
