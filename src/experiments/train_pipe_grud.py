#!/usr/bin/env python
"""Train the minimal probabilistic PIPE/GRU-D one-step state model."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import random
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

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, TARGET_COLUMNS


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_v0.parquet")
DEFAULT_SEQUENCE_MANIFEST = Path("reports/pipe_grud/pipe_sequence_manifest.json")
DEFAULT_MODELS_DIR = Path("models/pipe_grud")
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_MODEL = DEFAULT_MODELS_DIR / "pipe_grud_model_v0.pt"
DEFAULT_CHECKPOINT = DEFAULT_MODELS_DIR / "pipe_grud_checkpoint_v0.pt"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_grud_metrics.csv"
DEFAULT_PERSISTENCE_METRICS = DEFAULT_REPORT_DIR / "pipe_grud_persistence_metrics.csv"
DEFAULT_COMPARISON = DEFAULT_REPORT_DIR / "pipe_grud_persistence_comparison.csv"
DEFAULT_BLEND_WEIGHTS = DEFAULT_REPORT_DIR / "pipe_grud_output_blend_weights.csv"
DEFAULT_BLEND_SEARCH = DEFAULT_REPORT_DIR / "pipe_grud_output_blend_search.csv"
DEFAULT_TRAINING_CURVE = DEFAULT_REPORT_DIR / "pipe_grud_training_curve.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_grud_prediction_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_grud_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_grud_manifest.json"

MODEL_VERSION = "pipe_grud_v0"
ID_COLUMNS = ["source_id", "site_id", "sequence_step", "origin_year_month", "target_year_month", "split"]
STATE_TARGET_NAMES = [column.removeprefix("target_") for column in TARGET_COLUMNS]
TARGET_WEIGHTS = {
    "yN": 2.0,
    "yF": 1.0,
    "yT": 2.5,
    "sigma_N": 0.5,
    "sigma_F": 0.5,
    "sigma_T": 0.5,
    "delta_yN": 1.5,
    "delta_yF": 1.5,
    "delta_yT": 1.5,
}


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")
    tmp_path.replace(path)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _require_torch() -> Any:
    try:
        return importlib.import_module("torch")
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for PIPE/GRU-D training. Install the modeling group with Poetry before running this script."
        ) from exc


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch = _require_torch()
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _elapsed(started: float) -> str:
    return f"{time.monotonic() - started:,.1f}s"


def _parse_float_grid(value: str) -> list[float]:
    out = sorted({float(part.strip()) for part in value.split(",") if part.strip()})
    if not out or out[0] < 0.0 or out[-1] > 1.0:
        raise ValueError("Blend grid values must be between 0 and 1")
    return out


def load_sequences(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    columns = ID_COLUMNS + INPUT_COLUMNS + TARGET_COLUMNS
    frame = pd.read_parquet(path, columns=columns)
    if max_rows:
        frame = frame.head(max_rows).copy()
    frame["source_id"] = frame["source_id"].astype(str)
    frame["site_id"] = frame["site_id"].astype(str)
    frame["split"] = frame["split"].astype(str)
    numeric_columns = INPUT_COLUMNS + TARGET_COLUMNS + ["sequence_step"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame[INPUT_COLUMNS] = frame[INPUT_COLUMNS].fillna(0.0)
    frame[TARGET_COLUMNS] = frame[TARGET_COLUMNS].fillna(0.0)
    frame["sequence_step"] = frame["sequence_step"].astype("int64")
    return frame


def prepare_window_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["source_id", "site_id", "split", "sequence_step"]).reset_index(drop=True)
    previous = out[["source_id", "site_id", "split", "sequence_step"]].shift(1)
    is_break = (
        (out["source_id"] != previous["source_id"])
        | (out["site_id"] != previous["site_id"])
        | (out["split"] != previous["split"])
        | (out["sequence_step"] != previous["sequence_step"] + 1)
    )
    out["window_run_id"] = is_break.cumsum().astype("int64")
    out["window_position"] = out.groupby("window_run_id", sort=False).cumcount().astype("int64")
    return out


def eligible_window_indices(frame: pd.DataFrame, split: str, history_length: int) -> np.ndarray:
    mask = (frame["split"] == split) & (frame["window_position"] >= history_length - 1)
    return frame.index[mask].to_numpy(dtype="int64")


def sample_indices(indices: np.ndarray, max_windows: int | None, seed: int) -> np.ndarray:
    if max_windows is None or max_windows <= 0 or len(indices) <= max_windows:
        return indices
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(indices, size=max_windows, replace=False)).astype("int64")


def make_loss_weights() -> np.ndarray:
    return np.asarray([TARGET_WEIGHTS[name] for name in STATE_TARGET_NAMES], dtype="float32")


def gaussian_nll(mu: Any, logvar: Any, target: Any, weights: Any) -> Any:
    torch = _require_torch()
    logvar = torch.clamp(logvar, min=-10.0, max=2.0)
    loss = 0.5 * (logvar + ((target - mu) ** 2) / torch.exp(logvar))
    return (loss * weights).mean()


def apply_output_blend(mu: Any, x_batch: Any, blend_weights: Any | None) -> Any:
    if blend_weights is None:
        return mu
    persistence = x_batch[:, -1, : len(TARGET_COLUMNS)]
    return persistence + blend_weights * (mu - persistence)


def training_loss(mu: Any, logvar: Any, target: Any, weights: Any, mse_weight: float) -> Any:
    nll = gaussian_nll(mu, logvar, target, weights)
    if mse_weight <= 0:
        return nll
    mse = (((target - mu) ** 2) * weights).mean()
    return nll + float(mse_weight) * mse


class WindowDataset:
    def __init__(self, x_values: np.ndarray, y_values: np.ndarray, end_indices: np.ndarray, history_length: int) -> None:
        self.x_values = x_values
        self.y_values = y_values
        self.end_indices = end_indices.astype("int64")
        self.history_length = int(history_length)

    def __len__(self) -> int:
        return int(len(self.end_indices))

    def __getitem__(self, item: int) -> tuple[Any, Any]:
        torch = _require_torch()
        end_index = int(self.end_indices[item])
        start_index = end_index - self.history_length + 1
        x_window = self.x_values[start_index : end_index + 1]
        y_target = self.y_values[end_index]
        return torch.from_numpy(x_window), torch.from_numpy(y_target)


def make_model(
    input_dim: int,
    target_dim: int,
    hidden_dim: int,
    num_layers: int,
    dropout: float,
    residual_mode: str,
) -> Any:
    torch = _require_torch()

    class PipeGRUDModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.residual_mode = residual_mode
            self.gru = torch.nn.GRU(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.mu_head = torch.nn.Linear(hidden_dim, target_dim)
            self.logvar_head = torch.nn.Linear(hidden_dim, target_dim)

        def forward(self, x: Any) -> tuple[Any, Any]:
            _, hidden = self.gru(x)
            final_hidden = hidden[-1]
            mu = self.mu_head(final_hidden)
            if self.residual_mode == "add_last":
                mu = x[:, -1, :target_dim] + mu
            logvar = torch.clamp(self.logvar_head(final_hidden), min=-10.0, max=2.0)
            return mu, logvar

    return PipeGRUDModel()


def _data_loader(dataset: WindowDataset, *, batch_size: int, shuffle: bool, seed: int) -> Any:
    torch = _require_torch()
    generator = torch.Generator()
    generator.manual_seed(seed)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, generator=generator)


def train_epoch(model: Any, dataset: WindowDataset, args: argparse.Namespace, optimizer: Any, weights: Any, device: Any, epoch: int) -> float:
    model.train()
    total_loss = 0.0
    total_rows = 0
    loader = _data_loader(dataset, batch_size=args.batch_size, shuffle=True, seed=args.random_seed + epoch)
    for batch_index, (x_batch, y_batch) in enumerate(loader, start=1):
        x_batch = x_batch.to(device=device, dtype=weights.dtype)
        y_batch = y_batch.to(device=device, dtype=weights.dtype)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(x_batch)
        loss = training_loss(mu, logvar, y_batch, weights, args.mse_weight)
        loss.backward()
        if args.grad_clip > 0:
            torch = _require_torch()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()
        rows = int(len(y_batch))
        total_loss += float(loss.item()) * rows
        total_rows += rows
        if args.progress_every_batches and batch_index % args.progress_every_batches == 0:
            print(f"epoch {epoch}: batch {batch_index}; rows={total_rows:,}; loss={total_loss / total_rows:.5f}", flush=True)
    return total_loss / max(total_rows, 1)


def select_output_blend_weights(
    model: Any,
    dataset: WindowDataset,
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
        for x_batch, y_batch in loader:
            x_batch = x_batch.to(device=device, dtype=torch.float32)
            y_batch = y_batch.to(device=device, dtype=torch.float32)
            mu, _ = model(x_batch)
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


def _blend_weight_tensor(blend_weights: pd.DataFrame | None, device: Any) -> Any | None:
    if blend_weights is None or blend_weights.empty:
        return None
    torch = _require_torch()
    mapping = dict(zip(blend_weights["target"], blend_weights["blend_weight"], strict=True))
    values = [float(mapping[target]) for target in STATE_TARGET_NAMES]
    return torch.tensor(values, device=device, dtype=torch.float32)


def evaluate_model(
    model: Any,
    dataset: WindowDataset,
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
        for x_batch, y_batch in loader:
            x_batch = x_batch.to(device=device, dtype=weights.dtype)
            y_batch = y_batch.to(device=device, dtype=weights.dtype)
            mu, logvar = model(x_batch)
            mu = apply_output_blend(mu, x_batch, blend_weights)
            loss = gaussian_nll(mu, logvar, y_batch, weights)
            variance = torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))
            sigma = torch.sqrt(variance)
            lower = mu - 1.6448536269514722 * sigma
            upper = mu + 1.6448536269514722 * sigma
            error = mu - y_batch
            nll_by_value = 0.5 * (torch.clamp(logvar, min=-10.0, max=2.0) + (error**2) / variance)
            rows = int(len(y_batch))
            total_loss += float(loss.item()) * rows
            total_rows += rows
            sum_squared += (error.detach().cpu().numpy() ** 2).sum(axis=0)
            sum_abs += np.abs(error.detach().cpu().numpy()).sum(axis=0)
            sum_nll += nll_by_value.detach().cpu().numpy().sum(axis=0)
            sum_width += (upper - lower).detach().cpu().numpy().sum(axis=0)
            coverage += ((y_batch >= lower) & (y_batch <= upper)).detach().cpu().numpy().sum(axis=0)

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


def evaluate_persistence(frame: pd.DataFrame, indices_by_split: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    prediction_columns = [column.replace("target_", "x_", 1) for column in TARGET_COLUMNS]
    for split, indices in indices_by_split.items():
        if len(indices) == 0:
            continue
        y_true = frame.loc[indices, TARGET_COLUMNS].to_numpy(dtype="float64")
        y_pred = frame.loc[indices, prediction_columns].to_numpy(dtype="float64")
        error = y_pred - y_true
        rmse_by_target = np.sqrt(np.mean(error**2, axis=0))
        mae_by_target = np.mean(np.abs(error), axis=0)
        rows.append(
            {
                "split": split,
                "target": "all",
                "rows": int(len(indices)),
                "rmse": float(rmse_by_target.mean()),
                "mae": float(mae_by_target.mean()),
            }
        )
        for index, target in enumerate(STATE_TARGET_NAMES):
            rows.append(
                {
                    "split": split,
                    "target": target,
                    "rows": int(len(indices)),
                    "rmse": float(rmse_by_target[index]),
                    "mae": float(mae_by_target[index]),
                }
            )
    return pd.DataFrame(rows)


def compare_to_persistence(pipe_metrics: pd.DataFrame, persistence_metrics: pd.DataFrame) -> pd.DataFrame:
    pipe = pipe_metrics[["split", "target", "rows", "rmse", "mae"]].rename(
        columns={"rows": "pipe_rows", "rmse": "pipe_rmse", "mae": "pipe_mae"}
    )
    persistence = persistence_metrics.rename(
        columns={"rows": "persistence_rows", "rmse": "persistence_rmse", "mae": "persistence_mae"}
    )
    out = pipe.merge(persistence, on=["split", "target"], how="inner")
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
    return out.sort_values(["split", "target"]).reset_index(drop=True)


def validation_selection_objective(
    validation_metrics: pd.DataFrame,
    validation_loss: float,
    persistence_metrics: pd.DataFrame,
    selection_metric: str,
) -> float:
    if selection_metric == "nll":
        return float(validation_loss)
    current = validation_metrics[validation_metrics["target"] == "all"].iloc[0]
    if selection_metric == "rmse":
        return float(current.rmse)
    if selection_metric == "mae":
        return float(current.mae)
    if selection_metric != "balanced":
        raise ValueError(f"Unsupported checkpoint selection metric: {selection_metric}")
    persistence = persistence_metrics[
        (persistence_metrics["split"] == "validation") & (persistence_metrics["target"] == "all")
    ].iloc[0]
    rmse_scale = max(float(persistence.rmse), 1e-12)
    mae_scale = max(float(persistence.mae), 1e-12)
    return 0.5 * (float(current.rmse) / rmse_scale) + 0.5 * (float(current.mae) / mae_scale)


def prediction_examples(
    model: Any,
    frame: pd.DataFrame,
    dataset: WindowDataset,
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
    subset_dataset = WindowDataset(dataset.x_values, dataset.y_values, selected, dataset.history_length)
    loader = _data_loader(subset_dataset, batch_size=batch_size, shuffle=False, seed=0)
    rows = []
    offset = 0
    model.eval()
    with torch.no_grad():
        for x_batch, y_batch in loader:
            x_batch = x_batch.to(device=device, dtype=torch.float32)
            mu, logvar = model(x_batch)
            mu = apply_output_blend(mu, x_batch, blend_weights)
            sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0))).detach().cpu().numpy()
            mu_np = mu.detach().cpu().numpy()
            y_np = y_batch.detach().cpu().numpy()
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
    expected_config = {
        "history_length": args.history_length,
        "hidden_dim": args.hidden_dim,
        "num_layers": args.num_layers,
        "dropout": args.dropout,
        "residual_mode": args.residual_mode,
        "mse_weight": args.mse_weight,
        "checkpoint_selection_metric": args.checkpoint_selection_metric,
        "blend_selection_metric": args.blend_selection_metric,
        "blend_grid": _parse_float_grid(args.blend_grid),
    }
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
        "# PIPE/GRU-D Training Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.",
        "It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.",
        "Checkpoint selection evaluates the same blended output used by the final model.",
        "",
        "## Configuration",
        "",
        f"- History length: `{args.history_length}`",
        f"- Hidden dimension: `{args.hidden_dim}`",
        f"- GRU layers: `{args.num_layers}`",
        f"- Residual mode: `{args.residual_mode}`",
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
            "`blend_weight = 0` means pure persistence; `1` means pure neural prediction.",
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
            "Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.",
            "",
            "| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |",
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
    outputs = [path for path in outputs if path.exists()]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "model_version": MODEL_VERSION,
        "status": status,
        "config": {
            "history_length": int(args.history_length),
            "hidden_dim": int(args.hidden_dim),
            "num_layers": int(args.num_layers),
            "dropout": float(args.dropout),
            "residual_mode": args.residual_mode,
            "mse_weight": float(args.mse_weight),
            "checkpoint_selection_metric": args.checkpoint_selection_metric,
            "checkpoint_selection_uses_output_blend": True,
            "blend_grid": _parse_float_grid(args.blend_grid),
            "blend_selection_metric": args.blend_selection_metric,
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "learning_rate": float(args.learning_rate),
            "weight_decay": float(args.weight_decay),
            "random_seed": int(args.random_seed),
            "max_train_windows": args.max_train_windows,
            "max_eval_windows": args.max_eval_windows,
            "target_weights": TARGET_WEIGHTS,
            "input_columns": INPUT_COLUMNS,
            "target_columns": TARGET_COLUMNS,
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
        "inputs": [_file_record(args.sequences), _file_record(args.sequence_manifest)],
        "outputs": [_file_record(path) for path in outputs],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train minimal probabilistic PIPE/GRU-D model.")
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
    parser.add_argument("--history-length", type=int, default=6)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--residual-mode", choices=["add_last", "none"], default="add_last")
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
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    blend_grid = _parse_float_grid(args.blend_grid)

    torch = _require_torch()
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    set_reproducible_seed(args.random_seed)
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)

    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    print(f"sequence rows={len(frame):,}; elapsed={_elapsed(started_monotonic)}", flush=True)
    frame = prepare_window_frame(frame)
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
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
        residual_mode=args.residual_mode,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    weights = torch.from_numpy(make_loss_weights()).to(device=device, dtype=torch.float32)
    config = {
        "history_length": args.history_length,
        "input_dim": len(INPUT_COLUMNS),
        "target_dim": len(TARGET_COLUMNS),
        "hidden_dim": args.hidden_dim,
        "num_layers": args.num_layers,
        "dropout": args.dropout,
        "residual_mode": args.residual_mode,
        "mse_weight": args.mse_weight,
        "checkpoint_selection_metric": args.checkpoint_selection_metric,
        "blend_selection_metric": args.blend_selection_metric,
        "blend_grid": blend_grid,
    }

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
