import logging
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import verify_specialist_ownership
from app.core.exceptions import LLMUnavailableError, ProblemHTTPException
from app.core.security import encrypt_field
from app.models.llm_call_log import LLMCallLog, LLMOperation
from app.models.matrix import CompetencyCategory, CompetencyMatrix, CompetencySubItem, MatrixStatus
from app.models.user import User
from app.providers.base import MatrixGenerationContext
from app.providers.factory import get_llm_provider
from app.services import admin_service

logger = logging.getLogger(__name__)


def _matrix_already_exists(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/matrix-already-exists",
            "title": "Matrix already exists",
            "status": 409,
            "detail": "A competency matrix already exists for this specialist",
            "instance": instance,
        },
    )


def _matrix_not_found(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/matrix-not-found",
            "title": "Matrix not found",
            "status": 404,
            "detail": "No competency matrix found for this specialist",
            "instance": instance,
        },
    )


def _llm_unavailable(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=503,
        detail={
            "type": "https://vmatrix.app/errors/llm-unavailable",
            "title": "LLM unavailable",
            "status": 503,
            "detail": "Matrix generation is temporarily unavailable. Please try again.",
            "instance": instance,
        },
    )


async def _load_specialist(specialist_id: UUID, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == specialist_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ProblemHTTPException(
            status_code=404,
            detail={
                "type": "https://vmatrix.app/errors/specialist-not-found",
                "title": "Specialist not found",
                "status": 404,
                "detail": f"Specialist {specialist_id} not found",
                "instance": "",
            },
        )
    return user


async def generate_initial_matrix(
    specialist_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencyMatrix:
    await verify_specialist_ownership(specialist_id, current_user)

    existing = await db.execute(
        select(CompetencyMatrix).where(CompetencyMatrix.specialist_id == specialist_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise _matrix_already_exists(instance)

    specialist = await _load_specialist(specialist_id, db)
    level = specialist.specialist_level.value if specialist.specialist_level else "junior"

    settings_row = await admin_service.get_settings(db)
    domain = settings_row.default_competency_domain

    provider = get_llm_provider()
    context = MatrixGenerationContext(
        specialist_id=specialist_id,
        level=level,
        domain=domain,
    )

    prompt_summary = encrypt_field(f"level={level} domain={domain}")

    start = time.monotonic()
    llm_log = LLMCallLog(
        provider=settings.LLM_PROVIDER,
        operation=LLMOperation.MATRIX_GENERATION,
        specialist_id=specialist_id,
        request_payload=prompt_summary,
    )

    try:
        categories_draft, latency_ms, tokens_used = await provider.generate_initial_matrix(context)
    except LLMUnavailableError as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.error = str(exc)
        db.add(llm_log)
        await db.commit()
        raise _llm_unavailable(instance)

    llm_log.latency_ms = latency_ms
    llm_log.tokens_used = tokens_used

    matrix = CompetencyMatrix(
        specialist_id=specialist_id,
        domain=domain,
        status=MatrixStatus.PENDING_REVIEW,
    )
    db.add(matrix)
    await db.flush()

    for i, cat_draft in enumerate(categories_draft):
        category = CompetencyCategory(
            matrix_id=matrix.id,
            name=cat_draft.name,
            description=cat_draft.description,
            order=i,
        )
        db.add(category)
        await db.flush()

        for j, sub_draft in enumerate(cat_draft.sub_items):
            sub_item = CompetencySubItem(
                category_id=category.id,
                name=sub_draft.name,
                description=sub_draft.description,
                order=j,
                is_flagged=False,
            )
            db.add(sub_item)

    db.add(llm_log)
    await db.commit()
    await db.refresh(matrix)

    logger.info(
        "matrix generated specialist_id=%s domain=%s categories=%d latency_ms=%d",
        specialist_id,
        domain,
        len(categories_draft),
        latency_ms,
    )

    return await get_matrix(specialist_id, db, current_user=current_user, instance=instance)


async def get_matrix(
    specialist_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencyMatrix:
    await verify_specialist_ownership(specialist_id, current_user)

    result = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.specialist_id == specialist_id)
        .options(
            selectinload(CompetencyMatrix.categories).selectinload(CompetencyCategory.sub_items)
        )
    )
    matrix = result.scalar_one_or_none()
    if matrix is None:
        raise _matrix_not_found(instance)
    return matrix
