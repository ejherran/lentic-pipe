#!/usr/bin/env python
"""Pure paired site-bootstrap and within-family Holm inference for E5."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd


COMPONENT_ID = "E5_clustered_inference"
STAGE_ID = "E5"
INPUT_TABLE = "paired_metric_rows"
BOOTSTRAP_REPLICATES = 5000
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
INPUT_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
    "evaluation_cohort",
    "metric",
    "loss",
    "terminal_status",
)
COMPARISONS = (
    ("A_P1_vs_B1", "A", "P1", "B1"),
    ("A_P1_vs_B2", "A", "P1", "B2"),
    ("A_P1_vs_P0", "A", "P1", "P0"),
    ("B_M0_vs_P1", "B", "M0", "P1"),
    ("C_A2_vs_P1", "C", "A2", "P1"),
)
OUTPUT_PATHS = (
    "reports/closure_v1/05_inference/pairwise_effects.csv",
    "reports/closure_v1/05_inference/site_level_losses.csv",
    "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
    "reports/closure_v1/05_inference/multiplicity_report.csv",
    "reports/closure_v1/05_inference/statistical_inference_report.md",
)
COMPONENT_CONTRACT = {
    "schema_version": "closure_e5_clustered_inference_v1",
    "component_id": COMPONENT_ID,
    "stage_id": STAGE_ID,
    "input_table": INPUT_TABLE,
    "input_columns": list(INPUT_COLUMNS),
    "comparisons": [list(value) for value in COMPARISONS],
    "cluster_unit": ["source_id", "site_id"],
    "holdout_group_role": "traceability_only",
    "bootstrap_method": "paired_site_resampling_keep_all_rows",
    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    "confidence_level": 0.95,
    "multiplicity": "holm_within_family",
    "loss_orientation": "lower_is_better",
    "unavailable_comparisons_retained": True,
    "output_paths": list(OUTPUT_PATHS),
    "filesystem_writes": "forbidden",
}


class ClusteredInferenceError(RuntimeError):
    """Raised when the closed E5 inference contract is violated."""


def _digest(value: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return _digest(COMPONENT_CONTRACT)


def _validate(authority: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    required = {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    if any(
        type(authority.get(key)) is not type(expected)
        or authority.get(key) != expected
        for key, expected in required.items()
    ):
        raise ClusteredInferenceError("E5 E0-U authority drifted")
    expected_component = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "module_name": "src.experiments.compare_models_clustered",
        "source_path": "src/experiments/compare_models_clustered.py",
        "preflight_api": "preflight_closure_sealed_batch_component",
        "execute_api": "execute_closure_sealed_batch_component",
    }
    components = contract.get("components")
    if (
        contract.get("schema_version") != "closure_sealed_evaluation_batch_v1"
        or contract.get("experiment_id") != "closure_v1"
        or contract.get("execution_gate") != "E0-U"
        or contract.get("evaluation_refit") != "forbidden"
        or contract.get("failed_model_replacement") != "forbidden"
        or contract.get("silent_row_deletion") != "forbidden"
        or contract.get("one_batch_only") is not True
        or authority.get("sealed_batch_command") != contract.get("sealed_command")
        or not isinstance(components, list)
        or components.count(expected_component) != 1
    ):
        raise ClusteredInferenceError("E5 sealed batch contract drifted")
    return _digest(contract)


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": _validate(authority, sealed_batch_contract),
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def _holm(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["holm_p_value"] = np.nan
    for _, indices in result.groupby("family", sort=True).groups.items():
        eligible = result.loc[list(indices)].dropna(subset=["raw_p_value"]).sort_values(
            ["raw_p_value", "comparison_id", "metric", "horizon_months"],
            kind="mergesort",
        )
        running = 0.0
        total = len(eligible)
        for rank, (index, row) in enumerate(eligible.iterrows()):
            running = max(
                running,
                min(1.0, float(row["raw_p_value"]) * (total - rank)),
            )
            result.at[index, "holm_p_value"] = running
    return result


def _paired_rows(
    frame: pd.DataFrame, model_a: str, model_b: str
) -> pd.DataFrame:
    identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "horizon_months",
        "seed_slot",
        "evaluation_cohort",
        "metric",
    ]
    columns = identity + ["model_seed", "loss", "terminal_status"]
    left = frame.loc[frame["model_id"] == model_a, columns]
    right = frame.loc[frame["model_id"] == model_b, columns]
    if left.duplicated(identity).any() or right.duplicated(identity).any():
        raise ClusteredInferenceError("E5 model rows are not unique within seed slot")
    paired = left.merge(
        right,
        on=identity,
        how="inner",
        validate="one_to_one",
        suffixes=("_model_a", "_model_b"),
    )
    return paired


def _unavailable_effect(
    comparison_id: str,
    family: str,
    model_a: str,
    model_b: str,
    metric: str,
    horizon: int,
    cohort: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "comparison_id": comparison_id,
        "family": family,
        "metric": metric,
        "horizon_months": horizon,
        "evaluation_cohort": cohort,
        "model_a": model_a,
        "model_b": model_b,
        "status": "not_estimable",
        "not_estimable_reason": reason,
        "n_rows": 0,
        "n_sites": 0,
        "estimate_model_a": np.nan,
        "estimate_model_b": np.nan,
        "delta": np.nan,
        "site_balanced_delta_mean": np.nan,
        "site_balanced_delta_median": np.nan,
        "site_balanced_delta_iqr": np.nan,
        "relative_delta": np.nan,
        "ci95_low": np.nan,
        "ci95_high": np.nan,
        "site_win_rate": np.nan,
        "raw_p_value": np.nan,
        "effect_interpretation": "not_estimable",
    }


def paired_clustered_inference(
    frame: pd.DataFrame,
    *,
    model_availability: Mapping[str, str] | None = None,
    rng_seed: int = 1729,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, pd.DataFrame]:
    """Estimate paired effects while retaining unavailable comparisons."""

    if tuple(frame.columns) != INPUT_COLUMNS:
        raise ClusteredInferenceError("E5 paired metric columns are not exact")
    if type(rng_seed) is not int or rng_seed != 1729:
        raise ClusteredInferenceError("E5 bootstrap seed drifted")
    if type(replicates) is not int or replicates <= 0:
        raise ClusteredInferenceError("E5 bootstrap replicate count is invalid")
    work = frame.copy(deep=True)
    if work.empty:
        raise ClusteredInferenceError("E5 paired metric registry is empty")
    work["loss"] = pd.to_numeric(work["loss"], errors="coerce")
    if not work["horizon_months"].isin([1, 2, 3]).all():
        raise ClusteredInferenceError("E5 horizon universe drifted")
    if not work["seed_slot"].isin(REGISTERED_SEEDS).all():
        raise ClusteredInferenceError("E5 seed-slot universe drifted")
    if work[list(INPUT_COLUMNS[:-2])].isna().any().any():
        raise ClusteredInferenceError("E5 paired identity contains nulls")
    for column in (
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "model_id",
        "evaluation_cohort",
        "metric",
    ):
        if work[column].astype(str).str.len().eq(0).any():
            raise ClusteredInferenceError(f"E5 text identity drifted: {column}")
    terminal_statuses = {
        "success",
        "input_ineligible",
        "target_unavailable",
        "model_unavailable",
        "numerical_failure",
        "infrastructure_failure",
    }
    if not work["terminal_status"].isin(terminal_statuses).all():
        raise ClusteredInferenceError("E5 terminal status drifted")
    success = work["terminal_status"].eq("success")
    if work.loc[success, "loss"].isna().any() or work.loc[~success, "loss"].notna().any():
        raise ClusteredInferenceError("E5 terminal status/loss binding drifted")
    availability = dict(model_availability or {})
    dimensions = (
        work[["metric", "horizon_months", "evaluation_cohort"]]
        .drop_duplicates()
        .sort_values(["metric", "horizon_months", "evaluation_cohort"])
    )
    effects: list[dict[str, Any]] = []
    sites: list[pd.DataFrame] = []
    distributions: list[dict[str, Any]] = []
    ordinal = 0
    for comparison_id, family, model_a, model_b in COMPARISONS:
        paired = _paired_rows(work, model_a, model_b)
        for dimension in dimensions.to_dict("records"):
            metric = str(dimension["metric"])
            horizon = int(dimension["horizon_months"])
            cohort = str(dimension["evaluation_cohort"])
            group = paired[
                (paired["metric"] == metric)
                & (paired["horizon_months"] == horizon)
                & (paired["evaluation_cohort"] == cohort)
            ].copy()
            unavailable_models = [
                model
                for model in (model_a, model_b)
                if availability.get(model, "available") != "available"
            ]
            eligible = group[
                group["terminal_status_model_a"].eq("success")
                & group["terminal_status_model_b"].eq("success")
                & group["loss_model_a"].notna()
                & group["loss_model_b"].notna()
            ].copy()
            if unavailable_models or eligible.empty:
                reason = (
                    "model_unavailable:" + ",".join(unavailable_models)
                    if unavailable_models
                    else "no_exact_paired_success_rows"
                )
                effects.append(
                    _unavailable_effect(
                        comparison_id,
                        family,
                        model_a,
                        model_b,
                        metric,
                        horizon,
                        cohort,
                        reason,
                    )
                )
                continue
            eligible["delta"] = eligible["loss_model_b"] - eligible["loss_model_a"]
            site = (
                eligible.groupby(["source_id", "site_id"], sort=True, as_index=False)
                .agg(
                    holdout_group_id=("holdout_group_id", "first"),
                    n_rows=("delta", "size"),
                    loss_model_a=("loss_model_a", "mean"),
                    loss_model_b=("loss_model_b", "mean"),
                    delta=("delta", "mean"),
                )
            )
            site.insert(0, "comparison_id", comparison_id)
            site.insert(1, "family", family)
            site.insert(2, "metric", metric)
            site.insert(3, "horizon_months", horizon)
            site.insert(4, "evaluation_cohort", cohort)
            sites.append(site)
            clusters = [
                cast(tuple[Any, Any], key)
                for key in eligible.groupby(["source_id", "site_id"], sort=True).groups
            ]
            by_cluster = {
                cast(tuple[Any, Any], key): values["delta"].to_numpy(dtype="float64")
                for key, values in eligible.groupby(["source_id", "site_id"], sort=True)
            }
            rng = np.random.default_rng(rng_seed + ordinal)
            ordinal += 1
            boot = np.empty(replicates, dtype="float64")
            for replicate in range(replicates):
                sampled = rng.integers(0, len(clusters), size=len(clusters))
                values = np.concatenate([by_cluster[clusters[index]] for index in sampled])
                boot[replicate] = float(values.mean())
                distributions.append(
                    {
                        "comparison_id": comparison_id,
                        "family": family,
                        "metric": metric,
                        "horizon_months": horizon,
                        "evaluation_cohort": cohort,
                        "replicate": replicate,
                        "delta": boot[replicate],
                    }
                )
            lower = (np.count_nonzero(boot <= 0.0) + 1) / (replicates + 1)
            upper = (np.count_nonzero(boot >= 0.0) + 1) / (replicates + 1)
            raw_p = min(1.0, 2.0 * min(lower, upper))
            estimate_a = float(eligible["loss_model_a"].mean())
            estimate_b = float(eligible["loss_model_b"].mean())
            ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
            interpretation = (
                "model_a_lower_loss"
                if ci_low > 0.0
                else "model_b_lower_loss" if ci_high < 0.0 else "difference_not_demonstrated"
            )
            effects.append(
                {
                    "comparison_id": comparison_id,
                    "family": family,
                    "metric": metric,
                    "horizon_months": horizon,
                    "evaluation_cohort": cohort,
                    "model_a": model_a,
                    "model_b": model_b,
                    "status": "estimated",
                    "not_estimable_reason": "",
                    "n_rows": len(eligible),
                    "n_sites": len(clusters),
                    "estimate_model_a": estimate_a,
                    "estimate_model_b": estimate_b,
                    "delta": float(eligible["delta"].mean()),
                    "site_balanced_delta_mean": float(site["delta"].mean()),
                    "site_balanced_delta_median": float(site["delta"].median()),
                    "site_balanced_delta_iqr": float(
                        site["delta"].quantile(0.75) - site["delta"].quantile(0.25)
                    ),
                    "relative_delta": (
                        float(eligible["delta"].mean()) / abs(estimate_b)
                        if estimate_b != 0.0
                        else np.nan
                    ),
                    "ci95_low": float(ci_low),
                    "ci95_high": float(ci_high),
                    "site_win_rate": float((site["delta"] > 0.0).mean()),
                    "raw_p_value": raw_p,
                    "effect_interpretation": interpretation,
                }
            )
    effect_frame = _holm(pd.DataFrame(effects))
    multiplicity = effect_frame[
        [
            "comparison_id",
            "family",
            "metric",
            "horizon_months",
            "evaluation_cohort",
            "status",
            "raw_p_value",
            "holm_p_value",
        ]
    ].copy()
    return {
        "pairwise_effects": effect_frame,
        "site_level_losses": pd.concat(sites, ignore_index=True) if sites else pd.DataFrame(),
        "bootstrap_distributions": pd.DataFrame(distributions),
        "multiplicity_report": multiplicity,
    }


def _context(
    value: Mapping[str, Any],
) -> tuple[Mapping[str, pd.DataFrame], Mapping[str, str]]:
    if set(value) != {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }:
        raise ClusteredInferenceError("E5 batch_context keys drifted")
    if (
        type(value.get("execution_id")) is not str
        or not value["execution_id"]
        or type(value.get("rng_seed")) is not int
        or value["rng_seed"] != 1729
        or not isinstance(value.get("tables"), Mapping)
        or not isinstance(value.get("stage_results"), Mapping)
        or not isinstance(value.get("model_availability"), Mapping)
        or not isinstance(value.get("software_evidence"), Mapping)
    ):
        raise ClusteredInferenceError("E5 batch_context value drifted")
    tables = cast(Mapping[str, Any], value["tables"])
    availability = cast(Mapping[str, Any], value["model_availability"])
    if any(type(table) is not pd.DataFrame for table in tables.values()):
        raise ClusteredInferenceError("E5 tables are not DataFrames")
    if any(type(key) is not str or type(status) is not str for key, status in availability.items()):
        raise ClusteredInferenceError("E5 model availability drifted")
    if set(cast(Mapping[str, Any], value["software_evidence"])) != {
        "public_tests_xml", "test_report", "openapi", "openapi_contract_report",
        "end_to_end_report", "environment",
    }:
        raise ClusteredInferenceError("E5 software evidence keys drifted")
    return cast(Mapping[str, pd.DataFrame], tables), cast(Mapping[str, str], availability)


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    _validate(authority, sealed_batch_contract)
    tables, availability = _context(batch_context)
    if dict(availability) != dict(
        cast(Mapping[str, Any], sealed_batch_contract.get("model_availability", {}))
    ):
        raise ClusteredInferenceError("E5 model availability is not batch-bound")
    source = tables.get(INPUT_TABLE)
    if type(source) is not pd.DataFrame:
        raise ClusteredInferenceError(f"E5 input table is absent: {INPUT_TABLE}")
    result = paired_clustered_inference(
        source.copy(deep=True), model_availability=availability, rng_seed=1729
    )
    effects = result["pairwise_effects"]
    estimated = int(effects["status"].eq("estimated").sum())
    report = (
        "# Closure V1 E5 paired clustered inference\n\n"
        "Bootstrap: 5,000 paired `(source_id, site_id)` resamples, retaining all "
        "paired rows. Holm correction is within family only.\n\n"
        f"Estimated comparisons: {estimated}; not estimable: {len(effects) - estimated}.\n"
    )
    artifacts = {
        path: {
            "format": format_name,
            "payload": payload,
            "manifest_last": path == OUTPUT_PATHS[-1],
        }
        for path, format_name, payload in zip(
            OUTPUT_PATHS,
            ("csv", "csv", "parquet", "csv", "markdown"),
            (
                result["pairwise_effects"],
                result["site_level_losses"],
                result["bootstrap_distributions"],
                result["multiplicity_report"],
                report,
            ),
            strict=True,
        )
    }
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed" if estimated else "completed_unavailable",
        "artifacts": artifacts,
        "tables": result,
        "diagnostics": {
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "cluster_unit": ["source_id", "site_id"],
            "unavailable_model_ids": sorted(
                model for model, status in availability.items() if status != "available"
            ),
            "row_level_independence_assumed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


__all__ = [
    "ClusteredInferenceError",
    "component_contract",
    "component_contract_sha256",
    "paired_clustered_inference",
    "preflight_closure_sealed_batch_component",
    "execute_closure_sealed_batch_component",
]
