import json
import logging
import time
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError, ProblemHTTPException
from app.core.security import decrypt_field, encrypt_field
from app.models.llm_call_log import LLMCallLog, LLMOperation
from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.session import AssessmentQuestion, AssessmentResponse, AssessmentSession, SessionStatus
from app.models.user import User
from app.providers.base import QuestionGenerationContext, SubItemInfo
from app.providers.factory import get_llm_provider
from app.services.prompt_builder import build_question_generation_prompt

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_SESSION = 10


# ─── Error helpers ────────────────────────────────────────────────────────────

def _llm_unavailable(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=503,
        detail={
            "type": "https://vmatrix.app/errors/llm-unavailable",
            "title": "LLM unavailable",
            "status": 503,
            "detail": "Assessment service is temporarily unavailable. Please try again.",
            "instance": instance,
        },
    )


def _session_not_found(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/session-not-found",
            "title": "Session not found",
            "status": 404,
            "detail": "Assessment session not found",
            "instance": instance,
        },
    )


def _matrix_not_approved(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/matrix-not-approved",
            "title": "Matrix not approved",
            "status": 422,
            "detail": "Assessment sessions can only be started for an approved competency matrix.",
            "instance": instance,
        },
    )


def _category_not_found(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/category-not-found",
            "title": "Category not found",
            "status": 404,
            "detail": "Competency category not found in specialist matrix.",
            "instance": instance,
        },
    )


def _session_conflict(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/session-conflict",
            "title": "Active session exists",
            "status": 409,
            "detail": "An assessment session for this category is already in progress.",
            "instance": instance,
        },
    )


def _answer_conflict(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/answer-conflict",
            "title": "Answer already submitted",
            "status": 409,
            "detail": "This question already has a submitted answer.",
            "instance": instance,
        },
    )


def _question_not_in_session(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/question-not-found",
            "title": "Question not found",
            "status": 404,
            "detail": "Question does not belong to this session.",
            "instance": instance,
        },
    )


def _session_not_in_progress(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/session-not-in-progress",
            "title": "Session not in progress",
            "status": 422,
            "detail": "Answers can only be submitted to an active (IN_PROGRESS) session.",
            "instance": instance,
        },
    )


# ─── create_session_stream (SSE generator) ─────────────────────────────────────

async def create_session_stream(
    specialist_id: UUID,
    category_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> AsyncGenerator[str, None]:
    """Creates session + generates questions, then yields SSE events.

    All DB work happens before the first yield so the DB session is safely
    committed before the generator hands control to the HTTP layer.
    """
    # 1. LLM pre-flight — fail before any DB writes if provider is down
    provider = get_llm_provider()
    try:
        await provider.health_check()
    except LLMUnavailableError:
        raise _llm_unavailable(instance)

    # 2. Load matrix — must be APPROVED
    matrix_result = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.specialist_id == specialist_id)
    )
    matrix = matrix_result.scalar_one_or_none()
    if matrix is None or matrix.status != MatrixStatus.APPROVED:
        raise _matrix_not_approved(instance)

    # 3. Load category + sub_items — must belong to this matrix
    cat_result = await db.execute(
        select(CompetencyCategory)
        .where(
            CompetencyCategory.id == category_id,
            CompetencyCategory.matrix_id == matrix.id,
        )
        .options(selectinload(CompetencyCategory.sub_items))
    )
    category = cat_result.scalar_one_or_none()
    if category is None:
        raise _category_not_found(instance)

    # 4. Conflict check — no concurrent IN_PROGRESS session for same specialist+category
    conflict_result = await db.execute(
        select(AssessmentSession).where(
            AssessmentSession.specialist_id == specialist_id,
            AssessmentSession.category_id == category_id,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        ).with_for_update(skip_locked=True)
    )
    if conflict_result.scalar_one_or_none() is not None:
        raise _session_conflict(instance)

    # 5. Build LLM context
    level = (current_user.specialist_level.value if current_user.specialist_level else "junior")
    sub_items = [
        SubItemInfo(name=si.name, description=si.description)
        for si in sorted(category.sub_items, key=lambda x: x.order)
    ]
    context = QuestionGenerationContext(
        specialist_id=specialist_id,
        category_name=category.name,
        category_description=category.description,
        sub_items=sub_items,
        level=level,
        num_questions=MAX_QUESTIONS_PER_SESSION,
    )
    prompt = build_question_generation_prompt(context)
    encrypted_prompt = encrypt_field(prompt)

    start = time.monotonic()
    llm_log = LLMCallLog(
        provider=settings.LLM_PROVIDER,
        operation=LLMOperation.QUESTION_GENERATION,
        specialist_id=specialist_id,
        request_payload=encrypted_prompt,
    )

    # 6. Call LLM
    try:
        questions_draft, latency_ms, tokens_used = await provider.generate_questions(context)
    except LLMUnavailableError as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.error = str(exc)
        await db.rollback()
        db.add(llm_log)
        await db.commit()
        raise _llm_unavailable(instance)

    if not questions_draft:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.error = "provider returned no questions"
        await db.rollback()
        db.add(llm_log)
        await db.commit()
        raise _llm_unavailable(instance)

    llm_log.latency_ms = latency_ms
    llm_log.tokens_used = tokens_used

    # 7. Persist session + questions in one transaction
    session = AssessmentSession(
        specialist_id=specialist_id,
        category_id=category_id,
        status=SessionStatus.IN_PROGRESS,
    )
    db.add(session)
    await db.flush()

    persisted_questions: list[AssessmentQuestion] = []
    for draft in questions_draft:
        q = AssessmentQuestion(
            session_id=session.id,
            text=draft.text,
            question_type=draft.question_type,
            order=draft.order,
        )
        db.add(q)
        persisted_questions.append(q)

    db.add(llm_log)
    await db.commit()
    await db.refresh(session)
    for q in persisted_questions:
        await db.refresh(q)

    # 8. Pre-compute all SSE event payloads (no more DB access after this point)
    session_event = json.dumps({
        "type": "session",
        "session_id": str(session.id),
        "category_name": category.name,
        "level": level,
        "total_questions": len(persisted_questions),
    })
    question_events = [
        json.dumps({
            "type": "question",
            "id": str(q.id),
            "session_id": str(session.id),
            "text": q.text,
            "question_type": q.question_type,
            "order": q.order,
            "created_at": q.created_at.isoformat(),
            "updated_at": q.updated_at.isoformat(),
        })
        for q in sorted(persisted_questions, key=lambda x: x.order)
    ]

    # 9. Yield SSE events (generator body — no DB access here)
    async def _generator() -> AsyncGenerator[str, None]:
        yield f"data: {session_event}\n\n"
        for qe in question_events:
            yield f"data: {qe}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return _generator()


# ─── get_session ───────────────────────────────────────────────────────────────

async def get_session(
    session_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> AssessmentSession:
    # Specialists can only see their own sessions. CMs and Admins can see any.
    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .options(
            selectinload(AssessmentSession.questions),
            selectinload(AssessmentSession.responses),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise _session_not_found(instance)

    # Authorization check
    if current_user.role == "specialist" and session.specialist_id != current_user.id:
        raise _session_not_found(instance)

    # Decrypt responses if any
    for resp in session.responses:
        if resp.response_text:
            resp.response_text = decrypt_field(resp.response_text)

    return session


# ─── submit_answer ─────────────────────────────────────────────────────────────

async def submit_answer(
    session_id: UUID,
    question_id: UUID,
    response_text: str,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> AssessmentResponse:
    sess_result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .with_for_update()
    )
    session = sess_result.scalar_one_or_none()
    if session is None or session.specialist_id != current_user.id:
        raise _session_not_found(instance)
    if session.status != SessionStatus.IN_PROGRESS:
        raise _session_not_in_progress(instance)

    q_result = await db.execute(
        select(AssessmentQuestion).where(
            AssessmentQuestion.id == question_id,
            AssessmentQuestion.session_id == session_id,
        )
    )
    if q_result.scalar_one_or_none() is None:
        raise _question_not_in_session(instance)

    dup_result = await db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.session_id == session_id,
            AssessmentResponse.question_id == question_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise _answer_conflict(instance)

    response = AssessmentResponse(
        session_id=session_id,
        question_id=question_id,
        response_text=encrypt_field(response_text),
    )
    db.add(response)
    await db.commit()
    await db.refresh(response)
    return response
