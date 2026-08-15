"""Pure Closure V1 E2 site-transfer evaluation component.

The module never opens a dataset or writes an artifact.  The sealed E0-U
runner supplies already-opened, locked tables through ``batch_context`` and
owns the only publication transaction.  E2A evaluates the fixed location
holdout.  E2B always builds the predeclared five-fold assignment from
outcome-free site strata and evaluates fold-specific predictions when those
predictions are present; absence is retained explicitly rather than rescued
with a post-hoc fit.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    fbeta_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
)


COMPONENT_ID = "E2_site_transfer"
STAGE_ID = "E2"
GATE = "E0-U"
RNG_SEED = 1729
FOLD_COUNT = 5
HORIZONS = (1, 2, 3)
MINIMUM_MODELS = ("B1", "B2", "P0", "P1", "M0")
UNAVAILABLE_MODELS = ("P0", "P1")
SOFTWARE_EVIDENCE_KEYS = frozenset(
    {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }
)
CONTEXT_KEYS = frozenset(
    {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }
)
E2A_COHORTS = ("location_holdout",)
PREDICTION_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "common_origin_id",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
)
PREDICTION_REQUIRED_COLUMNS = (
    *PREDICTION_KEY_COLUMNS,
    "evaluation_cohort",
    "evaluation_role",
    "terminal_status",
    "bloom_status",
    "bloom_probability",
    "actual_bloom",
    "alert_threshold",
)
SITE_STRATA_COLUMNS = (
    "source_id",
    "site_id",
    "series_length_band",
    "historical_bloom_present",
    "coverage_band",
)
OUTPUT_PATHS = (
    "reports/closure_v1/02_site_transfer/location_holdout_metrics.csv",
    "reports/closure_v1/02_site_transfer/site_level_metrics.csv",
    "reports/closure_v1/02_site_transfer/fold_assignments.csv",
    "reports/closure_v1/02_site_transfer/generalization_gap.csv",
    "reports/closure_v1/02_site_transfer/site_transfer_report.md",
)
OUTPUT_TABLES = (
    "e2_location_metrics",
    "e2_site_metrics",
    "e2_fold_assignments",
    "e2_generalization_gaps",
)
REQUIRED_NONEMPTY_TABLES = (
    "e2_location_metrics",
    "e2_site_metrics",
    "e2_fold_assignments",
)


class ClosureSiteTransferError(RuntimeError):
    """Raised when the E2 in-memory contract drifts."""


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


def _contract_sha256(contract: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(dict(contract))).hexdigest()


def _require_authority(authority: Mapping[str, Any]) -> None:
    required = {
        "gate": GATE,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    if not isinstance(authority, Mapping):
        raise ClosureSiteTransferError("E2 authority is not a mapping")
    for key, expected in required.items():
        if type(authority.get(key)) is not type(expected) or authority.get(key) != expected:
            raise ClosureSiteTransferError(f"E2 authority field drifted: {key}")


def _require_component_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract, Mapping):
        raise ClosureSiteTransferError("E2 sealed contract is not a mapping")
    if contract.get("formal_model_lock_gate") != "E0-M" or contract.get(
        "execution_gate"
    ) != GATE:
        raise ClosureSiteTransferError("E2 sealed gate contract drifted")
    components = contract.get("components")
    if not isinstance(components, Sequence) or isinstance(components, (str, bytes)):
        raise ClosureSiteTransferError("E2 component registry is malformed")
    matches = [
        row
        for row in components
        if isinstance(row, Mapping) and row.get("component_id") == COMPONENT_ID
    ]
    if (
        len(matches) != 1
        or matches[0].get("stage_id") != STAGE_ID
        or matches[0].get("preflight_api")
        != "preflight_closure_sealed_batch_component"
        or matches[0].get("execute_api")
        != "execute_closure_sealed_batch_component"
    ):
        raise ClosureSiteTransferError("E2 component registry binding drifted")
    output_contracts = contract.get("component_output_contracts")
    expected_output_contract = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "output_tables": list(OUTPUT_TABLES),
        "required_nonempty_tables": list(REQUIRED_NONEMPTY_TABLES),
        "completed_nonempty_tables": [],
        "unavailable_nonempty_tables": [],
        "unavailable_empty_tables": [],
    }
    if (
        not isinstance(output_contracts, Sequence)
        or isinstance(output_contracts, (str, bytes))
        or list(output_contracts).count(expected_output_contract) != 1
    ):
        raise ClosureSiteTransferError("E2 output table contract drifted")


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Validate source-independent E2 bindings without dataset or filesystem I/O."""

    _require_authority(authority)
    _require_component_contract(sealed_batch_contract)
    if not isinstance(repo_root, Path):
        raise ClosureSiteTransferError("E2 repository root is not a Path")
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": _contract_sha256(sealed_batch_contract),
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def _copy_tables(value: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for key, frame in value.items():
        if type(key) is not str or not key:
            raise ClosureSiteTransferError("E2 table name is malformed")
        if not isinstance(frame, pd.DataFrame):
            raise ClosureSiteTransferError(f"E2 table is not a DataFrame: {key}")
        tables[key] = frame.copy(deep=True)
    return tables


def _validate_batch_context(batch_context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(batch_context, Mapping) or set(batch_context) != CONTEXT_KEYS:
        raise ClosureSiteTransferError("E2 batch_context keys drifted")
    execution_id = batch_context.get("execution_id")
    if type(execution_id) is not str or not execution_id:
        raise ClosureSiteTransferError("E2 execution_id is malformed")
    if type(batch_context.get("rng_seed")) is not int or batch_context["rng_seed"] != RNG_SEED:
        raise ClosureSiteTransferError("E2 RNG seed drifted")
    stage_results = batch_context.get("stage_results")
    availability = batch_context.get("model_availability")
    software_evidence = batch_context.get("software_evidence")
    if (
        not isinstance(stage_results, Mapping)
        or not isinstance(availability, Mapping)
        or not isinstance(software_evidence, Mapping)
    ):
        raise ClosureSiteTransferError("E2 context mappings are malformed")
    if software_evidence:
        raise ClosureSiteTransferError("E2 received unrelated software evidence")
    stage_results_copy: dict[str, dict[str, Any]] = {}
    for key, value in stage_results.items():
        if type(key) is not str or not key or not isinstance(value, Mapping):
            raise ClosureSiteTransferError("E2 stage-result mapping drifted")
        stage_results_copy[key] = dict(value)
    availability_copy: dict[str, str] = {}
    for key, value in availability.items():
        if type(key) is not str or value not in {"available", "unavailable"}:
            raise ClosureSiteTransferError("E2 model availability dialect drifted")
        availability_copy[key] = cast(str, value)
    for model_id in UNAVAILABLE_MODELS:
        if availability_copy.get(model_id) != "unavailable":
            raise ClosureSiteTransferError(f"E2 unavailable model drifted: {model_id}")
    tables = batch_context.get("tables")
    if not isinstance(tables, Mapping):
        raise ClosureSiteTransferError("E2 tables collection is malformed")
    return {
        "execution_id": execution_id,
        "rng_seed": RNG_SEED,
        "tables": _copy_tables(tables),
        "stage_results": stage_results_copy,
        "model_availability": availability_copy,
        "software_evidence": copy.deepcopy(dict(software_evidence)),
    }


def _exact_integer(series: pd.Series, *, name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    values = numeric.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ClosureSiteTransferError(f"E2 {name} is not exact integer")
    return numeric.astype("int64")


def _prediction_frame(frame: pd.DataFrame, *, context: str) -> pd.DataFrame:
    missing = set(PREDICTION_REQUIRED_COLUMNS).difference(frame.columns)
    if missing:
        raise ClosureSiteTransferError(f"E2 {context} columns missing: {sorted(missing)}")
    value = frame.copy(deep=True)
    if value.empty:
        raise ClosureSiteTransferError(f"E2 {context} is empty")
    for column in (
        "source_id",
        "site_id",
        "common_origin_id",
        "model_id",
        "evaluation_cohort",
        "evaluation_role",
        "terminal_status",
        "bloom_status",
    ):
        if value[column].isna().any() or (value[column].astype(str).str.len() == 0).any():
            raise ClosureSiteTransferError(f"E2 {context} {column} is malformed")
        value[column] = value[column].astype(str)
    value["horizon_months"] = _exact_integer(value["horizon_months"], name="horizon")
    value["model_seed"] = _exact_integer(value["model_seed"], name="model seed")
    value["seed_slot"] = _exact_integer(value["seed_slot"], name="seed slot")
    if not value["horizon_months"].isin(HORIZONS).all():
        raise ClosureSiteTransferError(f"E2 {context} horizon drifted")
    if not value["evaluation_role"].eq("test").all():
        raise ClosureSiteTransferError(f"E2 {context} evaluation role drifted")
    if not value["evaluation_cohort"].eq("location_holdout").all():
        raise ClosureSiteTransferError(
            f"E2 {context} is not restricted to the locked location holdout"
        )
    if value.duplicated(list(PREDICTION_KEY_COLUMNS)).any():
        raise ClosureSiteTransferError(f"E2 {context} contains duplicate predictions")
    for column in ("bloom_probability", "actual_bloom", "alert_threshold"):
        value[column] = pd.to_numeric(value[column], errors="coerce")
    terminal_statuses = {
        "success",
        "input_ineligible",
        "target_unavailable",
        "model_unavailable",
        "numerical_failure",
        "infrastructure_failure",
        "not_applicable",
    }
    if not value["bloom_status"].isin(terminal_statuses).all():
        raise ClosureSiteTransferError(f"E2 {context} bloom status drifted")
    success = value["bloom_status"].eq("success")
    if value.loc[success, ["bloom_probability", "actual_bloom", "alert_threshold"]].isna().any().any():
        raise ClosureSiteTransferError(f"E2 {context} successful row is incomplete")
    if (
        not value.loc[success, "bloom_probability"].between(0.0, 1.0).all()
        or not value.loc[success, "alert_threshold"].between(0.0, 1.0).all()
        or not value.loc[success, "actual_bloom"].isin([0.0, 1.0]).all()
    ):
        raise ClosureSiteTransferError(f"E2 {context} probability/label range drifted")
    observed_models = set(value["model_id"])
    if not set(MINIMUM_MODELS).issubset(observed_models):
        raise ClosureSiteTransferError("E2 minimum model set is incomplete")
    unavailable = value["model_id"].isin(UNAVAILABLE_MODELS)
    if not value.loc[unavailable, "bloom_status"].eq("model_unavailable").all():
        raise ClosureSiteTransferError("E2 P0/P1 unavailable terminal rows are absent or drifted")
    if value.loc[unavailable, "bloom_probability"].notna().any():
        raise ClosureSiteTransferError("E2 unavailable models contain invented predictions")
    return value.sort_values(list(PREDICTION_KEY_COLUMNS), kind="mergesort").reset_index(drop=True)


def _finite_optional(group: pd.DataFrame, actual: str, predicted: str) -> tuple[np.ndarray, np.ndarray] | None:
    if actual not in group or predicted not in group:
        return None
    left = pd.to_numeric(group[actual], errors="coerce").to_numpy(dtype="float64")
    right = pd.to_numeric(group[predicted], errors="coerce").to_numpy(dtype="float64")
    mask = np.isfinite(left) & np.isfinite(right)
    if not mask.any():
        return None
    return left[mask], right[mask]


def _metric_record(group: pd.DataFrame) -> dict[str, Any]:
    total = len(group)
    successful = group.loc[group["bloom_status"].eq("success")].copy()
    sites = group[["source_id", "site_id"]].drop_duplicates()
    base: dict[str, Any] = {
        "terminal_status": (
            "success" if len(successful) else str(group["bloom_status"].iloc[0])
        ),
        "site_count": int(len(sites)),
        "event_count": int(total),
        "successful_event_count": int(len(successful)),
        "prediction_availability_rate": float(len(successful) / total) if total else 0.0,
        "positive_count": 0,
        "pr_auc": None,
        "brier": None,
        "recall": None,
        "precision": None,
        "macro_f1": None,
        "f2": None,
        "alert_rate": None,
        "rmse": None,
        "mae": None,
        "coverage": None,
        "interval_width": None,
    }
    if successful.empty:
        return base
    labels = successful["actual_bloom"].to_numpy(dtype="int64")
    probabilities = successful["bloom_probability"].to_numpy(dtype="float64")
    thresholds = successful["alert_threshold"].to_numpy(dtype="float64")
    alerts = probabilities >= thresholds
    base.update(
        {
            "positive_count": int(labels.sum()),
            "pr_auc": (
                float(average_precision_score(labels, probabilities))
                if np.unique(labels).size == 2
                else None
            ),
            "brier": float(brier_score_loss(labels, probabilities)),
            "recall": float(recall_score(labels, alerts, zero_division=0)),
            "precision": float(precision_score(labels, alerts, zero_division=0)),
            "macro_f1": float(
                f1_score(labels, alerts, average="macro", zero_division=0)
            ),
            "f2": float(fbeta_score(labels, alerts, beta=2.0, zero_division=0)),
            "alert_rate": float(np.mean(alerts)),
        }
    )
    continuous = _finite_optional(successful, "actual_value", "predicted_value")
    if continuous is not None:
        actual, predicted = continuous
        base["rmse"] = float(math.sqrt(mean_squared_error(actual, predicted)))
        base["mae"] = float(mean_absolute_error(actual, predicted))
    if {"prediction_lower", "prediction_upper", "actual_value"}.issubset(successful.columns):
        lower = pd.to_numeric(successful["prediction_lower"], errors="coerce").to_numpy(dtype="float64")
        upper = pd.to_numeric(successful["prediction_upper"], errors="coerce").to_numpy(dtype="float64")
        actual = pd.to_numeric(successful["actual_value"], errors="coerce").to_numpy(dtype="float64")
        mask = np.isfinite(lower) & np.isfinite(upper) & np.isfinite(actual) & (lower <= upper)
        if mask.any():
            base["coverage"] = float(np.mean((actual[mask] >= lower[mask]) & (actual[mask] <= upper[mask])))
            base["interval_width"] = float(np.mean(upper[mask] - lower[mask]))
    return base


def _group_metrics(frame: pd.DataFrame, *, design: str, include_site: bool = False) -> pd.DataFrame:
    columns = [
        "model_id",
        "model_seed",
        "seed_slot",
        "horizon_months",
        "evaluation_cohort",
    ]
    if include_site:
        columns = ["source_id", "site_id", *columns]
    if design == "E2B":
        columns.append("fold_id")
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(columns, sort=True, dropna=False):
        values = key if isinstance(key, tuple) else (key,)
        row = dict(zip(columns, values, strict=True))
        row["design"] = design
        row.update(_metric_record(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(columns, kind="mergesort").reset_index(drop=True)


def build_grouped_fold_assignments(site_strata: pd.DataFrame, *, rng_seed: int = RNG_SEED) -> pd.DataFrame:
    """Create immutable five-fold site assignments without using test outcomes."""

    if set(SITE_STRATA_COLUMNS).difference(site_strata.columns):
        raise ClosureSiteTransferError("E2 site-strata columns are incomplete")
    value = site_strata.loc[:, SITE_STRATA_COLUMNS].copy(deep=True)
    if value.empty or value.duplicated(["source_id", "site_id"]).any():
        raise ClosureSiteTransferError("E2 site strata are empty or duplicated")
    for column in SITE_STRATA_COLUMNS:
        if value[column].isna().any():
            raise ClosureSiteTransferError(f"E2 site stratum is null: {column}")
        value[column] = value[column].astype(str)
    strata = list(SITE_STRATA_COLUMNS[2:])
    value["stratum_id"] = value[strata].agg("|".join, axis=1)
    value["_order"] = value.apply(
        lambda row: hashlib.sha256(
            f"E2B|{rng_seed}|{row['source_id']}|{row['site_id']}".encode("utf-8")
        ).hexdigest(),
        axis=1,
    )
    value = value.sort_values(["stratum_id", "_order", "source_id", "site_id"], kind="mergesort")
    offsets = {
        stratum: int(
            hashlib.sha256(f"E2B|{rng_seed}|{stratum}".encode("utf-8")).hexdigest(),
            16,
        )
        % FOLD_COUNT
        for stratum in value["stratum_id"].unique()
    }
    positions = value.groupby("stratum_id", sort=True).cumcount()
    value["fold_id"] = (
        positions + value["stratum_id"].map(offsets).astype("int64")
    ).mod(FOLD_COUNT).add(1)
    return value.drop(columns=["_order"]).sort_values(["fold_id", "source_id", "site_id"], kind="mergesort").reset_index(drop=True)


def build_generalization_gaps(metrics: pd.DataFrame) -> pd.DataFrame:
    identity = ["model_id", "model_seed", "seed_slot", "horizon_months"]
    subset = metrics.loc[
        metrics["design"].eq("E2A")
        & metrics["evaluation_cohort"].isin(E2A_COHORTS)
    ].copy()
    rows: list[dict[str, Any]] = []
    for key, group in subset.groupby(identity, sort=True):
        by_cohort = {str(row["evaluation_cohort"]): row for _, row in group.iterrows()}
        heldout = by_cohort.get("location_holdout")
        for metric in ("pr_auc", "brier", "rmse", "mae", "recall", "coverage", "prediction_availability_rate"):
            heldout_value = None if heldout is None else heldout.get(metric)
            lower_better = metric in {"brier", "rmse", "mae"}
            heldout_float = (
                float(cast(Any, heldout_value)) if pd.notna(heldout_value) else None
            )
            rows.append(
                {
                    **dict(zip(identity, key, strict=True)),
                    "metric": metric,
                    "legacy_value": None,
                    "heldout_value": heldout_float,
                    "delta_name": "error_increase" if lower_better else "location_transfer_gap",
                    "delta": None,
                    "estimable": False,
                    "not_estimable_reason": "legacy_evaluation_surface_not_frozen_before_e0_u",
                }
            )
    return pd.DataFrame(rows).sort_values([*identity, "metric"], kind="mergesort").reset_index(drop=True)


def _report(metrics: pd.DataFrame, gaps: pd.DataFrame, *, e2b_available: bool) -> str:
    heldout = metrics.loc[
        metrics["design"].eq("E2A")
        & metrics["evaluation_cohort"].eq("location_holdout")
    ]
    unavailable = int(heldout["terminal_status"].eq("model_unavailable").sum())
    estimable_gaps = int(gaps["estimable"].sum()) if not gaps.empty else 0
    return (
        "# Closure V1 E2 site-transfer evaluation\n\n"
        "This is internal evaluation on held-out WQP monitoring locations, not "
        "external validation on unseen water bodies.\n\n"
        f"- E2A metric rows: {len(metrics.loc[metrics['design'].eq('E2A')])}\n"
        f"- held-out unavailable rows retained: {unavailable}\n"
        f"- estimable transfer gaps: {estimable_gaps}\n"
        "- no legacy test surface was invented from fit, selection, or calibration rows.\n"
        f"- E2B grouped predictions supplied: {'yes' if e2b_available else 'no'}\n"
        "- E2B is terminally unavailable because no authenticated grouped prediction surface existed before E0-U.\n"
        "- P0 and P1 remain model_unavailable; no prediction was fabricated.\n"
    )


def _artifact(format_name: str, payload: Any, *, manifest_last: bool = False) -> dict[str, Any]:
    return {"format": format_name, "payload": payload, "manifest_last": manifest_last}


def validate_site_transfer_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ClosureSiteTransferError("E2 result is not a mapping")
    required = {
        "component_id",
        "stage_id",
        "status",
        "artifacts",
        "tables",
        "diagnostics",
        "outcome_paths_opened",
        "writes_performed",
    }
    if set(result) != required:
        raise ClosureSiteTransferError("E2 result keys drifted")
    if result.get("component_id") != COMPONENT_ID or result.get("stage_id") != STAGE_ID:
        raise ClosureSiteTransferError("E2 result identity drifted")
    if result.get("status") not in {"completed", "completed_unavailable"}:
        raise ClosureSiteTransferError("E2 result status drifted")
    if result.get("outcome_paths_opened") is not True or result.get("writes_performed") is not False:
        raise ClosureSiteTransferError("E2 result I/O flags drifted")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != set(OUTPUT_PATHS):
        raise ClosureSiteTransferError("E2 artifact path set drifted")
    for path, envelope in artifacts.items():
        if not isinstance(envelope, Mapping) or set(envelope) != {"format", "payload", "manifest_last"}:
            raise ClosureSiteTransferError(f"E2 artifact envelope drifted: {path}")
        if envelope["format"] not in {"csv", "json", "markdown", "parquet", "xml"}:
            raise ClosureSiteTransferError(f"E2 artifact format drifted: {path}")
        if type(envelope["manifest_last"]) is not bool:
            raise ClosureSiteTransferError(f"E2 manifest-last flag drifted: {path}")
    if sum(bool(cast(Mapping[str, Any], item)["manifest_last"]) for item in artifacts.values()) != 1:
        raise ClosureSiteTransferError("E2 requires one report sentinel")
    tables = result.get("tables")
    if not isinstance(tables, Mapping) or set(tables) != set(OUTPUT_TABLES):
        raise ClosureSiteTransferError("E2 output table set drifted")
    for name, frame in tables.items():
        if type(frame) is not pd.DataFrame:
            raise ClosureSiteTransferError(f"E2 output table type drifted: {name}")
    for name in REQUIRED_NONEMPTY_TABLES:
        if cast(pd.DataFrame, tables[name]).empty:
            raise ClosureSiteTransferError(f"E2 required output table is empty: {name}")
    return dict(result)


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Evaluate E2 entirely in memory and return runner-owned artifact payloads."""

    preflight_closure_sealed_batch_component(authority, sealed_batch_contract, repo_root)
    context = _validate_batch_context(batch_context)
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(
        cast(Mapping[str, Any], context["model_availability"])
    ) != dict(sealed_availability):
        raise ClosureSiteTransferError("E2 model availability is not batch-bound")
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "predictions_long" not in tables or "e2_site_strata" not in tables:
        raise ClosureSiteTransferError("E2 required in-memory tables are absent")
    predictions = _prediction_frame(tables["predictions_long"], context="E1 predictions")
    if (
        predictions.groupby(["source_id", "site_id"], sort=True)["evaluation_cohort"]
        .nunique()
        .ne(1)
        .any()
    ):
        raise ClosureSiteTransferError("E2 site crossed evaluation cohorts")
    evaluation = predictions.loc[predictions["evaluation_role"].eq("test")].copy()
    if set(evaluation["evaluation_cohort"]) != {"location_holdout"}:
        raise ClosureSiteTransferError("E2A location-holdout cohort drifted")
    assignments = build_grouped_fold_assignments(tables["e2_site_strata"], rng_seed=RNG_SEED)
    prediction_sites = set(
        map(
            tuple,
            predictions[["source_id", "site_id"]]
            .drop_duplicates()
            .itertuples(index=False, name=None),
        )
    )
    assignment_sites = set(
        map(
            tuple,
            assignments[["source_id", "site_id"]].itertuples(index=False, name=None),
        )
    )
    if assignment_sites != prediction_sites:
        raise ClosureSiteTransferError("E2 site-strata universe drifted")
    e2a_metrics = _group_metrics(evaluation, design="E2A")
    site_metrics = _group_metrics(evaluation, design="E2A", include_site=True)
    if "e2_grouped_predictions" in tables:
        raise ClosureSiteTransferError(
            "E2B grouped predictions were not frozen before E0-U"
        )
    e2b_available = False
    metrics = e2a_metrics
    gaps = build_generalization_gaps(e2a_metrics)
    report = _report(metrics, gaps, e2b_available=e2b_available)
    artifacts = {
        OUTPUT_PATHS[0]: _artifact("csv", metrics.copy(deep=True)),
        OUTPUT_PATHS[1]: _artifact("csv", site_metrics.copy(deep=True)),
        OUTPUT_PATHS[2]: _artifact("csv", assignments.copy(deep=True)),
        OUTPUT_PATHS[3]: _artifact("csv", gaps.copy(deep=True)),
        OUTPUT_PATHS[4]: _artifact("markdown", report, manifest_last=True),
    }
    status = "completed_unavailable"
    result = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": status,
        "artifacts": artifacts,
        "tables": {
            "e2_location_metrics": metrics.copy(deep=True),
            "e2_site_metrics": site_metrics.copy(deep=True),
            "e2_fold_assignments": assignments.copy(deep=True),
            "e2_generalization_gaps": gaps.copy(deep=True),
        },
        "diagnostics": {
            "execution_id": context["execution_id"],
            "e2a_complete": True,
            "e2a_estimand": "locked_location_holdout_only",
            "legacy_surface_available": False,
            "legacy_gap_not_estimable_reason": "legacy_evaluation_surface_not_frozen_before_e0_u",
            "e2b_predeclared": True,
            "e2b_predictions_available": e2b_available,
            "fold_count": FOLD_COUNT,
            "unavailable_models_retained": list(UNAVAILABLE_MODELS),
            "writes_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
    return validate_site_transfer_result(result)
