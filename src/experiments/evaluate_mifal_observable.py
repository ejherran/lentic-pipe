#!/usr/bin/env python
"""Run an isolated observable-surface MIFAL-ED/T2 smoke evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics import average_precision_score, brier_score_loss, matthews_corrcoef, precision_score, recall_score, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from src.mifal.ed_t2 import Interval, MIFALEDT2, interval_coverage, winkler_interval_score
from src.mifal.panel_adapter import (
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA,
    MIFAL_SURFACES,
    PANEL_ADAPTER_COLUMNS,
    add_previous_chla_columns,
    panel_row_to_mifal_payload,
    payload_availability,
)
from src.pandas_utils import dataframe_rows, group_key_tuple


MIFAL_OBSERVABLE_VERSION = "mifal_observable_v0"
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_REPORT_DIR = Path("reports/mifal")
DEFAULT_OUTPUT_NAME = "mifal_observable_smoke"
OUTPUT_SUFFIXES = {
    "predictions": "predictions.csv",
    "metrics": "metrics.csv",
    "availability": "availability.csv",
    "examples": "examples.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
SPLIT_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split", "bloom_h", "target_risk_chla_h"]
ID_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
REFERENCE_ORIGIN_COLUMNS = ["source_id", "site_id", "origin_year_month", "split"]
PREDICTED_VARIABLES = ["Tw", "TP", "TN", "Secchi", "Turb", "DOb", "Chl", "Chl_prev"]


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


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def _parse_int_csv(value: str) -> list[int]:
    try:
        return [int(item) for item in _parse_csv_list(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected comma-separated integers") from exc


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def _surface(value: str) -> str:
    if value not in MIFAL_SURFACES:
        raise argparse.ArgumentTypeError(f"Expected one of {', '.join(MIFAL_SURFACES)}")
    return value


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {key: output_dir / f"{output_name}_{suffix}" for key, suffix in OUTPUT_SUFFIXES.items()}


def _parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema.names)


def _available_columns(path: Path, requested: list[str]) -> list[str]:
    available = set(_parquet_columns(path))
    return [column for column in requested if column in available]


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported table suffix for {path}: expected .csv or .parquet")


def load_reference_keys(path: Path | None) -> tuple[pd.DataFrame | None, list[str]]:
    if path is None:
        return None, []
    reference = _read_table(path)
    reference = reference.rename(columns={"rollout_horizon_months": "horizon_months"})
    missing_origin = sorted(set(REFERENCE_ORIGIN_COLUMNS) - set(reference.columns))
    if missing_origin:
        raise ValueError(f"Reference rows are missing required origin columns: {missing_origin}")
    columns = [column for column in ID_COLUMNS if column in reference.columns]
    if "horizon_months" in columns:
        reference["horizon_months"] = pd.to_numeric(reference["horizon_months"], errors="raise").astype("int16")
    return reference[columns].drop_duplicates().copy(), columns


def load_surface(args: argparse.Namespace) -> pd.DataFrame:
    split_columns = set(_parquet_columns(args.splits))
    missing_split_columns = sorted(set(SPLIT_COLUMNS) - split_columns)
    if missing_split_columns:
        raise ValueError(f"Splits file is missing required columns: {missing_split_columns}")
    splits = pd.read_parquet(args.splits, columns=SPLIT_COLUMNS)
    splits = splits[splits["horizon_months"].isin(args.horizons)].copy()
    splits = splits[splits["split"].isin(args.evaluation_splits)].copy()
    reference_keys, reference_columns = load_reference_keys(args.reference_rows)
    if reference_keys is not None:
        splits = splits.merge(reference_keys, on=reference_columns, how="inner", validate="many_to_one")
    if args.max_rows_per_split is not None:
        sampled: list[pd.DataFrame] = []
        for _, group in splits.groupby(["split", "horizon_months"], sort=False):
            n = min(args.max_rows_per_split, len(group))
            sampled.append(group.sample(n=n, random_state=args.random_seed))
        splits = pd.concat(sampled, ignore_index=True) if sampled else splits.iloc[0:0].copy()

    read_columns = _available_columns(args.panel, PANEL_ADAPTER_COLUMNS)
    required = {"source_id", "site_id", "year_month", "mean_chlorophyll_a_ugL"}
    missing_panel_columns = sorted(required - set(read_columns))
    if missing_panel_columns:
        raise ValueError(f"Panel file is missing required adapter columns: {missing_panel_columns}")
    panel = pd.read_parquet(args.panel, columns=read_columns)
    panel_with_prev = add_previous_chla_columns(panel)
    frame = splits.merge(
        panel_with_prev,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
    )
    numeric_columns = frame.select_dtypes(include=[np.number]).columns
    frame[numeric_columns] = frame[numeric_columns].replace([np.inf, -np.inf], np.nan)
    frame["bloom_h"] = frame["bloom_h"].astype(bool).astype("int8")
    frame["target_risk_chla_h"] = pd.to_numeric(frame["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    return frame


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(math.sqrt(np.mean((y_true - y_pred) ** 2)))


def _f2_score(precision: float, recall: float) -> float:
    if pd.isna(precision) or pd.isna(recall):
        return float("nan")
    denominator = 4.0 * precision + recall
    return 0.0 if denominator == 0.0 else float(5.0 * precision * recall / denominator)


def _top_factor(result: dict[str, object]) -> str | None:
    factors = result.get("dominant_factors")
    if not isinstance(factors, list) or not factors:
        return None
    first = factors[0]
    if isinstance(first, tuple) and first:
        return str(first[0])
    return None


def run_predictions(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    model = MIFALEDT2()
    rows: list[dict[str, object]] = []
    for row in dataframe_rows(frame):
        row_dict = row._asdict()
        payload = panel_row_to_mifal_payload(row_dict, surface=args.surface)
        result = model.step(
            payload,
            dt_days=float(row_dict["horizon_months"]) * 30.4375,
            update_state=False,
            compute_voi=bool(args.include_voi),
        )
        interval = cast(Interval, result["risk_interval"])
        prediction = {
            "mifal_observable_version": MIFAL_OBSERVABLE_VERSION,
            "surface": args.surface,
            "source_id": row_dict["source_id"],
            "site_id": row_dict["site_id"],
            "origin_year_month": row_dict["origin_year_month"],
            "horizon_months": int(row_dict["horizon_months"]),
            "split": row_dict["split"],
            "bloom_h": int(row_dict["bloom_h"]),
            "target_risk_chla_h": float(row_dict["target_risk_chla_h"]),
            "risk_interval_lo": float(interval[0]),
            "risk_interval_hi": float(interval[1]),
            "risk_conservative": float(cast(float, result["risk_conservative"])),
            "uncertainty": float(cast(float, result["uncertainty"])),
            "interval_confidence": float(cast(float, result["interval_confidence"])),
            "data_reliability": float(cast(float, result["data_reliability"])),
            "confidence": float(cast(float, result["confidence"])),
            "alert_class": str(result["alert_class"]),
            "observation_reliability": float(cast(float, result["observation_reliability"])),
            "top_factor": _top_factor(result),
            "recommended_sampling": result.get("recommended_sampling"),
            "payload_variables": ",".join(sorted(payload)),
        }
        prediction.update(payload_availability(payload))
        rows.append(prediction)
    return pd.DataFrame(rows)


def summarize_availability(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group_columns in [[], ["split"], ["split", "horizon_months"]]:
        grouped = [((), predictions)] if not group_columns else predictions.groupby(group_columns, dropna=False, sort=True)
        for key, group in grouped:
            key_values = key if isinstance(key, tuple) else (key,)
            base = {column: value for column, value in zip(group_columns, key_values, strict=True)}
            for variable in PREDICTED_VARIABLES:
                column = f"has_{variable}"
                present = int(group[column].sum()) if column in group else 0
                rows.append(
                    {
                        "mifal_observable_version": MIFAL_OBSERVABLE_VERSION,
                        "surface": str(predictions["surface"].iloc[0]) if len(predictions) else "NA",
                        "group": "overall" if not group_columns else "_".join(group_columns),
                        **base,
                        "mifal_variable": variable,
                        "rows": int(len(group)),
                        "present_rows": present,
                        "coverage_rate": float(present / len(group)) if len(group) else float("nan"),
                    }
                )
    return pd.DataFrame(rows)


def prediction_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_columns = ["split", "horizon_months"]
    for key, group in predictions.groupby(group_columns, dropna=False, sort=True):
        split, horizon = group_key_tuple(key)
        y = group["bloom_h"].to_numpy(dtype="int8")
        target_risk = group["target_risk_chla_h"].to_numpy(dtype="float64")
        score = group["risk_conservative"].clip(0.0, 1.0).to_numpy(dtype="float64")
        pred = (score >= 0.5).astype("int8")
        precision = _safe_metric(precision_score, y, pred, zero_division=0)
        recall = _safe_metric(recall_score, y, pred, zero_division=0)
        intervals = list(zip(group["risk_interval_lo"].astype(float), group["risk_interval_hi"].astype(float), strict=True))
        rows.append(
            {
                "mifal_observable_version": MIFAL_OBSERVABLE_VERSION,
                "surface": str(group["surface"].iloc[0]),
                "split": split,
                "horizon_months": int(horizon),
                "rows": int(len(group)),
                "positive_rows": int(y.sum()),
                "positive_rate": float(y.mean()) if len(y) else float("nan"),
                "predicted_positive_rows": int(pred.sum()),
                "alert_rate": float(pred.mean()) if len(pred) else float("nan"),
                "threshold": 0.5,
                "precision": precision,
                "recall": recall,
                "f2": _f2_score(precision, recall),
                "mcc": _safe_metric(matthews_corrcoef, y, pred),
                "pr_auc": _safe_metric(average_precision_score, y, score),
                "roc_auc": _safe_metric(roc_auc_score, y, score),
                "brier": _safe_metric(brier_score_loss, y, score),
                "rmse_risk": _root_mean_squared_error(target_risk, score),
                "mae_risk": float(np.mean(np.abs(target_risk - score))),
                "interval_coverage_risk": interval_coverage(list(target_risk), intervals),
                "interval_mean_width": float((group["risk_interval_hi"] - group["risk_interval_lo"]).mean()),
                "winkler_score_risk": float(np.mean([winkler_interval_score(y_value, interval) for y_value, interval in zip(target_risk, intervals, strict=True)])),
                "mean_uncertainty": float(group["uncertainty"].mean()),
                "mean_data_reliability": float(group["data_reliability"].mean()),
                "mean_confidence": float(group["confidence"].mean()),
            }
        )
    return pd.DataFrame(rows)


def select_examples(predictions: pd.DataFrame, max_examples: int) -> pd.DataFrame:
    if predictions.empty or max_examples <= 0:
        return predictions.iloc[0:0].copy()
    sort_columns = ["uncertainty", "risk_conservative"]
    return predictions.sort_values(sort_columns, ascending=[False, False]).head(max_examples).reset_index(drop=True)


def write_report(args: argparse.Namespace, predictions: pd.DataFrame, metrics: pd.DataFrame, availability: pd.DataFrame) -> None:
    paths = output_paths(args.output_dir, args.output_name)
    lines = [
        "# MIFAL-ED/T2 Observable Smoke Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Surface: `{args.surface}`",
        f"Rows evaluated: `{_format_int(len(predictions))}`",
        f"Reference rows: `{args.reference_rows.as_posix() if args.reference_rows else 'none'}`",
        f"Include VOI: `{bool(args.include_voi)}`",
        "",
        "This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.",
        "",
        "## Metrics",
        "",
        "| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(metrics):
        lines.append(
            f"| `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
            f"{_format_int(int(row.positive_rows))} | {_format_float(float(row.pr_auc))} | "
            f"{_format_float(float(row.brier))} | {_format_float(float(row.precision))} | "
            f"{_format_float(float(row.recall))} | {_format_float(float(row.f2))} | "
            f"{_format_float(float(row.rmse_risk))} | {_format_float(float(row.interval_coverage_risk))} | "
            f"{_format_float(float(row.interval_mean_width))} | {_format_float(float(row.mean_data_reliability))} |"
        )

    overall_availability = availability[availability["group"] == "overall"] if not availability.empty else pd.DataFrame()
    lines.extend(
        [
            "",
            "## Payload Availability",
            "",
            "| variable | rows | present rows | coverage |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(overall_availability):
        lines.append(
            f"| `{row.mifal_variable}` | {_format_int(int(row.rows))} | {_format_int(int(row.present_rows))} | "
            f"{_format_float(float(row.coverage_rate))} |"
        )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Predictions: `{paths['predictions'].as_posix()}`",
            f"- Metrics: `{paths['metrics'].as_posix()}`",
            f"- Availability: `{paths['availability'].as_posix()}`",
            f"- Examples: `{paths['examples'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(args: argparse.Namespace, frame: pd.DataFrame, predictions: pd.DataFrame, metrics: pd.DataFrame, availability: pd.DataFrame, examples: pd.DataFrame, started_at: datetime) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    return {
        "status": "completed",
        "mifal_observable_version": MIFAL_OBSERVABLE_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "panel": args.panel.as_posix(),
            "splits": args.splits.as_posix(),
            "reference_rows": args.reference_rows.as_posix() if args.reference_rows else None,
            "surface": args.surface,
            "horizons": args.horizons,
            "evaluation_splits": args.evaluation_splits,
            "max_rows_per_split": args.max_rows_per_split,
            "random_seed": args.random_seed,
            "include_voi": bool(args.include_voi),
            "output_name": args.output_name,
        },
        "inputs": [_file_record(path) for path in [args.panel, args.splits, args.reference_rows] if path is not None],
        "row_counts": {
            "surface_rows": int(len(frame)),
            "prediction_rows": int(len(predictions)),
            "metric_rows": int(len(metrics)),
            "availability_rows": int(len(availability)),
            "example_rows": int(len(examples)),
        },
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an isolated MIFAL observable-surface smoke evaluation.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--reference-rows", type=Path, default=None)
    parser.add_argument("--surface", type=_surface, default=MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA)
    parser.add_argument("--horizons", type=_parse_int_csv, default="1,2,3")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="validation,test")
    parser.add_argument("--max-rows-per-split", type=int, default=250)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--include-voi", action="store_true")
    parser.add_argument("--max-examples", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    print(f"loading MIFAL observable surface from {args.splits} and {args.panel}", flush=True)
    frame = load_surface(args)
    print(f"running MIFAL on {len(frame):,} rows", flush=True)
    predictions = run_predictions(frame, args)
    metrics = prediction_metrics(predictions)
    availability = summarize_availability(predictions)
    examples = select_examples(predictions, args.max_examples)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(predictions, paths["predictions"])
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(availability, paths["availability"])
    _write_csv_atomic(examples, paths["examples"])
    write_report(args, predictions, metrics, availability)
    manifest = manifest_payload(args, frame, predictions, metrics, availability, examples, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"MIFAL observable report written: {paths['report']}", flush=True)
    print(f"MIFAL observable manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
