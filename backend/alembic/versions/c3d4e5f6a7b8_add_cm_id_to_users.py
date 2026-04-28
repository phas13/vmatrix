"""add_cm_id_to_users

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-28 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("cm_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_users_cm_id", "users", "users", ["cm_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_users_cm_id", "users", ["cm_id"])


def downgrade() -> None:
    op.drop_index("ix_users_cm_id", table_name="users")
    op.drop_constraint("fk_users_cm_id", "users", type_="foreignkey")
    op.drop_column("users", "cm_id")
