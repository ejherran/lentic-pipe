#!/usr/bin/env python
"""Train a history-encoded probabilistic PIPE Neural ODE state model."""

from __future__ import annotations

import argparse
import json
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
    evaluate_model,
    evaluate_persistence,
    load_sequences,
    make_loss_weights,
    prediction_examples,
    prepare_window_frame,
    sample_indices,
    select_output_blend_weights,
    set_reproducible_seed,
    train_epoch,
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


def make_history_neural_ode_model(
    *,
    input_dim: int,
    state_dim: int,
    season_dim: int,
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
            context_dim = history_hidden_dim + season_dim
            layer_input_dim = latent_dim + context_dim + 1
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
                torch.nn.Linear(history_hidden_dim + state_dim + season_dim, latent_dim),
                torch.nn.Tanh(),
            )
            self.dynamics = LatentDynamics()
            decoder_input_dim = latent_dim + history_hidden_dim + state_dim + season_dim
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
            context = torch.cat([history_context, season], dim=1)
            latent0 = self.latent_initial(torch.cat([history_context, last_state, season], dim=1))
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
            decoder_input = torch.cat([latent1, history_context, last_state, season], dim=1)
            delta = float(state_delta_scale) * torch.tanh(self.delta_head(decoder_input))
            mu = _bound_state_tensor(last_state + delta)
            logvar = torch.clamp(self.logvar_head(decoder_input), min=-10.0, max=2.0)
            return mu, logvar

    return PipeHistoryNeuralODEModel()


def model_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "architecture": "history_encoder_latent_ode",
        "history_length": int(args.history_length),
        "input_dim": len(INPUT_COLUMNS),
        "state_dim": len(STATE_INPUT_COLUMNS),
        "season_dim": len(SEASON_COLUMNS),
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
        "checkpoint_selection_metric": args.checkpoint_selection_metric,
        "checkpoint_selection_uses_output_blend": True,
        "blend_selection_metric": args.blend_selection_metric,
        "blend_grid": _parse_float_grid(args.blend_grid),
        "target_weights": TARGET_WEIGHTS,
        "input_columns": INPUT_COLUMNS,
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
        "The v1 runner is one-step; recursive rollout support is a downstream gate after one-step validation.",
        f"Synthetic smoke mode: `{bool(args.synthetic_smoke)}`.",
        "",
        "## Configuration",
        "",
        f"- History length: `{args.history_length}`",
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
        f"- Checkpoint selection metric: `{args.checkpoint_selection_metric}`",
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
            "checkpoint_selection_metric": args.checkpoint_selection_metric,
            "best_epoch": int(best_row["epoch"]) if best_row else None,
            "best_validation_loss": float(best_row["validation_loss"]) if best_row else None,
            "best_validation_rmse_all": float(best_row.get("validation_rmse_all", np.nan)) if best_row else None,
            "best_validation_mae_all": float(best_row.get("validation_mae_all", np.nan)) if best_row else None,
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
        print("building synthetic Neural ODE v1 smoke dataset", flush=True)
        frame = synthetic_sequence_frame(
            sites_per_split=args.synthetic_sites,
            months_per_split=args.synthetic_months_per_split,
            seed=args.random_seed,
        )
    else:
        print(f"loading sequences {args.sequences}", flush=True)
        frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_window_frame(frame)
    print(f"sequence rows={len(frame):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    x_values = frame[INPUT_COLUMNS].to_numpy(dtype="float32")
    y_values = frame[TARGET_COLUMNS].to_numpy(dtype="float32")

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

    datasets = {
        split: WindowDataset(x_values, y_values, indices, args.history_length) for split, indices in sampled_indices.items()
    }
    model = make_history_neural_ode_model(
        input_dim=len(INPUT_COLUMNS),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
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
