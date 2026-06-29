"""Dataset validation schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


WorkflowName = Literal[
    "canonical_observations",
    "monthly_panel",
    "fuzzy_state",
    "pipe_grud",
    "pipe_neural_ode",
    "mifal_ed_t2",
    "counterfactual_planning",
]

DatasetOutcome = Literal["valid", "valid_with_warnings", "invalid", "not_eligible"]
DatasetStorageStatus = Literal["registered"]


class DatasetObservation(BaseModel):
    """Long-form external observation submitted to the API."""

    source_id: str = Field(min_length=1, max_length=100)
    site_id: str = Field(min_length=1, max_length=200)
    observed_at: str = Field(description="ISO-8601 date or timestamp.")
    variable: str = Field(description="Canonical variable name or declared source variable.")
    value: float
    unit: str = Field(min_length=1, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    depth_m: float | None = Field(default=None, ge=0)
    qc_flag: str | None = None
    method: str | None = None
    notes: str | None = None


class DatasetValidationRequest(BaseModel):
    """Dataset validation request."""

    dataset_name: str | None = Field(default=None, max_length=255)
    observations: list[DatasetObservation] = Field(min_length=1, max_length=5000)
    requested_workflow: WorkflowName | None = None


class ValidationIssue(BaseModel):
    """Validation error or warning."""

    code: str
    message: str
    row_index: int | None = None
    field: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class WorkflowEligibility(BaseModel):
    """Workflow eligibility result."""

    workflow: str
    eligible: bool
    reason: str | None = None
    warnings: list[ValidationIssue] = Field(default_factory=list)


class DatasetValidationSummary(BaseModel):
    """High-level validation summary."""

    total_rows: int
    valid_rows: int
    invalid_rows: int
    sites: int
    months: int
    canonical_variable_counts: dict[str, int]


class DatasetValidationResponse(BaseModel):
    """Dataset validation response."""

    outcome: DatasetOutcome
    summary: DatasetValidationSummary
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    workflow_eligibility: list[WorkflowEligibility] = Field(default_factory=list)


class DatasetArtifact(BaseModel):
    """Artifact created by dataset registration."""

    name: str
    uri: str
    media_type: str
    sha256: str
    bytes: int = Field(ge=0)


class DatasetRegistrationResponse(BaseModel):
    """Persistent dataset registration response."""

    dataset_id: str
    dataset_name: str | None = None
    status: DatasetStorageStatus
    registered_at: str
    content_sha256: str
    requested_workflow: WorkflowName | None = None
    validation: DatasetValidationResponse
    artifacts: list[DatasetArtifact] = Field(default_factory=list)
