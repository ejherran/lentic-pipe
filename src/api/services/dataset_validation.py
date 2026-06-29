"""Deterministic validation for external long-form datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.api.schemas.dataset import (
    DatasetOutcome,
    DatasetObservation,
    DatasetValidationRequest,
    DatasetValidationResponse,
    DatasetValidationSummary,
    ValidationIssue,
    WorkflowEligibility,
)

_VARIABLES_CONFIG = Path("configs/variables.yaml")


@dataclass(frozen=True)
class CanonicalVariable:
    """Validation rules for a canonical variable."""

    name: str
    canonical_unit: str
    allowed_units: frozenset[str]
    conversions: dict[str, str]
    plausible_min: float | None
    plausible_max: float | None
    impossible_if: frozenset[str]


@lru_cache(maxsize=1)
def load_canonical_variables() -> dict[str, CanonicalVariable]:
    """Load canonical variable validation rules from configs/variables.yaml."""

    with _VARIABLES_CONFIG.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    raw_variables = config.get("canonical_variables", {})
    variables: dict[str, CanonicalVariable] = {}
    for name, spec in raw_variables.items():
        plausible = spec.get("plausible_range") or {}
        variables[name] = CanonicalVariable(
            name=name,
            canonical_unit=str(spec.get("canonical_unit", "")),
            allowed_units=frozenset(str(unit) for unit in spec.get("allowed_units", [])),
            conversions={str(unit): str(rule) for unit, rule in spec.get("conversions", {}).items()},
            plausible_min=_optional_float(plausible.get("min")),
            plausible_max=_optional_float(plausible.get("max")),
            impossible_if=frozenset(str(item) for item in spec.get("impossible_if", [])),
        )
    return variables


def validate_dataset_request(request: DatasetValidationRequest) -> DatasetValidationResponse:
    """Validate a long-form external dataset without mutating repository state."""

    variables = load_canonical_variables()
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    valid_rows = 0
    sites: set[str] = set()
    months: set[str] = set()
    variable_counts: dict[str, int] = {}

    for row_index, observation in enumerate(request.observations):
        row_errors, row_warnings, year_month = _validate_observation(
            observation,
            row_index,
            variables,
        )
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if row_errors:
            continue
        valid_rows += 1
        sites.add(observation.site_id)
        if year_month is not None:
            months.add(year_month)
        variable_counts[observation.variable] = variable_counts.get(observation.variable, 0) + 1

    summary = DatasetValidationSummary(
        total_rows=len(request.observations),
        valid_rows=valid_rows,
        invalid_rows=len(request.observations) - valid_rows,
        sites=len(sites),
        months=len(months),
        canonical_variable_counts=dict(sorted(variable_counts.items())),
    )
    eligibility = _workflow_eligibility(summary, request.requested_workflow)
    outcome = _outcome(errors, warnings, eligibility, request.requested_workflow)
    return DatasetValidationResponse(
        outcome=outcome,
        summary=summary,
        errors=errors,
        warnings=warnings,
        workflow_eligibility=eligibility,
    )


def workflow_eligibility_for_summary(
    summary: DatasetValidationSummary,
    requested_workflow: str | None = None,
) -> list[WorkflowEligibility]:
    """Return workflow eligibility for a previously validated dataset summary."""

    return _workflow_eligibility(summary, requested_workflow)


def parse_observed_year_month(raw: str) -> str | None:
    """Parse an observation timestamp into YYYY-MM for canonical outputs."""

    return _parse_year_month(raw)


def _validate_observation(
    observation: DatasetObservation,
    row_index: int,
    variables: dict[str, CanonicalVariable],
) -> tuple[list[ValidationIssue], list[ValidationIssue], str | None]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    variable = variables.get(observation.variable)

    if variable is None:
        errors.append(
            ValidationIssue(
                code="schema_validation_failed",
                message=f"Unsupported variable '{observation.variable}'.",
                row_index=row_index,
                field="variable",
                details={"supported_variables": sorted(variables)},
            )
        )
        return errors, warnings, _parse_year_month(observation.observed_at)

    if observation.unit not in variable.allowed_units:
        errors.append(
            ValidationIssue(
                code="unsupported_unit",
                message=(
                    f"Unit '{observation.unit}' is not supported for "
                    f"{observation.variable}."
                ),
                row_index=row_index,
                field="unit",
                details={
                    "variable": observation.variable,
                    "supported_units": sorted(variable.allowed_units),
                },
            )
        )

    year_month = _parse_year_month(observation.observed_at)
    if year_month is None:
        errors.append(
            ValidationIssue(
                code="schema_validation_failed",
                message="observed_at must be an ISO-8601 date or timestamp.",
                row_index=row_index,
                field="observed_at",
                details={"observed_at": observation.observed_at},
            )
        )

    if "negative" in variable.impossible_if and observation.value < 0:
        errors.append(
            ValidationIssue(
                code="value_out_of_range",
                message=f"{observation.variable} cannot be negative.",
                row_index=row_index,
                field="value",
                details={"value": observation.value},
            )
        )
    elif variable.plausible_min is not None and observation.value < variable.plausible_min:
        warnings.append(
            ValidationIssue(
                code="value_out_of_range",
                message=f"{observation.variable} is below the declared plausible range.",
                row_index=row_index,
                field="value",
                details={"value": observation.value, "min": variable.plausible_min},
            )
        )
    elif variable.plausible_max is not None and observation.value > variable.plausible_max:
        warnings.append(
            ValidationIssue(
                code="value_out_of_range",
                message=f"{observation.variable} is above the declared plausible range.",
                row_index=row_index,
                field="value",
                details={"value": observation.value, "max": variable.plausible_max},
            )
        )

    if observation.unit != variable.canonical_unit and observation.unit in variable.allowed_units:
        warnings.append(
            ValidationIssue(
                code="unit_conversion_required",
                message=(
                    f"{observation.variable} uses '{observation.unit}' and will be "
                    f"converted to canonical unit '{variable.canonical_unit}'."
                ),
                row_index=row_index,
                field="unit",
                details={
                    "input_unit": observation.unit,
                    "canonical_unit": variable.canonical_unit,
                },
            )
        )

    return errors, warnings, year_month


def _workflow_eligibility(
    summary: DatasetValidationSummary,
    requested_workflow: str | None,
) -> list[WorkflowEligibility]:
    checks = [
        _eligibility(
            "canonical_observations",
            summary.valid_rows > 0,
            "At least one valid observation is required.",
        ),
        _eligibility(
            "monthly_panel",
            summary.months > 0 and summary.sites > 0,
            "At least one valid site-month is required.",
        ),
        _eligibility(
            "fuzzy_state",
            _has_any(summary, {"TP_ugL", "TN_ugL", "DO_mgL", "pH", "turbidity_NTU", "temperature_C", "secchi_depth_m"}),
            "At least one supported state variable is required.",
        ),
        _eligibility(
            "pipe_grud",
            summary.months >= 3 and _has_any(summary, {"chlorophyll_a_ugL", "TP_ugL", "TN_ugL"}),
            "PIPE-GRU-D requires at least three months and a compatible trophic/nutrient signal.",
        ),
        _eligibility(
            "pipe_neural_ode",
            summary.months >= 6 and _has_any(summary, {"chlorophyll_a_ugL", "TP_ugL", "TN_ugL"}),
            "Neural ODE requires a longer compatible temporal history.",
        ),
        _eligibility(
            "mifal_ed_t2",
            _has_any(summary, {"chlorophyll_a_ugL", "TP_ugL", "TN_ugL", "temperature_C", "DO_mgL"}),
            "MIFAL-ED/T2 requires observable-minimal ecological variables.",
        ),
        _eligibility(
            "counterfactual_planning",
            summary.months >= 3 and _has_any(summary, {"TP_ugL", "TN_ugL", "DO_mgL", "secchi_depth_m", "turbidity_NTU"}),
            "Counterfactual planning requires eligible temporal output and intervention proxies.",
        ),
    ]
    if requested_workflow is None:
        return checks
    return [check for check in checks if check.workflow == requested_workflow]


def _eligibility(workflow: str, eligible: bool, reason: str) -> WorkflowEligibility:
    return WorkflowEligibility(
        workflow=workflow,
        eligible=eligible,
        reason=None if eligible else reason,
    )


def _has_any(summary: DatasetValidationSummary, variables: set[str]) -> bool:
    return any(summary.canonical_variable_counts.get(variable, 0) > 0 for variable in variables)


def _outcome(
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    eligibility: list[WorkflowEligibility],
    requested_workflow: str | None,
) -> DatasetOutcome:
    if errors:
        return "invalid"
    if requested_workflow is not None and any(not item.eligible for item in eligibility):
        return "not_eligible"
    if warnings:
        return "valid_with_warnings"
    return "valid"


def _parse_year_month(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return f"{parsed.year:04d}-{parsed.month:02d}"
    except ValueError:
        pass
    try:
        parsed_date = date.fromisoformat(value)
        return f"{parsed_date.year:04d}-{parsed_date.month:02d}"
    except ValueError:
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
