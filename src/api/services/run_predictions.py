"""Run-scoped prediction and alert views over generated API artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, cast

from src.api.errors import ErrorCode
from src.api.schemas.dataset import WorkflowName
from src.api.schemas.prediction import (
    AlertSeverity,
    RunAlertRecord,
    RunAlertResponse,
    RunPredictionRecord,
    RunPredictionResponse,
)
from src.api.services.run_repository import read_run_execution, run_plan_dir

_FUZZY_STATE_SCORES = "fuzzy_state_scores.csv"
_FUZZY_STATE_MANIFEST = "fuzzy_state_manifest.json"
_FUZZY_ROOT_MANIFEST = Path("reports/anfis/fuzzy_manifest.json")
_PREDICTION_LIMITS = [
    "These records are current-month expert fuzzy state scores, not temporal forecasts.",
    "The score is an expert IRC state-risk score, not a calibrated probability.",
    "Temporal early-warning alerts require PIPE-GRU-D or Neural ODE workflow adapters.",
]
_ALERT_LIMITS = [
    "These records are thresholded current-state risk indicators, not official public advisories.",
    "The alert flag is derived from expert fuzzy IRC state score and a frozen threshold.",
    "Temporal early-warning alerts require PIPE-GRU-D or Neural ODE workflow adapters.",
]


class RunPredictionError(Exception):
    """Expected prediction/alert access failure with a stable API error code."""

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


def list_run_predictions(plan_id: str, *, limit: int) -> RunPredictionResponse:
    """Return available run-scoped prediction/state-score records."""

    execution = read_run_execution(plan_id)
    run_dir = run_plan_dir(execution.plan_id)
    rows = _read_fuzzy_score_rows(run_dir, workflow=execution.workflow)
    manifest = _read_fuzzy_manifest(run_dir)
    records = [_prediction_record(row, execution.workflow, manifest) for row in rows]
    records = [record for record in records if record is not None][:limit]
    return RunPredictionResponse(
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        dataset_id=execution.dataset_id,
        workflow=execution.workflow,
        status="available",
        prediction_surface="expert_fuzzy_current_state",
        predictions=records,
        interpretation_limits=_PREDICTION_LIMITS,
    )


def list_run_alerts(plan_id: str, *, limit: int, only_alerts: bool) -> RunAlertResponse:
    """Return available run-scoped alert records."""

    execution = read_run_execution(plan_id)
    run_dir = run_plan_dir(execution.plan_id)
    rows = _read_fuzzy_score_rows(run_dir, workflow=execution.workflow)
    manifest = _read_fuzzy_manifest(run_dir)
    threshold = _manifest_threshold(manifest)
    policy_version = str(manifest.get("alert_policy_version", "expert_fuzzy_state_v0_threshold"))
    records = [
        record
        for record in (_alert_record(row, execution.workflow, threshold, policy_version) for row in rows)
        if record is not None
    ]
    records = sorted(records, key=lambda record: (-record.score, record.source_id, record.site_id, record.year_month))
    ranked_records = [
        record.model_copy(update={"rank": rank})
        for rank, record in enumerate(records, start=1)
        if not only_alerts or record.is_alert
    ][:limit]
    return RunAlertResponse(
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        dataset_id=execution.dataset_id,
        workflow=execution.workflow,
        status="available",
        alert_surface="expert_fuzzy_current_state_threshold",
        policy_version=policy_version,
        threshold=threshold,
        alerts=ranked_records,
        interpretation_limits=_ALERT_LIMITS,
    )


def _read_fuzzy_score_rows(run_dir: Path, *, workflow: str) -> list[dict[str, str]]:
    path = run_dir / _FUZZY_STATE_SCORES
    if not path.exists():
        raise RunPredictionError(
            ErrorCode.unsupported_pipeline_for_dataset,
            "Run execution does not include a supported prediction or alert surface.",
            details={
                "workflow": workflow,
                "required_artifact": _FUZZY_STATE_SCORES,
                "supported_workflows": ["fuzzy_state"],
            },
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_fuzzy_manifest(run_dir: Path) -> dict[str, object]:
    path = run_dir / _FUZZY_STATE_MANIFEST
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if _FUZZY_ROOT_MANIFEST.exists():
        return json.loads(_FUZZY_ROOT_MANIFEST.read_text(encoding="utf-8"))
    raise RunPredictionError(
        ErrorCode.dependency_not_ready,
        "Fuzzy manifest is required to interpret prediction and alert surfaces.",
        details={"required_artifact": _FUZZY_STATE_MANIFEST},
        http_status=424,
    )


def _prediction_record(
    row: dict[str, str],
    workflow: WorkflowName,
    manifest: dict[str, object],
) -> RunPredictionRecord | None:
    score = _float_or_none(row.get("irc1"))
    if score is None:
        return None
    return RunPredictionRecord(
        source_id=str(row.get("source_id", "")),
        site_id=str(row.get("site_id", "")),
        year_month=str(row.get("year_month", "")),
        horizon_months=0,
        target="current_irc_risk",
        score_name="irc1",
        score=score,
        score_kind="expert_score",
        model_family=str(manifest.get("state_version", "expert_fuzzy_state_v0")),
        workflow=workflow,
        components=_prediction_components(row),
        interpretation="Current-month expert fuzzy composite risk score.",
    )


def _alert_record(
    row: dict[str, str],
    workflow: WorkflowName,
    threshold: float,
    policy_version: str,
) -> RunAlertRecord | None:
    score = _float_or_none(row.get("irc1"))
    if score is None:
        return None
    is_alert = score >= threshold
    return RunAlertRecord(
        source_id=str(row.get("source_id", "")),
        site_id=str(row.get("site_id", "")),
        year_month=str(row.get("year_month", "")),
        horizon_months=0,
        target_event="current_irc_risk",
        score_name="irc1",
        score=score,
        threshold=threshold,
        is_alert=is_alert,
        severity=_severity(score, threshold),
        rank=1,
        policy_version=policy_version,
        workflow=workflow,
        interpretation="Thresholded current-month expert fuzzy composite risk indicator.",
    )


def _prediction_components(row: dict[str, str]) -> dict[str, object]:
    components: dict[str, object] = {}
    for column in ("yN", "yF", "yT", "irc1_no_chla", "risk_chla_current"):
        value = _float_or_none(row.get(column))
        if value is not None:
            components[column] = value
    for column in (
        "state_trophic_expert",
        "nutrient_pressure_label",
        "physicochemical_condition_label",
        "thermal_biological_label",
    ):
        value = row.get(column)
        if value not in {None, ""}:
            components[column] = str(value)
    return components


def _manifest_threshold(manifest: dict[str, object]) -> float:
    threshold = _float_or_none(manifest.get("alert_threshold"))
    if threshold is None:
        threshold = _float_or_none(manifest.get("threshold"))
    if threshold is None or threshold < 0.0 or threshold > 1.0:
        raise RunPredictionError(
            ErrorCode.pipeline_execution_failed,
            "Fuzzy manifest contains an invalid alert threshold.",
            details={"artifact": _FUZZY_STATE_MANIFEST},
            http_status=500,
        )
    return threshold


def _severity(score: float, threshold: float) -> AlertSeverity:
    if score >= threshold:
        return "alert"
    if score >= max(0.0, threshold * 0.66):
        return "watch"
    return "low"


def _float_or_none(value: object) -> float | None:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None
