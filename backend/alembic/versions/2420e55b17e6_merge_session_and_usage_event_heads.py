"""merge_session_and_usage_event_heads

Revision ID: 2420e55b17e6
Revises: b1c2d3e4f5a6, d2e3f4a5b6c7
Create Date: 2026-06-01 09:01:56.147210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2420e55b17e6'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3e4f5a6', 'd2e3f4a5b6c7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
