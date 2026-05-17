#!/usr/bin/env python
"""Apply the selected refined fuzzy model and freeze current model outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, group_key_tuple
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, recall_score, roc_auc_score


DEFAULT_REFINED_SCORES = Path("data/fuzzy/refined_scores_v0.parquet")
DEFAULT_SELECTION = Path("reports/anfis/refined_fuzzy_selection.csv")
DEFAULT_SOURCE_SELECTION = Path("reports/anfis/refined_fuzzy_source_selection.csv")
DEFAULT_REFINED_MANIFEST = Path("reports/anfis/refined_fuzzy_manifest.json")
DEFAULT_PREDICTIONS = Path("data/fuzzy/current_model_predictions_v0.parquet")
DEFAULT_METRICS = Path("reports/anfis/current_model_metrics.csv")
DEFAULT_REPORT = Path("reports/anfis/current_model_report.md")
DEFAULT_REGISTRY = Path("models/anfis/current_model_registry_v0.json")
DEFAULT_MANIFEST = Path("reports/anfis/current_model_manifest.json")

KEY_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
TARGET_COLUMNS = ["bloom_h", "target_risk_chla_h"]
AUDIT_COLUMNS = [
    "baseline_calibrated",
    "irc1_calibrated",
    "irc1_no_chla_calibrated",
    "source_selector",
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


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def load_selection(path: Path) -> pd.DataFrame:
    selection = pd.read_csv(path)
    required = {"horizon_months", "score_name", "selected_threshold", "selection_policy"}
    missing = required.difference(selection.columns)
    if missing:
        raise ValueError(f"Selection file {path} is missing columns: {sorted(missing)}")
    duplicated = selection["horizon_months"].duplicated()
    if duplicated.any():
        horizons = selection.loc[duplicated, "horizon_months"].tolist()
        raise ValueError(f"Selection file {path} has duplicated horizons: {horizons}")
    return selection.sort_values("horizon_months").reset_index(drop=True)


def load_source_selection(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["source_id", "selected_score", "horizon_months"])
    return pd.read_csv(path)


def apply_selection(
    refined_scores: pd.DataFrame,
    selection: pd.DataFrame,
    source_selection: pd.DataFrame | None = None,
) -> pd.DataFrame:
    output_columns = [column for column in KEY_COLUMNS + TARGET_COLUMNS + AUDIT_COLUMNS if column in refined_scores.columns]
    output = refined_scores[output_columns].copy()
    output["current_model_score_name"] = ""
    output["probability_bloom_h"] = np.nan
    output["threshold_bloom_h"] = np.nan
    output["predicted_bloom_h"] = False
    output["selection_policy"] = ""

    for row in dataframe_rows(selection):
        horizon = int(row.horizon_months)
        score_name = str(row.score_name)
        threshold = float(row.selected_threshold)
        if score_name not in refined_scores.columns:
            raise ValueError(f"Selected score `{score_name}` for horizon {horizon} is missing from refined scores")
        mask = refined_scores["horizon_months"].astype("int64") == horizon
        probability = _clip01(refined_scores.loc[mask, score_name])
        output.loc[mask, "current_model_score_name"] = score_name
        output.loc[mask, "probability_bloom_h"] = probability
        output.loc[mask, "threshold_bloom_h"] = threshold
        output.loc[mask, "predicted_bloom_h"] = probability >= threshold
        output.loc[mask, "selection_policy"] = str(row.selection_policy)

    if source_selection is not None and not source_selection.empty:
        source_cols = ["source_id", "horizon_months", "selected_score"]
        if set(source_cols).issubset(source_selection.columns):
            source_map = source_selection[source_cols].rename(columns={"selected_score": "source_selector_score_name"})
            output = output.merge(source_map, on=["source_id", "horizon_months"], how="left")
    if "source_selector_score_name" not in output.columns:
        output["source_selector_score_name"] = ""
    output["model_version"] = "current_refined_fuzzy_v0"
    return output


def evaluate_current_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    if "bloom_h" not in predictions.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_specs = [(["horizon_months", "split"], "all"), (["source_id", "horizon_months", "split"], "source")]
    for group_columns, source_mode in group_specs:
        for keys, group in predictions.groupby(group_columns, dropna=False):
            key_parts = group_key_tuple(keys)
            if source_mode == "all":
                horizon, split = key_parts
                source_id = "all"
            else:
                source_id, horizon, split = key_parts
            y = group["bloom_h"].astype("int8").to_numpy()
            probability = _clip01(group["probability_bloom_h"])
            predicted = group["predicted_bloom_h"].astype("int8").to_numpy()
            threshold = float(group["threshold_bloom_h"].iloc[0])
            rows.append(
                {
                    "model_version": "current_refined_fuzzy_v0",
                    "source_id": source_id,
                    "horizon_months": int(horizon),
                    "split": split,
                    "rows": int(len(group)),
                    "threshold": threshold,
                    "bloom_positive": int(y.sum()),
                    "bloom_rate": float(y.mean()) if len(y) else float("nan"),
                    "pr_auc": _safe_metric(average_precision_score, y, probability),
                    "roc_auc": _safe_metric(roc_auc_score, y, probability),
                    "brier": _safe_metric(brier_score_loss, y, probability),
                    "recall": _safe_metric(recall_score, y, predicted, zero_division=0),
                    "macro_f1": _safe_metric(f1_score, y, predicted, average="macro", zero_division=0),
                }
            )
    return pd.DataFrame(rows).sort_values(["horizon_months", "split", "source_id"]).reset_index(drop=True)


def build_registry(
    *,
    args: argparse.Namespace,
    selection: pd.DataFrame,
    source_selection: pd.DataFrame,
    predictions: pd.DataFrame,
) -> dict[str, Any]:
    inputs = [args.refined_scores, args.selection]
    if args.source_selection.exists():
        inputs.append(args.source_selection)
    if args.refined_manifest.exists():
        inputs.append(args.refined_manifest)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": "current_refined_fuzzy_v0",
        "model_family": "refined_expert_fuzzy_ensemble_v0",
        "purpose": "current best bloom probability model by horizon",
        "selection": selection.to_dict(orient="records"),
        "source_selection": source_selection.to_dict(orient="records") if not source_selection.empty else [],
        "prediction_rows": int(len(predictions)),
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "prediction_output": args.predictions.as_posix(),
    }


def write_report(
    *,
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    selection: pd.DataFrame,
) -> None:
    selected_summary = (
        predictions.groupby(["horizon_months", "current_model_score_name"], dropna=False)
        .agg(rows=("site_id", "size"), threshold=("threshold_bloom_h", "first"))
        .reset_index()
        .sort_values("horizon_months")
    )
    test_metrics = metrics[(metrics["source_id"] == "all") & (metrics["split"] == "test")].copy() if not metrics.empty else pd.DataFrame()
    lines = [
        "# Current Model Application Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This report applies the selected refined fuzzy score per horizon and freezes current model predictions.",
        "The selected scores were chosen upstream on `validation`; this script only applies that frozen selection.",
        "",
        "## Applied Scores",
        "",
        "| horizon | score | rows | threshold |",
        "|---:|---|---:|---:|",
    ]
    for row in dataframe_rows(selected_summary):
        lines.append(
            f"| {int(row.horizon_months)} | `{row.current_model_score_name}` | "
            f"{_format_int(int(row.rows))} | {_format_float(row.threshold)} |"
        )

    if not test_metrics.empty:
        lines.extend(
            [
                "",
                "## Test Metrics",
                "",
                "| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |",
                "|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataframe_rows(test_metrics.sort_values("horizon_months")):
            lines.append(
                f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | "
                f"{_format_float(row.roc_auc)} | {_format_float(row.brier)} | {_format_float(row.recall)} | "
                f"{_format_float(row.macro_f1)} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Predictions: `{args.predictions}`",
            f"- Metrics: `{args.metrics}`",
            f"- Registry: `{args.registry}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    selection: pd.DataFrame,
    source_selection: pd.DataFrame,
) -> dict[str, Any]:
    inputs = [args.refined_scores, args.selection]
    if args.source_selection.exists():
        inputs.append(args.source_selection)
    if args.refined_manifest.exists():
        inputs.append(args.refined_manifest)
    outputs = [args.predictions, args.metrics, args.report, args.registry]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": "current_refined_fuzzy_v0",
        "model_family": "refined_expert_fuzzy_ensemble_v0",
        "row_counts": {
            "prediction_rows": int(len(predictions)),
            "metrics_rows": int(len(metrics)),
            "selection_rows": int(len(selection)),
            "source_selection_rows": int(len(source_selection)),
        },
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refined-scores", type=Path, default=DEFAULT_REFINED_SCORES)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--source-selection", type=Path, default=DEFAULT_SOURCE_SELECTION)
    parser.add_argument("--refined-manifest", type=Path, default=DEFAULT_REFINED_MANIFEST)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"loading refined scores {args.refined_scores}", flush=True)
    refined_scores = pd.read_parquet(args.refined_scores)
    print(f"refined score rows={len(refined_scores):,}", flush=True)
    print(f"loading selection {args.selection}", flush=True)
    selection = load_selection(args.selection)
    source_selection = load_source_selection(args.source_selection)

    predictions = apply_selection(refined_scores, selection, source_selection)
    metrics = evaluate_current_predictions(predictions)
    registry = build_registry(args=args, selection=selection, source_selection=source_selection, predictions=predictions)

    _write_parquet_atomic(predictions, args.predictions)
    _write_csv_atomic(metrics, args.metrics)
    _write_json_atomic(registry, args.registry)
    write_report(args=args, predictions=predictions, metrics=metrics, selection=selection)
    manifest = build_manifest(
        args=args,
        predictions=predictions,
        metrics=metrics,
        selection=selection,
        source_selection=source_selection,
    )
    _write_json_atomic(manifest, args.manifest)

    print(f"wrote {args.predictions}", flush=True)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.registry}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
