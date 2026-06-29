"""improvements round 2: cancelled status, api key scopes, notification prefs, password reset purpose

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-05-16 00:00:02.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    if is_pg:
        op.execute(sa.text("ALTER TYPE run_status ADD VALUE IF NOT EXISTS 'cancelled'"))
        op.execute(sa.text("ALTER TYPE simulation_status ADD VALUE IF NOT EXISTS 'cancelled'"))
        op.execute(sa.text("ALTER TYPE email_code_purpose ADD VALUE IF NOT EXISTS 'password_reset'"))
        op.execute(sa.text(
            "CREATE TYPE api_key_scope AS ENUM ('full', 'read_only', 'predictions', 'simulations')"
        ))

    op.add_column(
        "api_keys",
        sa.Column(
            "scope",
            sa.Enum("full", "read_only", "predictions", "simulations",
                    name="api_key_scope", create_type=False),
            nullable=False,
            server_default="full",
        ),
    )

    for col in (
        "notify_on_run_completed",
        "notify_on_run_failed",
        "notify_on_simulation_completed",
        "notify_on_simulation_failed",
    ):
        op.add_column(
            "users",
            sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    for col in (
        "notify_on_run_completed",
        "notify_on_run_failed",
        "notify_on_simulation_completed",
        "notify_on_simulation_failed",
    ):
        op.drop_column("users", col)

    op.drop_column("api_keys", "scope")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS api_key_scope"))
