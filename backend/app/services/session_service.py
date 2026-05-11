import json
import logging
import math
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError, ProblemHTTPException
from app.core.security import decrypt_field, encrypt_field
from app.models.llm_call_log import LLMCallLog, LLMOperation
from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.notification import Notification, NotificationType
from app.models.session import (
    AssessmentQuestion,
    AssessmentResponse,
    AssessmentSession,
    DisputeStatus,
    SessionDispute,
    SessionStatus,
    SpecialistScore,
)
from app.models.user import User, UserRole
from app.providers.base import QAEntry, QuestionGenerationContext, ResponseEvaluationContext, SubItemInfo
from app.providers.factory import get_llm_provider
from app.services.prompt_builder import build_question_generation_prompt, build_response_evaluation_prompt

from app.schemas.pagination import PaginatedResponse
from app.schemas.session import SessionDisputeRead, SessionListItemRead

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


def _forbidden_access(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=403,
        detail={
            "type": "https://vmatrix.app/errors/forbidden",
            "title": "Forbidden",
            "status": 403,
            "detail": "You do not have permission to access this session.",
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


def _not_all_questions_answered(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/incomplete-session",
            "title": "Session incomplete",
            "status": 422,
            "detail": "All questions must be answered before evaluation.",
            "instance": instance,
        },
    )


def _session_already_evaluated(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/session-already-evaluated",
            "title": "Session already evaluated",
            "status": 409,
            "detail": "This session has already been completed.",
            "instance": instance,
        },
    )


def _dispute_already_exists(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/dispute-already-exists",
            "title": "Dispute already exists",
            "status": 409,
            "detail": "Session has an active dispute and cannot be disputed again.",
            "instance": instance,
        },
    )


def _session_not_completed(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/session-not-completed",
            "title": "Session not completed",
            "status": 422,
            "detail": "Disputes can only be submitted for completed sessions.",
            "instance": instance,
        },
    )


# ─── list_sessions ────────────────────────────────────────────────────────────

async def list_sessions(
    specialist_id: UUID,
    page: int,
    per_page: int,
    db: AsyncSession,
) -> PaginatedResponse[SessionListItemRead]:
    base_filter = (
        AssessmentSession.specialist_id == specialist_id,
        AssessmentSession.status == SessionStatus.COMPLETED,
    )

    count_result = await db.execute(
        select(func.count(AssessmentSession.id)).where(*base_filter)
    )
    total = count_result.scalar_one()

    sessions_result = await db.execute(
        select(AssessmentSession)
        .where(*base_filter)
        .options(selectinload(AssessmentSession.dispute))
        .order_by(AssessmentSession.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    sessions = sessions_result.scalars().all()

    category_ids = {s.category_id for s in sessions}
    cat_map: dict[UUID, str] = {}
    if category_ids:
        cats_result = await db.execute(
            select(CompetencyCategory).where(CompetencyCategory.id.in_(category_ids))
        )
        cat_map = {c.id: c.name for c in cats_result.scalars().all()}

    items = [
        SessionListItemRead(
            id=s.id,
            category_id=s.category_id,
            category_name=cat_map.get(s.category_id),
            status=s.status,
            final_score=s.final_score,
            previous_score=s.previous_score,
            created_at=s.created_at,
            updated_at=s.updated_at,
            dispute=SessionDisputeRead.model_validate(s.dispute) if s.dispute else None,
        )
        for s in sessions
    ]

    pages = math.ceil(total / per_page) if total > 0 else 1
    return PaginatedResponse[SessionListItemRead](
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
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


# ─── evaluate_session ─────────────────────────────────────────────────────────

async def evaluate_session(
    session_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> dict:
    # 1. Load session with FOR UPDATE to prevent concurrent evaluate calls
    sess_result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .with_for_update()
        .options(
            selectinload(AssessmentSession.questions),
            selectinload(AssessmentSession.responses),
        )
    )
    session = sess_result.scalar_one_or_none()
    if session is None or session.specialist_id != current_user.id:
        raise _session_not_found(instance)
    if session.status == SessionStatus.COMPLETED:
        raise _session_already_evaluated(instance)
    if session.status not in (SessionStatus.IN_PROGRESS, SessionStatus.EVALUATION_PENDING):
        raise _session_not_in_progress(instance)

    # 2. Validate all questions are answered
    question_ids = {q.id for q in session.questions}
    answered_ids = {r.question_id for r in session.responses}
    if question_ids != answered_ids:
        raise _not_all_questions_answered(instance)

    # 3. Build QA entries (decrypt response_text before passing to LLM)
    response_map = {r.question_id: r for r in session.responses}
    qa_entries = [
        QAEntry(
            question_text=q.text,
            question_type=q.question_type,
            response_text=decrypt_field(response_map[q.id].response_text)
            if response_map[q.id].response_text else "",
            order=q.order,
        )
        for q in sorted(session.questions, key=lambda x: x.order)
    ]

    # 4. Load category name for LLM context
    cat_result = await db.execute(
        select(CompetencyCategory).where(CompetencyCategory.id == session.category_id)
    )
    category = cat_result.scalar_one_or_none()
    category_name = category.name if category else ""
    level = current_user.specialist_level.value if current_user.specialist_level else "junior"

    context = ResponseEvaluationContext(
        specialist_id=current_user.id,
        category_name=category_name,
        level=level,
        qa_entries=qa_entries,
    )

    # 5. Build + encrypt prompt for LLM log
    prompt = build_response_evaluation_prompt(context)
    encrypted_prompt = encrypt_field(prompt)
    start = time.monotonic()
    llm_log = LLMCallLog(
        provider=settings.LLM_PROVIDER,
        operation=LLMOperation.RESPONSE_EVALUATION,
        specialist_id=current_user.id,
        request_payload=encrypted_prompt,
    )

    # 6. Call LLM
    provider = get_llm_provider()
    try:
        eval_result, latency_ms, tokens_used = await provider.evaluate_responses(context)
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.error = str(exc)
        session.status = SessionStatus.EVALUATION_PENDING
        db.add(llm_log)
        await db.commit()
        if isinstance(exc, LLMUnavailableError):
            raise _llm_unavailable(instance)
        raise ProblemHTTPException(
            status_code=500,
            detail={
                "type": "https://vmatrix.app/errors/evaluation-failed",
                "title": "Evaluation failed",
                "status": 500,
                "detail": f"An unexpected error occurred during evaluation: {str(exc)}",
                "instance": instance,
            },
        )

    llm_log.latency_ms = latency_ms
    llm_log.tokens_used = tokens_used

    # 7. Write per-question rationale (Fernet-encrypted)
    feedback_by_order = {fb.question_order: fb for fb in eval_result.per_question_feedback}
    for q in session.questions:
        resp = response_map.get(q.id)
        if resp:
            fb = feedback_by_order.get(q.order)
            resp.ai_rationale = encrypt_field(fb.commentary if fb else "No feedback provided")

    # 8. Get previous score before upsert
    prev_score_result = await db.execute(
        select(SpecialistScore).where(
            SpecialistScore.specialist_id == current_user.id,
            SpecialistScore.category_id == session.category_id,
        )
    )
    existing_score = prev_score_result.scalar_one_or_none()
    previous_score = existing_score.score if existing_score else None

    # 9. Upsert SpecialistScore
    now = datetime.now(timezone.utc)
    if existing_score:
        existing_score.score = eval_result.score
        existing_score.last_assessed_at = now
    else:
        db.add(SpecialistScore(
            specialist_id=current_user.id,
            category_id=session.category_id,
            score=eval_result.score,
            last_assessed_at=now,
        ))

    # 10. Calculate level percentage BEFORE commit
    from app.services.level_service import calculate_percentage
    level_percentage = await calculate_percentage(current_user.id, db)

    # 11. Update session — atomic with SpecialistScore upsert
    session.status = SessionStatus.COMPLETED
    session.final_score = eval_result.score
    session.previous_score = previous_score
    session.strengths = encrypt_field(eval_result.strengths or "")
    session.areas_for_growth = encrypt_field(eval_result.areas_for_growth or "")
    db.add(llm_log)
    from app.services.level_service import check_threshold
    await check_threshold(current_user.id, level_percentage, db)
    await db.commit()

    return {
        "session_id": session.id,
        "status": SessionStatus.COMPLETED,
        "final_score": eval_result.score,
        "previous_score": previous_score,
        "level_percentage": level_percentage,
    }


# ─── get_session ───────────────────────────────────────────────────────────────

async def get_session(
    session_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
    load_dispute: bool = False,
) -> AssessmentSession:
    # Specialists can only see their own sessions. CMs and Admins can see any.
    options = [
        selectinload(AssessmentSession.questions),
        selectinload(AssessmentSession.responses),
    ]
    if load_dispute:
        options.append(selectinload(AssessmentSession.dispute))

    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .options(*options)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise _session_not_found(instance)

    # authorization check
    if current_user.role == "specialist" and session.specialist_id != current_user.id:
        raise _session_not_found(instance)

    # Load category name
    cat_result = await db.execute(
        select(CompetencyCategory.name).where(CompetencyCategory.id == session.category_id)
    )
    session.category_name = cat_result.scalar()

    # Calculate level percentage
    from app.services.level_service import calculate_percentage
    session.level_percentage = await calculate_percentage(session.specialist_id, db)

    # Expunge from session before decryption to prevent accidental flushes of plaintext to DB
    db.expunge(session)
    for resp in session.responses:
        db.expunge(resp)

    # Decrypt encrypted fields
    for resp in session.responses:
        if resp.response_text:
            resp.response_text = decrypt_field(resp.response_text)
        if resp.ai_rationale:
            resp.ai_rationale = decrypt_field(resp.ai_rationale)
    if session.strengths:
        session.strengths = decrypt_field(session.strengths)
    if session.areas_for_growth:
        session.areas_for_growth = decrypt_field(session.areas_for_growth)

    return session


# ─── get_session_for_review ────────────────────────────────────────────────────

async def get_session_for_review(session_id: UUID, db: AsyncSession) -> AssessmentSession:
    """Load, decrypt and return a session for CM dispute review. No ownership check — caller's responsibility."""
    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .options(
            selectinload(AssessmentSession.questions),
            selectinload(AssessmentSession.responses),
            selectinload(AssessmentSession.dispute),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise _session_not_found(f"/cm/disputes/{session_id}")

    cat_result = await db.execute(
        select(CompetencyCategory.name).where(CompetencyCategory.id == session.category_id)
    )
    session.category_name = cat_result.scalar()

    db.expunge(session)
    for resp in session.responses:
        db.expunge(resp)

    for resp in session.responses:
        if resp.response_text:
            resp.response_text = decrypt_field(resp.response_text)
        if resp.ai_rationale:
            resp.ai_rationale = decrypt_field(resp.ai_rationale)

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


# ─── submit_dispute ────────────────────────────────────────────────────────────

DISPUTE_SUBMITTED_NOTIFICATION = "A specialist has submitted a dispute for session review."


async def submit_dispute(
    session_id: UUID,
    specialist_explanation: str,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> SessionDispute:
    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == session_id)
        .with_for_update()
        .options(selectinload(AssessmentSession.dispute))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise _session_not_found(instance)

    if session.specialist_id != current_user.id:
        raise _session_not_found(instance)

    if session.status != SessionStatus.COMPLETED:
        raise _session_not_completed(instance)

    if session.dispute is not None:
        raise _dispute_already_exists(instance)

    now = datetime.now(timezone.utc)
    dispute = SessionDispute(
        session_id=session_id,
        status=DisputeStatus.OPEN,
        specialist_explanation=specialist_explanation,
        submitted_at=now,
    )
    db.add(dispute)

    if current_user.cm_id is not None:
        notification = Notification(
            user_id=current_user.cm_id,
            type=NotificationType.DISPUTE_SUBMITTED,
            content=DISPUTE_SUBMITTED_NOTIFICATION,
        )
        db.add(notification)
    else:
        logger.warning(
            "Dispute submitted for session %s but specialist %s has no CM assigned.",
            session_id, current_user.id
        )

    await db.commit()
    await db.refresh(dispute)
    return dispute
