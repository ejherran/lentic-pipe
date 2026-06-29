"""Job-backed scientific workflow adapter registry."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol, cast, get_args

from src.api.config import api_workspace
from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetValidationRequest, WorkflowName
from src.api.schemas.run import (
    RunExecutionResponse,
    RunPlanArtifact,
    RunPlanRequest,
    RunPlanResponse,
    RunResultSummaryResponse,
)
from src.api.services.run_artifacts import summarize_run_results
from src.api.services.run_executor import execute_run_plan
from src.api.services.pipe_grud_external_adaptive_surface import (
    adaptive_surface_artifacts_available,
    run_external_pipe_adaptive_surface_build,
)
from src.api.services.pipe_grud_external_inference import run_external_pipe_grud_expert_surface_inference
from src.api.services.pipe_grud_external_reference_inference import (
    reference_inference_artifacts_available,
    run_external_pipe_grud_reference_profile_inference,
)
from src.api.services.pipe_neural_ode_external_reference_inference import (
    neural_ode_reference_inference_artifacts_available,
    run_external_pipe_neural_ode_reference_profile_inference,
)
from src.api.services.pipe_grud_external_sequences import build_external_pipe_sequence_artifacts
from src.api.services.mifal_external import (
    mifal_reference_artifacts_available,
    run_external_mifal_observable,
)
from src.api.services.counterfactual_planning_external import run_external_counterfactual_planning_v1
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import (
    RunExecutionNotFoundError,
    read_run_execution,
    run_plan_dir,
    save_run_execution,
    save_run_plan,
)
from src.api.services.dataset_repository import read_dataset_request
from src.api.services.dataset_validation import parse_observed_year_month
from src.mifal.panel_adapter import (
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA,
    validate_surface,
)

ADAPTER_INTERFACE_VERSION = "job_adapter_interface_v1"
_KNOWN_WORKFLOWS = frozenset(str(name) for name in get_args(WorkflowName))
_PIPE_GRUD_REFERENCE_PROFILE = "adaptive_wqp_focused"
_PIPE_GRUD_EXECUTION_MODES = frozenset(
    {
        "preflight",
        "build_sequences",
        "build_adaptive_surface",
        "infer_expert_surface",
        "infer_reference_profile",
        "artifact_reference",
    }
)
_PIPE_GRUD_SIGNAL_VARIABLES = frozenset({"chlorophyll_a_ugL", "TP_ugL", "TN_ugL"})
_PIPE_GRUD_REQUIRED_HISTORY_MONTHS = 12
_PIPE_GRUD_REFERENCE_ARTIFACTS = {
    "model": Path("models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt"),
    "model_manifest": Path("reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest.json"),
    "sequence_manifest": Path("reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json"),
    "rollout_validation_manifest": Path(
        "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_validation.json"
    ),
    "rollout_test_manifest": Path(
        "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_test.json"
    ),
    "calibration_manifest": Path(
        "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_manifest.json"
    ),
    "policy_manifest": Path(
        "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_manifest.json"
    ),
    "policy_thresholds": Path(
        "reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_thresholds.csv"
    ),
    "rollout_calibrators": Path("models/pipe_grud/adaptive_wqp_focused/rollout_calibrators"),
}
_NEURAL_ODE_REFERENCE_PROFILE = "adaptive_wqp_focused_history_v1_long80"
_NEURAL_ODE_EXECUTION_MODES = frozenset({"preflight", "infer_reference_profile", "artifact_reference"})
_NEURAL_ODE_SIGNAL_VARIABLES = frozenset({"chlorophyll_a_ugL", "TP_ugL", "TN_ugL"})
_NEURAL_ODE_REQUIRED_HISTORY_MONTHS = 12
_NEURAL_ODE_REFERENCE_ARTIFACTS = {
    "model": Path(
        "models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_model_v1.pt"
    ),
    "checkpoint": Path(
        "models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_checkpoint_v1.pt"
    ),
    "model_manifest": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_manifest.json"
    ),
    "rollout_validation_manifest": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_validation.json"
    ),
    "rollout_test_manifest": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_test.json"
    ),
    "calibration_manifest": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_manifest.json"
    ),
    "policy_manifest": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_manifest.json"
    ),
    "policy_thresholds": Path(
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_thresholds.csv"
    ),
    "rollout_calibrators": Path(
        "models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators"
    ),
}
_MIFAL_EXECUTION_MODES = frozenset({"preflight", "run_observable", "artifact_reference"})
_PLANNING_EXECUTION_MODES = frozenset({"preflight", "run_scenarios", "artifact_reference"})
_PLANNING_REFERENCE_ARTIFACTS = {
    "config": Path("configs/counterfactual_planning_v1.yaml"),
    "validation_report": Path("reports/planning/counterfactual_raw_proxy_v1_validation_report.md"),
    "validation_manifest": Path("reports/planning/counterfactual_raw_proxy_v1_validation_manifest.json"),
    "validation_metrics": Path("reports/planning/counterfactual_raw_proxy_v1_validation_metrics.csv"),
    "validation_summary": Path("reports/planning/counterfactual_raw_proxy_v1_validation_summary.csv"),
    "validation_pareto": Path("reports/planning/counterfactual_raw_proxy_v1_validation_pareto.csv"),
    "validation_crisis_report": Path(
        "reports/planning/counterfactual_raw_proxy_v1_validation_crisis_report.md"
    ),
    "validation_crisis_manifest": Path(
        "reports/planning/counterfactual_raw_proxy_v1_validation_crisis_manifest.json"
    ),
}
_TEMPORAL_ALERT_ARTIFACTS = frozenset(
    {
        "pipe_grud_reference_alerts.csv",
        "pipe_grud_reference_alerts.parquet",
        "pipe_grud_reference_rollouts.csv",
        "pipe_grud_reference_rollouts.parquet",
        "pipe_neural_ode_reference_alerts.csv",
        "pipe_neural_ode_reference_alerts.parquet",
        "pipe_neural_ode_reference_rollouts.csv",
        "pipe_neural_ode_reference_rollouts.parquet",
        "pipe_neural_ode_alerts.parquet",
        "mifal_alerts.csv",
        "mifal_alerts.parquet",
    }
)


class ScientificWorkflowAdapterError(ValueError):
    """Expected scientific adapter failure with an actionable message."""


class UnsupportedScientificWorkflowError(ScientificWorkflowAdapterError):
    """Raised when no job-backed adapter is registered for a workflow."""


@dataclass(frozen=True)
class ScientificWorkflowJob:
    """Resolved workflow request ready for job-backed execution."""

    model_type: ModelType
    dataset_id: str
    workflow: WorkflowName
    parameters: dict[str, Any]
    config: dict[str, Any]


@dataclass(frozen=True)
class ScientificWorkflowExecutionBundle:
    """Execution bundle produced by a scientific workflow adapter."""

    plan: RunPlanResponse
    execution: RunExecutionResponse
    summary: RunResultSummaryResponse


class ScientificWorkflowAdapter(Protocol):
    """Interface every job-backed scientific workflow adapter must implement."""

    adapter_id: str
    interface_version: str
    supported_workflows: frozenset[str]

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        """Validate adapter-local preconditions before building a plan."""

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        """Build and persist the workflow plan."""

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        """Execute the workflow and persist execution artifacts."""

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        """Collect lightweight summaries after execution."""

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        """Run the full adapter lifecycle."""


class LocalDeterministicWorkflowAdapter:
    """Adapter for the safe deterministic workflows already reviewed for the API."""

    adapter_id = "local_scientific_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"canonical_observations", "monthly_panel", "fuzzy_state"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        plan_request = RunPlanRequest(
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            parameters=job.parameters,
        )
        plan = save_run_plan(plan_run_request(plan_request))
        if not plan.executable:
            blocker_messages = [issue.message for issue in plan.blockers]
            raise ScientificWorkflowAdapterError(
                "Scientific workflow is not executable for this dataset: "
                + "; ".join(blocker_messages)
            )
        return plan

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        return execute_run_plan(plan.plan_id)

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        return summarize_run_results(plan.plan_id)

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        self.validate_preconditions(job)
        plan = self.build_plan(job)
        execution = self.execute(job, plan)
        summary = self.collect_artifacts(job, plan, execution)
        return ScientificWorkflowExecutionBundle(plan=plan, execution=execution, summary=summary)


class PipeGrudReferenceWorkflowAdapter:
    """PIPE-GRU-D adapter with external-data preflight and reviewed artifact reference mode."""

    adapter_id = "pipe_grud_reference_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"pipe_grud"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )
        execution_mode = _pipe_grud_execution_mode(job)
        if execution_mode not in _PIPE_GRUD_EXECUTION_MODES:
            raise ScientificWorkflowAdapterError(
                "PIPE-GRU-D adapter v0 requires parameters.execution_mode='preflight' for "
                "external dataset diagnostics, parameters.execution_mode='build_sequences' "
                "for external expert PIPE state/sequence artifacts, "
                "parameters.execution_mode='build_adaptive_surface' for adaptive ANFIS "
                "state/sequence artifacts, "
                "parameters.execution_mode='infer_expert_surface' for explicit diagnostic "
                "expert-surface rollouts, parameters.execution_mode='infer_reference_profile' "
                "for calibrated adaptive reference-profile inference, or "
                "parameters.execution_mode='artifact_reference' "
                "to validate the reviewed adaptive reference profile."
            )
        if execution_mode in {"preflight", "build_sequences"}:
            return
        if execution_mode == "build_adaptive_surface":
            available, missing = adaptive_surface_artifacts_available()
            if not available:
                raise ScientificWorkflowAdapterError(
                    "Adaptive ANFIS artifacts are not available for external adaptive surface build: "
                    + ", ".join(sorted(missing))
                )
            return
        if execution_mode == "infer_expert_surface":
            missing = [
                name
                for name, path in {
                    "model": _PIPE_GRUD_REFERENCE_ARTIFACTS["model"],
                    "model_manifest": _PIPE_GRUD_REFERENCE_ARTIFACTS["model_manifest"],
                }.items()
                if not path.exists()
            ]
            if missing:
                raise ScientificWorkflowAdapterError(
                    "PIPE-GRU-D model artifacts are not available for expert-surface inference: "
                    + ", ".join(sorted(missing))
                )
            return
        if execution_mode == "infer_reference_profile":
            available, missing = reference_inference_artifacts_available()
            if not available:
                raise ScientificWorkflowAdapterError(
                    "PIPE-GRU-D reference inference artifacts are not available: "
                    + ", ".join(sorted(missing))
                )
            return
        missing = [
            name for name, path in _PIPE_GRUD_REFERENCE_ARTIFACTS.items() if not _artifact_available(path)
        ]
        if missing:
            raise ScientificWorkflowAdapterError(
                "PIPE-GRU-D reference artifacts are not available: " + ", ".join(sorted(missing))
            )

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        plan_request = RunPlanRequest(
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            parameters=job.parameters,
        )
        plan = save_run_plan(plan_run_request(plan_request))
        if _pipe_grud_execution_mode(job) not in {
            "preflight",
            "build_sequences",
            "build_adaptive_surface",
            "infer_expert_surface",
            "infer_reference_profile",
        } and not plan.executable:
            blocker_messages = [issue.message for issue in plan.blockers]
            raise ScientificWorkflowAdapterError(
                "PIPE-GRU-D workflow is not executable for this dataset: "
                + "; ".join(blocker_messages)
            )
        return plan

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        if _pipe_grud_execution_mode(job) == "preflight":
            return self._execute_preflight(job, plan)
        if _pipe_grud_execution_mode(job) == "build_sequences":
            return self._execute_sequence_build(job, plan)
        if _pipe_grud_execution_mode(job) == "build_adaptive_surface":
            return self._execute_adaptive_surface_build(job, plan)
        if _pipe_grud_execution_mode(job) == "infer_expert_surface":
            return self._execute_expert_surface_inference(job, plan)
        if _pipe_grud_execution_mode(job) == "infer_reference_profile":
            return self._execute_reference_profile_inference(job, plan)

        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()

        references = _pipe_grud_reference_summary()
        row_counts = _pipe_grud_reference_row_counts(references)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "artifact_reference",
            "reference_profile": _PIPE_GRUD_REFERENCE_PROFILE,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            "references": references,
            "limitations": [
                "This adapter validates and reports the reviewed adaptive PIPE-GRU-D reference artifacts.",
                "It does not run dataset-specific PIPE-GRU-D inference for the submitted external dataset.",
                "External dataset inference requires a future adapter that builds compatible sequence tensors.",
            ],
        }
        report_path = run_dir / "pipe_grud_run_report.md"
        manifest_path = run_dir / "pipe_grud_run_manifest.json"
        _write_text(report_path, _pipe_grud_reference_report(manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()

        artifacts = [
            _run_artifact(workspace, report_path, name="pipe_grud_run_report.md", role="output"),
            _run_artifact(workspace, manifest_path, name="pipe_grud_run_manifest.json", role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_expert_surface_inference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_pipe_grud_expert_surface_inference(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_reference_profile_inference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_pipe_grud_reference_profile_inference(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_adaptive_surface_build(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_pipe_adaptive_surface_build(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_sequence_build(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = build_external_pipe_sequence_artifacts(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_preflight(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()

        request = read_dataset_request(job.dataset_id, workspace=workspace)
        diagnostics = _pipe_grud_external_dataset_preflight(request, plan)
        row_counts = _pipe_grud_preflight_row_counts(diagnostics)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "preflight",
            "reference_profile": _PIPE_GRUD_REFERENCE_PROFILE,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            **diagnostics,
        }
        report_path = run_dir / "pipe_grud_preflight_report.md"
        manifest_path = run_dir / "pipe_grud_preflight_manifest.json"
        _write_text(report_path, _pipe_grud_preflight_report(manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()

        artifacts = [
            _run_artifact(workspace, report_path, name="pipe_grud_preflight_report.md", role="output"),
            _run_artifact(workspace, manifest_path, name="pipe_grud_preflight_manifest.json", role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        summaries: dict[str, object] = {}
        preflight_manifest_path = run_plan_dir(plan.plan_id) / "pipe_grud_preflight_manifest.json"
        reference_inference_manifest_path = run_plan_dir(plan.plan_id) / "pipe_grud_reference_inference_manifest.json"
        adaptive_surface_manifest_path = run_plan_dir(plan.plan_id) / "pipe_adaptive_surface_manifest.json"
        inference_manifest_path = run_plan_dir(plan.plan_id) / "pipe_grud_external_inference_manifest.json"
        sequence_manifest_path = run_plan_dir(plan.plan_id) / "pipe_sequence_build_manifest.json"
        reference_manifest_path = run_plan_dir(plan.plan_id) / "pipe_grud_run_manifest.json"
        if preflight_manifest_path.exists():
            manifest = json.loads(preflight_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_preflight"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "reference_profile": manifest.get("reference_profile"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
                "next_actions": manifest.get("next_actions", []),
            }
        elif reference_inference_manifest_path.exists():
            manifest = json.loads(reference_inference_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_reference_profile_inference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "inference_version": manifest.get("inference_version"),
                "surface_contract": manifest.get("surface_contract"),
                "reference_profile": manifest.get("reference_profile"),
                "policy_name": manifest.get("policy_name"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
                "threshold_coverage": manifest.get("threshold_coverage", {}),
                "calibrator_coverage": manifest.get("calibrator_coverage", {}),
            }
        elif adaptive_surface_manifest_path.exists():
            manifest = json.loads(adaptive_surface_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_adaptive_surface_build"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "surface_version": manifest.get("surface_version"),
                "reference_profile": manifest.get("reference_profile"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
            }
        elif inference_manifest_path.exists():
            manifest = json.loads(inference_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_expert_surface_inference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "inference_version": manifest.get("inference_version"),
                "surface_contract": manifest.get("surface_contract"),
                "reference_profile": manifest.get("reference_profile"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
            }
        elif sequence_manifest_path.exists():
            manifest = json.loads(sequence_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_sequence_build"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "build_version": manifest.get("build_version"),
                "state_surface_version": manifest.get("state_surface_version"),
                "reference_profile": manifest.get("reference_profile"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
            }
        elif reference_manifest_path.exists():
            manifest = json.loads(reference_manifest_path.read_text(encoding="utf-8"))
            summaries["pipe_grud_reference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "reference_profile": manifest.get("reference_profile"),
                "limitations": manifest.get("limitations", []),
                "references": manifest.get("references", {}),
            }
        return RunResultSummaryResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            row_counts=execution.row_counts,
            summaries=summaries,
        )

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        self.validate_preconditions(job)
        plan = self.build_plan(job)
        execution = self.execute(job, plan)
        summary = self.collect_artifacts(job, plan, execution)
        return ScientificWorkflowExecutionBundle(plan=plan, execution=execution, summary=summary)


class PipeNeuralOdeReferenceWorkflowAdapter:
    """Neural ODE adapter for external preflight, inference, and reviewed artifact reporting."""

    adapter_id = "pipe_neural_ode_reference_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"pipe_neural_ode"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )
        execution_mode = _neural_ode_execution_mode(job)
        if execution_mode not in _NEURAL_ODE_EXECUTION_MODES:
            raise ScientificWorkflowAdapterError(
                "Neural ODE adapter v0 requires parameters.execution_mode='preflight' "
                "for external dataset diagnostics, parameters.execution_mode='infer_reference_profile' "
                "to run calibrated Neural ODE v1 reference-profile inference, or "
                "parameters.execution_mode='artifact_reference' to validate the reviewed Neural ODE v1 artifacts."
            )
        if execution_mode == "infer_reference_profile":
            available, missing = neural_ode_reference_inference_artifacts_available()
            if not available:
                raise ScientificWorkflowAdapterError(
                    "Neural ODE reference inference artifacts are not available: "
                    + ", ".join(sorted(missing))
                )
            return
        if execution_mode == "artifact_reference":
            missing = [
                name
                for name, path in _NEURAL_ODE_REFERENCE_ARTIFACTS.items()
                if not _artifact_available(path)
            ]
            if missing:
                raise ScientificWorkflowAdapterError(
                    "Neural ODE reference artifacts are not available: " + ", ".join(sorted(missing))
                )

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        plan_request = RunPlanRequest(
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            parameters=job.parameters,
        )
        return save_run_plan(plan_run_request(plan_request))

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        if _neural_ode_execution_mode(job) == "preflight":
            return self._execute_preflight(job, plan)
        if _neural_ode_execution_mode(job) == "infer_reference_profile":
            return self._execute_reference_profile_inference(job, plan)
        return self._execute_reference(job, plan)

    def _execute_reference_profile_inference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_pipe_neural_ode_reference_profile_inference(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_preflight(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        request = read_dataset_request(job.dataset_id, workspace=workspace)
        diagnostics = _temporal_external_dataset_preflight(
            request,
            plan,
            signal_variables=_NEURAL_ODE_SIGNAL_VARIABLES,
            required_history_months=_NEURAL_ODE_REQUIRED_HISTORY_MONTHS,
            workflow_label="Neural ODE v1",
            inference_ready=True,
            unavailable_surface_code="neural_ode_history_window_loader_not_available",
            unavailable_surface_message=(
                "Preflight does not execute Neural ODE v1 inference; use "
                "parameters.execution_mode='infer_reference_profile' to build the adaptive surface and run rollouts."
            ),
        )
        row_counts = _generic_preflight_row_counts(diagnostics)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "preflight",
            "reference_profile": _NEURAL_ODE_REFERENCE_PROFILE,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            **diagnostics,
            "limitations": [
                "Preflight is diagnostic only; it does not execute Neural ODE inference.",
                "Use execution_mode='infer_reference_profile' for dataset-specific calibrated Neural ODE v1 inference.",
                "Passing coverage checks does not guarantee field predictive skill for a new water body.",
            ],
        }
        report_path = run_dir / "pipe_neural_ode_preflight_report.md"
        manifest_path = run_dir / "pipe_neural_ode_preflight_manifest.json"
        _write_text(report_path, _generic_preflight_report("Neural ODE External Dataset Preflight", manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_reference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        references = _reference_artifact_summary(_NEURAL_ODE_REFERENCE_ARTIFACTS)
        row_counts = _reference_artifact_row_counts(references)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "artifact_reference",
            "reference_profile": _NEURAL_ODE_REFERENCE_PROFILE,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            "references": references,
            "limitations": [
                "This adapter validates and reports the reviewed Neural ODE v1 reference artifacts.",
                "It does not run dataset-specific Neural ODE inference for the submitted external dataset.",
                "External inference requires a future adapter that builds compatible history windows.",
            ],
        }
        report_path = run_dir / "pipe_neural_ode_run_report.md"
        manifest_path = run_dir / "pipe_neural_ode_run_manifest.json"
        _write_text(report_path, _reference_artifact_report("Neural ODE Reference Adapter Report", manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        summaries: dict[str, object] = {}
        run_dir = run_plan_dir(plan.plan_id)
        preflight_manifest = run_dir / "pipe_neural_ode_preflight_manifest.json"
        reference_inference_manifest = run_dir / "pipe_neural_ode_reference_inference_manifest.json"
        reference_manifest = run_dir / "pipe_neural_ode_run_manifest.json"
        if preflight_manifest.exists():
            manifest = json.loads(preflight_manifest.read_text(encoding="utf-8"))
            summaries["pipe_neural_ode_preflight"] = _preflight_summary(manifest)
        elif reference_inference_manifest.exists():
            manifest = json.loads(reference_inference_manifest.read_text(encoding="utf-8"))
            summaries["pipe_neural_ode_reference_profile_inference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "inference_version": manifest.get("inference_version"),
                "surface_contract": manifest.get("surface_contract"),
                "reference_profile": manifest.get("reference_profile"),
                "policy_name": manifest.get("policy_name"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
                "threshold_coverage": manifest.get("threshold_coverage", {}),
                "calibrator_coverage": manifest.get("calibrator_coverage", {}),
            }
        elif reference_manifest.exists():
            manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
            summaries["pipe_neural_ode_reference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "reference_profile": manifest.get("reference_profile"),
                "limitations": manifest.get("limitations", []),
                "references": manifest.get("references", {}),
            }
        return RunResultSummaryResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            row_counts=execution.row_counts,
            summaries=summaries,
        )

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        self.validate_preconditions(job)
        plan = self.build_plan(job)
        execution = self.execute(job, plan)
        summary = self.collect_artifacts(job, plan, execution)
        return ScientificWorkflowExecutionBundle(plan=plan, execution=execution, summary=summary)


class MifalEdT2WorkflowAdapter:
    """MIFAL-ED/T2 adapter for observable external scoring and reference reporting."""

    adapter_id = "mifal_observable_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"mifal_ed_t2"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )
        execution_mode = _mifal_execution_mode(job)
        if execution_mode not in _MIFAL_EXECUTION_MODES:
            raise ScientificWorkflowAdapterError(
                "MIFAL adapter v0 requires parameters.execution_mode='preflight' "
                "for observable input diagnostics, parameters.execution_mode='run_observable' "
                "to run deterministic MIFAL-ED/T2 scoring, or "
                "parameters.execution_mode='artifact_reference' to validate reviewed MIFAL artifacts."
            )
        surface = _mifal_surface(job)
        try:
            validate_surface(surface)
        except ValueError as exc:
            raise ScientificWorkflowAdapterError(str(exc)) from exc
        if execution_mode == "artifact_reference":
            available, missing = mifal_reference_artifacts_available(surface)
            if not available:
                raise ScientificWorkflowAdapterError(
                    "MIFAL reference artifacts are not available: " + ", ".join(sorted(missing))
                )

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        plan_request = RunPlanRequest(
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            parameters=job.parameters,
        )
        plan = save_run_plan(plan_run_request(plan_request))
        if _mifal_execution_mode(job) == "run_observable" and not plan.executable:
            blocker_messages = [issue.message for issue in plan.blockers]
            raise ScientificWorkflowAdapterError(
                "MIFAL workflow is not executable for this dataset: " + "; ".join(blocker_messages)
            )
        return plan

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        execution_mode = _mifal_execution_mode(job)
        if execution_mode == "preflight":
            return self._execute_preflight(job, plan)
        if execution_mode == "run_observable":
            return self._execute_observable(job, plan)
        return self._execute_reference(job, plan)

    def _execute_observable(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_mifal_observable(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_preflight(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        request = read_dataset_request(job.dataset_id, workspace=workspace)
        diagnostics = _mifal_external_dataset_preflight(request, plan, surface=_mifal_surface(job))
        row_counts = _generic_preflight_row_counts(diagnostics)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "preflight",
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            **diagnostics,
        }
        report_path = run_dir / "mifal_preflight_report.md"
        manifest_path = run_dir / "mifal_preflight_manifest.json"
        _write_text(report_path, _generic_preflight_report("MIFAL External Dataset Preflight", manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_reference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        surface = _mifal_surface(job)
        references = _reference_artifact_summary(_mifal_reference_artifacts(surface))
        row_counts = _reference_artifact_row_counts(references)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "artifact_reference",
            "surface": surface,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            "references": references,
            "limitations": [
                "This adapter validates and reports reviewed MIFAL observable artifacts.",
                "Use execution_mode='run_observable' to run deterministic MIFAL scoring on the submitted dataset.",
                "MIFAL emits bloom_h comparator alerts; it does not emit irc_alert.",
            ],
        }
        report_path = run_dir / "mifal_reference_report.md"
        manifest_path = run_dir / "mifal_reference_manifest.json"
        _write_text(report_path, _reference_artifact_report("MIFAL Reference Adapter Report", manifest_payload))
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        summaries: dict[str, object] = {}
        run_dir = run_plan_dir(plan.plan_id)
        preflight_manifest = run_dir / "mifal_preflight_manifest.json"
        observable_manifest = run_dir / "mifal_run_manifest.json"
        reference_manifest = run_dir / "mifal_reference_manifest.json"
        if preflight_manifest.exists():
            manifest = json.loads(preflight_manifest.read_text(encoding="utf-8"))
            summaries["mifal_preflight"] = _preflight_summary(manifest)
        elif observable_manifest.exists():
            manifest = json.loads(observable_manifest.read_text(encoding="utf-8"))
            summaries["mifal_observable"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "mifal_observable_version": manifest.get("mifal_observable_version"),
                "surface": manifest.get("surface"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "warnings": manifest.get("warnings", []),
                "calibration": manifest.get("calibration", {}),
            }
        elif reference_manifest.exists():
            manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
            summaries["mifal_reference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "surface": manifest.get("surface"),
                "limitations": manifest.get("limitations", []),
                "references": manifest.get("references", {}),
            }
        return RunResultSummaryResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            row_counts=execution.row_counts,
            summaries=summaries,
        )

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        self.validate_preconditions(job)
        plan = self.build_plan(job)
        execution = self.execute(job, plan)
        summary = self.collect_artifacts(job, plan, execution)
        return ScientificWorkflowExecutionBundle(plan=plan, execution=execution, summary=summary)


class CounterfactualPlanningWorkflowAdapter:
    """Counterfactual planning adapter for upstream preflight, V1 execution, and artifact reporting."""

    adapter_id = "counterfactual_planning_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"counterfactual_planning"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )
        execution_mode = _planning_execution_mode(job)
        if execution_mode not in _PLANNING_EXECUTION_MODES:
            raise ScientificWorkflowAdapterError(
                "Counterfactual planning adapter v0 requires parameters.execution_mode='preflight' "
                "to check upstream temporal output readiness, parameters.execution_mode='run_scenarios' "
                "to evaluate planning V1 scenarios against a completed upstream temporal run, or "
                "parameters.execution_mode='artifact_reference' to validate reviewed planning V1 artifacts."
            )
        if execution_mode == "run_scenarios":
            missing = [
                name
                for name, path in {"config": _PLANNING_REFERENCE_ARTIFACTS["config"]}.items()
                if not _artifact_available(path)
            ]
            if missing:
                raise ScientificWorkflowAdapterError(
                    "Counterfactual planning execution artifacts are not available: "
                    + ", ".join(sorted(missing))
                )
            if not str(job.parameters.get("upstream_plan_id", "")).strip():
                raise ScientificWorkflowAdapterError(
                    "Counterfactual planning execution requires parameters.upstream_plan_id."
                )
            return
        if execution_mode == "artifact_reference":
            missing = [
                name
                for name, path in _PLANNING_REFERENCE_ARTIFACTS.items()
                if not _artifact_available(path)
            ]
            if missing:
                raise ScientificWorkflowAdapterError(
                    "Counterfactual planning reference artifacts are not available: "
                    + ", ".join(sorted(missing))
                )

    def build_plan(self, job: ScientificWorkflowJob) -> RunPlanResponse:
        plan_request = RunPlanRequest(
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            parameters=job.parameters,
        )
        return save_run_plan(plan_run_request(plan_request))

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
        if _planning_execution_mode(job) == "preflight":
            return self._execute_preflight(job, plan)
        if _planning_execution_mode(job) == "run_scenarios":
            return self._execute_scenarios(job, plan)
        return self._execute_reference(job, plan)

    def _execute_scenarios(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        execution_id = _execution_id(plan.plan_id, self.adapter_id)
        result = run_external_counterfactual_planning_v1(
            dataset_id=job.dataset_id,
            plan=plan,
            run_dir=run_dir,
            workspace=workspace,
            execution_id=execution_id,
            adapter_id=self.adapter_id,
            adapter_interface_version=self.interface_version,
            started_at=started_at,
            parameters=job.parameters,
        )
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, path, name=path.name, role="manifest" if path.suffix == ".json" else "output")
            for path in result.output_paths
        ]
        execution = RunExecutionResponse(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=result.row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_preflight(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        diagnostics = _planning_preflight(job, plan)
        row_counts = _planning_preflight_row_counts(diagnostics)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "preflight",
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            **diagnostics,
            "limitations": [
                "Preflight is diagnostic only; it does not simulate counterfactual scenarios.",
                "Counterfactual planning is model-simulated comparison, not causal field evidence.",
                "Scenario execution requires an upstream compatible temporal alert or state surface.",
            ],
        }
        report_path = run_dir / "counterfactual_planning_preflight_report.md"
        manifest_path = run_dir / "counterfactual_planning_preflight_manifest.json"
        _write_text(
            report_path,
            _generic_preflight_report("Counterfactual Planning Preflight", manifest_payload),
        )
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def _execute_reference(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
    ) -> RunExecutionResponse:
        workspace = api_workspace()
        run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now_utc()
        references = _reference_artifact_summary(_PLANNING_REFERENCE_ARTIFACTS)
        row_counts = _reference_artifact_row_counts(references)
        manifest_payload: dict[str, object] = {
            "execution_id": _execution_id(plan.plan_id, self.adapter_id),
            "plan_id": plan.plan_id,
            "dataset_id": job.dataset_id,
            "workflow": job.workflow,
            "adapter": self.adapter_id,
            "adapter_interface_version": self.interface_version,
            "status": "completed",
            "execution_mode": "artifact_reference",
            "planning_version": "counterfactual_planning_raw_proxy_v1",
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            "references": references,
            "limitations": [
                "This adapter validates and reports reviewed counterfactual planning V1 artifacts.",
                "It does not run dataset-specific planning for the submitted external dataset.",
                "Planning output is model-simulated comparison, not causal field evidence.",
            ],
        }
        report_path = run_dir / "counterfactual_planning_reference_report.md"
        manifest_path = run_dir / "counterfactual_planning_reference_manifest.json"
        _write_text(
            report_path,
            _reference_artifact_report("Counterfactual Planning Reference Adapter Report", manifest_payload),
        )
        _write_json(manifest_path, manifest_payload)
        completed_at = _now_utc()
        artifacts = [
            _run_artifact(workspace, report_path, name=report_path.name, role="output"),
            _run_artifact(workspace, manifest_path, name=manifest_path.name, role="manifest"),
        ]
        execution = RunExecutionResponse(
            execution_id=str(manifest_payload["execution_id"]),
            plan_id=plan.plan_id,
            dataset_id=job.dataset_id,
            workflow=job.workflow,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            warnings=plan.warnings,
            artifacts=artifacts,
        )
        return save_run_execution(execution, workspace=workspace)

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        summaries: dict[str, object] = {}
        run_dir = run_plan_dir(plan.plan_id)
        preflight_manifest = run_dir / "counterfactual_planning_preflight_manifest.json"
        scenarios_manifest = run_dir / "counterfactual_manifest.json"
        reference_manifest = run_dir / "counterfactual_planning_reference_manifest.json"
        if preflight_manifest.exists():
            manifest = json.loads(preflight_manifest.read_text(encoding="utf-8"))
            summaries["counterfactual_planning_preflight"] = _preflight_summary(manifest)
        elif scenarios_manifest.exists():
            manifest = json.loads(scenarios_manifest.read_text(encoding="utf-8"))
            summaries["counterfactual_planning_v1"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "planning_version": manifest.get("planning_version"),
                "planning_api_version": manifest.get("planning_api_version"),
                "outcome": manifest.get("outcome"),
                "readiness": manifest.get("readiness", {}),
                "blockers": manifest.get("blockers", []),
                "warnings": manifest.get("warnings", []),
                "upstream": manifest.get("upstream", {}),
                "limitations": manifest.get("limitations", []),
            }
        elif reference_manifest.exists():
            manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
            summaries["counterfactual_planning_reference"] = {
                "adapter": manifest.get("adapter"),
                "execution_mode": manifest.get("execution_mode"),
                "planning_version": manifest.get("planning_version"),
                "limitations": manifest.get("limitations", []),
                "references": manifest.get("references", {}),
            }
        return RunResultSummaryResponse(
            plan_id=execution.plan_id,
            execution_id=execution.execution_id,
            dataset_id=execution.dataset_id,
            workflow=execution.workflow,
            row_counts=execution.row_counts,
            summaries=summaries,
        )

    def run(self, job: ScientificWorkflowJob) -> ScientificWorkflowExecutionBundle:
        self.validate_preconditions(job)
        plan = self.build_plan(job)
        execution = self.execute(job, plan)
        summary = self.collect_artifacts(job, plan, execution)
        return ScientificWorkflowExecutionBundle(plan=plan, execution=execution, summary=summary)


_ADAPTERS: tuple[ScientificWorkflowAdapter, ...] = (
    LocalDeterministicWorkflowAdapter(),
    PipeGrudReferenceWorkflowAdapter(),
    PipeNeuralOdeReferenceWorkflowAdapter(),
    MifalEdT2WorkflowAdapter(),
    CounterfactualPlanningWorkflowAdapter(),
)


def registered_scientific_workflow_adapters() -> tuple[ScientificWorkflowAdapter, ...]:
    """Return the registered job-backed scientific workflow adapters."""

    return _ADAPTERS


def executable_scientific_workflows() -> frozenset[str]:
    """Return workflows with a job-backed executable adapter."""

    workflows: set[str] = set()
    for adapter in _ADAPTERS:
        workflows.update(adapter.supported_workflows)
    return frozenset(workflows)


def adapter_for_workflow(workflow: str) -> ScientificWorkflowAdapter:
    """Return the registered adapter for a workflow or raise a clear error."""

    for adapter in _ADAPTERS:
        if workflow in adapter.supported_workflows:
            return adapter
    if workflow in _KNOWN_WORKFLOWS:
        raise UnsupportedScientificWorkflowError(
            f"No job-backed adapter is registered for workflow '{workflow}'. "
            f"Executable workflows: {sorted(executable_scientific_workflows())}."
        )
    raise UnsupportedScientificWorkflowError(f"Unsupported scientific workflow: {workflow}")


def build_scientific_workflow_job(
    model_type: ModelType,
    config: dict[str, Any],
) -> ScientificWorkflowJob:
    """Build a resolved scientific workflow job from run config."""

    workflow = str(config.get("workflow") or config.get("science_workflow") or "")
    if workflow not in _KNOWN_WORKFLOWS:
        raise UnsupportedScientificWorkflowError(f"Unsupported scientific workflow: {workflow}")
    dataset_id = config.get("dataset_id")
    if not dataset_id:
        raise ScientificWorkflowAdapterError(
            "Scientific workflow config requires a resolved dataset_id."
        )
    parameters = config.get("parameters")
    return ScientificWorkflowJob(
        model_type=model_type,
        dataset_id=str(dataset_id),
        workflow=cast(WorkflowName, workflow),
        parameters=parameters if isinstance(parameters, dict) else {},
        config=dict(config),
    )


def run_scientific_workflow_job(
    model_type: ModelType,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Execute a resolved scientific workflow config through the adapter registry."""

    job = build_scientific_workflow_job(model_type, config)
    adapter = adapter_for_workflow(job.workflow)
    bundle = adapter.run(job)
    return {
        "status": "completed",
        "adapter": adapter.adapter_id,
        "adapter_interface_version": adapter.interface_version,
        "model_type": model_type.value,
        "dataset_id": job.dataset_id,
        "workflow": job.workflow,
        "plan": bundle.plan.model_dump(mode="json"),
        "execution": bundle.execution.model_dump(mode="json"),
        "summary": bundle.summary.model_dump(mode="json"),
        "metrics": {
            "row_counts": bundle.execution.row_counts,
            "workflow": job.workflow,
        },
    }


def _pipe_grud_execution_mode(job: ScientificWorkflowJob) -> str:
    return str(job.parameters.get("execution_mode", "")).strip()


def _neural_ode_execution_mode(job: ScientificWorkflowJob) -> str:
    return str(job.parameters.get("execution_mode", "")).strip()


def _mifal_execution_mode(job: ScientificWorkflowJob) -> str:
    return str(job.parameters.get("execution_mode", "")).strip()


def _mifal_surface(job: ScientificWorkflowJob) -> str:
    return str(job.parameters.get("surface", MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA)).strip()


def _planning_execution_mode(job: ScientificWorkflowJob) -> str:
    return str(job.parameters.get("execution_mode", "")).strip()


def _temporal_external_dataset_preflight(
    request: DatasetValidationRequest,
    plan: RunPlanResponse,
    *,
    signal_variables: frozenset[str],
    required_history_months: int,
    workflow_label: str,
    inference_ready: bool,
    unavailable_surface_code: str,
    unavailable_surface_message: str,
) -> dict[str, object]:
    variable_counts, source_ids, site_months, month_ids, parseable_rows = _dataset_coverage(request)
    site_month_counts = {site_id: len(months) for site_id, months in sorted(site_months.items())}
    max_contiguous_site_months = max(
        (_max_contiguous_month_count(months) for months in site_months.values()),
        default=0,
    )
    signal_variables_present = sorted(
        variable for variable in signal_variables if variable_counts.get(variable, 0) > 0
    )
    has_signal = bool(signal_variables_present)
    history_candidate = (
        len(month_ids) >= 3
        and has_signal
        and max_contiguous_site_months >= required_history_months
    )
    ready = history_candidate and inference_ready and plan.executable

    blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if parseable_rows == 0:
        blockers.append(
            _preflight_issue(
                "no_parseable_observations",
                "No observations have a parseable observation month.",
            )
        )
    if len(month_ids) < 3:
        blockers.append(
            _preflight_issue(
                "insufficient_months",
                f"{workflow_label} requires at least three distinct observation months for basic eligibility.",
                {"months": len(month_ids), "minimum_months": 3},
            )
        )
    if not has_signal:
        blockers.append(
            _preflight_issue(
                "missing_trophic_or_nutrient_signal",
                f"{workflow_label} requires at least one compatible trophic or nutrient signal.",
                {"required_any": sorted(signal_variables)},
            )
        )
    if max_contiguous_site_months < required_history_months:
        blockers.append(
            _preflight_issue(
                "history_window_too_short",
                f"No site has enough contiguous monthly history for the reviewed {workflow_label} window.",
                {
                    "max_contiguous_site_months": max_contiguous_site_months,
                    "required_history_months": required_history_months,
                },
            )
        )
    if not inference_ready:
        blockers.append(
            _preflight_issue(
                unavailable_surface_code,
                unavailable_surface_message,
                {"adapter_stage": "preflight_only"},
            )
        )
    if variable_counts.get("chlorophyll_a_ugL", 0) == 0:
        warnings.append(
            _preflight_issue(
                "chlorophyll_signal_missing",
                "No chlorophyll-a observations were submitted; nutrient-only temporal runs may be weaker or ineligible for some alert targets.",
            )
        )
    if plan.blockers:
        warnings.append(
            _preflight_issue(
                "planner_not_ready",
                "The dry-run planner has blockers; inspect the planner section before attempting inference.",
                {"blocker_count": len(plan.blockers), "plan_status": str(plan.status)},
            )
        )

    return {
        "outcome": "ready_for_inference" if ready else "not_ready",
        "readiness": {
            "history_candidate": history_candidate,
            "inference_adapter_available": inference_ready,
            "planner_executable": plan.executable,
            "ready_for_inference": ready,
            "required_history_months": required_history_months,
        },
        "coverage": {
            "total_observations": len(request.observations),
            "parseable_observations": parseable_rows,
            "sources": len(source_ids),
            "sites": len(site_months),
            "months": len(month_ids),
            "site_months": sum(site_month_counts.values()),
            "max_contiguous_site_months": max_contiguous_site_months,
            "site_month_counts": site_month_counts,
        },
        "variables": {
            "counts": dict(sorted(variable_counts.items())),
            "signal_variables_present": signal_variables_present,
            "chlorophyll_present": variable_counts.get("chlorophyll_a_ugL", 0) > 0,
        },
        "blockers": blockers,
        "warnings": warnings,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "next_actions": [
            f"Provide at least {required_history_months} contiguous monthly observations for one site.",
            "Build the API history-window and rollout adapter before running dataset-specific temporal inference.",
        ],
    }


def _mifal_external_dataset_preflight(
    request: DatasetValidationRequest,
    plan: RunPlanResponse,
    *,
    surface: str,
) -> dict[str, object]:
    variable_counts, source_ids, site_months, month_ids, parseable_rows = _dataset_coverage(request)
    observable_variables = {
        "chlorophyll_a_ugL",
        "TP_ugL",
        "TN_ugL",
        "temperature_C",
        "DO_mgL",
        "secchi_depth_m",
        "turbidity_NTU",
    }
    present = sorted(variable for variable in observable_variables if variable_counts.get(variable, 0) > 0)
    has_minimal_signal = bool(
        set(present) & {"chlorophyll_a_ugL", "TP_ugL", "TN_ugL", "temperature_C", "DO_mgL"}
    )
    available, missing = mifal_reference_artifacts_available(surface)
    ready = parseable_rows > 0 and has_minimal_signal and plan.executable
    blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if parseable_rows == 0:
        blockers.append(
            _preflight_issue(
                "no_parseable_observations",
                "No observations have a parseable observation month.",
            )
        )
    if not has_minimal_signal:
        blockers.append(
            _preflight_issue(
                "missing_mifal_observable_signal",
                "MIFAL-ED/T2 requires at least one observable trophic, nutrient, temperature, or oxygen signal.",
                {"required_any": ["chlorophyll_a_ugL", "TP_ugL", "TN_ugL", "temperature_C", "DO_mgL"]},
            )
        )
    if not available:
        warnings.append(
            _preflight_issue(
                "mifal_calibration_artifacts_incomplete",
                "MIFAL scoring can run, but calibrated bloom alerts require reviewed calibrators and thresholds.",
                {"missing": sorted(missing)},
            )
        )
    if plan.blockers:
        warnings.append(
            _preflight_issue(
                "planner_not_ready",
                "The dry-run planner has blockers; inspect the planner section before attempting scoring.",
                {"blocker_count": len(plan.blockers), "plan_status": str(plan.status)},
            )
        )
    return {
        "outcome": "ready_for_mifal_scoring" if ready else "not_ready",
        "surface": surface,
        "readiness": {
            "observable_candidate": has_minimal_signal,
            "planner_executable": plan.executable,
            "calibration_artifacts_complete": available,
            "ready_for_mifal_scoring": ready,
        },
        "coverage": {
            "total_observations": len(request.observations),
            "parseable_observations": parseable_rows,
            "sources": len(source_ids),
            "sites": len(site_months),
            "months": len(month_ids),
            "site_months": sum(len(months) for months in site_months.values()),
        },
        "variables": {
            "counts": dict(sorted(variable_counts.items())),
            "observable_variables_present": present,
        },
        "blockers": blockers,
        "warnings": warnings,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "next_actions": [
            "Run parameters.execution_mode='run_observable' to produce MIFAL scores and bloom_h alerts.",
            "Inspect calibration coverage before using alert flags operationally.",
        ],
        "limitations": [
            "MIFAL-ED/T2 is deterministic eco-fuzzy scoring, not a learned causal field model.",
            "Calibration transferability is not guaranteed for a new water body.",
        ],
    }


def _dataset_coverage(
    request: DatasetValidationRequest,
) -> tuple[Counter[str], set[str], dict[str, set[str]], set[str], int]:
    variable_counts: Counter[str] = Counter()
    source_ids: set[str] = set()
    site_months: dict[str, set[str]] = {}
    month_ids: set[str] = set()
    parseable_rows = 0
    for observation in request.observations:
        source_ids.add(observation.source_id)
        year_month = parse_observed_year_month(observation.observed_at)
        if year_month is None:
            continue
        parseable_rows += 1
        variable_counts[observation.variable] += 1
        month_ids.add(year_month)
        site_months.setdefault(observation.site_id, set()).add(year_month)
    return variable_counts, source_ids, site_months, month_ids, parseable_rows


def _generic_preflight_row_counts(diagnostics: Mapping[str, object]) -> dict[str, int]:
    coverage_obj = diagnostics.get("coverage", {})
    coverage = cast(Mapping[str, object], coverage_obj) if isinstance(coverage_obj, dict) else {}
    variables_obj = diagnostics.get("variables", {})
    variables = cast(Mapping[str, object], variables_obj) if isinstance(variables_obj, dict) else {}
    counts_obj = variables.get("counts", {})
    counts = cast(Mapping[str, object], counts_obj) if isinstance(counts_obj, dict) else {}
    blockers = diagnostics.get("blockers", [])
    warnings = diagnostics.get("warnings", [])
    return {
        "observations": _int_mapping_value(coverage, "total_observations"),
        "parseable_observations": _int_mapping_value(coverage, "parseable_observations"),
        "sites": _int_mapping_value(coverage, "sites"),
        "months": _int_mapping_value(coverage, "months"),
        "site_months": _int_mapping_value(coverage, "site_months"),
        "variables": len(counts),
        "blockers": len(blockers) if isinstance(blockers, list) else 0,
        "warnings": len(warnings) if isinstance(warnings, list) else 0,
        "generated_reports": 2,
    }


def _generic_preflight_report(title: str, manifest: Mapping[str, object]) -> str:
    row_counts_obj = manifest.get("row_counts", {})
    row_counts = cast(Mapping[str, object], row_counts_obj) if isinstance(row_counts_obj, dict) else {}
    readiness_obj = manifest.get("readiness", {})
    readiness = cast(Mapping[str, object], readiness_obj) if isinstance(readiness_obj, dict) else {}
    blockers = _manifest_issue_list(manifest.get("blockers", []))
    warnings = _manifest_issue_list(manifest.get("warnings", []))
    next_actions_obj = manifest.get("next_actions", [])
    next_actions = [str(item) for item in next_actions_obj] if isinstance(next_actions_obj, list) else []
    limitations_obj = manifest.get("limitations", [])
    limitations = [str(item) for item in limitations_obj] if isinstance(limitations_obj, list) else []
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- interface: `{manifest['adapter_interface_version']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- outcome: `{manifest.get('outcome', 'unknown')}`",
            f"- dataset id: `{manifest['dataset_id']}`",
            f"- plan id: `{manifest['plan_id']}`",
            "",
            "## Readiness",
            "",
            *[f"- {key}: {value}" for key, value in sorted(readiness.items())],
            "",
            "## Row Counts",
            "",
            *[f"- {key}: {value}" for key, value in sorted(row_counts.items())],
            "",
            "## Blockers",
            "",
            *(_issue_report_lines(blockers) or ["- none"]),
            "",
            "## Warnings",
            "",
            *(_issue_report_lines(warnings) or ["- none"]),
            "",
            "## Next Actions",
            "",
            *[f"- {item}" for item in next_actions],
            "",
            "## Limitations",
            "",
            *([f"- {item}" for item in limitations] or ["- none"]),
            "",
        ]
    )


def _preflight_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "adapter": manifest.get("adapter"),
        "execution_mode": manifest.get("execution_mode"),
        "outcome": manifest.get("outcome"),
        "readiness": manifest.get("readiness", {}),
        "blockers": manifest.get("blockers", []),
        "warnings": manifest.get("warnings", []),
        "next_actions": manifest.get("next_actions", []),
    }


def _reference_artifact_summary(artifacts: Mapping[str, Path]) -> dict[str, object]:
    manifests = {
        name: _read_json_if_available(path)
        for name, path in artifacts.items()
        if path.suffix == ".json"
    }
    return {
        "artifact_status": {name: _artifact_status(path) for name, path in artifacts.items()},
        "manifests": {
            key: _compact_manifest_summary(value)
            for key, value in manifests.items()
            if value is not None
        },
    }


def _reference_artifact_row_counts(references: Mapping[str, object]) -> dict[str, int]:
    status_obj = references.get("artifact_status", {})
    statuses = cast(Mapping[str, object], status_obj) if isinstance(status_obj, dict) else {}
    available = 0
    for status in statuses.values():
        if isinstance(status, Mapping):
            status_map = cast(Mapping[str, object], status)
            if not status_map.get("available"):
                continue
            available += 1
    return {
        "reference_artifacts": len(statuses),
        "available_reference_artifacts": available,
        "generated_reports": 2,
    }


def _reference_artifact_report(title: str, manifest: Mapping[str, object]) -> str:
    row_counts_obj = manifest.get("row_counts", {})
    row_counts = cast(Mapping[str, object], row_counts_obj) if isinstance(row_counts_obj, dict) else {}
    limitations_obj = manifest.get("limitations", [])
    limitations = [str(item) for item in limitations_obj] if isinstance(limitations_obj, list) else []
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- interface: `{manifest['adapter_interface_version']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- dataset id: `{manifest['dataset_id']}`",
            f"- plan id: `{manifest['plan_id']}`",
            "",
            "## Row Counts",
            "",
            *[f"- {key}: {value}" for key, value in sorted(row_counts.items())],
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in limitations],
            "",
        ]
    )


def _mifal_reference_artifacts(surface: str) -> dict[str, Path]:
    slug = "current_chla" if surface == "observable_current_chla" else "no_current_chla"
    return {
        "validation_manifest": Path(f"reports/mifal/mifal_observable_{slug}_pipe_grud_validation_manifest.json"),
        "validation_report": Path(f"reports/mifal/mifal_observable_{slug}_pipe_grud_validation_report.md"),
        "validation_metrics": Path(f"reports/mifal/mifal_observable_{slug}_pipe_grud_validation_metrics.csv"),
        "calibration_manifest": Path(
            f"reports/mifal/mifal_observable_{slug}_pipe_grud_validation_calibration_manifest.json"
        ),
        "calibration_thresholds": Path(
            f"reports/mifal/mifal_observable_{slug}_pipe_grud_validation_calibration_thresholds.csv"
        ),
        "observable_calibrators": Path(f"models/mifal/observable_calibrators/{slug}_pipe_grud_validation"),
    }


def _planning_preflight(
    job: ScientificWorkflowJob,
    plan: RunPlanResponse,
) -> dict[str, object]:
    upstream_plan_id = str(job.parameters.get("upstream_plan_id", "")).strip()
    blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    upstream: dict[str, object] | None = None
    ready = False

    if not upstream_plan_id:
        blockers.append(
            _preflight_issue(
                "missing_upstream_plan_id",
                "Counterfactual planning requires parameters.upstream_plan_id for a completed temporal output run.",
            )
        )
    else:
        try:
            upstream_execution = read_run_execution(upstream_plan_id)
            artifact_names = sorted(artifact.name for artifact in upstream_execution.artifacts)
            compatible_artifacts = sorted(set(artifact_names) & _TEMPORAL_ALERT_ARTIFACTS)
            upstream = {
                "plan_id": upstream_execution.plan_id,
                "dataset_id": upstream_execution.dataset_id,
                "workflow": upstream_execution.workflow,
                "status": upstream_execution.status,
                "artifact_names": artifact_names,
                "compatible_artifacts": compatible_artifacts,
                "row_counts": upstream_execution.row_counts,
            }
            if upstream_execution.dataset_id != job.dataset_id:
                blockers.append(
                    _preflight_issue(
                        "upstream_dataset_mismatch",
                        "The upstream run belongs to a different registered dataset.",
                        {
                            "planning_dataset_id": job.dataset_id,
                            "upstream_dataset_id": upstream_execution.dataset_id,
                        },
                    )
                )
            if not compatible_artifacts:
                blockers.append(
                    _preflight_issue(
                        "upstream_temporal_alert_surface_missing",
                        "The upstream run does not expose a compatible temporal alert artifact.",
                        {"required_any": sorted(_TEMPORAL_ALERT_ARTIFACTS)},
                    )
                )
            ready = not blockers
        except RunExecutionNotFoundError:
            blockers.append(
                _preflight_issue(
                    "upstream_execution_not_found",
                    "The upstream plan has not been executed or cannot be found in the API workspace.",
                    {"upstream_plan_id": upstream_plan_id},
                )
            )

    if plan.blockers:
        warnings.append(
            _preflight_issue(
                "planner_not_ready",
                "The dry-run planner has blockers; this is expected until a concrete upstream surface is supplied.",
                {"blocker_count": len(plan.blockers), "plan_status": str(plan.status)},
            )
        )
    return {
        "outcome": "ready_for_planning_adapter" if ready else "not_ready",
        "readiness": {
            "upstream_plan_id": upstream_plan_id or None,
            "upstream_execution_available": upstream is not None,
            "compatible_temporal_alert_surface": bool(
                upstream and cast(list[object], upstream.get("compatible_artifacts", []))
            ),
            "ready_for_planning_adapter": ready,
        },
        "upstream": upstream or {},
        "blockers": blockers,
        "warnings": warnings,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "next_actions": [
            "Run a compatible temporal alert workflow for the same dataset.",
            "Pass its plan id as parameters.upstream_plan_id before scenario execution.",
        ],
    }


def _planning_preflight_row_counts(diagnostics: Mapping[str, object]) -> dict[str, int]:
    blockers = diagnostics.get("blockers", [])
    warnings = diagnostics.get("warnings", [])
    upstream_obj = diagnostics.get("upstream", {})
    upstream = cast(Mapping[str, object], upstream_obj) if isinstance(upstream_obj, dict) else {}
    artifacts = upstream.get("artifact_names", [])
    compatible = upstream.get("compatible_artifacts", [])
    return {
        "upstream_artifacts": len(artifacts) if isinstance(artifacts, list) else 0,
        "compatible_upstream_artifacts": len(compatible) if isinstance(compatible, list) else 0,
        "blockers": len(blockers) if isinstance(blockers, list) else 0,
        "warnings": len(warnings) if isinstance(warnings, list) else 0,
        "generated_reports": 2,
    }


def _pipe_grud_external_dataset_preflight(
    request: DatasetValidationRequest,
    plan: RunPlanResponse,
) -> dict[str, object]:
    history_length = _pipe_grud_reference_history_length()
    variable_counts: Counter[str] = Counter()
    site_months: dict[str, set[str]] = {}
    source_ids: set[str] = set()
    month_ids: set[str] = set()
    parseable_rows = 0

    for observation in request.observations:
        source_ids.add(observation.source_id)
        year_month = parse_observed_year_month(observation.observed_at)
        if year_month is None:
            continue
        parseable_rows += 1
        variable_counts[observation.variable] += 1
        month_ids.add(year_month)
        site_months.setdefault(observation.site_id, set()).add(year_month)

    site_month_counts = {
        site_id: len(months) for site_id, months in sorted(site_months.items())
    }
    max_contiguous_site_months = max(
        (_max_contiguous_month_count(months) for months in site_months.values()),
        default=0,
    )
    signal_variables_present = sorted(
        variable for variable in _PIPE_GRUD_SIGNAL_VARIABLES if variable_counts.get(variable, 0) > 0
    )
    has_signal = bool(signal_variables_present)
    sequence_candidate = (
        len(month_ids) >= 3
        and has_signal
        and max_contiguous_site_months >= history_length
    )
    state_surface_available = False
    ready_for_pipe_grud_inference = (
        sequence_candidate and state_surface_available and plan.executable
    )

    blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if parseable_rows == 0:
        blockers.append(
            _preflight_issue(
                "no_parseable_observations",
                "No observations have a parseable observation month.",
            )
        )
    if len(month_ids) < 3:
        blockers.append(
            _preflight_issue(
                "insufficient_months",
                "PIPE-GRU-D requires at least three distinct observation months for basic eligibility.",
                {"months": len(month_ids), "minimum_months": 3},
            )
        )
    if not has_signal:
        blockers.append(
            _preflight_issue(
                "missing_trophic_or_nutrient_signal",
                "PIPE-GRU-D requires at least one compatible trophic or nutrient signal.",
                {"required_any": sorted(_PIPE_GRUD_SIGNAL_VARIABLES)},
            )
        )
    if max_contiguous_site_months < history_length:
        blockers.append(
            _preflight_issue(
                "history_window_too_short",
                "No site has enough contiguous monthly history for the reviewed PIPE-GRU-D window.",
                {
                    "max_contiguous_site_months": max_contiguous_site_months,
                    "required_history_months": history_length,
                },
            )
        )
    blockers.append(
        _preflight_issue(
            "pipe_state_surface_not_available",
            "Dataset-specific adaptive/calibrated PIPE-GRU-D inference requires adaptive state sequence tensors; "
            "preflight does not build them, and the current sequence builder emits an expert-fuzzy surface.",
            {
                "required_surface": f"{_PIPE_GRUD_REFERENCE_PROFILE} PIPE sequence tensors",
                "adapter_stage": "preflight_only",
            },
        )
    )

    if variable_counts.get("chlorophyll_a_ugL", 0) == 0:
        warnings.append(
            _preflight_issue(
                "chlorophyll_signal_missing",
                "No chlorophyll-a observations were submitted; nutrient-only runs may be weaker or ineligible for some alert targets.",
            )
        )
    if len(site_months) > 1 and max_contiguous_site_months < history_length:
        warnings.append(
            _preflight_issue(
                "site_coverage_fragmented",
                "Temporal coverage is split across sites without a long enough contiguous site history.",
                {"site_month_counts": site_month_counts},
            )
        )
    if plan.blockers:
        warnings.append(
            _preflight_issue(
                "planner_not_ready",
                "The dry-run planner has blockers; inspect the planner section before attempting inference.",
                {"blocker_count": len(plan.blockers), "plan_status": str(plan.status)},
            )
        )

    return {
        "outcome": "ready_for_pipe_grud_inference" if ready_for_pipe_grud_inference else "not_ready",
        "readiness": {
            "sequence_candidate": sequence_candidate,
            "state_surface_available": state_surface_available,
            "planner_executable": plan.executable,
            "ready_for_pipe_grud_inference": ready_for_pipe_grud_inference,
            "required_history_months": history_length,
        },
        "coverage": {
            "total_observations": len(request.observations),
            "parseable_observations": parseable_rows,
            "sources": len(source_ids),
            "sites": len(site_months),
            "months": len(month_ids),
            "site_months": sum(site_month_counts.values()),
            "max_contiguous_site_months": max_contiguous_site_months,
            "site_month_counts": site_month_counts,
        },
        "variables": {
            "counts": dict(sorted(variable_counts.items())),
            "signal_variables_present": signal_variables_present,
            "chlorophyll_present": variable_counts.get("chlorophyll_a_ugL", 0) > 0,
        },
        "blockers": blockers,
        "warnings": warnings,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "next_actions": _pipe_grud_preflight_next_actions(
            sequence_candidate=sequence_candidate,
            has_signal=has_signal,
            max_contiguous_site_months=max_contiguous_site_months,
            history_length=history_length,
        ),
        "limitations": [
            "Preflight is diagnostic only; it does not execute PIPE-GRU-D inference.",
            "Passing basic coverage checks does not guarantee field predictive skill for a new water body.",
            "The reviewed PIPE-GRU-D reference profile depends on an adaptive state surface and calibrated alert policy.",
        ],
    }


def _pipe_grud_preflight_next_actions(
    *,
    sequence_candidate: bool,
    has_signal: bool,
    max_contiguous_site_months: int,
    history_length: int,
) -> list[str]:
    actions: list[str] = []
    if not has_signal:
        actions.append("Add at least one chlorophyll-a, total phosphorus, or total nitrogen signal.")
    if max_contiguous_site_months < history_length:
        actions.append(
            f"Provide at least {history_length} contiguous monthly observations for one site "
            "before temporal inference."
        )
    if sequence_candidate:
        actions.append(
            "Build the external adaptive PIPE state-surface adapter for this dataset."
        )
    actions.append(
        "After adaptive-compatible sequence tensors exist, run the calibrated PIPE-GRU-D inference adapter."
    )
    return actions


def _pipe_grud_preflight_row_counts(diagnostics: Mapping[str, object]) -> dict[str, int]:
    coverage_obj = diagnostics.get("coverage", {})
    coverage = cast(Mapping[str, object], coverage_obj) if isinstance(coverage_obj, dict) else {}
    variables_obj = diagnostics.get("variables", {})
    variables = cast(Mapping[str, object], variables_obj) if isinstance(variables_obj, dict) else {}
    counts_obj = variables.get("counts", {})
    counts = cast(Mapping[str, object], counts_obj) if isinstance(counts_obj, dict) else {}
    blockers = diagnostics.get("blockers", [])
    warnings = diagnostics.get("warnings", [])
    return {
        "observations": _int_mapping_value(coverage, "total_observations"),
        "parseable_observations": _int_mapping_value(coverage, "parseable_observations"),
        "sites": _int_mapping_value(coverage, "sites"),
        "months": _int_mapping_value(coverage, "months"),
        "site_months": _int_mapping_value(coverage, "site_months"),
        "max_contiguous_site_months": _int_mapping_value(coverage, "max_contiguous_site_months"),
        "variables": len(counts),
        "blockers": len(blockers) if isinstance(blockers, list) else 0,
        "warnings": len(warnings) if isinstance(warnings, list) else 0,
        "generated_reports": 2,
    }


def _pipe_grud_reference_history_length() -> int:
    manifest = _read_json_if_available(_PIPE_GRUD_REFERENCE_ARTIFACTS["model_manifest"])
    if manifest is None:
        return _PIPE_GRUD_REQUIRED_HISTORY_MONTHS
    config_obj = manifest.get("config", {})
    config = cast(Mapping[str, object], config_obj) if isinstance(config_obj, dict) else {}
    history_length = config.get("history_length")
    if isinstance(history_length, int | float):
        return int(history_length)
    return _PIPE_GRUD_REQUIRED_HISTORY_MONTHS


def _max_contiguous_month_count(months: set[str]) -> int:
    if not months:
        return 0
    month_numbers = sorted({_month_number(year_month) for year_month in months})
    longest = 1
    current = 1
    for previous, value in zip(month_numbers, month_numbers[1:], strict=False):
        if value == previous + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
    return longest


def _month_number(year_month: str) -> int:
    year, month = year_month.split("-", maxsplit=1)
    return int(year) * 12 + int(month)


def _preflight_issue(
    code: str,
    message: str,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "details": dict(details or {}),
    }


def _pipe_grud_reference_summary() -> dict[str, object]:
    manifests = {
        "model": _read_json_if_available(_PIPE_GRUD_REFERENCE_ARTIFACTS["model_manifest"]),
        "rollout_validation": _read_json_if_available(
            _PIPE_GRUD_REFERENCE_ARTIFACTS["rollout_validation_manifest"]
        ),
        "rollout_test": _read_json_if_available(_PIPE_GRUD_REFERENCE_ARTIFACTS["rollout_test_manifest"]),
        "calibration": _read_json_if_available(_PIPE_GRUD_REFERENCE_ARTIFACTS["calibration_manifest"]),
        "policy": _read_json_if_available(_PIPE_GRUD_REFERENCE_ARTIFACTS["policy_manifest"]),
    }
    artifact_status = {
        name: _artifact_status(path) for name, path in _PIPE_GRUD_REFERENCE_ARTIFACTS.items()
    }
    return {
        "profile": _PIPE_GRUD_REFERENCE_PROFILE,
        "artifact_status": artifact_status,
        "manifests": {
            key: _compact_manifest_summary(value) for key, value in manifests.items() if value is not None
        },
    }


def _pipe_grud_reference_row_counts(references: dict[str, object]) -> dict[str, int]:
    manifests_obj = references.get("manifests", {})
    manifests = cast(dict[str, object], manifests_obj) if isinstance(manifests_obj, dict) else {}
    return {
        "reference_model_metric_rows": _manifest_row_count(manifests, "model", "metric_rows"),
        "reference_validation_rollout_rows": _manifest_row_count(
            manifests, "rollout_validation", "evaluated_rollout_rows"
        ),
        "reference_test_rollout_rows": _manifest_row_count(
            manifests, "rollout_test", "evaluated_rollout_rows"
        ),
        "reference_policy_threshold_rows": _manifest_row_count(
            manifests, "policy", "threshold_rows"
        ),
        "generated_reports": 2,
    }


def _manifest_row_count(manifests: Mapping[str, object], manifest_name: str, key: str) -> int:
    manifest = manifests.get(manifest_name)
    if not isinstance(manifest, dict):
        return 0
    manifest_map = cast(Mapping[str, object], manifest)
    row_counts_obj = manifest_map.get("row_counts", {})
    if not isinstance(row_counts_obj, dict):
        return 0
    row_counts = cast(dict[str, object], row_counts_obj)
    value = row_counts.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _compact_manifest_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": payload.get("status"),
        "version": (
            payload.get("model_version")
            or payload.get("backtest_version")
            or payload.get("calibration_version")
            or payload.get("policy_version")
        ),
        "generated_at_utc": payload.get("generated_at_utc"),
        "row_counts": payload.get("row_counts", {}),
        "selection": payload.get("selection", {}),
    }


def _pipe_grud_reference_report(manifest: Mapping[str, object]) -> str:
    row_counts_obj = manifest.get("row_counts", {})
    row_counts = cast(dict[str, object], row_counts_obj) if isinstance(row_counts_obj, dict) else {}
    limitations_obj = manifest.get("limitations", [])
    limitations = (
        [str(item) for item in limitations_obj]
        if isinstance(limitations_obj, list)
        else []
    )
    return "\n".join(
        [
            "# PIPE-GRU-D Reference Adapter Report",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- interface: `{manifest['adapter_interface_version']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- reference profile: `{manifest['reference_profile']}`",
            f"- dataset id: `{manifest['dataset_id']}`",
            f"- plan id: `{manifest['plan_id']}`",
            "",
            "## Row Counts",
            "",
            *[f"- {key}: {value}" for key, value in sorted(row_counts.items())],
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in limitations],
            "",
        ]
    )


def _pipe_grud_preflight_report(manifest: Mapping[str, object]) -> str:
    row_counts_obj = manifest.get("row_counts", {})
    row_counts = cast(Mapping[str, object], row_counts_obj) if isinstance(row_counts_obj, dict) else {}
    readiness_obj = manifest.get("readiness", {})
    readiness = cast(Mapping[str, object], readiness_obj) if isinstance(readiness_obj, dict) else {}
    blockers = _manifest_issue_list(manifest.get("blockers", []))
    warnings = _manifest_issue_list(manifest.get("warnings", []))
    next_actions_obj = manifest.get("next_actions", [])
    next_actions = (
        [str(item) for item in next_actions_obj]
        if isinstance(next_actions_obj, list)
        else []
    )
    limitations_obj = manifest.get("limitations", [])
    limitations = (
        [str(item) for item in limitations_obj]
        if isinstance(limitations_obj, list)
        else []
    )
    return "\n".join(
        [
            "# PIPE-GRU-D External Dataset Preflight",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- interface: `{manifest['adapter_interface_version']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- outcome: `{manifest['outcome']}`",
            f"- reference profile: `{manifest['reference_profile']}`",
            f"- dataset id: `{manifest['dataset_id']}`",
            f"- plan id: `{manifest['plan_id']}`",
            "",
            "## Readiness",
            "",
            *[f"- {key}: {value}" for key, value in sorted(readiness.items())],
            "",
            "## Row Counts",
            "",
            *[f"- {key}: {value}" for key, value in sorted(row_counts.items())],
            "",
            "## Blockers",
            "",
            *(_issue_report_lines(blockers) or ["- none"]),
            "",
            "## Warnings",
            "",
            *(_issue_report_lines(warnings) or ["- none"]),
            "",
            "## Next Actions",
            "",
            *[f"- {item}" for item in next_actions],
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in limitations],
            "",
        ]
    )


def _manifest_issue_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        cast(Mapping[str, object], item)
        for item in value
        if isinstance(item, dict)
    ]


def _issue_report_lines(issues: list[Mapping[str, object]]) -> list[str]:
    return [
        f"- {issue.get('code', 'unknown')}: {issue.get('message', '')}"
        for issue in issues
    ]


def _int_mapping_value(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _read_json_if_available(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_available(path: Path) -> bool:
    return path.exists() or Path(f"{path.as_posix()}.dvc").exists()


def _artifact_status(path: Path) -> dict[str, object]:
    if path.exists():
        if path.is_dir():
            files = sorted(item for item in path.iterdir() if item.is_file())
            return {
                "path": path.as_posix(),
                "available": True,
                "kind": "directory",
                "file_count": len(files),
            }
        return {
            "path": path.as_posix(),
            "available": True,
            "kind": "file",
            "bytes": path.stat().st_size,
            "sha256": _sha256_path(path),
        }
    dvc_path = Path(f"{path.as_posix()}.dvc")
    return {
        "path": path.as_posix(),
        "available": dvc_path.exists(),
        "kind": "dvc_pointer" if dvc_path.exists() else "missing",
        "dvc_pointer": dvc_path.as_posix() if dvc_path.exists() else None,
    }


def _run_artifact(workspace: Path, path: Path, *, name: str, role: str) -> RunPlanArtifact:
    content = path.read_bytes()
    return RunPlanArtifact(
        name=name,
        role=role,
        uri=path.relative_to(workspace).as_posix(),
        required=False,
        availability="available",
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
    )


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _execution_id(plan_id: str, adapter_id: str) -> str:
    payload = f"{plan_id}:{adapter_id}"
    return f"exec_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
