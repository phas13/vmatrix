"""add evaluation fields to sessions

Revision ID: b1c2d3e4f5a6
Revises: a463c49bade6
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a463c49bade6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment_sessions", sa.Column("final_score", sa.Integer(), nullable=True))
    op.add_column("assessment_sessions", sa.Column("previous_score", sa.Integer(), nullable=True))
    op.add_column("assessment_sessions", sa.Column("strengths", sa.Text(), nullable=True))
    op.add_column("assessment_sessions", sa.Column("areas_for_growth", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessment_sessions", "areas_for_growth")
    op.drop_column("assessment_sessions", "strengths")
    op.drop_column("assessment_sessions", "previous_score")
    op.drop_column("assessment_sessions", "final_score")
