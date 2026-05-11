import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
