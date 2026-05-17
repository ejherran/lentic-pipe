#!/usr/bin/env python
"""Select and calibrate baseline models without using the test split for decisions."""

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

import joblib
import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    recall_score,
    roc_auc_score,
)

from src.experiments import baselines as baseline_run


DEFAULT_BASELINE_METRICS = Path("reports/baselines/baseline_metrics.csv")
DEFAULT_BASELINE_MANIFEST = Path("reports/baselines/baseline_manifest.json")
DEFAULT_MODELS_DIR = Path("models/baselines")
DEFAULT_REPORTS_DIR = Path("reports/baselines")
DEFAULT_SELECTION = DEFAULT_REPORTS_DIR / "baseline_selection.csv"
DEFAULT_CALIBRATED_METRICS = DEFAULT_REPORTS_DIR / "baseline_calibrated_metrics.csv"
DEFAULT_REPORT = DEFAULT_REPORTS_DIR / "baseline_selection_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORTS_DIR / "baseline_selection_manifest.json"
DEFAULT_CALIBRATORS_DIR = DEFAULT_MODELS_DIR / "calibrators"

BLOOM_CANDIDATES = ["constant", "source_month", "site_month", "persistence", "logistic_sgd"]
RISK_CANDIDATES = ["constant", "source_month", "site_month", "persistence", "ridge_sgd"]
SPLITS_TO_REPORT = ["validation", "test"]


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


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _select_bloom(metrics: pd.DataFrame) -> pd.DataFrame:
    validation = metrics[
        (metrics["split"] == "validation")
        & (metrics["model"].isin(BLOOM_CANDIDATES))
        & metrics["pr_auc"].notna()
    ].copy()
    validation = validation.sort_values(
        ["horizon_months", "pr_auc", "brier", "macro_f1"],
        ascending=[True, False, True, False],
        na_position="last",
    )
    selected = validation.groupby("horizon_months", as_index=False).head(1).copy()
    selected["selection_task"] = "bloom"
    selected["selection_policy"] = "validation max PR-AUC; tie min Brier; tie max macro-F1"
    return selected


def _select_risk(metrics: pd.DataFrame) -> pd.DataFrame:
    validation = metrics[
        (metrics["split"] == "validation")
        & (metrics["model"].isin(RISK_CANDIDATES))
        & metrics["mae_risk"].notna()
    ].copy()
    validation = validation.sort_values(
        ["horizon_months", "mae_risk", "rmse_risk"],
        ascending=[True, True, True],
        na_position="last",
    )
    selected = validation.groupby("horizon_months", as_index=False).head(1).copy()
    selected["selection_task"] = "risk"
    selected["selection_policy"] = "validation min MAE risk; tie min RMSE risk"
    return selected


def select_baselines(metrics: pd.DataFrame) -> pd.DataFrame:
    selected = pd.concat([_select_bloom(metrics), _select_risk(metrics)], ignore_index=True)
    return selected[
        [
            "selection_task",
            "horizon_months",
            "model",
            "task",
            "selection_policy",
            "rows",
            "bloom_rate",
            "pr_auc",
            "roc_auc",
            "brier",
            "recall",
            "macro_f1",
            "rmse_risk",
            "mae_risk",
        ]
    ].sort_values(["selection_task", "horizon_months"]).reset_index(drop=True)


def _load_artifact(models_dir: Path, model_name: str, horizon: int) -> Any:
    return joblib.load(models_dir / f"{model_name}_h{horizon}.joblib")


def predict_bloom_probability(
    frame: pd.DataFrame,
    model_name: str,
    horizon: int,
    args: argparse.Namespace,
    train_frame: pd.DataFrame | None = None,
) -> np.ndarray:
    train = train_frame.copy() if train_frame is not None else frame[frame["split"] == "train"].copy()
    fallback_probability = float(train["bloom_h"].mean())
    fallback_risk = float(train["target_risk_chla_h"].mean())

    if model_name == "constant":
        return np.full(len(frame), fallback_probability, dtype="float64")
    if model_name == "persistence":
        probability, _ = baseline_run.persistence_predictions(frame, fallback_probability, fallback_risk)
        return probability
    if model_name in {"source_month", "site_month"}:
        payload = _load_artifact(args.models_dir, model_name, horizon)
        keys = ["source_id", "origin_month"] if model_name == "source_month" else ["source_id", "site_id", "origin_month"]
        probability, _ = baseline_run.predict_from_climatology(
            frame,
            payload["table"],
            keys,
            float(payload["fallback_probability"]),
            float(payload["fallback_risk"]),
        )
        return probability
    if model_name == "logistic_sgd":
        model = _load_artifact(args.models_dir, model_name, horizon)
        return baseline_run._positive_class_probability(model, frame, args.numeric_features)
    raise ValueError(f"Unsupported bloom model for calibration: {model_name}")


def _candidate_thresholds(probability: np.ndarray) -> np.ndarray:
    quantiles = np.unique(np.quantile(probability, np.linspace(0.01, 0.99, 99)))
    fixed = np.linspace(0.05, 0.95, 19)
    return np.unique(np.concatenate([fixed, quantiles, np.array([0.5])]))


def choose_threshold(y_true: np.ndarray, probability: np.ndarray) -> tuple[float, float]:
    best_threshold = 0.5
    best_score = -1.0
    for threshold in _candidate_thresholds(probability):
        pred = (probability >= threshold).astype("int8")
        score = f1_score(y_true, pred, average="macro", zero_division=0)
        if score > best_score:
            best_score = float(score)
            best_threshold = float(threshold)
    return best_threshold, best_score


def evaluate_bloom(
    *,
    model: str,
    horizon: int,
    split: str,
    phase: str,
    y_true: np.ndarray,
    probability: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    probability = _clip01(probability)
    predicted = (probability >= threshold).astype("int8")
    matrix = confusion_matrix(y_true, predicted, labels=[0, 1])
    return {
        "selection_task": "bloom",
        "phase": phase,
        "model": model,
        "horizon_months": horizon,
        "split": split,
        "rows": int(len(y_true)),
        "threshold": threshold,
        "bloom_positive": int(y_true.sum()),
        "bloom_rate": float(y_true.mean()),
        "pr_auc": _safe_metric(average_precision_score, y_true, probability),
        "roc_auc": _safe_metric(roc_auc_score, y_true, probability),
        "brier": _safe_metric(brier_score_loss, y_true, probability),
        "recall": _safe_metric(recall_score, y_true, predicted, zero_division=0),
        "macro_f1": _safe_metric(f1_score, y_true, predicted, average="macro", zero_division=0),
        "tn": int(matrix[0, 0]),
        "fp": int(matrix[0, 1]),
        "fn": int(matrix[1, 0]),
        "tp": int(matrix[1, 1]),
    }


def calibration_table(
    *,
    model: str,
    horizon: int,
    split: str,
    phase: str,
    y_true: np.ndarray,
    probability: np.ndarray,
    bins: int,
) -> pd.DataFrame:
    probability = _clip01(probability)
    bin_ids = np.minimum(np.floor(probability * bins).astype("int64"), bins - 1)
    rows = []
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        rows.append(
            {
                "phase": phase,
                "model": model,
                "horizon_months": horizon,
                "split": split,
                "bin": bin_id,
                "bin_left": bin_id / bins,
                "bin_right": (bin_id + 1) / bins,
                "rows": int(mask.sum()),
                "mean_pred_probability": float(probability[mask].mean()) if mask.any() else np.nan,
                "observed_bloom_rate": float(y_true[mask].mean()) if mask.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def evaluate_risk_selection(selection: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    risk_selection = selection[selection["selection_task"] == "risk"]
    for selected in dataframe_rows(risk_selection):
        subset = metrics[
            (metrics["horizon_months"] == selected.horizon_months)
            & (metrics["model"] == selected.model)
            & (metrics["split"].isin(SPLITS_TO_REPORT))
        ].copy()
        subset["selection_task"] = "risk"
        subset["phase"] = "selected"
        rows.append(subset)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out[
        [
            "selection_task",
            "phase",
            "model",
            "horizon_months",
            "split",
            "rows",
            "rmse_risk",
            "mae_risk",
            "pr_auc",
            "roc_auc",
            "brier",
            "recall",
            "macro_f1",
        ]
    ]


def run_calibration(
    selection: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[Path]]:
    load_args = argparse.Namespace(
        splits=args.splits,
        panel=args.panel,
        horizons=args.horizons,
        sample_rows_per_split=0,
        random_seed=args.random_seed,
    )
    splits, panel, available_features = baseline_run.load_inputs(load_args)
    args.numeric_features = baseline_run.feature_columns_for_model(available_features)

    calibrated_rows: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    calibration_paths: list[Path] = []

    bloom_selection = selection[selection["selection_task"] == "bloom"]
    for selected in dataframe_rows(bloom_selection):
        horizon = int(selected.horizon_months)
        model_name = str(selected.model)
        print(f"h{horizon}: reconstructing selected bloom baseline `{model_name}`", flush=True)
        frame = baseline_run.make_horizon_frame(splits, panel, horizon, load_args)
        train = frame[frame["split"] == "train"].copy()
        validation = frame[frame["split"] == "validation"].copy()
        test = frame[frame["split"] == "test"].copy()

        validation_y = validation["bloom_h"].to_numpy(dtype="int8")
        validation_probability_raw = predict_bloom_probability(validation, model_name, horizon, args, train)

        calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        calibrator.fit(validation_probability_raw, validation_y)
        validation_probability_calibrated = _clip01(calibrator.predict(validation_probability_raw))
        threshold, threshold_macro_f1 = choose_threshold(validation_y, validation_probability_calibrated)

        calibrator_path = args.calibrators_dir / f"{model_name}_h{horizon}_isotonic.joblib"
        calibrator_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": model_name,
                "horizon_months": horizon,
                "calibrator": calibrator,
                "threshold": threshold,
                "threshold_selection": "validation max macro-F1 on calibrated probabilities",
                "threshold_macro_f1_validation": threshold_macro_f1,
            },
            calibrator_path,
        )
        artifacts.append(
            {
                "model": model_name,
                "horizon_months": horizon,
                "calibration": "isotonic",
                **_file_record(calibrator_path),
            }
        )

        for split_name, split_frame in [("validation", validation), ("test", test)]:
            y = split_frame["bloom_h"].to_numpy(dtype="int8")
            raw_probability = validation_probability_raw if split_name == "validation" else predict_bloom_probability(
                split_frame,
                model_name,
                horizon,
                args,
                train,
            )
            calibrated_probability = (
                validation_probability_calibrated
                if split_name == "validation"
                else _clip01(calibrator.predict(raw_probability))
            )
            calibrated_rows.append(
                evaluate_bloom(
                    model=model_name,
                    horizon=horizon,
                    split=split_name,
                    phase="uncalibrated_selected",
                    y_true=y,
                    probability=raw_probability,
                    threshold=0.5,
                )
            )
            calibrated_rows.append(
                evaluate_bloom(
                    model=model_name,
                    horizon=horizon,
                    split=split_name,
                    phase="isotonic_calibrated",
                    y_true=y,
                    probability=calibrated_probability,
                    threshold=threshold,
                )
            )
            table = calibration_table(
                model=model_name,
                horizon=horizon,
                split=split_name,
                phase="isotonic_calibrated",
                y_true=y,
                probability=calibrated_probability,
                bins=args.calibration_bins,
            )
            table_path = args.reports_dir / "calibration" / f"selected_{model_name}_h{horizon}_{split_name}_isotonic.csv"
            _write_csv_atomic(table, table_path)
            calibration_paths.append(table_path)
        print(f"h{horizon}: calibrated `{model_name}` with threshold={threshold:.4f}", flush=True)

    return pd.DataFrame(calibrated_rows), artifacts, calibration_paths


def write_report(
    *,
    selection: pd.DataFrame,
    calibrated_metrics: pd.DataFrame,
    risk_eval: pd.DataFrame,
    args: argparse.Namespace,
    artifacts: list[dict[str, Any]],
) -> None:
    lines = [
        "# Baseline Selection And Calibration Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Baseline metrics: `{args.baseline_metrics}`",
        f"Baseline manifest: `{args.baseline_manifest}`",
        "",
        "## Selection Policy",
        "",
        "- Bloom classification: choose per horizon on `validation` by max PR-AUC, then min Brier, then max macro-F1.",
        "- Risk regression: choose per horizon on `validation` by min MAE, then min RMSE.",
        "- Calibration: fit isotonic calibration on `validation` for the selected bloom baseline only.",
        "- Threshold: choose on `validation` after calibration by max macro-F1.",
        "- `test` is used only for final reporting.",
        "",
        "## Selected Baselines",
        "",
        "| task | horizon | model | validation PR-AUC | validation Brier | validation MAE risk | policy |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(selection):
        lines.append(
            f"| `{row.selection_task}` | {int(row.horizon_months)} | `{row.model}` | "
            f"{_format_float(row.pr_auc)} | {_format_float(row.brier)} | {_format_float(row.mae_risk)} | "
            f"{row.selection_policy} |"
        )

    lines.extend(
        [
            "",
            "## Calibrated Bloom Metrics",
            "",
            "| horizon | split | model | phase | rows | threshold | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(calibrated_metrics.sort_values(["horizon_months", "split", "phase"])):
        lines.append(
            f"| {int(row.horizon_months)} | `{row.split}` | `{row.model}` | `{row.phase}` | "
            f"{_format_int(int(row.rows))} | {_format_float(row.threshold)} | {_format_float(row.pr_auc)} | "
            f"{_format_float(row.roc_auc)} | {_format_float(row.brier)} | {_format_float(row.recall)} | "
            f"{_format_float(row.macro_f1)} |"
        )

    if not risk_eval.empty:
        lines.extend(
            [
                "",
                "## Selected Risk Metrics",
                "",
                "| horizon | split | model | rows | RMSE risk | MAE risk |",
                "|---:|---|---|---:|---:|---:|",
            ]
        )
        for row in dataframe_rows(risk_eval.sort_values(["horizon_months", "split"])):
            lines.append(
                f"| {int(row.horizon_months)} | `{row.split}` | `{row.model}` | "
                f"{_format_int(int(row.rows))} | {_format_float(row.rmse_risk)} | {_format_float(row.mae_risk)} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Selection CSV: `{args.selection}`",
            f"- Calibrated metrics CSV: `{args.calibrated_metrics}`",
            f"- Manifest: `{args.manifest}`",
            f"- Calibrators: `{args.calibrators_dir}`",
            "",
            "## Calibrator Artifacts",
            "",
            "| model | horizon | calibration | path | sha256 |",
            "|---|---:|---|---|---|",
        ]
    )
    for artifact in artifacts:
        lines.append(
            f"| `{artifact['model']}` | {int(artifact['horizon_months'])} | `{artifact['calibration']}` | "
            f"`{artifact['path']}` | `{artifact['sha256']}` |"
        )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-metrics", type=Path, default=DEFAULT_BASELINE_METRICS)
    parser.add_argument("--baseline-manifest", type=Path, default=DEFAULT_BASELINE_MANIFEST)
    parser.add_argument("--splits", type=Path, default=baseline_run.DEFAULT_SPLITS)
    parser.add_argument("--panel", type=Path, default=baseline_run.DEFAULT_PANEL)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--calibrators-dir", type=Path, default=DEFAULT_CALIBRATORS_DIR)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--calibrated-metrics", type=Path, default=DEFAULT_CALIBRATED_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--calibration-bins", type=int, default=10)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.calibrators_dir.mkdir(parents=True, exist_ok=True)

    metrics = pd.read_csv(args.baseline_metrics)
    with args.baseline_manifest.open("r", encoding="utf-8") as handle:
        baseline_manifest = json.load(handle)

    selection = select_baselines(metrics)
    _write_csv_atomic(selection, args.selection)
    print("selected baselines from validation metrics", flush=True)

    calibrated_metrics, artifacts, calibration_paths = run_calibration(selection, args)
    risk_eval = evaluate_risk_selection(selection, metrics)
    if not risk_eval.empty:
        risk_eval_for_write = risk_eval.copy()
        for missing in ["threshold", "bloom_positive", "bloom_rate", "tn", "fp", "fn", "tp"]:
            risk_eval_for_write[missing] = np.nan
        calibrated_metrics = pd.concat([calibrated_metrics, risk_eval_for_write], ignore_index=True, sort=False)
    _write_csv_atomic(calibrated_metrics, args.calibrated_metrics)
    write_report(
        selection=selection,
        calibrated_metrics=calibrated_metrics[calibrated_metrics["selection_task"] == "bloom"].copy(),
        risk_eval=risk_eval,
        args=args,
        artifacts=artifacts,
    )

    output_files = [
        _file_record(args.selection),
        _file_record(args.calibrated_metrics),
        _file_record(args.report),
        *[_file_record(path) for path in calibration_paths],
    ]
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_policy": {
            "bloom": "validation max PR-AUC; tie min Brier; tie max macro-F1",
            "risk": "validation min MAE risk; tie min RMSE risk",
            "calibration": "isotonic fit on validation for selected bloom baselines",
            "threshold": "validation max macro-F1 on calibrated probabilities",
            "test_usage": "report only",
        },
        "baseline_manifest": baseline_manifest,
        "selection": args.selection.as_posix(),
        "calibrated_metrics": args.calibrated_metrics.as_posix(),
        "report": args.report.as_posix(),
        "calibrator_artifacts": artifacts,
        "output_files": output_files,
    }
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.selection}", flush=True)
    print(f"wrote {args.calibrated_metrics}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
