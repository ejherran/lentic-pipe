"""Job-backed scientific workflow adapter registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol, cast, get_args

from src.api.config import api_workspace
from src.api.models.run import ModelType
from src.api.schemas.dataset import WorkflowName
from src.api.schemas.run import (
    RunExecutionResponse,
    RunPlanArtifact,
    RunPlanRequest,
    RunPlanResponse,
    RunResultSummaryResponse,
)
from src.api.services.run_artifacts import summarize_run_results
from src.api.services.run_executor import execute_run_plan
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import run_plan_dir, save_run_execution, save_run_plan

ADAPTER_INTERFACE_VERSION = "job_adapter_interface_v1"
_KNOWN_WORKFLOWS = frozenset(str(name) for name in get_args(WorkflowName))
_PIPE_GRUD_REFERENCE_PROFILE = "adaptive_wqp_focused"
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
    """Artifact-backed PIPE-GRU-D adapter for the reviewed adaptive reference profile."""

    adapter_id = "pipe_grud_reference_workflow_v0"
    interface_version = ADAPTER_INTERFACE_VERSION
    supported_workflows = frozenset({"pipe_grud"})

    def validate_preconditions(self, job: ScientificWorkflowJob) -> None:
        if job.workflow not in self.supported_workflows:
            raise UnsupportedScientificWorkflowError(
                f"Workflow '{job.workflow}' is not supported by adapter '{self.adapter_id}'."
            )
        execution_mode = str(job.parameters.get("execution_mode", ""))
        if execution_mode != "artifact_reference":
            raise ScientificWorkflowAdapterError(
                "PIPE-GRU-D adapter v0 is artifact-backed only. Set "
                "parameters.execution_mode='artifact_reference' to validate the reviewed "
                "adaptive reference profile. Dataset-specific PIPE inference is not wired yet."
            )
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
        if not plan.executable:
            blocker_messages = [issue.message for issue in plan.blockers]
            raise ScientificWorkflowAdapterError(
                "PIPE-GRU-D workflow is not executable for this dataset: "
                + "; ".join(blocker_messages)
            )
        return plan

    def execute(self, job: ScientificWorkflowJob, plan: RunPlanResponse) -> RunExecutionResponse:
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

    def collect_artifacts(
        self,
        job: ScientificWorkflowJob,
        plan: RunPlanResponse,
        execution: RunExecutionResponse,
    ) -> RunResultSummaryResponse:
        manifest_path = run_plan_dir(plan.plan_id) / "pipe_grud_run_manifest.json"
        summaries: dict[str, object] = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
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


_ADAPTERS: tuple[ScientificWorkflowAdapter, ...] = (
    LocalDeterministicWorkflowAdapter(),
    PipeGrudReferenceWorkflowAdapter(),
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
