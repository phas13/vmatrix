from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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
    email: EmailStr = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    password: str = Field(min_length=8, max_length=72)
    specialist_level: SpecialistLevel | None = None
    cm_id: UUID | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("full_name must not be empty or whitespace-only")
        return stripped

    @model_validator(mode="after")
    def enforce_role_consistency(self) -> "UserCreate":
        if self.role == UserRole.SPECIALIST:
            if self.specialist_level is None:
                raise ValueError("specialist_level is required when role is SPECIALIST")
        else:
            # ADMIN, CM, HR cannot have specialist-specific fields
            if self.specialist_level is not None:
                raise ValueError(f"specialist_level is not allowed for role {self.role.value}")
            if self.cm_id is not None:
                raise ValueError(f"cm_id is not allowed for role {self.role.value}")
        return self


class UserUpdate(BaseModel):
    """Partial update schema — Story 2.2 exposes only cm_id reassignment."""
    cm_id: UUID | None


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
