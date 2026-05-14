from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UsageEventAction(str, enum.Enum):
    USER_LOGIN = "user_login"
    SESSION_CREATED = "session_created"
    ANSWER_SUBMITTED = "answer_submitted"
    SESSION_EVALUATED = "session_evaluated"
    DISPUTE_SUBMITTED = "dispute_submitted"
    DISPUTE_RESOLVED = "dispute_resolved"
    PROMOTION_APPROVED = "promotion_approved"
    PROMOTION_REJECTED = "promotion_rejected"
    MATRIX_APPROVED = "matrix_approved"
    MATRIX_UPDATE_APPROVED = "matrix_update_approved"
    MATRIX_UPDATE_REJECTED = "matrix_update_rejected"


class UsageEventResourceType(str, enum.Enum):
    SESSION = "session"
    DISPUTE = "dispute"
    PROMOTION = "promotion"
    MATRIX = "matrix"
    MATRIX_PROPOSAL = "matrix_proposal"


class UsageEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_events"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_type: Mapped[UsageEventAction] = mapped_column(
        SAEnum(
            UsageEventAction,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    resource_type: Mapped[UsageEventResourceType | None] = mapped_column(
        SAEnum(
            UsageEventResourceType,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
