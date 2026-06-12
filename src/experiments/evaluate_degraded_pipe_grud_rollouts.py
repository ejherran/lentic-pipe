#!/usr/bin/env python
"""Recompute PIPE/GRU-D rollout backtests under state-input degradation."""

from __future__ import annotations

import argparse
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
import joblib

from src.pandas_utils import dataframe_rows

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS
from src.experiments.evaluate_controlled_degradation import (
    _parse_csv_list,
    _safe_output_name,
    add_control_deltas,
    build_metric_rows,
    operation_types,
    prepare_rows,
    read_config,
    select_scenarios,
    threshold_policies,
    validate_scenarios,
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
from src.experiments.calibrate_pipe_rollout_alerts import (
    DEFAULT_MODEL_DIR as DEFAULT_ROLLOUT_CALIBRATOR_DIR,
    CalibratorRecord,
    apply_bloom_calibrators,
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
    MODEL_VERSION as PIPE_MODEL_VERSION,
    load_sequences,
    prepare_window_frame,
    _require_torch,
)


DEGRADATION_VERSION = "pipe_grud_state_recomputed_degradation_v0"
DEFAULT_CONFIG = Path("configs/degradation_scenarios.yaml")
DEFAULT_REPORT_DIR = Path("reports/degradation")
DEFAULT_STATE_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_state_metrics.csv"
DEFAULT_ALERT_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_alert_metrics.csv"
DEFAULT_POLICY_METRICS = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_policy_metrics.csv"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_summary.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "controlled_degradation_pipe_recomputed_manifest.json"
DEFAULT_THRESHOLDS = Path("reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv")
OUTPUT_SUFFIXES = {
    "state_metrics": "state_metrics.csv",
    "alert_metrics": "alert_metrics.csv",
    "policy_metrics": "policy_metrics.csv",
    "summary": "summary.csv",
    "examples": "examples.csv",
    "report": "report.md",
    "manifest": "manifest.json",
    "backtest_rows": "backtest_rows.parquet",
}
SCENARIO_COLUMNS = [
    "degradation_version",
    "scenario_id",
    "scenario_family",
    "scenario_tier",
    "scenario_status",
    "seed",
    "score_recomputed",
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
    "affected_rows",
    "affected_cells",
    "affected_selected_window_rows",
    "affected_selected_window_cells",
    "operation_types",
]
SUPPORTED_OPERATIONS = {
    "set_sequence_inputs",
    "random_sequence_dropout",
    "temporal_sequence_block_dropout",
}
RANDOM_OPERATIONS = {
    "random_sequence_dropout",
    "temporal_sequence_block_dropout",
}


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


def _scenario_metadata(scenario: dict[str, Any], *, seed: int | None, status: str) -> dict[str, Any]:
    return {
        "degradation_version": DEGRADATION_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_family": str(scenario.get("family", "")),
        "scenario_tier": str(scenario.get("tier", "")),
        "scenario_status": status,
        "seed": seed,
        "score_recomputed": True,
    }


def _add_scenario_columns(frame: pd.DataFrame, scenario: dict[str, Any], *, seed: int | None, status: str) -> pd.DataFrame:
    out = frame.copy()
    metadata = _scenario_metadata(scenario, seed=seed, status=status)
    for column in reversed(SCENARIO_COLUMNS):
        out.insert(0, column, metadata[column])
    return out


def load_rollout_bloom_calibrators(
    calibrator_dir: Path,
    *,
    rollout_horizon: int,
    require_calibrators: bool,
) -> dict[int, CalibratorRecord]:
    calibrators: dict[int, CalibratorRecord] = {}
    for horizon in range(1, rollout_horizon + 1):
        matches = sorted(calibrator_dir.glob(f"rollout_bloom_h{horizon}_*_isotonic.joblib"))
        if not matches:
            if require_calibrators:
                raise FileNotFoundError(
                    f"No rollout bloom calibrator found for horizon {horizon} in {calibrator_dir}"
                )
            continue
        path = matches[0]
        payload = joblib.load(path)
        calibrators[horizon] = CalibratorRecord(
            horizon=int(payload.get("horizon_months", horizon)),
            score_column=str(payload.get("score_column", "irc_mean")),
            path=path,
            calibrator=payload["calibrator"],
            method=str(payload.get("method", "isotonic")),
            training_rows=int(payload.get("training_rows", 0)),
            positive_rows=int(payload.get("positive_rows", 0)),
        )
    return calibrators


def _pipe_state_variable_columns(config: dict[str, Any], group_name: str, frame: pd.DataFrame) -> list[str]:
    group = config.get("pipe_state_variable_groups", {}).get(group_name)
    if not isinstance(group, dict):
        raise ValueError(f"Unknown PIPE state variable group: {group_name}")
    columns = [str(column) for column in group.get("variables", [])]
    if not columns:
        raise ValueError(f"PIPE state variable group {group_name!r} is empty")
    non_input = sorted(set(columns) - set(INPUT_COLUMNS))
    if non_input:
        raise ValueError(
            f"PIPE state variable group {group_name!r} contains non-input columns: {non_input}"
        )
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"PIPE sequence frame is missing columns for group {group_name!r}: {missing}")
    return columns


def scenario_sequence_columns(scenario: dict[str, Any], config: dict[str, Any], frame: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for operation in scenario.get("operations", []):
        group_name = operation.get("variable_group")
        if group_name is None:
            continue
        columns.extend(_pipe_state_variable_columns(config, str(group_name), frame))
    return list(dict.fromkeys(columns))


def selected_window_indices(indices: np.ndarray, history_length: int) -> np.ndarray:
    if len(indices) == 0:
        return np.array([], dtype="int64")
    windows = [np.arange(index - history_length + 1, index + 1, dtype="int64") for index in indices]
    return np.unique(np.concatenate(windows))


def changed_counts(
    before: pd.DataFrame,
    after: pd.DataFrame,
    *,
    row_indices: np.ndarray,
    columns: list[str],
) -> tuple[int, int]:
    if len(row_indices) == 0 or not columns:
        return 0, 0
    before_values = before.loc[row_indices, columns].to_numpy(dtype="float64")
    after_values = after.loc[row_indices, columns].to_numpy(dtype="float64")
    changed = ~np.isclose(before_values, after_values, equal_nan=True)
    return int(changed.any(axis=1).sum()), int(changed.sum())


def _changed_mask(values: pd.DataFrame, fill_value: float) -> pd.DataFrame:
    numeric = values.apply(pd.to_numeric, errors="coerce")
    changed = numeric.notna() & ~np.isclose(numeric.to_numpy(dtype="float64"), float(fill_value), equal_nan=False)
    return pd.DataFrame(changed, index=values.index, columns=values.columns)


def _set_sequence_inputs(frame: pd.DataFrame, columns: list[str], fill_value: float) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns:
        return out, 0, 0
    changed = _changed_mask(out[columns], fill_value)
    out.loc[:, columns] = float(fill_value)
    return out, int(changed.any(axis=1).sum()), int(changed.sum().sum())


def _random_sequence_dropout(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    rate: float,
    fill_value: float,
    seed: int,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns or rate <= 0:
        return out, 0, 0
    rng = np.random.default_rng(seed)
    selected = rng.random((len(out), len(columns))) < float(rate)
    changed = _changed_mask(out[columns], fill_value).to_numpy() & selected
    for index, column in enumerate(columns):
        if selected[:, index].any():
            out.loc[selected[:, index], column] = float(fill_value)
    return out, int(changed.any(axis=1).sum()), int(changed.sum())


def _temporal_sequence_block_dropout(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    block_length_months: int,
    site_history_block_rate: float,
    fill_value: float,
    seed: int,
) -> tuple[pd.DataFrame, int, int]:
    out = frame.copy()
    if not columns or block_length_months <= 0 or site_history_block_rate <= 0:
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
    changed = _changed_mask(out.loc[affected_mask, columns], fill_value)
    out.loc[affected_mask, columns] = float(fill_value)
    return out, int(changed.any(axis=1).sum()), int(changed.sum().sum())


def apply_sequence_operations(
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
        if operation_type not in SUPPORTED_OPERATIONS:
            raise ValueError(
                f"Unsupported recomputed PIPE degradation operation {operation_type!r}; "
                f"supported operations are {sorted(SUPPORTED_OPERATIONS)}"
            )
        columns = _pipe_state_variable_columns(config, str(operation.get("variable_group")), out)
        fill_value = float(operation.get("fill_value", 0.0))
        if operation_type == "set_sequence_inputs":
            out, rows, cells = _set_sequence_inputs(out, columns, fill_value)
        elif operation_type == "random_sequence_dropout":
            out, rows, cells = _random_sequence_dropout(
                out,
                columns=columns,
                rate=float(operation.get("rate", 0.0)),
                fill_value=fill_value,
                seed=effective_seed,
            )
        else:
            out, rows, cells = _temporal_sequence_block_dropout(
                out,
                columns=columns,
                block_length_months=int(operation.get("block_length_months", 1)),
                site_history_block_rate=float(operation.get("site_history_block_rate", 0.0)),
                fill_value=fill_value,
                seed=effective_seed,
            )
        affected_rows += rows
        affected_cells += cells
    return out, affected_rows, affected_cells


def seeds_for_scenario(scenario: dict[str, Any], config: dict[str, Any]) -> list[int | None]:
    if not any(operation_type in RANDOM_OPERATIONS for operation_type in operation_types(scenario)):
        return [None]
    seeds = config.get("randomization", {}).get("seeds", [0])
    return [int(seed) for seed in seeds] if seeds else [0]


def validate_sequence_scenarios(scenarios: list[dict[str, Any]]) -> None:
    for scenario in scenarios:
        unsupported = sorted(set(operation_types(scenario)) - SUPPORTED_OPERATIONS)
        if unsupported:
            raise ValueError(
                f"Scenario {scenario['scenario_id']!r} is not a PIPE state recomputation scenario; "
                f"unsupported operations: {unsupported}"
            )


def run_scenario(
    *,
    frame: pd.DataFrame,
    indices: np.ndarray,
    observed: pd.DataFrame,
    bloom_targets: pd.DataFrame,
    scenario: dict[str, Any],
    config: dict[str, Any],
    seed: int | None,
    model: Any,
    blend_weights: Any | None,
    args: argparse.Namespace,
    history_length: int,
    device: Any,
    calibrators: dict[int, Any],
    rollout_bloom_calibrators: dict[int, CalibratorRecord],
    thresholds: pd.DataFrame,
    policies: list[str],
) -> dict[str, Any]:
    degraded, affected_rows, affected_cells = apply_sequence_operations(frame, scenario, config, seed)
    affected_selected_window_rows, affected_selected_window_cells = changed_counts(
        frame,
        degraded,
        row_indices=selected_window_indices(indices, history_length),
        columns=scenario_sequence_columns(scenario, config, frame),
    )
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
        state_metrics = _add_scenario_columns(pd.DataFrame(), scenario, seed=seed, status=status)
        alert_metrics = _add_scenario_columns(pd.DataFrame(), scenario, seed=seed, status=status)
        examples = _add_scenario_columns(pd.DataFrame(), scenario, seed=seed, status=status)
        policy_metrics = _add_scenario_columns(pd.DataFrame(), scenario, seed=seed, status=status)
        backtest_rows = _add_scenario_columns(pd.DataFrame(), scenario, seed=seed, status=status)
    else:
        state_metrics = _add_scenario_columns(build_state_metrics(backtest), scenario, seed=seed, status=status)
        alert_metrics = _add_scenario_columns(build_alert_metrics(backtest), scenario, seed=seed, status=status)
        examples = _add_scenario_columns(
            build_examples(backtest, args.examples_per_group),
            scenario,
            seed=seed,
            status=status,
        )
        backtest_rows_base = compact_backtest_rows(backtest)
        backtest_rows_base = apply_bloom_calibrators(backtest_rows_base, rollout_bloom_calibrators)
        prepared_policy_rows = prepare_rows(backtest_rows_base, thresholds, policies)
        policy_metrics_base = build_metric_rows(
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
        if not policy_metrics_base.empty:
            policy_metrics_base["degradation_version"] = DEGRADATION_VERSION
        policy_metrics = policy_metrics_base
        backtest_rows = _add_scenario_columns(backtest_rows_base, scenario, seed=seed, status=status)
    return {
        "status": status,
        "reason": "",
        "affected_rows": affected_rows,
        "affected_cells": affected_cells,
        "affected_selected_window_rows": affected_selected_window_rows,
        "affected_selected_window_cells": affected_selected_window_cells,
        "state_metrics": state_metrics,
        "alert_metrics": alert_metrics,
        "policy_metrics": policy_metrics,
        "examples": examples,
        "backtest_rows": backtest_rows,
    }


def build_report(
    *,
    args: argparse.Namespace,
    config: dict[str, Any],
    summary: pd.DataFrame,
    state_metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    policy_metrics: pd.DataFrame,
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
    policy_headline = (
        policy_metrics[
            (policy_metrics["split"] == "test")
            & (policy_metrics["source_id"] == "all")
            & (policy_metrics["alert_policy"].isin(args.policies))
        ].copy()
        if not policy_metrics.empty
        else pd.DataFrame()
    )
    alert_headline = (
        alert_metrics[
            (alert_metrics["group_type"] == "overall")
            & (alert_metrics["source_id"] == "all")
        ].copy()
        if not alert_metrics.empty
        else pd.DataFrame()
    )

    lines = [
        "# Recomputed PIPE/GRU-D State Degradation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report recomputes PIPE/GRU-D rollout scores after controlled degradation of PIPE sequence inputs.",
        "It does not degrade raw panel predictors directly; raw-predictor degradation requires rebuilding fuzzy states and sequence datasets upstream.",
        "",
        "## Configuration",
        "",
        f"- Config: `{args.config}`",
        f"- Scenario set: `{args.scenario_set}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- History length: `{history_length}`",
        f"- Rollout horizon: `{args.rollout_horizon}` month(s)",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- Max origins cap: `{args.max_origins}`",
        f"- Calibrated bloom horizons available: `{calibrated_horizons}`",
        f"- Rollout bloom calibrator horizons available: `{args.rollout_bloom_calibrator_horizons}`",
        f"- Policies: `{args.policies}`",
        f"- Requested policy evaluation splits: `{args.evaluation_splits}`",
        f"- Observed policy metric splits: `{sorted(policy_metrics['split'].dropna().astype(str).unique()) if not policy_metrics.empty else []}`",
        f"- Default downstream policy context: `{default_policy}`",
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
            "## Scenario Summary",
            "",
            "| scenario | status | seed | affected frame rows | affected frame cells | affected selected-window rows | affected selected-window cells | rollout rows | policy metric rows |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(summary.sort_values(["scenario_id", "seed"], na_position="first")):
        seed = "NA" if pd.isna(row.seed) else str(int(row.seed))
        lines.append(
            f"| `{row.scenario_id}` | `{row.scenario_status}` | {seed} | "
            f"{_format_int(int(row.affected_rows))} | {_format_int(int(row.affected_cells))} | "
            f"{_format_int(int(row.affected_selected_window_rows))} | "
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
            "- Labels are fixed and come from the undegraded sequence/split surfaces.",
            "- Only PIPE sequence input columns are degraded in this evaluator.",
            "- Seasonality columns are preserved by the configured scenario set.",
            "- Raw-predictor family ablations remain queued for an upstream fuzzy-state rebuild.",
            "- Degraded outputs are stress-test evidence, not official environmental alerts.",
            "",
            "## Outputs",
            "",
            f"- State metrics: `{args.state_metrics}`",
            f"- Alert metrics: `{args.alert_metrics}`",
            f"- Policy metrics: `{args.policy_metrics}`",
            f"- Summary: `{args.summary}`",
            f"- Examples: `{args.examples}`",
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
    inputs = [args.config, args.sequences, args.model, args.thresholds]
    if args.splits.exists():
        inputs.append(args.splits)
    if args.model_manifest.exists():
        inputs.append(args.model_manifest)
    inputs.extend(info.path for info in calibrators.values())
    inputs.extend(record.path for record in args.rollout_bloom_calibrators.values())
    outputs = [args.state_metrics, args.alert_metrics, args.policy_metrics, args.summary, args.examples, args.report]
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
            "scenario_config_protocol": config.get("protocol", {}),
        },
        "row_counts": {
            "selected_origins": int(selected_origins),
            "availability_summary_rows": int(len(availability_summary)),
            "summary_rows": int(len(summary)),
            "state_metric_rows": int(len(state_metrics)),
            "alert_metric_rows": int(len(alert_metrics)),
            "policy_metric_rows": int(len(policy_metrics)),
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
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--rollout-calibrator-dir", type=Path, default=DEFAULT_ROLLOUT_CALIBRATOR_DIR)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--state-metrics", type=Path, default=None)
    parser.add_argument("--alert-metrics", type=Path, default=None)
    parser.add_argument("--policy-metrics", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--examples", type=Path, default=None)
    parser.add_argument("--backtest-rows", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--output-name",
        type=_safe_output_name,
        default=None,
        help="Write named outputs without overriding default artifacts.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--scenario-set", default="pipe_state_recompute_smoke")
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
    if args.min_policy_rows < 1:
        raise ValueError("--min-policy-rows must be >= 1")

    config = read_config(args.config)
    validate_scenarios(config)
    scenarios = select_scenarios(config, args)
    validate_sequence_scenarios(scenarios)

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

    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_window_frame(frame)
    observed = observed_state_frame(frame)
    print(f"sequence rows={len(frame):,}; observed states={len(observed):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

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
    print(f"selected backtest origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

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
            summary_rows.append(
                {
                    **_scenario_metadata(scenario, seed=seed, status=str(outputs["status"])),
                    "reason": str(outputs["reason"]),
                    "selected_origins": int(len(indices)),
                    "evaluated_rollout_rows": int(len(backtest_rows)),
                    "state_metric_rows": int(len(state_metrics)),
                    "alert_metric_rows": int(len(alert_metrics)),
                    "policy_metric_rows": int(len(policy_metrics)),
                    "example_rows": int(len(examples)),
                    "backtest_row_rows": int(len(backtest_rows)),
                    "affected_rows": int(outputs["affected_rows"]),
                    "affected_cells": int(outputs["affected_cells"]),
                    "affected_selected_window_rows": int(outputs["affected_selected_window_rows"]),
                    "affected_selected_window_cells": int(outputs["affected_selected_window_cells"]),
                    "operation_types": ",".join(operation_types(scenario)),
                }
            )
            print(f"finished {scenario['scenario_id']} seed={seed}; elapsed={_elapsed(started_monotonic)}", flush=True)

    state_metrics_all = pd.concat(state_metric_parts, ignore_index=True) if state_metric_parts else pd.DataFrame()
    alert_metrics_all = pd.concat(alert_metric_parts, ignore_index=True) if alert_metric_parts else pd.DataFrame()
    policy_metrics_raw = pd.concat(policy_metric_parts, ignore_index=True) if policy_metric_parts else pd.DataFrame()
    policy_metrics_all = add_control_deltas(policy_metrics_raw)
    examples_all = pd.concat(example_parts, ignore_index=True) if example_parts else pd.DataFrame()
    backtest_rows_all = pd.concat(backtest_row_parts, ignore_index=True) if backtest_row_parts else pd.DataFrame()
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
