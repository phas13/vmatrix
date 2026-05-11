import enum
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.user import SpecialistLevel
from app.schemas.pagination import PaginatedResponse
from app.schemas.session import CategoryScoreRead, SessionListItemRead


class SpecialistCardRead(BaseModel):
    """Slim card for team overview list."""
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    full_name: str
    specialist_level: SpecialistLevel | None
    overall_percentage: int
    last_activity_at: datetime | None


class SpecialistDetailRead(BaseModel):
    """Full detail for /cm/specialist/{id} page."""
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    full_name: str
    specialist_level: SpecialistLevel | None
    overall_percentage: int
    category_scores: list[CategoryScoreRead]
    sessions: PaginatedResponse[SessionListItemRead]


class PendingActionType(str, enum.Enum):
    DISPUTE = "dispute"
    PROMOTION = "promotion"
    MATRIX_APPROVAL = "matrix_approval"
    UPDATE_PROPOSAL = "update_proposal"


class PendingActionRead(BaseModel):
    """Single pending action item for the CM action queue."""
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    type: PendingActionType
    specialist_id: UUID
    specialist_name: str
    description: str
    date: datetime


class PendingActionsResponse(BaseModel):
    """Aggregated pending actions grouped by type."""
    model_config = ConfigDict(from_attributes=False)

    disputes: list[PendingActionRead]
    promotions: list[PendingActionRead]
    matrix_approvals: list[PendingActionRead]
    update_proposals: list[PendingActionRead]
    total: int


class DisputeDecision(str, enum.Enum):
    UPHELD = "upheld"
    OVERRIDDEN = "overridden"


class QuestionResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    question_id: UUID
    question_text: str
    question_type: str
    order: int
    response_text: str | None
    ai_rationale: str | None


class DisputeDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    session_id: UUID
    specialist_id: UUID
    specialist_name: str
    category_id: UUID
    category_name: str | None
    status: str
    specialist_explanation: str
    submitted_at: datetime
    cm_decision: str | None
    ai_score: int | None
    transcript: list[QuestionResponseItem]


class DisputeResolveRequest(BaseModel):
    decision: DisputeDecision
    cm_note: str | None = None
    override_score: int | None = None

    @model_validator(mode="after")
    def validate_override_fields(self) -> Self:
        if self.decision == DisputeDecision.OVERRIDDEN:
            if not self.cm_note or not self.cm_note.strip():
                raise ValueError("cm_note is required when decision is OVERRIDDEN")
            if self.override_score is None:
                raise ValueError("override_score is required when decision is OVERRIDDEN")
            if not (0 <= self.override_score <= 100):
                raise ValueError("override_score must be between 0 and 100")
        return self


class DisputeResolveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    status: str
    cm_decision: str
    cm_note: str | None
    resolved_at: datetime
    updated_score: int | None
