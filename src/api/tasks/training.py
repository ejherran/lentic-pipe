"""Training and scientific workflow task for Run jobs."""

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from src.api.core.email import send_email
from src.api.database import AsyncSessionLocal
from src.api.models.run import ModelType, Run, RunStatus
from src.api.models.user import User
from src.api.schemas.dataset import WorkflowName
from src.api.schemas.run import RunPlanRequest
from src.api.services.run_artifacts import summarize_run_results
from src.api.services.run_executor import execute_run_plan
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import save_run_plan
from src.api.tasks.broker import broker

_SCIENTIFIC_WORKFLOWS = {
    "canonical_observations",
    "monthly_panel",
    "fuzzy_state",
    "pipe_grud",
    "pipe_neural_ode",
    "mifal_ed_t2",
    "counterfactual_planning",
}


async def _run_model_or_workflow(model_type: ModelType, config: dict | None) -> dict[str, Any]:
    """Run a configured scientific workflow or return an explicit placeholder."""

    if config and config.get("dataset_id") and (config.get("workflow") or config.get("science_workflow")):
        return _run_scientific_workflow(config)
    return {
        "status": "stub",
        "model_type": model_type,
        "note": (
            "No dataset_id/workflow pair was supplied. The async job lifecycle is active, "
            "but this run did not request a wired scientific workflow."
        ),
        "metrics": {
            "horizon_30": {"pr_auc": None, "brier": None, "picp": None},
            "horizon_60": {"pr_auc": None, "brier": None, "picp": None},
            "horizon_90": {"pr_auc": None, "brier": None, "picp": None},
        },
    }


def _run_scientific_workflow(config: dict) -> dict[str, Any]:
    """Execute the existing deterministic scientific workflow inside a job."""

    workflow = str(config.get("workflow") or config.get("science_workflow"))
    if workflow not in _SCIENTIFIC_WORKFLOWS:
        raise ValueError(f"Unsupported scientific workflow: {workflow}")
    workflow_name = cast(WorkflowName, workflow)
    parameters = config.get("parameters")
    plan_request = RunPlanRequest(
        dataset_id=str(config["dataset_id"]),
        workflow=workflow_name,
        parameters=parameters if isinstance(parameters, dict) else {},
    )
    plan = save_run_plan(plan_run_request(plan_request))
    if not plan.executable:
        blocker_messages = [issue.message for issue in plan.blockers]
        raise ValueError(
            "Scientific workflow is not executable for this dataset: "
            + "; ".join(blocker_messages)
        )
    execution = execute_run_plan(plan.plan_id)
    summary = summarize_run_results(plan.plan_id)
    return {
        "status": "completed",
        "adapter": "local_scientific_workflow_v0",
        "plan": plan.model_dump(mode="json"),
        "execution": execution.model_dump(mode="json"),
        "summary": summary.model_dump(mode="json"),
        "metrics": {
            "row_counts": execution.row_counts,
            "workflow": workflow,
        },
    }


@broker.task(timeout=300, max_retries=3)
async def train_model_task(run_id: str, request_id: str = "") -> None:
    async with AsyncSessionLocal() as db:
        cursor = cast(
            CursorResult[Any],
            await db.execute(
                update(Run)
                .where(Run.id == uuid.UUID(run_id), Run.status == RunStatus.pending)
                .values(status=RunStatus.running, started_at=datetime.now(timezone.utc))
            ),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return

        run: Run | None = await db.get(Run, uuid.UUID(run_id))
        if not run:
            return

        try:
            results = await _run_model_or_workflow(run.model_type, run.config)
            # Re-read from DB — user may have cancelled while the job was running.
            await db.refresh(run)
            if run.status == RunStatus.cancelled:
                return
            run.status = RunStatus.completed
            run.results = results
            run.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            await db.refresh(run)
            if run.status == RunStatus.cancelled:
                return
            run.status = RunStatus.failed
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)

        final_status = run.status
        error_message = run.error_message
        run_name = run.name or str(run.id)
        created_by = run.created_by
        await db.commit()

    async with AsyncSessionLocal() as db:
        user: User | None = await db.get(User, created_by)
        if not user or not user.email_verified:
            return
        if final_status == RunStatus.completed and user.notify_on_run_completed:
            await send_email(
                to=user.email,
                subject=f"Training run '{run_name}' completed",
                body_text=(
                    f"Your training run '{run_name}' has completed successfully.\n\n"
                    "You can retrieve the results via the Lentic API."
                ),
                body_html=(
                    f"<p>Your training run <strong>{run_name}</strong> has completed successfully.</p>"
                    "<p>You can retrieve the results via the Lentic API.</p>"
                ),
            )
        elif final_status == RunStatus.failed and user.notify_on_run_failed:
            await send_email(
                to=user.email,
                subject=f"Training run '{run_name}' failed",
                body_text=(
                    f"Your training run '{run_name}' has failed.\n\n"
                    f"Error: {error_message or 'Unknown error'}\n\n"
                    "Please check your run configuration and try again."
                ),
                body_html=(
                    f"<p>Your training run <strong>{run_name}</strong> has failed.</p>"
                    f"<p>Error: {error_message or 'Unknown error'}</p>"
                    "<p>Please check your run configuration and try again.</p>"
                ),
            )
