import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult

from src.api.config import settings
from src.api.core.metrics import runs_pending, runs_running, simulations_pending, simulations_running
from src.api.database import AsyncSessionLocal
from src.api.models.audit_log import AuditLog
from src.api.models.email_code import EmailCode
from src.api.models.run import Run, RunStatus
from src.api.models.simulation import Simulation, SimulationStatus
from src.api.models.user import RefreshToken
from src.api.tasks.broker import broker

_logger = logging.getLogger(__name__)


async def purge_expired_tokens_now() -> int:
    """Delete expired refresh token rows. Returns count of deleted rows."""
    async with AsyncSessionLocal() as db:
        result = cast(
            CursorResult,
            await db.execute(
                delete(RefreshToken).where(
                    RefreshToken.expires_at < datetime.now(timezone.utc)
                )
            ),
        )
        await db.commit()
    return int(result.rowcount)


async def purge_expired_email_codes() -> int:
    """Delete used or expired email codes. Returns count deleted."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = cast(
            CursorResult,
            await db.execute(
                delete(EmailCode).where(
                    (EmailCode.expires_at < now) | (EmailCode.used_at.is_not(None))
                )
            ),
        )
        await db.commit()
    deleted = int(result.rowcount)
    _logger.info("purge_expired_email_codes", extra={"deleted": deleted})
    return deleted


async def purge_old_audit_log() -> int:
    """Delete audit log rows older than AUDIT_LOG_RETAIN_DAYS. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.AUDIT_LOG_RETAIN_DAYS)
    async with AsyncSessionLocal() as db:
        result = cast(
            CursorResult,
            await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff)),
        )
        await db.commit()
    deleted = int(result.rowcount)
    _logger.info("purge_old_audit_log", extra={"deleted": deleted, "retain_days": settings.AUDIT_LOG_RETAIN_DAYS})
    return deleted


async def refresh_queue_metrics() -> None:
    async with AsyncSessionLocal() as db:
        runs_pending.set(
            (await db.execute(select(func.count()).select_from(Run).where(Run.status == RunStatus.pending))).scalar_one()
        )
        runs_running.set(
            (await db.execute(select(func.count()).select_from(Run).where(Run.status == RunStatus.running))).scalar_one()
        )
        simulations_pending.set(
            (await db.execute(select(func.count()).select_from(Simulation).where(Simulation.status == SimulationStatus.pending))).scalar_one()
        )
        simulations_running.set(
            (await db.execute(select(func.count()).select_from(Simulation).where(Simulation.status == SimulationStatus.running))).scalar_one()
        )


@broker.task
async def purge_expired_tokens() -> dict:
    """Taskiq task wrapper — can also be triggered manually via the queue."""
    deleted = await purge_expired_tokens_now()
    _logger.info("purge_expired_tokens completed", extra={"deleted": deleted})
    return {"deleted": deleted}
