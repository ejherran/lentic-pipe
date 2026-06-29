"""Run-scoped prediction and alert views over generated API artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any, cast

from src.api.errors import ErrorCode
from src.api.schemas.dataset import WorkflowName
from src.api.schemas.prediction import (
    AlertSeverity,
    PredictionScoreKind,
    RunAlertRecord,
    RunAlertResponse,
    RunPredictionRecord,
    RunPredictionResponse,
)
from src.api.services.run_repository import read_run_execution, run_plan_dir

_FUZZY_STATE_SCORES = "fuzzy_state_scores.csv"
_FUZZY_STATE_MANIFEST = "fuzzy_state_manifest.json"
_FUZZY_ROOT_MANIFEST = Path("reports/anfis/fuzzy_manifest.json")
_PIPE_GRUD_REFERENCE_ROLLOUTS = "pipe_grud_reference_rollouts.csv"
_PIPE_GRUD_REFERENCE_ALERTS = "pipe_grud_reference_alerts.csv"
_PIPE_GRUD_REFERENCE_MANIFEST = "pipe_grud_reference_inference_manifest.json"
_MIFAL_SCORES = "mifal_scores.csv"
_MIFAL_ALERTS = "mifal_alerts.csv"
_MIFAL_MANIFEST = "mifal_run_manifest.json"
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
_PIPE_GRUD_REFERENCE_PREDICTION_LIMITS = [
    "These records are model-derived temporal rollout indicators from the adaptive PIPE-GRU-D reference profile.",
    "Predictive skill and field transferability are not guaranteed for a new water body.",
    "The 2B alert policy is a selected operating profile, not causal field evidence.",
]
_PIPE_GRUD_REFERENCE_ALERT_LIMITS = [
    "These alerts are thresholded model-derived early-warning indicators, not official public advisories.",
    "Thresholds are horizon- and event-specific; the per-record threshold is authoritative.",
    "Predictive skill and field transferability are not guaranteed for a new water body.",
]
_MIFAL_PREDICTION_LIMITS = [
    "These records are deterministic MIFAL-ED/T2 eco-fuzzy bloom-risk indicators.",
    "Calibrated bloom probabilities depend on validation-derived calibrators; transferability is not guaranteed.",
    "MIFAL emits bloom_h comparator scores and does not emit irc_alert.",
]
_MIFAL_ALERT_LIMITS = [
    "These alerts are thresholded MIFAL-ED/T2 bloom_h indicators, not official public advisories.",
    "Thresholds are horizon-specific and validation-calibrated; inspect the run manifest for calibration coverage.",
    "The alert policy is model-derived comparison, not causal field evidence.",
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
    if (run_dir / _PIPE_GRUD_REFERENCE_ROLLOUTS).exists():
        rows = _read_csv_rows(run_dir / _PIPE_GRUD_REFERENCE_ROLLOUTS)
        manifest = _read_pipe_grud_reference_manifest(run_dir)
        records = _reference_prediction_records(rows, execution.workflow, manifest)[:limit]
        return RunPredictionResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            status="available",
            prediction_surface="pipe_grud_adaptive_reference_rollout",
            predictions=records,
            interpretation_limits=_PIPE_GRUD_REFERENCE_PREDICTION_LIMITS,
        )
    if (run_dir / _MIFAL_SCORES).exists():
        rows = _read_csv_rows(run_dir / _MIFAL_SCORES)
        manifest = _read_mifal_manifest(run_dir)
        records = _mifal_prediction_records(rows, execution.workflow, manifest)[:limit]
        return RunPredictionResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            status="available",
            prediction_surface="mifal_ed_t2_observable_bloom_risk",
            predictions=records,
            interpretation_limits=_MIFAL_PREDICTION_LIMITS,
        )
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
    if (run_dir / _PIPE_GRUD_REFERENCE_ALERTS).exists():
        rows = _read_csv_rows(run_dir / _PIPE_GRUD_REFERENCE_ALERTS)
        manifest = _read_pipe_grud_reference_manifest(run_dir)
        records = [
            record
            for record in (_reference_alert_record(row, execution.workflow) for row in rows)
            if record is not None
        ]
        records = sorted(records, key=lambda record: (-int(record.is_alert), -record.score, record.rank))
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
            alert_surface="pipe_grud_adaptive_reference_policy_2b",
            policy_version=str(manifest.get("policy_name", "closest_pr")),
            threshold=_first_threshold(ranked_records),
            alerts=ranked_records,
            interpretation_limits=_PIPE_GRUD_REFERENCE_ALERT_LIMITS,
        )
    if (run_dir / _MIFAL_ALERTS).exists():
        rows = _read_csv_rows(run_dir / _MIFAL_ALERTS)
        manifest = _read_mifal_manifest(run_dir)
        records = [
            record
            for record in (_mifal_alert_record(row, execution.workflow) for row in rows)
            if record is not None
        ]
        records = sorted(records, key=lambda record: (-int(record.is_alert), -record.score, record.rank))
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
            alert_surface="mifal_ed_t2_observable_bloom_policy",
            policy_version=str(manifest.get("policy_version", "")) or _mifal_manifest_policy(manifest),
            threshold=_first_threshold(ranked_records),
            alerts=ranked_records,
            interpretation_limits=_MIFAL_ALERT_LIMITS,
        )
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
                "supported_workflows": ["fuzzy_state", "pipe_grud", "mifal_ed_t2"],
            },
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
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


def _read_pipe_grud_reference_manifest(run_dir: Path) -> dict[str, object]:
    path = run_dir / _PIPE_GRUD_REFERENCE_MANIFEST
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raise RunPredictionError(
        ErrorCode.dependency_not_ready,
        "PIPE-GRU-D reference inference manifest is required to interpret prediction and alert surfaces.",
        details={"required_artifact": _PIPE_GRUD_REFERENCE_MANIFEST},
        http_status=424,
    )


def _read_mifal_manifest(run_dir: Path) -> dict[str, object]:
    path = run_dir / _MIFAL_MANIFEST
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raise RunPredictionError(
        ErrorCode.dependency_not_ready,
        "MIFAL run manifest is required to interpret prediction and alert surfaces.",
        details={"required_artifact": _MIFAL_MANIFEST},
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


def _reference_prediction_records(
    rows: list[dict[str, str]],
    workflow: WorkflowName,
    manifest: dict[str, object],
) -> list[RunPredictionRecord]:
    records: list[RunPredictionRecord] = []
    model_family = str(manifest.get("inference_version", "external_pipe_grud_reference_profile_inference_v0"))
    for row in rows:
        horizon = _int_or_none(row.get("rollout_horizon_months"))
        if horizon is None:
            continue
        irc_score = _float_or_none(row.get("alert_probability_irc"))
        if irc_score is not None:
            records.append(
                RunPredictionRecord(
                    source_id=str(row.get("source_id", "")),
                    site_id=str(row.get("site_id", "")),
                    year_month=str(row.get("forecast_year_month", "")),
                    horizon_months=horizon,
                    target="irc_alert",
                    score_name="alert_probability_irc",
                    score=irc_score,
                    score_kind="model_probability",
                    model_family=model_family,
                    workflow=workflow,
                    components=_reference_prediction_components(row),
                    interpretation="PIPE-GRU-D rollout probability of crossing the IRC alert threshold.",
                )
            )
        bloom_score = _float_or_none(row.get("rollout_probability_bloom_calibrated"))
        if bloom_score is not None:
            records.append(
                RunPredictionRecord(
                    source_id=str(row.get("source_id", "")),
                    site_id=str(row.get("site_id", "")),
                    year_month=str(row.get("forecast_year_month", "")),
                    horizon_months=horizon,
                    target="bloom_h",
                    score_name="rollout_probability_bloom_calibrated",
                    score=bloom_score,
                    score_kind="calibrated_probability",
                    model_family=model_family,
                    workflow=workflow,
                    components=_reference_prediction_components(row),
                    interpretation="Rollout-calibrated bloom probability from the adaptive PIPE-GRU-D reference profile.",
                )
            )
    return records


def _mifal_prediction_records(
    rows: list[dict[str, str]],
    workflow: WorkflowName,
    manifest: dict[str, object],
) -> list[RunPredictionRecord]:
    records: list[RunPredictionRecord] = []
    model_family = str(manifest.get("mifal_observable_version", "external_mifal_observable_api_v0"))
    for row in rows:
        horizon = _int_or_none(row.get("horizon_months"))
        if horizon is None:
            continue
        calibrated = _float_or_none(row.get("mifal_probability_bloom_calibrated"))
        conservative = _float_or_none(row.get("risk_conservative"))
        if calibrated is None and conservative is None:
            continue
        score = calibrated if calibrated is not None else conservative
        if score is None:
            continue
        score_name = "mifal_probability_bloom_calibrated" if calibrated is not None else "risk_conservative"
        score_kind: PredictionScoreKind = "calibrated_probability" if calibrated is not None else "expert_score"
        records.append(
            RunPredictionRecord(
                source_id=str(row.get("source_id", "")),
                site_id=str(row.get("site_id", "")),
                year_month=str(row.get("forecast_year_month", "")),
                horizon_months=horizon,
                target="bloom_h",
                score_name=score_name,
                score=score,
                score_kind=score_kind,
                model_family=model_family,
                workflow=workflow,
                components=_mifal_prediction_components(row),
                interpretation="MIFAL-ED/T2 observable bloom-risk indicator.",
            )
        )
    return records


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


def _mifal_alert_record(
    row: dict[str, str],
    workflow: WorkflowName,
) -> RunAlertRecord | None:
    score = _float_or_none(row.get("score"))
    threshold = _float_or_none(row.get("threshold"))
    horizon = _int_or_none(row.get("horizon_months"))
    if score is None or threshold is None or horizon is None:
        return None
    rank = _int_or_none(row.get("rank")) or 1
    return RunAlertRecord(
        source_id=str(row.get("source_id", "")),
        site_id=str(row.get("site_id", "")),
        year_month=str(row.get("forecast_year_month", "")),
        horizon_months=horizon,
        target_event=str(row.get("target_event", "")) or "bloom_h",
        score_name=str(row.get("score_name", "")) or "mifal_probability_bloom_calibrated",
        score=score,
        threshold=threshold,
        is_alert=_boolish(row.get("is_alert")),
        severity=cast(AlertSeverity, row.get("severity") or _severity(score, threshold)),
        rank=rank,
        policy_version=str(row.get("policy_version", "")),
        workflow=workflow,
        interpretation=str(row.get("interpretation", "MIFAL-ED/T2 bloom alert.")),
    )


def _reference_alert_record(
    row: dict[str, str],
    workflow: WorkflowName,
) -> RunAlertRecord | None:
    score = _float_or_none(row.get("score"))
    threshold = _float_or_none(row.get("threshold"))
    horizon = _int_or_none(row.get("rollout_horizon_months"))
    if score is None or threshold is None or horizon is None:
        return None
    rank = _int_or_none(row.get("rank")) or 1
    return RunAlertRecord(
        source_id=str(row.get("source_id", "")),
        site_id=str(row.get("site_id", "")),
        year_month=str(row.get("forecast_year_month", "")),
        horizon_months=horizon,
        target_event=str(row.get("target_event", "")),
        score_name=str(row.get("score_name", "")),
        score=score,
        threshold=threshold,
        is_alert=_boolish(row.get("is_alert")),
        severity=cast(AlertSeverity, row.get("severity") or _severity(score, threshold)),
        rank=rank,
        policy_version=str(row.get("policy_name", "")) or str(row.get("policy_version", "")),
        workflow=workflow,
        interpretation=str(row.get("interpretation", "PIPE-GRU-D reference profile alert.")),
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


def _reference_prediction_components(row: dict[str, str]) -> dict[str, object]:
    components: dict[str, object] = {}
    for column in (
        "origin_year_month",
        "origin_irc1_rollout_basis",
        "irc_mean",
        "irc_p05",
        "irc_p50",
        "irc_p95",
        "rollout_alert_probability_threshold_h",
        "rollout_bloom_probability_threshold_h",
        "probability_bloom_mean",
    ):
        value = _float_or_none(row.get(column))
        if value is not None:
            components[column] = value
        elif row.get(column) not in {None, ""}:
            components[column] = str(row[column])
    for column in (
        "rollout_predicted_irc_alert_h",
        "rollout_predicted_bloom_h",
        "reference_any_alert_h",
        "deterministic",
    ):
        if row.get(column) not in {None, ""}:
            components[column] = _boolish(row.get(column))
    return components


def _mifal_prediction_components(row: dict[str, str]) -> dict[str, object]:
    components: dict[str, object] = {}
    for column in (
        "origin_year_month",
        "surface",
        "alert_class",
        "dominant_factors",
        "recommended_sampling",
    ):
        if row.get(column) not in {None, ""}:
            components[column] = str(row[column])
    for column in (
        "risk_conservative",
        "risk_interval_low",
        "risk_interval_high",
        "uncertainty",
        "interval_confidence",
        "data_reliability",
        "confidence",
        "observation_reliability",
        "mifal_bloom_probability_threshold",
        "index_growth",
        "index_nutrients",
        "index_light",
        "index_stability",
        "index_disturbance",
        "index_memory",
    ):
        value = _float_or_none(row.get(column))
        if value is not None:
            components[column] = value
    for column in (
        "has_Tw",
        "has_TP",
        "has_TN",
        "has_Secchi",
        "has_Turb",
        "has_DOb",
        "has_Chl",
        "has_Chl_prev",
        "mifal_predicted_bloom_h",
    ):
        if row.get(column) not in {None, ""}:
            components[column] = _boolish(row.get(column))
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


def _first_threshold(records: list[RunAlertRecord]) -> float:
    if records:
        return records[0].threshold
    return 0.0


def _mifal_manifest_policy(manifest: dict[str, object]) -> str:
    calibration = manifest.get("calibration", {})
    if not isinstance(calibration, dict):
        return "mifal_observable_alert_calibration_v0"
    calibration_map = cast(Mapping[str, object], calibration)
    thresholds = calibration_map.get("thresholds", [])
    if isinstance(thresholds, list):
        for threshold in thresholds:
            if isinstance(threshold, Mapping):
                threshold_map = cast(Mapping[str, object], threshold)
                if not threshold_map.get("available"):
                    continue
                split = str(threshold_map.get("calibration_split", "validation"))
                objective = str(threshold_map.get("selection_objective", "threshold"))
                return f"mifal_observable_alert_calibration_v0:{split}:{objective}"
    return "mifal_observable_alert_calibration_v0"


def _float_or_none(value: object) -> float | None:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(float(cast(Any, value)))
    except (TypeError, ValueError):
        return None


def _boolish(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}
