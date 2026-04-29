from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import SpecialistLevel, UserRole


class SpecialistSummary(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    cm_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    password: str = Field(min_length=8)
    specialist_level: SpecialistLevel | None = None
    cm_id: UUID | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: UserRole
    specialist_level: SpecialistLevel | None = None
    cm_id: UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
