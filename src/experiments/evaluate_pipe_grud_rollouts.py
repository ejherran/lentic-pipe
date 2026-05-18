#!/usr/bin/env python
"""Backtest recursive PIPE/GRU-D rollouts against observed future states."""

from __future__ import annotations

import argparse
import math
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.pandas_utils import dataframe_rows, group_key_tuple

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, TARGET_COLUMNS
from src.experiments.rollout_pipe_grud import (
    DEFAULT_FUZZY_CALIBRATORS_DIR,
    DEFAULT_MODEL,
    DEFAULT_MODEL_MANIFEST,
    DEFAULT_SEQUENCES,
    ROLLOUT_VERSION,
    alert_band,
    build_rollouts,
    compute_irc,
    load_calibrators,
    _elapsed,
    _file_record,
    _format_float,
    _format_int,
    _load_model,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
)
from src.experiments.train_pipe_grud import (
    MODEL_VERSION as PIPE_MODEL_VERSION,
    load_sequences,
    prepare_window_frame,
    _require_torch,
)


DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_metrics.csv"
DEFAULT_ALERT_METRICS = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_alert_metrics.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_rollout_backtest_manifest.json"

BACKTEST_VERSION = "pipe_grud_rollout_backtest_v0"
STATE_KEY_COLUMNS = ["source_id", "site_id", "split", "observed_year_month"]
BACKTEST_KEY_COLUMNS = [
    "source_id",
    "site_id",
    "split",
    "origin_year_month",
    "forecast_year_month",
    "rollout_horizon_months",
]
EXAMPLE_COLUMNS = [
    "example_type",
    "source_id",
    "site_id",
    "split",
    "origin_year_month",
    "forecast_year_month",
    "rollout_horizon_months",
    "alert_probability_irc",
    "actual_irc",
    "irc_mean",
    "irc_abs_error",
    "predicted_alert_h",
    "actual_irc_alert",
    "probability_bloom_mean",
    "predicted_bloom_alert_h",
    "bloom_h",
]


def _periods(months: pd.Series) -> pd.PeriodIndex:
    return pd.PeriodIndex(months.astype(str), freq="M")


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


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def observed_state_frame(sequences: pd.DataFrame) -> pd.DataFrame:
    origin = sequences[["source_id", "site_id", "split", "origin_year_month"] + INPUT_COLUMNS[: len(PIPE_STATE_COLUMNS)]].copy()
    origin = origin.rename(columns={"origin_year_month": "observed_year_month"})
    origin = origin.rename(columns={f"x_{column}": f"actual_{column}" for column in PIPE_STATE_COLUMNS})

    target = sequences[["source_id", "site_id", "split", "target_year_month"] + TARGET_COLUMNS].copy()
    target = target.rename(columns={"target_year_month": "observed_year_month"})
    target = target.rename(columns={f"target_{column}": f"actual_{column}" for column in PIPE_STATE_COLUMNS})

    observed = pd.concat([origin, target], ignore_index=True)
    observed = observed[observed["observed_year_month"].notna()].copy()
    for column in ["source_id", "site_id", "split", "observed_year_month"]:
        observed[column] = observed[column].astype(str)
    value_columns = [f"actual_{column}" for column in PIPE_STATE_COLUMNS]
    for column in value_columns:
        observed[column] = pd.to_numeric(observed[column], errors="coerce")
    observed = (
        observed.groupby(STATE_KEY_COLUMNS, dropna=False)[value_columns]
        .mean()
        .reset_index()
        .sort_values(STATE_KEY_COLUMNS)
        .reset_index(drop=True)
    )
    return observed


def _future_availability(
    frame: pd.DataFrame,
    indices: np.ndarray,
    observed: pd.DataFrame,
    rollout_horizon: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = frame.loc[indices, ["source_id", "site_id", "split", "origin_year_month"]].copy()
    candidates["_frame_index"] = indices.astype("int64")
    origin_periods = _periods(candidates["origin_year_month"])
    observed_keys = observed[STATE_KEY_COLUMNS].drop_duplicates().copy()

    availability_columns: list[str] = []
    summary_rows: list[dict[str, Any]] = []
    for horizon in range(1, rollout_horizon + 1):
        column = f"has_observed_h{horizon}"
        availability_columns.append(column)
        check = candidates[["_frame_index", "source_id", "site_id", "split"]].copy()
        check["observed_year_month"] = (origin_periods + horizon).astype(str)
        merged = check.merge(
            observed_keys.assign(_observed_available=True),
            on=STATE_KEY_COLUMNS,
            how="left",
            validate="many_to_one",
        )
        candidates[column] = merged["_observed_available"].fillna(False).to_numpy(dtype=bool)
        summary_rows.append(
            {
                "rollout_horizon_months": horizon,
                "eligible_origins": int(len(candidates)),
                "origins_with_observed_future": int(candidates[column].sum()),
            }
        )

    candidates["available_horizons"] = candidates[availability_columns].sum(axis=1).astype("int16")
    summary = pd.DataFrame(summary_rows)
    return candidates, summary


def select_backtest_indices(
    frame: pd.DataFrame,
    args: argparse.Namespace,
    history_length: int,
    observed: pd.DataFrame,
) -> tuple[np.ndarray, pd.DataFrame]:
    eligible = frame[frame["window_position"] >= history_length - 1].copy()
    if args.split != "all":
        eligible = eligible[eligible["split"] == args.split].copy()
    if eligible.empty:
        raise ValueError("No eligible backtest origins found for the requested split")

    eligible = eligible.sort_values(["source_id", "site_id", "origin_year_month"], kind="mergesort")
    availability, summary = _future_availability(
        frame,
        eligible.index.to_numpy(dtype="int64"),
        observed,
        rollout_horizon=args.rollout_horizon,
    )
    horizon_columns = [f"has_observed_h{horizon}" for horizon in range(1, args.rollout_horizon + 1)]
    if args.allow_partial_horizons:
        selected = availability[availability["available_horizons"] > 0].copy()
    else:
        selected = availability[availability[horizon_columns].all(axis=1)].copy()
    if selected.empty:
        raise ValueError("No backtest origins have observed future states for the requested horizon policy")

    if args.max_origins is not None and len(selected) > args.max_origins:
        rng = np.random.default_rng(int(args.random_seed))
        selected_positions = rng.choice(selected.index.to_numpy(), size=int(args.max_origins), replace=False)
        selected = selected.loc[np.sort(selected_positions)].copy()

    summary["selected_origins"] = int(len(selected))
    summary["selection_policy"] = "any_observed_horizon" if args.allow_partial_horizons else "complete_horizons"
    return selected["_frame_index"].to_numpy(dtype="int64"), summary


def load_bloom_targets(path: Path, max_horizon: int) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    targets = pd.read_parquet(path)
    needed = [
        "source_id",
        "site_id",
        "origin_year_month",
        "horizon_months",
        "split",
        "target_year_month",
        "bloom_h",
        "target_risk_chla_h",
    ]
    missing = [column for column in needed if column not in targets.columns]
    if missing:
        raise ValueError(f"Bloom target split table is missing required columns: {missing}")
    targets = targets[needed].copy()
    targets = targets[targets["horizon_months"].between(1, max_horizon)].copy()
    targets = targets.rename(
        columns={
            "horizon_months": "rollout_horizon_months",
            "target_year_month": "bloom_target_year_month",
        }
    )
    targets["bloom_h"] = targets["bloom_h"].astype(bool).astype("int8")
    targets["target_risk_chla_h"] = pd.to_numeric(targets["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    for column in ["source_id", "site_id", "origin_year_month", "split", "bloom_target_year_month"]:
        targets[column] = targets[column].astype(str)
    return targets


def attach_observations(
    rollouts: pd.DataFrame,
    observed: pd.DataFrame,
    bloom_targets: pd.DataFrame,
    *,
    args: argparse.Namespace,
) -> pd.DataFrame:
    state = observed.rename(columns={"observed_year_month": "forecast_year_month"})
    out = rollouts.merge(
        state,
        on=["source_id", "site_id", "split", "forecast_year_month"],
        how="left",
        validate="many_to_one",
    )
    actual_columns = [f"actual_{column}" for column in PIPE_STATE_COLUMNS]
    out = out.dropna(subset=actual_columns).copy()
    if not bloom_targets.empty:
        out = out.merge(
            bloom_targets,
            on=["source_id", "site_id", "origin_year_month", "rollout_horizon_months", "split"],
            how="left",
            validate="many_to_one",
        )

    actual_states = out[actual_columns].to_numpy(dtype="float64")
    out["actual_irc"] = compute_irc(actual_states, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
    out["actual_irc_alert"] = out["actual_irc"] >= float(args.irc_alert_threshold)
    out["irc_error"] = out["irc_mean"].astype("float64") - out["actual_irc"].astype("float64")
    out["irc_abs_error"] = out["irc_error"].abs()
    out["irc_squared_error"] = out["irc_error"] ** 2
    out["irc_interval_90_covered"] = (out["actual_irc"] >= out["irc_p05"]) & (out["actual_irc"] <= out["irc_p95"])
    out["irc_interval_90_width"] = out["irc_p95"] - out["irc_p05"]
    out["irc_persistence_error"] = out["origin_irc1_rollout_basis"].astype("float64") - out["actual_irc"]
    out["irc_persistence_abs_error"] = out["irc_persistence_error"].abs()
    out["irc_persistence_squared_error"] = out["irc_persistence_error"] ** 2

    for column in PIPE_STATE_COLUMNS:
        actual = out[f"actual_{column}"].astype("float64")
        predicted = out[f"{column}_mean"].astype("float64")
        persistence = out[f"origin_{column}"].astype("float64")
        out[f"{column}_error"] = predicted - actual
        out[f"{column}_abs_error"] = out[f"{column}_error"].abs()
        out[f"{column}_squared_error"] = out[f"{column}_error"] ** 2
        out[f"{column}_interval_90_covered"] = (actual >= out[f"{column}_p05"]) & (actual <= out[f"{column}_p95"])
        out[f"{column}_interval_90_width"] = out[f"{column}_p95"] - out[f"{column}_p05"]
        out[f"{column}_persistence_error"] = persistence - actual
        out[f"{column}_persistence_abs_error"] = out[f"{column}_persistence_error"].abs()
        out[f"{column}_persistence_squared_error"] = out[f"{column}_persistence_error"] ** 2

    out["actual_irc_band"] = alert_band(out["actual_irc"])
    return out.sort_values(BACKTEST_KEY_COLUMNS).reset_index(drop=True)


def _iter_horizon_split_groups(frame: pd.DataFrame) -> Iterable[tuple[int, str, str, str, pd.DataFrame]]:
    for key, horizon_split in frame.groupby(["rollout_horizon_months", "split"], sort=True):
        horizon, split = group_key_tuple(key)
        yield int(horizon), str(split), "overall", "all", horizon_split
        for source_id, source_group in horizon_split.groupby("source_id", dropna=False, sort=True):
            yield int(horizon), str(split), "source", str(source_id), source_group


def _state_metric_row(
    *,
    horizon: int,
    split: str,
    group_type: str,
    group_value: str,
    target: str,
    rows: int,
    error: np.ndarray,
    abs_error: np.ndarray,
    squared_error: np.ndarray,
    covered: np.ndarray,
    width: np.ndarray,
    persistence_abs_error: np.ndarray,
    persistence_squared_error: np.ndarray,
) -> dict[str, Any]:
    rmse = math.sqrt(float(np.nanmean(squared_error))) if len(squared_error) else np.nan
    mae = float(np.nanmean(abs_error)) if len(abs_error) else np.nan
    persistence_rmse = math.sqrt(float(np.nanmean(persistence_squared_error))) if len(persistence_squared_error) else np.nan
    persistence_mae = float(np.nanmean(persistence_abs_error)) if len(persistence_abs_error) else np.nan
    return {
        "backtest_version": BACKTEST_VERSION,
        "group_type": group_type,
        "group_value": group_value,
        "source_id": group_value if group_type == "source" else "all",
        "split": split,
        "rollout_horizon_months": int(horizon),
        "target": target,
        "rows": int(rows),
        "rmse": rmse,
        "mae": mae,
        "bias": float(np.nanmean(error)) if len(error) else np.nan,
        "simulation_90_coverage": float(np.nanmean(covered)) if len(covered) else np.nan,
        "simulation_90_mean_width": float(np.nanmean(width)) if len(width) else np.nan,
        "persistence_rmse": persistence_rmse,
        "persistence_mae": persistence_mae,
        "rmse_relative_improvement": _safe_rate(persistence_rmse - rmse, persistence_rmse),
        "mae_relative_improvement": _safe_rate(persistence_mae - mae, persistence_mae),
    }


def build_state_metrics(backtest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, split, group_type, group_value, group in _iter_horizon_split_groups(backtest):
        rows.append(
            _state_metric_row(
                horizon=horizon,
                split=split,
                group_type=group_type,
                group_value=group_value,
                target="all",
                rows=len(group) * len(PIPE_STATE_COLUMNS),
                error=group[[f"{column}_error" for column in PIPE_STATE_COLUMNS]].to_numpy(dtype="float64").ravel(),
                abs_error=group[[f"{column}_abs_error" for column in PIPE_STATE_COLUMNS]].to_numpy(dtype="float64").ravel(),
                squared_error=group[[f"{column}_squared_error" for column in PIPE_STATE_COLUMNS]].to_numpy(dtype="float64").ravel(),
                covered=group[[f"{column}_interval_90_covered" for column in PIPE_STATE_COLUMNS]].to_numpy(dtype="float64").ravel(),
                width=group[[f"{column}_interval_90_width" for column in PIPE_STATE_COLUMNS]].to_numpy(dtype="float64").ravel(),
                persistence_abs_error=group[
                    [f"{column}_persistence_abs_error" for column in PIPE_STATE_COLUMNS]
                ].to_numpy(dtype="float64").ravel(),
                persistence_squared_error=group[
                    [f"{column}_persistence_squared_error" for column in PIPE_STATE_COLUMNS]
                ].to_numpy(dtype="float64").ravel(),
            )
        )
        for target in PIPE_STATE_COLUMNS:
            rows.append(
                _state_metric_row(
                    horizon=horizon,
                    split=split,
                    group_type=group_type,
                    group_value=group_value,
                    target=target,
                    rows=len(group),
                    error=group[f"{target}_error"].to_numpy(dtype="float64"),
                    abs_error=group[f"{target}_abs_error"].to_numpy(dtype="float64"),
                    squared_error=group[f"{target}_squared_error"].to_numpy(dtype="float64"),
                    covered=group[f"{target}_interval_90_covered"].to_numpy(dtype="float64"),
                    width=group[f"{target}_interval_90_width"].to_numpy(dtype="float64"),
                    persistence_abs_error=group[f"{target}_persistence_abs_error"].to_numpy(dtype="float64"),
                    persistence_squared_error=group[f"{target}_persistence_squared_error"].to_numpy(dtype="float64"),
                )
            )
        rows.append(
            _state_metric_row(
                horizon=horizon,
                split=split,
                group_type=group_type,
                group_value=group_value,
                target="irc1",
                rows=len(group),
                error=group["irc_error"].to_numpy(dtype="float64"),
                abs_error=group["irc_abs_error"].to_numpy(dtype="float64"),
                squared_error=group["irc_squared_error"].to_numpy(dtype="float64"),
                covered=group["irc_interval_90_covered"].to_numpy(dtype="float64"),
                width=group["irc_interval_90_width"].to_numpy(dtype="float64"),
                persistence_abs_error=group["irc_persistence_abs_error"].to_numpy(dtype="float64"),
                persistence_squared_error=group["irc_persistence_squared_error"].to_numpy(dtype="float64"),
            )
        )
    return pd.DataFrame(rows).sort_values(["split", "rollout_horizon_months", "group_type", "group_value", "target"])


def _classification_row(
    *,
    horizon: int,
    split: str,
    group_type: str,
    group_value: str,
    target_event: str,
    probability: np.ndarray,
    predicted: np.ndarray,
    actual: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    matrix = confusion_matrix(actual, predicted, labels=[0, 1])
    tn, fp, fn, tp = [int(value) for value in matrix.ravel()]
    return {
        "backtest_version": BACKTEST_VERSION,
        "target_event": target_event,
        "group_type": group_type,
        "group_value": group_value,
        "source_id": group_value if group_type == "source" else "all",
        "split": split,
        "rollout_horizon_months": int(horizon),
        "rows": int(len(actual)),
        "threshold": float(threshold),
        "positive_rows": int(actual.sum()),
        "positive_rate": float(actual.mean()) if len(actual) else np.nan,
        "predicted_positive_rows": int(predicted.sum()),
        "predicted_positive_rate": float(predicted.mean()) if len(predicted) else np.nan,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": _safe_metric(precision_score, actual, predicted, zero_division=0),
        "recall": _safe_metric(recall_score, actual, predicted, zero_division=0),
        "specificity": _safe_rate(tn, tn + fp),
        "macro_f1": _safe_metric(f1_score, actual, predicted, average="macro", zero_division=0),
        "pr_auc": _safe_metric(average_precision_score, actual, probability),
        "roc_auc": _safe_metric(roc_auc_score, actual, probability),
        "brier": _safe_metric(brier_score_loss, actual, probability),
    }


def build_alert_metrics(backtest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, split, group_type, group_value, group in _iter_horizon_split_groups(backtest):
        rows.append(
            _classification_row(
                horizon=horizon,
                split=split,
                group_type=group_type,
                group_value=group_value,
                target_event="irc_alert",
                probability=_clip01(group["alert_probability_irc"]),
                predicted=group["predicted_alert_h"].astype("int8").to_numpy(),
                actual=group["actual_irc_alert"].astype("int8").to_numpy(),
                threshold=float(group["alert_probability_threshold"].iloc[0]),
            )
        )
        if "bloom_h" in group.columns and group["bloom_h"].notna().any() and group["probability_bloom_mean"].notna().any():
            bloom_group = group[group["bloom_h"].notna() & group["probability_bloom_mean"].notna()].copy()
            rows.append(
                _classification_row(
                    horizon=horizon,
                    split=split,
                    group_type=group_type,
                    group_value=group_value,
                    target_event="bloom_h",
                    probability=_clip01(bloom_group["probability_bloom_mean"]),
                    predicted=bloom_group["predicted_bloom_alert_h"].astype("int8").to_numpy(),
                    actual=bloom_group["bloom_h"].astype("int8").to_numpy(),
                    threshold=float(bloom_group["bloom_probability_threshold_h"].iloc[0]),
                )
            )
    return pd.DataFrame(rows).sort_values(["target_event", "split", "rollout_horizon_months", "group_type", "group_value"])


def build_examples(backtest: pd.DataFrame, examples_per_group: int) -> pd.DataFrame:
    if examples_per_group <= 0 or backtest.empty:
        return pd.DataFrame(columns=EXAMPLE_COLUMNS)
    parts: list[pd.DataFrame] = []
    for _, group in backtest.groupby(["rollout_horizon_months", "split"], sort=True):
        largest = group.sort_values("irc_abs_error", ascending=False, kind="mergesort").head(examples_per_group).copy()
        largest["example_type"] = "largest_irc_abs_error"
        parts.append(largest)

        false_positive = group[(group["predicted_alert_h"]) & (~group["actual_irc_alert"])].copy()
        if not false_positive.empty:
            false_positive = false_positive.sort_values("alert_probability_irc", ascending=False, kind="mergesort").head(
                examples_per_group
            )
            false_positive["example_type"] = "irc_alert_false_positive"
            parts.append(false_positive)

        false_negative = group[(~group["predicted_alert_h"]) & (group["actual_irc_alert"])].copy()
        if not false_negative.empty:
            false_negative = false_negative.sort_values("alert_probability_irc", ascending=True, kind="mergesort").head(
                examples_per_group
            )
            false_negative["example_type"] = "irc_alert_false_negative"
            parts.append(false_negative)

    if not parts:
        return pd.DataFrame(columns=EXAMPLE_COLUMNS)
    examples = pd.concat(parts, ignore_index=True, sort=False)
    for column in EXAMPLE_COLUMNS:
        if column not in examples.columns:
            examples[column] = np.nan
    return examples[EXAMPLE_COLUMNS].sort_values(["rollout_horizon_months", "split", "example_type"])


def write_report(
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    examples: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    evaluated_rows: int,
    history_length: int,
    calibrated_horizons: list[int],
    started_at: datetime,
) -> None:
    headline = metrics[
        (metrics["group_type"] == "overall") & (metrics["source_id"] == "all") & (metrics["target"].isin(["all", "irc1"]))
    ].copy()
    alert_headline = alert_metrics[
        (alert_metrics["group_type"] == "overall") & (alert_metrics["source_id"] == "all")
    ].copy()
    lines = [
        "# PIPE/GRU-D Rollout Backtest Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.",
        "Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.",
        "",
        "## Configuration",
        "",
        f"- Split filter: `{args.split}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- Evaluated rollout rows: `{_format_int(evaluated_rows)}`",
        f"- Max origins cap: `{args.max_origins}`",
        f"- History length: `{history_length}`",
        f"- Rollout horizon: `{args.rollout_horizon}` month(s)",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- Horizon policy: `{'partial' if args.allow_partial_horizons else 'complete'}`",
        f"- IRC weights: alpha=`{args.irc_alpha}`, beta=`{args.irc_beta}`, gamma=`{args.irc_gamma}`",
        f"- IRC alert threshold: `{args.irc_alert_threshold}`",
        f"- Alert probability threshold: `{args.alert_prob_threshold}`",
        f"- Random seed: `{args.random_seed}`",
        f"- Calibrated bloom horizons available: `{calibrated_horizons}`",
        "",
        "## Future Availability",
        "",
        "| horizon | eligible origins | origins with observed future | selected origins | policy |",
        "|---:|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(availability_summary.sort_values("rollout_horizon_months")):
        lines.append(
            f"| {int(row.rollout_horizon_months)} | {_format_int(int(row.eligible_origins))} | "
            f"{_format_int(int(row.origins_with_observed_future))} | {_format_int(int(row.selected_origins))} | "
            f"`{row.selection_policy}` |"
        )

    lines.extend(
        [
            "",
            "## State Metrics",
            "",
            "| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if headline.empty:
        lines.append("| `NA` | NA | `NA` | 0 | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(headline.sort_values(["split", "rollout_horizon_months", "target"])):
            lines.append(
                f"| `{row.split}` | {int(row.rollout_horizon_months)} | `{row.target}` | "
                f"{_format_int(int(row.rows))} | {_format_float(row.rmse)} | {_format_float(row.persistence_rmse)} | "
                f"{_format_float(row.rmse_relative_improvement)} | {_format_float(row.mae)} | "
                f"{_format_float(row.simulation_90_coverage)} |"
            )

    lines.extend(
        [
            "",
            "## Alert Metrics",
            "",
            "| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if alert_headline.empty:
        lines.append("| `NA` | `NA` | NA | 0 | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(alert_headline.sort_values(["target_event", "split", "rollout_horizon_months"])):
            lines.append(
                f"| `{row.target_event}` | `{row.split}` | {int(row.rollout_horizon_months)} | "
                f"{_format_int(int(row.rows))} | {_format_float(row.positive_rate)} | "
                f"{_format_float(row.predicted_positive_rate)} | {_format_float(row.pr_auc)} | "
                f"{_format_float(row.brier)} | {_format_float(row.recall)} | {_format_float(row.macro_f1)} |"
            )

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.",
            "- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.",
            "- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.",
            "- Source-level rows are diagnostic and can be unstable for sources with limited support.",
            "",
            "## Outputs",
            "",
            f"- State metrics: `{args.metrics}`",
            f"- Alert metrics: `{args.alert_metrics}`",
            f"- Diagnostic examples: `{args.examples}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    examples: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    evaluated_rows: int,
    history_length: int,
    calibrators: dict[int, Any],
    model_config: dict[str, Any],
    model_payload: dict[str, Any],
    started_at: datetime,
) -> dict[str, Any]:
    inputs = [args.sequences, args.model]
    if args.splits.exists():
        inputs.append(args.splits)
    if args.model_manifest.exists():
        inputs.append(args.model_manifest)
    inputs.extend(info.path for info in calibrators.values())
    outputs = [args.metrics, args.alert_metrics, args.examples, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "backtest_version": BACKTEST_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "pipe_model_version": model_payload.get("model_version", PIPE_MODEL_VERSION),
        "config": {
            "split": args.split,
            "history_length": int(history_length),
            "rollout_horizon": int(args.rollout_horizon),
            "samples": int(1 if args.deterministic else args.samples),
            "deterministic": bool(args.deterministic),
            "batch_size": int(args.batch_size),
            "max_origins": args.max_origins,
            "allow_partial_horizons": bool(args.allow_partial_horizons),
            "irc_alpha": float(args.irc_alpha),
            "irc_beta": float(args.irc_beta),
            "irc_gamma": float(args.irc_gamma),
            "irc_alert_threshold": float(args.irc_alert_threshold),
            "alert_prob_threshold": float(args.alert_prob_threshold),
            "random_seed": int(args.random_seed),
            "model_config": model_config,
            "calibrated_bloom_horizons": sorted(calibrators),
        },
        "row_counts": {
            "selected_origins": int(selected_origins),
            "evaluated_rollout_rows": int(evaluated_rows),
            "availability_summary_rows": int(len(availability_summary)),
            "metric_rows": int(len(metrics)),
            "alert_metric_rows": int(len(alert_metrics)),
            "example_rows": int(len(examples)),
        },
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for path in outputs],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--alert-metrics", type=Path, default=DEFAULT_ALERT_METRICS)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--split", choices=["all", "train", "validation", "test"], default="test")
    parser.add_argument("--history-length", type=int, default=None)
    parser.add_argument("--rollout-horizon", type=int, default=3)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-origins", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--examples-per-group", type=int, default=20)
    parser.add_argument("--irc-alpha", type=float, default=0.5)
    parser.add_argument("--irc-beta", type=float, default=0.5)
    parser.add_argument("--irc-gamma", type=float, default=2.0)
    parser.add_argument("--irc-alert-threshold", type=float, default=0.5)
    parser.add_argument("--alert-prob-threshold", type=float, default=0.5)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--disable-calibrated-bloom", action="store_true")
    parser.add_argument("--require-calibrators", action="store_true")
    parser.add_argument("--allow-partial-horizons", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rollout_horizon < 1:
        raise ValueError("--rollout-horizon must be >= 1")
    if args.samples < 1:
        raise ValueError("--samples must be >= 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")
    if args.max_origins is not None and args.max_origins < 1:
        raise ValueError("--max-origins must be >= 1")

    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    torch = _require_torch()
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)

    print(f"loading model {args.model}", flush=True)
    model, model_config, model_payload, blend_weights = _load_model(args.model, device)
    history_length = int(args.history_length or model_config["history_length"])
    if history_length < 1:
        raise ValueError("history length must be >= 1")

    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_window_frame(frame)
    observed = observed_state_frame(frame)
    print(f"sequence rows={len(frame):,}; observed states={len(observed):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    calibrators = load_calibrators(args)
    print(f"loaded calibrated bloom horizons={sorted(calibrators)}", flush=True)

    indices, availability_summary = select_backtest_indices(frame, args, history_length, observed)
    print(f"selected backtest origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    rollouts = build_rollouts(
        frame,
        indices,
        model=model,
        blend_weights=blend_weights,
        args=args,
        history_length=history_length,
        device=device,
        calibrators=calibrators,
    )
    bloom_targets = load_bloom_targets(args.splits, args.rollout_horizon)
    backtest = attach_observations(rollouts, observed, bloom_targets, args=args)
    if backtest.empty:
        raise ValueError("No rollout rows could be matched to observed future states")
    print(f"matched observed rollout rows={len(backtest):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    metrics = build_state_metrics(backtest)
    alert_metrics = build_alert_metrics(backtest)
    examples = build_examples(backtest, args.examples_per_group)

    _write_csv_atomic(metrics, args.metrics)
    print(f"wrote {args.metrics}", flush=True)
    _write_csv_atomic(alert_metrics, args.alert_metrics)
    print(f"wrote {args.alert_metrics}", flush=True)
    _write_csv_atomic(examples, args.examples)
    print(f"wrote {args.examples}", flush=True)
    write_report(
        args=args,
        metrics=metrics,
        alert_metrics=alert_metrics,
        examples=examples,
        availability_summary=availability_summary,
        selected_origins=len(indices),
        evaluated_rows=len(backtest),
        history_length=history_length,
        calibrated_horizons=sorted(calibrators),
        started_at=started_at,
    )
    print(f"wrote {args.report}", flush=True)
    manifest = manifest_payload(
        args=args,
        metrics=metrics,
        alert_metrics=alert_metrics,
        examples=examples,
        availability_summary=availability_summary,
        selected_origins=len(indices),
        evaluated_rows=len(backtest),
        history_length=history_length,
        calibrators=calibrators,
        model_config=model_config,
        model_payload=model_payload,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}; elapsed={_elapsed(started_monotonic)}", flush=True)


if __name__ == "__main__":
    main()
