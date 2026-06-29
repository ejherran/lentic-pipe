"""Standard API error and warning catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Stable machine-readable error codes."""

    invalid_request = "invalid_request"
    authentication_required = "authentication_required"
    permission_denied = "permission_denied"
    resource_not_found = "resource_not_found"
    insufficient_coverage = "insufficient_coverage"
    unsupported_pipeline_for_dataset = "unsupported_pipeline_for_dataset"
    no_valid_monthly_panel = "no_valid_monthly_panel"
    upstream_artifact_missing = "upstream_artifact_missing"
    schema_validation_failed = "schema_validation_failed"
    unsupported_unit = "unsupported_unit"
    value_out_of_range = "value_out_of_range"
    dependency_not_ready = "dependency_not_ready"
    pipeline_execution_failed = "pipeline_execution_failed"


class WarningCode(str, Enum):
    """Stable machine-readable warning codes."""

    low_variable_coverage = "low_variable_coverage"
    high_missingness = "high_missingness"
    limited_temporal_history = "limited_temporal_history"
    low_site_count = "low_site_count"
    unit_conversion_approximate = "unit_conversion_approximate"
    current_chla_dependency = "current_chla_dependency"
    counterfactual_not_causal = "counterfactual_not_causal"
    model_outside_validation_domain = "model_outside_validation_domain"


class ApiProblem(BaseModel):
    """Structured API problem detail."""

    code: ErrorCode
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    run_id: str | None = None
    report_uri: str | None = None


class ApiErrorResponse(BaseModel):
    """Standard non-2xx error response."""

    error: ApiProblem


class ApiWarning(BaseModel):
    """Structured warning embedded in successful responses."""

    code: WarningCode
    message: str
    details: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class ErrorCatalogEntry:
    """Static error catalog entry."""

    http_status: int
    code: ErrorCode
    retryable: bool


ERROR_CATALOG: tuple[ErrorCatalogEntry, ...] = (
    ErrorCatalogEntry(400, ErrorCode.invalid_request, False),
    ErrorCatalogEntry(401, ErrorCode.authentication_required, False),
    ErrorCatalogEntry(403, ErrorCode.permission_denied, False),
    ErrorCatalogEntry(404, ErrorCode.resource_not_found, False),
    ErrorCatalogEntry(409, ErrorCode.insufficient_coverage, False),
    ErrorCatalogEntry(409, ErrorCode.unsupported_pipeline_for_dataset, False),
    ErrorCatalogEntry(409, ErrorCode.no_valid_monthly_panel, False),
    ErrorCatalogEntry(409, ErrorCode.upstream_artifact_missing, True),
    ErrorCatalogEntry(422, ErrorCode.schema_validation_failed, False),
    ErrorCatalogEntry(422, ErrorCode.unsupported_unit, False),
    ErrorCatalogEntry(422, ErrorCode.value_out_of_range, False),
    ErrorCatalogEntry(424, ErrorCode.dependency_not_ready, True),
    ErrorCatalogEntry(500, ErrorCode.pipeline_execution_failed, True),
)


def error_catalog() -> list[dict[str, object]]:
    """Return a JSON-friendly copy of the error catalog."""

    return [
        {
            "http_status": item.http_status,
            "code": item.code.value,
            "retryable": item.retryable,
        }
        for item in ERROR_CATALOG
    ]


def warning_catalog() -> list[str]:
    """Return a stable list of warning codes."""

    return [code.value for code in WarningCode]
