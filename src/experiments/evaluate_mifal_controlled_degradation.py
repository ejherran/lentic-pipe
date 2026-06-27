#!/usr/bin/env python
"""Evaluate MIFAL-ED/T2 under controlled raw-observation degradation."""

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

from src.experiments.evaluate_controlled_degradation import read_config, seeds_for_scenario, select_scenarios, validate_scenarios
from src.experiments.evaluate_mifal_observable import load_surface, run_predictions
from src.mifal.ed_t2 import interval_coverage, winkler_interval_score
from src.mifal.panel_adapter import MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA, MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA, MIFAL_SURFACES
from src.pandas_utils import dataframe_rows


MIFAL_DEGRADATION_VERSION = "mifal_controlled_degradation_v0"
DEFAULT_CONFIG = Path("configs/degradation_scenarios.yaml")
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_REFERENCE_ROWS = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet")
DEFAULT_THRESHOLDS = Path("reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_calibration_thresholds.csv")
DEFAULT_REPORT_DIR = Path("reports/degradation")
DEFAULT_OUTPUT_NAME = "mifal_controlled_degradation_smoke"
OUTPUT_SUFFIXES = {
    "metrics": "metrics.csv",
    "summary": "summary.csv",
    "availability": "availability.csv",
    "examples": "examples.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
METRIC_VALUE_COLUMNS = [
    "positive_rate",
    "mean_probability",
    "alert_rate",
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
    "calibration_bias",
    "absolute_calibration_bias",
    "interval_coverage_risk",
    "interval_mean_width",
    "winkler_score_risk",
    "mean_uncertainty",
    "mean_data_reliability",
    "mean_confidence",
    "mean_observation_reliability",
]
METRIC_COLUMNS = [
    "mifal_degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "surface",
    "split",
    "horizon_months",
    "source_id",
    "target_event",
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
    "mean_probability",
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
    "calibration_bias",
    "absolute_calibration_bias",
    "interval_coverage_risk",
    "interval_mean_width",
    "winkler_score_risk",
    "mean_uncertainty",
    "mean_data_reliability",
    "mean_confidence",
    "mean_observation_reliability",
    *[f"delta_{column}_vs_control" for column in METRIC_VALUE_COLUMNS],
]
SUMMARY_COLUMNS = [
    "mifal_degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "surface",
    "input_rows",
    "output_rows",
    "rows_retained_rate",
    "affected_rows",
    "affected_cells",
    "metrics_rows",
    "operation_types",
]
AVAILABILITY_COLUMNS = [
    "mifal_degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "seed",
    "surface",
    "split",
    "horizon_months",
    "mifal_variable",
    "rows",
    "present_rows",
    "coverage_rate",
]


@dataclass(frozen=True)
class JsonCalibrator:
    horizon: int
    path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class ObservationPacket:
    variable: str
    columns: tuple[str, ...]


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


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def _parse_int_csv(value: str) -> list[int]:
    try:
        return [int(item) for item in _parse_csv_list(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected comma-separated integers") from exc


def _optional_path(value: str) -> Path | None:
    normalized = value.strip()
    if normalized.lower() in {"", "none", "null"}:
        return None
    return Path(normalized)


def _surface(value: str) -> str:
    if value not in MIFAL_SURFACES:
        raise argparse.ArgumentTypeError(f"Expected one of {', '.join(MIFAL_SURFACES)}")
    return value


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _safe_rate(numerator: float, denominator: float) -> float:
    return float("nan") if denominator == 0.0 else float(numerator / denominator)


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


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


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {key: output_dir / f"{output_name}_{suffix}" for key, suffix in OUTPUT_SUFFIXES.items()}


def operation_types(scenario: dict[str, Any]) -> list[str]:
    return [str(operation.get("type")) for operation in scenario.get("operations", [])]


def _existing(columns: list[str], frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(column for column in columns if column in frame.columns)


def _packet(variable: str, stem: str, frame: pd.DataFrame) -> ObservationPacket | None:
    columns = _existing([f"mean_{stem}", f"n_obs_{stem}", f"qc_ok_rate_{stem}", f"std_{stem}"], frame)
    if not columns:
        return None
    return ObservationPacket(variable=variable, columns=columns)


def _previous_chla_packet(frame: pd.DataFrame) -> ObservationPacket | None:
    columns = _existing(
        [
            "prev_mean_chlorophyll_a_ugL",
            "prev_n_obs_chlorophyll_a_ugL",
            "prev_qc_ok_rate_chlorophyll_a_ugL",
            "prev_std_chlorophyll_a_ugL",
        ],
        frame,
    )
    if not columns:
        return None
    return ObservationPacket(variable="Chl_prev", columns=columns)


def mifal_observation_packets(frame: pd.DataFrame, surface: str) -> dict[str, list[ObservationPacket]]:
    current_chla = _packet("Chl", "chlorophyll_a_ugL", frame)
    previous_chla = _previous_chla_packet(frame)
    chlorophyll_memory = [packet for packet in [previous_chla] if packet is not None]
    if surface == MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA and current_chla is not None:
        chlorophyll_memory.insert(0, current_chla)

    nutrient_packets = [packet for packet in [_packet("TP", "TP_ugL", frame), _packet("TN", "TN_ugL", frame)] if packet is not None]
    light_packets = [
        packet
        for packet in [_packet("Secchi", "secchi_depth_m", frame), _packet("Turb", "turbidity_NTU", frame)]
        if packet is not None
    ]
    physicochemical_packets = [
        packet
        for packet in [_packet("Tw", "temperature_C", frame), _packet("DOb", "DO_mgL", frame), _packet("pH", "pH", frame)]
        if packet is not None
    ]
    all_core = [*chlorophyll_memory, *nutrient_packets, *light_packets, *physicochemical_packets]
    return {
        "chlorophyll_memory": chlorophyll_memory,
        "nutrients": nutrient_packets,
        "light": light_packets,
        "physicochemical": physicochemical_packets,
        "all_core_predictors": all_core,
    }


def packets_for_group(frame: pd.DataFrame, surface: str, group_name: str) -> list[ObservationPacket]:
    packets = mifal_observation_packets(frame, surface).get(group_name)
    if packets is None:
        raise ValueError(f"Unsupported MIFAL degradation variable group: {group_name}")
    return packets


def _set_packets_missing(frame: pd.DataFrame, packets: list[ObservationPacket]) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    columns = sorted({column for packet in packets for column in packet.columns})
    if not columns:
        return out, 0, 0
    before = out[columns].notna()
    for column in columns:
        out[column] = out[column].astype("float64")
    out.loc[:, columns] = np.nan
    return out, int(before.any(axis=1).sum()), int(before.sum().sum())


def _random_packet_dropout(frame: pd.DataFrame, *, packets: list[ObservationPacket], rate: float, seed: int) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not packets or rate <= 0.0:
        return out, 0, 0
    rng = np.random.default_rng(seed)
    affected_rows_mask = pd.Series(False, index=out.index)
    affected_cells = 0
    for packet in packets:
        columns = [column for column in packet.columns if column in out.columns]
        if not columns:
            continue
        eligible = out[columns].notna().any(axis=1).to_numpy()
        drop = (rng.random(len(out)) < float(rate)) & eligible
        if not drop.any():
            continue
        before = out.loc[drop, columns].notna()
        for column in columns:
            out[column] = out[column].astype("float64")
        out.loc[drop, columns] = np.nan
        affected_rows_mask.loc[out.index[drop]] = True
        affected_cells += int(before.sum().sum())
    return out, int(affected_rows_mask.sum()), affected_cells


def _temporal_packet_dropout(
    frame: pd.DataFrame,
    *,
    packets: list[ObservationPacket],
    block_length_months: int,
    site_history_block_rate: float,
    seed: int,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    columns = sorted({column for packet in packets for column in packet.columns if column in out.columns})
    if not columns or block_length_months <= 0 or site_history_block_rate <= 0.0:
        return out, 0, 0
    rng = np.random.default_rng(seed)
    affected_mask = pd.Series(False, index=out.index)
    for _, group in out.groupby(["source_id", "split", "site_id"], sort=True):
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
    for column in columns:
        out[column] = out[column].astype("float64")
    out.loc[affected_mask, columns] = np.nan
    return out, int(before.any(axis=1).sum()), int(before.sum().sum())


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
    if retain_fraction >= 1.0:
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
        retained.append(
            frame[
                (frame["source_id"] == group["source_id"].iloc[0])
                & (frame["split"] == group["split"].iloc[0])
                & (frame["site_id"].isin(keep_sites))
            ]
        )
    if not retained:
        return frame.iloc[0:0].copy()
    return pd.concat(retained, ignore_index=False).sort_index().copy()


def apply_operations(
    frame: pd.DataFrame,
    scenario: dict[str, Any],
    *,
    config: dict[str, Any],
    surface: str,
    seed: int | None,
) -> tuple[pd.DataFrame, int, int]:
    del config
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
            packets = packets_for_group(out, surface, str(operation.get("variable_group")))
            out, rows, cells = _set_packets_missing(out, packets)
            affected_rows += rows
            affected_cells += cells
        elif operation_type == "random_value_dropout":
            packets = packets_for_group(out, surface, str(operation.get("variable_group")))
            out, rows, cells = _random_packet_dropout(out, packets=packets, rate=float(operation.get("rate", 0.0)), seed=effective_seed)
            affected_rows += rows
            affected_cells += cells
        elif operation_type == "temporal_block_dropout":
            packets = packets_for_group(out, surface, str(operation.get("variable_group")))
            out, rows, cells = _temporal_packet_dropout(
                out,
                packets=packets,
                block_length_months=int(operation.get("block_length_months", 1)),
                site_history_block_rate=float(operation.get("site_history_block_rate", 0.0)),
                seed=effective_seed,
            )
            affected_rows += rows
            affected_cells += cells
        else:
            raise ValueError(f"Unsupported MIFAL degradation operation type: {operation_type}")
    return out.reset_index(drop=True), affected_rows, affected_cells


def load_calibrators(thresholds: pd.DataFrame) -> dict[int, JsonCalibrator]:
    calibrators: dict[int, JsonCalibrator] = {}
    for row in dataframe_rows(thresholds.sort_values("horizon_months")):
        path = Path(str(row.calibrator_path))
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        horizon = int(row.horizon_months)
        calibrators[horizon] = JsonCalibrator(horizon=horizon, path=path, payload=payload)
    return calibrators


def _apply_json_calibrator(scores: pd.Series, payload: dict[str, Any]) -> np.ndarray:
    values = _clip01(scores)
    if str(payload["method"]).startswith("constant"):
        return np.full(values.shape, float(payload["probability"]), dtype="float64")
    x_thresholds = np.asarray(payload["x_thresholds"], dtype="float64")
    y_thresholds = np.asarray(payload["y_thresholds"], dtype="float64")
    return np.interp(values, x_thresholds, y_thresholds, left=y_thresholds[0], right=y_thresholds[-1])


def apply_calibrators(predictions: pd.DataFrame, calibrators: dict[int, JsonCalibrator]) -> pd.DataFrame:
    out = predictions.copy()
    out["mifal_probability_bloom_calibrated"] = np.nan
    for horizon, calibrator in calibrators.items():
        mask = out["horizon_months"] == int(horizon)
        out.loc[mask, "mifal_probability_bloom_calibrated"] = _apply_json_calibrator(out.loc[mask, "risk_conservative"], calibrator.payload)
    out["mifal_probability_bloom_calibrated"] = out["mifal_probability_bloom_calibrated"].clip(0.0, 1.0)
    return out


def apply_thresholds(predictions: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    out = predictions.copy()
    out["mifal_bloom_probability_threshold"] = np.nan
    out["mifal_predicted_bloom_h"] = pd.NA
    for row in dataframe_rows(thresholds.sort_values("horizon_months")):
        mask = out["horizon_months"] == int(row.horizon_months)
        threshold = float(row.selected_threshold)
        out.loc[mask, "mifal_bloom_probability_threshold"] = threshold
        out.loc[mask, "mifal_predicted_bloom_h"] = (
            out.loc[mask, "mifal_probability_bloom_calibrated"].astype("float64") >= threshold
        ).astype("int8")
    return out


def _source_groups(frame: pd.DataFrame, include_all_sources: bool) -> list[tuple[str, pd.DataFrame]]:
    groups: list[tuple[str, pd.DataFrame]] = []
    if include_all_sources:
        groups.append(("all", frame))
    for source_id, group in frame.groupby("source_id", sort=True):
        groups.append((str(source_id), group))
    return groups


def _metric_row(
    group: pd.DataFrame,
    *,
    threshold: float,
    scenario: dict[str, Any],
    seed: int | None,
    surface: str,
    split: str,
    horizon: int,
    source_id: str,
    beta: float,
) -> dict[str, Any]:
    score = group["mifal_probability_bloom_calibrated"].to_numpy(dtype="float64")
    actual = group["bloom_h"].to_numpy(dtype="int8")
    predicted = (score >= threshold).astype("int8")
    tn, fp, fn, tp = confusion_matrix(actual, predicted, labels=[0, 1]).ravel()
    positive_rows = int(actual.sum())
    negative_rows = int(len(actual) - positive_rows)
    has_both_classes = positive_rows > 0 and negative_rows > 0
    precision = _safe_metric(precision_score, actual, predicted, zero_division=0)
    recall = _safe_metric(recall_score, actual, predicted, zero_division=0)
    specificity = _safe_rate(tn, tn + fp)
    target_risk = group["target_risk_chla_h"].to_numpy(dtype="float64")
    intervals = list(zip(group["risk_interval_lo"].astype(float), group["risk_interval_hi"].astype(float), strict=True))
    mean_probability = float(np.mean(score)) if len(score) else float("nan")
    positive_rate = float(actual.mean()) if len(actual) else float("nan")
    calibration_bias = mean_probability - positive_rate
    return {
        "mifal_degradation_version": MIFAL_DEGRADATION_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_family": str(scenario.get("family", "")),
        "scenario_tier": str(scenario.get("tier", "")),
        "scenario_status": "evaluated",
        "seed": seed,
        "surface": surface,
        "split": split,
        "horizon_months": int(horizon),
        "source_id": source_id,
        "target_event": "bloom_h",
        "score_column": "mifal_probability_bloom_calibrated",
        "threshold": float(threshold),
        "score_recomputed": True,
        "rows": int(len(group)),
        "control_rows": np.nan,
        "rows_retained_rate": np.nan,
        "positive_rows": positive_rows,
        "positive_rate": positive_rate,
        "predicted_positive_rows": int(predicted.sum()),
        "alert_rate": float(predicted.mean()) if len(predicted) else float("nan"),
        "mean_probability": mean_probability,
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
        "pr_auc": _safe_metric(average_precision_score, actual, score) if has_both_classes else np.nan,
        "roc_auc": _safe_metric(roc_auc_score, actual, score) if has_both_classes else np.nan,
        "brier": _safe_metric(brier_score_loss, actual, score),
        "rmse_risk": _root_mean_squared_error(target_risk, score),
        "mae_risk": float(np.mean(np.abs(target_risk - score))),
        "calibration_bias": calibration_bias,
        "absolute_calibration_bias": abs(calibration_bias),
        "interval_coverage_risk": interval_coverage(list(target_risk), intervals),
        "interval_mean_width": float((group["risk_interval_hi"] - group["risk_interval_lo"]).mean()),
        "winkler_score_risk": float(
            np.mean([winkler_interval_score(y_value, interval) for y_value, interval in zip(target_risk, intervals, strict=True)])
        ),
        "mean_uncertainty": float(group["uncertainty"].mean()),
        "mean_data_reliability": float(group["data_reliability"].mean()),
        "mean_confidence": float(group["confidence"].mean()),
        "mean_observation_reliability": float(group["observation_reliability"].mean()),
    }


def build_metrics(
    predictions: pd.DataFrame,
    thresholds: pd.DataFrame,
    *,
    scenario: dict[str, Any],
    seed: int | None,
    surface: str,
    evaluation_splits: list[str],
    include_all_sources: bool,
    min_rows: int,
    beta: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for threshold_row in dataframe_rows(thresholds.sort_values("horizon_months")):
        horizon = int(threshold_row.horizon_months)
        threshold = float(threshold_row.selected_threshold)
        for split in evaluation_splits:
            split_horizon = predictions[
                (predictions["split"] == split)
                & (predictions["horizon_months"] == horizon)
                & predictions["mifal_probability_bloom_calibrated"].notna()
                & predictions["bloom_h"].notna()
            ]
            if split_horizon.empty:
                continue
            for source_id, group in _source_groups(split_horizon, include_all_sources):
                if len(group) < int(min_rows):
                    continue
                rows.append(
                    _metric_row(
                        group,
                        threshold=threshold,
                        scenario=scenario,
                        seed=seed,
                        surface=surface,
                        split=split,
                        horizon=horizon,
                        source_id=source_id,
                        beta=beta,
                    )
                )
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=METRIC_COLUMNS)


def add_control_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    out = metrics.copy()
    out = out.drop(columns=[column for column in ["control_rows", "rows_retained_rate"] if column in out.columns])
    key = ["surface", "split", "horizon_months", "source_id", "target_event"]
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
        ["scenario_id", "seed", "surface", "split", "horizon_months", "source_id", "target_event"],
        na_position="first",
    )


def summarize_availability(
    predictions: pd.DataFrame,
    *,
    scenario: dict[str, Any],
    seed: int | None,
    surface: str,
    evaluation_splits: list[str],
) -> pd.DataFrame:
    variables = ["Tw", "TP", "TN", "Secchi", "Turb", "DOb", "Chl", "Chl_prev"]
    rows: list[dict[str, Any]] = []
    frame = predictions[predictions["split"].isin(evaluation_splits)].copy()
    for (split, horizon), group in frame.groupby(["split", "horizon_months"], sort=True):
        for variable in variables:
            column = f"has_{variable}"
            present = int(group[column].sum()) if column in group else 0
            rows.append(
                {
                    "mifal_degradation_version": MIFAL_DEGRADATION_VERSION,
                    "scenario_id": str(scenario["scenario_id"]),
                    "scenario_family": str(scenario.get("family", "")),
                    "scenario_tier": str(scenario.get("tier", "")),
                    "seed": seed,
                    "surface": surface,
                    "split": split,
                    "horizon_months": int(horizon),
                    "mifal_variable": variable,
                    "rows": int(len(group)),
                    "present_rows": present,
                    "coverage_rate": float(present / len(group)) if len(group) else float("nan"),
                }
            )
    return pd.DataFrame(rows, columns=AVAILABILITY_COLUMNS)


def select_examples(predictions: pd.DataFrame, scenario: dict[str, Any], seed: int | None, max_examples: int) -> pd.DataFrame:
    if predictions.empty or max_examples <= 0:
        return pd.DataFrame()
    columns = [
        "surface",
        "source_id",
        "site_id",
        "origin_year_month",
        "horizon_months",
        "split",
        "bloom_h",
        "target_risk_chla_h",
        "risk_conservative",
        "mifal_probability_bloom_calibrated",
        "mifal_bloom_probability_threshold",
        "mifal_predicted_bloom_h",
        "uncertainty",
        "data_reliability",
        "confidence",
        "payload_variables",
    ]
    out = predictions.sort_values(["uncertainty", "risk_conservative"], ascending=[False, False]).head(max_examples).copy()
    out.insert(0, "seed", seed)
    out.insert(0, "scenario_id", str(scenario["scenario_id"]))
    return out[[column for column in ["scenario_id", "seed", *columns] if column in out.columns]].reset_index(drop=True)


def run_scenarios(
    surface_frame: pd.DataFrame,
    scenarios: list[dict[str, Any]],
    config: dict[str, Any],
    thresholds: pd.DataFrame,
    calibrators: dict[int, JsonCalibrator],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_parts: list[pd.DataFrame] = []
    availability_parts: list[pd.DataFrame] = []
    example_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    prediction_args = argparse.Namespace(surface=args.surface, include_voi=args.include_voi)
    for scenario in scenarios:
        for seed in seeds_for_scenario(scenario, config):
            degraded, affected_rows, affected_cells = apply_operations(surface_frame, scenario, config=config, surface=args.surface, seed=seed)
            predictions = run_predictions(degraded, prediction_args)
            predictions = apply_calibrators(predictions, calibrators)
            predictions = apply_thresholds(predictions, thresholds)
            metrics = build_metrics(
                predictions,
                thresholds,
                scenario=scenario,
                seed=seed,
                surface=args.surface,
                evaluation_splits=args.evaluation_splits,
                include_all_sources=args.include_all_sources,
                min_rows=args.min_rows,
                beta=args.fbeta_beta,
            )
            availability = summarize_availability(predictions, scenario=scenario, seed=seed, surface=args.surface, evaluation_splits=args.evaluation_splits)
            examples = select_examples(predictions, scenario, seed, args.max_examples_per_run)
            metric_parts.append(metrics)
            availability_parts.append(availability)
            example_parts.append(examples)
            summary_rows.append(
                {
                    "mifal_degradation_version": MIFAL_DEGRADATION_VERSION,
                    "scenario_id": str(scenario["scenario_id"]),
                    "scenario_family": str(scenario.get("family", "")),
                    "scenario_tier": str(scenario.get("tier", "")),
                    "scenario_status": "evaluated" if not metrics.empty else "empty_after_degradation",
                    "seed": seed,
                    "surface": args.surface,
                    "input_rows": int(len(surface_frame)),
                    "output_rows": int(len(degraded)),
                    "rows_retained_rate": _safe_rate(len(degraded), len(surface_frame)),
                    "affected_rows": int(affected_rows),
                    "affected_cells": int(affected_cells),
                    "metrics_rows": int(len(metrics)),
                    "operation_types": ",".join(operation_types(scenario)),
                }
            )
    metrics = pd.concat(metric_parts, ignore_index=True) if metric_parts else pd.DataFrame(columns=METRIC_COLUMNS)
    metrics = add_control_deltas(metrics)
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    availability = pd.concat(availability_parts, ignore_index=True) if availability_parts else pd.DataFrame(columns=AVAILABILITY_COLUMNS)
    examples = pd.concat(example_parts, ignore_index=True) if example_parts else pd.DataFrame()
    return metrics, summary, availability, examples


def write_report(args: argparse.Namespace, metrics: pd.DataFrame, summary: pd.DataFrame, availability: pd.DataFrame) -> None:
    lines = [
        "# MIFAL Controlled Degradation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This report recomputes MIFAL-ED/T2 after controlled degradation of observable panel evidence.",
        "Labels, temporal splits, calibrators, and thresholds remain fixed.",
        "",
        "## Configuration",
        "",
        f"- Config: `{args.config}`",
        f"- Surface: `{args.surface}`",
        f"- Panel: `{args.panel}`",
        f"- Splits: `{args.splits}`",
        f"- Reference rows: `{args.reference_rows}`",
        f"- Thresholds: `{args.thresholds}`",
        f"- Scenario set: `{args.scenario_set}`",
        f"- Output name: `{args.output_name}`",
        f"- Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        f"- Include VOI: `{bool(args.include_voi)}`",
        "",
        "## Scenario Summary",
        "",
        "| scenario | seed | rows | retained | affected rows | affected cells | metrics rows |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    if summary.empty:
        lines.append("| `NA` | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(summary.sort_values(["scenario_id", "seed"], na_position="first")):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | {_format_int(int(row.output_rows))} | "
                f"{_format_float(float(row.rows_retained_rate))} | {_format_int(int(row.affected_rows))} | "
                f"{_format_int(int(row.affected_cells))} | {_format_int(int(row.metrics_rows))} |"
            )
    lines.extend(
        [
            "",
            "## Test Metrics",
            "",
            "| scenario | seed | horizon | source | rows | PR-AUC | Brier | F-beta | delta F-beta | interval width | confidence | calibration bias |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    headline = metrics[(metrics["split"] == "test") & (metrics["source_id"] == "all")].copy() if not metrics.empty else pd.DataFrame()
    if headline.empty:
        lines.append("| `NA` | NA | NA | `NA` | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(headline.sort_values(["scenario_id", "seed", "horizon_months"])):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | {int(row.horizon_months)} | `{row.source_id}` | "
                f"{_format_int(int(row.rows))} | {_format_float(float(row.pr_auc))} | {_format_float(float(row.brier))} | "
                f"{_format_float(float(row.fbeta))} | {_format_float(float(row.delta_fbeta_vs_control))} | "
                f"{_format_float(float(row.interval_mean_width))} | {_format_float(float(row.mean_confidence))} | "
                f"{_format_float(float(row.calibration_bias))} |"
            )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- This is a stress test, not an official environmental alert.",
            "- Calibration and threshold selection are not repeated under degraded evidence.",
            "- Better interval coverage with poor discrimination is a partial result, not a win.",
            "- MIFAL is evaluated only for `bloom_h`; it does not emit `irc_alert`.",
            "",
            "## Outputs",
            "",
        ]
    )
    paths = output_paths(args.output_dir, args.output_name)
    lines.extend(
        [
            f"- Metrics: `{paths['metrics'].as_posix()}`",
            f"- Summary: `{paths['summary'].as_posix()}`",
            f"- Availability: `{paths['availability'].as_posix()}`",
            f"- Examples: `{paths['examples'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(
    args: argparse.Namespace,
    surface_frame: pd.DataFrame,
    thresholds: pd.DataFrame,
    calibrators: dict[int, JsonCalibrator],
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    availability: pd.DataFrame,
    examples: pd.DataFrame,
    started_at: datetime,
) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    return {
        "status": "completed",
        "mifal_degradation_version": MIFAL_DEGRADATION_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "config": args.config.as_posix(),
            "panel": args.panel.as_posix(),
            "splits": args.splits.as_posix(),
            "reference_rows": args.reference_rows.as_posix() if args.reference_rows else None,
            "thresholds": args.thresholds.as_posix(),
            "surface": args.surface,
            "scenario_set": args.scenario_set,
            "scenarios": args.scenarios,
            "horizons": args.horizons,
            "evaluation_splits": args.evaluation_splits,
            "max_rows_per_split": args.max_rows_per_split,
            "random_seed": int(args.random_seed),
            "include_all_sources": bool(args.include_all_sources),
            "include_voi": bool(args.include_voi),
            "min_rows": int(args.min_rows),
            "fbeta_beta": float(args.fbeta_beta),
            "output_name": args.output_name,
        },
        "row_counts": {
            "surface_rows": int(len(surface_frame)),
            "threshold_rows": int(len(thresholds)),
            "calibrator_rows": int(len(calibrators)),
            "metric_rows": int(len(metrics)),
            "summary_rows": int(len(summary)),
            "availability_rows": int(len(availability)),
            "example_rows": int(len(examples)),
        },
        "inputs": [
            _file_record(args.config),
            _file_record(args.panel),
            _file_record(args.splits),
            *([_file_record(args.reference_rows)] if args.reference_rows else []),
            _file_record(args.thresholds),
            *[_file_record(calibrator.path) for calibrator in calibrators.values()],
        ],
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--reference-rows", type=_optional_path, default=DEFAULT_REFERENCE_ROWS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--surface", type=_surface, default=MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA)
    parser.add_argument("--scenario-set", default="mifal_observable_smoke")
    parser.add_argument("--scenarios", type=_parse_csv_list, default=None)
    parser.add_argument("--horizons", type=_parse_int_csv, default="1,2,3")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="validation,test")
    parser.add_argument("--max-rows-per-split", type=int, default=100)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--include-all-sources", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-voi", action="store_true")
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--fbeta-beta", type=float, default=2.0)
    parser.add_argument("--max-examples-per-run", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.min_rows < 1:
        raise ValueError("--min-rows must be >= 1")
    started_at = datetime.now(timezone.utc)
    config = read_config(args.config)
    validate_scenarios(config)
    scenarios = select_scenarios(config, args)
    thresholds = pd.read_csv(args.thresholds)
    thresholds = thresholds[thresholds["surface"] == args.surface].copy()
    if thresholds.empty:
        raise ValueError(f"No MIFAL threshold rows found for surface {args.surface!r}")
    calibrators = load_calibrators(thresholds)
    surface_args = argparse.Namespace(
        panel=args.panel,
        splits=args.splits,
        reference_rows=args.reference_rows,
        surface=args.surface,
        horizons=args.horizons,
        evaluation_splits=args.evaluation_splits,
        max_rows_per_split=args.max_rows_per_split,
        random_seed=args.random_seed,
    )
    print(f"loading MIFAL degradation surface from {args.splits} and {args.panel}", flush=True)
    surface_frame = load_surface(surface_args)
    print(f"running {len(scenarios):,} scenario definitions on {len(surface_frame):,} rows", flush=True)
    metrics, summary, availability, examples = run_scenarios(surface_frame, scenarios, config, thresholds, calibrators, args)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(summary, paths["summary"])
    _write_csv_atomic(availability, paths["availability"])
    _write_csv_atomic(examples, paths["examples"])
    write_report(args, metrics, summary, availability)
    manifest = manifest_payload(args, surface_frame, thresholds, calibrators, metrics, summary, availability, examples, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"MIFAL degradation report written: {paths['report']}", flush=True)
    print(f"MIFAL degradation manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
