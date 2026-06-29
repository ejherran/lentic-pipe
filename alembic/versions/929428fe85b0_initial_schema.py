"""Initial schema — all tables.

Revision ID: 929428fe85b0
Revises:
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "929428fe85b0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────────
    system_role = postgresql.ENUM(
        "admin", "researcher", "viewer", name="system_role", create_type=True
    )
    experiment_status = postgresql.ENUM(
        "draft", "active", "archived", name="experiment_status", create_type=True
    )
    collaborator_role = postgresql.ENUM(
        "owner", "editor", "viewer", name="collaborator_role", create_type=True
    )
    model_type = postgresql.ENUM(
        "PIPE_GRUD",
        "PIPE_NEURAL_ODE",
        "MIFAL",
        "BASELINE_CONSTANT",
        "BASELINE_LOGISTIC",
        "BASELINE_RF",
        "BASELINE_GB",
        name="model_type",
        create_type=True,
    )
    run_status = postgresql.ENUM(
        "pending", "running", "completed", "failed", name="run_status", create_type=True
    )
    simulation_status = postgresql.ENUM(
        "pending", "running", "completed", "failed", name="simulation_status", create_type=True
    )

    system_role.create(op.get_bind(), checkfirst=True)
    experiment_status.create(op.get_bind(), checkfirst=True)
    collaborator_role.create(op.get_bind(), checkfirst=True)
    model_type.create(op.get_bind(), checkfirst=True)
    run_status.create(op.get_bind(), checkfirst=True)
    simulation_status.create(op.get_bind(), checkfirst=True)

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column(
            "system_role",
            sa.Enum("admin", "researcher", "viewer", name="system_role", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── refresh_tokens ─────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jti", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)

    # ── experiments ────────────────────────────────────────────────────────────
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="experiment_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_experiments_created_by", "experiments", ["created_by"])

    # ── experiment_collaborators ───────────────────────────────────────────────
    op.create_table(
        "experiment_collaborators",
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.Enum("owner", "editor", "viewer", name="collaborator_role", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "invited_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── datasets ───────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_datasets_experiment_id", "datasets", ["experiment_id"])

    # ── runs ───────────────────────────────────────────────────────────────────
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "model_type",
            sa.Enum(
                "PIPE_GRUD",
                "PIPE_NEURAL_ODE",
                "MIFAL",
                "BASELINE_CONSTANT",
                "BASELINE_LOGISTIC",
                "BASELINE_RF",
                "BASELINE_GB",
                name="model_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="run_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_runs_experiment_id", "runs", ["experiment_id"])

    # ── predictions ────────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "model_type",
            sa.Enum(
                "PIPE_GRUD",
                "PIPE_NEURAL_ODE",
                "MIFAL",
                "BASELINE_CONSTANT",
                "BASELINE_LOGISTIC",
                "BASELINE_RF",
                "BASELINE_GB",
                name="model_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("site_id", sa.String(100), nullable=False),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("input_variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"])
    op.create_index("ix_predictions_experiment_id", "predictions", ["experiment_id"])

    # ── simulations ────────────────────────────────────────────────────────────
    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("site_id", sa.String(100), nullable=False),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("n_trajectories", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("scenario", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "completed", "failed",
                name="simulation_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_simulations_user_id", "simulations", ["user_id"])
    op.create_index("ix_simulations_experiment_id", "simulations", ["experiment_id"])


def downgrade() -> None:
    op.drop_table("simulations")
    op.drop_table("predictions")
    op.drop_table("runs")
    op.drop_table("datasets")
    op.drop_table("experiment_collaborators")
    op.drop_table("experiments")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS simulation_status")
    op.execute("DROP TYPE IF EXISTS run_status")
    op.execute("DROP TYPE IF EXISTS model_type")
    op.execute("DROP TYPE IF EXISTS collaborator_role")
    op.execute("DROP TYPE IF EXISTS experiment_status")
    op.execute("DROP TYPE IF EXISTS system_role")
