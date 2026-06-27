#!/usr/bin/env python
"""Calibrate MIFAL observable risk on validation predictions only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
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

from src.pandas_utils import dataframe_rows


MIFAL_CALIBRATION_VERSION = "mifal_observable_alert_calibration_v0"
DEFAULT_REPORT_DIR = Path("reports/mifal")
DEFAULT_CALIBRATOR_DIR = Path("models/mifal/observable_calibrators")
DEFAULT_PREDICTIONS = DEFAULT_REPORT_DIR / "mifal_observable_no_current_chla_smoke_predictions.csv"
DEFAULT_OUTPUT_NAME = "mifal_observable_no_current_chla_validation_calibration"
OUTPUT_SUFFIXES = {
    "thresholds": "thresholds.csv",
    "metrics": "metrics.csv",
    "calibrated_predictions": "calibrated_predictions.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
REQUIRED_COLUMNS = [
    "mifal_observable_version",
    "surface",
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "split",
    "bloom_h",
    "target_risk_chla_h",
    "risk_conservative",
    "uncertainty",
    "data_reliability",
]
THRESHOLD_COLUMNS = [
    "mifal_calibration_version",
    "surface",
    "target_event",
    "horizon_months",
    "calibration_split",
    "selection_objective",
    "fbeta_beta",
    "min_recall",
    "min_precision",
    "score_column",
    "selected_threshold",
    "constraint_satisfied",
    "calibration_rows",
    "calibration_positive_rows",
    "calibration_positive_rate",
    "calibration_predicted_positive_rows",
    "calibration_predicted_positive_rate",
    "calibration_precision",
    "calibration_recall",
    "calibration_fbeta",
    "calibration_macro_f1",
    "calibration_mcc",
    "calibrator_path",
    "calibrator_method",
]
METRIC_COLUMNS = [
    "mifal_calibration_version",
    "surface",
    "target_event",
    "split",
    "horizon_months",
    "score_column",
    "threshold",
    "rows",
    "positive_rows",
    "positive_rate",
    "predicted_positive_rows",
    "predicted_positive_rate",
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
]


@dataclass(frozen=True)
class JsonCalibrator:
    horizon: int
    path: Path
    method: str
    payload: dict[str, Any]
    training_rows: int
    positive_rows: int


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


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {key: output_dir / f"{output_name}_{suffix}" for key, suffix in OUTPUT_SUFFIXES.items()}


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _binary_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype("int8")
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).astype("int8")
    normalized = values.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y"}).astype("int8")


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
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


def read_predictions(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"MIFAL predictions are missing required columns: {missing}")
    out = frame.copy()
    out["bloom_h"] = _binary_series(out["bloom_h"])
    out["target_risk_chla_h"] = pd.to_numeric(out["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    out["risk_conservative"] = pd.to_numeric(out["risk_conservative"], errors="coerce").clip(0.0, 1.0)
    out["horizon_months"] = pd.to_numeric(out["horizon_months"], errors="raise").astype("int16")
    if out["surface"].nunique(dropna=False) != 1:
        raise ValueError("Calibrate one MIFAL surface at a time")
    return out


def fit_calibrators(rows: pd.DataFrame, args: argparse.Namespace) -> dict[int, JsonCalibrator]:
    calibrators: dict[int, JsonCalibrator] = {}
    for horizon, group in rows[rows["split"] == args.calibration_split].groupby("horizon_months", sort=True):
        valid = group["risk_conservative"].notna() & group["bloom_h"].notna()
        train = group.loc[valid].copy()
        y = train["bloom_h"].to_numpy(dtype="int8")
        x = train["risk_conservative"].to_numpy(dtype="float64")
        if len(train) < args.min_calibration_rows:
            method = "constant_insufficient_rows"
            probability = float(y.mean()) if len(y) else 0.0
            payload: dict[str, Any] = {"method": method, "probability": probability}
        elif len(np.unique(y)) < 2:
            method = "constant_single_class"
            payload = {"method": method, "probability": float(y.mean())}
        else:
            model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            model.fit(x, y)
            method = "isotonic"
            payload = {
                "method": method,
                "x_thresholds": [float(value) for value in model.X_thresholds_],
                "y_thresholds": [float(value) for value in model.y_thresholds_],
            }
        surface = str(rows["surface"].iloc[0])
        path = args.calibrator_dir / f"{surface}_h{int(horizon)}_bloom_h_calibrator.json"
        calibrator_payload = {
            "mifal_calibration_version": MIFAL_CALIBRATION_VERSION,
            "surface": surface,
            "target_event": "bloom_h",
            "horizon_months": int(horizon),
            "score_column": "risk_conservative",
            "calibration_split": args.calibration_split,
            "training_rows": int(len(train)),
            "positive_rows": int(y.sum()),
            **payload,
        }
        _write_json_atomic(calibrator_payload, path)
        calibrators[int(horizon)] = JsonCalibrator(
            horizon=int(horizon),
            path=path,
            method=method,
            payload=calibrator_payload,
            training_rows=int(len(train)),
            positive_rows=int(y.sum()),
        )
    return calibrators


def _apply_json_calibrator(scores: pd.Series, payload: dict[str, Any]) -> np.ndarray:
    values = _clip01(scores)
    if str(payload["method"]).startswith("constant"):
        return np.full(values.shape, float(payload["probability"]), dtype="float64")
    x_thresholds = np.asarray(payload["x_thresholds"], dtype="float64")
    y_thresholds = np.asarray(payload["y_thresholds"], dtype="float64")
    return np.interp(values, x_thresholds, y_thresholds, left=y_thresholds[0], right=y_thresholds[-1])


def apply_calibrators(rows: pd.DataFrame, calibrators: dict[int, JsonCalibrator]) -> pd.DataFrame:
    out = rows.copy()
    out["mifal_probability_bloom_calibrated"] = np.nan
    for horizon, calibrator in calibrators.items():
        mask = out["horizon_months"] == int(horizon)
        out.loc[mask, "mifal_probability_bloom_calibrated"] = _apply_json_calibrator(out.loc[mask, "risk_conservative"], calibrator.payload)
    out["mifal_probability_bloom_calibrated"] = out["mifal_probability_bloom_calibrated"].clip(0.0, 1.0)
    return out


def _candidate_thresholds(scores: np.ndarray) -> np.ndarray:
    finite = np.asarray(scores[np.isfinite(scores)], dtype="float64")
    if finite.size == 0:
        return np.array([0.5], dtype="float64")
    candidates = np.unique(np.concatenate([[0.0, 0.5, 1.0], finite]))
    return np.asarray(np.clip(candidates, 0.0, 1.0), dtype="float64")


def _threshold_candidate(threshold: float, scores: np.ndarray, actual: np.ndarray, beta: float) -> dict[str, float | bool]:
    predicted = (scores >= threshold).astype("int8")
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    macro_f1 = _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0)
    fbeta = _f_beta(precision, recall, beta)
    return {
        "threshold": float(threshold),
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else float("nan"),
        "precision": precision,
        "recall": recall,
        "fbeta": fbeta,
        "macro_f1": macro_f1,
        "mcc": _safe_metric(matthews_corrcoef, actual, predicted),
    }


def select_threshold(scores: np.ndarray, actual: np.ndarray, args: argparse.Namespace) -> dict[str, Any]:
    candidates = pd.DataFrame([_threshold_candidate(float(threshold), scores, actual, args.fbeta_beta) for threshold in _candidate_thresholds(scores)])
    candidates["constraint_satisfied"] = (candidates["recall"] >= args.min_recall) & (candidates["precision"] >= args.min_precision)
    constrained = candidates[candidates["constraint_satisfied"]].copy()
    ranking = constrained if not constrained.empty else candidates
    if args.selection_objective == "f_beta":
        order = ["fbeta", "recall", "precision", "threshold"]
    elif args.selection_objective == "closest_pr":
        ranking = ranking.copy()
        ranking["pr_gap"] = (ranking["precision"] - ranking["recall"]).abs()
        order = ["fbeta", "pr_gap", "recall", "precision"]
        ascending = [False, True, False, False]
        return ranking.sort_values(order, ascending=ascending, kind="mergesort").iloc[0].to_dict()
    elif args.selection_objective == "mcc":
        order = ["mcc", "fbeta", "recall", "threshold"]
    else:
        raise ValueError(f"Unknown selection objective: {args.selection_objective}")
    return ranking.sort_values(order, ascending=[False] * len(order), kind="mergesort").iloc[0].to_dict()


def select_thresholds(rows: pd.DataFrame, calibrators: dict[int, JsonCalibrator], args: argparse.Namespace) -> pd.DataFrame:
    threshold_rows: list[dict[str, Any]] = []
    surface = str(rows["surface"].iloc[0])
    calibration = rows[rows["split"] == args.calibration_split].copy()
    for horizon, group in calibration.groupby("horizon_months", sort=True):
        valid = group["mifal_probability_bloom_calibrated"].notna() & group["bloom_h"].notna()
        if int(valid.sum()) < args.min_threshold_rows:
            continue
        scores = group.loc[valid, "mifal_probability_bloom_calibrated"].to_numpy(dtype="float64")
        actual = group.loc[valid, "bloom_h"].to_numpy(dtype="int8")
        selected = select_threshold(scores, actual, args)
        calibrator = calibrators[int(horizon)]
        threshold_rows.append(
            {
                "mifal_calibration_version": MIFAL_CALIBRATION_VERSION,
                "surface": surface,
                "target_event": "bloom_h",
                "horizon_months": int(horizon),
                "calibration_split": args.calibration_split,
                "selection_objective": args.selection_objective,
                "fbeta_beta": float(args.fbeta_beta),
                "min_recall": float(args.min_recall),
                "min_precision": float(args.min_precision),
                "score_column": "mifal_probability_bloom_calibrated",
                "selected_threshold": float(selected["threshold"]),
                "constraint_satisfied": bool(selected["constraint_satisfied"]),
                "calibration_rows": int(len(actual)),
                "calibration_positive_rows": int(actual.sum()),
                "calibration_positive_rate": float(actual.mean()) if len(actual) else float("nan"),
                "calibration_predicted_positive_rows": int(selected["predicted_positive_rows"]),
                "calibration_predicted_positive_rate": float(selected["predicted_positive_rate"]),
                "calibration_precision": float(selected["precision"]),
                "calibration_recall": float(selected["recall"]),
                "calibration_fbeta": float(selected["fbeta"]),
                "calibration_macro_f1": float(selected["macro_f1"]),
                "calibration_mcc": float(selected["mcc"]),
                "calibrator_path": _manifest_path(calibrator.path),
                "calibrator_method": calibrator.method,
            }
        )
    if not threshold_rows:
        raise ValueError("No MIFAL threshold rows were selected")
    return pd.DataFrame(threshold_rows)[THRESHOLD_COLUMNS].sort_values(["horizon_months"]).reset_index(drop=True)


def apply_thresholds(rows: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    out["mifal_bloom_probability_threshold"] = np.nan
    out["mifal_predicted_bloom_h"] = pd.NA
    for row in dataframe_rows(thresholds):
        mask = out["horizon_months"] == int(row.horizon_months)
        threshold = float(row.selected_threshold)
        out.loc[mask, "mifal_bloom_probability_threshold"] = threshold
        out.loc[mask, "mifal_predicted_bloom_h"] = (
            out.loc[mask, "mifal_probability_bloom_calibrated"].astype("float64") >= threshold
        ).astype("int8")
    return out


def _metric_row(group: pd.DataFrame, threshold: float, split: str, horizon: int, surface: str, beta: float) -> dict[str, Any]:
    score = group["mifal_probability_bloom_calibrated"].to_numpy(dtype="float64")
    actual = group["bloom_h"].to_numpy(dtype="int8")
    predicted = (score >= threshold).astype("int8")
    tn, fp, fn, tp = confusion_matrix(actual, predicted, labels=[0, 1]).ravel()
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    specificity = _safe_rate(tn, tn + fp)
    target_risk = group["target_risk_chla_h"].to_numpy(dtype="float64")
    return {
        "mifal_calibration_version": MIFAL_CALIBRATION_VERSION,
        "surface": surface,
        "target_event": "bloom_h",
        "split": split,
        "horizon_months": int(horizon),
        "score_column": "mifal_probability_bloom_calibrated",
        "threshold": float(threshold),
        "rows": int(len(group)),
        "positive_rows": int(actual.sum()),
        "positive_rate": float(actual.mean()) if len(actual) else float("nan"),
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else float("nan"),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "fbeta": _f_beta(precision, recall, beta),
        "mcc": _safe_metric(matthews_corrcoef, actual, predicted),
        "pr_auc": _safe_metric(average_precision_score, actual, score),
        "roc_auc": _safe_metric(roc_auc_score, actual, score),
        "brier": _safe_metric(brier_score_loss, actual, score),
        "rmse_risk": _root_mean_squared_error(target_risk, score),
        "mae_risk": float(np.mean(np.abs(target_risk - score))),
    }


def build_metrics(rows: pd.DataFrame, thresholds: pd.DataFrame, evaluation_splits: list[str], beta: float) -> pd.DataFrame:
    metric_rows: list[dict[str, Any]] = []
    surface = str(rows["surface"].iloc[0])
    for threshold_row in dataframe_rows(thresholds):
        horizon = int(threshold_row.horizon_months)
        threshold = float(threshold_row.selected_threshold)
        for split in evaluation_splits:
            group = rows[(rows["split"] == split) & (rows["horizon_months"] == horizon)].copy()
            group = group[group["mifal_probability_bloom_calibrated"].notna() & group["bloom_h"].notna()]
            if group.empty:
                continue
            metric_rows.append(_metric_row(group, threshold, split, horizon, surface, beta))
    return pd.DataFrame(metric_rows)[METRIC_COLUMNS] if metric_rows else pd.DataFrame(columns=METRIC_COLUMNS)


def write_report(args: argparse.Namespace, thresholds: pd.DataFrame, metrics: pd.DataFrame, calibrators: dict[int, JsonCalibrator]) -> None:
    paths = output_paths(args.output_dir, args.output_name)
    surface = str(thresholds["surface"].iloc[0]) if not thresholds.empty else "NA"
    lines = [
        "# MIFAL-ED/T2 Validation Calibration Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Surface: `{surface}`",
        f"Predictions: `{args.predictions.as_posix()}`",
        f"Calibration split: `{args.calibration_split}`",
        f"Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        "",
        "Thresholds and calibrators are selected only on the calibration split. Do not read this report as held-out test evidence unless `test` is explicitly included as an evaluation split in a later run.",
        "",
        "## Thresholds",
        "",
        "| horizon | score | threshold | rows | positives | recall | precision | F-beta | method |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(thresholds):
        lines.append(
            f"| {int(row.horizon_months)} | `{row.score_column}` | {_format_float(float(row.selected_threshold))} | "
            f"{_format_int(int(row.calibration_rows))} | {_format_int(int(row.calibration_positive_rows))} | "
            f"{_format_float(float(row.calibration_recall))} | {_format_float(float(row.calibration_precision))} | "
            f"{_format_float(float(row.calibration_fbeta))} | `{row.calibrator_method}` |"
        )

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| split | horizon | rows | positives | threshold | PR-AUC | Brier | recall | precision | F-beta | MCC | risk RMSE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if metrics.empty:
        lines.append("| `NA` | 0 | 0 | 0 | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(metrics):
            lines.append(
                f"| `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
                f"{_format_int(int(row.positive_rows))} | {_format_float(float(row.threshold))} | "
                f"{_format_float(float(row.pr_auc))} | {_format_float(float(row.brier))} | "
                f"{_format_float(float(row.recall))} | {_format_float(float(row.precision))} | "
                f"{_format_float(float(row.fbeta))} | {_format_float(float(row.mcc))} | "
                f"{_format_float(float(row.rmse_risk))} |"
            )

    lines.extend(
        [
            "",
            "## Calibrator Files",
            "",
        ]
    )
    for calibrator in calibrators.values():
        lines.append(f"- h{calibrator.horizon}: `{_manifest_path(calibrator.path)}` ({calibrator.method})")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Thresholds: `{paths['thresholds'].as_posix()}`",
            f"- Metrics: `{paths['metrics'].as_posix()}`",
            f"- Calibrated predictions: `{paths['calibrated_predictions'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(args: argparse.Namespace, rows: pd.DataFrame, thresholds: pd.DataFrame, metrics: pd.DataFrame, calibrators: dict[int, JsonCalibrator], started_at: datetime) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    return {
        "status": "completed",
        "mifal_calibration_version": MIFAL_CALIBRATION_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "predictions": args.predictions.as_posix(),
            "calibrator_dir": args.calibrator_dir.as_posix(),
            "calibration_split": args.calibration_split,
            "evaluation_splits": args.evaluation_splits,
            "selection_objective": args.selection_objective,
            "fbeta_beta": float(args.fbeta_beta),
            "min_recall": float(args.min_recall),
            "min_precision": float(args.min_precision),
            "min_calibration_rows": int(args.min_calibration_rows),
            "min_threshold_rows": int(args.min_threshold_rows),
            "output_name": args.output_name,
        },
        "inputs": [_file_record(args.predictions)],
        "row_counts": {
            "input_rows": int(len(rows)),
            "threshold_rows": int(len(thresholds)),
            "metric_rows": int(len(metrics)),
            "calibrator_rows": int(len(calibrators)),
        },
        "calibrators": [_file_record(calibrator.path) for calibrator in calibrators.values()],
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate MIFAL observable predictions on validation only.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--calibrator-dir", type=Path, default=DEFAULT_CALIBRATOR_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--calibration-split", default="validation")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="validation")
    parser.add_argument("--selection-objective", choices=["f_beta", "closest_pr", "mcc"], default="f_beta")
    parser.add_argument("--fbeta-beta", type=float, default=2.0)
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--min-precision", type=float, default=0.0)
    parser.add_argument("--min-calibration-rows", type=int, default=20)
    parser.add_argument("--min-threshold-rows", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.calibration_split != "validation":
        raise ValueError("MIFAL Gate 2 calibration must use --calibration-split validation")
    started_at = datetime.now(timezone.utc)
    print(f"loading MIFAL predictions {args.predictions}", flush=True)
    rows = read_predictions(args.predictions)
    calibrators = fit_calibrators(rows, args)
    calibrated = apply_calibrators(rows, calibrators)
    thresholds = select_thresholds(calibrated, calibrators, args)
    calibrated = apply_thresholds(calibrated, thresholds)
    metrics = build_metrics(calibrated, thresholds, args.evaluation_splits, args.fbeta_beta)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(thresholds, paths["thresholds"])
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(calibrated, paths["calibrated_predictions"])
    write_report(args, thresholds, metrics, calibrators)
    manifest = manifest_payload(args, calibrated, thresholds, metrics, calibrators, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"MIFAL calibration report written: {paths['report']}", flush=True)
    print(f"MIFAL calibration manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
