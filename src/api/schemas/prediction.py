import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.api.models.run import ModelType

VALID_HORIZONS = {30, 60, 90}


class PredictionVariables(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "TP_ugL": 35.0,
                "TN_ugL": 900.0,
                "chlorophyll_a_ugL": 12.0,
                "DO_mgL": 8.1,
                "pH": 8.2,
                "turbidity_NTU": 5.0,
                "temperature_C": 22.0,
            }
        }
    }

    TP_ugL: float | None = None
    TN_ugL: float | None = None
    chlorophyll_a_ugL: float | None = None
    DO_mgL: float | None = None
    pH: float | None = None
    turbidity_NTU: float | None = None
    temperature_C: float | None = None
    secchi_depth_m: float | None = None
    wind_speed_ms: float | None = None
    residence_time_d: float | None = None


class PredictionCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "site_id": "MENDOTA",
                "year_month": "2022-06",
                "horizon_days": 90,
                "model": "PIPE_GRUD",
                "variables": {
                    "TP_ugL": 35.0,
                    "TN_ugL": 900.0,
                    "chlorophyll_a_ugL": 12.0,
                    "DO_mgL": 8.1,
                    "pH": 8.2,
                    "turbidity_NTU": 5.0,
                    "temperature_C": 22.0,
                },
            }
        }
    }

    site_id: str = Field(min_length=1, max_length=100)
    year_month: str
    horizon_days: int
    variables: PredictionVariables
    model: ModelType = ModelType.pipe_grud
    experiment_id: uuid.UUID | None = None

    @field_validator("horizon_days")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        if v not in VALID_HORIZONS:
            raise ValueError(f"horizon_days must be one of {sorted(VALID_HORIZONS)}")
        return v

    @field_validator("year_month")
    @classmethod
    def validate_year_month(cls, v: str) -> str:
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", v):
            raise ValueError("year_month must be in YYYY-MM format")
        return v


class PredictionBatchRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "predictions": [
                    {
                        "site_id": "MENDOTA",
                        "year_month": "2022-06",
                        "horizon_days": 90,
                        "model": "PIPE_GRUD",
                        "variables": {"TP_ugL": 35.0, "TN_ugL": 900.0, "temperature_C": 22.0},
                    },
                    {
                        "site_id": "WINGRA",
                        "year_month": "2022-06",
                        "horizon_days": 30,
                        "model": "BASELINE_RF",
                        "variables": {"TP_ugL": 18.0, "temperature_C": 20.0},
                    },
                ]
            }
        }
    }

    predictions: list[PredictionCreateRequest] = Field(min_length=1, max_length=20)


class PredictionResultDetail(BaseModel):
    bloom_probability: float | None = None
    risk_continuous: float | None = None
    trophic_state: str | None = None
    trophic_memberships: dict[str, float] | None = None
    irc: float | None = None
    state_vector: dict | None = None
    uncertainty: dict | None = None
    model_version: str | None = None
    note: str | None = None


class PredictionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    experiment_id: uuid.UUID | None
    model_type: ModelType
    site_id: str
    year_month: str
    horizon_days: int
    input_variables: dict
    result: dict | None
    created_at: datetime


from src.api.schemas.science_prediction import (  # noqa: E402
    AlertSeverity,
    PredictionScoreKind,
    PredictionSurfaceStatus,
    RunAlertRecord,
    RunAlertResponse,
    RunPredictionRecord,
    RunPredictionResponse,
)
