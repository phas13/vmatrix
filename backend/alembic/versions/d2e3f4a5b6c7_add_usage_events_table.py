"""add_usage_events_table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTION_VALUES = (
    "user_login",
    "session_created",
    "answer_submitted",
    "session_evaluated",
    "dispute_submitted",
    "dispute_resolved",
    "promotion_approved",
    "promotion_rejected",
    "matrix_approved",
    "matrix_update_approved",
    "matrix_update_rejected",
)

_RESOURCE_TYPE_VALUES = (
    "session",
    "dispute",
    "promotion",
    "matrix",
    "matrix_proposal",
)


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action_type",
            sa.Enum(*_ACTION_VALUES, name="usageeventaction", native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column(
            "resource_type",
            sa.Enum(*_RESOURCE_TYPE_VALUES, name="usageeventresourcetype", native_enum=False, length=50),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])
    op.create_index("ix_usage_events_action_type", "usage_events", ["action_type"])
    op.create_index("ix_usage_events_resource_id", "usage_events", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_resource_id", table_name="usage_events")
    op.drop_index("ix_usage_events_action_type", table_name="usage_events")
    op.drop_index("ix_usage_events_user_id", table_name="usage_events")
    op.drop_table("usage_events")
