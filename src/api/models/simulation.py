import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.api.database import Base
from src.api.models.base import UUIDPrimaryKey, utcnow
from src.api.models.types import JsonbType


class SimulationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Simulation(UUIDPrimaryKey, Base):
    __tablename__ = "simulations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    site_id: Mapped[str] = mapped_column(String(100), nullable=False)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    n_trajectories: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    scenario: Mapped[dict] = mapped_column(JsonbType, nullable=False)
    status: Mapped[SimulationStatus] = mapped_column(
        nullable=False, default=SimulationStatus.pending, index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
