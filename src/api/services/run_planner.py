"""Synchronous dry-run planner for registered dataset workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from src.api.errors import ErrorCode, WarningCode
from src.api.schemas.dataset import (
    DatasetRegistrationResponse,
    ValidationIssue,
    WorkflowName,
)
from src.api.schemas.run import (
    RunPlanArtifact,
    RunPlanRequest,
    RunPlanResponse,
    RunPlanStatus,
    RunPlanStep,
)
from src.api.services.dataset_repository import read_registered_dataset
from src.api.services.dataset_validation import workflow_eligibility_for_summary


@dataclass(frozen=True)
class ArtifactSpec:
    """Static artifact dependency or planned output."""

    name: str
    role: str
    uri: str | None
    required: bool = True
    reason: str | None = None


_COMMON_DEPENDENCIES = (
    ArtifactSpec("variable_config", "dependency", "configs/variables.yaml"),
)

_WORKFLOW_DEPENDENCIES: dict[str, tuple[ArtifactSpec, ...]] = {
    "canonical_observations": _COMMON_DEPENDENCIES,
    "monthly_panel": _COMMON_DEPENDENCIES,
    "fuzzy_state": _COMMON_DEPENDENCIES
    + (
        ArtifactSpec(
            "expert_fuzzy_manifest",
            "dependency",
            "reports/anfis/fuzzy_manifest.json",
        ),
    ),
    "pipe_grud": _COMMON_DEPENDENCIES
    + (
        ArtifactSpec(
            "pipe_grud_model",
            "dependency",
            "models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt",
        ),
        ArtifactSpec(
            "pipe_grud_rollout_calibrators",
            "dependency",
            "models/pipe_grud/adaptive_wqp_focused/rollout_calibrators",
        ),
        ArtifactSpec(
            "pipe_grud_alert_policy",
            "dependency",
            "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_thresholds.csv",
        ),
    ),
    "pipe_neural_ode": _COMMON_DEPENDENCIES
    + (
        ArtifactSpec(
            "pipe_neural_ode_history_model",
            "dependency",
            "models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_model_v1.pt",
        ),
        ArtifactSpec(
            "pipe_neural_ode_rollout_calibrators",
            "dependency",
            "models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators",
        ),
        ArtifactSpec(
            "pipe_neural_ode_alert_policy",
            "dependency",
            "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_thresholds.csv",
        ),
    ),
    "mifal_ed_t2": _COMMON_DEPENDENCIES
    + (
        ArtifactSpec(
            "mifal_observable_calibrators",
            "dependency",
            "models/mifal/observable_calibrators/current_chla_pipe_grud_validation",
        ),
    ),
    "counterfactual_planning": _COMMON_DEPENDENCIES
    + (
        ArtifactSpec(
            "counterfactual_planning_config",
            "dependency",
            "configs/counterfactual_planning_v1.yaml",
        ),
        ArtifactSpec(
            "upstream_temporal_alert_surface",
            "dependency",
            None,
            reason=(
                "Counterfactual planning requires a completed temporal state/alert "
                "workflow output for this registered dataset."
            ),
        ),
    ),
}

_WORKFLOW_OUTPUTS: dict[str, tuple[str, ...]] = {
    "canonical_observations": (
        "canonical_observations.jsonl",
        "canonical_observations.csv",
        "execution_manifest.json",
    ),
    "monthly_panel": (
        "canonical_observations.jsonl",
        "canonical_observations.csv",
        "monthly_panel.csv",
        "execution_manifest.json",
    ),
    "fuzzy_state": (
        "canonical_observations.jsonl",
        "canonical_observations.csv",
        "monthly_panel.csv",
        "monthly_panel_wide.csv",
        "fuzzy_state_scores.csv",
        "fuzzy_state_trace.csv",
        "fuzzy_state_manifest.json",
        "execution_manifest.json",
    ),
    "pipe_grud": (
        "pipe_monthly_panel.csv",
        "pipe_monthly_panel_wide.csv",
        "pipe_state_surface.csv",
        "pipe_state_surface.parquet",
        "pipe_sequences.csv",
        "pipe_sequences.parquet",
        "pipe_inference_origins.csv",
        "pipe_inference_origins.parquet",
        "pipe_sequence_summary.csv",
        "pipe_sequence_discarded_summary.csv",
        "pipe_sequence_build_report.md",
        "pipe_sequence_build_manifest.json",
        "pipe_adaptive_features.csv",
        "pipe_adaptive_state_surface.csv",
        "pipe_adaptive_state_surface.parquet",
        "pipe_adaptive_sequence_state.csv",
        "pipe_adaptive_sequence_state.parquet",
        "pipe_adaptive_module_coverage.csv",
        "pipe_adaptive_surface_report.md",
        "pipe_adaptive_surface_manifest.json",
        "pipe_grud_external_rollouts.csv",
        "pipe_grud_external_rollouts.parquet",
        "pipe_grud_external_rollout_summary.csv",
        "pipe_grud_external_top_alerts.csv",
        "pipe_grud_external_recent_top_alerts.csv",
        "pipe_grud_external_inference_report.md",
        "pipe_grud_external_inference_manifest.json",
        "pipe_grud_reference_rollouts.csv",
        "pipe_grud_reference_rollouts.parquet",
        "pipe_grud_reference_rollout_summary.csv",
        "pipe_grud_reference_policy_summary.csv",
        "pipe_grud_reference_alerts.csv",
        "pipe_grud_reference_alerts.parquet",
        "pipe_grud_reference_top_alerts.csv",
        "pipe_grud_reference_recent_top_alerts.csv",
        "pipe_grud_reference_inference_report.md",
        "pipe_grud_reference_inference_manifest.json",
        "pipe_grud_rollout_rows.parquet",
        "pipe_grud_alerts.parquet",
        "pipe_grud_run_report.md",
        "pipe_grud_run_manifest.json",
    ),
    "pipe_neural_ode": (
        "canonical_observations.parquet",
        "monthly_panel.parquet",
        "state_history_windows.parquet",
        "pipe_neural_ode_rollout_rows.parquet",
        "pipe_neural_ode_alerts.parquet",
        "pipe_neural_ode_run_report.md",
        "pipe_neural_ode_run_manifest.json",
    ),
    "mifal_ed_t2": (
        "canonical_observations.parquet",
        "monthly_panel.parquet",
        "mifal_observable_surface.csv",
        "mifal_observable_surface.parquet",
        "mifal_scores.csv",
        "mifal_scores.parquet",
        "mifal_alerts.csv",
        "mifal_alerts.parquet",
        "mifal_run_report.md",
        "mifal_run_manifest.json",
    ),
    "counterfactual_planning": (
        "counterfactual_metrics.csv",
        "counterfactual_summary.csv",
        "counterfactual_pareto.csv",
        "counterfactual_examples.csv",
        "counterfactual_report.md",
        "counterfactual_manifest.json",
    ),
}

_WORKFLOW_STEPS: dict[str, tuple[tuple[str, str], ...]] = {
    "canonical_observations": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("canonicalize", "Convert supported observations into canonical long-form observations"),
        ("write_manifest", "Write canonical observations manifest"),
    ),
    "monthly_panel": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("canonicalize", "Convert supported observations into canonical long-form observations"),
        ("build_panel", "Aggregate canonical observations into source/site/month panel rows"),
        ("write_manifest", "Write monthly panel manifest"),
    ),
    "fuzzy_state": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("canonicalize", "Convert supported observations into canonical long-form observations"),
        ("build_panel", "Aggregate canonical observations into source/site/month panel rows"),
        ("score_fuzzy_state", "Compute supported fuzzy ecological state modules"),
        ("write_manifest", "Write fuzzy state manifest"),
    ),
    "pipe_grud": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("build_panel", "Build canonical monthly panel and PIPE-compatible sequence surface"),
        ("run_rollout", "Run PIPE-GRU-D rollout against available model artifacts"),
        ("apply_alert_policy", "Apply calibrated rollout alert policy"),
        ("write_report", "Write run report and reproducibility manifest"),
    ),
    "pipe_neural_ode": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("build_history", "Build canonical panel and historical state windows"),
        ("run_rollout", "Run Neural ODE rollout against available model artifacts"),
        ("apply_alert_policy", "Apply calibrated rollout alert policy"),
        ("write_report", "Write run report and reproducibility manifest"),
    ),
    "mifal_ed_t2": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("build_observable_surface", "Build observable-minimal ecological surface"),
        ("run_mifal", "Run MIFAL-ED/T2 comparator workflow"),
        ("write_report", "Write run report and reproducibility manifest"),
    ),
    "counterfactual_planning": (
        ("load_dataset", "Load registered dataset payload and validation manifest"),
        ("load_upstream_surface", "Load completed temporal state/alert output for the dataset"),
        ("simulate_scenarios", "Evaluate configured counterfactual intervention scenarios"),
        ("select_pareto", "Summarize Pareto policies and scenario diagnostics"),
        ("write_report", "Write planning report and reproducibility manifest"),
    ),
}


def plan_run_request(request: RunPlanRequest) -> RunPlanResponse:
    """Build a deterministic dry-run plan for a registered dataset workflow."""

    dataset = read_registered_dataset(request.dataset_id)
    plan_id = _plan_id(dataset, request)
    blockers = _validation_blockers(dataset)
    warnings = list(dataset.validation.warnings)
    eligibility = workflow_eligibility_for_summary(dataset.validation.summary, request.workflow)

    if not blockers and eligibility and not eligibility[0].eligible:
        blockers.append(
            ValidationIssue(
                code=ErrorCode.unsupported_pipeline_for_dataset.value,
                message=eligibility[0].reason or "Dataset is not eligible for the requested workflow.",
                field="workflow",
                details={"workflow": request.workflow, "dataset_id": request.dataset_id},
            )
        )

    artifacts = _input_artifacts(dataset)
    dependency_artifacts, missing_dependencies = _dependency_artifacts(request.workflow)
    artifacts.extend(dependency_artifacts)
    artifacts.extend(_output_artifacts(request.workflow, plan_id))

    if missing_dependencies:
        blockers.append(
            ValidationIssue(
                code=ErrorCode.upstream_artifact_missing.value,
                message="One or more required workflow dependencies are missing.",
                field="workflow",
                details={"artifacts": missing_dependencies},
            )
        )

    if request.workflow == "counterfactual_planning":
        warnings.append(
            ValidationIssue(
                code=WarningCode.counterfactual_not_causal.value,
                message="Counterfactual planning output is model-simulated, not causal field evidence.",
                field="workflow",
                details={"workflow": request.workflow},
            )
        )

    status = _status(blockers)
    return RunPlanResponse(
        plan_id=plan_id,
        dataset_id=request.dataset_id,
        workflow=request.workflow,
        status=status,
        executable=status == "ready",
        created_at=_now_utc(),
        validation_outcome=dataset.validation.outcome,
        parameters=request.parameters,
        blockers=blockers,
        warnings=warnings,
        required_artifacts=artifacts,
        steps=_steps(request.workflow, status),
    )


def _validation_blockers(dataset: DatasetRegistrationResponse) -> list[ValidationIssue]:
    if not dataset.validation.errors:
        return []
    return list(dataset.validation.errors)


def _status(blockers: list[ValidationIssue]) -> RunPlanStatus:
    if not blockers:
        return "ready"
    if all(item.code == ErrorCode.unsupported_pipeline_for_dataset.value for item in blockers):
        return "not_eligible"
    return "blocked"


def _input_artifacts(dataset: DatasetRegistrationResponse) -> list[RunPlanArtifact]:
    return [
        RunPlanArtifact(
            name=artifact.name,
            role="input",
            uri=artifact.uri,
            required=True,
            availability="available",
        )
        for artifact in dataset.artifacts
    ]


def _dependency_artifacts(workflow: WorkflowName) -> tuple[list[RunPlanArtifact], list[str]]:
    artifacts: list[RunPlanArtifact] = []
    missing: list[str] = []
    for spec in _WORKFLOW_DEPENDENCIES.get(workflow, ()):
        available = _artifact_available(spec.uri)
        availability = "available" if available else "missing"
        reason = spec.reason
        if not available:
            missing.append(spec.name)
            reason = reason or "Required local workflow dependency is not available."
        artifacts.append(
            RunPlanArtifact(
                name=spec.name,
                role=spec.role,
                uri=spec.uri,
                required=spec.required,
                availability=availability,
                reason=reason,
            )
        )
    return artifacts, missing


def _output_artifacts(workflow: WorkflowName, plan_id: str) -> list[RunPlanArtifact]:
    return [
        RunPlanArtifact(
            name=filename,
            role="output",
            uri=f"runs/{plan_id}/{filename}",
            required=False,
            availability="generated",
            reason="Planned output; not created by dry-run planning.",
        )
        for filename in _WORKFLOW_OUTPUTS.get(workflow, ())
    ]


def _steps(workflow: WorkflowName, status: RunPlanStatus) -> list[RunPlanStep]:
    steps: list[RunPlanStep] = []
    for index, (step_id, name) in enumerate(_WORKFLOW_STEPS.get(workflow, ())):
        if index == 0:
            step_status = "available"
        elif status == "ready":
            step_status = "planned"
        else:
            step_status = "blocked"
        steps.append(
            RunPlanStep(
                step_id=step_id,
                name=name,
                status=step_status,
                notes=["Dry-run only; this endpoint does not execute the step."],
            )
        )
    return steps


def _artifact_available(uri: str | None) -> bool:
    if uri is None:
        return False
    path = Path(uri)
    return path.exists() or Path(f"{uri}.dvc").exists()


def _plan_id(dataset: DatasetRegistrationResponse, request: RunPlanRequest) -> str:
    payload = {
        "dataset_id": request.dataset_id,
        "dataset_sha256": dataset.content_sha256,
        "workflow": request.workflow,
        "parameters": request.parameters,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"plan_{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
