import asyncio
import logging
import uuid

from src.api.database import AsyncSessionLocal
from src.api.models.audit_log import AuditAction, AuditLog

_logger = logging.getLogger(__name__)

_session_factory = AsyncSessionLocal


def fire_audit(
    action: AuditAction,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    detail: dict | None = None,
) -> None:
    task = asyncio.create_task(
        _write(action, user_id, resource_type, resource_id, ip_address, detail)
    )
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)


async def _write(
    action: AuditAction,
    user_id: uuid.UUID | None,
    resource_type: str | None,
    resource_id: str | None,
    ip_address: str | None,
    detail: dict | None,
) -> None:
    try:
        async with _session_factory() as db:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    detail=detail,
                )
            )
            await db.commit()
    except Exception:
        _logger.warning("audit_write_failed", extra={"action": action})
