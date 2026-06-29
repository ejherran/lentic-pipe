import uuid
from datetime import datetime

from pydantic import BaseModel

from src.api.models.experiment import CollaboratorRole, ExperimentStatus


class ExperimentCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Mendota Bloom Study 2024",
                "description": "Seasonal phosphorus load analysis for Lake Mendota",
                "config": {"data_freeze": "2023-12-31", "cv_folds": 5},
            }
        }
    }

    title: str
    description: str | None = None
    config: dict | None = None


class ExperimentUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    config: dict | None = None
    status: ExperimentStatus | None = None


class ExperimentImportRequest(BaseModel):
    experiment: dict
    datasets: list[dict] = []


class ExperimentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    description: str | None
    config: dict | None
    status: ExperimentStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CollaboratorResponse(BaseModel):
    model_config = {"from_attributes": True}

    user_id: uuid.UUID
    role: CollaboratorRole
    invited_by_id: uuid.UUID | None
    created_at: datetime


class AddCollaboratorRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {"user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "role": "editor"}
        }
    }

    user_id: uuid.UUID
    role: CollaboratorRole = CollaboratorRole.viewer


class UpdateCollaboratorRequest(BaseModel):
    role: CollaboratorRole


class DatasetCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Mendota 2018–2022 panel",
                "description": "Monthly limnological measurements from NTL-LTER",
                "source_id": "EDI.395.3",
                "file_path": "/data/mendota_panel.parquet",
                "meta": {"n_rows": 60, "variables": ["TP_ugL", "TN_ugL", "chlorophyll_a_ugL"]},
            }
        }
    }

    name: str
    description: str | None = None
    source_id: str | None = None
    file_path: str | None = None
    meta: dict | None = None


class DatasetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    description: str | None
    source_id: str | None
    file_path: str | None
    meta: dict | None
    created_by: uuid.UUID | None
    created_at: datetime
