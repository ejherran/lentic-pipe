import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.api.database import Base
from src.api.models.base import UUIDPrimaryKey, utcnow
from src.api.models.run import ModelType
from src.api.models.types import JsonbType


class Prediction(UUIDPrimaryKey, Base):
    __tablename__ = "predictions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_type: Mapped[ModelType] = mapped_column(nullable=False)
    site_id: Mapped[str] = mapped_column(String(100), nullable=False)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    input_variables: Mapped[dict] = mapped_column(JsonbType, nullable=False)
    result: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
