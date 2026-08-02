#!/usr/bin/env python
"""Build the locked, cutoff-safe closure holdout assignment.

The selector uses only WQP monitoring-location information available through
December 2021. Chlorophyll-a is never part of the precursor surface. Historical
binary bloom labels are read separately, through the same cutoff, only to
require complete h1--h3 targets and define the pre-specified historical-bloom
stratum.

Import the pure functions in this module for synthetic validation. The CLI is
deliberately guarded: a real assignment requires a valid protocol lock, the
locked hash of this script, the locked repository HEAD, and an explicit
execution flag. ``--dry-run`` validates those guards without reading the panel
or writing an assignment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_TARGETS = Path("data/targets/monthly_targets_model_v0.parquet")
DEFAULT_TARGET_MANIFEST = Path("data/targets/target_manifest_v0.json")
DEFAULT_CONFIG = Path("configs/closure_v1/location_holdout.yaml")
DEFAULT_PROTOCOL_LOCK = Path("reports/closure_v1/00_protocol/protocol_lock.json")
DEFAULT_ASSIGNMENT = Path("data/closure_v1/closure_holdout_assignment.csv")
DEFAULT_SUMMARY = Path("reports/closure_v1/00_protocol/holdout_summary_pre_cutoff.csv")
DEFAULT_MANIFEST = Path("reports/closure_v1/00_protocol/holdout_manifest.json")
DEFAULT_COHORT_FLOW = Path("reports/closure_v1/00_protocol/cohort_flow_preoutcome.csv")
DEFAULT_LEAKAGE_AUDIT = Path("reports/closure_v1/00_protocol/holdout_leakage_audit.json")

KEY_COLUMNS = ["source_id", "site_id", "year_month"]
NUTRIENT_COLUMNS = ["mean_TP_ugL", "mean_TN_ugL"]
TEMPERATURE_COLUMNS = ["mean_temperature_C"]
LIGHT_PROXY_COLUMNS = ["mean_secchi_depth_m", "mean_turbidity_NTU"]
PHYSICOCHEMICAL_COLUMNS = ["mean_DO_mgL", "mean_pH"]
PRECURSOR_VALUE_COLUMNS = (
    NUTRIENT_COLUMNS + TEMPERATURE_COLUMNS + LIGHT_PROXY_COLUMNS + PHYSICOCHEMICAL_COLUMNS
)
PRECURSOR_READ_COLUMNS = KEY_COLUMNS + PRECURSOR_VALUE_COLUMNS

HISTORICAL_OUTCOME_COLUMN = "bloom_h"
HISTORICAL_OUTCOME_READ_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    HISTORICAL_OUTCOME_COLUMN,
]

ASSIGNMENT_HOLDOUT = "internal_holdout"
ASSIGNMENT_DEVELOPMENT = "development"

ASSIGNMENT_OUTPUT_COLUMNS = [
    "source_id",
    "site_id",
    "holdout_group_id",
    "assignment_role",
    "stratum_id",
    "historical_bloom_presence",
    "precursor_coverage_fraction",
    "precursor_coverage_band",
    "series_length_months",
    "series_length_band",
    "deterministic_rank_sha256",
]

LOCATION_PROFILE_COLUMNS = [
    "source_id",
    "site_id",
    "holdout_group_id",
    "first_year_month",
    "last_year_month",
    "series_length_months",
    "input_eligible_months",
    "nutrient_coverage_fraction",
    "temperature_coverage_fraction",
    "light_coverage_fraction",
    "physicochemical_coverage_fraction",
    "context_coverage_fraction",
    "precursor_coverage_fraction",
    "precursor_coverage_band",
    "series_length_band",
    "eligible_origin_count",
    "first_eligible_origin",
    "last_eligible_origin",
    "first_historical_target_month",
    "last_historical_target_month",
    "historical_target_months",
    "historical_bloom_events",
    "historical_bloom_prevalence",
    "historical_bloom_presence",
    "stratum_id",
]


def _period(value: str, *, field_name: str) -> pd.Period:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError(f"{field_name} must use YYYY-MM format; received {value!r}")
    try:
        period = cast(pd.Period, pd.Period(value, freq="M"))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid calendar month: {value!r}") from exc
    if str(period) != value:
        raise ValueError(f"{field_name} is not a canonical calendar month: {value!r}")
    return period


def _dataframe_rows(frame: pd.DataFrame) -> Any:
    return frame.itertuples(index=False)


def _group_key_tuple(key: Any) -> tuple[Any, ...]:
    return key if isinstance(key, tuple) else (key,)


@dataclass(frozen=True)
class HoldoutConfig:
    """Locked decisions for the closure-v1 monitoring-location selector."""

    source_id: str = "wqp"
    information_cutoff: str = "2021-12"
    latest_eligible_origin: str = "2021-09"
    history_length_months: int = 12
    horizons_months: tuple[int, ...] = (1, 2, 3)
    bloom_threshold_ug_l: float = 30.0
    holdout_fraction: float = 0.20
    selection_seed: int = 20260802

    def __post_init__(self) -> None:
        cutoff = _period(self.information_cutoff, field_name="information_cutoff")
        latest_origin = _period(self.latest_eligible_origin, field_name="latest_eligible_origin")
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if self.history_length_months != 12:
            raise ValueError("closure_v1 requires a 12-month history")
        if self.horizons_months != (1, 2, 3):
            raise ValueError("closure_v1 requires complete horizons (1, 2, 3)")
        if latest_origin.ordinal + max(self.horizons_months) > cutoff.ordinal:
            raise ValueError("latest_eligible_origin would place a target after information_cutoff")
        if not math.isfinite(self.bloom_threshold_ug_l) or self.bloom_threshold_ug_l <= 0:
            raise ValueError("bloom_threshold_ug_l must be finite and positive")
        if not 0.0 < self.holdout_fraction < 1.0:
            raise ValueError("holdout_fraction must be strictly between zero and one")


@dataclass(frozen=True)
class HoldoutSelection:
    """Pure, in-memory products of cutoff-safe eligibility and assignment."""

    eligible_origins: pd.DataFrame
    location_profiles: pd.DataFrame
    assignment: pd.DataFrame
    quota_summary: pd.DataFrame


def _required_mapping(payload: dict[str, Any], key: str, *, context: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{context}.{key} must be a mapping")
    return value


def _require_config_value(payload: dict[str, Any], key: str, expected: Any, *, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise ValueError(f"{context}.{key} must be {expected!r}; found {actual!r}")


def load_holdout_config(config_path: Path) -> tuple[HoldoutConfig, dict[str, Any]]:
    """Load the machine-readable holdout contract and reject decision drift."""

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("location holdout config must be a YAML mapping")
    _require_config_value(payload, "schema_version", "closure_location_holdout_v1_1", context="config")
    _require_config_value(payload, "experiment_id", "closure_v1", context="config")

    inputs = _required_mapping(payload, "inputs", context="config")
    _require_config_value(inputs, "monthly_panel", DEFAULT_PANEL.as_posix(), context="inputs")
    _require_config_value(inputs, "monthly_targets", DEFAULT_TARGETS.as_posix(), context="inputs")
    _require_config_value(
        inputs,
        "target_manifest",
        DEFAULT_TARGET_MANIFEST.as_posix(),
        context="inputs",
    )

    unit = _required_mapping(payload, "unit", context="config")
    _require_config_value(unit, "unit_type", "wqp_monitoring_location", context="unit")
    _require_config_value(unit, "group_key", ["source_id", "site_id"], context="unit")
    _require_config_value(unit, "source_ids", ["wqp"], context="unit")
    _require_config_value(unit, "waterbody_claim_authorized", False, context="unit")

    boundary = _required_mapping(payload, "information_boundary", context="config")
    _require_config_value(boundary, "information_cutoff", "2021-12", context="information_boundary")
    _require_config_value(boundary, "last_eligible_origin", "2021-09", context="information_boundary")
    _require_config_value(
        boundary,
        "historical_target_rows_must_end_by",
        "2021-12",
        context="information_boundary",
    )
    _require_config_value(
        boundary,
        "post_cutoff_target_values_for_assignment",
        "forbidden",
        context="information_boundary",
    )
    _require_config_value(
        boundary,
        "post_cutoff_target_availability_for_assignment",
        "forbidden",
        context="information_boundary",
    )
    _require_config_value(
        boundary,
        "parquet_read_api_filter_required",
        "target_year_month_not_after_2021_12",
        context="information_boundary",
    )
    _require_config_value(
        boundary,
        "post_cutoff_target_rows_materialized_to_selector_logic",
        False,
        context="information_boundary",
    )
    _require_config_value(
        boundary,
        "storage_engine_internal_page_decoding_audited_or_claimed",
        False,
        context="information_boundary",
    )

    projection = _required_mapping(payload, "selection_projection", context="config")
    _require_config_value(
        projection,
        "permitted_precursor_columns",
        PRECURSOR_VALUE_COLUMNS,
        context="selection_projection",
    )
    _require_config_value(
        projection,
        "permitted_historical_outcome_columns",
        [HISTORICAL_OUTCOME_COLUMN],
        context="selection_projection",
    )
    _require_config_value(
        projection,
        "historical_outcome_deduplication_key",
        ["source_id", "site_id", "target_year_month"],
        context="selection_projection",
    )
    forbidden_chla = projection.get("forbidden_chla_input_columns")
    if not isinstance(forbidden_chla, list) or not forbidden_chla:
        raise ValueError("selection_projection.forbidden_chla_input_columns must be a non-empty list")
    if any(column in PRECURSOR_VALUE_COLUMNS for column in forbidden_chla):
        raise ValueError("a forbidden Chl-a field appears in the precursor allowlist")

    eligibility = _required_mapping(payload, "eligibility", context="config")
    _require_config_value(eligibility, "source_id_equals", "wqp", context="eligibility")
    _require_config_value(eligibility, "history_length_months", 12, context="eligibility")
    _require_config_value(eligibility, "consecutive_history_required", True, context="eligibility")
    _require_config_value(eligibility, "max_gap_months", 1, context="eligibility")
    _require_config_value(eligibility, "complete_horizons_required", [1, 2, 3], context="eligibility")
    _require_config_value(eligibility, "minimum_complete_historical_origins", 1, context="eligibility")
    _require_config_value(eligibility, "last_eligible_origin", "2021-09", context="eligibility")
    _require_config_value(
        eligibility,
        "all_eligibility_targets_not_after",
        "2021-12",
        context="eligibility",
    )

    coverage = _required_mapping(payload, "precursor_coverage", context="config")
    _require_config_value(
        coverage,
        "covered_month_rule",
        "nutrient_and_temperature_and_either_light_proxy_or_physicochemical",
        context="precursor_coverage",
    )
    _require_config_value(
        coverage,
        "location_coverage_fraction_denominator",
        "distinct_history_months_not_after_2021_12",
        context="precursor_coverage",
    )
    evidence_rules = _required_mapping(coverage, "monthly_evidence_rules", context="precursor_coverage")
    expected_evidence = {
        "nutrient": NUTRIENT_COLUMNS,
        "temperature": TEMPERATURE_COLUMNS,
        "light_proxy": LIGHT_PROXY_COLUMNS,
        "physicochemical": PHYSICOCHEMICAL_COLUMNS,
    }
    for evidence_name, columns in expected_evidence.items():
        evidence = _required_mapping(evidence_rules, evidence_name, context="monthly_evidence_rules")
        _require_config_value(evidence, "any_finite", columns, context=f"monthly_evidence_rules.{evidence_name}")
    bands = _required_mapping(coverage, "bands", context="precursor_coverage")
    low = _required_mapping(bands, "low", context="precursor_coverage.bands")
    medium = _required_mapping(bands, "medium", context="precursor_coverage.bands")
    high = _required_mapping(bands, "high", context="precursor_coverage.bands")
    _require_config_value(low, "lower_inclusive", 0.0, context="precursor_coverage.bands.low")
    _require_config_value(low, "upper_exclusive", 1.0 / 3.0, context="precursor_coverage.bands.low")
    _require_config_value(medium, "lower_inclusive", 1.0 / 3.0, context="precursor_coverage.bands.medium")
    _require_config_value(medium, "upper_exclusive", 2.0 / 3.0, context="precursor_coverage.bands.medium")
    _require_config_value(high, "lower_inclusive", 2.0 / 3.0, context="precursor_coverage.bands.high")
    _require_config_value(high, "upper_inclusive", 1.0, context="precursor_coverage.bands.high")

    stratification = _required_mapping(payload, "stratification", context="config")
    _require_config_value(
        stratification,
        "columns",
        ["historical_bloom_presence", "precursor_coverage_band", "series_length_band"],
        context="stratification",
    )
    bloom = _required_mapping(stratification, "historical_bloom_presence", context="stratification")
    _require_config_value(
        bloom,
        "bloom_threshold_ug_l",
        30.0,
        context="stratification.historical_bloom_presence",
    )
    _require_config_value(
        bloom,
        "repeated_horizon_rows_are_deduplicated",
        True,
        context="stratification.historical_bloom_presence",
    )

    sampling = _required_mapping(payload, "sampling", context="config")
    _require_config_value(sampling, "selection_fraction", 0.20, context="sampling")
    _require_config_value(sampling, "seed", 20260802, context="sampling")
    _require_config_value(
        sampling,
        "global_target_count_rule",
        "floor_eligible_count_times_fraction",
        context="sampling",
    )
    _require_config_value(
        sampling,
        "stratum_ideal_quota_rule",
        "stratum_eligible_count_times_selection_fraction",
        context="sampling",
    )
    _require_config_value(
        sampling,
        "initial_stratum_quota_rule",
        "floor_of_stratum_ideal_quota",
        context="sampling",
    )
    _require_config_value(
        sampling,
        "remainder_allocation",
        "descending_fractional_remainder_until_global_target_is_met",
        context="sampling",
    )
    _require_config_value(sampling, "remainder_tie_break", "lexicographic_stratum_id", context="sampling")
    _require_config_value(
        sampling,
        "within_stratum_rank",
        "sha256_of_seed_source_id_and_site_id",
        context="sampling",
    )
    _require_config_value(sampling, "sampling_without_replacement", True, context="sampling")

    zero_holdout_policy = _required_mapping(payload, "zero_holdout_policy", context="config")
    _require_config_value(
        zero_holdout_policy,
        "action",
        "fail_gate",
        context="zero_holdout_policy",
    )
    _require_config_value(
        zero_holdout_policy,
        "minimum_holdout_locations",
        1,
        context="zero_holdout_policy",
    )
    _require_config_value(
        zero_holdout_policy,
        "permit_empty_assignment_artifact",
        False,
        context="zero_holdout_policy",
    )

    assignment = _required_mapping(payload, "assignment", context="config")
    _require_config_value(assignment, "selected_role", ASSIGNMENT_HOLDOUT, context="assignment")
    _require_config_value(assignment, "nonselected_role", ASSIGNMENT_DEVELOPMENT, context="assignment")
    _require_config_value(assignment, "all_rows_of_group_share_assignment", True, context="assignment")
    _require_config_value(assignment, "replacement_for_missing_future_outcome", "forbidden", context="assignment")
    _require_config_value(assignment, "replacement_for_model_failure", "forbidden", context="assignment")
    _require_config_value(
        assignment,
        "expected_output_columns",
        ASSIGNMENT_OUTPUT_COLUMNS,
        context="assignment",
    )

    outputs = _required_mapping(payload, "outputs", context="config")
    expected_outputs = {
        "assignment": DEFAULT_ASSIGNMENT.as_posix(),
        "summary_pre_cutoff": DEFAULT_SUMMARY.as_posix(),
        "cohort_flow_preoutcome": DEFAULT_COHORT_FLOW.as_posix(),
        "leakage_audit": DEFAULT_LEAKAGE_AUDIT.as_posix(),
        "manifest": DEFAULT_MANIFEST.as_posix(),
    }
    _require_config_value(outputs, "expected_output_count", 5, context="outputs")
    for output_name, output_path in expected_outputs.items():
        _require_config_value(outputs, output_name, output_path, context="outputs")
    _require_config_value(
        outputs,
        "write_order",
        list(expected_outputs.values()),
        context="outputs",
    )
    _require_config_value(outputs, "manifest_written_last", True, context="outputs")
    _require_config_value(
        outputs,
        "output_contains_post_cutoff_outcome_values",
        False,
        context="outputs",
    )
    _require_config_value(
        outputs,
        "output_contains_post_cutoff_outcome_availability",
        False,
        context="outputs",
    )

    config = HoldoutConfig(
        source_id=str(eligibility["source_id_equals"]),
        information_cutoff=str(boundary["information_cutoff"]),
        latest_eligible_origin=str(eligibility["last_eligible_origin"]),
        history_length_months=int(eligibility["history_length_months"]),
        horizons_months=tuple(int(value) for value in eligibility["complete_horizons_required"]),
        bloom_threshold_ug_l=float(bloom["bloom_threshold_ug_l"]),
        holdout_fraction=float(sampling["selection_fraction"]),
        selection_seed=int(sampling["seed"]),
    )
    return config, payload


def load_and_validate_target_manifest(
    manifest_path: Path,
    *,
    targets_path: Path,
    config: HoldoutConfig,
) -> dict[str, Any]:
    """Bind the historical bloom labels to their frozen 30 ug/L target contract."""

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("target manifest must be a JSON object")
    if payload.get("status") != "completed":
        raise ValueError("target manifest status must be 'completed'")
    threshold = payload.get("bloom_threshold_chla_ugL")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("target manifest bloom_threshold_chla_ugL must be numeric")
    if not math.isfinite(float(threshold)) or float(threshold) != config.bloom_threshold_ug_l:
        raise ValueError(
            "target manifest bloom_threshold_chla_ugL does not match the locked holdout threshold"
        )
    model_long_targets = payload.get("model_long_targets")
    if not isinstance(model_long_targets, str) or not model_long_targets:
        raise ValueError("target manifest model_long_targets must be a non-empty path")

    manifest_target = Path(model_long_targets)
    manifest_target_resolved = (
        manifest_target.resolve()
        if manifest_target.is_absolute()
        else (PROJECT_ROOT / manifest_target).resolve()
    )
    configured_target_resolved = (
        targets_path.resolve()
        if targets_path.is_absolute()
        else (PROJECT_ROOT / targets_path).resolve()
    )
    if manifest_target_resolved != configured_target_resolved:
        raise ValueError(
            "target manifest model_long_targets does not match inputs.monthly_targets"
        )
    return payload


def _contains_chlorophyll_name(column: str) -> bool:
    normalized = column.lower().replace("-", "_")
    known_aliases = {
        "chl",
        "chl_prev",
        "irc1",
        "irc1_adaptive",
        "x_irc1",
        "x_irc1_adaptive",
    }
    return (
        "chlorophyll" in normalized
        or "chla" in normalized
        or "chl_a" in normalized
        or normalized in known_aliases
    )


def _validate_required_columns(frame: pd.DataFrame, required: list[str], *, label: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _normalize_months(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    out = frame.copy()
    if out[KEY_COLUMNS].isna().any().any():
        raise ValueError(f"{label} contains null source/site/month keys")
    month_values = out["year_month"].astype(str)
    if not month_values.str.fullmatch(r"\d{4}-\d{2}").all():
        raise ValueError(f"{label} contains non-canonical year_month values")
    try:
        periods = pd.PeriodIndex(month_values, freq="M")
    except ValueError as exc:
        raise ValueError(f"{label} contains invalid year_month values") from exc
    if not (periods.astype(str) == month_values.to_numpy()).all():
        raise ValueError(f"{label} contains non-canonical year_month values")
    out["year_month"] = periods.astype(str)
    out["source_id"] = out["source_id"].astype(str)
    out["site_id"] = out["site_id"].astype(str)
    return out


def _normalize_named_month(frame: pd.DataFrame, column: str, *, label: str) -> pd.DataFrame:
    out = frame.copy()
    values = out[column].astype(str)
    if out[column].isna().any() or not values.str.fullmatch(r"\d{4}-\d{2}").all():
        raise ValueError(f"{label} contains non-canonical {column} values")
    try:
        periods = pd.PeriodIndex(values, freq="M")
    except ValueError as exc:
        raise ValueError(f"{label} contains invalid {column} values") from exc
    if not (periods.astype(str) == values.to_numpy()).all():
        raise ValueError(f"{label} contains non-canonical {column} values")
    out[column] = periods.astype(str)
    return out


def build_precursor_month_status(
    precursor_rows: pd.DataFrame,
    config: HoldoutConfig = HoldoutConfig(),
) -> pd.DataFrame:
    """Return cutoff-safe monthly precursor availability with no Chl-a fields.

    A month is input-eligible only when it has a nutrient (TP or TN), water
    temperature, and either a light proxy (Secchi/turbidity) or a
    physicochemical proxy (DO/pH). Duplicate canonical panel keys are rejected.
    """

    chlorophyll_columns = sorted(column for column in precursor_rows.columns if _contains_chlorophyll_name(column))
    if chlorophyll_columns:
        raise ValueError(
            "Precursor rows must not contain chlorophyll-a columns; pass historical outcomes separately: "
            f"{chlorophyll_columns}"
        )
    _validate_required_columns(precursor_rows, PRECURSOR_READ_COLUMNS, label="precursor_rows")
    frame = _normalize_months(precursor_rows[PRECURSOR_READ_COLUMNS], label="precursor_rows")
    cutoff = _period(config.information_cutoff, field_name="information_cutoff")
    periods = pd.PeriodIndex(frame["year_month"], freq="M")
    frame = frame.loc[(frame["source_id"] == config.source_id) & (periods <= cutoff)].copy()

    if frame.duplicated(KEY_COLUMNS).any():
        duplicates = frame.loc[frame.duplicated(KEY_COLUMNS, keep=False), KEY_COLUMNS]
        sample = duplicates.drop_duplicates().head(5).to_dict(orient="records")
        raise ValueError(f"precursor_rows contains duplicate source/site/month keys: {sample}")

    for column in PRECURSOR_VALUE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)

    status = frame[KEY_COLUMNS].copy()
    status["nutrient_available"] = frame[NUTRIENT_COLUMNS].notna().any(axis=1)
    status["temperature_available"] = frame[TEMPERATURE_COLUMNS].notna().any(axis=1)
    status["light_available"] = frame[LIGHT_PROXY_COLUMNS].notna().any(axis=1)
    status["physicochemical_available"] = frame[PHYSICOCHEMICAL_COLUMNS].notna().any(axis=1)
    status["context_available"] = status["light_available"] | status["physicochemical_available"]
    status["input_eligible"] = (
        status["nutrient_available"] & status["temperature_available"] & status["context_available"]
    )
    domain_count = (
        status["nutrient_available"].astype("int8")
        + status["temperature_available"].astype("int8")
        + status["context_available"].astype("int8")
    )
    status["precursor_domain_fraction"] = domain_count.astype("float64") / 3.0
    return status.sort_values(KEY_COLUMNS).reset_index(drop=True)


def build_historical_outcome_index(
    historical_outcomes: pd.DataFrame,
    config: HoldoutConfig = HoldoutConfig(),
) -> pd.DataFrame:
    """Normalize historical bloom labels without retaining post-cutoff targets."""

    _validate_required_columns(
        historical_outcomes,
        HISTORICAL_OUTCOME_READ_COLUMNS,
        label="historical_outcomes",
    )
    frame = historical_outcomes[HISTORICAL_OUTCOME_READ_COLUMNS].copy()
    if frame[["source_id", "site_id"]].isna().any().any():
        raise ValueError("historical_outcomes contains null source/site keys")
    frame["source_id"] = frame["source_id"].astype(str)
    frame["site_id"] = frame["site_id"].astype(str)
    frame = _normalize_named_month(frame, "origin_year_month", label="historical_outcomes")
    frame = _normalize_named_month(frame, "target_year_month", label="historical_outcomes")
    cutoff = _period(config.information_cutoff, field_name="information_cutoff")
    target_periods = pd.PeriodIndex(frame["target_year_month"], freq="M")
    frame = frame.loc[(frame["source_id"] == config.source_id) & (target_periods <= cutoff)].copy()
    horizons = pd.to_numeric(frame["horizon_months"], errors="coerce")
    if horizons.isna().any() or not horizons.isin(config.horizons_months).all():
        raise ValueError("historical_outcomes contains invalid horizon_months values")
    frame["horizon_months"] = horizons.astype("int8")
    bloom_values = frame[HISTORICAL_OUTCOME_COLUMN]
    if bloom_values.isna().any() or not bloom_values.isin([True, False, 0, 1]).all():
        raise ValueError("historical_outcomes.bloom_h must contain only non-null boolean labels")
    frame[HISTORICAL_OUTCOME_COLUMN] = bloom_values.astype(bool)

    origin_periods = pd.PeriodIndex(frame["origin_year_month"], freq="M")
    expected_targets = origin_periods + frame["horizon_months"].astype("int64").to_numpy()
    if not (expected_targets.astype(str) == frame["target_year_month"].to_numpy()).all():
        raise ValueError("historical_outcomes contains origin/horizon/target month inconsistencies")

    outcome_key = ["source_id", "site_id", "origin_year_month", "horizon_months"]
    duplicated = frame.duplicated(outcome_key, keep=False)
    if duplicated.any():
        duplicate_groups = frame.loc[duplicated].groupby(outcome_key, sort=True, dropna=False)
        target_conflicts = duplicate_groups["target_year_month"].nunique(dropna=False)
        bloom_conflicts = duplicate_groups[HISTORICAL_OUTCOME_COLUMN].nunique(dropna=False)
        conflicts = pd.concat([target_conflicts, bloom_conflicts], axis=1).max(axis=1)
        if (conflicts > 1).any():
            conflict_keys = conflicts[conflicts > 1].head(5).index.tolist()
            raise ValueError(f"historical_outcomes contains conflicting duplicate keys: {conflict_keys}")
        frame = frame.drop_duplicates(outcome_key, keep="first")

    return frame.sort_values(outcome_key).reset_index(drop=True)


def build_eligible_origins(
    precursor_status: pd.DataFrame,
    historical_outcome_index: pd.DataFrame,
    config: HoldoutConfig = HoldoutConfig(),
) -> pd.DataFrame:
    """Find origins with 12 consecutive eligible inputs and complete h1--h3.

    Returned rows contain target month identifiers, never target values.
    """

    status_columns = KEY_COLUMNS + ["input_eligible"]
    _validate_required_columns(precursor_status, status_columns, label="precursor_status")
    _validate_required_columns(
        historical_outcome_index,
        HISTORICAL_OUTCOME_READ_COLUMNS,
        label="historical_outcome_index",
    )
    latest_origin = _period(config.latest_eligible_origin, field_name="latest_eligible_origin")
    cutoff = _period(config.information_cutoff, field_name="information_cutoff")

    outcomes_by_location: dict[tuple[str, str], dict[tuple[str, int], tuple[str, bool]]] = {}
    for group_key, group in historical_outcome_index.groupby(["source_id", "site_id"], sort=True):
        source_id, site_id = (str(value) for value in _group_key_tuple(group_key))
        outcomes_by_location[(source_id, site_id)] = {
            (str(row.origin_year_month), int(row.horizon_months)): (
                str(row.target_year_month),
                bool(row.bloom_h),
            )
            for row in _dataframe_rows(group)
        }

    records: list[dict[str, Any]] = []
    for group_key, group in precursor_status.groupby(["source_id", "site_id"], sort=True):
        source_id, site_id = (str(value) for value in _group_key_tuple(group_key))
        outcome_lookup = outcomes_by_location.get((source_id, site_id), {})
        eligible_months = {
            cast(pd.Period, pd.Period(str(row.year_month), freq="M"))
            for row in _dataframe_rows(group)
            if bool(row.input_eligible)
        }
        for origin in sorted(eligible_months):
            if origin > latest_origin:
                continue
            history = [origin - offset for offset in range(config.history_length_months - 1, -1, -1)]
            if any(month not in eligible_months for month in history):
                continue
            target_months = [origin + horizon for horizon in config.horizons_months]
            if target_months[-1] > cutoff:
                continue
            outcome_keys = [(str(origin), horizon) for horizon in config.horizons_months]
            if any(key not in outcome_lookup for key in outcome_keys):
                continue
            if any(outcome_lookup[key][0] != str(month) for key, month in zip(outcome_keys, target_months, strict=True)):
                raise ValueError("historical outcome lookup does not match the required target month")
            record: dict[str, Any] = {
                "source_id": source_id,
                "site_id": site_id,
                "holdout_group_id": f"{source_id}::{site_id}",
                "origin_year_month": str(origin),
                "history_start_year_month": str(history[0]),
                "history_end_year_month": str(history[-1]),
                "history_length_months": config.history_length_months,
                "complete_horizons": True,
            }
            for horizon, target_month in zip(config.horizons_months, target_months, strict=True):
                record[f"target_year_month_h{horizon}"] = str(target_month)
            records.append(record)

    target_columns = [f"target_year_month_h{horizon}" for horizon in config.horizons_months]
    columns = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "origin_year_month",
        "history_start_year_month",
        "history_end_year_month",
        "history_length_months",
        "complete_horizons",
        *target_columns,
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records, columns=columns).sort_values(
        ["source_id", "site_id", "origin_year_month"]
    ).reset_index(drop=True)


def coverage_band(value: float) -> str:
    """Map precursor coverage to the locked third-based bands."""

    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"coverage must be finite and within [0, 1]; received {value!r}")
    if value < 1.0 / 3.0:
        return "low"
    if value < 2.0 / 3.0:
        return "medium"
    return "high"


def series_length_band(months: int) -> str:
    """Map observed pre-cutoff months to the locked length bands."""

    if months < 12:
        raise ValueError("eligible closure locations must contain at least 12 months")
    if months <= 23:
        return "short"
    if months <= 59:
        return "medium"
    return "long"


def build_location_profiles(
    precursor_status: pd.DataFrame,
    historical_outcome_index: pd.DataFrame,
    eligible_origins: pd.DataFrame,
    config: HoldoutConfig = HoldoutConfig(),
) -> pd.DataFrame:
    """Summarize cutoff-safe strata for locations with at least one origin."""

    if eligible_origins.empty:
        return pd.DataFrame(columns=LOCATION_PROFILE_COLUMNS)

    outcomes_by_location: dict[tuple[str, str], dict[str, bool]] = {}
    for group_key, group in historical_outcome_index.groupby(["source_id", "site_id"], sort=True):
        source_id, site_id = (str(value) for value in _group_key_tuple(group_key))
        target_lookup: dict[str, bool] = {}
        for row in _dataframe_rows(group):
            target_month = str(row.target_year_month)
            bloom = bool(row.bloom_h)
            if target_month in target_lookup and target_lookup[target_month] != bloom:
                raise ValueError(
                    "historical_outcomes contains inconsistent bloom labels for a deduplicated target month"
                )
            target_lookup[target_month] = bloom
        outcomes_by_location[(source_id, site_id)] = target_lookup

    records: list[dict[str, Any]] = []
    eligible_keys = eligible_origins[["source_id", "site_id"]].drop_duplicates()
    status = precursor_status.merge(eligible_keys, on=["source_id", "site_id"], how="inner", validate="many_to_one")
    for group_key, group in status.groupby(["source_id", "site_id"], sort=True):
        source_id, site_id = (str(value) for value in _group_key_tuple(group_key))
        site_origins = eligible_origins.loc[
            (eligible_origins["source_id"] == source_id) & (eligible_origins["site_id"] == site_id)
        ].copy()
        outcome_lookup = outcomes_by_location[(source_id, site_id)]
        target_months = sorted(outcome_lookup)
        target_values = [outcome_lookup[month] for month in target_months]
        bloom_events = sum(target_values)
        month_count = len(group)
        precursor_coverage = float(group["input_eligible"].mean())
        bloom_present = bloom_events > 0
        coverage_label = coverage_band(precursor_coverage)
        length_label = series_length_band(month_count)
        records.append(
            {
                "source_id": source_id,
                "site_id": site_id,
                "holdout_group_id": f"{source_id}::{site_id}",
                "first_year_month": str(group["year_month"].min()),
                "last_year_month": str(group["year_month"].max()),
                "series_length_months": month_count,
                "input_eligible_months": int(group["input_eligible"].sum()),
                "nutrient_coverage_fraction": float(group["nutrient_available"].mean()),
                "temperature_coverage_fraction": float(group["temperature_available"].mean()),
                "light_coverage_fraction": float(group["light_available"].mean()),
                "physicochemical_coverage_fraction": float(group["physicochemical_available"].mean()),
                "context_coverage_fraction": float(group["context_available"].mean()),
                "precursor_coverage_fraction": precursor_coverage,
                "precursor_coverage_band": coverage_label,
                "series_length_band": length_label,
                "eligible_origin_count": len(site_origins),
                "first_eligible_origin": str(site_origins["origin_year_month"].min()),
                "last_eligible_origin": str(site_origins["origin_year_month"].max()),
                "first_historical_target_month": target_months[0],
                "last_historical_target_month": target_months[-1],
                "historical_target_months": len(target_months),
                "historical_bloom_events": bloom_events,
                "historical_bloom_prevalence": bloom_events / len(target_months),
                "historical_bloom_presence": bloom_present,
                "stratum_id": (
                    f"bloom={int(bloom_present)}|coverage={coverage_label}|length={length_label}"
                ),
            }
        )

    return pd.DataFrame.from_records(records, columns=LOCATION_PROFILE_COLUMNS).sort_values(
        ["source_id", "site_id"]
    ).reset_index(drop=True)


def allocate_stratum_quotas(location_profiles: pd.DataFrame, holdout_fraction: float = 0.20) -> pd.DataFrame:
    """Allocate the floor total from stratum-fraction quotas and largest remainder."""

    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be strictly between zero and one")
    _validate_required_columns(location_profiles, ["stratum_id"], label="location_profiles")
    total_locations = len(location_profiles)
    holdout_total = math.floor(total_locations * holdout_fraction)
    if holdout_total == 0:
        raise ValueError(
            "zero_holdout_policy=fail_gate: floor(eligible_locations * holdout_fraction) is zero"
        )
    counts = location_profiles.groupby("stratum_id", sort=True, dropna=False).size().reset_index()
    counts.columns = ["stratum_id", "eligible_locations"]
    counts["exact_quota"] = counts["eligible_locations"] * holdout_fraction
    counts["base_quota"] = np.floor(counts["exact_quota"]).astype("int64")
    counts["quota_remainder"] = counts["exact_quota"] - counts["base_quota"]
    counts["holdout_quota"] = counts["base_quota"].copy()

    remaining = holdout_total - int(counts["base_quota"].sum())
    if remaining:
        remainder_order = counts.sort_values(
            ["quota_remainder", "stratum_id"], ascending=[False, True], kind="stable"
        ).index[:remaining]
        counts.loc[remainder_order, "holdout_quota"] += 1

    if int(counts["holdout_quota"].sum()) != holdout_total:
        raise RuntimeError("largest-remainder allocation did not preserve the locked holdout total")
    if (counts["holdout_quota"] > counts["eligible_locations"]).any():
        raise RuntimeError("largest-remainder allocation attempted sampling with replacement")
    return counts.sort_values("stratum_id").reset_index(drop=True)


def _selection_hash(seed: int, source_id: str, site_id: str) -> str:
    payload = f"{seed}\x1f{source_id}\x1f{site_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assign_holdout_locations(
    location_profiles: pd.DataFrame,
    *,
    holdout_fraction: float = 0.20,
    selection_seed: int = 20260802,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign complete monitoring-location groups without replacement."""

    generated_columns = {"assignment_role", "deterministic_rank_sha256"}
    required = [
        column for column in ASSIGNMENT_OUTPUT_COLUMNS if column not in generated_columns
    ]
    _validate_required_columns(location_profiles, required, label="location_profiles")
    if location_profiles.duplicated(["source_id", "site_id"]).any():
        raise ValueError("location_profiles must contain one row per source_id + site_id")

    quotas = allocate_stratum_quotas(location_profiles, holdout_fraction)
    if location_profiles.empty:
        empty = location_profiles.copy()
        for column in [
            "deterministic_rank_sha256",
            "rank_within_stratum",
            "stratum_quota",
            "assignment_role",
        ]:
            empty[column] = pd.Series(dtype="object")
        quotas["selected_locations"] = pd.Series(dtype="int64")
        return empty, quotas

    assignment = location_profiles.merge(
        quotas[["stratum_id", "holdout_quota"]],
        on="stratum_id",
        how="left",
        validate="many_to_one",
    )
    assignment["deterministic_rank_sha256"] = [
        _selection_hash(selection_seed, str(source_id), str(site_id))
        for source_id, site_id in zip(assignment["source_id"], assignment["site_id"], strict=True)
    ]
    assignment = assignment.sort_values(
        ["stratum_id", "deterministic_rank_sha256", "source_id", "site_id"], kind="stable"
    ).reset_index(drop=True)
    assignment["rank_within_stratum"] = assignment.groupby("stratum_id", sort=False).cumcount() + 1
    assignment["stratum_quota"] = assignment["holdout_quota"].astype("int64")
    assignment["assignment_role"] = np.where(
        assignment["rank_within_stratum"] <= assignment["stratum_quota"],
        ASSIGNMENT_HOLDOUT,
        ASSIGNMENT_DEVELOPMENT,
    )
    assignment = assignment.drop(columns=["holdout_quota"]).sort_values(
        ["source_id", "site_id"]
    ).reset_index(drop=True)

    selected = (
        assignment.assign(_selected=assignment["assignment_role"].eq(ASSIGNMENT_HOLDOUT).astype("int64"))
        .groupby("stratum_id", sort=True)["_selected"]
        .sum()
        .rename("selected_locations")
        .reset_index()
    )
    quotas = quotas.merge(selected, on="stratum_id", how="left", validate="one_to_one")
    quotas["selected_locations"] = quotas["selected_locations"].fillna(0).astype("int64")
    if not (quotas["selected_locations"] == quotas["holdout_quota"]).all():
        raise RuntimeError("deterministic ranks did not satisfy the allocated stratum quotas")
    assignment = assignment.loc[:, ASSIGNMENT_OUTPUT_COLUMNS]
    return assignment, quotas


def build_holdout_selection(
    precursor_rows: pd.DataFrame,
    historical_outcomes: pd.DataFrame,
    config: HoldoutConfig = HoldoutConfig(),
) -> HoldoutSelection:
    """Build eligibility, profiles, quotas, and assignment entirely in memory."""

    precursor_status = build_precursor_month_status(precursor_rows, config)
    outcome_index = build_historical_outcome_index(historical_outcomes, config)
    eligible_origins = build_eligible_origins(precursor_status, outcome_index, config)
    profiles = build_location_profiles(precursor_status, outcome_index, eligible_origins, config)
    if profiles.empty:
        raise ValueError("No WQP monitoring locations satisfy the locked pre-cutoff eligibility rules")
    assignment, quotas = assign_holdout_locations(
        profiles,
        holdout_fraction=config.holdout_fraction,
        selection_seed=config.selection_seed,
    )
    return HoldoutSelection(
        eligible_origins=eligible_origins,
        location_profiles=profiles,
        assignment=assignment,
        quota_summary=quotas,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def validate_protocol_lock(
    lock_path: Path,
    script_path: Path = Path(__file__),
    *,
    current_head: str | None = None,
) -> dict[str, Any]:
    """Validate the closure protocol lock and this selector's locked hash."""

    if not lock_path.is_file():
        raise FileNotFoundError(f"Protocol lock does not exist: {lock_path}")
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Protocol lock must be a JSON object")
    expected_scalars = {
        "lock_version": "closure_protocol_lock_v1",
        "status": "locked",
        "experiment_id": "closure_v1",
        "plan_version": "1.1",
    }
    for field, expected in expected_scalars.items():
        if payload.get(field) != expected:
            raise ValueError(f"Protocol lock field {field!r} must equal {expected!r}")
    if payload.get("future_outcomes_accessed") is not False:
        raise ValueError("Protocol lock must attest future_outcomes_accessed=false")
    if payload.get("outcome_access_definition") != (
        "semantic_decoding_inspection_aggregation_or_use_of_outcome_rows"
    ):
        raise ValueError("Protocol lock contains an unexpected outcome_access_definition")
    if payload.get("lock_command_reads_complete_source_bytes_for_sha256") is not True:
        raise ValueError("Protocol lock must disclose complete source-byte hashing")
    if payload.get("lock_command_semantically_decodes_post_2021_outcomes") is not False:
        raise ValueError("Protocol lock must attest no semantic decoding of post-2021 outcomes")
    if payload.get("holdout_assignment_created") is not False:
        raise ValueError("Protocol lock must attest holdout_assignment_created=false")

    locked_repository = payload.get("locked_repository")
    if not isinstance(locked_repository, dict):
        raise ValueError("Protocol lock is missing locked_repository")
    if locked_repository.get("worktree_status") != "clean":
        raise ValueError("Protocol lock must record locked_repository.worktree_status='clean'")
    locked_head = locked_repository.get("head")
    if not isinstance(locked_head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", locked_head):
        raise ValueError("Protocol lock contains an invalid locked_repository.head")
    components = payload.get("protocol_components")
    if not isinstance(components, list):
        raise ValueError("Protocol lock is missing protocol_components")
    script_record_path = _manifest_path(script_path)
    normalized_records: list[dict[str, Any]] = []
    for index, record in enumerate(components):
        if not isinstance(record, dict):
            raise ValueError(f"protocol_components[{index}] must be an object")
        typed_record = cast(dict[str, Any], record)
        component_path = typed_record.get("path")
        expected_hash = typed_record.get("sha256")
        expected_bytes = typed_record.get("bytes")
        role = typed_record.get("role")
        if not isinstance(component_path, str) or not component_path:
            raise ValueError(f"protocol_components[{index}].path must be a non-empty string")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError(f"protocol_components[{index}].sha256 must be a SHA-256 digest")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise ValueError(f"protocol_components[{index}].bytes must be a non-negative integer")
        if not isinstance(role, str) or not role:
            raise ValueError(f"protocol_components[{index}].role must be a non-empty string")
        candidate = Path(component_path)
        if candidate.is_absolute():
            raise ValueError(f"Protocol component path must be repository-relative: {component_path}")
        resolved = (PROJECT_ROOT / candidate).resolve()
        try:
            resolved.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError(f"Protocol component escapes the repository: {component_path}") from exc
        if not resolved.is_file():
            raise ValueError(f"Locked protocol component is missing: {component_path}")
        if resolved.stat().st_size != expected_bytes:
            raise ValueError(f"Protocol lock byte-size mismatch for {component_path}")
        if _sha256_file(resolved) != expected_hash:
            raise ValueError(f"Protocol lock hash mismatch for {component_path}")
        normalized_records.append(typed_record)

    matching = [record for record in normalized_records if record.get("path") == script_record_path]
    if len(matching) != 1:
        raise ValueError(f"Protocol lock must contain exactly one component for {script_record_path}")
    if current_head is not None:
        ancestor_check = subprocess.run(
            ["git", "merge-base", "--is-ancestor", locked_head, current_head],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestor_check.returncode != 0:
            raise ValueError(f"Locked HEAD {locked_head} is not an ancestor of current HEAD {current_head}")
    return payload


def require_tracked_clean_protocol_lock(lock_path: Path) -> None:
    """Require the real-execution lock file to be tracked and unmodified."""

    relative = _manifest_path(lock_path)
    if Path(relative).is_absolute():
        raise ValueError("Real selection requires a protocol lock inside the repository")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise ValueError(f"Real selection requires a Git-tracked protocol lock: {relative}")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise ValueError(f"Real selection requires an unmodified protocol lock: {status}")


def require_clean_worktree() -> None:
    """Prevent a real assignment from depending on any uncommitted file."""

    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise ValueError("Real selection requires a fully clean worktree")


def require_locked_component(protocol_lock: dict[str, Any], path: Path) -> None:
    """Require a path to be one of the already verified protocol components."""

    records = protocol_lock.get("protocol_components")
    if not isinstance(records, list):
        raise ValueError("Protocol lock is missing protocol_components")
    relative = _manifest_path(path)
    matching = [record for record in records if isinstance(record, dict) and record.get("path") == relative]
    if len(matching) != 1:
        raise ValueError(f"Protocol lock must contain exactly one component for {relative}")


def _locked_source_record(protocol_lock: dict[str, Any], path: Path) -> dict[str, Any]:
    records = protocol_lock.get("source_artifacts")
    if not isinstance(records, list):
        raise ValueError("Protocol lock is missing source_artifacts")
    relative = _manifest_path(path)
    matching = [record for record in records if isinstance(record, dict) and record.get("path") == relative]
    if len(matching) != 1:
        raise ValueError(f"Protocol lock must contain exactly one source artifact for {relative}")
    record = matching[0]
    if not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
        raise ValueError(f"Locked source artifact has an invalid SHA-256: {relative}")
    if record.get("bytes") != path.stat().st_size:
        raise ValueError(f"Locked source artifact byte-size mismatch: {relative}")
    actual_hash = _sha256_file(path)
    if record["sha256"] != actual_hash:
        raise ValueError(f"Locked source artifact SHA-256 mismatch: {relative}")
    return {
        "path": relative,
        "role": record.get("role"),
        "bytes": record["bytes"],
        "sha256": record["sha256"],
        "hash_source": "protocol_lock",
    }


def read_pre_cutoff_panel_projections(
    panel_path: Path,
    targets_path: Path,
    config: HoldoutConfig = HoldoutConfig(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read only locked columns and rows through the information cutoff."""

    filters = [
        ("source_id", "==", config.source_id),
        ("year_month", "<=", config.information_cutoff),
    ]
    precursor_rows = pd.read_parquet(panel_path, columns=PRECURSOR_READ_COLUMNS, filters=filters)
    target_filters = [
        ("source_id", "==", config.source_id),
        ("target_year_month", "<=", config.information_cutoff),
    ]
    historical_outcomes = pd.read_parquet(
        targets_path,
        columns=HISTORICAL_OUTCOME_READ_COLUMNS,
        filters=target_filters,
    )
    return precursor_rows, historical_outcomes


def _read_and_revalidate_locked_projections(
    protocol_lock: dict[str, Any],
    panel_path: Path,
    targets_path: Path,
    config: HoldoutConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Read cutoff-safe projections between two full locked-source validations."""

    initial_records = [
        _locked_source_record(protocol_lock, panel_path),
        _locked_source_record(protocol_lock, targets_path),
    ]
    precursor_rows, historical_outcomes = read_pre_cutoff_panel_projections(
        panel_path,
        targets_path,
        config,
    )
    final_records = [
        _locked_source_record(protocol_lock, panel_path),
        _locked_source_record(protocol_lock, targets_path),
    ]
    if final_records != initial_records:
        raise RuntimeError("Locked panel or targets changed while the cutoff-safe projections were read")
    return precursor_rows, historical_outcomes, initial_records


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        frame.to_csv(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _output_record(path: Path) -> dict[str, Any]:
    return {"path": _manifest_path(path), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _configured_path(
    payload: dict[str, Any],
    section_name: str,
    key: str,
    override: Path | None,
) -> Path:
    section = _required_mapping(payload, section_name, context="config")
    configured_value = section.get(key)
    if not isinstance(configured_value, str) or not configured_value:
        raise ValueError(f"config.{section_name}.{key} must be a non-empty path")
    configured = Path(configured_value)
    if override is not None and override.resolve() != configured.resolve():
        raise ValueError(
            f"--{key.replace('_', '-')} cannot override the locked config path "
            f"{configured.as_posix()} with {override.as_posix()}"
        )
    return configured


def _assert_outputs_absent(paths: list[Path]) -> None:
    existing = [path.as_posix() for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "Locked holdout outputs are immutable and will not be replaced; existing paths: "
            f"{existing}"
        )


def build_cohort_flow_preoutcome(selection: HoldoutSelection) -> pd.DataFrame:
    """Summarize assigned locations and eligible historical origins without future outcomes."""

    origins_with_role = selection.eligible_origins.merge(
        selection.assignment[["source_id", "site_id", "assignment_role"]],
        on=["source_id", "site_id"],
        how="left",
        validate="many_to_one",
    )
    rows = [
        {
            "stage": "eligible_before_assignment",
            "assignment_role": "all",
            "monitoring_locations": len(selection.assignment),
            "eligible_historical_origins": len(selection.eligible_origins),
        }
    ]
    for role in (ASSIGNMENT_DEVELOPMENT, ASSIGNMENT_HOLDOUT):
        rows.append(
            {
                "stage": "deterministic_assignment",
                "assignment_role": role,
                "monitoring_locations": int(selection.assignment["assignment_role"].eq(role).sum()),
                "eligible_historical_origins": int(origins_with_role["assignment_role"].eq(role).sum()),
            }
        )
    return pd.DataFrame(rows)


def build_holdout_leakage_audit(
    selection: HoldoutSelection,
    config: HoldoutConfig,
) -> dict[str, Any]:
    """Build and enforce the pre-outcome cutoff and group-integrity checks."""

    target_columns = [f"target_year_month_h{horizon}" for horizon in config.horizons_months]
    target_max = max(str(selection.eligible_origins[column].max()) for column in target_columns)
    selected_count = int(selection.assignment["assignment_role"].eq(ASSIGNMENT_HOLDOUT).sum())
    expected_count = math.floor(len(selection.assignment) * config.holdout_fraction)
    checks = {
        "precursor_months_not_after_cutoff": bool(
            selection.location_profiles["last_year_month"].le(config.information_cutoff).all()
        ),
        "historical_target_months_not_after_cutoff": bool(
            selection.location_profiles["last_historical_target_month"]
            .le(config.information_cutoff)
            .all()
        ),
        "eligibility_targets_not_after_cutoff": target_max <= config.information_cutoff,
        "eligible_origins_not_after_locked_last_origin": bool(
            selection.eligible_origins["origin_year_month"]
            .le(config.latest_eligible_origin)
            .all()
        ),
        "precursor_projection_has_no_chla_or_derived_alias": not any(
            _contains_chlorophyll_name(column) for column in PRECURSOR_READ_COLUMNS
        ),
        "one_assignment_per_source_site": not selection.assignment.duplicated(
            ["source_id", "site_id"]
        ).any(),
        "assignment_roles_are_locked": set(selection.assignment["assignment_role"].astype(str)).issubset(
            {ASSIGNMENT_DEVELOPMENT, ASSIGNMENT_HOLDOUT}
        ),
        "selected_count_matches_floor_target": selected_count == expected_count,
        "nonzero_internal_holdout": selected_count > 0,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"Pre-outcome holdout leakage audit failed: {failed}")
    return {
        "audit_version": "closure_holdout_leakage_audit_v1",
        "status": "passed",
        "experiment_id": "closure_v1",
        "future_outcomes_accessed": False,
        "information_cutoff": config.information_cutoff,
        "latest_eligible_origin": config.latest_eligible_origin,
        "historical_bloom_scope": "all_unique_wqp_target_months_not_after_cutoff",
        "maximum_eligible_target_month": target_max,
        "eligible_locations": len(selection.assignment),
        "selected_internal_holdout_locations": selected_count,
        "expected_internal_holdout_locations": expected_count,
        "checks": checks,
    }


def _write_locked_outputs(
    selection: HoldoutSelection,
    *,
    assignment_path: Path,
    summary_path: Path,
    cohort_flow_path: Path,
    leakage_audit_path: Path,
    manifest_path: Path,
    config_path: Path,
    source_records: list[dict[str, Any]],
    protocol_lock_path: Path,
    protocol_lock: dict[str, Any],
    config: HoldoutConfig,
) -> None:
    output_paths = [assignment_path, summary_path, cohort_flow_path, leakage_audit_path, manifest_path]
    _assert_outputs_absent(output_paths)
    if selection.assignment.columns.tolist() != ASSIGNMENT_OUTPUT_COLUMNS:
        raise ValueError(
            "assignment columns must exactly match the locked output schema and order: "
            f"{ASSIGNMENT_OUTPUT_COLUMNS}"
        )
    cohort_flow = build_cohort_flow_preoutcome(selection)
    leakage_audit = build_holdout_leakage_audit(selection, config)

    manifest = {
        "manifest_version": "closure_holdout_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "future_outcomes_accessed": False,
        "unit_type": "wqp_monitoring_location",
        "group_key": ["source_id", "site_id"],
        "waterbody_claim_authorized": False,
        "holdout_config": {
            "path": _manifest_path(config_path),
            "bytes": config_path.stat().st_size,
            "sha256": _sha256_file(config_path),
        },
        "source_inputs": source_records,
        "columns_projected": {
            "precursors": PRECURSOR_READ_COLUMNS,
            "historical_outcomes": HISTORICAL_OUTCOME_READ_COLUMNS,
        },
        "selection": {
            "source_id": config.source_id,
            "information_cutoff": config.information_cutoff,
            "latest_eligible_origin": config.latest_eligible_origin,
            "history_length_months": config.history_length_months,
            "horizons_months": list(config.horizons_months),
            "bloom_threshold_ug_l": config.bloom_threshold_ug_l,
            "holdout_fraction": config.holdout_fraction,
            "selection_seed": config.selection_seed,
            "allocation": "floor_total_then_stratum_fraction_largest_remainder",
            "ranking": "sha256",
            "sampling_with_replacement": False,
        },
        "counts": {
            "eligible_origins": len(selection.eligible_origins),
            "eligible_locations": len(selection.assignment),
            "holdout_locations": int(
                selection.assignment["assignment_role"].eq(ASSIGNMENT_HOLDOUT).sum()
            ),
            "development_locations": int(
                selection.assignment["assignment_role"].eq(ASSIGNMENT_DEVELOPMENT).sum()
            ),
        },
        "protocol_lock": {
            "path": _manifest_path(protocol_lock_path),
            "sha256": _sha256_file(protocol_lock_path),
            "locked_repository_head": protocol_lock["locked_repository"]["head"],
        },
    }
    try:
        _write_csv_atomic(selection.assignment, assignment_path)
        _write_csv_atomic(selection.quota_summary, summary_path)
        _write_csv_atomic(cohort_flow, cohort_flow_path)
        _write_json_atomic(leakage_audit, leakage_audit_path)
        manifest["outputs"] = [
            _output_record(assignment_path),
            _output_record(summary_path),
            _output_record(cohort_flow_path),
            _output_record(leakage_audit_path),
        ]
        # The manifest is the completion marker and must always be written last.
        _write_json_atomic(manifest, manifest_path)
    except BaseException:
        for path in output_paths:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".tmp").unlink(missing_ok=True)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--panel", type=Path)
    parser.add_argument("--targets", type=Path)
    parser.add_argument("--target-manifest", type=Path)
    parser.add_argument("--protocol-lock", type=Path, default=DEFAULT_PROTOCOL_LOCK)
    parser.add_argument("--assignment", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--cohort-flow-preoutcome", type=Path)
    parser.add_argument("--leakage-audit", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the protocol lock and print the fixed projection without reading data or writing outputs.",
    )
    parser.add_argument(
        "--execute-locked-selection",
        action="store_true",
        help="Explicitly authorize the one-time locked pre-cutoff assignment build.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    config, config_payload = load_holdout_config(args.config)
    panel_path = _configured_path(config_payload, "inputs", "monthly_panel", args.panel)
    targets_path = _configured_path(config_payload, "inputs", "monthly_targets", args.targets)
    target_manifest_path = _configured_path(
        config_payload,
        "inputs",
        "target_manifest",
        args.target_manifest,
    )
    assignment_path = _configured_path(config_payload, "outputs", "assignment", args.assignment)
    summary_path = _configured_path(config_payload, "outputs", "summary_pre_cutoff", args.summary)
    cohort_flow_path = _configured_path(
        config_payload,
        "outputs",
        "cohort_flow_preoutcome",
        args.cohort_flow_preoutcome,
    )
    leakage_audit_path = _configured_path(
        config_payload,
        "outputs",
        "leakage_audit",
        args.leakage_audit,
    )
    manifest_path = _configured_path(config_payload, "outputs", "manifest", args.manifest)
    protocol_lock = validate_protocol_lock(
        args.protocol_lock,
        Path(__file__),
        current_head=_git_head(),
    )
    require_locked_component(protocol_lock, args.config)
    target_manifest_record = _locked_source_record(protocol_lock, target_manifest_path)
    load_and_validate_target_manifest(
        target_manifest_path,
        targets_path=targets_path,
        config=config,
    )
    if args.dry_run:
        print("protocol lock: valid", flush=True)
        print(f"locked HEAD: {protocol_lock['locked_repository']['head']}", flush=True)
        print(f"precursor projection: {PRECURSOR_READ_COLUMNS}", flush=True)
        print(f"historical outcome projection: {HISTORICAL_OUTCOME_READ_COLUMNS}", flush=True)
        print("dry run complete; panel was not read and no outputs were written", flush=True)
        return
    if not args.execute_locked_selection:
        raise SystemExit(
            "Refusing to build an assignment without --execute-locked-selection; "
            "use --dry-run to validate guards without reading data."
        )

    require_tracked_clean_protocol_lock(args.protocol_lock)
    require_clean_worktree()
    _assert_outputs_absent(
        [assignment_path, summary_path, cohort_flow_path, leakage_audit_path, manifest_path]
    )
    precursor_rows, historical_outcomes, locked_data_records = _read_and_revalidate_locked_projections(
        protocol_lock,
        panel_path,
        targets_path,
        config,
    )
    source_records = [*locked_data_records, target_manifest_record]
    selection = build_holdout_selection(precursor_rows, historical_outcomes, config)
    _write_locked_outputs(
        selection,
        assignment_path=assignment_path,
        summary_path=summary_path,
        cohort_flow_path=cohort_flow_path,
        leakage_audit_path=leakage_audit_path,
        manifest_path=manifest_path,
        config_path=args.config,
        source_records=source_records,
        protocol_lock_path=args.protocol_lock,
        protocol_lock=protocol_lock,
        config=config,
    )
    print(f"wrote {assignment_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    print(f"wrote {cohort_flow_path}", flush=True)
    print(f"wrote {leakage_audit_path}", flush=True)
    print(f"wrote {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
