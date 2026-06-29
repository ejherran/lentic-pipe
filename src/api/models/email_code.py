import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.api.database import Base
from src.api.models.base import UUIDPrimaryKey, utcnow


class EmailCodePurpose(str, enum.Enum):
    verification = "verification"
    password_reset = "password_reset"


class EmailCode(UUIDPrimaryKey, Base):
    __tablename__ = "email_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    purpose: Mapped[EmailCodePurpose] = mapped_column(
        Enum(EmailCodePurpose, name="email_code_purpose"), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
