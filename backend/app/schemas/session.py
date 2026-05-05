from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.session import SessionStatus


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    specialist_id: UUID
    category_id: UUID
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
