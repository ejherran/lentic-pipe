import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from src.api.core.dependencies import CurrentUser, DBDep, require_system_role
from src.api.models.audit_log import AuditAction, AuditLog
from src.api.models.run import Run, RunStatus
from src.api.models.simulation import Simulation, SimulationStatus
from src.api.models.user import SystemRole
from src.api.schemas.common import Page

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminDep = require_system_role(SystemRole.admin)

_ADMIN_ONLY = "Requires `system_role: admin`."


class QueueStatsResponse(BaseModel):
    runs: dict[str, int]
    simulations: dict[str, int]


class AuditLogEntry(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: AuditAction
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    detail: dict[str, Any] | None
    created_at: datetime


@router.get(
    "/audit-log",
    response_model=Page[AuditLogEntry],
    dependencies=[AdminDep],
    summary="List audit log entries",
    description=(
        f"Paginated audit log of sensitive operations system-wide. {_ADMIN_ONLY}\n\n"
        "**Recorded actions:** `login_success`, `login_failure`, `user_registered`, "
        "`password_changed`, `password_reset`, `api_key_created`, `api_key_deleted`, "
        "`role_changed`, `experiment_deleted`, `user_deleted`.\n\n"
        "**Filters:** `?user_id=`, `?action=`, ordered by `created_at` descending."
    ),
)
async def list_audit_log(
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based offset"),
    user_id: uuid.UUID | None = Query(None, description="Filter by user UUID"),
    action: AuditAction | None = Query(None, description="Filter by action type"),
):
    base = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if user_id is not None:
        base = base.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        base = base.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)

    total = (await db.execute(count_stmt)).scalar_one()
    items = list(
        (await db.execute(base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/queue",
    response_model=QueueStatsResponse,
    dependencies=[AdminDep],
    summary="Job queue statistics",
    description=(
        f"Per-status counts for training runs and simulations system-wide. {_ADMIN_ONLY}\n\n"
        "Useful for monitoring the Taskiq worker queue depth without scraping Prometheus."
    ),
)
async def queue_stats(db: DBDep):
    run_rows = (
        await db.execute(
            select(Run.status, func.count().label("n"))
            .group_by(Run.status)
        )
    ).all()
    sim_rows = (
        await db.execute(
            select(Simulation.status, func.count().label("n"))
            .group_by(Simulation.status)
        )
    ).all()

    runs = {row.status: row.n for row in run_rows}
    sims = {row.status: row.n for row in sim_rows}

    all_run_statuses = [s.value for s in RunStatus]
    all_sim_statuses = [s.value for s in SimulationStatus]

    return QueueStatsResponse(
        runs={s: runs.get(s, 0) for s in all_run_statuses},
        simulations={s: sims.get(s, 0) for s in all_sim_statuses},
    )
