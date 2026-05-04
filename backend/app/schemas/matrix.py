from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.matrix import MatrixStatus


class SubItemFlagRequest(BaseModel):
    note: str | None = None


class SubItemEditRequest(BaseModel):
    id: UUID
    name: str
    description: str


class MatrixApproveRequest(BaseModel):
    sub_item_edits: list[SubItemEditRequest] = []
    sub_items_to_remove: list[UUID] = []


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
    approved_by_id: UUID | None = None
    approved_at: datetime | None = None
    cm_changes: dict[str, Any] | None = None
