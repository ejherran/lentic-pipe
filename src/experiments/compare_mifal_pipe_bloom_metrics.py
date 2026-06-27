#!/usr/bin/env python
"""Compare calibrated MIFAL bloom metrics against PIPE bloom metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from src.pandas_utils import dataframe_rows


COMPARISON_VERSION = "mifal_pipe_bloom_metric_comparison_v0"
DEFAULT_MIFAL_METRICS = Path("reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_metrics.csv")
DEFAULT_PIPE_METRICS = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_metrics.csv")
DEFAULT_OUTPUT_DIR = Path("reports/mifal")
DEFAULT_OUTPUT_NAME = "mifal_vs_pipe_grud_bloom_validation_comparison"
OUTPUT_SUFFIXES = {
    "comparison": "comparison.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
MIFAL_REQUIRED_COLUMNS = [
    "model_name",
    "surface",
    "split",
    "horizon_months",
    "rows",
    "positive_rows",
    "predicted_positive_rate",
    "precision",
    "recall",
    "fbeta",
    "pr_auc",
    "brier",
]
PIPE_REQUIRED_COLUMNS = [
    "target_event",
    "split",
    "rollout_horizon_months",
    "rows",
    "positive_rows",
    "predicted_positive_rate",
    "precision",
    "recall",
    "fbeta",
    "pr_auc",
    "brier",
]
COMPARISON_COLUMNS = [
    "comparison_version",
    "target_event",
    "split",
    "horizon_months",
    "mifal_model",
    "mifal_surface",
    "pipe_model",
    "rows",
    "pipe_rows",
    "row_delta",
    "positive_rows",
    "pipe_positive_rows",
    "positive_row_delta",
    "mifal_predicted_positive_rate",
    "pipe_predicted_positive_rate",
    "delta_predicted_positive_rate",
    "mifal_precision",
    "pipe_precision",
    "delta_precision",
    "mifal_recall",
    "pipe_recall",
    "delta_recall",
    "mifal_fbeta",
    "pipe_fbeta",
    "delta_fbeta",
    "mifal_pr_auc",
    "pipe_pr_auc",
    "delta_pr_auc",
    "mifal_brier",
    "pipe_brier",
    "delta_brier",
]


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


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": _manifest_path(path), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, default=_json_default)
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


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {key: output_dir / f"{output_name}_{suffix}" for key, suffix in OUTPUT_SUFFIXES.items()}


def _read_csv(path: Path, required: list[str], label: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} metrics are missing required columns: {missing}")
    return frame.copy()


def load_mifal_metrics(path: Path, splits: list[str]) -> pd.DataFrame:
    frame = _read_csv(path, MIFAL_REQUIRED_COLUMNS, "MIFAL")
    frame = frame[frame["split"].isin(splits)].copy()
    frame["horizon_months"] = pd.to_numeric(frame["horizon_months"], errors="raise").astype("int16")
    return frame


def load_pipe_metrics(path: Path, splits: list[str], target_event: str) -> pd.DataFrame:
    frame = _read_csv(path, PIPE_REQUIRED_COLUMNS, "PIPE")
    frame = frame[(frame["target_event"] == target_event) & (frame["split"].isin(splits))].copy()
    frame = frame.rename(columns={"rollout_horizon_months": "horizon_months"})
    frame["horizon_months"] = pd.to_numeric(frame["horizon_months"], errors="raise").astype("int16")
    return frame


def _metric_delta(row: Any, pipe: pd.Series, metric: str) -> float:
    return float(getattr(row, metric)) - float(pipe[metric])


def build_comparison(mifal: pd.DataFrame, pipe: pd.DataFrame, pipe_model: str, target_event: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in dataframe_rows(mifal.sort_values(["model_name", "split", "horizon_months"])):
        match = pipe[(pipe["split"] == row.split) & (pipe["horizon_months"] == int(row.horizon_months))]
        if match.empty:
            continue
        pipe_row = match.iloc[0]
        rows.append(
            {
                "comparison_version": COMPARISON_VERSION,
                "target_event": target_event,
                "split": row.split,
                "horizon_months": int(row.horizon_months),
                "mifal_model": row.model_name,
                "mifal_surface": row.surface,
                "pipe_model": pipe_model,
                "rows": int(row.rows),
                "pipe_rows": int(pipe_row["rows"]),
                "row_delta": int(row.rows) - int(pipe_row["rows"]),
                "positive_rows": int(row.positive_rows),
                "pipe_positive_rows": int(pipe_row["positive_rows"]),
                "positive_row_delta": int(row.positive_rows) - int(pipe_row["positive_rows"]),
                "mifal_predicted_positive_rate": float(row.predicted_positive_rate),
                "pipe_predicted_positive_rate": float(pipe_row["predicted_positive_rate"]),
                "delta_predicted_positive_rate": _metric_delta(row, pipe_row, "predicted_positive_rate"),
                "mifal_precision": float(row.precision),
                "pipe_precision": float(pipe_row["precision"]),
                "delta_precision": _metric_delta(row, pipe_row, "precision"),
                "mifal_recall": float(row.recall),
                "pipe_recall": float(pipe_row["recall"]),
                "delta_recall": _metric_delta(row, pipe_row, "recall"),
                "mifal_fbeta": float(row.fbeta),
                "pipe_fbeta": float(pipe_row["fbeta"]),
                "delta_fbeta": _metric_delta(row, pipe_row, "fbeta"),
                "mifal_pr_auc": float(row.pr_auc),
                "pipe_pr_auc": float(pipe_row["pr_auc"]),
                "delta_pr_auc": _metric_delta(row, pipe_row, "pr_auc"),
                "mifal_brier": float(row.brier),
                "pipe_brier": float(pipe_row["brier"]),
                "delta_brier": _metric_delta(row, pipe_row, "brier"),
            }
        )
    if not rows:
        raise ValueError("No matching MIFAL/PIPE metric rows were found")
    return pd.DataFrame(rows)[COMPARISON_COLUMNS].sort_values(["mifal_model", "split", "horizon_months"]).reset_index(drop=True)


def write_report(args: argparse.Namespace, comparison: pd.DataFrame) -> None:
    paths = output_paths(args.output_dir, args.output_name)
    lines = [
        "# MIFAL vs PIPE Bloom Metric Comparison v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Target event: `{args.target_event}`",
        f"Splits: `{', '.join(args.evaluation_splits)}`",
        f"MIFAL metrics: `{args.mifal_metrics.as_posix()}`",
        f"PIPE metrics: `{args.pipe_metrics.as_posix()}`",
        "",
        "This is a metric-level comparison for `bloom_h` only. MIFAL does not emit the PIPE `irc_alert` target.",
        "Negative delta Brier is favorable for MIFAL; positive deltas for PR-AUC, F-beta, precision, and recall are favorable for MIFAL.",
        "",
        "## Comparison",
        "",
        "| MIFAL model | split | horizon | rows | delta PR-AUC | delta Brier | delta F-beta | delta precision | delta recall |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(comparison):
        lines.append(
            f"| `{row.mifal_model}` | `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
            f"{_format_float(float(row.delta_pr_auc))} | {_format_float(float(row.delta_brier))} | "
            f"{_format_float(float(row.delta_fbeta))} | {_format_float(float(row.delta_precision))} | "
            f"{_format_float(float(row.delta_recall))} |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Comparison: `{paths['comparison'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(args: argparse.Namespace, comparison: pd.DataFrame, started_at: datetime) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    return {
        "status": "completed",
        "comparison_version": COMPARISON_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "mifal_metrics": args.mifal_metrics.as_posix(),
            "pipe_metrics": args.pipe_metrics.as_posix(),
            "pipe_model": args.pipe_model,
            "target_event": args.target_event,
            "evaluation_splits": args.evaluation_splits,
            "output_name": args.output_name,
        },
        "row_counts": {"comparison_rows": int(len(comparison))},
        "inputs": [_file_record(args.mifal_metrics), _file_record(args.pipe_metrics)],
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare calibrated MIFAL bloom metrics against PIPE bloom metrics.")
    parser.add_argument("--mifal-metrics", type=Path, default=DEFAULT_MIFAL_METRICS)
    parser.add_argument("--pipe-metrics", type=Path, default=DEFAULT_PIPE_METRICS)
    parser.add_argument("--pipe-model", default="pipe_grud_adaptive_wqp_focused")
    parser.add_argument("--target-event", default="bloom_h")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="validation")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    if args.target_event != "bloom_h":
        raise ValueError("This comparison is restricted to bloom_h because MIFAL does not emit irc_alert")
    mifal = load_mifal_metrics(args.mifal_metrics, args.evaluation_splits)
    pipe = load_pipe_metrics(args.pipe_metrics, args.evaluation_splits, args.target_event)
    comparison = build_comparison(mifal, pipe, args.pipe_model, args.target_event)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(comparison, paths["comparison"])
    write_report(args, comparison)
    manifest = manifest_payload(args, comparison, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"MIFAL vs PIPE comparison report written: {paths['report']}", flush=True)
    print(f"MIFAL vs PIPE comparison manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
