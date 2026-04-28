from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpecialistSummary(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    cm_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)
