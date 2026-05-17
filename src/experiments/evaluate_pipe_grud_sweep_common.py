#!/usr/bin/env python
"""Evaluate PIPE/GRU-D sweep trials on a common eligible window population."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows

from src.experiments.train_pipe_grud import (
    DEFAULT_SEQUENCES,
    INPUT_COLUMNS,
    TARGET_COLUMNS,
    WindowDataset,
    _require_torch,
    compare_to_persistence,
    evaluate_model,
    evaluate_persistence,
    load_sequences,
    make_loss_weights,
    make_model,
    prepare_window_frame,
    validation_selection_objective,
)


DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_SWEEP_SUMMARY = DEFAULT_REPORT_DIR / "pipe_grud_sweep_summary.csv"
DEFAULT_OUTPUT = DEFAULT_REPORT_DIR / "pipe_grud_sweep_common_eval.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_grud_sweep_common_eval_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_grud_sweep_common_eval_manifest.json"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


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


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def load_completed_trials(path: Path, max_rank: int | None) -> pd.DataFrame:
    summary = pd.read_csv(path)
    completed = summary[summary["status"].isin(["completed", "skipped_completed"])].copy()
    completed = completed[completed["selection_rank"].notna()].copy()
    completed["selection_rank"] = completed["selection_rank"].astype(int)
    if max_rank is not None and max_rank > 0:
        completed = completed[completed["selection_rank"] <= max_rank].copy()
    if completed.empty:
        raise ValueError("No completed sweep trials are available for common evaluation")
    return completed.sort_values(["selection_rank", "trial_id"]).reset_index(drop=True)


def eligible_common_indices(frame: pd.DataFrame, split: str, common_history_length: int) -> np.ndarray:
    mask = (frame["split"] == split) & (frame["window_position"] >= common_history_length - 1)
    return frame.index[mask].to_numpy(dtype="int64")


def _blend_tensor_from_artifact(artifact: dict[str, Any], device: Any) -> Any | None:
    torch = _require_torch()
    weights = artifact.get("output_blend_weights", {})
    if not weights:
        return None
    target_names = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    values = [float(weights[target]) for target in target_names]
    return torch.tensor(values, device=device, dtype=torch.float32)


def _metric_row(metrics: pd.DataFrame, split: str) -> dict[str, float | int]:
    row = metrics[(metrics["split"] == split) & (metrics["target"] == "all")].iloc[0]
    return {
        f"common_{split}_rows": int(row.rows),
        f"common_{split}_rmse": float(row.rmse),
        f"common_{split}_mae": float(row.mae),
        f"common_{split}_nll": float(row.nll),
        f"common_{split}_interval_90_coverage": float(row.interval_90_coverage),
    }


def _comparison_row(comparison: pd.DataFrame, split: str) -> dict[str, float]:
    row = comparison[(comparison["split"] == split) & (comparison["target"] == "all")].iloc[0]
    return {
        f"common_{split}_rmse_relative_improvement": float(row.rmse_relative_improvement),
        f"common_{split}_mae_relative_improvement": float(row.mae_relative_improvement),
    }


def common_selection_objective(
    metrics: pd.DataFrame,
    validation_loss: float,
    persistence_metrics: pd.DataFrame,
    metric_name: str,
) -> float:
    validation_metrics = metrics[metrics["split"] == "validation"].drop(columns=["split"]).reset_index(drop=True)
    return validation_selection_objective(validation_metrics, validation_loss, persistence_metrics, metric_name)


def evaluate_trial(
    trial: pd.Series,
    *,
    frame: pd.DataFrame,
    x_values: np.ndarray,
    y_values: np.ndarray,
    common_indices: dict[str, np.ndarray],
    persistence_metrics: pd.DataFrame,
    args: argparse.Namespace,
    device: Any,
    weights: Any,
) -> dict[str, Any]:
    torch = _require_torch()
    model_path = Path(str(trial.model_path))
    artifact = torch.load(model_path, map_location=device, weights_only=False)
    config = artifact["config"]
    history_length = int(config["history_length"])
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=int(config["hidden_dim"]),
        num_layers=int(config["num_layers"]),
        dropout=float(config["dropout"]),
        residual_mode=str(config["residual_mode"]),
    ).to(device)
    model.load_state_dict(artifact["model_state_dict"])
    blend_tensor = _blend_tensor_from_artifact(artifact, device)
    datasets = {
        split: WindowDataset(x_values, y_values, indices, history_length) for split, indices in common_indices.items()
    }
    metric_frames = []
    validation_loss = math.nan
    for split in ["train", "validation", "test"]:
        metrics, loss = evaluate_model(
            model,
            datasets[split],
            batch_size=args.batch_size,
            weights=weights,
            device=device,
            blend_weights=blend_tensor,
        )
        if split == "validation":
            validation_loss = float(loss)
        metrics.insert(0, "split", split)
        metric_frames.append(metrics)
    metrics_frame = pd.concat(metric_frames, ignore_index=True)
    comparison = compare_to_persistence(metrics_frame, persistence_metrics)
    common_objective = common_selection_objective(
        metrics_frame,
        validation_loss,
        persistence_metrics,
        args.checkpoint_selection_metric,
    )
    row: dict[str, Any] = {
        "trial_id": trial.trial_id,
        "original_selection_rank": int(trial.selection_rank),
        "common_history_length": int(args.common_history_length),
        "history_length": history_length,
        "hidden_dim": int(config["hidden_dim"]),
        "mse_weight": float(config["mse_weight"]),
        "learning_rate": float(trial.learning_rate),
        "random_seed": int(config["random_seed"]) if "random_seed" in config else int(trial.random_seed),
        "original_best_validation_objective": float(trial.best_validation_objective),
        "common_validation_objective": float(common_objective),
        "common_validation_loss": float(validation_loss),
        "model_path": model_path.as_posix(),
        "trial_report_path": str(trial.report_path),
    }
    for split in ["train", "validation", "test"]:
        row.update(_metric_row(metrics_frame, split))
        row.update(_comparison_row(comparison, split))
    return row


def rank_common(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    out = out.sort_values(
        ["common_validation_objective", "common_validation_rmse", "common_validation_mae", "common_test_rmse", "trial_id"]
    ).reset_index(drop=True)
    out.insert(0, "common_selection_rank", range(1, len(out) + 1))
    return out


def write_report(summary: pd.DataFrame, args: argparse.Namespace, started_at: datetime) -> None:
    best = summary.iloc[0] if not summary.empty else None
    lines = [
        "# PIPE/GRU-D Sweep Common-Window Evaluation",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This evaluation compares sweep trials on the same end-window population.",
        "It is required before promoting a trial when history length varies across the sweep.",
        "Ranking is selected on common validation windows only; common test metrics are included for audit.",
        "",
        "## Common Window",
        "",
        f"- Common history length: `{args.common_history_length}`",
        f"- Checkpoint selection metric: `{args.checkpoint_selection_metric}`",
        "",
        "## Best Common Validation Selection",
        "",
    ]
    if best is None:
        lines.append("No trial was evaluated.")
    else:
        lines.extend(
            [
                f"- Trial: `{best.trial_id}`",
                f"- Original sweep rank: `{int(best.original_selection_rank)}`",
                f"- History length: `{int(best.history_length)}`",
                f"- Hidden dimension: `{int(best.hidden_dim)}`",
                f"- MSE weight: `{_format_float(float(best.mse_weight))}`",
                f"- Common validation objective: `{_format_float(float(best.common_validation_objective))}`",
                f"- Common validation RMSE all: `{_format_float(float(best.common_validation_rmse))}`",
                f"- Common validation MAE all: `{_format_float(float(best.common_validation_mae))}`",
                f"- Common test RMSE all: `{_format_float(float(best.common_test_rmse))}`",
                f"- Common test MAE all: `{_format_float(float(best.common_test_mae))}`",
                f"- Common test RMSE improvement vs persistence: `{_format_float(float(best.common_test_rmse_relative_improvement))}`",
                f"- Common test MAE improvement vs persistence: `{_format_float(float(best.common_test_mae_relative_improvement))}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Ranked Common Evaluation",
            "",
            "| rank | trial | original rank | h | hidden | mse | validation objective | validation RMSE | validation MAE | test RMSE | test MAE |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(summary):
        lines.append(
            f"| {int(row.common_selection_rank)} | `{row.trial_id}` | {int(row.original_selection_rank)} | "
            f"{int(row.history_length)} | {int(row.hidden_dim)} | {_format_float(float(row.mse_weight))} | "
            f"{_format_float(float(row.common_validation_objective))} | "
            f"{_format_float(float(row.common_validation_rmse))} | {_format_float(float(row.common_validation_mae))} | "
            f"{_format_float(float(row.common_test_rmse))} | {_format_float(float(row.common_test_mae))} |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Common evaluation CSV: `{args.output}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    summary: pd.DataFrame,
    started_at: datetime,
    common_rows: dict[str, int],
) -> dict[str, Any]:
    best = summary.iloc[0].to_dict() if not summary.empty else {}
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "config": {
            "common_history_length": int(args.common_history_length),
            "checkpoint_selection_metric": args.checkpoint_selection_metric,
            "max_rank": args.max_rank,
            "batch_size": int(args.batch_size),
            "device": args.device,
        },
        "row_counts": {
            "evaluated_trials": int(len(summary)),
            "common_windows": common_rows,
        },
        "selection": best,
        "inputs": [_file_record(args.sequences), _file_record(args.sweep_summary)],
        "outputs": [_file_record(path) for path in [args.output, args.report] if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PIPE/GRU-D sweep trials on common windows.")
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--sweep-summary", type=Path, default=DEFAULT_SWEEP_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--common-history-length", type=int, default=None)
    parser.add_argument("--checkpoint-selection-metric", choices=["nll", "rmse", "mae", "balanced"], default="balanced")
    parser.add_argument("--max-rank", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    trials = load_completed_trials(args.sweep_summary, args.max_rank)
    if args.common_history_length is None:
        args.common_history_length = int(trials["history_length"].max())
    if args.common_history_length < int(trials["history_length"].max()):
        raise ValueError("--common-history-length must be >= the largest evaluated trial history length")
    torch = _require_torch()
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)
    print(f"loading sequences {args.sequences}", flush=True)
    frame = prepare_window_frame(load_sequences(args.sequences))
    x_values = frame[INPUT_COLUMNS].to_numpy(dtype="float32")
    y_values = frame[TARGET_COLUMNS].to_numpy(dtype="float32")
    common_indices = {
        split: eligible_common_indices(frame, split, args.common_history_length) for split in ["train", "validation", "test"]
    }
    common_rows = {split: int(len(indices)) for split, indices in common_indices.items()}
    print(f"common windows={common_rows}", flush=True)
    if common_rows["train"] == 0 or common_rows["validation"] == 0 or common_rows["test"] == 0:
        raise ValueError("Common train, validation, and test windows must all be non-empty")
    persistence_metrics = evaluate_persistence(frame, common_indices)
    weights = torch.from_numpy(make_loss_weights()).to(device=device, dtype=torch.float32)
    rows = []
    for index, trial in enumerate(dataframe_rows(trials), start=1):
        print(f"evaluating trial {index}/{len(trials)}: {trial.trial_id}", flush=True)
        rows.append(
            evaluate_trial(
                pd.Series(trial._asdict()),
                frame=frame,
                x_values=x_values,
                y_values=y_values,
                common_indices=common_indices,
                persistence_metrics=persistence_metrics,
                args=args,
                device=device,
                weights=weights,
            )
        )
    summary = rank_common(pd.DataFrame(rows))
    _write_csv_atomic(summary, args.output)
    write_report(summary, args, started_at)
    manifest = manifest_payload(args=args, summary=summary, started_at=started_at, common_rows=common_rows)
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.output}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
