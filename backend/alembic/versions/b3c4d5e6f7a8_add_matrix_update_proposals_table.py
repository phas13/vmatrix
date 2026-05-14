"""add matrix_update_proposals table

Revision ID: b3c4d5e6f7a8
Revises: f281bc1fa13f
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "f281bc1fa13f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matrix_update_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposed_change", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("matrix_id", sa.UUID(), sa.ForeignKey("competency_matrices.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="proposalstatus", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matrix_update_proposals_status", "matrix_update_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_matrix_update_proposals_status", table_name="matrix_update_proposals")
    op.drop_table("matrix_update_proposals")
