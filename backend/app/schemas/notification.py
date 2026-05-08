from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: NotificationType
    content: str
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
