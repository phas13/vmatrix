"""add system_settings table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("promotion_threshold", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("default_competency_domain", sa.String(100), nullable=False, server_default="DevOps"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_system_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO system_settings (id, promotion_threshold, default_competency_domain, created_at, updated_at) "
        "VALUES (1, 90, 'DevOps', now(), now())"
    )


def downgrade() -> None:
    op.drop_table("system_settings")
