from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.session import SessionStatus


class SessionCreateRequest(BaseModel):
    category_id: UUID


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    text: str
    question_type: str
    order: int
    created_at: datetime
    updated_at: datetime


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    specialist_id: UUID
    category_id: UUID
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class SessionWithQuestionsRead(SessionRead):
    questions: list[QuestionRead] = []


class SubmitAnswerRequest(BaseModel):
    question_id: UUID
    response_text: str

    @field_validator("response_text")
    @classmethod
    def response_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("response_text must not be blank")
        return v


class SubmitAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    question_id: UUID
    created_at: datetime
    updated_at: datetime
