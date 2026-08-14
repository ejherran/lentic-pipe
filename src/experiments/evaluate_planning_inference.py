"""Pure, paired E9 planning inference for the sealed Closure V1 batch.

The module receives already-computed scenario outcomes.  It never refits P1,
opens a path, or publishes an artifact; it only returns deterministic in-memory
artifact envelopes to the runner-owned transaction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import numpy as np
import pandas as pd

from src.experiments.evaluate_anfis_ablation import (
    ClosureAnfisAblationError,
    artifact_envelope,
    validate_batch_context,
    validate_component_boundary,
)


COMPONENT_ID = "E9_planning_inference"
STAGE_ID = "E9"
MODEL_ID = "P1"
RNG_SEED = 1729
BOOTSTRAP_REPLICATES = 2000
MINIMUM_CLUSTER_COUNT = 2
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
BASELINE_SCENARIO = "no_action"
ACTION_SCENARIOS = (
    "tp_reduction_10",
    "tp_reduction_25",
    "tn_reduction_10",
    "tp_tn_reduction_10",
    "clarity_mild",
    "clarity_strong",
    "oxygen_support_05",
    "nutrient_clarity_mild",
    "nutrient_clarity_strong",
)
SCENARIO_IDS = (BASELINE_SCENARIO, *ACTION_SCENARIOS)
SENSITIVITY_MULTIPLIERS = (0.5, 1.0, 2.0)
PRIMARY_COST_WEIGHT = 0.05
PRIMARY_UNCERTAINTY_WEIGHT = 0.10
PRIMARY_SUPPORT_WEIGHT = 0.05
PLANNING_COLUMNS = (
    "model_id",
    "seed",
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "scenario_id",
    "status",
    "delta_irc",
    "delta_bloom",
    "delta_u",
    "relative_cost",
    "support_violation",
)
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)
ROW_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)
OUTPUT_PATHS = (
    "reports/closure_v1/09_planning/planning_origin_deltas.parquet",
    "reports/closure_v1/09_planning/planning_bootstrap.csv",
    "reports/closure_v1/09_planning/planning_sensitivity.csv",
    "reports/closure_v1/09_planning/ecological_coherence.csv",
    "reports/closure_v1/09_planning/planning_inference_report.md",
)
COMPONENT_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_e9_planning_inference_component_v1",
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "input_table": "planning_scenarios",
        "model_id": MODEL_ID,
        "registered_seeds": list(REGISTERED_SEEDS),
        "baseline_scenario_id": BASELINE_SCENARIO,
        "action_scenario_ids": list(ACTION_SCENARIOS),
        "exact_row_requires_all_seeds": True,
        "seed_aggregation": "paired_delta_then_equal_seed_mean",
        "base_objective": "0.60*delta_irc+0.40*delta_bloom",
        "primary_objective": "base_objective-0.05*relative_cost-0.10*max(0,delta_u)-0.05*support_violation",
        "inference_unit": "location_cluster_not_seed",
        "alternative": "greater_than_zero",
        "multiplicity": "holm_nine_actions",
        "minimum_cluster_count": MINIMUM_CLUSTER_COUNT,
        "sensitivity_multipliers": list(SENSITIVITY_MULTIPLIERS),
        "refit": False,
        "output_paths": list(OUTPUT_PATHS),
        "pure_in_memory": True,
    }
)


class ClosurePlanningInferenceError(RuntimeError):
    """Raised when E9 inputs or the locked inferential contract drift."""


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _plain_json(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_canonical_json_bytes(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return hashlib.sha256(_canonical_json_bytes(COMPONENT_CONTRACT)).hexdigest()


def _boundary(authority: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    try:
        return validate_component_boundary(
            authority,
            contract,
            component_id=COMPONENT_ID,
            stage_id=STAGE_ID,
            output_paths=OUTPUT_PATHS,
        )
    except ClosureAnfisAblationError as exc:
        raise ClosurePlanningInferenceError(str(exc)) from exc


def _require_columns(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ClosurePlanningInferenceError(
            f"planning_scenarios missing columns: {missing}"
        )


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, PLANNING_COLUMNS)
    optional = [name for name in ("holdout_group_id",) if name in frame.columns]
    out = frame.loc[:, [*PLANNING_COLUMNS, *optional]].copy()
    for column in (
        "model_id",
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "scenario_id",
        "status",
    ):
        out[column] = out[column].astype(str)
        if bool(out[column].eq("").any()):
            raise ClosurePlanningInferenceError(
                f"planning_scenarios {column} is empty"
            )
    out["seed"] = pd.to_numeric(out["seed"], errors="raise").astype("int64")
    out["horizon_months"] = pd.to_numeric(
        out["horizon_months"], errors="raise"
    ).astype("int64")
    for column in (
        "delta_irc",
        "delta_bloom",
        "delta_u",
        "relative_cost",
        "support_violation",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if set(out["model_id"]) != {MODEL_ID} and not out.empty:
        raise ClosurePlanningInferenceError("planning_scenarios must contain only P1")
    if not set(out["seed"]).issubset(REGISTERED_SEEDS):
        raise ClosurePlanningInferenceError("planning_scenarios contains an unregistered seed")
    if not set(out["horizon_months"]).issubset({1, 2, 3}):
        raise ClosurePlanningInferenceError("planning horizon drifted")
    if not set(out["scenario_id"]).issubset(SCENARIO_IDS):
        raise ClosurePlanningInferenceError("planning scenario catalog drifted")
    if not set(out["status"]).issubset(TERMINAL_STATUSES):
        raise ClosurePlanningInferenceError("planning terminal status drifted")
    for column in ("origin_year_month", "target_year_month"):
        if not out[column].str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
            raise ClosurePlanningInferenceError(f"planning {column} is not canonical")
    key = ["model_id", "seed", *ROW_COLUMNS, "scenario_id"]
    if bool(out.duplicated(key).any()):
        raise ClosurePlanningInferenceError("planning_scenarios contains duplicate exact rows")
    intent_sets = out.groupby(list(ROW_COLUMNS), sort=True).apply(
        lambda group: set(zip(group["seed"], group["scenario_id"], strict=True)),
        include_groups=False,
    )
    expected_intents = {
        (seed, scenario_id)
        for seed in REGISTERED_SEEDS
        for scenario_id in SCENARIO_IDS
    }
    if not out.empty and any(intents != expected_intents for intents in intent_sets):
        raise ClosurePlanningInferenceError(
            "planning_scenarios omits a registered seed-by-scenario intent"
        )
    success = out["status"].eq("success")
    finite = np.isfinite(
        out[
            [
                "delta_irc",
                "delta_bloom",
                "delta_u",
                "relative_cost",
                "support_violation",
            ]
        ]
    )
    if bool((success & ~finite.all(axis=1)).any()):
        raise ClosurePlanningInferenceError("successful planning rows contain nonfinite values")
    if bool(
        out.loc[
            ~success,
            [
                "delta_irc",
                "delta_bloom",
                "delta_u",
                "relative_cost",
                "support_violation",
            ],
        ]
        .notna()
        .any()
        .any()
    ):
        raise ClosurePlanningInferenceError(
            "non-success planning rows contain invented scientific values"
        )
    if bool(
        (
            success
            & ~out["support_violation"].between(0.0, 1.0, inclusive="both")
        ).any()
    ):
        raise ClosurePlanningInferenceError("planning support must be a [0,1] violation flag/rate")
    if bool((success & (out["relative_cost"] < 0.0)).any()):
        raise ClosurePlanningInferenceError("planning relative cost must be nonnegative")
    out["base_objective"] = 0.60 * out["delta_irc"] + 0.40 * out["delta_bloom"]
    out["objective"] = (
        out["base_objective"]
        - PRIMARY_COST_WEIGHT * out["relative_cost"]
        - PRIMARY_UNCERTAINTY_WEIGHT * np.maximum(0.0, out["delta_u"])
        - PRIMARY_SUPPORT_WEIGHT * out["support_violation"]
    )
    baseline_success = success & out["scenario_id"].eq(BASELINE_SCENARIO)
    baseline_zero_columns = (
        "delta_irc",
        "delta_bloom",
        "delta_u",
        "relative_cost",
        "support_violation",
        "base_objective",
        "objective",
    )
    if bool(
        (
            ~np.isclose(
                out.loc[baseline_success, list(baseline_zero_columns)],
                0.0,
                rtol=0.0,
                atol=1e-12,
            )
        ).any()
    ):
        raise ClosurePlanningInferenceError("no_action deltas/penalties must be exactly zero")
    if "holdout_group_id" in out:
        out["cluster_id"] = out["holdout_group_id"].astype(str)
        if bool(out["cluster_id"].eq("").any()):
            raise ClosurePlanningInferenceError("holdout_group_id must be nonempty")
    else:
        out["cluster_id"] = out["source_id"] + ":" + out["site_id"]
    return out.sort_values(key, kind="mergesort").reset_index(drop=True)


def paired_origin_deltas(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Require exact action/no-action success for all five registered seeds."""

    columns = [
        *ROW_COLUMNS,
        "cluster_id",
        "scenario_id",
        "delta_irc",
        "delta_bloom",
        "delta_u",
        "base_objective",
        "delta_objective",
        "relative_cost",
        "support_violation",
        "seed_count",
        "status",
    ]
    failure_columns = [*ROW_COLUMNS, "scenario_id", "failure_code"]
    if frame.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=failure_columns)
    success = frame.loc[frame["status"].eq("success")].copy()
    baseline = success.loc[success["scenario_id"].eq(BASELINE_SCENARIO)].copy()
    baseline = baseline.rename(
        columns={
            "objective": "baseline_objective",
            "delta_irc": "baseline_delta_irc",
            "delta_bloom": "baseline_delta_bloom",
            "delta_u": "baseline_delta_u",
            "base_objective": "baseline_base_objective",
            "relative_cost": "baseline_relative_cost",
            "support_violation": "baseline_support_violation",
            "cluster_id": "baseline_cluster_id",
        }
    )
    join = ["model_id", "seed", *ROW_COLUMNS]
    paired_rows: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    all_rows = frame.loc[:, list(ROW_COLUMNS)].drop_duplicates()
    for scenario_id in ACTION_SCENARIOS:
        action = success.loc[success["scenario_id"].eq(scenario_id)].copy()
        merged = action.merge(
            baseline.loc[
                :,
                [
                    *join,
                    "baseline_objective",
                    "baseline_delta_irc",
                    "baseline_delta_bloom",
                    "baseline_delta_u",
                    "baseline_base_objective",
                    "baseline_relative_cost",
                    "baseline_support_violation",
                    "baseline_cluster_id",
                ],
            ],
            on=join,
            how="inner",
            validate="one_to_one",
        )
        if not merged.empty and bool(
            (merged["cluster_id"] != merged["baseline_cluster_id"]).any()
        ):
            raise ClosurePlanningInferenceError("paired planning cluster identity drifted")
        merged["delta_objective_seed"] = (
            merged["objective"] - merged["baseline_objective"]
        )
        for column in (
            "delta_irc",
            "delta_bloom",
            "delta_u",
            "base_objective",
            "relative_cost",
            "support_violation",
        ):
            merged[f"{column}_seed"] = merged[column] - merged[f"baseline_{column}"]
        group_key = [*ROW_COLUMNS, "cluster_id"]
        counts = merged.groupby(group_key, dropna=False)["seed"].agg(
            lambda values: len(set(int(value) for value in values))
        )
        complete_index = counts.loc[counts.eq(len(REGISTERED_SEEDS))].index
        complete = merged.set_index(group_key).loc[
            merged.set_index(group_key).index.isin(complete_index)
        ].reset_index()
        if not complete.empty:
            grouped = (
                complete.groupby(group_key, dropna=False, as_index=False)
                .agg(
                    delta_irc=("delta_irc_seed", "mean"),
                    delta_bloom=("delta_bloom_seed", "mean"),
                    delta_u=("delta_u_seed", "mean"),
                    base_objective=("base_objective_seed", "mean"),
                    delta_objective=("delta_objective_seed", "mean"),
                    relative_cost=("relative_cost_seed", "mean"),
                    support_violation=("support_violation_seed", "mean"),
                    seed_count=("seed", "nunique"),
                )
                .assign(scenario_id=scenario_id, status="shared_success")
            )
            paired_rows.append(grouped.loc[:, columns])
        complete_rows = complete.loc[:, list(ROW_COLUMNS)].drop_duplicates()
        missing_rows = all_rows.merge(
            complete_rows.assign(_complete=True), on=list(ROW_COLUMNS), how="left"
        )
        for row in missing_rows.loc[missing_rows["_complete"].isna()].itertuples(
            index=False
        ):
            failures.append(
                {
                    **{name: getattr(row, name) for name in ROW_COLUMNS},
                    "scenario_id": scenario_id,
                    "failure_code": "missing_action_or_no_action_registered_seed",
                }
            )
    deltas = (
        pd.concat(paired_rows, ignore_index=True)
        if paired_rows
        else pd.DataFrame(columns=columns)
    )
    failed = pd.DataFrame(failures, columns=failure_columns).drop_duplicates()
    return deltas.sort_values(["scenario_id", *ROW_COLUMNS], kind="mergesort").reset_index(
        drop=True
    ), failed.sort_values(["scenario_id", *ROW_COLUMNS], kind="mergesort").reset_index(
        drop=True
    )


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return monotone Holm-adjusted p-values for the fixed nine-action family."""

    if set(p_values) != set(ACTION_SCENARIOS):
        raise ClosurePlanningInferenceError("Holm universe must contain the exact nine actions")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        if not np.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ClosurePlanningInferenceError("Holm received an invalid p-value")
        running = max(running, min(1.0, (total - rank) * float(value)))
        adjusted[name] = running
    return adjusted


def _bootstrap(
    deltas: pd.DataFrame, *, rng_seed: int = RNG_SEED
) -> tuple[pd.DataFrame, pd.DataFrame]:
    replicate_columns = ["scenario_id", "replicate", "delta_objective"]
    summary_columns = [
        "scenario_id",
        "row_count",
        "cluster_count",
        "estimate",
        "ci95_lower",
        "ci95_upper",
        "p_value_greater",
        "p_holm",
        "reject_holm_0_05",
        "status",
    ]
    rng = np.random.default_rng(rng_seed)
    replicate_rows: list[dict[str, Any]] = []
    raw_p: dict[str, float] = {}
    partial: dict[str, dict[str, Any]] = {}
    for scenario_id in ACTION_SCENARIOS:
        part = deltas.loc[deltas["scenario_id"].eq(scenario_id)].copy()
        clusters = sorted(part["cluster_id"].astype(str).unique())
        if len(clusters) < MINIMUM_CLUSTER_COUNT:
            raw_p[scenario_id] = 1.0
            partial[scenario_id] = {
                "scenario_id": scenario_id,
                "row_count": 0,
                "cluster_count": 0,
                "estimate": np.nan,
                "ci95_lower": np.nan,
                "ci95_upper": np.nan,
                "p_value_greater": 1.0,
                "status": "insufficient_cluster_support",
            }
            continue
        observed = float(part["delta_objective"].mean())
        values = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
        grouped = {key: group for key, group in part.groupby("cluster_id", sort=False)}
        for replicate in range(BOOTSTRAP_REPLICATES):
            selected = rng.choice(clusters, size=len(clusters), replace=True)
            sampled = pd.concat([grouped[key] for key in selected], ignore_index=True)
            estimate = float(sampled["delta_objective"].mean())
            values[replicate] = estimate
            replicate_rows.append(
                {
                    "scenario_id": scenario_id,
                    "replicate": replicate + 1,
                    "delta_objective": estimate,
                }
            )
        p_value = float((1 + np.sum(values <= 0.0)) / (BOOTSTRAP_REPLICATES + 1))
        raw_p[scenario_id] = p_value
        partial[scenario_id] = {
            "scenario_id": scenario_id,
            "row_count": int(len(part)),
            "cluster_count": int(len(clusters)),
            "estimate": observed,
            "ci95_lower": float(np.quantile(values, 0.025)),
            "ci95_upper": float(np.quantile(values, 0.975)),
            "p_value_greater": p_value,
            "status": "available",
        }
    adjusted = holm_adjust(raw_p)
    summaries: list[dict[str, Any]] = []
    for scenario_id in ACTION_SCENARIOS:
        row = dict(partial[scenario_id])
        row["p_holm"] = adjusted[scenario_id]
        row["reject_holm_0_05"] = bool(
            row["status"] == "available" and adjusted[scenario_id] <= 0.05
        )
        summaries.append(row)
    replicates = pd.DataFrame(replicate_rows, columns=replicate_columns)
    summary = pd.DataFrame(summaries, columns=summary_columns)
    return replicates, summary


def _sensitivity(deltas: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "scenario_id",
        "cost_weight_multiplier",
        "support_penalty_multiplier",
        "row_count",
        "delta_objective",
        "positive",
        "role",
    ]
    rows: list[dict[str, Any]] = []
    for scenario_id in ACTION_SCENARIOS:
        part = deltas.loc[deltas["scenario_id"].eq(scenario_id)]
        for cost_multiplier in SENSITIVITY_MULTIPLIERS:
            for support_multiplier in SENSITIVITY_MULTIPLIERS:
                if part.empty:
                    estimate = np.nan
                else:
                    adjusted = (
                        part["base_objective"]
                        - PRIMARY_COST_WEIGHT
                        * cost_multiplier
                        * part["relative_cost"]
                        - PRIMARY_UNCERTAINTY_WEIGHT
                        * np.maximum(0.0, part["delta_u"])
                        - PRIMARY_SUPPORT_WEIGHT
                        * support_multiplier
                        * part["support_violation"]
                    )
                    estimate = float(adjusted.mean())
                rows.append(
                    {
                        "scenario_id": scenario_id,
                        "cost_weight_multiplier": cost_multiplier,
                        "support_penalty_multiplier": support_multiplier,
                        "row_count": int(len(part)),
                        "delta_objective": estimate,
                        "positive": bool(np.isfinite(estimate) and estimate > 0.0),
                        "role": "descriptive_only",
                    }
                )
    return pd.DataFrame(rows, columns=columns)


def _coherence(deltas: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "scenario_id",
        "row_count",
        "positive_objective_row_fraction",
        "ecologically_coherent_row_fraction",
        "mean_delta_irc",
        "mean_delta_bloom",
        "mean_delta_u",
        "mean_support_violation",
        "mean_relative_cost",
        "confirmatory_delta_objective",
        "ci95_lower",
        "ci95_upper",
        "p_holm",
        "dictamen",
    ]
    indexed = summary.set_index("scenario_id")
    rows: list[dict[str, Any]] = []
    for scenario_id in ACTION_SCENARIOS:
        part = deltas.loc[deltas["scenario_id"].eq(scenario_id)]
        infer = indexed.loc[scenario_id]
        lower = float(infer["ci95_lower"])
        estimate = float(infer["estimate"])
        if infer["status"] != "available" or not np.isfinite(estimate):
            verdict = "not_estimable_model_or_rows_unavailable"
        elif bool(infer["reject_holm_0_05"]) and lower > 0.0:
            verdict = "positive_internal_planning_evidence"
        else:
            verdict = "no_confirmatory_positive_evidence"
        rows.append(
            {
                "scenario_id": scenario_id,
                "row_count": int(len(part)),
                "positive_objective_row_fraction": (
                    float(part["delta_objective"].gt(0.0).mean()) if not part.empty else np.nan
                ),
                "ecologically_coherent_row_fraction": (
                    float(
                        (
                            part["delta_irc"].ge(0.0)
                            & part["delta_bloom"].ge(0.0)
                        ).mean()
                    )
                    if not part.empty
                    else np.nan
                ),
                "mean_delta_irc": float(part["delta_irc"].mean()) if not part.empty else np.nan,
                "mean_delta_bloom": float(part["delta_bloom"].mean()) if not part.empty else np.nan,
                "mean_delta_u": float(part["delta_u"].mean()) if not part.empty else np.nan,
                "mean_support_violation": (
                    float(part["support_violation"].mean()) if not part.empty else np.nan
                ),
                "mean_relative_cost": (
                    float(part["relative_cost"].mean()) if not part.empty else np.nan
                ),
                "confirmatory_delta_objective": estimate,
                "ci95_lower": lower,
                "ci95_upper": float(infer["ci95_upper"]),
                "p_holm": float(infer["p_holm"]),
                "dictamen": verdict,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _report(
    deltas: pd.DataFrame,
    failures: pd.DataFrame,
    summary: pd.DataFrame,
    coherence: pd.DataFrame,
) -> str:
    positive = int(coherence["dictamen"].eq("positive_internal_planning_evidence").sum())
    unavailable = int(coherence["dictamen"].eq("not_estimable_model_or_rows_unavailable").sum())
    return "\n".join(
        [
            "# Closure V1 — E9 planning inference",
            "",
            "The registered P1 planning surface is evaluated without refit against exact no-action pairs.",
            "",
            f"- Shared-success action-origin rows: `{len(deltas)}`",
            f"- Explicit incomplete intent rows: `{len(failures)}`",
            f"- Fixed confirmatory actions: `{len(summary)}`",
            f"- Holm-positive internal actions: `{positive}`",
            f"- Not-estimable actions: `{unavailable}`",
            f"- Cluster bootstrap replicates per estimable action: `{BOOTSTRAP_REPLICATES}`",
            "- Sensitivity grid is descriptive and cannot redefine the confirmatory family.",
            "",
            "These counterfactual proxy comparisons are neither causal field effects nor official recommendations.",
            "",
        ]
    )


def _empty_result(*, reason: str) -> dict[str, Any]:
    deltas, failures = paired_origin_deltas(pd.DataFrame(columns=[*PLANNING_COLUMNS, "cluster_id"]))
    replicates, summary = _bootstrap(deltas)
    sensitivity = _sensitivity(deltas)
    coherence = _coherence(deltas, summary)
    report = _report(deltas, failures, summary, coherence)
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed_unavailable",
        "artifacts": {
            OUTPUT_PATHS[0]: artifact_envelope("parquet", deltas),
            OUTPUT_PATHS[1]: artifact_envelope("csv", summary),
            OUTPUT_PATHS[2]: artifact_envelope("csv", sensitivity),
            OUTPUT_PATHS[3]: artifact_envelope("csv", coherence),
            OUTPUT_PATHS[4]: artifact_envelope("markdown", report, manifest_last=True),
        },
        "tables": {
            "e9_planning_origin_deltas": deltas.copy(deep=True),
            "e9_planning_bootstrap_replicates": replicates.copy(deep=True),
            "e9_planning_inference": summary.copy(deep=True),
            "e9_planning_failures": failures.copy(deep=True),
            "e9_planning_sensitivity": sensitivity.copy(deep=True),
            "e9_ecological_coherence": coherence.copy(deep=True),
        },
        "diagnostics": {
            "component_contract_sha256": component_contract_sha256(),
            "unavailable_reason": reason,
            "model_id": MODEL_ID,
            "refit_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(repo_root, Path):
        raise ClosurePlanningInferenceError("E9 repository root is not a Path")
    del repo_root
    contract_sha256 = _boundary(authority, sealed_batch_contract)
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": contract_sha256,
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    preflight_closure_sealed_batch_component(authority, sealed_batch_contract, repo_root)
    try:
        context = validate_batch_context(batch_context)
    except ClosureAnfisAblationError as exc:
        raise ClosurePlanningInferenceError(str(exc)) from exc
    availability = cast(dict[str, Any], context["model_availability"])
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(availability) != dict(
        sealed_availability
    ):
        raise ClosurePlanningInferenceError("model availability is not batch-bound")
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "planning_scenarios" not in tables:
        raise ClosurePlanningInferenceError("batch_context lacks planning_scenarios")
    planning = _normalize(tables["planning_scenarios"])
    state = availability.get(MODEL_ID)
    if state not in {"available", "unavailable"}:
        raise ClosurePlanningInferenceError(f"{MODEL_ID} availability is absent")
    if state == "unavailable":
        if not planning.empty and not planning["status"].eq("model_unavailable").all():
            raise ClosurePlanningInferenceError("unavailable P1 produced planning results")
        return _empty_result(reason=f"{MODEL_ID}_model_unavailable")
    if planning["status"].eq("model_unavailable").any():
        raise ClosurePlanningInferenceError("available P1 was silently unavailable")
    deltas, failures = paired_origin_deltas(planning)
    replicates, summary = _bootstrap(deltas, rng_seed=cast(int, context["rng_seed"]))
    sensitivity = _sensitivity(deltas)
    coherence = _coherence(deltas, summary)
    report = _report(deltas, failures, summary, coherence)
    artifacts = {
        OUTPUT_PATHS[0]: artifact_envelope("parquet", deltas),
        OUTPUT_PATHS[1]: artifact_envelope("csv", summary),
        OUTPUT_PATHS[2]: artifact_envelope("csv", sensitivity),
        OUTPUT_PATHS[3]: artifact_envelope("csv", coherence),
        OUTPUT_PATHS[4]: artifact_envelope("markdown", report, manifest_last=True),
    }
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed" if not deltas.empty else "completed_unavailable",
        "artifacts": artifacts,
        "tables": {
            "e9_planning_origin_deltas": deltas.copy(deep=True),
            "e9_planning_bootstrap_replicates": replicates.copy(deep=True),
            "e9_planning_inference": summary.copy(deep=True),
            "e9_planning_failures": failures.copy(deep=True),
            "e9_planning_sensitivity": sensitivity.copy(deep=True),
            "e9_ecological_coherence": coherence.copy(deep=True),
        },
        "diagnostics": {
            "component_contract_sha256": component_contract_sha256(),
            "input_row_count": int(len(planning)),
            "shared_success_row_count": int(len(deltas)),
            "failure_row_count": int(len(failures)),
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "holm_universe_size": len(ACTION_SCENARIOS),
            "refit_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
