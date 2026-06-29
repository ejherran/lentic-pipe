"""Minimal run-scoped counterfactual simulations for generated API surfaces."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.api.errors import ErrorCode
from src.api.schemas.simulation import (
    AlertChange,
    CounterfactualIntervention,
    CurrentStateCounterfactualRecord,
    CurrentStateCounterfactualRequest,
    CurrentStateCounterfactualResponse,
)
from src.api.services.run_repository import read_run_execution, run_plan_dir
from src.fuzzy.expert import build_expert_state

_FUZZY_WIDE_PANEL = "monthly_panel_wide.csv"
_FUZZY_STATE_SCORES = "fuzzy_state_scores.csv"
_FUZZY_STATE_MANIFEST = "fuzzy_state_manifest.json"
_SIMULATION_DIR = "simulations"
_NONNEGATIVE_VARIABLES = {
    "chlorophyll_a_ugL",
    "TP_ugL",
    "TN_ugL",
    "DO_mgL",
    "turbidity_NTU",
    "secchi_depth_m",
}
_PANEL_COLUMN_BY_VARIABLE = {
    "chlorophyll_a_ugL": "mean_chlorophyll_a_ugL",
    "TP_ugL": "mean_TP_ugL",
    "TN_ugL": "mean_TN_ugL",
    "DO_mgL": "mean_DO_mgL",
    "pH": "mean_pH",
    "turbidity_NTU": "mean_turbidity_NTU",
    "temperature_C": "mean_temperature_C",
    "secchi_depth_m": "mean_secchi_depth_m",
}
_INTERPRETATION_LIMITS = [
    "This is a deterministic current-state expert fuzzy simulation, not causal field evidence.",
    "The simulation recomputes current fuzzy state scores after declared input changes.",
    "It does not run temporal rollouts, PIPE-GRU-D, Neural ODE, or intervention planning.",
    "Scenario values are user-declared research assumptions and should be checked for plausibility.",
]


class RunSimulationError(Exception):
    """Expected counterfactual simulation failure with a stable API error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, object] | None = None,
        http_status: int = 409,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


def simulate_current_state_counterfactual(
    plan_id: str,
    request: CurrentStateCounterfactualRequest,
) -> CurrentStateCounterfactualResponse:
    """Run a minimal current-state counterfactual simulation over fuzzy outputs."""

    execution = read_run_execution(plan_id)
    run_dir = run_plan_dir(execution.plan_id)
    wide_panel_path = run_dir / _FUZZY_WIDE_PANEL
    baseline_path = run_dir / _FUZZY_STATE_SCORES
    manifest_path = run_dir / _FUZZY_STATE_MANIFEST
    if not wide_panel_path.exists() or not baseline_path.exists():
        raise RunSimulationError(
            ErrorCode.unsupported_pipeline_for_dataset,
            "Run execution does not include the fuzzy state surface required for this simulation.",
            details={
                "workflow": execution.workflow,
                "required_artifacts": [_FUZZY_WIDE_PANEL, _FUZZY_STATE_SCORES],
                "supported_workflows": ["fuzzy_state"],
            },
        )
    manifest = _read_manifest(manifest_path)
    threshold = _manifest_threshold(manifest)
    weights = _manifest_weights(manifest)

    panel = pd.read_csv(wide_panel_path)
    scenario_panel = _apply_interventions(panel, request.interventions)
    scenario_panel = _refresh_derived_columns(scenario_panel)
    scenario_state, _trace = build_expert_state(scenario_panel, irc_weights=weights)
    baseline = pd.read_csv(baseline_path)
    rows = _comparison_rows(baseline, scenario_state, threshold, request.only_changed_alerts)
    rows = rows[: request.limit]

    simulation_id = _simulation_id(execution.plan_id, request)
    result_path = run_dir / _SIMULATION_DIR / simulation_id / "counterfactual_current_state.json"
    result_uri = result_path.relative_to(run_dir.parent.parent).as_posix()
    response = CurrentStateCounterfactualResponse(
        simulation_id=simulation_id,
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        dataset_id=execution.dataset_id,
        workflow=execution.workflow,
        status="completed",
        simulation_scope="expert_fuzzy_current_state",
        scenario_name=request.scenario_name,
        interventions=request.interventions,
        threshold=threshold,
        result_uri=result_uri,
        rows=rows,
        interpretation_limits=_INTERPRETATION_LIMITS,
    )
    _write_response(result_path, response)
    return response


def _apply_interventions(
    panel: pd.DataFrame,
    interventions: list[CounterfactualIntervention],
) -> pd.DataFrame:
    scenario = panel.copy()
    for intervention in interventions:
        column = _PANEL_COLUMN_BY_VARIABLE[intervention.variable]
        if column not in scenario.columns:
            raise RunSimulationError(
                ErrorCode.pipeline_execution_failed,
                "Counterfactual input panel is missing a required variable column.",
                details={"variable": intervention.variable, "column": column},
                http_status=500,
            )
        values = pd.to_numeric(scenario[column], errors="coerce")
        if intervention.operation == "scale":
            if intervention.value < 0.0:
                raise RunSimulationError(
                    ErrorCode.invalid_request,
                    "Scale interventions must use a non-negative value.",
                    details={"variable": intervention.variable, "value": intervention.value},
                    http_status=400,
                )
            updated = values * intervention.value
        elif intervention.operation == "add":
            updated = values + intervention.value
        elif intervention.operation == "set":
            updated = pd.Series(intervention.value, index=scenario.index, dtype="float64").where(values.notna())
        else:
            raise RunSimulationError(
                ErrorCode.invalid_request,
                "Unsupported counterfactual intervention operation.",
                details={"operation": intervention.operation},
                http_status=400,
            )
        if intervention.variable in _NONNEGATIVE_VARIABLES and (updated.dropna() < 0.0).any():
            raise RunSimulationError(
                ErrorCode.value_out_of_range,
                "Counterfactual intervention would produce negative values for a non-negative variable.",
                details={"variable": intervention.variable, "operation": intervention.operation},
                http_status=422,
            )
        scenario[column] = updated
    return scenario


def _refresh_derived_columns(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    tp = pd.to_numeric(out.get("mean_TP_ugL"), errors="coerce")
    tn = pd.to_numeric(out.get("mean_TN_ugL"), errors="coerce")
    out["TN_TP_ratio"] = (tn / tp.where(tp > 0.0)).replace([math.inf, -math.inf], pd.NA)
    chla = pd.to_numeric(out.get("mean_chlorophyll_a_ugL"), errors="coerce")
    out["risk_chla"] = chla.map(_chlorophyll_risk)
    return out


def _comparison_rows(
    baseline: pd.DataFrame,
    scenario: pd.DataFrame,
    threshold: float,
    only_changed_alerts: bool,
) -> list[CurrentStateCounterfactualRecord]:
    merged = baseline.merge(
        scenario,
        on=["source_id", "site_id", "year_month"],
        how="inner",
        suffixes=("_baseline", "_simulated"),
    )
    records: list[CurrentStateCounterfactualRecord] = []
    for _, row in merged.iterrows():
        baseline_score = _float_or_none(row.get("irc1_baseline"))
        simulated_score = _float_or_none(row.get("irc1_simulated"))
        if baseline_score is None or simulated_score is None:
            continue
        baseline_alert = baseline_score >= threshold
        simulated_alert = simulated_score >= threshold
        alert_change = _alert_change(baseline_alert, simulated_alert)
        if only_changed_alerts and alert_change in {"unchanged_alert", "unchanged_non_alert"}:
            continue
        records.append(
            CurrentStateCounterfactualRecord(
                source_id=str(row.get("source_id", "")),
                site_id=str(row.get("site_id", "")),
                year_month=str(row.get("year_month", "")),
                horizon_months=0,
                baseline_score=baseline_score,
                simulated_score=simulated_score,
                delta_score=simulated_score - baseline_score,
                baseline_alert=baseline_alert,
                simulated_alert=simulated_alert,
                alert_change=alert_change,
                baseline_components=_components(row, suffix="baseline"),
                simulated_components=_components(row, suffix="simulated"),
            )
        )
    return sorted(records, key=lambda item: (item.delta_score, item.source_id, item.site_id, item.year_month))


def _components(row: Any, *, suffix: str) -> dict[str, object]:
    components: dict[str, object] = {}
    for column in ("yN", "yF", "yT", "irc1_no_chla", "risk_chla_current"):
        value = _float_or_none(row.get(f"{column}_{suffix}"))
        if value is not None:
            components[column] = value
    for column in (
        "state_trophic_expert",
        "nutrient_pressure_label",
        "physicochemical_condition_label",
        "thermal_biological_label",
    ):
        value = row.get(f"{column}_{suffix}")
        if value not in {None, ""}:
            components[column] = str(value)
    return components


def _alert_change(baseline_alert: bool, simulated_alert: bool) -> AlertChange:
    if baseline_alert and not simulated_alert:
        return "cleared"
    if not baseline_alert and simulated_alert:
        return "new_alert"
    if baseline_alert and simulated_alert:
        return "unchanged_alert"
    return "unchanged_non_alert"


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RunSimulationError(
            ErrorCode.dependency_not_ready,
            "Fuzzy state manifest is required for current-state counterfactual simulation.",
            details={"required_artifact": _FUZZY_STATE_MANIFEST},
            http_status=424,
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_threshold(manifest: dict[str, object]) -> float:
    threshold = _float_or_none(manifest.get("alert_threshold"))
    if threshold is None:
        threshold = _float_or_none(manifest.get("threshold"))
    if threshold is None or threshold < 0.0 or threshold > 1.0:
        raise RunSimulationError(
            ErrorCode.pipeline_execution_failed,
            "Fuzzy manifest contains an invalid counterfactual alert threshold.",
            details={"artifact": _FUZZY_STATE_MANIFEST},
            http_status=500,
        )
    return threshold


def _manifest_weights(manifest: dict[str, object]) -> dict[str, float]:
    raw_payload = manifest.get("irc_weights")
    if not isinstance(raw_payload, dict):
        raise RunSimulationError(
            ErrorCode.pipeline_execution_failed,
            "Fuzzy manifest contains invalid IRC weights.",
            details={"artifact": _FUZZY_STATE_MANIFEST},
            http_status=500,
        )
    raw_weights = cast(dict[str, object], raw_payload)
    weights: dict[str, float] = {}
    for name in ("alpha", "beta", "gamma"):
        value = _float_or_none(raw_weights.get(name))
        if value is None or value <= 0.0:
            raise RunSimulationError(
                ErrorCode.pipeline_execution_failed,
                "Fuzzy manifest contains invalid IRC weights.",
                details={"artifact": _FUZZY_STATE_MANIFEST, "weight": name},
                http_status=500,
            )
        weights[name] = value
    return weights


def _simulation_id(plan_id: str, request: CurrentStateCounterfactualRequest) -> str:
    payload = {
        "plan_id": plan_id,
        "scenario_name": request.scenario_name,
        "interventions": [item.model_dump(mode="json") for item in request.interventions],
        "only_changed_alerts": request.only_changed_alerts,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sim_{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


def _write_response(path: Path, response: CurrentStateCounterfactualResponse) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _chlorophyll_risk(chla_ugl: object) -> float | None:
    value = _float_or_none(chla_ugl)
    if value is None:
        return None
    low = math.log(5.0 + 0.1)
    high = math.log(30.0 + 0.1)
    risk = (math.log(max(value, 0.0) + 0.1) - low) / (high - low)
    return min(1.0, max(0.0, risk))


def _float_or_none(value: object) -> float | None:
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number
