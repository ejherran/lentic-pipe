#!/usr/bin/env python
"""Evaluate calibrated MIFAL surfaces on an exact matched key surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from src.mifal.ed_t2 import interval_coverage, winkler_interval_score
from src.pandas_utils import dataframe_rows, group_key_tuple


MIFAL_MATCHED_VERSION = "mifal_observable_matched_surface_v0"
DEFAULT_REPORT_DIR = Path("reports/mifal")
DEFAULT_OUTPUT_NAME = "mifal_observable_current_vs_no_current_matched_validation_smoke"
DEFAULT_PREDICTIONS = [
    "no_current_chla=reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_calibrated_predictions.csv",
    "current_chla=reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_calibrated_predictions.csv",
]
OUTPUT_SUFFIXES = {
    "matched_rows": "matched_rows.csv",
    "metrics": "metrics.csv",
    "comparison": "comparison.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
MATCH_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
ORIGIN_COLUMNS = ["source_id", "site_id", "origin_year_month", "split"]
REQUIRED_COLUMNS = [
    *MATCH_COLUMNS,
    "bloom_h",
    "target_risk_chla_h",
]
METRIC_COLUMNS = [
    "mifal_matched_version",
    "model_name",
    "surface",
    "split",
    "horizon_months",
    "rows",
    "positive_rows",
    "positive_rate",
    "predicted_positive_rows",
    "predicted_positive_rate",
    "threshold",
    "tn",
    "fp",
    "fn",
    "tp",
    "precision",
    "recall",
    "specificity",
    "macro_f1",
    "fbeta",
    "mcc",
    "pr_auc",
    "roc_auc",
    "brier",
    "rmse_risk",
    "mae_risk",
    "interval_coverage_risk",
    "interval_mean_width",
    "winkler_score_risk",
    "mean_uncertainty",
    "mean_data_reliability",
    "mean_confidence",
]
COMPARISON_COLUMNS = [
    "mifal_matched_version",
    "baseline_model",
    "comparison_model",
    "split",
    "horizon_months",
    "rows",
    "delta_pr_auc",
    "delta_brier",
    "delta_fbeta",
    "delta_mcc",
    "delta_precision",
    "delta_recall",
    "delta_rmse_risk",
    "delta_mae_risk",
    "delta_interval_width",
    "delta_data_reliability",
]


@dataclass(frozen=True)
class PredictionSpec:
    name: str
    path: Path


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


def _safe_model_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Prediction names must use only letters, numbers, underscores, and hyphens")
    return normalized


def parse_prediction_spec(value: str) -> PredictionSpec:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Prediction specs must use NAME=PATH")
    name, raw_path = value.split("=", 1)
    return PredictionSpec(name=_safe_model_name(name), path=Path(raw_path))


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {key: output_dir / f"{output_name}_{suffix}" for key, suffix in OUTPUT_SUFFIXES.items()}


def _binary_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype("int8")
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).astype("int8")
    normalized = values.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y"}).astype("int8")


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _safe_rate(numerator: float, denominator: float) -> float:
    return float("nan") if denominator == 0.0 else float(numerator / denominator)


def _root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(math.sqrt(np.mean((y_true - y_pred) ** 2)))


def _f_beta(precision: float, recall: float, beta: float) -> float:
    if pd.isna(precision) or pd.isna(recall):
        return float("nan")
    beta2 = beta**2
    denominator = beta2 * precision + recall
    if denominator == 0.0:
        return 0.0
    return float((1.0 + beta2) * precision * recall / denominator)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported table suffix for {path}: expected .csv or .parquet")


def _score_column(frame: pd.DataFrame) -> str:
    if "mifal_probability_bloom_calibrated" in frame.columns:
        return "mifal_probability_bloom_calibrated"
    if "risk_conservative" in frame.columns:
        return "risk_conservative"
    raise ValueError("MIFAL predictions must include mifal_probability_bloom_calibrated or risk_conservative")


def read_predictions(spec: PredictionSpec) -> pd.DataFrame:
    frame = _read_table(spec.path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"{spec.path} is missing required columns: {missing}")
    duplicated = frame.duplicated(MATCH_COLUMNS)
    if duplicated.any():
        raise ValueError(f"{spec.path} contains duplicate matched keys")
    out = frame.copy()
    out["model_name"] = spec.name
    out["bloom_h"] = _binary_series(out["bloom_h"])
    out["target_risk_chla_h"] = pd.to_numeric(out["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    out["horizon_months"] = pd.to_numeric(out["horizon_months"], errors="raise").astype("int16")
    score_column = _score_column(out)
    out["mifal_matched_score"] = pd.to_numeric(out[score_column], errors="coerce").clip(0.0, 1.0)
    if "mifal_predicted_bloom_h" in out.columns:
        out["mifal_matched_prediction"] = _binary_series(out["mifal_predicted_bloom_h"])
    elif "mifal_bloom_probability_threshold" in out.columns:
        threshold = pd.to_numeric(out["mifal_bloom_probability_threshold"], errors="coerce").fillna(0.5)
        out["mifal_matched_prediction"] = (out["mifal_matched_score"] >= threshold).astype("int8")
    else:
        out["mifal_matched_prediction"] = (out["mifal_matched_score"] >= 0.5).astype("int8")
    if "mifal_bloom_probability_threshold" in out.columns:
        out["mifal_matched_threshold"] = pd.to_numeric(out["mifal_bloom_probability_threshold"], errors="coerce").fillna(0.5)
    else:
        out["mifal_matched_threshold"] = 0.5
    for column in ["uncertainty", "data_reliability", "confidence", "risk_interval_lo", "risk_interval_hi"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
        else:
            out[column] = np.nan
    if "surface" not in out.columns:
        out["surface"] = spec.name
    return out


def read_reference_keys(path: Path) -> tuple[pd.DataFrame, list[str]]:
    reference = _read_table(path)
    reference = reference.rename(columns={"rollout_horizon_months": "horizon_months"})
    missing_origin = sorted(set(ORIGIN_COLUMNS) - set(reference.columns))
    if missing_origin:
        raise ValueError(f"Reference rows are missing required origin columns: {missing_origin}")
    columns = [column for column in MATCH_COLUMNS if column in reference.columns]
    if "horizon_months" in columns:
        reference["horizon_months"] = pd.to_numeric(reference["horizon_months"], errors="raise").astype("int16")
    return reference[columns].drop_duplicates().copy(), columns


def build_matched_keys(
    predictions: dict[str, pd.DataFrame],
    evaluation_splits: list[str],
    reference_keys: pd.DataFrame | None,
    reference_columns: list[str],
    max_rows_per_group: int | None,
    random_seed: int,
) -> pd.DataFrame:
    items = list(predictions.items())
    keys = items[0][1][MATCH_COLUMNS].drop_duplicates().copy()
    for _, frame in items[1:]:
        keys = keys.merge(frame[MATCH_COLUMNS].drop_duplicates(), on=MATCH_COLUMNS, how="inner", validate="one_to_one")
    keys = keys[keys["split"].isin(evaluation_splits)].copy()
    if reference_keys is not None:
        keys = keys.merge(reference_keys, on=reference_columns, how="inner", validate="many_to_one")
    keys = keys.drop_duplicates(MATCH_COLUMNS).sort_values(MATCH_COLUMNS, kind="mergesort").reset_index(drop=True)
    if max_rows_per_group is not None:
        sampled: list[pd.DataFrame] = []
        for _, group in keys.groupby(["split", "horizon_months"], sort=True):
            n = min(int(max_rows_per_group), len(group))
            sampled.append(group.sample(n=n, random_state=random_seed))
        keys = pd.concat(sampled, ignore_index=True) if sampled else keys.iloc[0:0].copy()
        keys = keys.sort_values(MATCH_COLUMNS, kind="mergesort").reset_index(drop=True)
    if keys.empty:
        raise ValueError("No matched MIFAL rows found for the requested inputs")
    return keys


def build_long_matched_rows(predictions: dict[str, pd.DataFrame], keys: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    keep_columns = [
        "model_name",
        "surface",
        *MATCH_COLUMNS,
        "bloom_h",
        "target_risk_chla_h",
        "mifal_matched_score",
        "mifal_matched_prediction",
        "mifal_matched_threshold",
        "risk_conservative",
        "risk_interval_lo",
        "risk_interval_hi",
        "uncertainty",
        "data_reliability",
        "confidence",
        "top_factor",
        "recommended_sampling",
    ]
    for _, frame in predictions.items():
        matched = keys.merge(frame, on=MATCH_COLUMNS, how="left", validate="one_to_one")
        for column in keep_columns:
            if column not in matched.columns:
                matched[column] = np.nan
        rows.append(matched[keep_columns])
    return pd.concat(rows, ignore_index=True, sort=False)


def _metric_row(group: pd.DataFrame, beta: float) -> dict[str, Any]:
    score = _clip01(group["mifal_matched_score"])
    actual = group["bloom_h"].to_numpy(dtype="int8")
    predicted = group["mifal_matched_prediction"].to_numpy(dtype="int8")
    tn, fp, fn, tp = [int(value) for value in confusion_matrix(actual, predicted, labels=[0, 1]).ravel()]
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    target_risk = group["target_risk_chla_h"].to_numpy(dtype="float64")
    interval_valid = group["risk_interval_lo"].notna() & group["risk_interval_hi"].notna() & group["target_risk_chla_h"].notna()
    intervals = list(
        zip(
            group.loc[interval_valid, "risk_interval_lo"].astype(float),
            group.loc[interval_valid, "risk_interval_hi"].astype(float),
            strict=True,
        )
    )
    interval_targets = group.loc[interval_valid, "target_risk_chla_h"].astype(float).to_list()
    interval_width = group["risk_interval_hi"] - group["risk_interval_lo"]
    return {
        "mifal_matched_version": MIFAL_MATCHED_VERSION,
        "model_name": str(group["model_name"].iloc[0]),
        "surface": str(group["surface"].iloc[0]),
        "split": str(group["split"].iloc[0]),
        "horizon_months": int(group["horizon_months"].iloc[0]),
        "rows": int(len(group)),
        "positive_rows": int(actual.sum()),
        "positive_rate": float(actual.mean()) if len(actual) else float("nan"),
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else float("nan"),
        "threshold": float(group["mifal_matched_threshold"].median()),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "specificity": _safe_rate(tn, tn + fp),
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "fbeta": _f_beta(precision, recall, beta),
        "mcc": _safe_metric(matthews_corrcoef, actual, predicted),
        "pr_auc": _safe_metric(average_precision_score, actual, score),
        "roc_auc": _safe_metric(roc_auc_score, actual, score),
        "brier": _safe_metric(brier_score_loss, actual, score),
        "rmse_risk": _root_mean_squared_error(target_risk, score),
        "mae_risk": float(np.mean(np.abs(target_risk - score))),
        "interval_coverage_risk": interval_coverage(interval_targets, intervals) if intervals else float("nan"),
        "interval_mean_width": float(interval_width.mean()) if interval_width.notna().any() else float("nan"),
        "winkler_score_risk": float(
            np.mean([winkler_interval_score(y_value, interval) for y_value, interval in zip(interval_targets, intervals, strict=True)])
        )
        if intervals
        else float("nan"),
        "mean_uncertainty": float(group["uncertainty"].mean()) if group["uncertainty"].notna().any() else float("nan"),
        "mean_data_reliability": float(group["data_reliability"].mean()) if group["data_reliability"].notna().any() else float("nan"),
        "mean_confidence": float(group["confidence"].mean()) if group["confidence"].notna().any() else float("nan"),
    }


def build_metrics(rows: pd.DataFrame, beta: float) -> pd.DataFrame:
    metric_rows: list[dict[str, Any]] = []
    for key, group in rows.groupby(["model_name", "split", "horizon_months"], sort=True):
        _model_name, _split, _horizon = group_key_tuple(key)
        valid = group["mifal_matched_score"].notna() & group["bloom_h"].notna()
        if valid.any():
            metric_rows.append(_metric_row(group.loc[valid].copy(), beta))
    if not metric_rows:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return pd.DataFrame(metric_rows)[METRIC_COLUMNS].sort_values(["model_name", "split", "horizon_months"]).reset_index(drop=True)


def build_comparison(metrics: pd.DataFrame, baseline_model: str) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)
    baseline = metrics[metrics["model_name"] == baseline_model].copy()
    rows: list[dict[str, Any]] = []
    for row in dataframe_rows(metrics[metrics["model_name"] != baseline_model]):
        match = baseline[(baseline["split"] == row.split) & (baseline["horizon_months"] == int(row.horizon_months))]
        if match.empty:
            continue
        base = match.iloc[0]
        rows.append(
            {
                "mifal_matched_version": MIFAL_MATCHED_VERSION,
                "baseline_model": baseline_model,
                "comparison_model": row.model_name,
                "split": row.split,
                "horizon_months": int(row.horizon_months),
                "rows": int(min(int(row.rows), int(base["rows"]))),
                "delta_pr_auc": float(row.pr_auc) - float(base["pr_auc"]),
                "delta_brier": float(row.brier) - float(base["brier"]),
                "delta_fbeta": float(row.fbeta) - float(base["fbeta"]),
                "delta_mcc": float(row.mcc) - float(base["mcc"]),
                "delta_precision": float(row.precision) - float(base["precision"]),
                "delta_recall": float(row.recall) - float(base["recall"]),
                "delta_rmse_risk": float(row.rmse_risk) - float(base["rmse_risk"]),
                "delta_mae_risk": float(row.mae_risk) - float(base["mae_risk"]),
                "delta_interval_width": float(row.interval_mean_width) - float(base["interval_mean_width"]),
                "delta_data_reliability": float(row.mean_data_reliability) - float(base["mean_data_reliability"]),
            }
        )
    if not rows:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)
    return pd.DataFrame(rows)[COMPARISON_COLUMNS].sort_values(["comparison_model", "split", "horizon_months"]).reset_index(drop=True)


def write_report(
    args: argparse.Namespace,
    specs: list[PredictionSpec],
    keys: pd.DataFrame,
    rows: pd.DataFrame,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
) -> None:
    paths = output_paths(args.output_dir, args.output_name)
    lines = [
        "# MIFAL-ED/T2 Matched-Surface Evaluation Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Matched key rows: `{_format_int(len(keys))}`",
        f"Long matched prediction rows: `{_format_int(len(rows))}`",
        f"Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        f"Reference rows: `{args.reference_rows.as_posix() if args.reference_rows else 'none'}`",
        "",
        "This report evaluates already-calibrated MIFAL predictions on an exact intersection of source, site, origin month, horizon, and split.",
        "It does not fit calibrators, select thresholds, or use test rows unless `test` is explicitly requested.",
        "",
        "## Inputs",
        "",
    ]
    for spec in specs:
        lines.append(f"- `{spec.name}`: `{spec.path.as_posix()}`")

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| model | surface | split | horizon | rows | positives | predicted positive rate | PR-AUC | Brier | precision | recall | F-beta | MCC | risk RMSE | interval width | data reliability |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if metrics.empty:
        lines.append("| `NA` | `NA` | `NA` | 0 | 0 | 0 | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(metrics):
            lines.append(
                f"| `{row.model_name}` | `{row.surface}` | `{row.split}` | {int(row.horizon_months)} | "
                f"{_format_int(int(row.rows))} | {_format_int(int(row.positive_rows))} | "
                f"{_format_float(float(row.predicted_positive_rate))} | {_format_float(float(row.pr_auc))} | "
                f"{_format_float(float(row.brier))} | {_format_float(float(row.precision))} | "
                f"{_format_float(float(row.recall))} | {_format_float(float(row.fbeta))} | "
                f"{_format_float(float(row.mcc))} | {_format_float(float(row.rmse_risk))} | "
                f"{_format_float(float(row.interval_mean_width))} | {_format_float(float(row.mean_data_reliability))} |"
            )

    lines.extend(
        [
            "",
            "## Comparison Against First Input",
            "",
            "| baseline | comparison | split | horizon | delta PR-AUC | delta Brier | delta F-beta | delta MCC | delta recall | delta precision |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if comparison.empty:
        lines.append("| `NA` | `NA` | `NA` | 0 | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(comparison):
            lines.append(
                f"| `{row.baseline_model}` | `{row.comparison_model}` | `{row.split}` | {int(row.horizon_months)} | "
                f"{_format_float(float(row.delta_pr_auc))} | {_format_float(float(row.delta_brier))} | "
                f"{_format_float(float(row.delta_fbeta))} | {_format_float(float(row.delta_mcc))} | "
                f"{_format_float(float(row.delta_recall))} | {_format_float(float(row.delta_precision))} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Matched rows: `{paths['matched_rows'].as_posix()}`",
            f"- Metrics: `{paths['metrics'].as_posix()}`",
            f"- Comparison: `{paths['comparison'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(
    args: argparse.Namespace,
    specs: list[PredictionSpec],
    keys: pd.DataFrame,
    rows: pd.DataFrame,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    started_at: datetime,
) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    inputs = [spec.path for spec in specs]
    if args.reference_rows is not None:
        inputs.append(args.reference_rows)
    return {
        "status": "completed",
        "mifal_matched_version": MIFAL_MATCHED_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "predictions": [{"name": spec.name, "path": spec.path.as_posix()} for spec in specs],
            "reference_rows": args.reference_rows.as_posix() if args.reference_rows else None,
            "evaluation_splits": args.evaluation_splits,
            "max_rows_per_group": args.max_rows_per_group,
            "fbeta_beta": float(args.fbeta_beta),
            "random_seed": int(args.random_seed),
            "output_name": args.output_name,
        },
        "row_counts": {
            "matched_key_rows": int(len(keys)),
            "matched_prediction_rows": int(len(rows)),
            "metric_rows": int(len(metrics)),
            "comparison_rows": int(len(comparison)),
        },
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate calibrated MIFAL predictions on an exact matched surface.")
    parser.add_argument("--prediction", action="append", default=None, help="Repeated NAME=PATH calibrated MIFAL prediction input.")
    parser.add_argument("--reference-rows", type=Path, default=None)
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="validation")
    parser.add_argument("--max-rows-per-group", type=int, default=None)
    parser.add_argument("--fbeta-beta", type=float, default=2.0)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction_values = args.prediction if args.prediction is not None else DEFAULT_PREDICTIONS
    specs = [parse_prediction_spec(value) for value in prediction_values]
    if len(specs) < 2:
        raise ValueError("At least two --prediction inputs are required for matched-surface evaluation")
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise ValueError("Prediction input names must be unique")
    if args.max_rows_per_group is not None and args.max_rows_per_group < 1:
        raise ValueError("--max-rows-per-group must be >= 1")

    started_at = datetime.now(timezone.utc)
    print(f"loading {len(specs)} calibrated MIFAL prediction files", flush=True)
    predictions = {spec.name: read_predictions(spec) for spec in specs}
    reference_keys = None
    reference_columns: list[str] = []
    if args.reference_rows is not None:
        reference_keys, reference_columns = read_reference_keys(args.reference_rows)
    keys = build_matched_keys(
        predictions,
        evaluation_splits=args.evaluation_splits,
        reference_keys=reference_keys,
        reference_columns=reference_columns,
        max_rows_per_group=args.max_rows_per_group,
        random_seed=args.random_seed,
    )
    rows = build_long_matched_rows(predictions, keys)
    metrics = build_metrics(rows, args.fbeta_beta)
    comparison = build_comparison(metrics, baseline_model=specs[0].name)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(rows, paths["matched_rows"])
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(comparison, paths["comparison"])
    write_report(args, specs, keys, rows, metrics, comparison)
    manifest = manifest_payload(args, specs, keys, rows, metrics, comparison, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"MIFAL matched-surface report written: {paths['report']}", flush=True)
    print(f"MIFAL matched-surface manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
