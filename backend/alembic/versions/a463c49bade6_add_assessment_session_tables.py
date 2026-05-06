"""add assessment session tables

Revision ID: a463c49bade6
Revises: f281bc1fa13f
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "a463c49bade6"
down_revision = "f281bc1fa13f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("specialist_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["specialist_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["competency_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_specialist_id", "assessment_sessions", ["specialist_id"])
    op.create_index("ix_sessions_category_id", "assessment_sessions", ["category_id"])

    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_session_id", "assessment_questions", ["session_id"])

    op.create_table(
        "assessment_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column("ai_rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_id"], ["assessment_questions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "question_id", name="uq_responses_session_question"),
    )
    op.create_index("ix_responses_session_id", "assessment_responses", ["session_id"])
    op.create_index("ix_responses_question_id", "assessment_responses", ["question_id"])

    op.create_table(
        "session_disputes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("specialist_explanation", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cm_decision", sa.String(length=20), nullable=True),
        sa.Column("cm_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cm_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cm_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disputes_session_id", "session_disputes", ["session_id"])
    op.create_index("ix_disputes_cm_id", "session_disputes", ["cm_id"])

    op.create_table(
        "specialist_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("specialist_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["specialist_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["competency_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specialist_id", "category_id", name="uq_specialist_scores_spec_cat"),
    )
    op.create_index("ix_specialist_scores_specialist_id", "specialist_scores", ["specialist_id"])
    op.create_index("ix_specialist_scores_category_id", "specialist_scores", ["category_id"])


def downgrade() -> None:
    op.drop_table("specialist_scores")
    op.drop_table("session_disputes")
    op.drop_table("assessment_responses")
    op.drop_table("assessment_questions")
    op.drop_table("assessment_sessions")
