import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.api.database import Base
from src.api.models.base import TimestampMixin, UUIDPrimaryKey, utcnow
from src.api.models.types import JsonbType


class ExperimentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class CollaboratorRole(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class Experiment(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "experiments"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experiment_status"),
        nullable=False,
        default=ExperimentStatus.draft,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    collaborators: Mapped[list["ExperimentCollaborator"]] = relationship(
        "ExperimentCollaborator",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset", back_populates="experiment", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship(  # noqa: F821
        "Run", back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentCollaborator(Base):
    __tablename__ = "experiment_collaborators"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[CollaboratorRole] = mapped_column(
        Enum(CollaboratorRole, name="collaborator_role"), nullable=False
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="collaborators")
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[user_id], back_populates="collaborations"
    )
    invited_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[invited_by_id]
    )


class Dataset(UUIDPrimaryKey, Base):
    __tablename__ = "datasets"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JsonbType, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="datasets")


from src.api.models.run import Run  # noqa: E402, F401
from src.api.models.user import User  # noqa: E402, F401
