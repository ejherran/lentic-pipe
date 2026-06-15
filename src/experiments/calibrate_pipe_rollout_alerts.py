#!/usr/bin/env python
"""Calibrate rollout alerts and select horizon-specific thresholds."""

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.pandas_utils import dataframe_rows


BACKTEST_VERSION = "pipe_grud_rollout_backtest_v0"
CALIBRATION_VERSION = "pipe_grud_rollout_alert_calibration_v0"
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_MODEL_DIR = Path("models/pipe_grud/rollout_calibrators")
DEFAULT_BACKTEST_ROWS = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_rows.parquet"
DEFAULT_THRESHOLDS = DEFAULT_REPORT_DIR / "pipe_rollout_calibration_thresholds.csv"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_rollout_calibration_metrics.csv"
DEFAULT_CALIBRATED_ROWS = DEFAULT_REPORT_DIR / "pipe_rollout_calibrated_backtest_rows.parquet"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_rollout_calibration_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_rollout_calibration_manifest.json"

KEY_COLUMNS = [
    "source_id",
    "site_id",
    "split",
    "origin_year_month",
    "forecast_year_month",
    "rollout_horizon_months",
]
REQUIRED_COLUMNS = [
    *KEY_COLUMNS,
    "alert_probability_irc",
    "actual_irc_alert",
    "irc_mean",
]
BLOOM_COLUMNS = ["bloom_h"]
THRESHOLD_COLUMNS = [
    "calibration_version",
    "target_event",
    "rollout_horizon_months",
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
    "calibration_macro_f1",
    "calibration_fbeta",
    "calibration_specificity",
    "calibrator_path",
    "calibrator_method",
    "calibrator_training_rows",
    "calibrator_positive_rows",
]
METRIC_COLUMNS = [
    "calibration_version",
    "target_event",
    "split",
    "rollout_horizon_months",
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
    "pr_auc",
    "roc_auc",
    "brier",
]


@dataclass(frozen=True)
class ConstantProbability:
    probability: float

    def predict(self, values: np.ndarray | pd.Series) -> np.ndarray:
        array = np.asarray(values, dtype="float64")
        return np.full(array.shape, float(self.probability), dtype="float64")


@dataclass(frozen=True)
class CalibratorRecord:
    horizon: int
    score_column: str
    path: Path
    calibrator: Any
    method: str
    training_rows: int
    positive_rows: int


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


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


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


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        frame.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported input suffix for {path}: expected .parquet or .csv")


def write_table(frame: pd.DataFrame, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        _write_parquet_atomic(frame, path)
        return
    if suffix == ".csv":
        _write_csv_atomic(frame, path)
        return
    raise ValueError(f"Unsupported output suffix for {path}: expected .parquet or .csv")


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _binary_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype("int8")
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).astype("int8")
    normalized = values.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y"}).astype("int8")


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def validate_backtest_rows(rows: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in rows.columns]
    if missing:
        raise ValueError(f"Backtest rows are missing required columns: {missing}")
    if not any(column in rows.columns for column in BLOOM_COLUMNS):
        raise ValueError("Backtest rows must include `bloom_h` for rollout-specific bloom calibration")


def prepare_rows(rows: pd.DataFrame) -> pd.DataFrame:
    validate_backtest_rows(rows)
    out = rows.copy()
    for column in ["source_id", "site_id", "split", "origin_year_month", "forecast_year_month"]:
        out[column] = out[column].astype(str)
    out["rollout_horizon_months"] = pd.to_numeric(out["rollout_horizon_months"], errors="coerce").astype("int64")
    for column in ["alert_probability_irc", "irc_mean", "bloom_h"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out["actual_irc_alert"] = _binary_series(out["actual_irc_alert"])
    return out.sort_values(KEY_COLUMNS).reset_index(drop=True)


def _fit_calibrator(scores: np.ndarray, actual: np.ndarray) -> tuple[Any, str]:
    if len(np.unique(actual)) < 2:
        return ConstantProbability(float(actual.mean()) if len(actual) else 0.0), "constant"
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    calibrator.fit(scores, actual)
    return calibrator, "isotonic"


def fit_bloom_calibrators(rows: pd.DataFrame, args: argparse.Namespace) -> dict[int, CalibratorRecord]:
    calibrators: dict[int, CalibratorRecord] = {}
    training = rows[(rows["split"] == args.calibration_split) & rows["bloom_h"].notna()].copy()
    args.calibrator_dir.mkdir(parents=True, exist_ok=True)
    for horizon, group in training.groupby("rollout_horizon_months", sort=True):
        score = pd.to_numeric(group[args.bloom_score_column], errors="coerce")
        actual = pd.to_numeric(group["bloom_h"], errors="coerce")
        valid = score.notna() & actual.notna()
        group = group.loc[valid].copy()
        if len(group) < int(args.min_calibration_rows):
            continue
        score_values = _clip01(group[args.bloom_score_column])
        actual_values = group["bloom_h"].astype("int8").to_numpy()
        calibrator, method = _fit_calibrator(score_values, actual_values)
        path = args.calibrator_dir / f"rollout_bloom_h{int(horizon)}_{args.bloom_score_column}_isotonic.joblib"
        calibrators[int(horizon)] = CalibratorRecord(
            horizon=int(horizon),
            score_column=args.bloom_score_column,
            path=path,
            calibrator=calibrator,
            method=method,
            training_rows=int(len(group)),
            positive_rows=int(actual_values.sum()),
        )
    return calibrators


def apply_bloom_calibrators(rows: pd.DataFrame, calibrators: dict[int, CalibratorRecord]) -> pd.DataFrame:
    out = rows.copy()
    out["rollout_probability_bloom_calibrated"] = np.nan
    out["rollout_bloom_calibrator_method"] = pd.NA
    for horizon, record in calibrators.items():
        mask = out["rollout_horizon_months"] == int(horizon)
        score = pd.to_numeric(out.loc[mask, record.score_column], errors="coerce")
        valid_index = score[score.notna()].index
        if len(valid_index) == 0:
            continue
        probability = record.calibrator.predict(_clip01(out.loc[valid_index, record.score_column]))
        out.loc[valid_index, "rollout_probability_bloom_calibrated"] = _clip01(probability)
        out.loc[valid_index, "rollout_bloom_calibrator_method"] = record.method
    return out


def _candidate_thresholds(scores: np.ndarray) -> np.ndarray:
    finite = _clip01(scores[np.isfinite(scores)])
    if len(finite) == 0:
        return np.array([0.5], dtype="float64")
    return np.unique(np.concatenate([np.array([0.0, 0.5, 1.0], dtype="float64"), finite]))


def _fbeta_score(precision: float, recall: float, beta: float) -> float:
    if pd.isna(precision) or pd.isna(recall):
        return float("nan")
    beta2 = beta * beta
    denominator = beta2 * precision + recall
    if denominator == 0:
        return 0.0
    return float((1.0 + beta2) * precision * recall / denominator)


def _classification_counts(actual: np.ndarray, predicted: np.ndarray) -> tuple[int, int, int, int]:
    matrix = confusion_matrix(actual, predicted, labels=[0, 1])
    tn, fp, fn, tp = [int(value) for value in matrix.ravel()]
    return tn, fp, fn, tp


def _threshold_candidate_row(
    *,
    threshold: float,
    scores: np.ndarray,
    actual: np.ndarray,
    beta: float,
) -> dict[str, Any]:
    predicted = (scores >= threshold).astype("int8")
    tn, fp, fn, tp = _classification_counts(actual, predicted)
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    return {
        "threshold": float(threshold),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "specificity": _safe_rate(tn, tn + fp),
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "fbeta": _fbeta_score(precision, recall, beta),
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else np.nan,
    }


def select_threshold(
    *,
    scores: np.ndarray,
    actual: np.ndarray,
    args: argparse.Namespace,
) -> dict[str, Any]:
    candidates = pd.DataFrame(
        [
            _threshold_candidate_row(
                threshold=float(threshold),
                scores=scores,
                actual=actual,
                beta=float(args.fbeta_beta),
            )
            for threshold in _candidate_thresholds(scores)
        ]
    )
    candidates["meets_min_recall"] = True if args.min_recall is None else candidates["recall"] >= float(args.min_recall)
    candidates["meets_min_precision"] = (
        True if args.min_precision is None else candidates["precision"] >= float(args.min_precision)
    )
    candidates["constraint_satisfied"] = candidates["meets_min_recall"] & candidates["meets_min_precision"]
    eligible = candidates[candidates["constraint_satisfied"]].copy()
    if eligible.empty:
        eligible = candidates.copy()

    if args.selection_objective == "recall_target":
        selected = eligible.sort_values(
            ["recall", "precision", "fbeta", "threshold"],
            ascending=[False, False, False, False],
            kind="mergesort",
        ).iloc[0]
    elif args.selection_objective == "precision_target":
        selected = eligible.sort_values(
            ["precision", "recall", "fbeta", "threshold"],
            ascending=[False, False, False, False],
            kind="mergesort",
        ).iloc[0]
    else:
        selected = eligible.sort_values(
            ["fbeta", "recall", "precision", "threshold"],
            ascending=[False, False, False, False],
            kind="mergesort",
        ).iloc[0]
    return selected.to_dict()


def _metric_row(
    *,
    calibration_version: str,
    target_event: str,
    split: str,
    horizon: int,
    score_column: str,
    probability: np.ndarray,
    actual: np.ndarray,
    threshold: float,
    beta: float,
) -> dict[str, Any]:
    predicted = (probability >= threshold).astype("int8")
    tn, fp, fn, tp = _classification_counts(actual, predicted)
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    return {
        "calibration_version": calibration_version,
        "target_event": target_event,
        "split": split,
        "rollout_horizon_months": int(horizon),
        "score_column": score_column,
        "threshold": float(threshold),
        "rows": int(len(actual)),
        "positive_rows": int(actual.sum()),
        "positive_rate": float(actual.mean()) if len(actual) else np.nan,
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else np.nan,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "specificity": _safe_rate(tn, tn + fp),
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "fbeta": _fbeta_score(precision, recall, beta=beta),
        "pr_auc": _safe_metric(average_precision_score, actual, probability),
        "roc_auc": _safe_metric(roc_auc_score, actual, probability),
        "brier": _safe_metric(brier_score_loss, actual, probability),
    }


def select_thresholds(rows: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    threshold_rows: list[dict[str, Any]] = []
    event_specs: list[dict[str, Any]] = [
        {
            "target_event": "irc_alert",
            "score_column": "alert_probability_irc",
            "actual_column": "actual_irc_alert",
            "calibrator_path": None,
            "calibrator_method": "none",
            "calibrator_training_rows": 0,
            "calibrator_positive_rows": 0,
        },
        {
            "target_event": "bloom_h",
            "score_column": "rollout_probability_bloom_calibrated",
            "actual_column": "bloom_h",
            "calibrator_path": None,
            "calibrator_method": "rollout_isotonic",
            "calibrator_training_rows": 0,
            "calibrator_positive_rows": 0,
        },
    ]
    for spec in event_specs:
        if spec["score_column"] not in rows.columns or spec["actual_column"] not in rows.columns:
            continue
        for horizon, group in rows[rows["split"] == args.calibration_split].groupby("rollout_horizon_months", sort=True):
            score = pd.to_numeric(group[spec["score_column"]], errors="coerce")
            actual = pd.to_numeric(group[spec["actual_column"]], errors="coerce")
            valid = score.notna() & actual.notna()
            if valid.sum() < int(args.min_threshold_rows):
                continue
            scores = _clip01(score.loc[valid])
            actual_values = actual.loc[valid].astype("int8").to_numpy()
            selected = select_threshold(scores=scores, actual=actual_values, args=args)
            threshold_rows.append(
                {
                    "calibration_version": args.calibration_version,
                    "target_event": spec["target_event"],
                    "rollout_horizon_months": int(horizon),
                    "calibration_split": args.calibration_split,
                    "selection_objective": args.selection_objective,
                    "fbeta_beta": float(args.fbeta_beta),
                    "min_recall": args.min_recall,
                    "min_precision": args.min_precision,
                    "score_column": spec["score_column"],
                    "selected_threshold": float(selected["threshold"]),
                    "constraint_satisfied": bool(selected["constraint_satisfied"]),
                    "calibration_rows": int(len(actual_values)),
                    "calibration_positive_rows": int(actual_values.sum()),
                    "calibration_positive_rate": float(actual_values.mean()) if len(actual_values) else np.nan,
                    "calibration_predicted_positive_rows": int(selected["predicted_positive_rows"]),
                    "calibration_predicted_positive_rate": float(selected["predicted_positive_rate"]),
                    "calibration_precision": float(selected["precision"]),
                    "calibration_recall": float(selected["recall"]),
                    "calibration_macro_f1": float(selected["macro_f1"]),
                    "calibration_fbeta": float(selected["fbeta"]),
                    "calibration_specificity": float(selected["specificity"]),
                    "calibrator_path": spec["calibrator_path"],
                    "calibrator_method": spec["calibrator_method"],
                    "calibrator_training_rows": int(spec["calibrator_training_rows"]),
                    "calibrator_positive_rows": int(spec["calibrator_positive_rows"]),
                }
            )
    if not threshold_rows:
        return pd.DataFrame(columns=THRESHOLD_COLUMNS)
    return pd.DataFrame(threshold_rows)[THRESHOLD_COLUMNS].sort_values(["target_event", "rollout_horizon_months"]).reset_index(drop=True)


def attach_calibrator_metadata(thresholds: pd.DataFrame, calibrators: dict[int, CalibratorRecord]) -> pd.DataFrame:
    out = thresholds.copy()
    for index, row in out[out["target_event"] == "bloom_h"].iterrows():
        record = calibrators.get(int(row["rollout_horizon_months"]))
        if record is None:
            continue
        out.loc[index, "calibrator_path"] = record.path.as_posix()
        out.loc[index, "calibrator_method"] = record.method
        out.loc[index, "calibrator_training_rows"] = record.training_rows
        out.loc[index, "calibrator_positive_rows"] = record.positive_rows
    return out


def apply_selected_thresholds(rows: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    out["rollout_alert_probability_threshold_h"] = np.nan
    out["rollout_predicted_irc_alert_h"] = False
    out["rollout_bloom_probability_threshold_h"] = np.nan
    out["rollout_predicted_bloom_h"] = False
    for row in dataframe_rows(thresholds):
        horizon = int(row.rollout_horizon_months)
        mask = out["rollout_horizon_months"] == horizon
        if row.target_event == "irc_alert":
            out.loc[mask, "rollout_alert_probability_threshold_h"] = float(row.selected_threshold)
            out.loc[mask, "rollout_predicted_irc_alert_h"] = (
                out.loc[mask, "alert_probability_irc"].astype("float64") >= float(row.selected_threshold)
            )
        elif row.target_event == "bloom_h":
            out.loc[mask, "rollout_bloom_probability_threshold_h"] = float(row.selected_threshold)
            out.loc[mask, "rollout_predicted_bloom_h"] = (
                out.loc[mask, "rollout_probability_bloom_calibrated"].astype("float64") >= float(row.selected_threshold)
            )
    return out


def build_metrics(rows: pd.DataFrame, thresholds: pd.DataFrame, evaluation_splits: list[str]) -> pd.DataFrame:
    metric_rows: list[dict[str, Any]] = []
    for row in dataframe_rows(thresholds):
        score_column = str(row.score_column)
        actual_column = "actual_irc_alert" if row.target_event == "irc_alert" else "bloom_h"
        for split in evaluation_splits:
            group = rows[(rows["split"] == split) & (rows["rollout_horizon_months"] == int(row.rollout_horizon_months))]
            if group.empty:
                continue
            score = pd.to_numeric(group[score_column], errors="coerce")
            actual = pd.to_numeric(group[actual_column], errors="coerce")
            valid = score.notna() & actual.notna()
            if not valid.any():
                continue
            metric_rows.append(
                _metric_row(
                    calibration_version=str(row.calibration_version),
                    target_event=str(row.target_event),
                    split=split,
                    horizon=int(row.rollout_horizon_months),
                    score_column=score_column,
                    probability=_clip01(score.loc[valid]),
                    actual=actual.loc[valid].astype("int8").to_numpy(),
                    threshold=float(row.selected_threshold),
                    beta=float(row.fbeta_beta),
                )
            )
    if not metric_rows:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return pd.DataFrame(metric_rows)[METRIC_COLUMNS].sort_values(["target_event", "split", "rollout_horizon_months"]).reset_index(drop=True)


def write_calibrators(calibrators: dict[int, CalibratorRecord], thresholds: pd.DataFrame, args: argparse.Namespace) -> list[Path]:
    written: list[Path] = []
    for horizon, record in calibrators.items():
        threshold_rows = thresholds[
            (thresholds["target_event"] == "bloom_h") & (thresholds["rollout_horizon_months"] == int(horizon))
        ]
        threshold = float(threshold_rows["selected_threshold"].iloc[0]) if not threshold_rows.empty else 0.5
        payload = {
            "calibration_version": args.calibration_version,
            "calibrator": record.calibrator,
            "method": record.method,
            "score_column": record.score_column,
            "horizon_months": int(horizon),
            "threshold": threshold,
            "training_split": args.calibration_split,
            "training_rows": record.training_rows,
            "positive_rows": record.positive_rows,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        record.path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(payload, record.path)
        written.append(record.path)
    return written


def write_report(args: argparse.Namespace, thresholds: pd.DataFrame, metrics: pd.DataFrame, calibrator_paths: list[Path]) -> None:
    headline = metrics[metrics["split"].isin(args.evaluation_splits)].copy()
    lines = [
        f"# {args.model_label} Rollout Alert Calibration Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.",
        "Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.",
        "",
        "## Configuration",
        "",
        f"- Backtest rows: `{[path.as_posix() for path in args.backtest_rows]}`",
        f"- Calibration split: `{args.calibration_split}`",
        f"- Evaluation splits: `{args.evaluation_splits}`",
        f"- Bloom score column: `{args.bloom_score_column}`",
        f"- Selection objective: `{args.selection_objective}`",
        f"- F-beta beta: `{args.fbeta_beta}`",
        f"- Minimum recall: `{args.min_recall}`",
        f"- Minimum precision: `{args.min_precision}`",
        f"- Calibrator directory: `{args.calibrator_dir}`",
        "",
        "## Selected Thresholds",
        "",
        "| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    if thresholds.empty:
        lines.append("| `NA` | NA | `NA` | NA | 0 | 0 | NA | NA | NA | `False` |")
    else:
        for row in dataframe_rows(thresholds):
            lines.append(
                f"| `{row.target_event}` | {int(row.rollout_horizon_months)} | `{row.score_column}` | "
                f"{_format_float(row.selected_threshold)} | {_format_int(int(row.calibration_rows))} | "
                f"{_format_int(int(row.calibration_positive_rows))} | {_format_float(row.calibration_recall)} | "
                f"{_format_float(row.calibration_precision)} | {_format_float(row.calibration_fbeta)} | "
                f"`{bool(row.constraint_satisfied)}` |"
            )

    lines.extend(
        [
            "",
            "## Evaluation Metrics",
            "",
            "| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if headline.empty:
        lines.append("| `NA` | `NA` | NA | 0 | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(headline):
            lines.append(
                f"| `{row.target_event}` | `{row.split}` | {int(row.rollout_horizon_months)} | "
                f"{_format_int(int(row.rows))} | {_format_float(row.positive_rate)} | "
                f"{_format_float(row.predicted_positive_rate)} | {_format_float(row.pr_auc)} | "
                f"{_format_float(row.brier)} | {_format_float(row.recall)} | "
                f"{_format_float(row.precision)} | {_format_float(row.fbeta)} |"
            )

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Thresholds are selected on validation/calibration rows only.",
            "- Test metrics must be read as held-out evaluation, not threshold tuning evidence.",
            "- If a horizon has insufficient bloom positives, its calibrator is omitted.",
            f"- These outputs refine alert decisions; they do not retrain {args.model_label}.",
            "",
            "## Outputs",
            "",
            f"- Thresholds: `{args.thresholds}`",
            f"- Metrics: `{args.metrics}`",
            f"- Calibrated rows: `{args.calibrated_rows}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    if calibrator_paths:
        lines.extend(["", "## Calibrators", ""])
        lines.extend(f"- `{path}`" for path in calibrator_paths)
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    rows: pd.DataFrame,
    thresholds: pd.DataFrame,
    metrics: pd.DataFrame,
    calibrator_paths: list[Path],
) -> dict[str, Any]:
    outputs = [args.thresholds, args.metrics, args.calibrated_rows, args.report, *calibrator_paths]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "calibration_version": args.calibration_version,
        "backtest_version": args.backtest_version,
        "config": {
            "model_label": args.model_label,
            "calibration_split": args.calibration_split,
            "evaluation_splits": args.evaluation_splits,
            "bloom_score_column": args.bloom_score_column,
            "selection_objective": args.selection_objective,
            "fbeta_beta": float(args.fbeta_beta),
            "min_recall": args.min_recall,
            "min_precision": args.min_precision,
            "min_calibration_rows": int(args.min_calibration_rows),
            "min_threshold_rows": int(args.min_threshold_rows),
        },
        "row_counts": {
            "backtest_rows": int(len(rows)),
            "threshold_rows": int(len(thresholds)),
            "metric_rows": int(len(metrics)),
            "calibrator_files": int(len(calibrator_paths)),
        },
        "inputs": [_file_record(path) for path in args.backtest_rows],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def _parse_splits(value: str) -> list[str]:
    splits = [item.strip() for item in value.split(",") if item.strip()]
    if not splits:
        raise argparse.ArgumentTypeError("At least one split is required")
    return splits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backtest-rows",
        type=Path,
        action="append",
        default=None,
        help="Backtest row table. Repeat to concatenate validation/test exports.",
    )
    parser.add_argument("--calibrator-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--calibrated-rows", type=Path, default=DEFAULT_CALIBRATED_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model-label", default="PIPE/GRU-D")
    parser.add_argument("--calibration-version", default=CALIBRATION_VERSION)
    parser.add_argument("--backtest-version", default=BACKTEST_VERSION)
    parser.add_argument("--calibration-split", default="validation")
    parser.add_argument("--evaluation-splits", type=_parse_splits, default=["validation", "test"])
    parser.add_argument(
        "--bloom-score-column",
        choices=["irc_mean", "irc_p50", "alert_probability_irc"],
        default="irc_mean",
    )
    parser.add_argument(
        "--selection-objective",
        choices=["fbeta", "recall_target", "precision_target"],
        default="fbeta",
    )
    parser.add_argument("--fbeta-beta", type=float, default=2.0)
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--min-precision", type=float, default=None)
    parser.add_argument("--min-calibration-rows", type=int, default=20)
    parser.add_argument("--min-threshold-rows", type=int, default=20)
    args = parser.parse_args()
    if args.backtest_rows is None:
        args.backtest_rows = [DEFAULT_BACKTEST_ROWS]
    return args


def main() -> None:
    args = parse_args()
    if args.fbeta_beta <= 0:
        raise ValueError("--fbeta-beta must be positive")
    if args.min_calibration_rows < 1:
        raise ValueError("--min-calibration-rows must be >= 1")
    if args.min_threshold_rows < 1:
        raise ValueError("--min-threshold-rows must be >= 1")

    rows = prepare_rows(pd.concat([read_table(path) for path in args.backtest_rows], ignore_index=True, sort=False))
    if args.calibration_split not in set(rows["split"]):
        raise ValueError(f"Calibration split {args.calibration_split!r} is not present in backtest rows")

    calibrators = fit_bloom_calibrators(rows, args)
    calibrated = apply_bloom_calibrators(rows, calibrators)
    thresholds = attach_calibrator_metadata(select_thresholds(calibrated, args), calibrators)
    calibrated = apply_selected_thresholds(calibrated, thresholds)
    metrics = build_metrics(calibrated, thresholds, args.evaluation_splits)
    calibrator_paths = write_calibrators(calibrators, thresholds, args)

    _write_csv_atomic(thresholds, args.thresholds)
    _write_csv_atomic(metrics, args.metrics)
    write_table(calibrated, args.calibrated_rows)
    write_report(args, thresholds, metrics, calibrator_paths)
    manifest = manifest_payload(
        args=args,
        rows=calibrated,
        thresholds=thresholds,
        metrics=metrics,
        calibrator_paths=calibrator_paths,
    )
    _write_json_atomic(manifest, args.manifest)

    print(f"wrote {args.thresholds}", flush=True)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.calibrated_rows}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
