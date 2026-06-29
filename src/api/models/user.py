import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.api.database import Base
from src.api.models.base import TimestampMixin, UUIDPrimaryKey, utcnow


class SystemRole(str, enum.Enum):
    admin = "admin"
    researcher = "researcher"
    viewer = "viewer"


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role"), nullable=False, default=SystemRole.researcher
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_on_run_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_on_run_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_on_simulation_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_on_simulation_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    collaborations: Mapped[list["ExperimentCollaborator"]] = relationship(  # noqa: F821
        "ExperimentCollaborator", foreign_keys="ExperimentCollaborator.user_id",
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(UUIDPrimaryKey, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


# Import here to avoid circular imports
from src.api.models.experiment import ExperimentCollaborator  # noqa: E402, F401
