#!/usr/bin/env python
"""Closed E5 confirmatory ledger for the current Closure V1 model lock.

Every registered confirmatory hypothesis depends on at least one model that is
terminally unavailable. E5 preserves the complete 27-row registry, the locked
Holm universes and intent denominators, while emitting no invented inference.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd


COMPONENT_ID = "E5_clustered_inference"
STAGE_ID = "E5"
INPUT_TABLE = "paired_metric_rows"
REGISTRY_TABLE = "hypothesis_registry"
BOOTSTRAP_REPLICATES = 5000
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
LOCKED_UNAVAILABLE_MODELS = ("P0", "P1", "A2")
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
HYPOTHESIS_COLUMNS = (
    "hypothesis_id",
    "multiplicity_family",
    "comparison_id",
    "endpoints",
    "estimand",
    "alternative",
    "evaluation_cohort",
    "horizons_months",
    "multiplicity_universe_size",
    "correction_method",
    "family_wise_alpha",
    "availability_condition",
    "status",
    "availability_reason",
    "p_value",
    "effect_estimate",
    "confidence_interval",
    "holm_universe_retained",
)
FAMILY_COUNTS = {"A": 3, "B": 13, "C": 1, "D": 9, "E": 1}
FAMILY_UNIVERSES = {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}
OUTPUT_PATHS = (
    "reports/closure_v1/05_inference/pairwise_effects.csv",
    "reports/closure_v1/05_inference/site_level_losses.csv",
    "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
    "reports/closure_v1/05_inference/multiplicity_report.csv",
    "reports/closure_v1/05_inference/statistical_inference_report.md",
)
OUTPUT_TABLES = (
    "pairwise_effects",
    "site_level_losses",
    "bootstrap_distributions",
    "multiplicity_report",
)
COMPONENT_CONTRACT = {
    "schema_version": "closure_e5_confirmatory_unavailable_ledger_v3",
    "component_id": COMPONENT_ID,
    "stage_id": STAGE_ID,
    "input_tables": [INPUT_TABLE, REGISTRY_TABLE],
    "input_columns": {
        INPUT_TABLE: list(INPUT_COLUMNS),
        REGISTRY_TABLE: list(HYPOTHESIS_COLUMNS),
    },
    "hypothesis_count": 27,
    "family_counts": FAMILY_COUNTS,
    "holm_universe_sizes": FAMILY_UNIVERSES,
    "cluster_unit": "holdout_group_id",
    "bootstrap_replicates_if_estimable": BOOTSTRAP_REPLICATES,
    "current_lock_branch": "all_confirmatory_hypotheses_not_estimable_model_unavailable",
    "future_available_branch": "fail_closed_requires_successor_contract",
    "output_paths": list(OUTPUT_PATHS),
    "filesystem_writes": "forbidden",
}


class ClusteredInferenceError(RuntimeError):
    """Raised when the closed E5 inference contract is violated."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_canonical_json_bytes(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return hashlib.sha256(_canonical_json_bytes(COMPONENT_CONTRACT)).hexdigest()


def _validate_boundary(
    authority: Mapping[str, Any], contract: Mapping[str, Any]
) -> str:
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
    if not isinstance(authority, Mapping) or any(
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
        or contract.get("one_batch_only") is not True
        or authority.get("sealed_batch_command") != contract.get("sealed_command")
        or not isinstance(components, Sequence)
        or isinstance(components, (str, bytes))
        or list(components).count(expected_component) != 1
    ):
        raise ClusteredInferenceError("E5 sealed batch contract drifted")
    return hashlib.sha256(_canonical_json_bytes(dict(contract))).hexdigest()


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
        "contract_sha256": _validate_boundary(authority, sealed_batch_contract),
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def _validate_paired_rows(frame: pd.DataFrame) -> tuple[int, int, int]:
    if tuple(frame.columns) != INPUT_COLUMNS or frame.empty:
        raise ClusteredInferenceError("E5 paired metric surface is absent or drifted")
    work = frame.copy(deep=True)
    text_columns = (
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "model_id",
        "evaluation_cohort",
        "metric",
        "terminal_status",
    )
    if work[list(text_columns)].isna().any().any():
        raise ClusteredInferenceError("E5 paired identity contains nulls")
    for column in text_columns:
        work[column] = work[column].astype(str)
        if work[column].str.len().eq(0).any():
            raise ClusteredInferenceError(f"E5 text identity drifted: {column}")
    if (
        not work["source_id"].eq("wqp").all()
        or not work["evaluation_cohort"].eq("location_holdout").all()
        or not work["holdout_group_id"].eq(
            work["source_id"] + "::" + work["site_id"]
        ).all()
    ):
        raise ClusteredInferenceError("E5 locked location-holdout identity drifted")
    for column in ("horizon_months", "model_seed", "seed_slot"):
        numeric = pd.to_numeric(work[column], errors="raise")
        values = numeric.to_numpy(dtype="float64")
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ClusteredInferenceError(f"E5 non-integral identity: {column}")
        work[column] = numeric.astype("int64")
    if (
        not work["horizon_months"].isin([1, 2, 3]).all()
        or not work["seed_slot"].isin(REGISTERED_SEEDS).all()
        or work.duplicated(list(INPUT_COLUMNS[:10])).any()
    ):
        raise ClusteredInferenceError("E5 paired key universe drifted")
    success = work["terminal_status"].eq("success")
    loss = pd.to_numeric(work["loss"], errors="coerce")
    if loss.loc[success].isna().any() or loss.loc[~success].notna().any():
        raise ClusteredInferenceError("E5 terminal status/loss binding drifted")
    intents = work[
        [
            "source_id",
            "site_id",
            "holdout_group_id",
            "common_origin_id",
            "horizon_months",
        ]
    ].drop_duplicates()
    return len(intents), intents["holdout_group_id"].nunique(), len(work)


def _normalize_registry(frame: pd.DataFrame) -> pd.DataFrame:
    if tuple(frame.columns) != HYPOTHESIS_COLUMNS or len(frame) != 27:
        raise ClusteredInferenceError("E5 hypothesis registry shape drifted")
    registry = frame.copy(deep=True).fillna("")
    for column in HYPOTHESIS_COLUMNS:
        registry[column] = registry[column].astype(str)
    if registry["hypothesis_id"].duplicated().any():
        raise ClusteredInferenceError("E5 hypothesis identifiers are duplicated")
    observed_counts = registry["multiplicity_family"].value_counts().to_dict()
    if observed_counts != FAMILY_COUNTS:
        raise ClusteredInferenceError("E5 hypothesis-family registry drifted")
    universe = pd.to_numeric(
        registry["multiplicity_universe_size"], errors="raise"
    ).astype("int64")
    for family, expected in FAMILY_UNIVERSES.items():
        if not universe.loc[registry["multiplicity_family"].eq(family)].eq(expected).all():
            raise ClusteredInferenceError(f"E5 Holm universe drifted: {family}")
    alpha = pd.to_numeric(registry["family_wise_alpha"], errors="raise")
    if (
        not registry["correction_method"].eq("holm").all()
        or not alpha.eq(0.05).all()
        or not registry["evaluation_cohort"].eq("locked_location_holdout").all()
        or not registry["status"].eq("not_estimable_model_unavailable").all()
        or not registry["availability_reason"].eq(
            "P1_model_unavailable_no_substitution"
        ).all()
        or not registry["holm_universe_retained"].str.lower().eq("true").all()
        or registry[["p_value", "effect_estimate", "confidence_interval"]]
        .ne("")
        .any()
        .any()
    ):
        raise ClusteredInferenceError("E5 frozen unavailable ledger drifted")
    registry["multiplicity_universe_size"] = universe
    registry["family_wise_alpha"] = alpha.astype("float64")
    registry["holm_universe_retained"] = True
    for column in ("p_value", "effect_estimate", "confidence_interval"):
        registry[column] = None
    return registry.sort_values("hypothesis_id", kind="mergesort").reset_index(
        drop=True
    )


def build_unavailable_confirmatory_ledger(
    paired_rows: pd.DataFrame,
    hypothesis_registry: pd.DataFrame,
    *,
    model_availability: Mapping[str, str],
) -> dict[str, pd.DataFrame]:
    if any(
        model_availability.get(model_id) != "unavailable"
        for model_id in LOCKED_UNAVAILABLE_MODELS
    ):
        raise ClusteredInferenceError(
            "E5 available-model branch requires a new pre-outcome contract"
        )
    intent_count, site_count, paired_registry_rows = _validate_paired_rows(paired_rows)
    registry = _normalize_registry(hypothesis_registry)
    effects = registry.copy(deep=True)
    effects["intent_origin_count"] = intent_count
    effects["intent_site_count"] = site_count
    effects["paired_metric_registry_row_count"] = paired_registry_rows
    effects["shared_success_origin_count"] = 0
    effects["shared_success_site_count"] = 0
    effects["raw_p_value"] = None
    effects["holm_p_value"] = None
    effects["effect_estimate_numeric"] = None
    effects["ci95_low"] = None
    effects["ci95_high"] = None
    effects["terminal_status"] = "not_estimable_model_unavailable"
    multiplicity = effects[
        [
            "hypothesis_id",
            "multiplicity_family",
            "multiplicity_universe_size",
            "correction_method",
            "family_wise_alpha",
            "terminal_status",
            "raw_p_value",
            "holm_p_value",
            "holm_universe_retained",
        ]
    ].copy(deep=True)
    site_losses = pd.DataFrame(
        columns=(
            "hypothesis_id",
            "holdout_group_id",
            "shared_success_origin_count",
            "loss_model_a",
            "loss_model_b",
            "delta",
        )
    )
    bootstrap = pd.DataFrame(
        columns=("hypothesis_id", "replicate", "cluster_unit", "delta")
    )
    return {
        "pairwise_effects": effects,
        "site_level_losses": site_losses,
        "bootstrap_distributions": bootstrap,
        "multiplicity_report": multiplicity,
    }


def _context(
    value: Mapping[str, Any],
) -> tuple[Mapping[str, pd.DataFrame], Mapping[str, str]]:
    expected_keys = {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
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
    if set(tables) != {INPUT_TABLE, REGISTRY_TABLE} or any(
        type(table) is not pd.DataFrame for table in tables.values()
    ):
        raise ClusteredInferenceError("E5 least-privilege table view drifted")
    evidence = cast(Mapping[str, Any], value["software_evidence"])
    if evidence:
        raise ClusteredInferenceError("E5 received unrelated software evidence")
    availability = cast(Mapping[str, Any], value["model_availability"])
    if any(type(key) is not str or type(status) is not str for key, status in availability.items()):
        raise ClusteredInferenceError("E5 model availability drifted")
    return cast(Mapping[str, pd.DataFrame], tables), cast(Mapping[str, str], availability)


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    _validate_boundary(authority, sealed_batch_contract)
    tables, availability = _context(batch_context)
    if dict(availability) != dict(
        cast(Mapping[str, Any], sealed_batch_contract.get("model_availability", {}))
    ):
        raise ClusteredInferenceError("E5 model availability is not batch-bound")
    result = build_unavailable_confirmatory_ledger(
        tables[INPUT_TABLE].copy(deep=True),
        tables[REGISTRY_TABLE].copy(deep=True),
        model_availability=availability,
    )
    effects = result["pairwise_effects"]
    report = (
        "# Closure V1 E5 confirmatory inference ledger\n\n"
        "All 27 preregistered hypotheses are retained with their original Holm "
        "universes (A=3, B=78, C=1, D=9, E=1). P0, P1 and A2 are terminally "
        "unavailable, so no effect, interval, p-value or bootstrap draw is "
        "estimable and no multiplicity family was reduced.\n\n"
        f"- locked intent-horizon denominator: {int(effects['intent_origin_count'].iloc[0])}\n"
        f"- locked holdout-group denominator: {int(effects['intent_site_count'].iloc[0])}\n"
        "- cluster unit under any successor contract: holdout_group_id.\n"
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
        "status": "completed_unavailable",
        "artifacts": artifacts,
        "tables": result,
        "diagnostics": {
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "cluster_unit": "holdout_group_id",
            "hypothesis_count": 27,
            "family_universe_sizes": FAMILY_UNIVERSES,
            "unavailable_model_ids": list(LOCKED_UNAVAILABLE_MODELS),
            "holm_universe_reduced": False,
            "row_level_independence_assumed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


__all__ = [
    "ClusteredInferenceError",
    "build_unavailable_confirmatory_ledger",
    "component_contract",
    "component_contract_sha256",
    "execute_closure_sealed_batch_component",
    "preflight_closure_sealed_batch_component",
]
