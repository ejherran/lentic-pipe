import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.api.database import Base
from src.api.models.base import UUIDPrimaryKey, utcnow
from src.api.models.types import JsonbType


class AuditAction(str, enum.Enum):
    login_success = "login_success"
    login_failure = "login_failure"
    user_registered = "user_registered"
    password_changed = "password_changed"
    password_reset = "password_reset"
    api_key_created = "api_key_created"
    api_key_deleted = "api_key_deleted"
    role_changed = "role_changed"
    experiment_deleted = "experiment_deleted"
    user_deleted = "user_deleted"


class AuditLog(UUIDPrimaryKey, Base):
    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False, index=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
