import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

from src.api.models.run import ModelType, RunStatus

# Required top-level keys for each model type that needs explicit configuration.
# Baselines and MIFAL are self-contained; PIPE models require horizon and seed.
_REQUIRED_CONFIG_KEYS: dict[ModelType, set[str]] = {
    ModelType.pipe_grud: {"horizon_days", "seed"},
    ModelType.pipe_neural_ode: {"horizon_days", "seed"},
}


class RunCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "pipe-grud-horizon90-seed42",
                "model_type": "PIPE_GRUD",
                "config": {"horizon_days": 90, "seed": 42},
            }
        }
    }

    name: str | None = None
    model_type: ModelType
    config: dict | None = None

    @model_validator(mode="after")
    def validate_config_for_model_type(self) -> "RunCreateRequest":
        if self.config and self.config.get("dataset_id") and (
            self.config.get("workflow") or self.config.get("science_workflow")
        ):
            return self
        required = _REQUIRED_CONFIG_KEYS.get(self.model_type)
        if required:
            provided = set(self.config or {})
            missing = required - provided
            if missing:
                raise ValueError(
                    f"config is missing required keys for {self.model_type}: {sorted(missing)}"
                )
        return self


class RunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str | None
    model_type: ModelType
    config: dict | None
    status: RunStatus
    task_id: str | None
    error_message: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RunResultsResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: RunStatus
    results: dict | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class RunCompareRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "run_ids": [
                    "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "7cb12a45-1234-4abc-9def-0123456789ab",
                ]
            }
        }
    }

    run_ids: list[uuid.UUID]

    @field_validator("run_ids")
    @classmethod
    def validate_run_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) < 2:
            raise ValueError("At least 2 run IDs are required for comparison")
        if len(v) > 10:
            raise ValueError("Cannot compare more than 10 runs at once")
        if len(set(v)) != len(v):
            raise ValueError("Duplicate run IDs are not allowed")
        return v


class RunCompareEntry(BaseModel):
    model_config = {"from_attributes": True}

    run_id: uuid.UUID
    name: str | None
    model_type: ModelType
    status: RunStatus
    metrics: dict | None


class RunCompareResponse(BaseModel):
    experiment_id: uuid.UUID
    runs: list[RunCompareEntry]
    # Metrics extracted side-by-side for quick inspection
    metric_table: dict[str, dict[str, float | None]]


# Scientific workflow schemas kept separate from the job lifecycle schemas.
# Re-exported here while the public API preserves the existing local workflow
# import paths.
from src.api.schemas.science_run import (  # noqa: E402
    RunArtifactListResponse,
    RunArtifactPreviewFormat,
    RunArtifactPreviewResponse,
    RunExecutionStatus,
    RunExecutionResponse,
    RunPlanArtifactAvailability,
    RunPlanArtifact,
    RunPlanRequest,
    RunPlanResponse,
    RunPlanStatus,
    RunPlanStep,
    RunPlanStepStatus,
    RunResultSummaryResponse,
)
