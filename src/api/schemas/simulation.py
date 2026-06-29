"""Counterfactual simulation response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.api.schemas.dataset import WorkflowName

CounterfactualOperation = Literal["scale", "add", "set"]
CounterfactualVariable = Literal[
    "chlorophyll_a_ugL",
    "TP_ugL",
    "TN_ugL",
    "DO_mgL",
    "pH",
    "turbidity_NTU",
    "temperature_C",
    "secchi_depth_m",
]
AlertChange = Literal["cleared", "new_alert", "unchanged_alert", "unchanged_non_alert"]


class CounterfactualIntervention(BaseModel):
    """Single deterministic current-state intervention."""

    variable: CounterfactualVariable
    operation: CounterfactualOperation
    value: float


class CurrentStateCounterfactualRequest(BaseModel):
    """Request a minimal current-state counterfactual simulation."""

    scenario_name: str | None = Field(default=None, max_length=120)
    interventions: list[CounterfactualIntervention] = Field(min_length=1, max_length=20)
    limit: int = Field(default=100, ge=1, le=1000)
    only_changed_alerts: bool = False


class CurrentStateCounterfactualRecord(BaseModel):
    """Single current-state counterfactual comparison row."""

    source_id: str
    site_id: str
    year_month: str
    horizon_months: int = Field(ge=0)
    baseline_score: float = Field(ge=0.0, le=1.0)
    simulated_score: float = Field(ge=0.0, le=1.0)
    delta_score: float
    baseline_alert: bool
    simulated_alert: bool
    alert_change: AlertChange
    baseline_components: dict[str, object] = Field(default_factory=dict)
    simulated_components: dict[str, object] = Field(default_factory=dict)


class CurrentStateCounterfactualResponse(BaseModel):
    """Minimal run-scoped current-state counterfactual simulation response."""

    simulation_id: str
    plan_id: str
    execution_id: str
    dataset_id: str
    workflow: WorkflowName
    status: Literal["completed"]
    simulation_scope: Literal["expert_fuzzy_current_state"]
    scenario_name: str | None = None
    interventions: list[CounterfactualIntervention]
    threshold: float = Field(ge=0.0, le=1.0)
    result_uri: str
    rows: list[CurrentStateCounterfactualRecord] = Field(default_factory=list)
    interpretation_limits: list[str] = Field(default_factory=list)
