#!/usr/bin/env python
"""Train and evaluate baseline models on leakage-safe monthly splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, group_key_tuple, year_month_month, year_month_year
import pyarrow.parquet as pq
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_REPORTS_DIR = Path("reports/baselines")
DEFAULT_MODELS_DIR = Path("models/baselines")
DEFAULT_METRICS = DEFAULT_REPORTS_DIR / "baseline_metrics.csv"
DEFAULT_REPORT = DEFAULT_REPORTS_DIR / "baseline_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORTS_DIR / "baseline_manifest.json"

ID_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
TARGET_COLUMNS = ["bloom_h", "target_risk_chla_h"]
FEATURE_KEY_COLUMNS = ["source_id", "site_id", "year_month"]

BASE_FEATURE_COLUMNS = [
    "mean_DO_mgL",
    "mean_TN_ugL",
    "mean_TP_ugL",
    "mean_chlorophyll_a_ugL",
    "mean_pH",
    "mean_secchi_depth_m",
    "mean_temperature_C",
    "mean_turbidity_NTU",
    "std_DO_mgL",
    "std_TN_ugL",
    "std_TP_ugL",
    "std_chlorophyll_a_ugL",
    "std_pH",
    "std_secchi_depth_m",
    "std_temperature_C",
    "std_turbidity_NTU",
    "n_obs_DO_mgL",
    "n_obs_TN_ugL",
    "n_obs_TP_ugL",
    "n_obs_chlorophyll_a_ugL",
    "n_obs_pH",
    "n_obs_secchi_depth_m",
    "n_obs_temperature_C",
    "n_obs_turbidity_NTU",
    "n_bad_DO_mgL",
    "n_bad_TN_ugL",
    "n_bad_TP_ugL",
    "n_bad_chlorophyll_a_ugL",
    "n_bad_pH",
    "n_bad_secchi_depth_m",
    "n_bad_temperature_C",
    "n_bad_turbidity_NTU",
    "qc_ok_rate_DO_mgL",
    "qc_ok_rate_TN_ugL",
    "qc_ok_rate_TP_ugL",
    "qc_ok_rate_chlorophyll_a_ugL",
    "qc_ok_rate_pH",
    "qc_ok_rate_secchi_depth_m",
    "qc_ok_rate_temperature_C",
    "qc_ok_rate_turbidity_NTU",
    "month",
    "season_sin_1",
    "season_cos_1",
    "season_sin_2",
    "season_cos_2",
    "TN_TP_ratio",
    "log_TP",
    "log_TN",
    "log_chlorophyll_a",
    "risk_chla",
]

MODEL_CHOICES = [
    "constant",
    "source_month",
    "site_month",
    "persistence",
    "logistic_sgd",
    "ridge_sgd",
    "hist_gradient_boosting",
]
DEFAULT_MODELS = ["constant", "source_month", "site_month", "persistence", "logistic_sgd", "ridge_sgd"]


@dataclass(frozen=True)
class PredictionBundle:
    model_name: str
    task: str
    horizon: int
    split: str
    y_bloom: np.ndarray
    y_risk: np.ndarray
    pred_probability: np.ndarray | None = None
    pred_risk: np.ndarray | None = None


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
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _artifact_record(model: str, horizon: int, path: Path) -> dict[str, Any]:
    return {
        "model": model,
        "horizon_months": horizon,
        **_file_record(path),
    }


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
        value = metric_fn(*args, **kwargs)
    except ValueError:
        return float("nan")
    return float(value)


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(math.sqrt(mean_squared_error(y_true, y_pred)))


def _available_feature_columns(panel_path: Path) -> list[str]:
    columns = pq.ParquetFile(panel_path).schema.names
    return [column for column in BASE_FEATURE_COLUMNS if column in columns]


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    split_columns = ID_COLUMNS + TARGET_COLUMNS
    splits = pd.read_parquet(args.splits, columns=split_columns)
    splits = splits[splits["horizon_months"].isin(args.horizons)].copy()
    splits["bloom_h"] = splits["bloom_h"].astype(bool).astype("int8")
    splits["target_risk_chla_h"] = pd.to_numeric(splits["target_risk_chla_h"], errors="coerce").clip(0, 1)
    splits["origin_month"] = year_month_month(splits["origin_year_month"]).astype("int16")
    splits["origin_year"] = year_month_year(splits["origin_year_month"]).astype("int16")

    feature_columns = _available_feature_columns(args.panel)
    panel = pd.read_parquet(args.panel, columns=FEATURE_KEY_COLUMNS + feature_columns)
    panel[feature_columns] = panel[feature_columns].replace([np.inf, -np.inf], np.nan)
    panel = panel.rename(columns={"year_month": "origin_year_month"})
    return splits, panel, feature_columns


def make_horizon_frame(splits: pd.DataFrame, panel: pd.DataFrame, horizon: int, args: argparse.Namespace) -> pd.DataFrame:
    frame = splits[splits["horizon_months"] == horizon].merge(
        panel,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
    )
    numeric_columns = frame.select_dtypes(include=[np.number]).columns
    frame[numeric_columns] = frame[numeric_columns].replace([np.inf, -np.inf], np.nan)
    if args.sample_rows_per_split:
        sampled = []
        for split, group in frame.groupby("split", sort=False):
            n = min(args.sample_rows_per_split, len(group))
            sampled.append(group.sample(n=n, random_state=args.random_seed))
            print(f"h{horizon}: sampled {n:,}/{len(group):,} rows for {split}", flush=True)
        frame = pd.concat(sampled, ignore_index=True)
    return frame


def sklearn_training_subset(train: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if args.max_train_rows_per_horizon and len(train) > args.max_train_rows_per_horizon:
        train = train.sample(n=args.max_train_rows_per_horizon, random_state=args.random_seed).copy()
    return train


def build_preprocessor(numeric_features: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler(with_mean=False)),
        ]
    )
    categorical_pipe = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipe, numeric_features),
            ("source", categorical_pipe, ["source_id"]),
        ],
        remainder="drop",
        sparse_threshold=0.3,
    )


def feature_columns_for_model(feature_columns: list[str]) -> list[str]:
    extra = ["origin_month", "origin_year"]
    return [column for column in feature_columns + extra if column not in {"source_id", "site_id"}]


def fit_logistic_sgd(train: pd.DataFrame, numeric_features: list[str], args: argparse.Namespace) -> Pipeline:
    model = Pipeline(
        steps=[
            ("prep", build_preprocessor(numeric_features)),
            (
                "model",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=args.sgd_alpha,
                    max_iter=args.sgd_max_iter,
                    tol=args.sgd_tol,
                    class_weight="balanced",
                    random_state=args.random_seed,
                    n_jobs=args.n_jobs,
                ),
            ),
        ]
    )
    x_train = train[["source_id"] + numeric_features]
    y_train = train["bloom_h"].to_numpy(dtype="int8")
    return model.fit(x_train, y_train)


def fit_ridge_sgd(train: pd.DataFrame, numeric_features: list[str], args: argparse.Namespace) -> Pipeline:
    model = Pipeline(
        steps=[
            ("prep", build_preprocessor(numeric_features)),
            (
                "model",
                SGDRegressor(
                    loss="squared_error",
                    penalty="l2",
                    alpha=args.sgd_alpha,
                    max_iter=args.sgd_max_iter,
                    tol=args.sgd_tol,
                    random_state=args.random_seed,
                ),
            ),
        ]
    )
    x_train = train[["source_id"] + numeric_features]
    y_train = train["target_risk_chla_h"].to_numpy(dtype="float64")
    return model.fit(x_train, y_train)


def fit_hist_gradient_models(
    train: pd.DataFrame,
    numeric_features: list[str],
    args: argparse.Namespace,
) -> tuple[Pipeline, Pipeline]:
    train_for_tree = train
    if len(train_for_tree) > args.tree_max_train_rows:
        train_for_tree = train_for_tree.sample(n=args.tree_max_train_rows, random_state=args.random_seed).copy()

    def make_dense_preprocessor() -> ColumnTransformer:
        return ColumnTransformer(
            transformers=[
                ("numeric", SimpleImputer(strategy="median", add_indicator=True), numeric_features),
                ("source", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["source_id"]),
            ],
            remainder="drop",
            sparse_threshold=0.0,
        )

    classifier = Pipeline(
        steps=[
            ("prep", make_dense_preprocessor()),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=args.tree_max_iter,
                    learning_rate=args.tree_learning_rate,
                    max_leaf_nodes=args.tree_max_leaf_nodes,
                    random_state=args.random_seed,
                ),
            ),
        ]
    )
    regressor = Pipeline(
        steps=[
            ("prep", make_dense_preprocessor()),
            (
                "model",
                HistGradientBoostingRegressor(
                    max_iter=args.tree_max_iter,
                    learning_rate=args.tree_learning_rate,
                    max_leaf_nodes=args.tree_max_leaf_nodes,
                    random_state=args.random_seed,
                ),
            ),
        ]
    )
    x_train = train_for_tree[["source_id"] + numeric_features]
    classifier.fit(x_train, train_for_tree["bloom_h"].to_numpy(dtype="int8"))
    regressor.fit(x_train, train_for_tree["target_risk_chla_h"].to_numpy(dtype="float64"))
    return classifier, regressor


def _smooth_rate(successes: pd.Series, rows: pd.Series, prior: float, strength: float) -> pd.Series:
    return (successes + prior * strength) / (rows + strength)


def fit_climatology(train: pd.DataFrame, keys: list[str], prior_probability: float, prior_risk: float, strength: float) -> pd.DataFrame:
    grouped = train.groupby(keys, dropna=False).agg(
        rows=("bloom_h", "size"),
        bloom_positive=("bloom_h", "sum"),
        risk_sum=("target_risk_chla_h", "sum"),
    ).reset_index()
    grouped["pred_probability"] = _smooth_rate(grouped["bloom_positive"], grouped["rows"], prior_probability, strength)
    grouped["pred_risk"] = _smooth_rate(grouped["risk_sum"], grouped["rows"], prior_risk, strength).clip(0, 1)
    return grouped[keys + ["rows", "pred_probability", "pred_risk"]]


def predict_from_climatology(
    frame: pd.DataFrame,
    table: pd.DataFrame,
    keys: list[str],
    fallback_probability: float,
    fallback_risk: float,
) -> tuple[np.ndarray, np.ndarray]:
    joined = frame[keys].merge(table, on=keys, how="left")
    probability = joined["pred_probability"].fillna(fallback_probability).to_numpy(dtype="float64")
    risk = joined["pred_risk"].fillna(fallback_risk).to_numpy(dtype="float64")
    return _clip01(probability), _clip01(risk)


def persistence_predictions(frame: pd.DataFrame, fallback_probability: float, fallback_risk: float) -> tuple[np.ndarray, np.ndarray]:
    risk = pd.to_numeric(frame.get("risk_chla"), errors="coerce")
    probability = risk.fillna(fallback_probability).to_numpy(dtype="float64")
    risk_pred = risk.fillna(fallback_risk).to_numpy(dtype="float64")
    return _clip01(probability), _clip01(risk_pred)


def _prediction_frame_for_split(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    return frame[frame["split"] == split].copy()


def _positive_class_probability(model: Pipeline, frame: pd.DataFrame, numeric_features: list[str]) -> np.ndarray:
    x_eval = frame[["source_id"] + numeric_features]
    probabilities = model.predict_proba(x_eval)
    return _clip01(probabilities[:, 1])


def _risk_prediction(model: Pipeline, frame: pd.DataFrame, numeric_features: list[str]) -> np.ndarray:
    x_eval = frame[["source_id"] + numeric_features]
    return _clip01(model.predict(x_eval))


def evaluate_predictions(bundle: PredictionBundle, threshold: float) -> dict[str, Any]:
    y_bloom = bundle.y_bloom.astype("int8")
    y_risk = bundle.y_risk.astype("float64")
    pred_probability = bundle.pred_probability
    pred_risk = bundle.pred_risk

    output: dict[str, Any] = {
        "model": bundle.model_name,
        "task": bundle.task,
        "horizon_months": bundle.horizon,
        "split": bundle.split,
        "rows": int(len(y_bloom)),
        "threshold": threshold,
        "bloom_positive": int(y_bloom.sum()),
        "bloom_rate": float(y_bloom.mean()) if len(y_bloom) else float("nan"),
        "pr_auc": float("nan"),
        "roc_auc": float("nan"),
        "brier": float("nan"),
        "recall": float("nan"),
        "macro_f1": float("nan"),
        "rmse_risk": float("nan"),
        "mae_risk": float("nan"),
        "false_alarms_per_site_year": float("nan"),
    }

    if pred_probability is not None:
        pred_probability = _clip01(pred_probability)
        output["pr_auc"] = _safe_metric(average_precision_score, y_bloom, pred_probability)
        output["roc_auc"] = _safe_metric(roc_auc_score, y_bloom, pred_probability)
        output["brier"] = _safe_metric(brier_score_loss, y_bloom, pred_probability)
        y_pred = (pred_probability >= threshold).astype("int8")
        output["recall"] = _safe_metric(recall_score, y_bloom, y_pred, zero_division=0)
        output["macro_f1"] = _safe_metric(f1_score, y_bloom, y_pred, average="macro", zero_division=0)

    if pred_risk is not None:
        pred_risk = _clip01(pred_risk)
        output["rmse_risk"] = _safe_metric(_root_mean_squared_error, y_risk, pred_risk)
        output["mae_risk"] = _safe_metric(mean_absolute_error, y_risk, pred_risk)

    return output


def confusion_output(bundle: PredictionBundle, threshold: float) -> pd.DataFrame | None:
    if bundle.pred_probability is None:
        return None
    y_pred = (_clip01(bundle.pred_probability) >= threshold).astype("int8")
    matrix = confusion_matrix(bundle.y_bloom.astype("int8"), y_pred, labels=[0, 1])
    return pd.DataFrame(
        [
            {
                "model": bundle.model_name,
                "task": bundle.task,
                "horizon_months": bundle.horizon,
                "split": bundle.split,
                "threshold": threshold,
                "tn": int(matrix[0, 0]),
                "fp": int(matrix[0, 1]),
                "fn": int(matrix[1, 0]),
                "tp": int(matrix[1, 1]),
            }
        ]
    )


def calibration_output(bundle: PredictionBundle, bins: int) -> pd.DataFrame | None:
    if bundle.pred_probability is None:
        return None
    probability = _clip01(bundle.pred_probability)
    y = bundle.y_bloom.astype("int8")
    bin_ids = np.minimum(np.floor(probability * bins).astype("int64"), bins - 1)
    rows = []
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        if not mask.any():
            rows.append(
                {
                    "model": bundle.model_name,
                    "task": bundle.task,
                    "horizon_months": bundle.horizon,
                    "split": bundle.split,
                    "bin": bin_id,
                    "bin_left": bin_id / bins,
                    "bin_right": (bin_id + 1) / bins,
                    "rows": 0,
                    "mean_pred_probability": np.nan,
                    "observed_bloom_rate": np.nan,
                }
            )
            continue
        rows.append(
            {
                "model": bundle.model_name,
                "task": bundle.task,
                "horizon_months": bundle.horizon,
                "split": bundle.split,
                "bin": bin_id,
                "bin_left": bin_id / bins,
                "bin_right": (bin_id + 1) / bins,
                "rows": int(mask.sum()),
                "mean_pred_probability": float(probability[mask].mean()),
                "observed_bloom_rate": float(y[mask].mean()),
            }
        )
    return pd.DataFrame(rows)


def false_alarm_rate(frame: pd.DataFrame, probability: np.ndarray, threshold: float) -> float:
    predicted = _clip01(probability) >= threshold
    false_positive = predicted & (frame["bloom_h"].to_numpy(dtype="int8") == 0)
    site_years = frame[["source_id", "site_id", "origin_year"]].drop_duplicates()
    if site_years.empty:
        return float("nan")
    return float(false_positive.sum() / len(site_years))


def add_false_alarm_metric(metrics: dict[str, Any], frame: pd.DataFrame, probability: np.ndarray | None, threshold: float) -> None:
    if probability is None:
        return
    metrics["false_alarms_per_site_year"] = false_alarm_rate(frame, probability, threshold)


def save_model_artifact(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(payload, tmp_path)
    tmp_path.replace(path)


def write_bundle_outputs(
    bundle: PredictionBundle,
    frame: pd.DataFrame,
    args: argparse.Namespace,
    metrics_rows: list[dict[str, Any]],
    confusion_rows: list[pd.DataFrame],
    calibration_rows: list[pd.DataFrame],
) -> None:
    metrics = evaluate_predictions(bundle, args.threshold)
    add_false_alarm_metric(metrics, frame, bundle.pred_probability, args.threshold)
    metrics_rows.append(metrics)
    confusion = confusion_output(bundle, args.threshold)
    if confusion is not None:
        confusion_rows.append(confusion)
    calibration = calibration_output(bundle, args.calibration_bins)
    if calibration is not None:
        calibration_rows.append(calibration)


def evaluate_horizon_models(
    frame: pd.DataFrame,
    train: pd.DataFrame,
    sklearn_train: pd.DataFrame,
    numeric_features: list[str],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame], list[pd.DataFrame], list[dict[str, Any]]]:
    horizon = int(frame["horizon_months"].iloc[0])
    metrics_rows: list[dict[str, Any]] = []
    confusion_rows: list[pd.DataFrame] = []
    calibration_rows: list[pd.DataFrame] = []
    artifacts: list[dict[str, Any]] = []

    prior_probability = float(train["bloom_h"].mean())
    prior_risk = float(train["target_risk_chla_h"].mean())
    source_month_table = None
    site_month_table = None
    logistic_model = None
    ridge_model = None
    tree_classifier = None
    tree_regressor = None

    if "source_month" in args.models:
        print(f"h{horizon}: fitting source_month climatology on {len(train):,} train rows", flush=True)
        source_month_table = fit_climatology(
            train,
            ["source_id", "origin_month"],
            prior_probability,
            prior_risk,
            args.climatology_strength,
        )
        artifact_path = args.models_dir / f"source_month_h{horizon}.joblib"
        save_model_artifact(
            {
                "model": "source_month",
                "horizon_months": horizon,
                "table": source_month_table,
                "fallback_probability": prior_probability,
                "fallback_risk": prior_risk,
            },
            artifact_path,
        )
        artifacts.append(_artifact_record("source_month", horizon, artifact_path))

    if "site_month" in args.models:
        print(f"h{horizon}: fitting site_month climatology on {len(train):,} train rows", flush=True)
        site_month_table = fit_climatology(
            train,
            ["source_id", "site_id", "origin_month"],
            prior_probability,
            prior_risk,
            args.climatology_strength,
        )
        artifact_path = args.models_dir / f"site_month_h{horizon}.joblib"
        save_model_artifact(
            {
                "model": "site_month",
                "horizon_months": horizon,
                "table": site_month_table,
                "fallback_probability": prior_probability,
                "fallback_risk": prior_risk,
            },
            artifact_path,
        )
        artifacts.append(_artifact_record("site_month", horizon, artifact_path))

    if "logistic_sgd" in args.models:
        print(f"h{horizon}: fitting logistic_sgd on {len(sklearn_train):,} train rows", flush=True)
        logistic_model = fit_logistic_sgd(sklearn_train, numeric_features, args)
        artifact_path = args.models_dir / f"logistic_sgd_h{horizon}.joblib"
        save_model_artifact(logistic_model, artifact_path)
        artifacts.append(_artifact_record("logistic_sgd", horizon, artifact_path))

    if "ridge_sgd" in args.models:
        print(f"h{horizon}: fitting ridge_sgd on {len(sklearn_train):,} train rows", flush=True)
        ridge_model = fit_ridge_sgd(sklearn_train, numeric_features, args)
        artifact_path = args.models_dir / f"ridge_sgd_h{horizon}.joblib"
        save_model_artifact(ridge_model, artifact_path)
        artifacts.append(_artifact_record("ridge_sgd", horizon, artifact_path))

    if "hist_gradient_boosting" in args.models:
        print(f"h{horizon}: fitting hist_gradient_boosting on up to {args.tree_max_train_rows:,} train rows", flush=True)
        tree_classifier, tree_regressor = fit_hist_gradient_models(sklearn_train, numeric_features, args)
        classifier_path = args.models_dir / f"hist_gradient_boosting_classifier_h{horizon}.joblib"
        regressor_path = args.models_dir / f"hist_gradient_boosting_regressor_h{horizon}.joblib"
        save_model_artifact(tree_classifier, classifier_path)
        save_model_artifact(tree_regressor, regressor_path)
        artifacts.append(_artifact_record("hist_gradient_boosting_classifier", horizon, classifier_path))
        artifacts.append(_artifact_record("hist_gradient_boosting_regressor", horizon, regressor_path))

    for split in ["train", "validation", "test"]:
        eval_frame = _prediction_frame_for_split(frame, split)
        if eval_frame.empty:
            continue
        print(f"h{horizon}: evaluating {split} ({len(eval_frame):,} rows)", flush=True)
        y_bloom = eval_frame["bloom_h"].to_numpy(dtype="int8")
        y_risk = eval_frame["target_risk_chla_h"].to_numpy(dtype="float64")

        if "constant" in args.models:
            probability = np.full(len(eval_frame), prior_probability, dtype="float64")
            risk = np.full(len(eval_frame), prior_risk, dtype="float64")
            write_bundle_outputs(
                PredictionBundle("constant", "classification_and_risk", horizon, split, y_bloom, y_risk, probability, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if source_month_table is not None:
            probability, risk = predict_from_climatology(
                eval_frame,
                source_month_table,
                ["source_id", "origin_month"],
                prior_probability,
                prior_risk,
            )
            write_bundle_outputs(
                PredictionBundle("source_month", "classification_and_risk", horizon, split, y_bloom, y_risk, probability, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if site_month_table is not None:
            probability, risk = predict_from_climatology(
                eval_frame,
                site_month_table,
                ["source_id", "site_id", "origin_month"],
                prior_probability,
                prior_risk,
            )
            write_bundle_outputs(
                PredictionBundle("site_month", "classification_and_risk", horizon, split, y_bloom, y_risk, probability, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if "persistence" in args.models:
            probability, risk = persistence_predictions(eval_frame, prior_probability, prior_risk)
            write_bundle_outputs(
                PredictionBundle("persistence", "classification_and_risk", horizon, split, y_bloom, y_risk, probability, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if logistic_model is not None:
            probability = _positive_class_probability(logistic_model, eval_frame, numeric_features)
            write_bundle_outputs(
                PredictionBundle("logistic_sgd", "classification", horizon, split, y_bloom, y_risk, probability, None),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if ridge_model is not None:
            risk = _risk_prediction(ridge_model, eval_frame, numeric_features)
            write_bundle_outputs(
                PredictionBundle("ridge_sgd", "risk", horizon, split, y_bloom, y_risk, risk, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if tree_classifier is not None:
            probability = _positive_class_probability(tree_classifier, eval_frame, numeric_features)
            write_bundle_outputs(
                PredictionBundle(
                    "hist_gradient_boosting_classifier",
                    "classification",
                    horizon,
                    split,
                    y_bloom,
                    y_risk,
                    probability,
                    None,
                ),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

        if tree_regressor is not None:
            risk = _risk_prediction(tree_regressor, eval_frame, numeric_features)
            write_bundle_outputs(
                PredictionBundle("hist_gradient_boosting_regressor", "risk", horizon, split, y_bloom, y_risk, risk, risk),
                eval_frame,
                args,
                metrics_rows,
                confusion_rows,
                calibration_rows,
            )

    return metrics_rows, confusion_rows, calibration_rows, artifacts


def write_report(metrics: pd.DataFrame, args: argparse.Namespace, artifacts: list[dict[str, Any]]) -> None:
    validation_test = metrics[metrics["split"].isin(["validation", "test"])].copy()
    ranked = validation_test.sort_values(
        ["horizon_months", "split", "pr_auc", "brier"],
        ascending=[True, True, False, True],
        na_position="last",
    )
    lines = [
        "# Baseline Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Splits: `{args.splits}`",
        f"Panel: `{args.panel}`",
        f"Rows evaluated in metrics table: `{_format_int(int(metrics['rows'].sum()))}`",
        f"Models requested: `{', '.join(args.models)}`",
        f"Threshold for confusion matrices: `{args.threshold}`",
        "",
        "## Scope",
        "",
        "Baselines are trained only on the train split for each horizon and evaluated on train, validation, and test.",
        "Feature columns come from the origin month panel only; target and future columns are not used as features.",
        "",
        "## Best Validation/Test Rows By PR-AUC",
        "",
        "| horizon | split | model | task | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | RMSE risk | MAE risk |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(ranked.head(36)):
        lines.append(
            f"| {int(row.horizon_months)} | `{row.split}` | `{row.model}` | `{row.task}` | "
            f"{_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | {_format_float(row.roc_auc)} | "
            f"{_format_float(row.brier)} | {_format_float(row.recall)} | {_format_float(row.macro_f1)} | "
            f"{_format_float(row.rmse_risk)} | {_format_float(row.mae_risk)} |"
        )

    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Metrics: `{args.metrics}`",
            f"- Manifest: `{args.manifest}`",
            f"- Confusion matrices: `{args.reports_dir / 'confusion_matrices'}`",
            f"- Calibration tables: `{args.reports_dir / 'calibration'}`",
            f"- Model artifacts: `{args.models_dir}`",
            "",
            "## Model Artifacts",
            "",
            "| model | horizon | path |",
            "|---|---:|---|",
        ]
    )
    for artifact in artifacts:
        lines.append(f"| `{artifact['model']}` | {int(artifact['horizon_months'])} | `{artifact['path']}` |")

    _write_text_atomic("\n".join(lines) + "\n", args.report)


def collect_output_files(args: argparse.Namespace, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paths = [args.metrics, args.report]
    paths.extend(sorted((args.reports_dir / "confusion_matrices").glob("*.csv")))
    paths.extend(sorted((args.reports_dir / "calibration").glob("*.csv")))
    paths.extend(Path(artifact["path"]) for artifact in artifacts)
    seen: set[str] = set()
    records = []
    for path in paths:
        key = path.as_posix()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        records.append(_file_record(path))
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--models", nargs="+", choices=MODEL_CHOICES, default=DEFAULT_MODELS)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--calibration-bins", type=int, default=10)
    parser.add_argument("--sample-rows-per-split", type=int, default=0)
    parser.add_argument("--max-train-rows-per-horizon", type=int, default=0)
    parser.add_argument("--climatology-strength", type=float, default=20.0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--sgd-alpha", type=float, default=0.0001)
    parser.add_argument("--sgd-max-iter", type=int, default=100)
    parser.add_argument("--sgd-tol", type=float, default=0.001)
    parser.add_argument("--tree-max-train-rows", type=int, default=200_000)
    parser.add_argument("--tree-max-iter", type=int, default=150)
    parser.add_argument("--tree-learning-rate", type=float, default=0.05)
    parser.add_argument("--tree-max-leaf-nodes", type=int, default=31)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    (args.reports_dir / "confusion_matrices").mkdir(parents=True, exist_ok=True)
    (args.reports_dir / "calibration").mkdir(parents=True, exist_ok=True)

    print("loading splits and origin-month panel features", flush=True)
    splits, panel, available_features = load_inputs(args)
    numeric_features = feature_columns_for_model(available_features)
    print(
        f"loaded splits={len(splits):,}, panel_rows={len(panel):,}, numeric_features={len(numeric_features)}",
        flush=True,
    )

    all_metrics: list[dict[str, Any]] = []
    all_confusion: list[pd.DataFrame] = []
    all_calibration: list[pd.DataFrame] = []
    artifacts: list[dict[str, Any]] = []

    started = datetime.now(timezone.utc)
    for horizon in args.horizons:
        horizon_frame = make_horizon_frame(splits, panel, horizon, args)
        train = horizon_frame[horizon_frame["split"] == "train"].copy()
        sklearn_train = sklearn_training_subset(train, args)
        if train.empty:
            raise ValueError(f"No train rows available for horizon {horizon}")
        print(
            f"h{horizon}: rows={len(horizon_frame):,}; train_rows={len(train):,}; "
            f"sklearn_train_rows={len(sklearn_train):,}; "
            f"bloom_rate_train={train['bloom_h'].mean():.4f}",
            flush=True,
        )
        metrics_rows, confusion_rows, calibration_rows, horizon_artifacts = evaluate_horizon_models(
            horizon_frame,
            train,
            sklearn_train,
            numeric_features,
            args,
        )
        all_metrics.extend(metrics_rows)
        all_confusion.extend(confusion_rows)
        all_calibration.extend(calibration_rows)
        artifacts.extend(horizon_artifacts)
        elapsed = datetime.now(timezone.utc) - started
        print(f"h{horizon}: finished baseline evaluation; elapsed={elapsed}", flush=True)

    metrics = pd.DataFrame(all_metrics).sort_values(["horizon_months", "split", "model", "task"]).reset_index(drop=True)
    _write_csv_atomic(metrics, args.metrics)
    if all_confusion:
        confusion = pd.concat(all_confusion, ignore_index=True)
        for key, group in confusion.groupby(["model", "horizon_months", "split"], sort=False):
            model, horizon, split = group_key_tuple(key)
            path = args.reports_dir / "confusion_matrices" / f"{model}_h{int(horizon)}_{split}.csv"
            _write_csv_atomic(group, path)
    if all_calibration:
        calibration = pd.concat(all_calibration, ignore_index=True)
        for key, group in calibration.groupby(["model", "horizon_months", "split"], sort=False):
            model, horizon, split = group_key_tuple(key)
            path = args.reports_dir / "calibration" / f"{model}_h{int(horizon)}_{split}.csv"
            _write_csv_atomic(group, path)

    write_report(metrics, args, artifacts)
    output_files = collect_output_files(args, artifacts)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "splits": args.splits.as_posix(),
        "panel": args.panel.as_posix(),
        "horizons": args.horizons,
        "models": args.models,
        "threshold": args.threshold,
        "sample_rows_per_split": args.sample_rows_per_split,
        "max_train_rows_per_horizon": args.max_train_rows_per_horizon,
        "numeric_features": numeric_features,
        "metrics": args.metrics.as_posix(),
        "report": args.report.as_posix(),
        "model_artifacts": artifacts,
        "output_files": output_files,
    }
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
