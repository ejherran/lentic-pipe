import re
import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

from src.api.models.simulation import SimulationStatus
from src.api.schemas.science_simulation import CounterfactualIntervention

VALID_HORIZONS = {30, 60, 90}


class NutrientReductionScenario(BaseModel):
    type: Literal["nutrient_reduction"]
    TP_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    TN_factor: float = Field(default=1.0, ge=0.0, le=1.0)


class AerationScenario(BaseModel):
    type: Literal["aeration"]
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)


class NoActionScenario(BaseModel):
    type: Literal["no_action"]


class CombinedScenario(BaseModel):
    type: Literal["combined"]
    TP_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    TN_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    temperature_delta: float = Field(default=0.0, ge=-5.0, le=5.0)
    pH_delta: float = Field(default=0.0, ge=-1.0, le=1.0)


class CurrentStateCounterfactualScenario(BaseModel):
    type: Literal["current_state_counterfactual"]
    plan_id: str = Field(min_length=16, max_length=128)
    scenario_name: str | None = Field(default=None, max_length=120)
    interventions: list[CounterfactualIntervention] = Field(min_length=1, max_length=20)
    limit: int = Field(default=100, ge=1, le=1000)
    only_changed_alerts: bool = False


Scenario = Annotated[
    Union[
        NutrientReductionScenario,
        AerationScenario,
        NoActionScenario,
        CombinedScenario,
        CurrentStateCounterfactualScenario,
    ],
    Field(discriminator="type"),
]


class SimulationCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "site_id": "MENDOTA",
                "year_month": "2022-06",
                "horizon_days": 90,
                "n_trajectories": 30,
                "scenario": {
                    "type": "nutrient_reduction",
                    "TP_factor": 0.85,
                    "TN_factor": 0.90,
                },
            }
        }
    }

    site_id: str = Field(min_length=1, max_length=100)
    year_month: str
    horizon_days: int
    n_trajectories: int = Field(default=30, ge=1, le=200)
    scenario: Scenario
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


class SimulationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    experiment_id: uuid.UUID | None
    site_id: str
    year_month: str
    horizon_days: int
    n_trajectories: int
    scenario: dict
    status: SimulationStatus
    task_id: str | None
    result: dict | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


from src.api.schemas.science_simulation import (  # noqa: E402
    AlertChange,
    CounterfactualOperation,
    CounterfactualVariable,
    CounterfactualIntervention,
    CurrentStateCounterfactualRecord,
    CurrentStateCounterfactualRequest,
    CurrentStateCounterfactualResponse,
)
