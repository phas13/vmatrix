"""add competency matrix tables and llm_call_logs

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competency_matrices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("specialist_id", sa.UUID(), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["specialist_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specialist_id", name="uq_matrices_specialist_id"),
    )
    op.create_index("ix_competency_matrices_specialist_id", "competency_matrices", ["specialist_id"])

    op.create_table(
        "competency_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("matrix_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["matrix_id"], ["competency_matrices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competency_categories_matrix_id", "competency_categories", ["matrix_id"])

    op.create_table(
        "competency_sub_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("flag_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["category_id"], ["competency_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competency_sub_items_category_id", "competency_sub_items", ["category_id"])

    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("specialist_id", sa.UUID(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["specialist_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_call_logs_specialist_id", "llm_call_logs", ["specialist_id"])


def downgrade() -> None:
    op.drop_table("llm_call_logs")
    op.drop_index("ix_competency_sub_items_category_id", table_name="competency_sub_items")
    op.drop_table("competency_sub_items")
    op.drop_index("ix_competency_categories_matrix_id", table_name="competency_categories")
    op.drop_table("competency_categories")
    op.drop_index("ix_competency_matrices_specialist_id", table_name="competency_matrices")
    op.drop_table("competency_matrices")
