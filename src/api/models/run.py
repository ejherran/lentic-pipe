import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.api.database import Base
from src.api.models.base import UUIDPrimaryKey, utcnow
from src.api.models.types import JsonbType


class ModelType(str, enum.Enum):
    pipe_grud = "PIPE_GRUD"
    pipe_neural_ode = "PIPE_NEURAL_ODE"
    mifal = "MIFAL"
    baseline_constant = "BASELINE_CONSTANT"
    baseline_logistic = "BASELINE_LOGISTIC"
    baseline_rf = "BASELINE_RF"
    baseline_gb = "BASELINE_GB"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Run(UUIDPrimaryKey, Base):
    __tablename__ = "runs"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_type: Mapped[ModelType] = mapped_column(
        Enum(ModelType, name="model_type"), nullable=False
    )
    config: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.pending, index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    results: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="runs")  # noqa: F821


from src.api.models.experiment import Experiment  # noqa: E402, F401
