#!/usr/bin/env python
"""Evaluate controlled degradation scenarios on precomputed alert score rows."""

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
import yaml
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.pandas_utils import dataframe_rows


DEGRADATION_VERSION = "controlled_degradation_v0"
DEFAULT_CONFIG = Path("configs/degradation_scenarios.yaml")
DEFAULT_SCORED_ROWS = Path("reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet")
DEFAULT_THRESHOLDS = Path("reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv")
DEFAULT_REPORT_DIR = Path("reports/degradation")
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_metrics.csv"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "controlled_degradation_summary.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "controlled_degradation_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "controlled_degradation_manifest.json"
OUTPUT_SUFFIXES = {
    "metrics": "metrics.csv",
    "summary": "summary.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}

KEY_COLUMNS = [
    "source_id",
    "site_id",
    "split",
    "origin_year_month",
    "rollout_horizon_months",
]
EVENT_SPECS = {
    "irc_alert": {
        "actual_column": "actual_irc_alert",
    },
    "bloom_h": {
        "actual_column": "bloom_h",
    },
}
SCORE_AFFECTING_OPERATIONS = {
    "random_value_dropout",
    "set_variables_missing",
    "temporal_block_dropout",
}
METRIC_VALUE_COLUMNS = [
    "positive_rate",
    "alert_rate",
    "precision",
    "recall",
    "specificity",
    "f1",
    "f2",
    "mcc",
    "balanced_accuracy",
    "pr_auc",
    "roc_auc",
    "brier",
]
METRIC_COLUMNS = [
    "degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "split",
    "rollout_horizon_months",
    "source_id",
    "target_event",
    "alert_policy",
    "score_column",
    "threshold",
    "score_recomputed",
    "rows",
    "control_rows",
    "rows_retained_rate",
    "positive_rows",
    "positive_rate",
    "predicted_positive_rows",
    "alert_rate",
    "tn",
    "fp",
    "fn",
    "tp",
    "precision",
    "recall",
    "specificity",
    "f1",
    "f2",
    "mcc",
    "balanced_accuracy",
    "pr_auc",
    "roc_auc",
    "brier",
    *[f"delta_{column}_vs_control" for column in METRIC_VALUE_COLUMNS],
]
SUMMARY_COLUMNS = [
    "degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "reason",
    "score_recomputed",
    "input_rows",
    "output_rows",
    "rows_retained_rate",
    "affected_rows",
    "affected_cells",
    "metrics_rows",
    "operation_types",
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


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


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


def _f2_score(precision: float, recall: float) -> float:
    if pd.isna(precision) or pd.isna(recall):
        return float("nan")
    beta2 = 4.0
    denominator = beta2 * precision + recall
    if denominator == 0:
        return 0.0
    return float((1.0 + beta2) * precision * recall / denominator)


def _mcc(tn: int, fp: int, fn: int, tp: int) -> float:
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denominator == 0:
        return float("nan")
    return float(((tp * tn) - (fp * fn)) / denominator)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table suffix for {path}: expected .parquet or .csv")


def read_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Config {path} did not parse to a mapping")
    if payload.get("schema_version") != 1:
        raise ValueError("Only degradation config schema_version 1 is supported")
    return payload


def default_output(
    path_from_args: Path | None,
    config: dict[str, Any],
    key: str,
    fallback: Path,
    *,
    output_name: str | None = None,
    output_dir: Path = DEFAULT_REPORT_DIR,
) -> Path:
    if path_from_args is not None:
        return path_from_args
    if output_name is not None:
        suffix = OUTPUT_SUFFIXES[key]
        return output_dir / f"controlled_degradation_{output_name}_{suffix}"
    value = config.get("outputs", {}).get(key)
    return Path(value) if value else fallback


def validate_scenarios(config: dict[str, Any]) -> None:
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Config must define at least one scenario")
    ids = [scenario.get("scenario_id") for scenario in scenarios]
    duplicates = sorted({scenario_id for scenario_id in ids if ids.count(scenario_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate scenario_id values: {duplicates}")
    defined_sets = config.get("scenario_sets", {})
    if not isinstance(defined_sets, dict):
        raise ValueError("scenario_sets must be a mapping")
    known = set(ids)
    for set_name, scenario_ids in defined_sets.items():
        missing = sorted(set(scenario_ids) - known)
        if missing:
            raise ValueError(f"scenario set {set_name!r} references unknown scenarios: {missing}")


def select_scenarios(config: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    scenarios = config["scenarios"]
    if args.scenarios:
        selected_ids = args.scenarios
    elif args.scenario_set == "all":
        selected_ids = [scenario["scenario_id"] for scenario in scenarios]
    else:
        scenario_sets = config.get("scenario_sets", {})
        if args.scenario_set not in scenario_sets:
            raise ValueError(f"Unknown scenario set {args.scenario_set!r}")
        selected_ids = list(scenario_sets[args.scenario_set])
    lookup = {scenario["scenario_id"]: scenario for scenario in scenarios}
    missing = sorted(set(selected_ids) - set(lookup))
    if missing:
        raise ValueError(f"Selected unknown scenarios: {missing}")
    return [lookup[scenario_id] for scenario_id in selected_ids]


def threshold_policies(config: dict[str, Any], args: argparse.Namespace) -> list[str]:
    if args.policies:
        return args.policies
    default_policy = config.get("protocol", {}).get("default_alert_policy", {}).get("selection_objective", "closest_pr")
    comparisons = config.get("protocol", {}).get("comparison_alert_policies", [])
    policies = [str(default_policy), *[str(item) for item in comparisons]]
    return list(dict.fromkeys(policies))


def validate_rows(rows: pd.DataFrame, thresholds: pd.DataFrame, policies: list[str]) -> None:
    required = set(KEY_COLUMNS)
    required.update(["forecast_year_month"])
    threshold_rows = thresholds[thresholds["policy_name"].isin(policies)]
    if threshold_rows.empty:
        raise ValueError(f"No threshold rows found for requested policies: {policies}")
    required.update(threshold_rows["score_column"].dropna().astype(str).unique())
    for event in threshold_rows["target_event"].dropna().astype(str).unique():
        if event not in EVENT_SPECS:
            raise ValueError(f"Unsupported target_event in thresholds: {event}")
        required.add(EVENT_SPECS[event]["actual_column"])
    missing = sorted(column for column in required if column not in rows.columns)
    if missing:
        raise ValueError(f"Scored rows are missing required columns: {missing}")


def prepare_rows(rows: pd.DataFrame, thresholds: pd.DataFrame, policies: list[str]) -> pd.DataFrame:
    validate_rows(rows, thresholds, policies)
    out = rows.copy()
    for column in ["source_id", "site_id", "split", "origin_year_month", "forecast_year_month"]:
        out[column] = out[column].astype(str)
    out["rollout_horizon_months"] = pd.to_numeric(out["rollout_horizon_months"], errors="coerce").astype("int64")
    for spec in EVENT_SPECS.values():
        actual_column = spec["actual_column"]
        if actual_column in out.columns:
            out[actual_column] = _binary_series(out[actual_column])
    for column in thresholds["score_column"].dropna().astype(str).unique():
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def operation_types(scenario: dict[str, Any]) -> list[str]:
    return [str(operation.get("type")) for operation in scenario.get("operations", [])]


def scenario_needs_recompute(scenario: dict[str, Any]) -> bool:
    return any(operation_type in SCORE_AFFECTING_OPERATIONS for operation_type in operation_types(scenario))


def seeds_for_scenario(scenario: dict[str, Any], config: dict[str, Any]) -> list[int | None]:
    random_operations = {"random_value_dropout", "temporal_block_dropout", "stratified_site_retention"}
    if not any(operation_type in random_operations for operation_type in operation_types(scenario)):
        return [None]
    seeds = config.get("randomization", {}).get("seeds", [0])
    if not seeds:
        return [0]
    return [int(seed) for seed in seeds]


def variable_group_columns(config: dict[str, Any], group_name: str, frame: pd.DataFrame) -> list[str]:
    group = config.get("canonical_variable_groups", {}).get(group_name)
    if not isinstance(group, dict):
        raise ValueError(f"Unknown variable group: {group_name}")
    variables = [str(column) for column in group.get("variables", [])]
    return [column for column in variables if column in frame.columns]


def _set_columns_missing(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns:
        return out, 0, 0
    before = out[columns].notna()
    out.loc[:, columns] = np.nan
    affected_cells = int(before.sum().sum())
    affected_rows = int(before.any(axis=1).sum())
    return out, affected_rows, affected_cells


def _random_value_dropout(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    rate: float,
    seed: int,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns or rate <= 0:
        return out, 0, 0
    rng = np.random.default_rng(seed)
    eligible = out[columns].notna().to_numpy()
    drop = (rng.random(eligible.shape) < float(rate)) & eligible
    for index, column in enumerate(columns):
        if drop[:, index].any():
            out.loc[drop[:, index], column] = np.nan
    affected_rows = int(drop.any(axis=1).sum())
    affected_cells = int(drop.sum())
    return out, affected_rows, affected_cells


def _temporal_block_dropout(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    block_length_months: int,
    site_history_block_rate: float,
    seed: int,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns or block_length_months <= 0 or site_history_block_rate <= 0:
        return out, 0, 0
    rng = np.random.default_rng(seed)
    affected_mask = pd.Series(False, index=out.index)
    group_columns = ["source_id", "split", "site_id"]
    for _, group in out.groupby(group_columns, sort=True):
        if rng.random() >= float(site_history_block_rate):
            continue
        months = pd.PeriodIndex(group["origin_year_month"].astype(str), freq="M")
        unique_months = pd.PeriodIndex(sorted(months.unique()), freq="M")
        if len(unique_months) == 0:
            continue
        start = unique_months[int(rng.integers(0, len(unique_months)))]
        end = start + int(block_length_months) - 1
        selected = (months >= start) & (months <= end)
        if selected.any():
            affected_mask.loc[group.index[selected]] = True
    if not affected_mask.any():
        return out, 0, 0
    before = out.loc[affected_mask, columns].notna()
    out.loc[affected_mask, columns] = np.nan
    affected_cells = int(before.sum().sum())
    affected_rows = int(before.any(axis=1).sum())
    return out, affected_rows, affected_cells


def _filter_source_id(frame: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
    out = frame
    include = operation.get("include")
    exclude = operation.get("exclude")
    if include:
        include_set = {str(value) for value in include}
        out = out[out["source_id"].isin(include_set)].copy()
    if exclude:
        exclude_set = {str(value) for value in exclude}
        out = out[~out["source_id"].isin(exclude_set)].copy()
    return out


def _stratified_site_retention(frame: pd.DataFrame, retain_fraction: float, seed: int) -> pd.DataFrame:
    if retain_fraction >= 1:
        return frame.copy()
    rng = np.random.default_rng(seed)
    retained: list[pd.DataFrame] = []
    site_frame = frame[["source_id", "split", "site_id"]].drop_duplicates().sort_values(["source_id", "split", "site_id"])
    for _, group in site_frame.groupby(["source_id", "split"], sort=True):
        sites = group["site_id"].to_numpy()
        keep_count = int(np.ceil(len(sites) * max(float(retain_fraction), 0.0)))
        keep_count = min(len(sites), max(1, keep_count)) if len(sites) else 0
        if keep_count == 0:
            continue
        keep_sites = set(rng.choice(sites, size=keep_count, replace=False).tolist())
        retained.append(frame[(frame["source_id"] == group["source_id"].iloc[0]) & (frame["split"] == group["split"].iloc[0]) & (frame["site_id"].isin(keep_sites))])
    if not retained:
        return frame.iloc[0:0].copy()
    return pd.concat(retained, ignore_index=False).sort_index().copy()


def apply_operations(
    frame: pd.DataFrame,
    scenario: dict[str, Any],
    config: dict[str, Any],
    seed: int | None,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    affected_rows = 0
    affected_cells = 0
    effective_seed = 0 if seed is None else int(seed)
    for operation in scenario.get("operations", []):
        operation_type = str(operation.get("type"))
        if operation_type == "filter_source_id":
            out = _filter_source_id(out, operation)
        elif operation_type == "stratified_site_retention":
            out = _stratified_site_retention(out, float(operation.get("retain_fraction", 1.0)), effective_seed)
        elif operation_type == "set_variables_missing":
            columns = variable_group_columns(config, str(operation.get("variable_group")), out)
            out, rows, cells = _set_columns_missing(out, columns)
            affected_rows += rows
            affected_cells += cells
        elif operation_type == "random_value_dropout":
            columns = variable_group_columns(config, str(operation.get("variable_group")), out)
            out, rows, cells = _random_value_dropout(
                out,
                columns=columns,
                rate=float(operation.get("rate", 0.0)),
                seed=effective_seed,
            )
            affected_rows += rows
            affected_cells += cells
        elif operation_type == "temporal_block_dropout":
            columns = variable_group_columns(config, str(operation.get("variable_group")), out)
            out, rows, cells = _temporal_block_dropout(
                out,
                columns=columns,
                block_length_months=int(operation.get("block_length_months", 1)),
                site_history_block_rate=float(operation.get("site_history_block_rate", 0.0)),
                seed=effective_seed,
            )
            affected_rows += rows
            affected_cells += cells
        else:
            raise ValueError(f"Unsupported degradation operation type: {operation_type}")
    return out.reset_index(drop=True), affected_rows, affected_cells


def _valid_arrays(group: pd.DataFrame, score_column: str, actual_column: str) -> tuple[np.ndarray, np.ndarray]:
    score = pd.to_numeric(group[score_column], errors="coerce")
    actual = pd.to_numeric(group[actual_column], errors="coerce")
    valid = score.notna() & actual.notna()
    return _clip01(score.loc[valid]), actual.loc[valid].astype("int8").to_numpy()


def _metric_dict(probability: np.ndarray, actual: np.ndarray, threshold: float) -> dict[str, Any]:
    probability = _clip01(probability)
    actual = actual.astype("int8")
    predicted = (probability >= threshold).astype("int8")
    tn = int(((predicted == 0) & (actual == 0)).sum())
    fp = int(((predicted == 1) & (actual == 0)).sum())
    fn = int(((predicted == 0) & (actual == 1)).sum())
    tp = int(((predicted == 1) & (actual == 1)).sum())
    positive_rows = int(actual.sum())
    negative_rows = int(len(actual) - positive_rows)
    has_both_classes = positive_rows > 0 and negative_rows > 0
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    specificity = _safe_rate(tn, tn + fp)
    balanced_accuracy = float(np.mean([recall, specificity])) if has_both_classes else float("nan")
    return {
        "rows": int(len(actual)),
        "positive_rows": positive_rows,
        "positive_rate": float(actual.mean()) if len(actual) else np.nan,
        "predicted_positive_rows": int(predicted.sum()),
        "alert_rate": float(predicted.mean()) if len(predicted) else np.nan,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": _safe_metric(f1_score, actual, predicted, zero_division=0),
        "f2": _f2_score(precision, recall),
        "mcc": _mcc(tn, fp, fn, tp),
        "balanced_accuracy": balanced_accuracy,
        "pr_auc": _safe_metric(average_precision_score, actual, probability) if has_both_classes else np.nan,
        "roc_auc": _safe_metric(roc_auc_score, actual, probability) if has_both_classes else np.nan,
        "brier": _safe_metric(brier_score_loss, actual, probability),
    }


def source_groups(frame: pd.DataFrame, include_all_sources: bool) -> list[tuple[str, pd.DataFrame]]:
    groups: list[tuple[str, pd.DataFrame]] = []
    if include_all_sources:
        groups.append(("all", frame))
    for source_id, group in frame.groupby("source_id", sort=True):
        groups.append((str(source_id), group))
    return groups


def build_metric_rows(
    frame: pd.DataFrame,
    thresholds: pd.DataFrame,
    scenario: dict[str, Any],
    *,
    seed: int | None,
    policies: list[str],
    splits: list[str],
    include_all_sources: bool,
    min_rows: int,
    score_recomputed: bool,
) -> pd.DataFrame:
    metric_rows: list[dict[str, Any]] = []
    threshold_rows = thresholds[thresholds["policy_name"].isin(policies)].copy()
    for threshold in dataframe_rows(threshold_rows):
        target_event = str(threshold.target_event)
        if target_event not in EVENT_SPECS:
            continue
        actual_column = EVENT_SPECS[target_event]["actual_column"]
        score_column = str(threshold.score_column)
        horizon = int(threshold.rollout_horizon_months)
        for split in splits:
            split_horizon = frame[(frame["split"] == split) & (frame["rollout_horizon_months"] == horizon)]
            if split_horizon.empty:
                continue
            for source_id, group in source_groups(split_horizon, include_all_sources):
                probability, actual = _valid_arrays(group, score_column, actual_column)
                if len(actual) < int(min_rows):
                    continue
                metrics = _metric_dict(probability, actual, threshold=float(threshold.selected_threshold))
                metric_rows.append(
                    {
                        "degradation_version": DEGRADATION_VERSION,
                        "scenario_id": str(scenario["scenario_id"]),
                        "scenario_family": str(scenario.get("family", "")),
                        "scenario_tier": str(scenario.get("tier", "")),
                        "scenario_status": "evaluated",
                        "seed": seed,
                        "split": split,
                        "rollout_horizon_months": horizon,
                        "source_id": source_id,
                        "target_event": target_event,
                        "alert_policy": str(threshold.policy_name),
                        "score_column": score_column,
                        "threshold": float(threshold.selected_threshold),
                        "score_recomputed": bool(score_recomputed),
                        **metrics,
                    }
                )
    if not metric_rows:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return pd.DataFrame(metric_rows)


def add_control_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    out = metrics.copy()
    key = ["split", "rollout_horizon_months", "source_id", "target_event", "alert_policy"]
    control = out[out["scenario_id"] == "control_observed"][key + ["rows", *METRIC_VALUE_COLUMNS]].copy()
    control = control.rename(columns={"rows": "control_rows", **{column: f"control_{column}" for column in METRIC_VALUE_COLUMNS}})
    out = out.merge(control, on=key, how="left", validate="many_to_one")
    out["control_rows"] = pd.to_numeric(out["control_rows"], errors="coerce")
    out["rows_retained_rate"] = out["rows"] / out["control_rows"]
    for column in METRIC_VALUE_COLUMNS:
        out[f"delta_{column}_vs_control"] = out[column] - out[f"control_{column}"]
    for column in [f"control_{column}" for column in METRIC_VALUE_COLUMNS]:
        out = out.drop(columns=column)
    return out[METRIC_COLUMNS].sort_values(
        ["scenario_id", "seed", "split", "rollout_horizon_months", "source_id", "target_event", "alert_policy"],
        na_position="first",
    )


def skipped_summary_row(
    scenario: dict[str, Any],
    *,
    seed: int | None,
    input_rows: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "degradation_version": DEGRADATION_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_family": str(scenario.get("family", "")),
        "scenario_tier": str(scenario.get("tier", "")),
        "scenario_status": "skipped_requires_model_recompute",
        "seed": seed,
        "reason": reason,
        "score_recomputed": False,
        "input_rows": int(input_rows),
        "output_rows": 0,
        "rows_retained_rate": np.nan,
        "affected_rows": 0,
        "affected_cells": 0,
        "metrics_rows": 0,
        "operation_types": ",".join(operation_types(scenario)),
    }


def build_scenario_outputs(
    rows: pd.DataFrame,
    thresholds: pd.DataFrame,
    config: dict[str, Any],
    scenarios: list[dict[str, Any]],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        needs_recompute = scenario_needs_recompute(scenario)
        if needs_recompute and not args.evaluate_passthrough_scores:
            summary_rows.append(
                skipped_summary_row(
                    scenario,
                    seed=None,
                    input_rows=len(rows),
                    reason="scenario changes predictor evidence and requires model score recomputation",
                )
            )
            continue
        for seed in seeds_for_scenario(scenario, config):
            degraded, affected_rows, affected_cells = apply_operations(rows, scenario, config, seed)
            score_recomputed = False
            metrics = build_metric_rows(
                degraded,
                thresholds,
                scenario,
                seed=seed,
                policies=args.policies,
                splits=args.evaluation_splits,
                include_all_sources=args.include_all_sources,
                min_rows=args.min_rows,
                score_recomputed=score_recomputed,
            )
            metric_parts.append(metrics)
            summary_rows.append(
                {
                    "degradation_version": DEGRADATION_VERSION,
                    "scenario_id": str(scenario["scenario_id"]),
                    "scenario_family": str(scenario.get("family", "")),
                    "scenario_tier": str(scenario.get("tier", "")),
                    "scenario_status": "evaluated" if not metrics.empty else "empty_after_degradation",
                    "seed": seed,
                    "reason": "" if not needs_recompute else "evaluated with passthrough precomputed scores",
                    "score_recomputed": bool(score_recomputed),
                    "input_rows": int(len(rows)),
                    "output_rows": int(len(degraded)),
                    "rows_retained_rate": _safe_rate(len(degraded), len(rows)),
                    "affected_rows": int(affected_rows),
                    "affected_cells": int(affected_cells),
                    "metrics_rows": int(len(metrics)),
                    "operation_types": ",".join(operation_types(scenario)),
                }
            )
    metrics = pd.concat(metric_parts, ignore_index=True) if metric_parts else pd.DataFrame(columns=METRIC_COLUMNS)
    metrics = add_control_deltas(metrics)
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    return metrics, summary


def write_report(args: argparse.Namespace, config: dict[str, Any], metrics: pd.DataFrame, summary: pd.DataFrame) -> None:
    default_policy = config.get("protocol", {}).get("default_alert_policy", {}).get("selection_objective", "closest_pr")
    lines = [
        "# Controlled Degradation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This report evaluates controlled-degradation scenarios on precomputed alert score rows.",
        "Scenarios that modify predictor evidence are skipped unless passthrough-score evaluation is explicitly enabled.",
        "",
        "## Configuration",
        "",
        f"- Config: `{args.config}`",
        f"- Scored rows: `{args.scored_rows}`",
        f"- Thresholds: `{args.thresholds}`",
        f"- Scenario set: `{args.scenario_set}`",
        f"- Output name: `{args.output_name}`",
        f"- Policies: `{args.policies}`",
        f"- Evaluation splits: `{args.evaluation_splits}`",
        f"- Default policy: `{default_policy}`",
        f"- Passthrough precomputed scores: `{args.evaluate_passthrough_scores}`",
        "",
        "## Scenario Summary",
        "",
        "| scenario | status | seed | output rows | retained | metrics rows | reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    if summary.empty:
        lines.append("| `NA` | `NA` | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(summary.sort_values(["scenario_id", "seed"], na_position="first")):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            reason = str(row.reason) if str(row.reason) else ""
            lines.append(
                f"| `{row.scenario_id}` | `{row.scenario_status}` | {seed} | "
                f"{_format_int(int(row.output_rows))} | {_format_float(row.rows_retained_rate)} | "
                f"{_format_int(int(row.metrics_rows))} | {reason} |"
            )
    lines.extend(
        [
            "",
            "## Default-Policy Test Metrics",
            "",
            "| scenario | seed | horizon | source | event | rows | recall | precision | alert rate | F2 | delta F2 |",
            "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    headline = metrics[
        (metrics["split"] == "test")
        & (metrics["alert_policy"] == str(default_policy))
        & (metrics["source_id"] == "all")
    ].copy() if not metrics.empty else pd.DataFrame()
    if headline.empty:
        lines.append("| `NA` | NA | NA | `NA` | `NA` | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(headline.sort_values(["scenario_id", "seed", "rollout_horizon_months", "target_event"])):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | {int(row.rollout_horizon_months)} | `{row.source_id}` | "
                f"`{row.target_event}` | {_format_int(int(row.rows))} | {_format_float(row.recall)} | "
                f"{_format_float(row.precision)} | {_format_float(row.alert_rate)} | {_format_float(row.f2)} | "
                f"{_format_float(row.delta_f2_vs_control)} |"
            )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Labels are not modified by this evaluator.",
            "- Source-scoped site identity is preserved.",
            "- Ranking metrics are reported as NA for groups with only one observed class.",
            "- Predictor-degradation scenarios require model recomputation for scientific performance claims.",
            "- Degraded outputs are stress-test evidence, not official environmental alerts.",
            "",
            "## Outputs",
            "",
            f"- Metrics: `{args.metrics}`",
            f"- Summary: `{args.summary}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    args: argparse.Namespace,
    config: dict[str, Any],
    rows: pd.DataFrame,
    thresholds: pd.DataFrame,
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
) -> dict[str, Any]:
    outputs = [args.metrics, args.summary, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "degradation_version": DEGRADATION_VERSION,
        "config": {
            "scenario_set": args.scenario_set,
            "scenarios": args.scenarios,
            "output_name": args.output_name,
            "output_dir": args.output_dir,
            "policies": args.policies,
            "evaluation_splits": args.evaluation_splits,
            "include_all_sources": bool(args.include_all_sources),
            "evaluate_passthrough_scores": bool(args.evaluate_passthrough_scores),
            "min_rows": int(args.min_rows),
            "default_alert_policy": config.get("protocol", {}).get("default_alert_policy", {}),
        },
        "row_counts": {
            "input_rows": int(len(rows)),
            "threshold_rows": int(len(thresholds)),
            "metric_rows": int(len(metrics)),
            "summary_rows": int(len(summary)),
            "evaluated_runs": int((summary["scenario_status"] == "evaluated").sum()) if not summary.empty else 0,
            "skipped_runs": int(summary["scenario_status"].astype(str).str.startswith("skipped").sum()) if not summary.empty else 0,
            "evaluated_scenarios": int(summary.loc[summary["scenario_status"] == "evaluated", "scenario_id"].nunique())
            if not summary.empty
            else 0,
            "skipped_scenarios": int(summary.loc[summary["scenario_status"].astype(str).str.startswith("skipped"), "scenario_id"].nunique())
            if not summary.empty
            else 0,
        },
        "inputs": [_file_record(args.config), _file_record(args.scored_rows), _file_record(args.thresholds)],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scored-rows", type=Path, default=DEFAULT_SCORED_ROWS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--metrics", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--output-name",
        type=_safe_output_name,
        default=None,
        help="Write named outputs without overriding the default smoke artifacts.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--scenario-set", default="smoke")
    parser.add_argument("--scenarios", type=_parse_csv_list, default=None)
    parser.add_argument("--policies", type=_parse_csv_list, default=None)
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default=None)
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--include-all-sources", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--evaluate-passthrough-scores",
        action="store_true",
        help="Evaluate precomputed scores even for predictor-degradation scenarios; for diagnostics only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = read_config(args.config)
    validate_scenarios(config)
    args.metrics = default_output(
        args.metrics,
        config,
        "metrics",
        DEFAULT_METRICS,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.summary = default_output(
        args.summary,
        config,
        "summary",
        DEFAULT_SUMMARY,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.report = default_output(
        args.report,
        config,
        "report",
        DEFAULT_REPORT,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.manifest = default_output(
        args.manifest,
        config,
        "manifest",
        DEFAULT_MANIFEST,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    if args.min_rows < 1:
        raise ValueError("--min-rows must be >= 1")
    if args.evaluation_splits is None:
        args.evaluation_splits = [str(split) for split in config.get("evaluation", {}).get("splits", ["validation", "test"])]
    args.policies = threshold_policies(config, args)
    scenarios = select_scenarios(config, args)

    rows_raw = _read_table(args.scored_rows)
    thresholds = pd.read_csv(args.thresholds)
    rows = prepare_rows(rows_raw, thresholds, args.policies)
    metrics, summary = build_scenario_outputs(rows, thresholds, config, scenarios, args)

    _write_csv_atomic(metrics, args.metrics)
    _write_csv_atomic(summary, args.summary)
    write_report(args, config, metrics, summary)
    _write_json_atomic(manifest_payload(args, config, rows, thresholds, metrics, summary), args.manifest)
    print(f"wrote {args.metrics}", flush=True)
    print(f"wrote {args.summary}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
