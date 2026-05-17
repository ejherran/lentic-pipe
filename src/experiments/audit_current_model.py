#!/usr/bin/env python
"""Audit the frozen current refined fuzzy model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, group_key_tuple
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


DEFAULT_PREDICTIONS = Path("data/fuzzy/current_model_predictions_v0.parquet")
DEFAULT_METRICS = Path("reports/anfis/current_model_metrics.csv")
DEFAULT_REGISTRY = Path("models/anfis/current_model_registry_v0.json")
DEFAULT_CURRENT_MANIFEST = Path("reports/anfis/current_model_manifest.json")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "current_model_audit.md"
DEFAULT_CALIBRATION_BINS = DEFAULT_REPORT_DIR / "current_model_calibration_bins.csv"
DEFAULT_LIFT_TABLE = DEFAULT_REPORT_DIR / "current_model_lift_table.csv"
DEFAULT_CONFUSION = DEFAULT_REPORT_DIR / "current_model_confusion_by_group.csv"
DEFAULT_ERROR_EXAMPLES = DEFAULT_REPORT_DIR / "current_model_error_examples.csv"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "current_model_audit_manifest.json"

EVIDENCE_COLUMNS = ["full_evidence", "exogenous_evidence"]
ERROR_COLUMNS = [
    "model_version",
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "split",
    "error_type",
    "probability_bloom_h",
    "threshold_bloom_h",
    "bloom_h",
    "target_risk_chla_h",
    "current_model_score_name",
    "source_selector_score_name",
    "full_evidence",
    "exogenous_evidence",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
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


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return _json_sanitize(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


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
        json.dump(_json_sanitize(payload), handle, indent=2, ensure_ascii=False, default=_json_default, allow_nan=False)
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
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def _evidence_band(values: pd.Series) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce")
    return pd.cut(
        clean,
        bins=[-np.inf, 0.0, 0.33, 0.66, np.inf],
        labels=["missing", "low", "medium", "high"],
        include_lowest=True,
    ).astype("object").fillna("missing")


def _group_specs(frame: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    groups = [("all", frame)]
    groups.extend((str(source), group) for source, group in frame.groupby("source_id", dropna=False))
    return groups


def build_calibration_bins(predictions: pd.DataFrame, bins: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, horizon_split in predictions.groupby(["horizon_months", "split"], sort=True):
        horizon, split = group_key_tuple(key)
        for source_id, group in _group_specs(horizon_split):
            probability = _clip01(group["probability_bloom_h"])
            y = group["bloom_h"].astype("int8").to_numpy()
            bin_ids = np.minimum(np.floor(probability * bins).astype("int64"), bins - 1)
            for bin_id in range(bins):
                mask = bin_ids == bin_id
                rows.append(
                    {
                        "model_version": "current_refined_fuzzy_v0",
                        "source_id": source_id,
                        "horizon_months": int(horizon),
                        "split": split,
                        "bin": int(bin_id),
                        "bin_left": float(bin_id / bins),
                        "bin_right": float((bin_id + 1) / bins),
                        "rows": int(mask.sum()),
                        "bloom_positive": int(y[mask].sum()) if mask.any() else 0,
                        "mean_pred_probability": float(probability[mask].mean()) if mask.any() else np.nan,
                        "observed_bloom_rate": float(y[mask].mean()) if mask.any() else np.nan,
                        "abs_calibration_error": (
                            float(abs(probability[mask].mean() - y[mask].mean())) if mask.any() else np.nan
                        ),
                    }
                )
    return pd.DataFrame(rows)


def calibration_summary(calibration_bins: pd.DataFrame) -> pd.DataFrame:
    rows = []
    non_empty = calibration_bins[calibration_bins["rows"] > 0].copy()
    for keys, group in non_empty.groupby(["source_id", "horizon_months", "split"], sort=True):
        source_id, horizon, split = keys
        total = int(group["rows"].sum())
        weighted_abs = float((group["abs_calibration_error"] * group["rows"]).sum() / total) if total else np.nan
        rows.append(
            {
                "source_id": source_id,
                "horizon_months": int(horizon),
                "split": split,
                "rows": total,
                "expected_blooms": float((group["mean_pred_probability"] * group["rows"]).sum()),
                "observed_blooms": int(group["bloom_positive"].sum()),
                "weighted_abs_calibration_error": weighted_abs,
                "max_abs_calibration_error": float(group["abs_calibration_error"].max()),
            }
        )
    return pd.DataFrame(rows)


def build_lift_table(predictions: pd.DataFrame, deciles: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, horizon_split in predictions.groupby(["horizon_months", "split"], sort=True):
        horizon, split = group_key_tuple(key)
        for source_id, group in _group_specs(horizon_split):
            if group.empty:
                continue
            ranked = group.sort_values("probability_bloom_h", ascending=False).reset_index(drop=True)
            y = ranked["bloom_h"].astype("int8").to_numpy()
            probability = _clip01(ranked["probability_bloom_h"])
            decile_ids = np.minimum(np.floor(np.arange(len(ranked)) * deciles / len(ranked)).astype("int64") + 1, deciles)
            total_positive = int(y.sum())
            base_rate = float(y.mean()) if len(y) else np.nan
            cumulative_positive = 0
            for decile in range(1, deciles + 1):
                mask = decile_ids == decile
                positive = int(y[mask].sum())
                cumulative_positive += positive
                rate = float(y[mask].mean()) if mask.any() else np.nan
                rows.append(
                    {
                        "model_version": "current_refined_fuzzy_v0",
                        "source_id": source_id,
                        "horizon_months": int(horizon),
                        "split": split,
                        "decile": int(decile),
                        "rows": int(mask.sum()),
                        "bloom_positive": positive,
                        "bloom_rate": rate,
                        "base_bloom_rate": base_rate,
                        "lift": _safe_rate(rate, base_rate),
                        "capture_rate": _safe_rate(positive, total_positive),
                        "cumulative_capture_rate": _safe_rate(cumulative_positive, total_positive),
                        "mean_pred_probability": float(probability[mask].mean()) if mask.any() else np.nan,
                        "min_pred_probability": float(probability[mask].min()) if mask.any() else np.nan,
                        "max_pred_probability": float(probability[mask].max()) if mask.any() else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def evaluate_group(
    *,
    group_type: str,
    group_value: str,
    source_id: str,
    horizon: int,
    split: str,
    group: pd.DataFrame,
) -> dict[str, Any]:
    y = group["bloom_h"].astype("int8").to_numpy()
    probability = _clip01(group["probability_bloom_h"])
    predicted = group["predicted_bloom_h"].astype("int8").to_numpy()
    matrix = confusion_matrix(y, predicted, labels=[0, 1])
    tn, fp, fn, tp = [int(value) for value in matrix.ravel()]
    return {
        "model_version": "current_refined_fuzzy_v0",
        "group_type": group_type,
        "group_value": group_value,
        "source_id": source_id,
        "horizon_months": int(horizon),
        "split": split,
        "rows": int(len(group)),
        "threshold": float(group["threshold_bloom_h"].iloc[0]),
        "bloom_positive": int(y.sum()),
        "bloom_rate": float(y.mean()) if len(y) else np.nan,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": _safe_metric(precision_score, y, predicted, zero_division=0),
        "recall": _safe_metric(recall_score, y, predicted, zero_division=0),
        "specificity": _safe_rate(tn, tn + fp),
        "false_positive_rate": _safe_rate(fp, fp + tn),
        "false_negative_rate": _safe_rate(fn, fn + tp),
        "macro_f1": _safe_metric(f1_score, y, predicted, average="macro", zero_division=0),
        "pr_auc": _safe_metric(average_precision_score, y, probability),
        "roc_auc": _safe_metric(roc_auc_score, y, probability),
        "brier": _safe_metric(brier_score_loss, y, probability),
    }


def build_confusion_by_group(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    enriched = predictions.copy()
    for evidence_column in EVIDENCE_COLUMNS:
        if evidence_column in enriched.columns:
            enriched[f"{evidence_column}_band"] = _evidence_band(enriched[evidence_column])

    for key, horizon_split in enriched.groupby(["horizon_months", "split"], sort=True):
        horizon, split = group_key_tuple(key)
        rows.append(
            evaluate_group(
                group_type="overall",
                group_value="all",
                source_id="all",
                horizon=int(horizon),
                split=split,
                group=horizon_split,
            )
        )
        for source_id, source_group in horizon_split.groupby("source_id", dropna=False):
            rows.append(
                evaluate_group(
                    group_type="source",
                    group_value=str(source_id),
                    source_id=str(source_id),
                    horizon=int(horizon),
                    split=split,
                    group=source_group,
                )
            )
        for evidence_column in EVIDENCE_COLUMNS:
            band_column = f"{evidence_column}_band"
            if band_column not in horizon_split.columns:
                continue
            for band, band_group in horizon_split.groupby(band_column, dropna=False):
                rows.append(
                    evaluate_group(
                        group_type=f"{evidence_column}_band",
                        group_value=str(band),
                        source_id="all",
                        horizon=int(horizon),
                        split=split,
                        group=band_group,
                    )
                )
    return pd.DataFrame(rows)


def build_error_examples(predictions: pd.DataFrame, examples_per_group: int) -> pd.DataFrame:
    frame = predictions.copy()
    frame["bloom_h_int"] = frame["bloom_h"].astype("int8")
    frame["predicted_int"] = frame["predicted_bloom_h"].astype("int8")
    false_positive = frame[(frame["predicted_int"] == 1) & (frame["bloom_h_int"] == 0)].copy()
    false_positive["error_type"] = "false_positive"
    false_positive["_sort_key"] = -false_positive["probability_bloom_h"].astype("float64")
    false_negative = frame[(frame["predicted_int"] == 0) & (frame["bloom_h_int"] == 1)].copy()
    false_negative["error_type"] = "false_negative"
    false_negative["_sort_key"] = false_negative["probability_bloom_h"].astype("float64")
    errors = pd.concat([false_positive, false_negative], ignore_index=True, sort=False)
    if errors.empty:
        return pd.DataFrame(columns=ERROR_COLUMNS)
    parts = []
    for _, group in errors.groupby(["horizon_months", "split", "error_type"], sort=True):
        parts.append(group.sort_values("_sort_key").head(examples_per_group))
    out = pd.concat(parts, ignore_index=True)
    for column in ERROR_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[ERROR_COLUMNS].sort_values(["horizon_months", "split", "error_type", "probability_bloom_h"])


def write_report(
    *,
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    calibration: pd.DataFrame,
    lift: pd.DataFrame,
    confusion: pd.DataFrame,
    error_examples: pd.DataFrame,
) -> None:
    calibration_all = calibration[
        (calibration["source_id"] == "all") & (calibration["split"] == "test")
    ].copy()
    lift_top = lift[
        (lift["source_id"] == "all") & (lift["split"] == "test") & (lift["decile"] == 1)
    ].copy()
    evidence_confusion = confusion[
        (confusion["split"] == "test") & (confusion["group_type"].isin(["full_evidence_band", "exogenous_evidence_band"]))
    ].copy()
    test_metrics = metrics[(metrics["source_id"] == "all") & (metrics["split"] == "test")].copy() if not metrics.empty else pd.DataFrame()
    lines = [
        "# Current Model Audit Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This audit reviews the frozen `current_refined_fuzzy_v0` predictions.",
        "It does not retrain, reselect, or alter model outputs.",
        "",
        "## Headline Test Metrics",
        "",
        "| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(test_metrics.sort_values("horizon_months")):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | "
            f"{_format_float(row.roc_auc)} | {_format_float(row.brier)} | {_format_float(row.recall)} | "
            f"{_format_float(row.macro_f1)} |"
        )
    lines.extend(
        [
            "",
            "## Calibration Summary",
            "",
            "| horizon | rows | expected blooms | observed blooms | weighted abs error | max bin abs error |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(calibration_all.sort_values("horizon_months")):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_float(row.expected_blooms)} | "
            f"{_format_int(int(row.observed_blooms))} | {_format_float(row.weighted_abs_calibration_error)} | "
            f"{_format_float(row.max_abs_calibration_error)} |"
        )
    lines.extend(
        [
            "",
            "## Top Decile Lift",
            "",
            "| horizon | rows | bloom rate | base rate | lift | capture rate | min probability |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(lift_top.sort_values("horizon_months")):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_float(row.bloom_rate)} | "
            f"{_format_float(row.base_bloom_rate)} | {_format_float(row.lift)} | "
            f"{_format_float(row.capture_rate)} | {_format_float(row.min_pred_probability)} |"
        )
    if not evidence_confusion.empty:
        lines.extend(
            [
                "",
                "## Evidence Band Test Metrics",
                "",
                "| evidence group | band | horizon | rows | PR-AUC | Brier | recall | macro-F1 |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataframe_rows(evidence_confusion.sort_values(["group_type", "horizon_months", "group_value"])):
            lines.append(
                f"| `{row.group_type}` | `{row.group_value}` | {int(row.horizon_months)} | "
                f"{_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | {_format_float(row.brier)} | "
                f"{_format_float(row.recall)} | {_format_float(row.macro_f1)} |"
            )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- LakeBeD test and validation support is small compared with AquaMatch and WQP; source-level metrics for LakeBeD are high variance.",
            "- `source_selector` is selected from validation and should be re-audited after adding new data sources.",
            "- Error examples are high-confidence false positives and low-confidence false negatives, not causal explanations.",
            "",
            "## Outputs",
            "",
            f"- Calibration bins: `{args.calibration_bins}`",
            f"- Lift table: `{args.lift_table}`",
            f"- Confusion by group: `{args.confusion}`",
            f"- Error examples: `{args.error_examples}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    calibration_bins: pd.DataFrame,
    lift: pd.DataFrame,
    confusion: pd.DataFrame,
    error_examples: pd.DataFrame,
) -> dict[str, Any]:
    inputs = [args.predictions]
    for optional in [args.metrics, args.registry, args.current_manifest]:
        if optional.exists():
            inputs.append(optional)
    outputs = [args.report, args.calibration_bins, args.lift_table, args.confusion, args.error_examples]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": "current_refined_fuzzy_v0",
        "audit": "current_model_audit_v0",
        "row_counts": {
            "prediction_rows": int(len(predictions)),
            "metrics_rows": int(len(metrics)),
            "calibration_bin_rows": int(len(calibration_bins)),
            "lift_rows": int(len(lift)),
            "confusion_rows": int(len(confusion)),
            "error_example_rows": int(len(error_examples)),
        },
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--current-manifest", type=Path, default=DEFAULT_CURRENT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--calibration-bins", type=Path, default=DEFAULT_CALIBRATION_BINS)
    parser.add_argument("--lift-table", type=Path, default=DEFAULT_LIFT_TABLE)
    parser.add_argument("--confusion", type=Path, default=DEFAULT_CONFUSION)
    parser.add_argument("--error-examples", type=Path, default=DEFAULT_ERROR_EXAMPLES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bins", type=int, default=10)
    parser.add_argument("--deciles", type=int, default=10)
    parser.add_argument("--examples-per-group", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"loading predictions {args.predictions}", flush=True)
    predictions = pd.read_parquet(args.predictions)
    print(f"prediction rows={len(predictions):,}", flush=True)
    metrics = pd.read_csv(args.metrics) if args.metrics.exists() else pd.DataFrame()

    print("building calibration bins", flush=True)
    calibration_bins = build_calibration_bins(predictions, bins=args.bins)
    calibration = calibration_summary(calibration_bins)
    print("building lift table", flush=True)
    lift = build_lift_table(predictions, deciles=args.deciles)
    print("building confusion and evidence-band metrics", flush=True)
    confusion = build_confusion_by_group(predictions)
    print("collecting error examples", flush=True)
    error_examples = build_error_examples(predictions, examples_per_group=args.examples_per_group)

    _write_csv_atomic(calibration_bins, args.calibration_bins)
    _write_csv_atomic(lift, args.lift_table)
    _write_csv_atomic(confusion, args.confusion)
    _write_csv_atomic(error_examples, args.error_examples)
    write_report(
        args=args,
        predictions=predictions,
        metrics=metrics,
        calibration=calibration,
        lift=lift,
        confusion=confusion,
        error_examples=error_examples,
    )
    manifest = build_manifest(
        args=args,
        predictions=predictions,
        metrics=metrics,
        calibration_bins=calibration_bins,
        lift=lift,
        confusion=confusion,
        error_examples=error_examples,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.calibration_bins}", flush=True)
    print(f"wrote {args.lift_table}", flush=True)
    print(f"wrote {args.confusion}", flush=True)
    print(f"wrote {args.error_examples}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
