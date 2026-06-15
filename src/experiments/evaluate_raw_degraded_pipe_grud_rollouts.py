#!/usr/bin/env python
"""Evaluate PIPE/GRU-D rollouts after raw-predictor degradation and fuzzy rebuild."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.experiments.build_expert_fuzzy import DEFAULT_MANIFEST as DEFAULT_FUZZY_MANIFEST
from src.experiments.build_expert_fuzzy import DEFAULT_PANEL
from src.experiments.build_pipe_sequences import (
    INPUT_SURFACE_FULL,
    INPUT_SURFACE_NO_CURRENT_CHLA,
    INPUT_COLUMNS,
    _parse_source_ids,
    build_sequence_candidates,
    filter_state_sources,
    filter_leakage_safe_sequences,
)
from src.experiments.calibrate_pipe_rollout_alerts import apply_bloom_calibrators
from src.experiments.evaluate_controlled_degradation import (
    _parse_csv_list,
    _safe_output_name,
    add_control_deltas,
    build_metric_rows,
    operation_types,
    prepare_rows,
    read_config,
    seeds_for_scenario,
    select_scenarios,
    threshold_policies,
    validate_scenarios,
)
from src.experiments.evaluate_degraded_pipe_grud_rollouts import (
    DEFAULT_THRESHOLDS,
    changed_counts,
    load_rollout_bloom_calibrators,
    selected_window_indices,
)
from src.experiments.evaluate_pipe_grud_rollouts import (
    DEFAULT_SPLITS,
    attach_observations,
    build_alert_metrics,
    build_examples,
    build_state_metrics,
    compact_backtest_rows,
    load_bloom_targets,
    observed_state_frame,
    select_backtest_indices,
    write_table_atomic,
)
from src.experiments.rollout_pipe_grud import (
    DEFAULT_FUZZY_CALIBRATORS_DIR,
    DEFAULT_MODEL,
    DEFAULT_MODEL_MANIFEST,
    DEFAULT_SEQUENCES,
    ROLLOUT_VERSION,
    build_rollouts,
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
    ID_COLUMNS,
    MODEL_VERSION as PIPE_MODEL_VERSION,
    load_sequences,
    prepare_window_frame,
    _require_torch,
)
from src.fuzzy.expert import DEFAULT_IRC_WEIGHTS, build_expert_state
from src.pandas_utils import dataframe_rows


DEGRADATION_VERSION = "pipe_grud_raw_predictor_recomputed_degradation_v0"
DEFAULT_CONFIG = Path("configs/degradation_scenarios.yaml")
DEFAULT_REPORT_DIR = Path("reports/degradation")
DEFAULT_STATE_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_state_metrics.csv"
DEFAULT_ALERT_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_alert_metrics.csv"
DEFAULT_POLICY_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_policy_metrics.csv"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_summary.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_examples.csv"
DEFAULT_DIAGNOSTICS = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_diagnostics.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "controlled_degradation_raw_predictor_recomputed_manifest.json"
OUTPUT_SUFFIXES = {
    "state_metrics": "state_metrics.csv",
    "alert_metrics": "alert_metrics.csv",
    "policy_metrics": "policy_metrics.csv",
    "summary": "summary.csv",
    "examples": "examples.csv",
    "diagnostics": "diagnostics.csv",
    "report": "report.md",
    "manifest": "manifest.json",
    "backtest_rows": "backtest_rows.parquet",
}
SUPPORTED_OPERATIONS = {
    "set_variables_missing",
    "random_value_dropout",
    "temporal_block_dropout",
}
SCENARIO_COLUMNS = [
    "degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "score_recomputed",
    "fuzzy_state_rebuilt",
    "labels_preserved",
]
SUMMARY_COLUMNS = [
    *SCENARIO_COLUMNS,
    "reason",
    "selected_origins",
    "evaluated_rollout_rows",
    "state_metric_rows",
    "alert_metric_rows",
    "policy_metric_rows",
    "example_rows",
    "backtest_row_rows",
    "raw_panel_rows",
    "rebuilt_state_rows",
    "rebuilt_sequence_rows",
    "raw_affected_rows",
    "raw_affected_cells",
    "affected_sequence_rows",
    "affected_sequence_cells",
    "affected_selected_window_rows",
    "affected_selected_window_cells",
    "operation_types",
    "raw_variable_columns",
]
RAW_AGGREGATE_PREFIXES = ("mean", "std", "min", "max", "n_obs", "n_bad", "qc_ok_rate")
DERIVED_COLUMNS_BY_CANONICAL = {
    "TP_ugL": ["log_TP", "TN_TP_ratio"],
    "TN_ugL": ["log_TN", "TN_TP_ratio"],
    "chlorophyll_a_ugL": ["log_chlorophyll_a", "risk_chla"],
}
DIAGNOSTIC_INPUT_COLUMNS = [
    "x_yN",
    "x_yF",
    "x_yT",
    "x_sigma_N",
    "x_sigma_F",
    "x_sigma_T",
    "x_delta_yN",
    "x_delta_yF",
    "x_delta_yT",
    "x_irc_basis",
]


def _default_output(
    path_from_args: Path | None,
    key: str,
    fallback: Path | None,
    *,
    output_name: str | None,
    output_dir: Path,
) -> Path | None:
    if path_from_args is not None:
        return path_from_args
    if output_name is not None:
        return output_dir / f"controlled_degradation_{output_name}_{OUTPUT_SUFFIXES[key]}"
    return fallback


def _scenario_metadata(
    scenario: dict[str, Any],
    *,
    seed: int | None,
    status: str,
    fuzzy_state_rebuilt: bool,
) -> dict[str, Any]:
    return {
        "degradation_version": DEGRADATION_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_family": str(scenario.get("family", "")),
        "scenario_tier": str(scenario.get("tier", "")),
        "scenario_status": status,
        "seed": seed,
        "score_recomputed": True,
        "fuzzy_state_rebuilt": bool(fuzzy_state_rebuilt),
        "labels_preserved": True,
    }


def _add_scenario_columns(
    frame: pd.DataFrame,
    scenario: dict[str, Any],
    *,
    seed: int | None,
    status: str,
    fuzzy_state_rebuilt: bool,
) -> pd.DataFrame:
    out = frame.copy()
    metadata = _scenario_metadata(
        scenario,
        seed=seed,
        status=status,
        fuzzy_state_rebuilt=fuzzy_state_rebuilt,
    )
    for column in reversed(SCENARIO_COLUMNS):
        out.insert(0, column, metadata[column])
    return out


def load_frozen_irc_weights(path: Path) -> tuple[dict[str, float], str]:
    if not path.exists():
        return {key: float(value) for key, value in DEFAULT_IRC_WEIGHTS.items()}, "expert_default"
    payload = json.loads(path.read_text(encoding="utf-8"))
    weights = payload.get("irc_weights")
    if not isinstance(weights, dict):
        return {key: float(value) for key, value in DEFAULT_IRC_WEIGHTS.items()}, "expert_default"
    missing = sorted(set(DEFAULT_IRC_WEIGHTS) - set(weights))
    if missing:
        raise ValueError(f"Fuzzy manifest is missing IRC weight keys: {missing}")
    return {key: float(weights[key]) for key in DEFAULT_IRC_WEIGHTS}, "fuzzy_manifest"


def _panel_columns_for_variable(variable: str, frame: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    if variable in frame.columns:
        columns.append(variable)
    for prefix in RAW_AGGREGATE_PREFIXES:
        column = f"{prefix}_{variable}"
        if column in frame.columns:
            columns.append(column)
    for column in DERIVED_COLUMNS_BY_CANONICAL.get(variable, []):
        if column in frame.columns:
            columns.append(column)
    return list(dict.fromkeys(columns))


def raw_variable_group_columns(config: dict[str, Any], group_name: str, frame: pd.DataFrame) -> list[str]:
    group = config.get("canonical_variable_groups", {}).get(group_name)
    if not isinstance(group, dict):
        raise ValueError(f"Unknown canonical variable group: {group_name}")
    columns: list[str] = []
    for variable in [str(value) for value in group.get("variables", [])]:
        columns.extend(_panel_columns_for_variable(variable, frame))
    columns = list(dict.fromkeys(columns))
    if not columns:
        raise ValueError(f"Canonical variable group {group_name!r} maps to no panel columns")
    return columns


def _set_columns_missing(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    before = out[columns].notna()
    out.loc[:, columns] = np.nan
    return out, int(before.any(axis=1).sum()), int(before.sum().sum())


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
    dropped = (rng.random(eligible.shape) < float(rate)) & eligible
    for index, column in enumerate(columns):
        if dropped[:, index].any():
            out.loc[dropped[:, index], column] = np.nan
    return out, int(dropped.any(axis=1).sum()), int(dropped.sum())


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
    for _, group in out.groupby(["source_id", "site_id"], sort=True):
        if rng.random() >= float(site_history_block_rate):
            continue
        months = pd.PeriodIndex(group["year_month"].astype(str), freq="M")
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
    return out, int(before.any(axis=1).sum()), int(before.sum().sum())


def apply_raw_operations(
    frame: pd.DataFrame,
    scenario: dict[str, Any],
    config: dict[str, Any],
    seed: int | None,
) -> tuple[pd.DataFrame, int, int, list[str]]:
    out = frame.copy()
    affected_rows = 0
    affected_cells = 0
    raw_columns: list[str] = []
    effective_seed = 0 if seed is None else int(seed)
    for operation in scenario.get("operations", []):
        operation_type = str(operation.get("type"))
        if operation_type not in SUPPORTED_OPERATIONS:
            raise ValueError(
                f"Unsupported raw predictor recomputation operation {operation_type!r}; "
                f"supported operations are {sorted(SUPPORTED_OPERATIONS)}"
            )
        columns = raw_variable_group_columns(config, str(operation.get("variable_group")), out)
        raw_columns.extend(columns)
        if operation_type == "set_variables_missing":
            out, rows, cells = _set_columns_missing(out, columns)
        elif operation_type == "random_value_dropout":
            out, rows, cells = _random_value_dropout(
                out,
                columns=columns,
                rate=float(operation.get("rate", 0.0)),
                seed=effective_seed,
            )
        else:
            out, rows, cells = _temporal_block_dropout(
                out,
                columns=columns,
                block_length_months=int(operation.get("block_length_months", 1)),
                site_history_block_rate=float(operation.get("site_history_block_rate", 0.0)),
                seed=effective_seed,
            )
        affected_rows += rows
        affected_cells += cells
    return out.reset_index(drop=True), affected_rows, affected_cells, list(dict.fromkeys(raw_columns))


def validate_raw_scenarios(scenarios: list[dict[str, Any]]) -> None:
    for scenario in scenarios:
        unsupported = sorted(set(operation_types(scenario)) - SUPPORTED_OPERATIONS)
        if unsupported:
            raise ValueError(
                f"Scenario {scenario['scenario_id']!r} is not a raw predictor rebuild scenario; "
                f"unsupported operations: {unsupported}"
            )


def filter_panel_sources(panel: pd.DataFrame, source_ids: list[str]) -> pd.DataFrame:
    if not source_ids:
        return panel
    available = set(panel["source_id"].astype(str).unique())
    missing = sorted(set(source_ids).difference(available))
    if missing:
        raise ValueError(f"Requested source_id values are not present in the monthly panel: {missing}")
    out = panel[panel["source_id"].astype(str).isin(source_ids)].copy()
    if out.empty:
        raise ValueError(f"Source filter removed all monthly panel rows: {source_ids}")
    return out.reset_index(drop=True)


def build_recomputed_sequences(
    panel: pd.DataFrame,
    *,
    irc_weights: dict[str, float],
    sequence_args: argparse.Namespace,
) -> tuple[pd.DataFrame, int, int]:
    source_ids = getattr(sequence_args, "source_ids_normalized", [])
    panel = filter_panel_sources(panel, source_ids)
    state, _ = build_expert_state(panel, irc_weights=irc_weights)
    state = filter_state_sources(state, source_ids)
    candidates = build_sequence_candidates(
        state,
        input_surface=getattr(sequence_args, "input_surface", INPUT_SURFACE_FULL),
    )
    sequences, discarded = filter_leakage_safe_sequences(candidates, sequence_args)
    return sequences, int(len(state)), int(len(discarded))


def align_degraded_inputs(
    base_frame: pd.DataFrame,
    degraded_sequences: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    key_columns = ID_COLUMNS
    degraded = degraded_sequences[key_columns + INPUT_COLUMNS].copy()
    for column in ["source_id", "site_id", "origin_year_month", "target_year_month", "split"]:
        degraded[column] = degraded[column].astype(str)
    degraded["sequence_step"] = pd.to_numeric(degraded["sequence_step"], errors="coerce").astype("int64")
    degraded["_degraded_present"] = True
    degraded = degraded.rename(columns={column: f"{column}__degraded" for column in INPUT_COLUMNS})

    out = base_frame.copy()
    lookup = out[key_columns].copy()
    for column in ["source_id", "site_id", "origin_year_month", "target_year_month", "split"]:
        lookup[column] = lookup[column].astype(str)
    lookup["sequence_step"] = pd.to_numeric(lookup["sequence_step"], errors="coerce").astype("int64")

    merged = lookup.merge(degraded, on=key_columns, how="left", validate="one_to_one")
    missing_rows = int(merged["_degraded_present"].isna().sum())
    if missing_rows:
        raise ValueError(f"Rebuilt sequences are missing {missing_rows:,} canonical sequence rows")
    for column in INPUT_COLUMNS:
        out[column] = pd.to_numeric(merged[f"{column}__degraded"], errors="coerce").fillna(0.0).to_numpy()
    return out, missing_rows


def _source_key(frame: pd.DataFrame) -> pd.Series:
    return frame["source_id"].astype(str) + "\x1f" + frame["site_id"].astype(str)


def build_surface_diagnostics(panel: pd.DataFrame, frame: pd.DataFrame, indices: np.ndarray) -> pd.DataFrame:
    panel_work = panel[["source_id", "site_id", "year_month"]].copy()
    for column in ["source_id", "site_id", "year_month"]:
        panel_work[column] = panel_work[column].astype(str)
    panel_work["_source_site_key"] = _source_key(panel_work)
    panel_summary = (
        panel_work.groupby("source_id", dropna=False)
        .agg(panel_rows=("site_id", "size"), panel_sites=("_source_site_key", "nunique"))
        .reset_index()
    )

    sequence_work = frame[["source_id", "site_id", "origin_year_month"]].copy()
    sequence_work["_source_site_key"] = _source_key(sequence_work)
    sequence_summary = (
        sequence_work.groupby("source_id", dropna=False)
        .agg(canonical_sequence_rows=("site_id", "size"), canonical_sequence_sites=("_source_site_key", "nunique"))
        .reset_index()
    )

    selected_work = frame.loc[indices, ["source_id", "site_id", "origin_year_month"]].copy()
    selected_work["_source_site_key"] = _source_key(selected_work)
    selected_summary = (
        selected_work.groupby("source_id", dropna=False)
        .agg(selected_origin_rows=("site_id", "size"), selected_origin_sites=("_source_site_key", "nunique"))
        .reset_index()
    )

    origin_keys = sequence_work.rename(columns={"origin_year_month": "year_month"})[
        ["source_id", "site_id", "year_month"]
    ].drop_duplicates()
    panel_origin_match = panel_work[["source_id", "site_id", "year_month"]].merge(
        origin_keys.assign(_has_sequence_origin=True),
        on=["source_id", "site_id", "year_month"],
        how="left",
        validate="many_to_one",
    )
    panel_missing_origin = (
        panel_origin_match[panel_origin_match["_has_sequence_origin"].isna()]
        .groupby("source_id", dropna=False)
        .size()
        .rename("panel_rows_without_sequence_origin")
        .reset_index()
    )

    out = panel_summary.merge(sequence_summary, on="source_id", how="outer")
    out = out.merge(selected_summary, on="source_id", how="outer")
    out = out.merge(panel_missing_origin, on="source_id", how="outer")
    out["source_id"] = out["source_id"].astype(str)
    for column in [
        "panel_rows",
        "panel_sites",
        "canonical_sequence_rows",
        "canonical_sequence_sites",
        "selected_origin_rows",
        "selected_origin_sites",
        "panel_rows_without_sequence_origin",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype("int64")
    out["source_in_canonical_sequences"] = out["canonical_sequence_rows"] > 0
    out["source_in_selected_origins"] = out["selected_origin_rows"] > 0
    out.insert(0, "diagnostic_type", "surface_by_source")
    return out.sort_values("source_id").reset_index(drop=True)


def _input_irc_basis(frame: pd.DataFrame, irc_weights: dict[str, float]) -> pd.Series:
    alpha = float(irc_weights["alpha"])
    beta = float(irc_weights["beta"])
    gamma = float(irc_weights["gamma"])
    denominator = alpha + beta + gamma
    if denominator <= 0:
        raise ValueError("IRC weights must sum to a positive value")
    values = (
        alpha * pd.to_numeric(frame["x_yN"], errors="coerce")
        + beta * (1.0 - pd.to_numeric(frame["x_yF"], errors="coerce"))
        + gamma * pd.to_numeric(frame["x_yT"], errors="coerce")
    ) / denominator
    return values.clip(0.0, 1.0)


def input_change_diagnostics(
    before: pd.DataFrame,
    after: pd.DataFrame,
    *,
    row_indices: np.ndarray,
    scenario: dict[str, Any],
    seed: int | None,
    scope: str,
    irc_weights: dict[str, float],
    fuzzy_state_rebuilt: bool,
) -> pd.DataFrame:
    if len(row_indices) == 0:
        row_indices = np.array([], dtype="int64")
    before_values = before.loc[row_indices, INPUT_COLUMNS].copy()
    after_values = after.loc[row_indices, INPUT_COLUMNS].copy()
    before_values["x_irc_basis"] = _input_irc_basis(before.loc[row_indices], irc_weights)
    after_values["x_irc_basis"] = _input_irc_basis(after.loc[row_indices], irc_weights)
    rows: list[dict[str, Any]] = []
    metadata = _scenario_metadata(
        scenario,
        seed=seed,
        status="evaluated",
        fuzzy_state_rebuilt=fuzzy_state_rebuilt,
    )
    for column in DIAGNOSTIC_INPUT_COLUMNS:
        before_column = pd.to_numeric(before_values[column], errors="coerce")
        after_column = pd.to_numeric(after_values[column], errors="coerce")
        delta = after_column - before_column
        changed = ~np.isclose(before_column.to_numpy(dtype="float64"), after_column.to_numpy(dtype="float64"), equal_nan=True)
        rows.append(
            {
                "diagnostic_type": "input_change",
                **metadata,
                "scope": scope,
                "input_column": column,
                "rows": int(len(row_indices)),
                "changed_rows": int(changed.sum()),
                "mean_before": float(before_column.mean()) if len(before_column) else np.nan,
                "mean_after": float(after_column.mean()) if len(after_column) else np.nan,
                "mean_delta": float(delta.mean()) if len(delta) else np.nan,
                "mean_abs_delta": float(delta.abs().mean()) if len(delta) else np.nan,
                "max_abs_delta": float(delta.abs().max()) if len(delta) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def control_rebuild_diagnostics(
    *,
    panel: pd.DataFrame,
    frame: pd.DataFrame,
    indices: np.ndarray,
    history_length: int,
    irc_weights: dict[str, float],
    sequence_args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rebuilt_sequences, rebuilt_state_rows, discarded_rows = build_recomputed_sequences(
        panel,
        irc_weights=irc_weights,
        sequence_args=sequence_args,
    )
    rebuilt_frame, missing_rows = align_degraded_inputs(frame, rebuilt_sequences)
    all_indices = np.arange(len(frame), dtype="int64")
    selected_indices = selected_window_indices(indices, history_length)
    all_rows, all_cells = changed_counts(frame, rebuilt_frame, row_indices=all_indices, columns=INPUT_COLUMNS)
    selected_rows, selected_cells = changed_counts(frame, rebuilt_frame, row_indices=selected_indices, columns=INPUT_COLUMNS)
    row = {
        "diagnostic_type": "control_rebuild",
        "source_id": "all",
        "canonical_sequence_rows": int(len(frame)),
        "rebuilt_state_rows": int(rebuilt_state_rows),
        "rebuilt_sequence_rows": int(len(rebuilt_sequences)),
        "rebuilt_discarded_rows": int(discarded_rows),
        "alignment_missing_rows": int(missing_rows),
        "affected_sequence_rows": int(all_rows),
        "affected_sequence_cells": int(all_cells),
        "affected_selected_window_rows": int(selected_rows),
        "affected_selected_window_cells": int(selected_cells),
    }
    input_rows = input_change_diagnostics(
        frame,
        rebuilt_frame,
        row_indices=selected_indices,
        scenario={"scenario_id": "control_rebuild", "family": "diagnostic", "tier": "diagnostic", "operations": []},
        seed=None,
        scope="selected_window",
        irc_weights=irc_weights,
        fuzzy_state_rebuilt=True,
    )
    return pd.DataFrame([row]), input_rows


def run_scenario(
    *,
    frame: pd.DataFrame,
    indices: np.ndarray,
    observed: pd.DataFrame,
    bloom_targets: pd.DataFrame,
    panel: pd.DataFrame,
    irc_weights: dict[str, float],
    sequence_args: argparse.Namespace,
    scenario: dict[str, Any],
    config: dict[str, Any],
    seed: int | None,
    model: Any,
    blend_weights: Any | None,
    args: argparse.Namespace,
    history_length: int,
    device: Any,
    calibrators: dict[int, Any],
    rollout_bloom_calibrators: dict[int, Any],
    thresholds: pd.DataFrame,
    policies: list[str],
) -> dict[str, Any]:
    fuzzy_state_rebuilt = bool(scenario.get("operations"))
    raw_affected_rows = 0
    raw_affected_cells = 0
    raw_columns: list[str] = []
    rebuilt_state_rows = 0
    rebuilt_sequence_rows = len(frame)

    if fuzzy_state_rebuilt:
        panel = filter_panel_sources(panel, getattr(sequence_args, "source_ids_normalized", []))
        degraded_panel, raw_affected_rows, raw_affected_cells, raw_columns = apply_raw_operations(
            panel,
            scenario,
            config,
            seed,
        )
        sequences, rebuilt_state_rows, _discarded_rows = build_recomputed_sequences(
            degraded_panel,
            irc_weights=irc_weights,
            sequence_args=sequence_args,
        )
        rebuilt_sequence_rows = len(sequences)
        degraded, _missing_rows = align_degraded_inputs(frame, sequences)
    else:
        degraded = frame.copy()

    all_indices = np.arange(len(frame), dtype="int64")
    affected_sequence_rows, affected_sequence_cells = changed_counts(
        frame,
        degraded,
        row_indices=all_indices,
        columns=INPUT_COLUMNS,
    )
    affected_selected_window_rows, affected_selected_window_cells = changed_counts(
        frame,
        degraded,
        row_indices=selected_window_indices(indices, history_length),
        columns=INPUT_COLUMNS,
    )
    diagnostic_parts = [
        input_change_diagnostics(
            frame,
            degraded,
            row_indices=all_indices,
            scenario=scenario,
            seed=seed,
            scope="all_sequence_rows",
            irc_weights=irc_weights,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        ),
        input_change_diagnostics(
            frame,
            degraded,
            row_indices=selected_window_indices(indices, history_length),
            scenario=scenario,
            seed=seed,
            scope="selected_window",
            irc_weights=irc_weights,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        ),
    ]

    rollouts = build_rollouts(
        degraded,
        indices,
        model=model,
        blend_weights=blend_weights,
        args=args,
        history_length=history_length,
        device=device,
        calibrators=calibrators,
    )
    backtest = attach_observations(rollouts, observed, bloom_targets, args=args)
    status = "evaluated" if not backtest.empty else "empty_after_recompute"
    if backtest.empty:
        state_metrics = _add_scenario_columns(
            pd.DataFrame(),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        alert_metrics = _add_scenario_columns(
            pd.DataFrame(),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        examples = _add_scenario_columns(
            pd.DataFrame(),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        policy_metrics = pd.DataFrame()
        backtest_rows = _add_scenario_columns(
            pd.DataFrame(),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
    else:
        state_metrics = _add_scenario_columns(
            build_state_metrics(backtest),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        alert_metrics = _add_scenario_columns(
            build_alert_metrics(backtest),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        examples = _add_scenario_columns(
            build_examples(backtest, args.examples_per_group),
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )
        backtest_rows_base = compact_backtest_rows(backtest)
        backtest_rows_base = apply_bloom_calibrators(backtest_rows_base, rollout_bloom_calibrators)
        prepared_policy_rows = prepare_rows(backtest_rows_base, thresholds, policies)
        policy_metrics = build_metric_rows(
            prepared_policy_rows,
            thresholds,
            scenario,
            seed=seed,
            policies=policies,
            splits=args.evaluation_splits,
            include_all_sources=args.include_all_sources,
            min_rows=args.min_policy_rows,
            score_recomputed=True,
        )
        if not policy_metrics.empty:
            policy_metrics["degradation_version"] = DEGRADATION_VERSION
        backtest_rows = _add_scenario_columns(
            backtest_rows_base,
            scenario,
            seed=seed,
            status=status,
            fuzzy_state_rebuilt=fuzzy_state_rebuilt,
        )

    return {
        "status": status,
        "reason": "",
        "raw_affected_rows": raw_affected_rows,
        "raw_affected_cells": raw_affected_cells,
        "raw_columns": raw_columns,
        "rebuilt_state_rows": rebuilt_state_rows,
        "rebuilt_sequence_rows": rebuilt_sequence_rows,
        "affected_sequence_rows": affected_sequence_rows,
        "affected_sequence_cells": affected_sequence_cells,
        "affected_selected_window_rows": affected_selected_window_rows,
        "affected_selected_window_cells": affected_selected_window_cells,
        "fuzzy_state_rebuilt": fuzzy_state_rebuilt,
        "state_metrics": state_metrics,
        "alert_metrics": alert_metrics,
        "policy_metrics": policy_metrics,
        "examples": examples,
        "backtest_rows": backtest_rows,
        "diagnostics": pd.concat(diagnostic_parts, ignore_index=True),
    }


def build_report(
    *,
    args: argparse.Namespace,
    config: dict[str, Any],
    summary: pd.DataFrame,
    state_metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    policy_metrics: pd.DataFrame,
    diagnostics: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    history_length: int,
    calibrated_horizons: list[int],
    started_at: datetime,
) -> str:
    default_policy = config.get("protocol", {}).get("default_alert_policy", {}).get("selection_objective", "closest_pr")
    state_headline = (
        state_metrics[
            (state_metrics["group_type"] == "overall")
            & (state_metrics["source_id"] == "all")
            & (state_metrics["target"].isin(["all", "irc1"]))
        ].copy()
        if not state_metrics.empty
        else pd.DataFrame()
    )
    alert_headline = (
        alert_metrics[(alert_metrics["group_type"] == "overall") & (alert_metrics["source_id"] == "all")].copy()
        if not alert_metrics.empty
        else pd.DataFrame()
    )
    policy_headline = (
        policy_metrics[
            (policy_metrics["split"] == "test")
            & (policy_metrics["source_id"] == "all")
            & (policy_metrics["alert_policy"].isin(args.policies))
        ].copy()
        if not policy_metrics.empty
        else pd.DataFrame()
    )
    lines = [
        "# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report degrades raw monthly panel predictors, rebuilds the deterministic fuzzy state, "
        "rebuilds PIPE sequence inputs, and recomputes frozen PIPE/GRU-D rollouts.",
        "Observed labels and future states remain fixed from the undegraded canonical sequence/split surfaces.",
        "Fuzzy IRC weights are frozen; no fuzzy weights, PIPE weights, calibrators, or alert thresholds are refit.",
        "",
        "## Configuration",
        "",
        f"- Config: `{args.config}`",
        f"- Panel: `{args.panel}`",
        f"- Canonical sequences/labels: `{args.sequences}`",
        f"- Rebuilt input surface: `{args.input_surface}`",
        f"- Rebuilt source filter: `{args.source_ids_normalized or 'all'}`",
        f"- Fuzzy manifest for frozen weights: `{args.fuzzy_manifest}`",
        f"- Fuzzy weight source: `{args.fuzzy_weight_source}`",
        f"- Scenario set: `{args.scenario_set}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- History length: `{history_length}`",
        f"- Rollout horizon: `{args.rollout_horizon}` month(s)",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- Max origins cap: `{args.max_origins}`",
        f"- Policies: `{args.policies}`",
        f"- Requested policy evaluation splits: `{args.evaluation_splits}`",
        f"- Default downstream policy context: `{default_policy}`",
        f"- Calibrated bloom horizons available: `{calibrated_horizons}`",
        f"- Rollout bloom calibrator horizons available: `{args.rollout_bloom_calibrator_horizons}`",
        "",
        "## Evaluation Surface Diagnostics",
        "",
        "| source | panel rows | panel sites | canonical sequence rows | selected origins | panel rows without sequence origin |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    surface = diagnostics[diagnostics["diagnostic_type"] == "surface_by_source"].copy()
    if surface.empty:
        lines.append("| `NA` | 0 | 0 | 0 | 0 | 0 |")
    else:
        for row in dataframe_rows(surface.sort_values("source_id")):
            lines.append(
                f"| `{row.source_id}` | {_format_int(int(row.panel_rows))} | {_format_int(int(row.panel_sites))} | "
                f"{_format_int(int(row.canonical_sequence_rows))} | {_format_int(int(row.selected_origin_rows))} | "
                f"{_format_int(int(row.panel_rows_without_sequence_origin))} |"
            )

    lines.extend(
        [
            "",
            "## Control Rebuild Drift",
            "",
            "| canonical sequence rows | rebuilt state rows | rebuilt sequence rows | alignment missing rows | sequence cells changed | selected-window cells changed |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    control_rebuild = diagnostics[diagnostics["diagnostic_type"] == "control_rebuild"].copy()
    if control_rebuild.empty:
        lines.append("| 0 | 0 | 0 | 0 | 0 | 0 |")
    else:
        row = next(dataframe_rows(control_rebuild.head(1)))
        lines.append(
            f"| {_format_int(int(row.canonical_sequence_rows))} | {_format_int(int(row.rebuilt_state_rows))} | "
            f"{_format_int(int(row.rebuilt_sequence_rows))} | {_format_int(int(row.alignment_missing_rows))} | "
            f"{_format_int(int(row.affected_sequence_cells))} | "
            f"{_format_int(int(row.affected_selected_window_cells))} |"
        )

    input_focus = diagnostics[
        (diagnostics["diagnostic_type"] == "input_change")
        & (diagnostics["scope"] == "selected_window")
        & (diagnostics["input_column"].isin(["x_yN", "x_yF", "x_yT", "x_irc_basis"]))
        & (diagnostics["scenario_id"] != "control_observed")
    ].copy()
    lines.extend(
        [
            "",
            "## Selected-Window Input Changes",
            "",
            "| scenario | input | rows | changed rows | mean before | mean after | mean delta | mean absolute delta |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if input_focus.empty:
        lines.append("| `NA` | `NA` | 0 | 0 | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(input_focus.sort_values(["scenario_id", "input_column"])):
            lines.append(
                f"| `{row.scenario_id}` | `{row.input_column}` | {_format_int(int(row.rows))} | "
                f"{_format_int(int(row.changed_rows))} | {_format_float(row.mean_before)} | "
                f"{_format_float(row.mean_after)} | {_format_float(row.mean_delta)} | "
                f"{_format_float(row.mean_abs_delta)} |"
            )

    lines.extend(
        [
            "",
            "## Future Availability",
            "",
            "| horizon | eligible origins | origins with observed future | selected origins | policy |",
            "|---:|---:|---:|---:|---|",
        ]
    )
    for row in dataframe_rows(availability_summary.sort_values("rollout_horizon_months")):
        lines.append(
            f"| {int(row.rollout_horizon_months)} | {_format_int(int(row.eligible_origins))} | "
            f"{_format_int(int(row.origins_with_observed_future))} | {_format_int(int(row.selected_origins))} | "
            f"`{row.selection_policy}` |"
        )

    lines.extend(
        [
            "",
            "## Scenario Summary",
            "",
            "| scenario | status | seed | raw cells | sequence cells | selected-window cells | rollout rows | policy metric rows |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(summary.sort_values(["scenario_id", "seed"], na_position="first")):
        seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
        lines.append(
            f"| `{row.scenario_id}` | `{row.scenario_status}` | {seed} | "
            f"{_format_int(int(row.raw_affected_cells))} | {_format_int(int(row.affected_sequence_cells))} | "
            f"{_format_int(int(row.affected_selected_window_cells))} | "
            f"{_format_int(int(row.evaluated_rollout_rows))} | {_format_int(int(row.policy_metric_rows))} |"
        )

    lines.extend(
        [
            "",
            "## State Metrics",
            "",
            "| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |",
            "|---|---:|---|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    if state_headline.empty:
        lines.append("| `NA` | NA | `NA` | NA | `NA` | 0 | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(
            state_headline.sort_values(["scenario_id", "seed", "split", "rollout_horizon_months", "target"])
        ):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | `{row.split}` | {int(row.rollout_horizon_months)} | "
                f"`{row.target}` | {_format_int(int(row.rows))} | {_format_float(row.rmse)} | "
                f"{_format_float(row.persistence_rmse)} | {_format_float(row.rmse_relative_improvement)} | "
                f"{_format_float(row.mae)} |"
            )

    lines.extend(
        [
            "",
            "## Alert Metrics",
            "",
            "| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if alert_headline.empty:
        lines.append("| `NA` | NA | `NA` | `NA` | NA | 0 | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(
            alert_headline.sort_values(["scenario_id", "seed", "target_event", "split", "rollout_horizon_months"])
        ):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | `{row.target_event}` | `{row.split}` | "
                f"{int(row.rollout_horizon_months)} | {_format_int(int(row.rows))} | "
                f"{_format_float(row.positive_rate)} | {_format_float(row.predicted_positive_rate)} | "
                f"{_format_float(row.pr_auc)} | {_format_float(row.brier)} | {_format_float(row.recall)} |"
            )

    lines.extend(
        [
            "",
            "## Policy Metrics",
            "",
            "| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if policy_headline.empty:
        lines.append("| `NA` | NA | `NA` | `NA` | `NA` | NA | 0 | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(
            policy_headline.sort_values(
                ["scenario_id", "seed", "alert_policy", "target_event", "rollout_horizon_months"]
            )
        ):
            seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
            lines.append(
                f"| `{row.scenario_id}` | {seed} | `{row.alert_policy}` | `{row.target_event}` | "
                f"`{row.split}` | {int(row.rollout_horizon_months)} | {_format_int(int(row.rows))} | "
                f"{_format_float(row.recall)} | {_format_float(row.precision)} | "
                f"{_format_float(row.alert_rate)} | {_format_float(row.f2)} | "
                f"{_format_float(row.delta_f2_vs_control)} |"
            )

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.",
            "- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.",
            "- This experiment measures operational dependence of the current pipeline, not ecological causal importance.",
            "- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.",
            "- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.",
            "- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.",
            "- Degraded outputs are stress-test evidence, not official environmental alerts.",
            "",
            "## Outputs",
            "",
            f"- State metrics: `{args.state_metrics}`",
            f"- Alert metrics: `{args.alert_metrics}`",
            f"- Policy metrics: `{args.policy_metrics}`",
            f"- Summary: `{args.summary}`",
            f"- Examples: `{args.examples}`",
            f"- Diagnostics: `{args.diagnostics}`",
            f"- Backtest rows: `{args.backtest_rows}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    return "\n".join(lines)


def manifest_payload(
    *,
    args: argparse.Namespace,
    config: dict[str, Any],
    summary: pd.DataFrame,
    state_metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    policy_metrics: pd.DataFrame,
    diagnostics: pd.DataFrame,
    examples: pd.DataFrame,
    backtest_rows: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    history_length: int,
    calibrators: dict[int, Any],
    model_config: dict[str, Any],
    model_payload: dict[str, Any],
    started_at: datetime,
) -> dict[str, Any]:
    inputs = [args.config, args.panel, args.sequences, args.model, args.thresholds]
    if args.splits.exists():
        inputs.append(args.splits)
    if args.model_manifest.exists():
        inputs.append(args.model_manifest)
    if args.fuzzy_manifest.exists():
        inputs.append(args.fuzzy_manifest)
    inputs.extend(info.path for info in calibrators.values())
    inputs.extend(record.path for record in args.rollout_bloom_calibrators.values())
    outputs = [
        args.state_metrics,
        args.alert_metrics,
        args.policy_metrics,
        args.summary,
        args.examples,
        args.diagnostics,
        args.report,
    ]
    if args.backtest_rows is not None:
        outputs.append(args.backtest_rows)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "degradation_version": DEGRADATION_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "pipe_model_version": model_payload.get("model_version", PIPE_MODEL_VERSION),
        "config": {
            "scenario_set": args.scenario_set,
            "scenarios": args.scenarios,
            "split": args.split,
            "history_length": int(history_length),
            "rollout_horizon": int(args.rollout_horizon),
            "samples": int(1 if args.deterministic else args.samples),
            "deterministic": bool(args.deterministic),
            "batch_size": int(args.batch_size),
            "max_origins": args.max_origins,
            "max_rows": args.max_rows,
            "allow_partial_horizons": bool(args.allow_partial_horizons),
            "irc_alpha": float(args.irc_alpha),
            "irc_beta": float(args.irc_beta),
            "irc_gamma": float(args.irc_gamma),
            "irc_alert_threshold": float(args.irc_alert_threshold),
            "alert_prob_threshold": float(args.alert_prob_threshold),
            "random_seed": int(args.random_seed),
            "model_config": model_config,
            "calibrated_bloom_horizons": sorted(calibrators),
            "rollout_bloom_calibrator_horizons": sorted(args.rollout_bloom_calibrators),
            "thresholds": args.thresholds,
            "policies": args.policies,
            "evaluation_splits": args.evaluation_splits,
            "include_all_sources": bool(args.include_all_sources),
            "min_policy_rows": int(args.min_policy_rows),
            "max_gap_months": int(args.max_gap_months),
            "input_surface": args.input_surface,
            "source_ids": args.source_ids_normalized,
            "train_end": args.train_end,
            "validation_start": args.validation_start,
            "validation_end": args.validation_end,
            "test_start": args.test_start,
            "test_end": args.test_end,
            "fuzzy_weight_source": args.fuzzy_weight_source,
            "frozen_irc_weights": args.frozen_irc_weights,
            "scenario_config_protocol": config.get("protocol", {}),
        },
        "row_counts": {
            "selected_origins": int(selected_origins),
            "availability_summary_rows": int(len(availability_summary)),
            "summary_rows": int(len(summary)),
            "state_metric_rows": int(len(state_metrics)),
            "alert_metric_rows": int(len(alert_metrics)),
            "policy_metric_rows": int(len(policy_metrics)),
            "diagnostic_rows": int(len(diagnostics)),
            "example_rows": int(len(examples)),
            "backtest_row_rows": int(len(backtest_rows)),
            "evaluated_runs": int((summary["scenario_status"] == "evaluated").sum()) if not summary.empty else 0,
        },
        "scenario_summary": summary.to_dict(orient="records"),
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for path in outputs if path is not None and path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--fuzzy-manifest", type=Path, default=DEFAULT_FUZZY_MANIFEST)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--rollout-calibrator-dir", type=Path, default=Path("models/pipe_grud/rollout_calibrators"))
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--state-metrics", type=Path, default=None)
    parser.add_argument("--alert-metrics", type=Path, default=None)
    parser.add_argument("--policy-metrics", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--examples", type=Path, default=None)
    parser.add_argument("--diagnostics", type=Path, default=None)
    parser.add_argument("--backtest-rows", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-name", type=_safe_output_name, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--scenario-set", default="raw_predictor_rebuild_smoke")
    parser.add_argument("--scenarios", type=_parse_csv_list, default=None)
    parser.add_argument("--policies", type=_parse_csv_list, default=None)
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default=None)
    parser.add_argument("--min-policy-rows", type=int, default=1)
    parser.add_argument("--include-all-sources", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--split", choices=["all", "train", "validation", "test"], default="test")
    parser.add_argument("--history-length", type=int, default=None)
    parser.add_argument("--rollout-horizon", type=int, default=3)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-origins", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--examples-per-group", type=int, default=20)
    parser.add_argument(
        "--input-surface",
        choices=[INPUT_SURFACE_FULL, INPUT_SURFACE_NO_CURRENT_CHLA],
        default=INPUT_SURFACE_FULL,
        help="PIPE input surface to rebuild after raw predictor degradation.",
    )
    parser.add_argument(
        "--source-ids",
        nargs="*",
        default=None,
        help="Optional source_id filter to apply before rebuilding degraded PIPE sequences.",
    )
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
    parser.add_argument("--require-rollout-calibrators", action="store_true")
    parser.add_argument("--allow-partial-horizons", action="store_true")
    parser.add_argument("--max-gap-months", type=int, default=1)
    parser.add_argument("--train-end", default="2018-12")
    parser.add_argument("--validation-start", default="2019-01")
    parser.add_argument("--validation-end", default="2021-12")
    parser.add_argument("--test-start", default="2022-01")
    parser.add_argument("--test-end", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.source_ids_normalized = _parse_source_ids(args.source_ids)
    if args.rollout_horizon < 1:
        raise ValueError("--rollout-horizon must be >= 1")
    if args.samples < 1:
        raise ValueError("--samples must be >= 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")
    if args.max_origins is not None and args.max_origins < 1:
        raise ValueError("--max-origins must be >= 1")
    if args.min_policy_rows < 1:
        raise ValueError("--min-policy-rows must be >= 1")

    config = read_config(args.config)
    validate_scenarios(config)
    scenarios = select_scenarios(config, args)
    validate_raw_scenarios(scenarios)

    args.state_metrics = _default_output(
        args.state_metrics,
        "state_metrics",
        DEFAULT_STATE_METRICS,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.alert_metrics = _default_output(
        args.alert_metrics,
        "alert_metrics",
        DEFAULT_ALERT_METRICS,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.policy_metrics = _default_output(
        args.policy_metrics,
        "policy_metrics",
        DEFAULT_POLICY_METRICS,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.summary = _default_output(
        args.summary,
        "summary",
        DEFAULT_SUMMARY,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.examples = _default_output(
        args.examples,
        "examples",
        DEFAULT_EXAMPLES,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.diagnostics = _default_output(
        args.diagnostics,
        "diagnostics",
        DEFAULT_DIAGNOSTICS,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.report = _default_output(
        args.report,
        "report",
        DEFAULT_REPORT,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.manifest = _default_output(
        args.manifest,
        "manifest",
        DEFAULT_MANIFEST,
        output_name=args.output_name,
        output_dir=args.output_dir,
    )
    args.backtest_rows = _default_output(
        args.backtest_rows,
        "backtest_rows",
        None,
        output_name=args.output_name if args.backtest_rows is not None else None,
        output_dir=args.output_dir,
    )
    assert args.state_metrics is not None
    assert args.alert_metrics is not None
    assert args.policy_metrics is not None
    assert args.summary is not None
    assert args.examples is not None
    assert args.diagnostics is not None
    assert args.report is not None
    assert args.manifest is not None

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

    print(f"loading canonical sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_window_frame(frame)
    observed = observed_state_frame(frame)
    print(
        f"sequence rows={len(frame):,}; observed states={len(observed):,}; elapsed={_elapsed(started_monotonic)}",
        flush=True,
    )

    print(f"loading raw monthly panel {args.panel}", flush=True)
    panel = pd.read_parquet(args.panel)
    print(f"panel rows={len(panel):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    frozen_irc_weights, fuzzy_weight_source = load_frozen_irc_weights(args.fuzzy_manifest)
    args.frozen_irc_weights = frozen_irc_weights
    args.fuzzy_weight_source = fuzzy_weight_source
    print(
        "using frozen fuzzy weights "
        f"alpha={frozen_irc_weights['alpha']}, beta={frozen_irc_weights['beta']}, "
        f"gamma={frozen_irc_weights['gamma']} ({fuzzy_weight_source})",
        flush=True,
    )

    calibrators = load_calibrators(args)
    print(f"loaded calibrated bloom horizons={sorted(calibrators)}", flush=True)
    rollout_bloom_calibrators = load_rollout_bloom_calibrators(
        args.rollout_calibrator_dir,
        rollout_horizon=args.rollout_horizon,
        require_calibrators=args.require_rollout_calibrators,
    )
    args.rollout_bloom_calibrators = rollout_bloom_calibrators
    args.rollout_bloom_calibrator_horizons = sorted(rollout_bloom_calibrators)
    print(f"loaded rollout bloom calibrator horizons={sorted(rollout_bloom_calibrators)}", flush=True)

    thresholds = pd.read_csv(args.thresholds)
    args.policies = threshold_policies(config, args)
    if args.evaluation_splits is None:
        if args.split == "all":
            args.evaluation_splits = [
                str(split) for split in config.get("evaluation", {}).get("splits", ["validation", "test"])
            ]
        else:
            args.evaluation_splits = [str(args.split)]

    indices, availability_summary = select_backtest_indices(frame, args, history_length, observed)
    bloom_targets = load_bloom_targets(args.splits, args.rollout_horizon)
    sequence_args = argparse.Namespace(
        max_gap_months=args.max_gap_months,
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        test_start=args.test_start,
        test_end=args.test_end,
        input_surface=args.input_surface,
        source_ids_normalized=args.source_ids_normalized,
    )
    print(f"selected backtest origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    print("building evaluation-surface diagnostics", flush=True)
    diagnostic_panel = filter_panel_sources(panel, args.source_ids_normalized)
    diagnostic_parts: list[pd.DataFrame] = [build_surface_diagnostics(diagnostic_panel, frame, indices)]
    print("rebuilding undegraded fuzzy state/sequence for drift diagnostics", flush=True)
    control_rebuild, control_rebuild_inputs = control_rebuild_diagnostics(
        panel=panel,
        frame=frame,
        indices=indices,
        history_length=history_length,
        irc_weights=frozen_irc_weights,
        sequence_args=sequence_args,
    )
    diagnostic_parts.extend([control_rebuild, control_rebuild_inputs])
    print(f"finished rebuild diagnostics; elapsed={_elapsed(started_monotonic)}", flush=True)

    state_metric_parts: list[pd.DataFrame] = []
    alert_metric_parts: list[pd.DataFrame] = []
    policy_metric_parts: list[pd.DataFrame] = []
    example_parts: list[pd.DataFrame] = []
    backtest_row_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for scenario in scenarios:
        for seed in seeds_for_scenario(scenario, config):
            print(f"running scenario {scenario['scenario_id']} seed={seed}", flush=True)
            outputs = run_scenario(
                frame=frame,
                indices=indices,
                observed=observed,
                bloom_targets=bloom_targets,
                panel=panel,
                irc_weights=frozen_irc_weights,
                sequence_args=sequence_args,
                scenario=scenario,
                config=config,
                seed=seed,
                model=model,
                blend_weights=blend_weights,
                args=args,
                history_length=history_length,
                device=device,
                calibrators=calibrators,
                rollout_bloom_calibrators=rollout_bloom_calibrators,
                thresholds=thresholds,
                policies=args.policies,
            )
            state_metrics = outputs["state_metrics"]
            alert_metrics = outputs["alert_metrics"]
            policy_metrics = outputs["policy_metrics"]
            examples = outputs["examples"]
            backtest_rows = outputs["backtest_rows"]
            state_metric_parts.append(state_metrics)
            alert_metric_parts.append(alert_metrics)
            policy_metric_parts.append(policy_metrics)
            example_parts.append(examples)
            backtest_row_parts.append(backtest_rows)
            diagnostic_parts.append(outputs["diagnostics"])
            summary_rows.append(
                {
                    **_scenario_metadata(
                        scenario,
                        seed=seed,
                        status=str(outputs["status"]),
                        fuzzy_state_rebuilt=bool(outputs["fuzzy_state_rebuilt"]),
                    ),
                    "reason": str(outputs["reason"]),
                    "selected_origins": int(len(indices)),
                    "evaluated_rollout_rows": int(len(backtest_rows)),
                    "state_metric_rows": int(len(state_metrics)),
                    "alert_metric_rows": int(len(alert_metrics)),
                    "policy_metric_rows": int(len(policy_metrics)),
                    "example_rows": int(len(examples)),
                    "backtest_row_rows": int(len(backtest_rows)),
                    "raw_panel_rows": int(len(panel)),
                    "rebuilt_state_rows": int(outputs["rebuilt_state_rows"]),
                    "rebuilt_sequence_rows": int(outputs["rebuilt_sequence_rows"]),
                    "raw_affected_rows": int(outputs["raw_affected_rows"]),
                    "raw_affected_cells": int(outputs["raw_affected_cells"]),
                    "affected_sequence_rows": int(outputs["affected_sequence_rows"]),
                    "affected_sequence_cells": int(outputs["affected_sequence_cells"]),
                    "affected_selected_window_rows": int(outputs["affected_selected_window_rows"]),
                    "affected_selected_window_cells": int(outputs["affected_selected_window_cells"]),
                    "operation_types": ",".join(operation_types(scenario)),
                    "raw_variable_columns": ",".join(outputs["raw_columns"]),
                }
            )
            print(f"finished {scenario['scenario_id']} seed={seed}; elapsed={_elapsed(started_monotonic)}", flush=True)

    state_metrics_all = pd.concat(state_metric_parts, ignore_index=True) if state_metric_parts else pd.DataFrame()
    alert_metrics_all = pd.concat(alert_metric_parts, ignore_index=True) if alert_metric_parts else pd.DataFrame()
    policy_metrics_raw = pd.concat(policy_metric_parts, ignore_index=True) if policy_metric_parts else pd.DataFrame()
    policy_metrics_all = add_control_deltas(policy_metrics_raw)
    examples_all = pd.concat(example_parts, ignore_index=True) if example_parts else pd.DataFrame()
    backtest_rows_all = pd.concat(backtest_row_parts, ignore_index=True) if backtest_row_parts else pd.DataFrame()
    diagnostics_all = pd.concat(diagnostic_parts, ignore_index=True, sort=False) if diagnostic_parts else pd.DataFrame()
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    _write_csv_atomic(state_metrics_all, args.state_metrics)
    print(f"wrote {args.state_metrics}", flush=True)
    _write_csv_atomic(alert_metrics_all, args.alert_metrics)
    print(f"wrote {args.alert_metrics}", flush=True)
    _write_csv_atomic(policy_metrics_all, args.policy_metrics)
    print(f"wrote {args.policy_metrics}", flush=True)
    _write_csv_atomic(summary, args.summary)
    print(f"wrote {args.summary}", flush=True)
    _write_csv_atomic(examples_all, args.examples)
    print(f"wrote {args.examples}", flush=True)
    _write_csv_atomic(diagnostics_all, args.diagnostics)
    print(f"wrote {args.diagnostics}", flush=True)
    if args.backtest_rows is not None:
        write_table_atomic(backtest_rows_all, args.backtest_rows)
        print(f"wrote {args.backtest_rows}", flush=True)

    report = build_report(
        args=args,
        config=config,
        summary=summary,
        state_metrics=state_metrics_all,
        alert_metrics=alert_metrics_all,
        policy_metrics=policy_metrics_all,
        diagnostics=diagnostics_all,
        availability_summary=availability_summary,
        selected_origins=len(indices),
        history_length=history_length,
        calibrated_horizons=sorted(calibrators),
        started_at=started_at,
    )
    _write_text_atomic(report, args.report)
    print(f"wrote {args.report}", flush=True)

    manifest = manifest_payload(
        args=args,
        config=config,
        summary=summary,
        state_metrics=state_metrics_all,
        alert_metrics=alert_metrics_all,
        policy_metrics=policy_metrics_all,
        diagnostics=diagnostics_all,
        examples=examples_all,
        backtest_rows=backtest_rows_all,
        availability_summary=availability_summary,
        selected_origins=len(indices),
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
