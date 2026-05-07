from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session, require_csrf, require_role
from app.models.user import User, UserRole
from app.schemas.session import (
    EvaluateSessionResponse,
    SessionCreateRequest,
    SessionResultRead,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SubmitDisputeRequest,
    SubmitDisputeResponse,
)
from app.services import session_service

router = APIRouter()


@router.post("", status_code=200)
async def create_session(
    request: Request,
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.SPECIALIST)),
    _csrf: None = Depends(require_csrf),
) -> StreamingResponse:
    stream = await session_service.create_session_stream(
        specialist_id=current_user.id,
        category_id=body.category_id,
        db=db,
        current_user=current_user,
        instance=str(request.url.path),
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{session_id}", response_model=SessionResultRead)
async def get_session(
    request: Request,
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SessionResultRead:
    session = await session_service.get_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
        instance=str(request.url.path),
        load_dispute=True,
    )
    session.questions.sort(key=lambda q: q.order)
    return SessionResultRead.model_validate(session)


@router.post("/{session_id}/actions/evaluate", response_model=EvaluateSessionResponse, status_code=200)
async def evaluate_session(
    request: Request,
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.SPECIALIST)),
    _csrf: None = Depends(require_csrf),
) -> EvaluateSessionResponse:
    result = await session_service.evaluate_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
        instance=str(request.url.path),
    )
    return EvaluateSessionResponse(**result)


@router.post(
    "/{session_id}/actions/submit-dispute",
    response_model=SubmitDisputeResponse,
    status_code=201,
)
async def submit_dispute(
    request: Request,
    session_id: UUID,
    body: SubmitDisputeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.SPECIALIST)),
    _csrf: None = Depends(require_csrf),
) -> SubmitDisputeResponse:
    dispute = await session_service.submit_dispute(
        session_id=session_id,
        specialist_explanation=body.specialist_explanation,
        db=db,
        current_user=current_user,
        instance=str(request.url.path),
    )
    return SubmitDisputeResponse.model_validate(dispute)


@router.post("/{session_id}/actions/submit-answer", response_model=SubmitAnswerResponse, status_code=201)
async def submit_answer(
    request: Request,
    session_id: UUID,
    body: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.SPECIALIST)),
    _csrf: None = Depends(require_csrf),
) -> SubmitAnswerResponse:
    response = await session_service.submit_answer(
        session_id=session_id,
        question_id=body.question_id,
        response_text=body.response_text,
        db=db,
        current_user=current_user,
        instance=str(request.url.path),
    )
    return SubmitAnswerResponse.model_validate(response)
