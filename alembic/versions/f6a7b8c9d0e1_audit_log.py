"""audit_log table and audit_action enum

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-05-16 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTIONS = [
    "login_success",
    "login_failure",
    "password_changed",
    "password_reset",
    "api_key_created",
    "api_key_deleted",
    "role_changed",
    "experiment_deleted",
    "user_deleted",
]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "CREATE TYPE audit_action AS ENUM ("
            + ", ".join(f"'{v}'" for v in _AUDIT_ACTIONS)
            + ")"
        )
        action_col = sa.Column(
            "action",
            sa.Enum(*_AUDIT_ACTIONS, name="audit_action"),
            nullable=False,
        )
    else:
        action_col = sa.Column("action", sa.String(64), nullable=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        action_col,
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS audit_action")
