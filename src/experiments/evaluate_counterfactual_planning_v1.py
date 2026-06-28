#!/usr/bin/env python
"""Evaluate raw-proxy, support-aware counterfactual planning scenarios."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import yaml

from src.experiments.evaluate_counterfactual_planning import (
    NON_CAUSAL_GUARDRAIL,
    _binary_metric_values,
    _file_record,
    _format_float,
    _format_int,
    _manifest_path,
    _parse_csv_list,
    _sha256_file,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
    output_paths,
    planning_horizons,
    read_table,
    require_columns,
)
from src.fuzzy.expert import build_expert_state


PLANNING_VERSION = "counterfactual_planning_raw_proxy_v1"
DEFAULT_CONFIG = Path("configs/counterfactual_planning_v1.yaml")
DEFAULT_PLANNING_ROWS = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_VARIABLES_CONFIG = Path("configs/variables.yaml")
DEFAULT_OUTPUT_DIR = Path("reports/planning")
DEFAULT_OUTPUT_NAME = "counterfactual_raw_proxy_v1"
KEY_COLUMNS = ["source_id", "site_id", "split", "origin_year_month"]
ORIGIN_KEY_COLUMNS = ["source_id", "site_id", "origin_year_month"]
PANEL_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
EXPERT_KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
STATE_COLUMNS = ["yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T"]
METRIC_GROUP_COLUMNS = [
    "scenario_family",
    "scenario_id",
    "split",
    "horizon_months",
    "source_id",
]


@dataclass(frozen=True)
class RawOperation:
    variable: str
    panel_column: str
    operation: str
    value: float


@dataclass(frozen=True)
class RawScenarioSpec:
    scenario_id: str
    scenario_family: str
    action_type: str
    operations: tuple[RawOperation, ...]
    relative_cost: float
    scenario_status: str
    infeasible_reason: str


def load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a YAML mapping: {path}")
    if payload.get("schema_version") != 1:
        raise ValueError("Only counterfactual planning v1 schema_version 1 is supported")
    return payload


def variable_ranges(path: Path) -> dict[str, tuple[float | None, float | None]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Variables config must be a YAML mapping: {path}")
    variables = payload.get("canonical_variables", {})
    ranges: dict[str, tuple[float | None, float | None]] = {}
    for variable, spec in variables.items():
        if not isinstance(spec, dict):
            continue
        plausible = spec.get("plausible_range", {})
        if not isinstance(plausible, dict):
            continue
        min_value = plausible.get("min")
        max_value = plausible.get("max")
        ranges[str(variable)] = (
            float(min_value) if min_value is not None else None,
            float(max_value) if max_value is not None else None,
        )
    return ranges


def _cost_budget(config: dict[str, Any], planning_mode: str) -> float:
    budgets = config.get("constraints", {}).get("max_relative_cost", {})
    return float(budgets.get(planning_mode, float("inf")))


def _lambda_cost(config: dict[str, Any], planning_mode: str) -> float:
    return float(config.get("objective", {}).get("planning_modes", {}).get(planning_mode, {}).get("lambda_cost", 0.05))


def build_raw_scenarios(config: dict[str, Any], *, planning_mode: str) -> list[RawScenarioSpec]:
    family = config.get("scenario_family", {})
    if not bool(family.get("enabled", True)):
        raise ValueError("scenario_family is disabled")
    family_name = str(family.get("name", "raw_proxy_support_grid"))
    budget = _cost_budget(config, planning_mode)
    scenarios: list[RawScenarioSpec] = []
    for raw in family.get("scenarios", []):
        if not isinstance(raw, dict):
            raise ValueError("Each scenario must be a mapping")
        scenario_id = str(raw["scenario_id"])
        operations = tuple(
            RawOperation(
                variable=str(operation["variable"]),
                panel_column=str(operation["panel_column"]),
                operation=str(operation["operation"]),
                value=float(operation["value"]),
            )
            for operation in raw.get("operations", [])
        )
        relative_cost = float(raw.get("relative_cost", 0.0))
        scenario_status = "completed" if relative_cost <= budget else "infeasible"
        reason = "" if scenario_status == "completed" else "cost_exceeds_budget"
        scenarios.append(
            RawScenarioSpec(
                scenario_id=scenario_id,
                scenario_family=family_name,
                action_type=str(raw.get("action_type", scenario_id)),
                operations=operations,
                relative_cost=relative_cost,
                scenario_status=scenario_status,
                infeasible_reason=reason,
            )
        )
    if not any(scenario.scenario_id == "no_action" for scenario in scenarios):
        raise ValueError("The raw-proxy scenario grid must include no_action")
    return scenarios


def prepare_planning_rows(
    rows: pd.DataFrame,
    config: dict[str, Any],
    *,
    evaluation_splits: list[str],
    source_ids: list[str] | None,
    max_rows_per_split: int | None,
) -> pd.DataFrame:
    require_columns(rows, KEY_COLUMNS, "planning rows")
    frame = rows.copy()
    frame = frame[frame["split"].astype(str).isin(evaluation_splits)].copy()
    if source_ids is not None:
        frame = frame[frame["source_id"].astype(str).isin(source_ids)].copy()
    if max_rows_per_split is not None:
        frame = (
            frame.sort_values(KEY_COLUMNS, kind="mergesort")
            .groupby("split", group_keys=False, sort=False)
            .head(max_rows_per_split)
            .copy()
        )
    if frame.empty:
        raise ValueError("No planning rows remain after split/source filtering")
    if "horizon_months" in frame.columns:
        frame["horizon_months"] = pd.to_numeric(frame["horizon_months"], errors="raise").astype(int)
        return frame.reset_index(drop=True)
    if "rollout_horizon_months" in frame.columns:
        frame["horizon_months"] = pd.to_numeric(frame["rollout_horizon_months"], errors="raise").astype(int)
        return frame.reset_index(drop=True)
    expanded = []
    for horizon in planning_horizons(config):
        horizon_frame = frame.copy()
        horizon_frame["horizon_months"] = int(horizon)
        expanded.append(horizon_frame)
    return pd.concat(expanded, ignore_index=True)


def _origin_rows(planning_rows: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    panel_columns = [column for column in panel.columns if column not in {"split"}]
    origins = planning_rows[ORIGIN_KEY_COLUMNS].drop_duplicates().copy()
    panel_frame = panel[panel_columns].copy()
    merged = origins.merge(
        panel_frame,
        left_on=["source_id", "site_id", "origin_year_month"],
        right_on=["source_id", "site_id", "year_month"],
        how="left",
    )
    merged["year_month"] = merged["year_month"].fillna(merged["origin_year_month"])
    if "site_id_source" not in merged.columns:
        merged["site_id_source"] = merged["source_id"].astype(str) + ":" + merged["site_id"].astype(str)
    else:
        merged["site_id_source"] = merged["site_id_source"].fillna(
            merged["source_id"].astype(str) + ":" + merged["site_id"].astype(str)
        )
    if "site_name" not in merged.columns:
        merged["site_name"] = merged["site_id"].astype(str)
    else:
        merged["site_name"] = merged["site_name"].fillna(merged["site_id"].astype(str))
    return merged


def _refresh_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if {"mean_TN_ugL", "mean_TP_ugL"}.issubset(out.columns):
        denominator = pd.to_numeric(out["mean_TP_ugL"], errors="coerce").replace(0.0, np.nan)
        out["TN_TP_ratio"] = pd.to_numeric(out["mean_TN_ugL"], errors="coerce") / denominator
    return out


def _state_for_origins(origins: pd.DataFrame) -> pd.DataFrame:
    expert_frame = origins.copy()
    for column in EXPERT_KEY_COLUMNS:
        if column not in expert_frame.columns:
            raise ValueError(f"Origin panel rows are missing expert key column: {column}")
    state, _ = build_expert_state(expert_frame, include_trace_columns=False)
    state = state.rename(
        columns={
            "year_month": "origin_year_month",
            "yN": "raw_yN",
            "yF": "raw_yF",
            "yT": "raw_yT",
            "sigma_N": "raw_sigma_N",
            "sigma_F": "raw_sigma_F",
            "sigma_T": "raw_sigma_T",
        }
    )
    return state[
        [
            "source_id",
            "site_id",
            "origin_year_month",
            "raw_yN",
            "raw_yF",
            "raw_yT",
            "raw_sigma_N",
            "raw_sigma_F",
            "raw_sigma_T",
        ]
    ]


def support_bounds(panel: pd.DataFrame, origins: pd.DataFrame, column: str, config: dict[str, Any]) -> pd.DataFrame:
    support = config.get("constraints", {}).get("historical_support", {})
    site_cfg = support.get("site_level_quantiles", {})
    source_cfg = support.get("source_level_fallback_quantiles", {})
    min_months = int(site_cfg.get("min_observed_months", 24))
    site_lower = float(site_cfg.get("lower", 0.05))
    site_upper = float(site_cfg.get("upper", 0.95))
    source_lower = float(source_cfg.get("lower", 0.01))
    source_upper = float(source_cfg.get("upper", 0.99))

    clean = panel[["source_id", "site_id", column]].copy()
    clean[column] = pd.to_numeric(clean[column], errors="coerce")
    site_stats = (
        clean.dropna(subset=[column])
        .groupby(["source_id", "site_id"], dropna=False)[column]
        .agg(
            support_n="count",
            site_lower=lambda values: float(values.quantile(site_lower)),
            site_upper=lambda values: float(values.quantile(site_upper)),
        )
        .reset_index()
    )
    source_stats = (
        clean.dropna(subset=[column])
        .groupby("source_id", dropna=False)[column]
        .agg(
            source_lower=lambda values: float(values.quantile(source_lower)),
            source_upper=lambda values: float(values.quantile(source_upper)),
        )
        .reset_index()
    )
    out = origins[["source_id", "site_id", "origin_year_month"]].copy()
    out = out.merge(site_stats, on=["source_id", "site_id"], how="left")
    out = out.merge(source_stats, on="source_id", how="left")
    use_site = out["support_n"].fillna(0).astype(float) >= min_months
    out["support_lower"] = out["site_lower"].where(use_site, out["source_lower"])
    out["support_upper"] = out["site_upper"].where(use_site, out["source_upper"])
    out["support_scope"] = np.where(use_site, "site", "source")
    return out[["source_id", "site_id", "origin_year_month", "support_lower", "support_upper", "support_scope"]]


def build_support_lookup(
    panel: pd.DataFrame,
    origins: pd.DataFrame,
    scenarios: list[RawScenarioSpec],
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    columns = sorted({operation.panel_column for scenario in scenarios for operation in scenario.operations})
    return {column: support_bounds(panel, origins, column, config) for column in columns}


def apply_raw_scenario(
    origins: pd.DataFrame,
    support_lookup: dict[str, pd.DataFrame],
    scenario: RawScenarioSpec,
    config: dict[str, Any],
    ranges: dict[str, tuple[float | None, float | None]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = origins.copy()
    support_flags = pd.DataFrame(
        {
            "source_id": origins["source_id"],
            "site_id": origins["site_id"],
            "origin_year_month": origins["origin_year_month"],
            "support_violation": 0,
            "plausible_clip": 0,
            "support_scope": "",
        }
    )
    clip_to_plausible = bool(config.get("constraints", {}).get("clip_to_plausible_range", True))
    for operation in scenario.operations:
        if operation.panel_column not in out.columns:
            out[operation.panel_column] = np.nan
        before = pd.to_numeric(out[operation.panel_column], errors="coerce")
        if operation.operation == "multiply":
            after = before * operation.value
        elif operation.operation == "add":
            after = before + operation.value
        else:
            raise ValueError(f"Unsupported operation {operation.operation!r}")

        min_value, max_value = ranges.get(operation.variable, (None, None))
        clipped = pd.Series(False, index=out.index)
        if clip_to_plausible:
            if min_value is not None:
                clipped = clipped | (after < min_value)
                after = after.clip(lower=min_value)
            if max_value is not None:
                clipped = clipped | (after > max_value)
                after = after.clip(upper=max_value)
        bounds = support_lookup[operation.panel_column]
        lower = pd.to_numeric(bounds["support_lower"], errors="coerce")
        upper = pd.to_numeric(bounds["support_upper"], errors="coerce")
        outside_support = (after < lower) | (after > upper)
        outside_support = outside_support.fillna(False)
        support_flags["support_violation"] = (
            support_flags["support_violation"].astype(int) | outside_support.astype(int)
        )
        support_flags["plausible_clip"] = support_flags["plausible_clip"].astype(int) | clipped.fillna(False).astype(int)
        support_flags["support_scope"] = np.where(
            support_flags["support_scope"].astype(str) == "",
            bounds["support_scope"].astype(str),
            support_flags["support_scope"].astype(str),
        )
        out[operation.panel_column] = after

    out = _refresh_derived_columns(out)
    return out, support_flags


def compute_irc_score(frame: pd.DataFrame, prefix: str) -> pd.Series:
    y_n = pd.to_numeric(frame[f"{prefix}_yN"], errors="raise")
    y_f = pd.to_numeric(frame[f"{prefix}_yF"], errors="raise")
    y_t = pd.to_numeric(frame[f"{prefix}_yT"], errors="raise")
    return ((y_n + (1.0 - y_f) + y_t) / 3.0).clip(0.0, 1.0)


def compute_bloom_proxy(frame: pd.DataFrame, irc_score: pd.Series, prefix: str) -> pd.Series:
    y_t = pd.to_numeric(frame[f"{prefix}_yT"], errors="raise")
    return (0.5 * y_t + 0.5 * irc_score).clip(0.0, 1.0)


def compute_uncertainty(frame: pd.DataFrame, prefix: str) -> pd.Series:
    columns = [f"{prefix}_sigma_N", f"{prefix}_sigma_F", f"{prefix}_sigma_T"]
    return frame[columns].apply(pd.to_numeric, errors="coerce").mean(axis=1).fillna(0.0).clip(lower=0.0)


def objective_components(
    baseline_irc: float,
    scenario_irc: float,
    baseline_bloom: float,
    scenario_bloom: float,
    baseline_uncertainty: float,
    scenario_uncertainty: float,
    relative_cost: float,
    support_violation: float,
    config: dict[str, Any],
    *,
    planning_mode: str,
) -> dict[str, float]:
    objective_config = config.get("objective", {})
    weights = objective_config.get("weights", {})
    w_irc = float(weights.get("irc_alert_risk_reduction", 0.6))
    w_bloom = float(weights.get("bloom_probability_reduction", 0.4))
    lambda_cost = _lambda_cost(config, planning_mode)
    lambda_uncertainty = float(objective_config.get("lambda_uncertainty", 0.10))
    lambda_support = float(objective_config.get("lambda_support", 0.05))
    irc_reduction = baseline_irc - scenario_irc
    bloom_reduction = baseline_bloom - scenario_bloom
    uncertainty_delta = scenario_uncertainty - baseline_uncertainty
    weighted_risk_reduction = (w_irc * irc_reduction) + (w_bloom * bloom_reduction)
    support_penalty = lambda_support * max(0.0, support_violation)
    objective_value = (
        weighted_risk_reduction
        - (lambda_cost * relative_cost)
        - (lambda_uncertainty * max(0.0, uncertainty_delta))
        - support_penalty
    )
    baseline_risk = (w_irc * baseline_irc) + (w_bloom * baseline_bloom)
    return {
        "irc_reduction": irc_reduction,
        "bloom_reduction": bloom_reduction,
        "risk_reduction_absolute": weighted_risk_reduction,
        "risk_reduction_relative": weighted_risk_reduction / baseline_risk if baseline_risk else float("nan"),
        "uncertainty_delta": uncertainty_delta,
        "support_penalty": support_penalty,
        "objective_value": objective_value,
    }


def evaluate_scenario(
    planning_rows: pd.DataFrame,
    origins: pd.DataFrame,
    support_lookup: dict[str, pd.DataFrame],
    baseline_state: pd.DataFrame,
    scenario: RawScenarioSpec,
    config: dict[str, Any],
    ranges: dict[str, tuple[float | None, float | None]],
    *,
    planning_mode: str,
) -> pd.DataFrame:
    scenario_origins, support_flags = apply_raw_scenario(origins, support_lookup, scenario, config, ranges)
    scenario_state = _state_for_origins(scenario_origins).rename(
        columns={
            "raw_yN": "scenario_yN",
            "raw_yF": "scenario_yF",
            "raw_yT": "scenario_yT",
            "raw_sigma_N": "scenario_sigma_N",
            "raw_sigma_F": "scenario_sigma_F",
            "raw_sigma_T": "scenario_sigma_T",
        }
    )
    base = baseline_state.rename(
        columns={
            "raw_yN": "baseline_yN",
            "raw_yF": "baseline_yF",
            "raw_yT": "baseline_yT",
            "raw_sigma_N": "baseline_sigma_N",
            "raw_sigma_F": "baseline_sigma_F",
            "raw_sigma_T": "baseline_sigma_T",
        }
    )
    keys = ["source_id", "site_id", "origin_year_month"]
    merged = planning_rows[KEY_COLUMNS + ["horizon_months"]].copy()
    merged = merged.merge(base, on=keys, how="left")
    merged = merged.merge(scenario_state, on=keys, how="left")
    merged = merged.merge(support_flags, on=keys, how="left")

    baseline_irc = compute_irc_score(merged, "baseline")
    scenario_irc = compute_irc_score(merged, "scenario")
    baseline_bloom = compute_bloom_proxy(merged, baseline_irc, "baseline")
    scenario_bloom = compute_bloom_proxy(merged, scenario_irc, "scenario")
    baseline_uncertainty = compute_uncertainty(merged, "baseline")
    scenario_uncertainty = compute_uncertainty(merged, "scenario")
    support_violation = pd.to_numeric(merged["support_violation"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

    out = merged[KEY_COLUMNS + ["horizon_months"]].copy()
    out["planning_version"] = PLANNING_VERSION
    out["scenario_family"] = scenario.scenario_family
    out["scenario_id"] = scenario.scenario_id
    out["action_type"] = scenario.action_type
    out["scenario_status"] = scenario.scenario_status
    out["infeasible_reason"] = scenario.infeasible_reason
    out["relative_cost"] = scenario.relative_cost
    out["support_violation"] = support_violation.to_numpy()
    out["plausible_clip"] = pd.to_numeric(merged["plausible_clip"], errors="coerce").fillna(0).astype(int).to_numpy()
    out["baseline_irc_alert_score"] = baseline_irc.to_numpy()
    out["scenario_irc_alert_score"] = scenario_irc.to_numpy()
    out["baseline_bloom_probability"] = baseline_bloom.to_numpy()
    out["scenario_bloom_probability"] = scenario_bloom.to_numpy()
    out["baseline_uncertainty"] = baseline_uncertainty.to_numpy()
    out["scenario_uncertainty"] = scenario_uncertainty.to_numpy()
    for column in ["actual_irc_alert", "bloom_h"]:
        if column in planning_rows.columns:
            out[column] = planning_rows[column].to_numpy()
    components = [
        objective_components(
            float(base_irc),
            float(scen_irc),
            float(base_bloom),
            float(scen_bloom),
            float(base_uncertainty),
            float(scen_uncertainty),
            scenario.relative_cost,
            float(support),
            config,
            planning_mode=planning_mode,
        )
        for base_irc, scen_irc, base_bloom, scen_bloom, base_uncertainty, scen_uncertainty, support in zip(
            baseline_irc,
            scenario_irc,
            baseline_bloom,
            scenario_bloom,
            baseline_uncertainty,
            scenario_uncertainty,
            support_violation,
            strict=True,
        )
    ]
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(components)], axis=1)


def build_metric_rows(scenario_rows: pd.DataFrame, *, alert_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in scenario_rows.groupby(METRIC_GROUP_COLUMNS, dropna=False, sort=True):
        valid_group = group[group["scenario_status"] == "completed"]
        metric_group = valid_group if not valid_group.empty else group
        record: dict[str, Any] = {
            "planning_version": PLANNING_VERSION,
            "scenario_family": group["scenario_family"].iloc[0],
            "scenario_id": group["scenario_id"].iloc[0],
            "action_type": group["action_type"].iloc[0],
            "scenario_status": group["scenario_status"].iloc[0],
            "infeasible_reason": group["infeasible_reason"].iloc[0],
            "split": group["split"].iloc[0],
            "horizon_months": int(group["horizon_months"].iloc[0]),
            "source_id": group["source_id"].iloc[0],
            "rows": int(len(group)),
            "feasible_rows": int(len(valid_group)),
            "infeasible_rows": int(len(group) - len(valid_group)),
            "support_violation_rows": int(group["support_violation"].sum()),
            "plausible_clip_rows": int(group["plausible_clip"].sum()),
            "relative_cost": float(group["relative_cost"].iloc[0]),
        }
        for column in [
            "baseline_irc_alert_score",
            "scenario_irc_alert_score",
            "baseline_bloom_probability",
            "scenario_bloom_probability",
            "baseline_uncertainty",
            "scenario_uncertainty",
            "irc_reduction",
            "bloom_reduction",
            "risk_reduction_absolute",
            "risk_reduction_relative",
            "uncertainty_delta",
            "support_penalty",
            "objective_value",
        ]:
            record[column] = float(metric_group[column].mean()) if not metric_group.empty else float("nan")
        record["support_violation_rate"] = (
            float(metric_group["support_violation"].mean()) if not metric_group.empty else float("nan")
        )
        if "actual_irc_alert" in metric_group.columns:
            record.update(
                _binary_metric_values(metric_group["actual_irc_alert"], metric_group["scenario_irc_alert_score"], alert_threshold)
            )
        else:
            record.update({"alert_rate": float("nan"), "precision": float("nan"), "recall": float("nan"), "f2": float("nan"), "mcc": float("nan")})
        rows.append(record)
    return pd.DataFrame(rows)


def pareto_front(summary: pd.DataFrame) -> pd.Series:
    feasible = summary["scenario_status"] == "completed"
    out = pd.Series(False, index=summary.index)
    candidates = summary[feasible]
    for index, row in candidates.iterrows():
        dominated = (
            (candidates["risk_reduction_absolute"] >= row["risk_reduction_absolute"])
            & (candidates["relative_cost"] <= row["relative_cost"])
            & (candidates["support_violation_rate"] <= row["support_violation_rate"])
            & (
                (candidates["risk_reduction_absolute"] > row["risk_reduction_absolute"])
                | (candidates["relative_cost"] < row["relative_cost"])
                | (candidates["support_violation_rate"] < row["support_violation_rate"])
            )
        )
        out.loc[index] = not bool(dominated.any())
    return out


def build_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    summary = (
        metrics.groupby(["scenario_family", "scenario_id", "action_type"], dropna=False, sort=True)
        .agg(
            scenario_status=("scenario_status", "first"),
            infeasible_reason=("infeasible_reason", "first"),
            metric_rows=("scenario_id", "size"),
            rows=("rows", "sum"),
            feasible_rows=("feasible_rows", "sum"),
            infeasible_rows=("infeasible_rows", "sum"),
            support_violation_rows=("support_violation_rows", "sum"),
            plausible_clip_rows=("plausible_clip_rows", "sum"),
            relative_cost=("relative_cost", "first"),
            baseline_irc_alert_score=("baseline_irc_alert_score", "mean"),
            scenario_irc_alert_score=("scenario_irc_alert_score", "mean"),
            baseline_bloom_probability=("baseline_bloom_probability", "mean"),
            scenario_bloom_probability=("scenario_bloom_probability", "mean"),
            risk_reduction_absolute=("risk_reduction_absolute", "mean"),
            risk_reduction_relative=("risk_reduction_relative", "mean"),
            uncertainty_delta=("uncertainty_delta", "mean"),
            support_penalty=("support_penalty", "mean"),
            support_violation_rate=("support_violation_rate", "mean"),
            objective_value=("objective_value", "mean"),
        )
        .reset_index()
    )
    summary["pareto_front"] = pareto_front(summary)
    feasible_mask = summary["scenario_status"] == "completed"
    summary["pareto_rank"] = np.nan
    summary.loc[feasible_mask, "pareto_rank"] = (
        summary.loc[feasible_mask, "objective_value"].rank(method="dense", ascending=False).astype(int)
    )
    return summary.sort_values(["scenario_status", "pareto_rank", "scenario_id"], na_position="last").reset_index(drop=True)


def build_pareto(summary: pd.DataFrame) -> pd.DataFrame:
    return summary[summary["pareto_front"]].sort_values(
        ["objective_value", "risk_reduction_absolute"], ascending=[False, False], kind="mergesort"
    )


def build_examples(scenario_rows: pd.DataFrame, *, examples_per_scenario: int) -> pd.DataFrame:
    columns = [
        *KEY_COLUMNS,
        "horizon_months",
        "scenario_id",
        "action_type",
        "scenario_status",
        "infeasible_reason",
        "relative_cost",
        "support_violation",
        "plausible_clip",
        "baseline_irc_alert_score",
        "scenario_irc_alert_score",
        "baseline_bloom_probability",
        "scenario_bloom_probability",
        "risk_reduction_absolute",
        "support_penalty",
        "objective_value",
    ]
    available = [column for column in columns if column in scenario_rows.columns]
    return (
        scenario_rows.sort_values(["scenario_id", "objective_value"], ascending=[True, False], kind="mergesort")
        .groupby("scenario_id", group_keys=False, sort=False)
        .head(examples_per_scenario)[available]
        .reset_index(drop=True)
    )


def write_report(
    path: Path,
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pareto: pd.DataFrame,
) -> None:
    completed = summary[summary["scenario_status"] == "completed"].copy()
    top = completed.sort_values("objective_value", ascending=False, kind="mergesort").head(10)
    lines = [
        "# Counterfactual Planning V1 Raw-Proxy Report",
        "",
        f"Planning version: `{PLANNING_VERSION}`.",
        "",
        "## Non-Causal Guardrail",
        "",
        NON_CAUSAL_GUARDRAIL,
        "",
        "The reported scenarios are raw-input perturbations used for simulated",
        "comparison against no action. They are not field interventions and are",
        "not official environmental recommendations.",
        "",
        "## Configuration",
        "",
        f"- Config: `{_manifest_path(args.config)}`",
        f"- Planning rows: `{_manifest_path(args.planning_rows)}`",
        f"- Monthly panel: `{_manifest_path(args.panel)}`",
        f"- Variables config: `{_manifest_path(args.variables_config)}`",
        f"- Planning mode: `{args.planning_mode}`",
        f"- Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        "",
        "## Row Counts",
        "",
        f"- Metric rows: `{_format_int(len(metrics))}`",
        f"- Scenario summaries: `{_format_int(len(summary))}`",
        f"- Pareto-front rows: `{_format_int(len(pareto))}`",
        "",
        "## Top Scenarios By Objective",
        "",
    ]
    if top.empty:
        lines.append("No completed scenarios were available for ranking.")
    else:
        lines.extend(
            [
                "| Scenario | Action | Objective | Risk reduction | Cost | Support violation | Pareto |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in top.itertuples(index=False):
            lines.append(
                "| "
                f"`{row.scenario_id}` | `{row.action_type}` | "
                f"{_format_float(row.objective_value)} | "
                f"{_format_float(row.risk_reduction_absolute)} | "
                f"{_format_float(row.relative_cost)} | "
                f"{_format_float(row.support_violation_rate)} | "
                f"{bool(row.pareto_front)} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "A positive objective means only that the raw-proxy scenario improved the",
            "configured risk-cost-uncertainty-support objective under this fuzzy-state",
            "simulation. Historical support violations are penalized and reported, not",
            "treated as causal evidence.",
        ]
    )
    _write_text_atomic("\n".join(lines), path)


def manifest_payload(
    *,
    args: argparse.Namespace,
    config: dict[str, Any],
    paths: dict[str, Path],
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pareto: pd.DataFrame,
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "status": "completed",
        "planning_version": PLANNING_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "script": {
            "path": "src/experiments/evaluate_counterfactual_planning_v1.py",
            "sha256": _sha256_file(Path("src/experiments/evaluate_counterfactual_planning_v1.py")),
        },
        "inputs": [
            {"role": "config", **_file_record(args.config)},
            {"role": "planning_rows", **_file_record(args.planning_rows)},
            {"role": "panel", **_file_record(args.panel)},
            {"role": "variables_config", **_file_record(args.variables_config)},
        ],
        "config": {
            "output_name": args.output_name,
            "output_dir": _manifest_path(args.output_dir),
            "planning_mode": args.planning_mode,
            "evaluation_splits": args.evaluation_splits,
            "source_ids": args.source_ids,
            "max_rows_per_split": args.max_rows_per_split,
            "config_phase": config.get("protocol", {}).get("phase"),
        },
        "row_counts": {
            "metric_rows": int(len(metrics)),
            "summary_rows": int(len(summary)),
            "pareto_rows": int(len(pareto)),
        },
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
        "guardrail": NON_CAUSAL_GUARDRAIL,
    }


def print_run_summary(
    *,
    args: argparse.Namespace,
    paths: dict[str, Path],
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pareto: pd.DataFrame,
) -> None:
    print("Counterfactual planning V1 completed.")
    print(f"Planning version: {PLANNING_VERSION}")
    print(f"Output name: {args.output_name}")
    print(f"Evaluation splits: {', '.join(args.evaluation_splits)}")
    print(f"Metric rows: {len(metrics):,}")
    print(f"Scenario summaries: {len(summary):,}")
    print(f"Pareto rows: {len(pareto):,}")
    print("Created files:")
    for key in ["metrics", "summary", "pareto", "examples", "report", "manifest"]:
        path = paths[key]
        size = path.stat().st_size if path.exists() else 0
        print(f"- {key}: {_manifest_path(path)} ({size:,} bytes)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--planning-rows", type=Path, default=DEFAULT_PLANNING_ROWS)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--variables-config", type=Path, default=DEFAULT_VARIABLES_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--planning-mode", default=None)
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default=None)
    parser.add_argument("--source-ids", type=_parse_csv_list, default=None)
    parser.add_argument("--max-rows-per-split", type=int, default=None)
    parser.add_argument("--examples-per-scenario", type=int, default=5)
    parser.add_argument("--alert-threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    started_at = datetime.now(timezone.utc)
    args = parse_args()
    config = load_config(args.config)
    planning_mode = args.planning_mode or str(config.get("objective", {}).get("default_planning_mode", "normal"))
    args.planning_mode = planning_mode
    if args.evaluation_splits is None:
        selection_split = str(config.get("planning_unit", {}).get("selection_split", "validation"))
        args.evaluation_splits = [selection_split]

    planning_raw = read_table(args.planning_rows)
    panel = read_table(args.panel)
    ranges = variable_ranges(args.variables_config)
    planning_rows = prepare_planning_rows(
        planning_raw,
        config,
        evaluation_splits=args.evaluation_splits,
        source_ids=args.source_ids,
        max_rows_per_split=args.max_rows_per_split,
    )
    origins = _origin_rows(planning_rows, panel)
    baseline_state = _state_for_origins(_refresh_derived_columns(origins))
    scenarios = build_raw_scenarios(config, planning_mode=planning_mode)
    support_lookup = build_support_lookup(panel, origins, scenarios, config)
    scenario_rows = pd.concat(
        [
            evaluate_scenario(
                planning_rows,
                origins,
                support_lookup,
                baseline_state,
                scenario,
                config,
                ranges,
                planning_mode=planning_mode,
            )
            for scenario in scenarios
        ],
        ignore_index=True,
    )
    metrics = build_metric_rows(scenario_rows, alert_threshold=args.alert_threshold)
    summary = build_summary(metrics)
    pareto = build_pareto(summary)
    examples = build_examples(scenario_rows, examples_per_scenario=args.examples_per_scenario)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(summary, paths["summary"])
    _write_csv_atomic(pareto, paths["pareto"])
    _write_csv_atomic(examples, paths["examples"])
    write_report(paths["report"], args=args, metrics=metrics, summary=summary, pareto=pareto)
    _write_json_atomic(
        manifest_payload(
            args=args,
            config=config,
            paths=paths,
            metrics=metrics,
            summary=summary,
            pareto=pareto,
            started_at=started_at,
        ),
        paths["manifest"],
    )
    print_run_summary(args=args, paths=paths, metrics=metrics, summary=summary, pareto=pareto)


if __name__ == "__main__":
    main()
