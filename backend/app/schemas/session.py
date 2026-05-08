from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import SpecialistLevel
from app.models.session import SessionStatus, DisputeStatus


class SessionDisputeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    status: DisputeStatus
    specialist_explanation: str
    submitted_at: datetime
    cm_decision: str | None = None
    cm_note: str | None = None
    resolved_at: datetime | None = None
    cm_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SubmitDisputeRequest(BaseModel):
    specialist_explanation: str = Field(..., max_length=10000)

    @field_validator("specialist_explanation")
    @classmethod
    def explanation_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("specialist_explanation must not be blank")
        return v


class SubmitDisputeResponse(SessionDisputeRead):
    pass



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


class ResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    question_id: UUID
    response_text: str
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


class EvaluateSessionResponse(BaseModel):
    session_id: UUID
    status: SessionStatus
    final_score: int
    previous_score: int | None
    level_percentage: int


class ResponseWithRationaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    question_id: UUID
    response_text: str
    ai_rationale: str | None
    created_at: datetime
    updated_at: datetime


class SessionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    specialist_id: UUID
    category_id: UUID
    category_name: str | None = None
    status: SessionStatus
    final_score: int | None
    previous_score: int | None
    level_percentage: int = 0
    strengths: str | None
    areas_for_growth: str | None
    questions: list[QuestionRead] = []
    responses: list[ResponseWithRationaleRead] = []
    dispute: SessionDisputeRead | None = None
    created_at: datetime
    updated_at: datetime


class CategoryScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: UUID
    category_name: str
    score: int | None
    previous_score: int | None
    last_assessed_at: datetime | None


class SpecialistDashboardRead(BaseModel):
    specialist_level: SpecialistLevel | None
    overall_percentage: int
    category_scores: list[CategoryScoreRead]
