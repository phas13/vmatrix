from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.matrix import MatrixStatus


class SubItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    name: str
    description: str
    order: int
    is_flagged: bool
    flag_note: str | None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    matrix_id: UUID
    name: str
    description: str
    order: int
    sub_items: list[SubItemRead]


class MatrixRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    specialist_id: UUID
    domain: str
    status: MatrixStatus
    created_at: datetime
    updated_at: datetime
    categories: list[CategoryRead]
