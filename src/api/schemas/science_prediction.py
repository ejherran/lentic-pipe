"""Prediction and alert response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.api.schemas.dataset import WorkflowName

PredictionSurfaceStatus = Literal["available"]
PredictionScoreKind = Literal["expert_score", "model_probability", "calibrated_probability"]
AlertSeverity = Literal["low", "watch", "alert"]


class RunPredictionRecord(BaseModel):
    """Single run-scoped prediction or state-score record."""

    source_id: str
    site_id: str
    year_month: str
    horizon_months: int = Field(ge=0)
    target: str
    score_name: str
    score: float = Field(ge=0.0, le=1.0)
    score_kind: PredictionScoreKind
    model_family: str
    workflow: WorkflowName
    components: dict[str, object] = Field(default_factory=dict)
    interpretation: str


class RunPredictionResponse(BaseModel):
    """Run-scoped prediction/state-score surface."""

    plan_id: str
    execution_id: str
    dataset_id: str
    workflow: WorkflowName
    status: PredictionSurfaceStatus
    prediction_surface: str
    predictions: list[RunPredictionRecord] = Field(default_factory=list)
    interpretation_limits: list[str] = Field(default_factory=list)


class RunAlertRecord(BaseModel):
    """Single run-scoped alert record."""

    source_id: str
    site_id: str
    year_month: str
    horizon_months: int = Field(ge=0)
    target_event: str
    score_name: str
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    is_alert: bool
    severity: AlertSeverity
    rank: int = Field(ge=1)
    policy_version: str
    workflow: WorkflowName
    interpretation: str


class RunAlertResponse(BaseModel):
    """Run-scoped alert view derived from an available prediction surface."""

    plan_id: str
    execution_id: str
    dataset_id: str
    workflow: WorkflowName
    status: PredictionSurfaceStatus
    alert_surface: str
    policy_version: str
    threshold: float = Field(ge=0.0, le=1.0)
    alerts: list[RunAlertRecord] = Field(default_factory=list)
    interpretation_limits: list[str] = Field(default_factory=list)
