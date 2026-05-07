from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    EVALUATION_PENDING = "evaluation_pending"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class AssessmentSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assessment_sessions"

    specialist_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("competency_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, native_enum=False, length=30,
               values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SessionStatus.IN_PROGRESS,
    )
    final_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    areas_for_growth: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[list["AssessmentQuestion"]] = relationship(back_populates="session")
    responses: Mapped[list["AssessmentResponse"]] = relationship(back_populates="session")
    dispute: Mapped["SessionDispute | None"] = relationship(back_populates="session", uselist=False)


class AssessmentQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assessment_questions"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "theoretical" | "practical"
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    session: Mapped["AssessmentSession"] = relationship(back_populates="questions")


class AssessmentResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assessment_responses"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)   # Fernet-encrypted
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 0-100
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)     # Fernet-encrypted
    session: Mapped["AssessmentSession"] = relationship(back_populates="responses")

    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_responses_session_question"),
    )


class SessionDispute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "session_disputes"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[DisputeStatus] = mapped_column(
        SAEnum(DisputeStatus, native_enum=False, length=20,
               values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DisputeStatus.OPEN,
    )
    specialist_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cm_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)   # "upheld" | "overridden"
    cm_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cm_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session: Mapped["AssessmentSession"] = relationship(back_populates="dispute")


class SpecialistScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks per-category competency scores for each specialist.

    Named SpecialistScore (not SpecialistLevel) to avoid collision with the
    SpecialistLevel enum in models/user.py which is exported as SpecialistLevel.
    """
    __tablename__ = "specialist_scores"

    specialist_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("competency_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)   # 0-100
    last_assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("specialist_id", "category_id", name="uq_specialist_scores_spec_cat"),
    )
