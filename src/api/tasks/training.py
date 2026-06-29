"""Training and scientific workflow task for Run jobs."""

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.email import send_email
from src.api.database import AsyncSessionLocal
from src.api.models.run import ModelType, Run, RunStatus
from src.api.models.user import User
from src.api.services.experiment_datasets import (
    config_requests_scientific_workflow,
    resolve_scientific_dataset_config,
)
from src.api.services.scientific_workflow_adapters import run_scientific_workflow_job
from src.api.tasks.broker import broker


async def _run_model_or_workflow(
    model_type: ModelType,
    config: dict[str, Any] | None,
    *,
    experiment_id: uuid.UUID | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Run a configured scientific workflow or return an explicit placeholder."""

    if config_requests_scientific_workflow(config):
        resolved_config = await resolve_scientific_dataset_config(
            config or {},
            experiment_id=experiment_id,
            db=db,
        )
        return run_scientific_workflow_job(model_type, resolved_config)
    return {
        "status": "stub",
        "model_type": model_type.value,
        "note": (
            "No dataset/workflow pair was supplied. The async job lifecycle is active, "
            "but this run did not request a registered scientific workflow adapter."
        ),
        "metrics": {
            "horizon_30": {"pr_auc": None, "brier": None, "picp": None},
            "horizon_60": {"pr_auc": None, "brier": None, "picp": None},
            "horizon_90": {"pr_auc": None, "brier": None, "picp": None},
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
            results = await _run_model_or_workflow(
                run.model_type,
                run.config,
                experiment_id=run.experiment_id,
                db=db,
            )
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
