"""make created_by nullable; add status indexes on runs and simulations

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    # Allow created_by to be NULL so ON DELETE SET NULL doesn't violate NOT NULL.
    if is_pg:
        op.alter_column("experiments", "created_by", nullable=True)
        op.alter_column("runs", "created_by", nullable=True)
        op.alter_column("datasets", "created_by", nullable=True)

    # Indexes on status columns — frequently used in WHERE and GROUP BY.
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_simulations_status", "simulations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_simulations_status", table_name="simulations")
    op.drop_index("ix_runs_status", table_name="runs")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.alter_column("experiments", "created_by", nullable=False)
        op.alter_column("runs", "created_by", nullable=False)
        op.alter_column("datasets", "created_by", nullable=False)
