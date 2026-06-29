import uuid
from datetime import datetime

from pydantic import BaseModel

from src.api.models.experiment import ExperimentStatus
from src.api.models.run import ModelType, RunStatus


class WorkspaceDatasetSummary(BaseModel):
    """Compact dataset metadata for workspace navigation."""

    id: uuid.UUID
    name: str
    source_id: str | None
    file_path: str | None
    scientific_dataset_id: str | None
    validation_outcome: str | None
    created_at: datetime


class WorkspaceRunOutputSummary(BaseModel):
    """Output surfaces discoverable from a persisted run result bundle."""

    plan_id: str | None = None
    artifacts: bool = False
    result_summary: bool = False
    predictions: bool = False
    alerts: bool = False


class WorkspaceRunSummary(BaseModel):
    """Compact run metadata for workspace navigation."""

    id: uuid.UUID
    name: str | None
    model_type: ModelType
    status: RunStatus
    workflow: str | None
    execution_mode: str | None
    outputs: WorkspaceRunOutputSummary
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class WorkspaceExperimentCatalogEntry(BaseModel):
    """One experiment row in the authenticated workspace catalog."""

    id: uuid.UUID
    title: str
    description: str | None
    status: ExperimentStatus
    role: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    dataset_count: int
    run_count: int
    run_status_counts: dict[str, int]
    latest_dataset: WorkspaceDatasetSummary | None
    latest_run: WorkspaceRunSummary | None
    latest_scientific_run: WorkspaceRunSummary | None
    available_views: list[str]


class WorkspaceCatalogSummary(BaseModel):
    """Page-level catalog totals for quick dashboards and clients."""

    visible_experiments: int
    page_experiments: int
    page_datasets: int
    page_runs: int
    page_scientific_runs: int
    page_run_status_counts: dict[str, int]
    page_output_view_counts: dict[str, int]


class WorkspaceCatalogResponse(BaseModel):
    """Authenticated catalog of experiment-scoped workspace resources."""

    items: list[WorkspaceExperimentCatalogEntry]
    total: int
    limit: int
    offset: int
    summary: WorkspaceCatalogSummary
