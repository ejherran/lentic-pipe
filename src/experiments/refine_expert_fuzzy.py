#!/usr/bin/env python
"""Refine expert fuzzy scores with validation-only ensemble selection."""

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

from src.pandas_utils import dataframe_rows, group_key_tuple
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.experiments import baselines as baseline_run
from src.experiments import select_baselines


DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_STATE = Path("data/fuzzy/state_vector_v0.parquet")
DEFAULT_BASELINE_SELECTION = Path("reports/baselines/baseline_selection.csv")
DEFAULT_BASELINE_MODELS_DIR = Path("models/baselines")
DEFAULT_BASELINE_CALIBRATORS_DIR = Path("models/baselines/calibrators")
DEFAULT_FUZZY_CALIBRATORS_DIR = Path("models/anfis/calibrators")
DEFAULT_MODELS_DIR = Path("models/anfis/refined")
DEFAULT_OUTPUT_DIR = Path("data/fuzzy")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_PREDICTIONS = DEFAULT_OUTPUT_DIR / "refined_scores_v0.parquet"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "refined_fuzzy_metrics.csv"
DEFAULT_SELECTION = DEFAULT_REPORT_DIR / "refined_fuzzy_selection.csv"
DEFAULT_SOURCE_SELECTION = DEFAULT_REPORT_DIR / "refined_fuzzy_source_selection.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "refined_fuzzy_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "refined_fuzzy_manifest.json"

KEY_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
TARGET_COLUMNS = ["bloom_h", "target_risk_chla_h"]
STATE_JOIN_COLUMNS = ["source_id", "site_id", "year_month"]
STATE_FEATURE_COLUMNS = [
    "irc1",
    "irc1_no_chla",
    "yN",
    "yF",
    "yT",
    "yT_no_chla",
    "sigma_N",
    "sigma_F",
    "sigma_T",
    "sigma_T_no_chla",
    "delta_yN",
    "delta_yF",
    "delta_yT",
    "delta_yT_no_chla",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
    "missing_N",
    "missing_F",
    "missing_T",
    "missing_T_no_chla",
]
CORE_SCORE_COLUMNS = ["baseline_calibrated", "irc1_calibrated", "irc1_no_chla_calibrated"]
META_NUMERIC_FEATURES = [
    "baseline_calibrated",
    "irc1_calibrated",
    "irc1_no_chla_calibrated",
    "irc1",
    "irc1_no_chla",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
    "full_evidence",
    "exogenous_evidence",
    "sigma_N",
    "sigma_F",
    "sigma_T",
    "sigma_T_no_chla",
    "delta_yN",
    "delta_yF",
    "delta_yT",
    "delta_yT_no_chla",
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


def _candidate_thresholds(probability: np.ndarray) -> np.ndarray:
    probability = _clip01(probability)
    quantiles = np.unique(np.quantile(probability, np.linspace(0.01, 0.99, 99)))
    fixed = np.linspace(0.05, 0.95, 19)
    return np.unique(np.concatenate([fixed, quantiles, np.array([0.5])]))


def choose_threshold(y_true: np.ndarray, probability: np.ndarray) -> tuple[float, float]:
    best_threshold = 0.5
    best_score = -1.0
    for threshold in _candidate_thresholds(probability):
        predicted = (_clip01(probability) >= threshold).astype("int8")
        score = f1_score(y_true, predicted, average="macro", zero_division=0)
        if score > best_score:
            best_score = float(score)
            best_threshold = float(threshold)
    return best_threshold, best_score


def evaluate_probability(
    *,
    score_name: str,
    horizon: int,
    split: str,
    source_id: str,
    threshold: float,
    y_true: np.ndarray,
    probability: np.ndarray,
) -> dict[str, Any]:
    probability = _clip01(probability)
    predicted = (probability >= threshold).astype("int8")
    return {
        "score_name": score_name,
        "horizon_months": int(horizon),
        "split": split,
        "source_id": source_id,
        "rows": int(len(y_true)),
        "threshold": float(threshold),
        "bloom_positive": int(np.asarray(y_true, dtype="int8").sum()),
        "bloom_rate": float(np.asarray(y_true, dtype="float64").mean()) if len(y_true) else float("nan"),
        "pr_auc": _safe_metric(average_precision_score, y_true, probability),
        "roc_auc": _safe_metric(roc_auc_score, y_true, probability),
        "brier": _safe_metric(brier_score_loss, y_true, probability),
        "recall": _safe_metric(recall_score, y_true, predicted, zero_division=0),
        "macro_f1": _safe_metric(f1_score, y_true, predicted, average="macro", zero_division=0),
    }


def load_state(path: Path) -> pd.DataFrame:
    columns = STATE_JOIN_COLUMNS + STATE_FEATURE_COLUMNS
    state = pd.read_parquet(path, columns=columns)
    return state.rename(columns={"year_month": "origin_year_month"})


def load_baseline_selection(path: Path) -> pd.DataFrame:
    selection = pd.read_csv(path)
    out = selection[selection["selection_task"] == "bloom"].copy()
    if out.empty:
        raise ValueError(f"No bloom baseline selection rows in {path}")
    return out[["horizon_months", "model"]].drop_duplicates()


def load_calibrator(path: Path) -> tuple[Any, float]:
    payload = joblib.load(path)
    return payload["calibrator"], float(payload["threshold"])


def baseline_calibrator_path(args: argparse.Namespace, model_name: str, horizon: int) -> Path:
    return args.baseline_calibrators_dir / f"{model_name}_h{horizon}_isotonic.joblib"


def fuzzy_calibrator_path(args: argparse.Namespace, score_name: str, horizon: int) -> Path:
    return args.fuzzy_calibrators_dir / f"{score_name}_h{horizon}_isotonic.joblib"


def add_evidence_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in STATE_FEATURE_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    for column in ["irc1", "irc1_no_chla", "yN", "yF", "yT", "yT_no_chla"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.5).clip(0.0, 1.0)
    for column in ["sigma_N", "sigma_F", "sigma_T", "sigma_T_no_chla"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(1.0).clip(0.0, 1.0)
    for column in ["evidence_N", "evidence_F", "evidence_T", "evidence_T_no_chla"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    for column in ["missing_N", "missing_F", "missing_T", "missing_T_no_chla"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(1.0).clip(0.0, 1.0)
    for column in ["delta_yN", "delta_yF", "delta_yT", "delta_yT_no_chla"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0).clip(-1.0, 1.0)
    out["full_evidence"] = out[["evidence_N", "evidence_F", "evidence_T"]].mean(axis=1).clip(0.0, 1.0)
    out["exogenous_evidence"] = out[["evidence_N", "evidence_F", "evidence_T_no_chla"]].mean(axis=1).clip(0.0, 1.0)
    return out


def build_deterministic_candidates(frame: pd.DataFrame, blend_weights: list[float]) -> dict[str, np.ndarray]:
    baseline = _clip01(frame["baseline_calibrated"])
    irc1 = _clip01(frame["irc1_calibrated"])
    no_chla = _clip01(frame["irc1_no_chla_calibrated"])
    full_evidence = _clip01(frame["full_evidence"])
    trophic_evidence = _clip01(frame["evidence_T"])
    exogenous_evidence = _clip01(frame["exogenous_evidence"])
    candidates = {
        "baseline_calibrated": baseline,
        "irc1_calibrated": irc1,
        "irc1_no_chla_calibrated": no_chla,
    }
    for weight in blend_weights:
        suffix = str(weight).replace(".", "p")
        candidates[f"blend_irc1_w{suffix}"] = _clip01((1.0 - weight) * baseline + weight * irc1)
        candidates[f"gate_full_irc1_w{suffix}"] = _clip01(baseline + weight * full_evidence * (irc1 - baseline))
        candidates[f"gate_trophic_irc1_w{suffix}"] = _clip01(baseline + weight * trophic_evidence * (irc1 - baseline))
        candidates[f"gate_exogenous_no_chla_w{suffix}"] = _clip01(
            baseline + weight * exogenous_evidence * (no_chla - baseline)
        )
    return candidates


def make_meta_model(random_seed: int, max_iter: int) -> Pipeline:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler(with_mean=False)),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipe, META_NUMERIC_FEATURES),
            ("source", OneHotEncoder(handle_unknown="ignore"), ["source_id"]),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("prep", preprocessor),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=max_iter,
                    random_state=random_seed,
                ),
            ),
        ]
    )


def fit_meta_candidate(
    validation: pd.DataFrame,
    eval_frame: pd.DataFrame,
    *,
    horizon: int,
    args: argparse.Namespace,
) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    y_validation = validation["bloom_h"].to_numpy(dtype="int8")
    if len(np.unique(y_validation)) < 2:
        return None, None
    model = make_meta_model(args.random_seed, args.meta_max_iter)
    model.fit(validation[["source_id"] + META_NUMERIC_FEATURES], y_validation)
    probability = model.predict_proba(eval_frame[["source_id"] + META_NUMERIC_FEATURES])[:, 1]
    path = args.models_dir / f"meta_logistic_h{horizon}.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": "meta_logistic",
            "horizon_months": int(horizon),
            "fit_split": "validation",
            "features": ["source_id"] + META_NUMERIC_FEATURES,
            "estimator": model,
        },
        path,
    )
    artifact = {"model": "meta_logistic", "horizon_months": int(horizon), **_file_record(path)}
    return _clip01(probability), artifact


def source_specific_selector(
    validation: pd.DataFrame,
    eval_frame: pd.DataFrame,
    candidate_columns: list[str],
    *,
    min_rows: int,
    fallback_candidate: str,
    brier_tolerance: float,
) -> tuple[np.ndarray, pd.DataFrame]:
    selected_rows: list[dict[str, Any]] = []
    selected_by_source: dict[str, str] = {}
    for source_id, group in validation.groupby("source_id", dropna=False):
        y = group["bloom_h"].to_numpy(dtype="int8")
        if len(group) < min_rows or len(np.unique(y)) < 2:
            selected_by_source[str(source_id)] = fallback_candidate
            selected_rows.append(
                {
                    "source_id": source_id,
                    "selected_score": fallback_candidate,
                    "validation_rows": int(len(group)),
                    "selection_reason": "fallback_low_rows_or_single_class",
                    "validation_pr_auc": np.nan,
                    "validation_brier": np.nan,
                }
            )
            continue
        rows = []
        for column in candidate_columns:
            probability = group[column].to_numpy(dtype="float64")
            rows.append(
                {
                    "score_name": column,
                    "validation_pr_auc": _safe_metric(average_precision_score, y, probability),
                    "validation_brier": _safe_metric(brier_score_loss, y, probability),
                }
            )
        ranked = pd.DataFrame(rows)
        baseline_brier = ranked.loc[ranked["score_name"] == "baseline_calibrated", "validation_brier"]
        if not baseline_brier.empty:
            safe = ranked[ranked["validation_brier"] <= float(baseline_brier.iloc[0]) + float(brier_tolerance)].copy()
            if not safe.empty:
                ranked = safe
        ranked = ranked.sort_values(
            ["validation_pr_auc", "validation_brier", "score_name"],
            ascending=[False, True, True],
        )
        best = ranked.iloc[0]
        selected_by_source[str(source_id)] = str(best.score_name)
        selected_rows.append(
            {
                "source_id": source_id,
                "selected_score": str(best.score_name),
                "validation_rows": int(len(group)),
                "selection_reason": f"validation max PR-AUC with Brier <= baseline + {brier_tolerance:g}; tie min Brier",
                "validation_pr_auc": float(best.validation_pr_auc),
                "validation_brier": float(best.validation_brier),
            }
        )
    eval_reset = eval_frame.reset_index(drop=True)
    out = np.empty(len(eval_reset), dtype="float64")
    for source_id, index in eval_reset.groupby("source_id", dropna=False).groups.items():
        column = selected_by_source.get(str(source_id), fallback_candidate)
        positions = np.asarray(index, dtype="int64")
        out[positions] = eval_reset.loc[positions, column].to_numpy(dtype="float64")
    return _clip01(out), pd.DataFrame(selected_rows)


def add_candidate_columns(
    frame: pd.DataFrame,
    *,
    validation: pd.DataFrame,
    horizon: int,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame]:
    out = frame.copy()
    deterministic = build_deterministic_candidates(out, args.blend_weights)
    for name, values in deterministic.items():
        out[name] = values
    artifacts: list[dict[str, Any]] = []
    meta_probability, artifact = fit_meta_candidate(validation, out, horizon=horizon, args=args)
    if meta_probability is not None:
        out["meta_logistic"] = meta_probability
    if artifact is not None:
        artifacts.append(artifact)
    candidate_columns = [
        column
        for column in out.columns
        if column in deterministic or column == "meta_logistic"
    ]
    validation_with_candidates = out[out["split"] == "validation"].copy()
    global_best = select_global_candidate(
        validation_with_candidates,
        candidate_columns,
        brier_tolerance=args.selection_brier_tolerance,
    )["score_name"]
    source_score, source_selection = source_specific_selector(
        validation_with_candidates,
        out,
        candidate_columns,
        min_rows=args.source_min_validation_rows,
        fallback_candidate=str(global_best),
        brier_tolerance=args.selection_brier_tolerance,
    )
    source_selection["horizon_months"] = int(horizon)
    out["source_selector"] = source_score
    return out, artifacts, source_selection


def select_global_candidate(validation: pd.DataFrame, candidate_columns: list[str], brier_tolerance: float = 0.002) -> pd.Series:
    y = validation["bloom_h"].to_numpy(dtype="int8")
    rows = []
    for column in candidate_columns:
        probability = validation[column].to_numpy(dtype="float64")
        threshold, threshold_macro_f1 = choose_threshold(y, probability)
        rows.append(
            {
                "score_name": column,
                "threshold": threshold,
                "validation_threshold_macro_f1": threshold_macro_f1,
                "validation_pr_auc": _safe_metric(average_precision_score, y, probability),
                "validation_brier": _safe_metric(brier_score_loss, y, probability),
                "validation_macro_f1": threshold_macro_f1,
            }
        )
    ranked = pd.DataFrame(rows)
    baseline_brier = ranked.loc[ranked["score_name"] == "baseline_calibrated", "validation_brier"]
    if not baseline_brier.empty:
        safe = ranked[ranked["validation_brier"] <= float(baseline_brier.iloc[0]) + float(brier_tolerance)].copy()
        if not safe.empty:
            ranked = safe
    ranked = ranked.sort_values(
        ["validation_pr_auc", "validation_brier", "validation_macro_f1", "score_name"],
        ascending=[False, True, False, True],
    )
    return ranked.iloc[0]


def evaluate_candidate_columns(frame: pd.DataFrame, candidate_columns: list[str]) -> pd.DataFrame:
    thresholds = {}
    rows: list[dict[str, Any]] = []
    validation = frame[frame["split"] == "validation"].copy()
    for horizon, horizon_validation in validation.groupby("horizon_months", sort=True):
        y = horizon_validation["bloom_h"].to_numpy(dtype="int8")
        for column in candidate_columns:
            threshold, _ = choose_threshold(y, horizon_validation[column].to_numpy(dtype="float64"))
            thresholds[(int(horizon), column)] = threshold
    for key, group in frame.groupby(["horizon_months", "split"], sort=True):
        horizon, split = group_key_tuple(key)
        y = group["bloom_h"].to_numpy(dtype="int8")
        for column in candidate_columns:
            threshold = thresholds[(int(horizon), column)]
            rows.append(
                evaluate_probability(
                    score_name=column,
                    horizon=int(horizon),
                    split=str(split),
                    source_id="all",
                    threshold=threshold,
                    y_true=y,
                    probability=group[column].to_numpy(dtype="float64"),
                )
            )
            for source_id, source_group in group.groupby("source_id", dropna=False):
                rows.append(
                    evaluate_probability(
                        score_name=column,
                        horizon=int(horizon),
                        split=str(split),
                        source_id=str(source_id),
                        threshold=threshold,
                        y_true=source_group["bloom_h"].to_numpy(dtype="int8"),
                        probability=source_group[column].to_numpy(dtype="float64"),
                    )
                )
    return pd.DataFrame(rows)


def build_selection(metrics: pd.DataFrame, brier_tolerance: float = 0.002) -> pd.DataFrame:
    validation = metrics[(metrics["split"] == "validation") & (metrics["source_id"] == "all")].copy()
    baseline_validation = validation[validation["score_name"] == "baseline_calibrated"][
        ["horizon_months", "brier"]
    ].rename(columns={"brier": "baseline_validation_brier"})
    validation = validation.merge(baseline_validation, on="horizon_months", how="left")
    validation["brier_allowed"] = validation["baseline_validation_brier"] + float(brier_tolerance)
    validation["calibration_safe"] = validation["brier"] <= validation["brier_allowed"]
    selected_parts = []
    for _, horizon_frame in validation.groupby("horizon_months", sort=True):
        eligible = horizon_frame[horizon_frame["calibration_safe"]].copy()
        if eligible.empty:
            eligible = horizon_frame.copy()
        ranked = eligible.sort_values(
            ["pr_auc", "brier", "macro_f1", "score_name"],
            ascending=[False, True, False, True],
        )
        selected_parts.append(ranked.head(1))
    selected = pd.concat(selected_parts, ignore_index=True)
    test = metrics[(metrics["split"] == "test") & (metrics["source_id"] == "all")].copy()
    baseline_test = test[test["score_name"] == "baseline_calibrated"][
        ["horizon_months", "pr_auc", "brier", "macro_f1", "recall"]
    ].rename(
        columns={
            "pr_auc": "baseline_test_pr_auc",
            "brier": "baseline_test_brier",
            "macro_f1": "baseline_test_macro_f1",
            "recall": "baseline_test_recall",
        }
    )
    selected_test = selected[["horizon_months", "score_name"]].merge(test, on=["horizon_months", "score_name"], how="left")
    selected_test = selected_test.merge(baseline_test, on="horizon_months", how="left")
    selected_test["delta_test_pr_auc_vs_baseline"] = selected_test["pr_auc"] - selected_test["baseline_test_pr_auc"]
    selected_test["delta_test_brier_vs_baseline"] = selected_test["brier"] - selected_test["baseline_test_brier"]
    selected_test["delta_test_macro_f1_vs_baseline"] = selected_test["macro_f1"] - selected_test["baseline_test_macro_f1"]
    selected = selected.rename(
        columns={
            "pr_auc": "validation_pr_auc",
            "brier": "validation_brier",
            "macro_f1": "validation_macro_f1",
            "recall": "validation_recall",
            "threshold": "selected_threshold",
        }
    )
    test_columns = [
        "horizon_months",
        "score_name",
        "rows",
        "pr_auc",
        "roc_auc",
        "brier",
        "recall",
        "macro_f1",
        "baseline_test_pr_auc",
        "baseline_test_brier",
        "baseline_test_macro_f1",
        "delta_test_pr_auc_vs_baseline",
        "delta_test_brier_vs_baseline",
        "delta_test_macro_f1_vs_baseline",
    ]
    selected = selected.merge(
        selected_test[test_columns].rename(
            columns={
                "rows": "test_rows",
                "pr_auc": "test_pr_auc",
                "roc_auc": "test_roc_auc",
                "brier": "test_brier",
                "recall": "test_recall",
                "macro_f1": "test_macro_f1",
            }
        ),
        on=["horizon_months", "score_name"],
        how="left",
    )
    selected["selection_policy"] = (
        f"validation max PR-AUC among candidates with validation Brier <= baseline + {brier_tolerance:g}; "
        "tie min Brier; tie max macro-F1; test report only"
    )
    return selected[
        [
            "horizon_months",
            "score_name",
            "selection_policy",
            "selected_threshold",
            "baseline_validation_brier",
            "brier_allowed",
            "validation_pr_auc",
            "validation_brier",
            "validation_recall",
            "validation_macro_f1",
            "test_rows",
            "test_pr_auc",
            "test_roc_auc",
            "test_brier",
            "test_recall",
            "test_macro_f1",
            "baseline_test_pr_auc",
            "baseline_test_brier",
            "baseline_test_macro_f1",
            "delta_test_pr_auc_vs_baseline",
            "delta_test_brier_vs_baseline",
            "delta_test_macro_f1_vs_baseline",
        ]
    ].sort_values("horizon_months")


def mark_selected_scores(predictions: pd.DataFrame, selection: pd.DataFrame) -> pd.DataFrame:
    out = predictions.copy()
    out["selected_score_name"] = ""
    out["selected_probability"] = np.nan
    out["selected_threshold"] = np.nan
    for row in dataframe_rows(selection):
        mask = out["horizon_months"] == int(row.horizon_months)
        out.loc[mask, "selected_score_name"] = str(row.score_name)
        out.loc[mask, "selected_probability"] = out.loc[mask, str(row.score_name)].to_numpy(dtype="float64")
        out.loc[mask, "selected_threshold"] = float(row.selected_threshold)
    return out


def build_horizon_frame(
    *,
    horizon: int,
    selected_model: str,
    splits: pd.DataFrame,
    panel: pd.DataFrame,
    state: pd.DataFrame,
    args: argparse.Namespace,
    load_args: argparse.Namespace,
    predict_args: argparse.Namespace,
) -> pd.DataFrame:
    frame = baseline_run.make_horizon_frame(splits, panel, horizon, load_args)
    train = frame[frame["split"] == "train"].copy()
    eval_frame = frame[frame["split"].isin(["validation", "test"])].copy()
    raw_baseline = select_baselines.predict_bloom_probability(eval_frame, selected_model, horizon, predict_args, train)
    baseline_calibrator, _ = load_calibrator(baseline_calibrator_path(args, selected_model, horizon))
    eval_frame["baseline_raw"] = _clip01(raw_baseline)
    eval_frame["baseline_calibrated"] = _clip01(baseline_calibrator.predict(raw_baseline))
    eval_frame = eval_frame.merge(
        state,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
    )
    eval_frame = add_evidence_features(eval_frame)
    for score_name in ["irc1", "irc1_no_chla"]:
        calibrator, _ = load_calibrator(fuzzy_calibrator_path(args, score_name, horizon))
        eval_frame[f"{score_name}_calibrated"] = _clip01(
            calibrator.predict(eval_frame[score_name].clip(0.0, 1.0).to_numpy(dtype="float64"))
        )
    keep_columns = (
        KEY_COLUMNS
        + TARGET_COLUMNS
        + ["baseline_raw", "baseline_calibrated", "irc1_calibrated", "irc1_no_chla_calibrated"]
        + STATE_FEATURE_COLUMNS
        + ["full_evidence", "exogenous_evidence"]
    )
    return eval_frame[keep_columns].reset_index(drop=True).copy()


def write_report(
    *,
    selection: pd.DataFrame,
    metrics: pd.DataFrame,
    source_selection: pd.DataFrame,
    args: argparse.Namespace,
    artifacts: list[dict[str, Any]],
) -> None:
    baseline = metrics[
        (metrics["source_id"] == "all") & (metrics["split"] == "test") & (metrics["score_name"] == "baseline_calibrated")
    ].copy()
    lines = [
        "# Refined Expert Fuzzy Ensemble Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This step does not rebuild the fuzzy state vector. It tests whether fuzzy scores improve the selected calibrated baseline.",
        "All candidate selection is done on `validation`; `test` is report-only.",
        f"Selection policy: {selection['selection_policy'].iloc[0] if not selection.empty else 'NA'}.",
        "",
        "## Selected Refined Scores",
        "",
        "| horizon | selected score | threshold | validation PR-AUC | test PR-AUC | baseline test PR-AUC | d PR-AUC | test Brier | baseline test Brier | d Brier | test macro-F1 | d macro-F1 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(selection):
        lines.append(
            f"| {int(row.horizon_months)} | `{row.score_name}` | {_format_float(row.selected_threshold)} | "
            f"{_format_float(row.validation_pr_auc)} | {_format_float(row.test_pr_auc)} | "
            f"{_format_float(row.baseline_test_pr_auc)} | {_format_float(row.delta_test_pr_auc_vs_baseline)} | "
            f"{_format_float(row.test_brier)} | {_format_float(row.baseline_test_brier)} | "
            f"{_format_float(row.delta_test_brier_vs_baseline)} | {_format_float(row.test_macro_f1)} | "
            f"{_format_float(row.delta_test_macro_f1_vs_baseline)} |"
        )
    lines.extend(
        [
            "",
            "## Baseline Test Reference",
            "",
            "| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(baseline.sort_values("horizon_months")):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | "
            f"{_format_float(row.roc_auc)} | {_format_float(row.brier)} | {_format_float(row.recall)} | "
            f"{_format_float(row.macro_f1)} |"
        )
    source_counts = source_selection.groupby(["horizon_months", "selected_score"], dropna=False).size().reset_index()
    source_counts.columns = ["horizon_months", "selected_score", "sources"]
    lines.extend(
        [
            "",
            "## Source Selector Summary",
            "",
            "| horizon | selected score | sources |",
            "|---:|---|---:|",
        ]
    )
    for row in dataframe_rows(source_counts.sort_values(["horizon_months", "selected_score"])):
        lines.append(f"| {int(row.horizon_months)} | `{row.selected_score}` | {int(row.sources)} |")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Predictions: `{args.predictions}`",
            f"- Metrics: `{args.metrics}`",
            f"- Selection: `{args.selection}`",
            f"- Source selection: `{args.source_selection}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    if artifacts:
        lines.extend(["", "## Model Artifacts", "", "| model | horizon | path | sha256 |", "|---|---:|---|---|"])
        for artifact in artifacts:
            lines.append(
                f"| `{artifact['model']}` | {int(artifact['horizon_months'])} | "
                f"`{artifact['path']}` | `{artifact['sha256']}` |"
            )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    selection: pd.DataFrame,
    source_selection: pd.DataFrame,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    input_paths = [
        args.splits,
        args.panel,
        args.state,
        args.baseline_selection,
    ]
    output_paths = [args.predictions, args.metrics, args.selection, args.source_selection, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_family": "refined_expert_fuzzy_ensemble_v0",
        "selection_policy": (
            f"validation max PR-AUC among candidates with validation Brier <= baseline + "
            f"{args.selection_brier_tolerance:g}; tie min Brier; tie max macro-F1; test report only"
        ),
        "selection_brier_tolerance": float(args.selection_brier_tolerance),
        "row_counts": {
            "prediction_rows": int(len(predictions)),
            "metrics_rows": int(len(metrics)),
            "selection_rows": int(len(selection)),
            "source_selection_rows": int(len(source_selection)),
        },
        "inputs": [_file_record(path) for path in input_paths if path.exists()],
        "outputs": [_file_record(path) for path in output_paths if path.exists()],
        "model_artifacts": artifacts,
    }


def _parse_blend_weights(value: str) -> list[float]:
    weights = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not weights or any(weight < 0.0 or weight > 1.0 for weight in weights):
        raise ValueError("--blend-weights must contain values between 0 and 1")
    return sorted(set(weights))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--baseline-selection", type=Path, default=DEFAULT_BASELINE_SELECTION)
    parser.add_argument("--baseline-models-dir", type=Path, default=DEFAULT_BASELINE_MODELS_DIR)
    parser.add_argument("--baseline-calibrators-dir", type=Path, default=DEFAULT_BASELINE_CALIBRATORS_DIR)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--source-selection", type=Path, default=DEFAULT_SOURCE_SELECTION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--blend-weights", default="0.25,0.5,0.75")
    parser.add_argument("--selection-brier-tolerance", type=float, default=0.002)
    parser.add_argument("--source-min-validation-rows", type=int, default=1000)
    parser.add_argument("--meta-max-iter", type=int, default=500)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--sample-rows-per-split", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.blend_weights = _parse_blend_weights(args.blend_weights)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    print(f"loading selected baselines {args.baseline_selection}", flush=True)
    baseline_selection = load_baseline_selection(args.baseline_selection)
    print(f"loading state {args.state}", flush=True)
    state = load_state(args.state)
    load_args = argparse.Namespace(
        splits=args.splits,
        panel=args.panel,
        horizons=args.horizons,
        sample_rows_per_split=args.sample_rows_per_split,
        random_seed=args.random_seed,
    )
    print(f"loading panel and splits from {args.panel} / {args.splits}", flush=True)
    splits, panel, available_features = baseline_run.load_inputs(load_args)
    predict_args = argparse.Namespace(
        models_dir=args.baseline_models_dir,
        numeric_features=baseline_run.feature_columns_for_model(available_features),
    )

    prediction_parts: list[pd.DataFrame] = []
    artifact_rows: list[dict[str, Any]] = []
    source_selection_parts: list[pd.DataFrame] = []
    for row in dataframe_rows(baseline_selection):
        horizon = int(row.horizon_months)
        if horizon not in args.horizons:
            continue
        selected_model = str(row.model)
        print(f"h{horizon}: building refinement frame using baseline `{selected_model}`", flush=True)
        horizon_frame = build_horizon_frame(
            horizon=horizon,
            selected_model=selected_model,
            splits=splits,
            panel=panel,
            state=state,
            args=args,
            load_args=load_args,
            predict_args=predict_args,
        )
        validation = horizon_frame[horizon_frame["split"] == "validation"].copy()
        print(f"h{horizon}: fitting validation-only refined candidates", flush=True)
        horizon_frame, artifacts, source_selection = add_candidate_columns(
            horizon_frame,
            validation=validation,
            horizon=horizon,
            args=args,
        )
        artifact_rows.extend(artifacts)
        source_selection_parts.append(source_selection)
        prediction_parts.append(horizon_frame)

    predictions = pd.concat(prediction_parts, ignore_index=True)
    candidate_columns = [
        column
        for column in predictions.columns
        if column
        in {
            "baseline_calibrated",
            "irc1_calibrated",
            "irc1_no_chla_calibrated",
            "meta_logistic",
            "source_selector",
        }
        or column.startswith("blend_")
        or column.startswith("gate_")
    ]
    metrics = evaluate_candidate_columns(predictions, candidate_columns)
    selection = build_selection(metrics, brier_tolerance=args.selection_brier_tolerance)
    predictions = mark_selected_scores(predictions, selection)
    source_selection = pd.concat(source_selection_parts, ignore_index=True) if source_selection_parts else pd.DataFrame()

    _write_parquet_atomic(predictions, args.predictions)
    _write_csv_atomic(metrics, args.metrics)
    _write_csv_atomic(selection, args.selection)
    _write_csv_atomic(source_selection, args.source_selection)
    write_report(
        selection=selection,
        metrics=metrics,
        source_selection=source_selection,
        args=args,
        artifacts=artifact_rows,
    )
    manifest = build_manifest(
        args=args,
        predictions=predictions,
        metrics=metrics,
        selection=selection,
        source_selection=source_selection,
        artifacts=artifact_rows,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.predictions}", flush=True)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.selection}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
