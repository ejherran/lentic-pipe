"""Job-backed scientific workflow adapter registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast, get_args

from src.api.models.run import ModelType
from src.api.schemas.dataset import WorkflowName
from src.api.schemas.run import (
    RunExecutionResponse,
    RunPlanRequest,
    RunPlanResponse,
    RunResultSummaryResponse,
)
from src.api.services.run_artifacts import summarize_run_results
from src.api.services.run_executor import execute_run_plan
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import save_run_plan

ADAPTER_INTERFACE_VERSION = "job_adapter_interface_v1"
_KNOWN_WORKFLOWS = frozenset(str(name) for name in get_args(WorkflowName))


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


_ADAPTERS: tuple[ScientificWorkflowAdapter, ...] = (LocalDeterministicWorkflowAdapter(),)


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
