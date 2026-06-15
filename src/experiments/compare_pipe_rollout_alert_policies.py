#!/usr/bin/env python
"""Compare rollout alert threshold policies on validation and test."""

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
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.pandas_utils import dataframe_rows


POLICY_VERSION = "pipe_grud_rollout_alert_policy_2b_v0"
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_CALIBRATED_ROWS = DEFAULT_REPORT_DIR / "pipe_rollout_calibrated_backtest_rows.parquet"
DEFAULT_THRESHOLDS = DEFAULT_REPORT_DIR / "pipe_rollout_policy_2b_thresholds.csv"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_rollout_policy_2b_metrics.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_rollout_policy_2b_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_rollout_policy_2b_manifest.json"

BALANCED_OBJECTIVES = ["f1", "mcc", "balanced_accuracy", "gmean_pr", "closest_pr"]
SELECTION_OBJECTIVES = ["fixed", "fbeta", *BALANCED_OBJECTIVES]
EVENT_SPECS = [
    {
        "target_event": "irc_alert",
        "score_column": "alert_probability_irc",
        "actual_column": "actual_irc_alert",
        "fixed_score_column": "alert_probability_irc",
        "fixed_threshold_column": "alert_probability_threshold",
    },
    {
        "target_event": "bloom_h",
        "score_column": "rollout_probability_bloom_calibrated",
        "actual_column": "bloom_h",
        "fixed_score_column": "probability_bloom_mean",
        "fixed_threshold_column": "bloom_probability_threshold_h",
    },
]
THRESHOLD_COLUMNS = [
    "policy_version",
    "policy_name",
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
    "calibration_tn",
    "calibration_fp",
    "calibration_fn",
    "calibration_tp",
    "calibration_precision",
    "calibration_recall",
    "calibration_specificity",
    "calibration_f1",
    "calibration_macro_f1",
    "calibration_fbeta",
    "calibration_balanced_accuracy",
    "calibration_mcc",
    "calibration_gmean_pr",
    "calibration_pr_distance",
]
METRIC_COLUMNS = [
    "policy_version",
    "policy_name",
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
    "f1",
    "macro_f1",
    "fbeta",
    "balanced_accuracy",
    "mcc",
    "gmean_pr",
    "pr_distance",
    "pr_auc",
    "roc_auc",
    "brier",
]


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


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def _binary_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype("boolean").astype("Int8")
    if pd.api.types.is_numeric_dtype(values):
        numeric = pd.to_numeric(values, errors="coerce")
        out = pd.Series(pd.NA, index=values.index, dtype="Int8")
        present = numeric.notna()
        out.loc[present] = (numeric.loc[present] != 0).astype("int8")
        return out
    normalized = values.astype("string").str.strip().str.lower()
    out = pd.Series(pd.NA, index=values.index, dtype="Int8")
    out.loc[normalized.isin({"1", "true", "t", "yes", "y"})] = 1
    out.loc[normalized.isin({"0", "false", "f", "no", "n"})] = 0
    return out


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _fbeta_score(precision: float, recall: float, beta: float) -> float:
    if pd.isna(precision) or pd.isna(recall):
        return float("nan")
    beta2 = beta * beta
    denominator = beta2 * precision + recall
    if denominator == 0:
        return 0.0
    return float((1.0 + beta2) * precision * recall / denominator)


def _mcc(tn: int, fp: int, fn: int, tp: int) -> float:
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denominator == 0:
        return float("nan")
    return float(((tp * tn) - (fp * fn)) / denominator)


def _candidate_thresholds(scores: np.ndarray) -> np.ndarray:
    finite = _clip01(scores[np.isfinite(scores)])
    if len(finite) == 0:
        return np.array([0.5], dtype="float64")
    return np.unique(np.concatenate([np.array([0.0, 0.5, 1.0], dtype="float64"), finite]))


def _metric_dict(
    *,
    probability: np.ndarray,
    actual: np.ndarray,
    threshold: float,
    beta: float,
) -> dict[str, Any]:
    probability = _clip01(probability)
    predicted = (probability >= threshold).astype("int8")
    actual = actual.astype("int8")
    tn = int(((predicted == 0) & (actual == 0)).sum())
    fp = int(((predicted == 1) & (actual == 0)).sum())
    fn = int(((predicted == 0) & (actual == 1)).sum())
    tp = int(((predicted == 1) & (actual == 1)).sum())
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    specificity = _safe_rate(tn, tn + fp)
    f1 = _safe_metric(f1_score, actual, predicted, zero_division=0)
    fbeta = _fbeta_score(precision, recall, beta)
    gmean_pr = math.sqrt(max(precision, 0.0) * max(recall, 0.0))
    pr_distance = math.sqrt((1.0 - precision) ** 2 + (1.0 - recall) ** 2)
    return {
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
        "specificity": specificity,
        "f1": f1,
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "fbeta": fbeta,
        "balanced_accuracy": float(np.nanmean([recall, specificity])),
        "mcc": _mcc(tn, fp, fn, tp),
        "gmean_pr": gmean_pr,
        "pr_distance": pr_distance,
        "pr_auc": _safe_metric(average_precision_score, actual, probability),
        "roc_auc": _safe_metric(roc_auc_score, actual, probability),
        "brier": _safe_metric(brier_score_loss, actual, probability),
    }


def _valid_arrays(group: pd.DataFrame, score_column: str, actual_column: str) -> tuple[np.ndarray, np.ndarray]:
    score = pd.to_numeric(group[score_column], errors="coerce")
    actual = pd.to_numeric(group[actual_column], errors="coerce")
    valid = score.notna() & actual.notna()
    return _clip01(score.loc[valid]), actual.loc[valid].astype("int8").to_numpy()


def _constraint_satisfied(row: pd.Series, args: argparse.Namespace) -> bool:
    if args.min_recall is not None and row["recall"] < float(args.min_recall):
        return False
    if args.min_precision is not None and row["precision"] < float(args.min_precision):
        return False
    return True


def select_candidate(candidates: pd.DataFrame, objective: str, args: argparse.Namespace) -> pd.Series:
    candidates = candidates.copy()
    candidates["constraint_satisfied"] = candidates.apply(lambda row: _constraint_satisfied(row, args), axis=1)
    eligible = candidates[candidates["constraint_satisfied"]].copy()
    if eligible.empty:
        eligible = candidates.copy()

    if objective == "fbeta":
        order = ["fbeta", "recall", "precision", "threshold"]
        ascending = [False, False, False, False]
    elif objective == "f1":
        order = ["f1", "mcc", "balanced_accuracy", "precision", "recall", "threshold"]
        ascending = [False, False, False, False, False, False]
    elif objective == "mcc":
        order = ["mcc", "f1", "balanced_accuracy", "precision", "recall", "threshold"]
        ascending = [False, False, False, False, False, False]
    elif objective == "balanced_accuracy":
        order = ["balanced_accuracy", "mcc", "f1", "precision", "recall", "threshold"]
        ascending = [False, False, False, False, False, False]
    elif objective == "gmean_pr":
        order = ["gmean_pr", "f1", "mcc", "precision", "recall", "threshold"]
        ascending = [False, False, False, False, False, False]
    elif objective == "closest_pr":
        order = ["pr_distance", "f1", "mcc", "precision", "recall", "threshold"]
        ascending = [True, False, False, False, False, False]
    else:
        raise ValueError(f"Unsupported selection objective: {objective}")
    return eligible.sort_values(order, ascending=ascending, kind="mergesort").iloc[0]


def validate_rows(rows: pd.DataFrame, objectives: list[str]) -> None:
    required = {"split", "rollout_horizon_months"}
    for spec in EVENT_SPECS:
        required.update([spec["actual_column"]])
        if "fixed" in objectives:
            required.update([spec["fixed_score_column"], spec["fixed_threshold_column"]])
        if any(objective != "fixed" for objective in objectives):
            required.update([spec["score_column"]])
    missing = sorted(column for column in required if column not in rows.columns)
    if missing:
        raise ValueError(f"Calibrated rollout rows are missing required columns: {missing}")


def prepare_rows(rows: pd.DataFrame, objectives: list[str]) -> pd.DataFrame:
    validate_rows(rows, objectives)
    out = rows.copy()
    out["split"] = out["split"].astype(str)
    out["rollout_horizon_months"] = pd.to_numeric(out["rollout_horizon_months"], errors="coerce").astype("int64")
    for spec in EVENT_SPECS:
        out[spec["actual_column"]] = _binary_series(out[spec["actual_column"]])
        for column in [spec["score_column"], spec["fixed_score_column"], spec["fixed_threshold_column"]]:
            if column in out.columns:
                out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def build_thresholds(rows: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    threshold_rows: list[dict[str, Any]] = []
    calibration = rows[rows["split"] == args.calibration_split].copy()
    for spec in EVENT_SPECS:
        for horizon, group in calibration.groupby("rollout_horizon_months", sort=True):
            for objective in args.selection_objectives:
                if objective == "fixed":
                    score_column = spec["fixed_score_column"]
                    threshold_values = pd.to_numeric(group[spec["fixed_threshold_column"]], errors="coerce").dropna()
                    if threshold_values.empty:
                        continue
                    threshold = float(threshold_values.iloc[0])
                    scores, actual = _valid_arrays(group, score_column, spec["actual_column"])
                    if len(actual) < int(args.min_threshold_rows):
                        continue
                    selected = pd.Series(_metric_dict(probability=scores, actual=actual, threshold=threshold, beta=args.fbeta_beta))
                    selected["constraint_satisfied"] = True
                else:
                    score_column = spec["score_column"]
                    scores, actual = _valid_arrays(group, score_column, spec["actual_column"])
                    if len(actual) < int(args.min_threshold_rows):
                        continue
                    candidates = pd.DataFrame(
                        [
                            _metric_dict(
                                probability=scores,
                                actual=actual,
                                threshold=float(threshold),
                                beta=float(args.fbeta_beta),
                            )
                            for threshold in _candidate_thresholds(scores)
                        ]
                    )
                    selected = select_candidate(candidates, objective, args)

                threshold_rows.append(
                    {
                        "policy_version": args.policy_version,
                        "policy_name": objective,
                        "target_event": spec["target_event"],
                        "rollout_horizon_months": int(horizon),
                        "calibration_split": args.calibration_split,
                        "selection_objective": objective,
                        "fbeta_beta": float(args.fbeta_beta),
                        "min_recall": args.min_recall,
                        "min_precision": args.min_precision,
                        "score_column": score_column,
                        "selected_threshold": float(selected["threshold"]),
                        "constraint_satisfied": bool(selected["constraint_satisfied"]),
                        "calibration_rows": int(selected["rows"]),
                        "calibration_positive_rows": int(selected["positive_rows"]),
                        "calibration_positive_rate": float(selected["positive_rate"]),
                        "calibration_predicted_positive_rows": int(selected["predicted_positive_rows"]),
                        "calibration_predicted_positive_rate": float(selected["predicted_positive_rate"]),
                        "calibration_tn": int(selected["tn"]),
                        "calibration_fp": int(selected["fp"]),
                        "calibration_fn": int(selected["fn"]),
                        "calibration_tp": int(selected["tp"]),
                        "calibration_precision": float(selected["precision"]),
                        "calibration_recall": float(selected["recall"]),
                        "calibration_specificity": float(selected["specificity"]),
                        "calibration_f1": float(selected["f1"]),
                        "calibration_macro_f1": float(selected["macro_f1"]),
                        "calibration_fbeta": float(selected["fbeta"]),
                        "calibration_balanced_accuracy": float(selected["balanced_accuracy"]),
                        "calibration_mcc": float(selected["mcc"]),
                        "calibration_gmean_pr": float(selected["gmean_pr"]),
                        "calibration_pr_distance": float(selected["pr_distance"]),
                    }
                )
    if not threshold_rows:
        return pd.DataFrame(columns=THRESHOLD_COLUMNS)
    return (
        pd.DataFrame(threshold_rows)[THRESHOLD_COLUMNS]
        .sort_values(["target_event", "rollout_horizon_months", "policy_name"])
        .reset_index(drop=True)
    )


def build_metrics(rows: pd.DataFrame, thresholds: pd.DataFrame, evaluation_splits: list[str]) -> pd.DataFrame:
    metric_rows: list[dict[str, Any]] = []
    for threshold in dataframe_rows(thresholds):
        spec = next(item for item in EVENT_SPECS if item["target_event"] == threshold.target_event)
        score_column = str(threshold.score_column)
        for split in evaluation_splits:
            group = rows[
                (rows["split"] == split) & (rows["rollout_horizon_months"] == int(threshold.rollout_horizon_months))
            ]
            scores, actual = _valid_arrays(group, score_column, spec["actual_column"])
            if len(actual) == 0:
                continue
            metrics = _metric_dict(
                probability=scores,
                actual=actual,
                threshold=float(threshold.selected_threshold),
                beta=float(threshold.fbeta_beta),
            )
            metric_rows.append(
                {
                    "policy_version": str(threshold.policy_version),
                    "policy_name": str(threshold.policy_name),
                    "target_event": str(threshold.target_event),
                    "split": split,
                    "rollout_horizon_months": int(threshold.rollout_horizon_months),
                    "score_column": score_column,
                    "threshold": float(threshold.selected_threshold),
                    **{column: metrics[column] for column in METRIC_COLUMNS if column in metrics},
                }
            )
    if not metric_rows:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return (
        pd.DataFrame(metric_rows)[METRIC_COLUMNS]
        .sort_values(["target_event", "split", "rollout_horizon_months", "policy_name"])
        .reset_index(drop=True)
    )


def write_report(args: argparse.Namespace, thresholds: pd.DataFrame, metrics: pd.DataFrame) -> None:
    test = metrics[metrics["split"] == "test"].copy()
    lines = [
        f"# {args.model_label} Rollout Alert Policy Frontier Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.",
        "It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.",
        "",
        "## Configuration",
        "",
        f"- Calibrated rows: `{args.calibrated_rows}`",
        f"- Calibration split: `{args.calibration_split}`",
        f"- Evaluation splits: `{args.evaluation_splits}`",
        f"- Selection objectives: `{args.selection_objectives}`",
        f"- F-beta beta: `{args.fbeta_beta}`",
        f"- Minimum recall constraint: `{args.min_recall}`",
        f"- Minimum precision constraint: `{args.min_precision}`",
        "",
        "## Test Frontier",
        "",
        "| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if test.empty:
        lines.append("| `NA` | NA | `NA` | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(test.sort_values(["target_event", "rollout_horizon_months", "policy_name"])):
            lines.append(
                f"| `{row.target_event}` | {int(row.rollout_horizon_months)} | `{row.policy_name}` | "
                f"{_format_float(row.threshold)} | {_format_int(int(row.rows))} | {_format_float(row.positive_rate)} | "
                f"{_format_float(row.recall)} | {_format_float(row.precision)} | "
                f"{_format_float(row.predicted_positive_rate)} | {_format_float(row.f1)} | "
                f"{_format_float(row.fbeta)} | {_format_float(row.mcc)} | {_format_float(row.balanced_accuracy)} |"
            )

    lines.extend(
        [
            "",
            "## Objective Meanings",
            "",
            "- `fixed`: the pre-existing fixed threshold policy.",
            "- `fbeta`: recall-weighted F-beta selection; with beta 2.0 this is the sensitive early-warning policy.",
            "- `f1`: harmonic mean of precision and recall.",
            "- `mcc`: Matthews correlation coefficient, using all confusion-matrix cells.",
            "- `balanced_accuracy`: mean of recall and specificity.",
            "- `gmean_pr`: geometric mean of precision and recall.",
            "- `closest_pr`: smallest Euclidean distance to the ideal precision-recall point `(1, 1)`.",
            "",
            "## Interpretation Guardrails",
            "",
            "- All non-fixed thresholds are selected on validation rows only.",
            "- Test rows are used for evaluation only.",
            f"- These policies compare alert decisions; they do not retrain {args.model_label}.",
            "- A balanced objective is a modeling choice, not an objective truth; it should be defended by the decision context.",
            "",
            "## Outputs",
            "",
            f"- Thresholds: `{args.thresholds}`",
            f"- Metrics: `{args.metrics}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(args: argparse.Namespace, rows: pd.DataFrame, thresholds: pd.DataFrame, metrics: pd.DataFrame) -> dict[str, Any]:
    outputs = [args.thresholds, args.metrics, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "policy_version": args.policy_version,
        "config": {
            "model_label": args.model_label,
            "calibration_split": args.calibration_split,
            "evaluation_splits": args.evaluation_splits,
            "selection_objectives": args.selection_objectives,
            "fbeta_beta": float(args.fbeta_beta),
            "min_recall": args.min_recall,
            "min_precision": args.min_precision,
            "min_threshold_rows": int(args.min_threshold_rows),
        },
        "row_counts": {
            "calibrated_rows": int(len(rows)),
            "threshold_rows": int(len(thresholds)),
            "metric_rows": int(len(metrics)),
        },
        "inputs": [_file_record(args.calibrated_rows)],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrated-rows", type=Path, default=DEFAULT_CALIBRATED_ROWS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model-label", default="PIPE/GRU-D")
    parser.add_argument("--policy-version", default=POLICY_VERSION)
    parser.add_argument("--calibration-split", default="validation")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default=["validation", "test"])
    parser.add_argument("--selection-objectives", type=_parse_csv_list, default=SELECTION_OBJECTIVES)
    parser.add_argument("--fbeta-beta", type=float, default=2.0)
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--min-precision", type=float, default=None)
    parser.add_argument("--min-threshold-rows", type=int, default=20)
    args = parser.parse_args()
    unknown = sorted(set(args.selection_objectives) - set(SELECTION_OBJECTIVES))
    if unknown:
        raise ValueError(f"Unsupported selection objectives: {unknown}")
    return args


def main() -> None:
    args = parse_args()
    if args.fbeta_beta <= 0:
        raise ValueError("--fbeta-beta must be positive")
    if args.min_threshold_rows < 1:
        raise ValueError("--min-threshold-rows must be >= 1")
    rows = prepare_rows(pd.read_parquet(args.calibrated_rows), args.selection_objectives)
    if args.calibration_split not in set(rows["split"]):
        raise ValueError(f"Calibration split {args.calibration_split!r} is not present in calibrated rows")
    thresholds = build_thresholds(rows, args)
    metrics = build_metrics(rows, thresholds, args.evaluation_splits)
    _write_csv_atomic(thresholds, args.thresholds)
    _write_csv_atomic(metrics, args.metrics)
    write_report(args, thresholds, metrics)
    _write_json_atomic(manifest_payload(args, rows, thresholds, metrics), args.manifest)
    print(f"wrote {args.thresholds}", flush=True)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
