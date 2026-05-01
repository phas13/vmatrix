from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LLMOperation(str, enum.Enum):
    MATRIX_GENERATION = "matrix_generation"
    QUESTION_GENERATION = "question_generation"
    RESPONSE_EVALUATION = "response_evaluation"
    MATRIX_MONITORING = "matrix_monitoring"


class LLMCallLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "llm_call_logs"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[LLMOperation] = mapped_column(
        SAEnum(
            LLMOperation,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    specialist_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
