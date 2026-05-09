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
