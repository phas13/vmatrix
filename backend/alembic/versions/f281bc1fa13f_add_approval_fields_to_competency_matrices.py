"""add approval fields to competency_matrices

Revision ID: f281bc1fa13f
Revises: f6a7b8c9d0e1
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "f281bc1fa13f"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competency_matrices",
        sa.Column("approved_by_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "competency_matrices",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "competency_matrices",
        sa.Column("cm_changes", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_competency_matrices_approved_by_id",
        "competency_matrices",
        "users",
        ["approved_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_competency_matrices_approved_by_id", "competency_matrices", ["approved_by_id"])


def downgrade() -> None:
    op.drop_index("ix_competency_matrices_approved_by_id", table_name="competency_matrices")
    op.drop_constraint("fk_competency_matrices_approved_by_id", "competency_matrices", type_="foreignkey")
    op.drop_column("competency_matrices", "cm_changes")
    op.drop_column("competency_matrices", "approved_at")
    op.drop_column("competency_matrices", "approved_by_id")
