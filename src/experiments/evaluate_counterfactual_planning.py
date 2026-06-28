#!/usr/bin/env python
"""Evaluate minimal counterfactual planning grids on state-proxy rows."""

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import yaml


PLANNING_VERSION = "counterfactual_planning_grid_v0"
DEFAULT_CONFIG = Path("configs/counterfactual_planning.yaml")
DEFAULT_PLANNING_ROWS = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/planning")
DEFAULT_OUTPUT_NAME = "counterfactual_grid"
STATE_COLUMNS = ["x_yN", "x_yF", "x_yT"]
UNCERTAINTY_COLUMNS = ["x_sigma_N", "x_sigma_F", "x_sigma_T"]
KEY_COLUMNS = ["source_id", "site_id", "split", "origin_year_month"]
METRIC_GROUP_COLUMNS = [
    "scenario_family",
    "scenario_id",
    "split",
    "horizon_months",
    "source_id",
]
NON_CAUSAL_GUARDRAIL = (
    "Counterfactual planning is simulation-based decision support, not field "
    "causality, and not official environmental advice."
)


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    scenario_family: str
    action_type: str
    x_yN_offset: float
    x_yF_offset: float
    relative_cost: float
    scenario_status: str
    infeasible_reason: str


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


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int | float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{int(value):,}"


def _slug_float(value: float) -> str:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "0"
    prefix = "m" if value < 0 else "p"
    return prefix + f"{abs(value):.3f}".replace(".", "p").rstrip("0").rstrip("p")


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a YAML mapping: {path}")
    if payload.get("schema_version") != 1:
        raise ValueError("Only counterfactual planning config schema_version 1 is supported")
    return payload


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table extension for {path}; expected .parquet or .csv")


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {
        "metrics": output_dir / f"{output_name}_metrics.csv",
        "summary": output_dir / f"{output_name}_summary.csv",
        "pareto": output_dir / f"{output_name}_pareto.csv",
        "examples": output_dir / f"{output_name}_examples.csv",
        "report": output_dir / f"{output_name}_report.md",
        "manifest": output_dir / f"{output_name}_manifest.json",
    }


def require_columns(frame: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def planning_horizons(config: dict[str, Any]) -> list[int]:
    unit = config.get("planning_unit", {})
    horizons = unit.get("horizons_months", [1, 2, 3])
    out = [int(value) for value in horizons]
    if not out:
        raise ValueError("planning_unit.horizons_months must contain at least one horizon")
    return out


def prepare_planning_rows(
    rows: pd.DataFrame,
    config: dict[str, Any],
    *,
    evaluation_splits: list[str],
    source_ids: list[str] | None,
    max_rows_per_split: int | None,
) -> pd.DataFrame:
    require_columns(rows, [*KEY_COLUMNS, *STATE_COLUMNS], "planning rows")
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

    horizons = planning_horizons(config)
    expanded = []
    for horizon in horizons:
        horizon_frame = frame.copy()
        horizon_frame["horizon_months"] = int(horizon)
        expanded.append(horizon_frame)
    return pd.concat(expanded, ignore_index=True)


def _state_offsets(config: dict[str, Any], column: str) -> list[float]:
    channels = config.get("scenario_spaces", {}).get("state_proxy", {}).get("channels", {})
    values = channels.get(column, {}).get("absolute_offsets", [0.0])
    offsets = [float(value) for value in values]
    if 0.0 not in offsets:
        offsets.insert(0, 0.0)
    return sorted(set(offsets))


def _action_type(x_yN_offset: float, x_yF_offset: float) -> str:
    has_nutrient = not math.isclose(x_yN_offset, 0.0, abs_tol=1e-12)
    has_clarity = not math.isclose(x_yF_offset, 0.0, abs_tol=1e-12)
    if has_nutrient and has_clarity:
        return "combined_nutrient_clarity"
    if has_nutrient:
        return "nutrient_reduction_tp"
    if has_clarity:
        return "clarity_improvement"
    return "no_action"


def _state_proxy_cost(config: dict[str, Any], x_yN_offset: float, x_yF_offset: float) -> float:
    actions = config.get("proxy_actions", {})
    unit = float(config.get("state_proxy_cost_unit", 0.05))
    if unit <= 0:
        raise ValueError("state_proxy_cost_unit must be positive when provided")
    cost = 0.0
    if not math.isclose(x_yN_offset, 0.0, abs_tol=1e-12):
        cost += abs(x_yN_offset) / unit * float(actions.get("nutrient_reduction_tp", {}).get("relative_unit_cost", 1.0))
    if not math.isclose(x_yF_offset, 0.0, abs_tol=1e-12):
        cost += abs(x_yF_offset) / unit * float(actions.get("clarity_improvement", {}).get("relative_unit_cost", 0.7))
    if (
        not math.isclose(x_yN_offset, 0.0, abs_tol=1e-12)
        and not math.isclose(x_yF_offset, 0.0, abs_tol=1e-12)
    ):
        cost += float(actions.get("combined_nutrient_clarity", {}).get("relative_coordination_cost", 0.2))
    return float(cost)


def _cost_budget(config: dict[str, Any], planning_mode: str) -> float:
    budgets = config.get("constraints", {}).get("max_relative_cost", {})
    return float(budgets.get(planning_mode, float("inf")))


def build_state_grid_scenarios(config: dict[str, Any], *, planning_mode: str) -> list[ScenarioSpec]:
    family = config.get("scenario_families", {}).get("minimal_state_grid", {})
    if not bool(family.get("enabled", True)):
        raise ValueError("scenario_families.minimal_state_grid is disabled")
    include_actions = set(family.get("include_actions", ["no_action"]))
    max_nonzero = int(family.get("max_combined_nonzero_offsets", 2))
    budget = _cost_budget(config, planning_mode)
    scenarios: list[ScenarioSpec] = []
    seen: set[str] = set()
    for x_yN_offset in _state_offsets(config, "x_yN"):
        for x_yF_offset in _state_offsets(config, "x_yF"):
            nonzero_offsets = int(not math.isclose(x_yN_offset, 0.0, abs_tol=1e-12)) + int(
                not math.isclose(x_yF_offset, 0.0, abs_tol=1e-12)
            )
            if nonzero_offsets > max_nonzero:
                continue
            action_type = _action_type(x_yN_offset, x_yF_offset)
            if action_type not in include_actions:
                continue
            if action_type == "no_action":
                scenario_id = "no_action"
            else:
                scenario_id = f"state_yN_{_slug_float(x_yN_offset)}_yF_{_slug_float(x_yF_offset)}"
            if scenario_id in seen:
                continue
            seen.add(scenario_id)
            relative_cost = _state_proxy_cost(config, x_yN_offset, x_yF_offset)
            scenario_status = "completed" if relative_cost <= budget else "infeasible"
            reason = "" if scenario_status == "completed" else "cost_exceeds_budget"
            scenarios.append(
                ScenarioSpec(
                    scenario_id=scenario_id,
                    scenario_family="minimal_state_grid",
                    action_type=action_type,
                    x_yN_offset=float(x_yN_offset),
                    x_yF_offset=float(x_yF_offset),
                    relative_cost=relative_cost,
                    scenario_status=scenario_status,
                    infeasible_reason=reason,
                )
            )
    if not any(scenario.scenario_id == "no_action" for scenario in scenarios):
        raise ValueError("The state grid must include a no_action scenario")
    return sorted(scenarios, key=lambda item: (item.action_type != "no_action", item.scenario_id))


def irc_weights(config: dict[str, Any]) -> tuple[float, float, float]:
    weights = config.get("risk_estimator", {}).get("irc_weights", {})
    alpha = float(weights.get("alpha", 1.0))
    beta = float(weights.get("beta", 1.0))
    gamma = float(weights.get("gamma", 1.0))
    if alpha + beta + gamma <= 0:
        raise ValueError("IRC weights must sum to a positive value")
    return alpha, beta, gamma


def compute_irc_score(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    alpha, beta, gamma = irc_weights(config)
    y_n = pd.to_numeric(frame["x_yN"], errors="raise")
    y_f = pd.to_numeric(frame["x_yF"], errors="raise")
    y_t = pd.to_numeric(frame["x_yT"], errors="raise")
    score = (alpha * y_n + beta * (1.0 - y_f) + gamma * y_t) / (alpha + beta + gamma)
    return score.clip(0.0, 1.0)


def compute_bloom_proxy(frame: pd.DataFrame, irc_score: pd.Series) -> pd.Series:
    trophic_state = pd.to_numeric(frame["x_yT"], errors="raise").clip(0.0, 1.0)
    return (0.5 * trophic_state + 0.5 * irc_score).clip(0.0, 1.0)


def compute_uncertainty(frame: pd.DataFrame) -> pd.Series:
    available = [column for column in UNCERTAINTY_COLUMNS if column in frame.columns]
    if not available:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return frame[available].apply(pd.to_numeric, errors="coerce").mean(axis=1).fillna(0.0).clip(lower=0.0)


def apply_state_scenario(frame: pd.DataFrame, scenario: ScenarioSpec, config: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    out["x_yN_before_clip"] = pd.to_numeric(out["x_yN"], errors="raise") + scenario.x_yN_offset
    out["x_yF_before_clip"] = pd.to_numeric(out["x_yF"], errors="raise") + scenario.x_yF_offset
    clip_enabled = bool(config.get("constraints", {}).get("state_channels_clip_to_unit_interval", True))
    if clip_enabled:
        out["x_yN"] = out["x_yN_before_clip"].clip(0.0, 1.0)
        out["x_yF"] = out["x_yF_before_clip"].clip(0.0, 1.0)
    else:
        out["x_yN"] = out["x_yN_before_clip"]
        out["x_yF"] = out["x_yF_before_clip"]
    clipped = (out["x_yN"] != out["x_yN_before_clip"]) | (out["x_yF"] != out["x_yF_before_clip"])
    out["state_clipped"] = clipped.astype(int)
    return out


def _binary_metric_values(actual: pd.Series, score: pd.Series, threshold: float) -> dict[str, float]:
    valid = actual.notna() & score.notna()
    if not valid.any():
        return {"alert_rate": float("nan"), "precision": float("nan"), "recall": float("nan"), "f2": float("nan"), "mcc": float("nan")}
    y_true = actual.loc[valid].astype(int).to_numpy()
    y_pred = (score.loc[valid].astype(float).to_numpy() >= threshold).astype(int)
    tp = float(((y_true == 1) & (y_pred == 1)).sum())
    fp = float(((y_true == 0) & (y_pred == 1)).sum())
    fn = float(((y_true == 1) & (y_pred == 0)).sum())
    tn = float(((y_true == 0) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    beta2 = 4.0
    f2_denominator = beta2 * precision + recall
    f2 = (1.0 + beta2) * precision * recall / f2_denominator if f2_denominator else float("nan")
    mcc_denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn) - (fp * fn)) / mcc_denominator if mcc_denominator else float("nan")
    return {
        "alert_rate": float(y_pred.mean()),
        "precision": precision,
        "recall": recall,
        "f2": f2,
        "mcc": mcc,
    }


def objective_components(
    baseline_irc: float,
    scenario_irc: float,
    baseline_bloom: float,
    scenario_bloom: float,
    baseline_uncertainty: float,
    scenario_uncertainty: float,
    relative_cost: float,
    config: dict[str, Any],
    *,
    planning_mode: str,
) -> dict[str, float]:
    objective_config = config.get("objective", {})
    weights = objective_config.get("weights", {})
    w_irc = float(weights.get("irc_alert_risk_reduction", 0.6))
    w_bloom = float(weights.get("bloom_probability_reduction", 0.4))
    lambda_cost = float(objective_config.get("planning_modes", {}).get(planning_mode, {}).get("lambda_cost", 0.05))
    lambda_uncertainty = float(objective_config.get("lambda_uncertainty", 0.10))
    irc_reduction = baseline_irc - scenario_irc
    bloom_reduction = baseline_bloom - scenario_bloom
    uncertainty_delta = scenario_uncertainty - baseline_uncertainty
    weighted_risk_reduction = (w_irc * irc_reduction) + (w_bloom * bloom_reduction)
    objective_value = weighted_risk_reduction - (lambda_cost * relative_cost) - (
        lambda_uncertainty * max(0.0, uncertainty_delta)
    )
    baseline_risk = (w_irc * baseline_irc) + (w_bloom * baseline_bloom)
    relative_reduction = weighted_risk_reduction / baseline_risk if baseline_risk else float("nan")
    return {
        "irc_reduction": irc_reduction,
        "bloom_reduction": bloom_reduction,
        "risk_reduction_absolute": weighted_risk_reduction,
        "risk_reduction_relative": relative_reduction,
        "uncertainty_delta": uncertainty_delta,
        "objective_value": objective_value,
    }


def evaluate_scenario(
    rows: pd.DataFrame,
    scenario: ScenarioSpec,
    config: dict[str, Any],
    *,
    planning_mode: str,
) -> pd.DataFrame:
    scenario_rows = apply_state_scenario(rows, scenario, config)
    scenario_irc = compute_irc_score(scenario_rows, config)
    scenario_bloom = compute_bloom_proxy(scenario_rows, scenario_irc)
    scenario_uncertainty = compute_uncertainty(scenario_rows)

    baseline = rows.copy()
    baseline_irc = compute_irc_score(baseline, config)
    baseline_bloom = compute_bloom_proxy(baseline, baseline_irc)
    baseline_uncertainty = compute_uncertainty(baseline)

    out = rows[KEY_COLUMNS + ["horizon_months"]].copy()
    out["scenario_family"] = scenario.scenario_family
    out["scenario_id"] = scenario.scenario_id
    out["action_type"] = scenario.action_type
    out["scenario_status"] = scenario.scenario_status
    out["infeasible_reason"] = scenario.infeasible_reason
    out["x_yN_offset"] = scenario.x_yN_offset
    out["x_yF_offset"] = scenario.x_yF_offset
    out["x_yN_scenario"] = scenario_rows["x_yN"].to_numpy()
    out["x_yF_scenario"] = scenario_rows["x_yF"].to_numpy()
    out["state_clipped"] = scenario_rows["state_clipped"].to_numpy()
    out["relative_cost"] = scenario.relative_cost
    out["baseline_irc_alert_score"] = baseline_irc.to_numpy()
    out["scenario_irc_alert_score"] = scenario_irc.to_numpy()
    out["baseline_bloom_probability"] = baseline_bloom.to_numpy()
    out["scenario_bloom_probability"] = scenario_bloom.to_numpy()
    out["baseline_uncertainty"] = baseline_uncertainty.to_numpy()
    out["scenario_uncertainty"] = scenario_uncertainty.to_numpy()
    if "actual_irc_alert" in rows.columns:
        out["actual_irc_alert"] = rows["actual_irc_alert"].to_numpy()
    if "bloom_h" in rows.columns:
        out["bloom_h"] = rows["bloom_h"].to_numpy()
    components = [
        objective_components(
            float(base_irc),
            float(scen_irc),
            float(base_bloom),
            float(scen_bloom),
            float(base_uncertainty),
            float(scen_uncertainty),
            scenario.relative_cost,
            config,
            planning_mode=planning_mode,
        )
        for base_irc, scen_irc, base_bloom, scen_bloom, base_uncertainty, scen_uncertainty in zip(
            baseline_irc,
            scenario_irc,
            baseline_bloom,
            scenario_bloom,
            baseline_uncertainty,
            scenario_uncertainty,
            strict=True,
        )
    ]
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(components)], axis=1)


def build_metric_rows(scenario_rows: pd.DataFrame, *, alert_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in scenario_rows.groupby(METRIC_GROUP_COLUMNS, dropna=False, sort=True):
        valid_group = group[group["scenario_status"] == "completed"]
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
            "clipped_rows": int(group["state_clipped"].sum()),
            "x_yN_offset": float(group["x_yN_offset"].iloc[0]),
            "x_yF_offset": float(group["x_yF_offset"].iloc[0]),
            "relative_cost": float(group["relative_cost"].iloc[0]),
        }
        metric_group = valid_group if not valid_group.empty else group
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
            "objective_value",
        ]:
            record[column] = float(metric_group[column].mean()) if not metric_group.empty else float("nan")
        if "actual_irc_alert" in metric_group.columns:
            record.update(_binary_metric_values(metric_group["actual_irc_alert"], metric_group["scenario_irc_alert_score"], alert_threshold))
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
            & (candidates["uncertainty_delta"] <= row["uncertainty_delta"])
            & (
                (candidates["risk_reduction_absolute"] > row["risk_reduction_absolute"])
                | (candidates["relative_cost"] < row["relative_cost"])
                | (candidates["uncertainty_delta"] < row["uncertainty_delta"])
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
            clipped_rows=("clipped_rows", "sum"),
            x_yN_offset=("x_yN_offset", "first"),
            x_yF_offset=("x_yF_offset", "first"),
            relative_cost=("relative_cost", "first"),
            baseline_irc_alert_score=("baseline_irc_alert_score", "mean"),
            scenario_irc_alert_score=("scenario_irc_alert_score", "mean"),
            baseline_bloom_probability=("baseline_bloom_probability", "mean"),
            scenario_bloom_probability=("scenario_bloom_probability", "mean"),
            risk_reduction_absolute=("risk_reduction_absolute", "mean"),
            risk_reduction_relative=("risk_reduction_relative", "mean"),
            uncertainty_delta=("uncertainty_delta", "mean"),
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
        "x_yN_offset",
        "x_yF_offset",
        "x_yN_scenario",
        "x_yF_scenario",
        "state_clipped",
        "baseline_irc_alert_score",
        "scenario_irc_alert_score",
        "baseline_bloom_probability",
        "scenario_bloom_probability",
        "risk_reduction_absolute",
        "relative_cost",
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
    config: dict[str, Any],
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pareto: pd.DataFrame,
) -> None:
    completed = summary[summary["scenario_status"] == "completed"].copy()
    top = completed.sort_values("objective_value", ascending=False, kind="mergesort").head(10)
    lines = [
        "# Counterfactual Planning Grid Report",
        "",
        f"Planning version: `{PLANNING_VERSION}`.",
        "",
        "## Non-Causal Guardrail",
        "",
        NON_CAUSAL_GUARDRAIL,
        "",
        "The reported scenarios are model-input perturbations used for simulated",
        "comparison against no action. They are not field interventions and are",
        "not official environmental recommendations.",
        "",
        "## Configuration",
        "",
        f"- Config: `{_manifest_path(args.config)}`",
        f"- Planning rows: `{_manifest_path(args.planning_rows)}`",
        f"- Scenario family: `{args.scenario_family}`",
        f"- Planning mode: `{args.planning_mode}`",
        f"- Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        f"- Alert threshold used for optional label metrics: `{_format_float(args.alert_threshold)}`",
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
                "| Scenario | Action | Objective | Risk reduction | Cost | Uncertainty delta | Pareto |",
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
                f"{_format_float(row.uncertainty_delta)} | "
                f"{bool(row.pareto_front)} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "A positive objective means only that the scenario improved the configured",
            "risk-cost-uncertainty objective under this state-proxy simulation. If no",
            "scenario improves the objective, that is a valid result: the current",
            "surface does not support prescriptive use under the tested assumptions.",
            "",
        ]
    )
    if config.get("reporting", {}).get("prohibited_claim"):
        lines.extend(["Prohibited claim:", "", f"> {config['reporting']['prohibited_claim']}", ""])
    while lines and lines[-1] == "":
        lines.pop()
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
    output_records = [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()]
    return {
        "status": "completed",
        "planning_version": PLANNING_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "script": {
            "path": "src/experiments/evaluate_counterfactual_planning.py",
            "sha256": _sha256_file(Path("src/experiments/evaluate_counterfactual_planning.py")),
        },
        "inputs": [
            {"role": "config", **_file_record(args.config)},
            {"role": "planning_rows", **_file_record(args.planning_rows)},
        ],
        "config": {
            "output_name": args.output_name,
            "output_dir": _manifest_path(args.output_dir),
            "scenario_family": args.scenario_family,
            "planning_mode": args.planning_mode,
            "evaluation_splits": args.evaluation_splits,
            "source_ids": args.source_ids,
            "max_rows_per_split": args.max_rows_per_split,
            "alert_threshold": args.alert_threshold,
            "config_phase": config.get("protocol", {}).get("phase"),
        },
        "row_counts": {
            "metric_rows": int(len(metrics)),
            "summary_rows": int(len(summary)),
            "pareto_rows": int(len(pareto)),
        },
        "outputs": output_records,
        "guardrail": NON_CAUSAL_GUARDRAIL,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--planning-rows", type=Path, default=DEFAULT_PLANNING_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--scenario-family", default="minimal_state_grid")
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
    paths = output_paths(args.output_dir, args.output_name)

    raw_rows = read_table(args.planning_rows)
    planning_rows = prepare_planning_rows(
        raw_rows,
        config,
        evaluation_splits=args.evaluation_splits,
        source_ids=args.source_ids,
        max_rows_per_split=args.max_rows_per_split,
    )
    if args.scenario_family != "minimal_state_grid":
        raise ValueError("The first implementation only supports --scenario-family minimal_state_grid")
    scenarios = build_state_grid_scenarios(config, planning_mode=planning_mode)
    scenario_rows = pd.concat(
        [evaluate_scenario(planning_rows, scenario, config, planning_mode=planning_mode) for scenario in scenarios],
        ignore_index=True,
    )
    metrics = build_metric_rows(scenario_rows, alert_threshold=args.alert_threshold)
    summary = build_summary(metrics)
    pareto = build_pareto(summary)
    examples = build_examples(scenario_rows, examples_per_scenario=args.examples_per_scenario)

    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(summary, paths["summary"])
    _write_csv_atomic(pareto, paths["pareto"])
    _write_csv_atomic(examples, paths["examples"])
    write_report(paths["report"], config=config, args=args, metrics=metrics, summary=summary, pareto=pareto)
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


if __name__ == "__main__":
    main()
