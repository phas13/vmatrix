import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import verify_specialist_ownership
from app.core.exceptions import LLMUnavailableError, ProblemHTTPException
from app.core.security import encrypt_field
from app.models.llm_call_log import LLMCallLog, LLMOperation
from app.models.matrix import CompetencyCategory, CompetencyMatrix, CompetencySubItem, MatrixStatus, MatrixUpdateProposal, ProposalStatus
from app.models.notification import Notification, NotificationType
from app.models.system_settings import SystemSettings
from app.models.user import User, UserRole
from app.providers.base import MatrixGenerationContext, MatrixUpdateProposalDraft
from app.providers.factory import get_llm_provider
from app.schemas.matrix import MatrixApproveRequest
from app.services.prompt_builder import build_matrix_generation_prompt

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


def _specialist_not_found(specialist_id: UUID, instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/specialist-not-found",
            "title": "Specialist not found",
            "status": 404,
            "detail": f"Specialist {specialist_id} not found",
            "instance": instance,
        },
    )


def _specialist_level_required(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/specialist-level-required",
            "title": "Specialist level required",
            "status": 422,
            "detail": "Specialist must have a seniority level assigned before a matrix can be generated",
            "instance": instance,
        },
    )


def _domain_unavailable(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=503,
        detail={
            "type": "https://vmatrix.app/errors/competency-domain-unavailable",
            "title": "Competency domain unavailable",
            "status": 503,
            "detail": "Default competency domain is not configured",
            "instance": instance,
        },
    )


async def _load_specialist(specialist_id: UUID, db: AsyncSession, instance: str) -> User:
    result = await db.execute(select(User).where(User.id == specialist_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.role != UserRole.SPECIALIST:
        raise _specialist_not_found(specialist_id, instance)
    return user


async def _read_default_domain(db: AsyncSession) -> str | None:
    """Read the singleton SystemSettings row without bootstrapping side-effects.

    The singleton row is seeded by migration; this query never writes. Returns
    the raw `default_competency_domain` string, or None if the row is missing
    or the value is empty/whitespace.
    """
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    domain = (row.default_competency_domain or "").strip()
    return domain or None


async def generate_initial_matrix(
    specialist_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencyMatrix:
    await verify_specialist_ownership(specialist_id, current_user)

    existing = await db.execute(
        select(CompetencyMatrix).where(CompetencyMatrix.specialist_id == specialist_id).with_for_update()
    )
    if existing.scalar_one_or_none() is not None:
        raise _matrix_already_exists(instance)

    specialist = await _load_specialist(specialist_id, db, instance)
    if specialist.specialist_level is None:
        raise _specialist_level_required(instance)
    level = specialist.specialist_level.value

    raw_domain = await _read_default_domain(db)
    if raw_domain is None:
        raise _domain_unavailable(instance)
    
    # Sanitize domain for prompt safety: alphanumeric, spaces, and hyphens only; max 50 chars.
    import re
    domain = re.sub(r"[^a-zA-Z0-9 \-]", "", raw_domain)[:50].strip()

    provider = get_llm_provider()
    context = MatrixGenerationContext(
        specialist_id=specialist_id,
        level=level,
        domain=domain,
    )

    prompt = build_matrix_generation_prompt(level=level, domain=domain)
    encrypted_prompt = encrypt_field(prompt)

    start = time.monotonic()
    llm_log = LLMCallLog(
        provider=settings.LLM_PROVIDER,
        operation=LLMOperation.MATRIX_GENERATION,
        specialist_id=specialist_id,
        request_payload=encrypted_prompt,
    )

    try:
        categories_draft, latency_ms, tokens_used = await provider.generate_initial_matrix(context)
    except LLMUnavailableError as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.error = str(exc)
        await db.rollback()
        db.add(llm_log)
        await db.commit()
        raise _llm_unavailable(instance)

    if not categories_draft:
        latency_ms = int((time.monotonic() - start) * 1000)
        llm_log.latency_ms = latency_ms
        llm_log.tokens_used = tokens_used
        llm_log.error = "provider returned no categories"
        await db.rollback()
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
            name=cat_draft.name[:255],  # Truncate to DB limit
            description=cat_draft.description[:1000] if cat_draft.description else None,
            order=i,
        )
        db.add(category)
        await db.flush()

        for j, sub_draft in enumerate(cat_draft.sub_items):
            sub_item = CompetencySubItem(
                category_id=category.id,
                name=sub_draft.name[:255],  # Truncate to DB limit
                description=sub_draft.description[:1000] if sub_draft.description else None,
                order=j,
                is_flagged=False,
            )
            db.add(sub_item)

    db.add(llm_log)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _matrix_already_exists(instance)

    logger.info(
        "matrix generated specialist_id=%s domain=%s categories=%d latency_ms=%d",
        specialist_id,
        domain,
        len(categories_draft),
        latency_ms,
    )

    eager = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.id == matrix.id)
        .options(
            selectinload(CompetencyMatrix.categories).selectinload(CompetencyCategory.sub_items)
        )
    )
    return eager.scalar_one()


async def get_matrix(
    specialist_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencyMatrix:
    await verify_specialist_ownership(specialist_id, current_user)

    if current_user.role == UserRole.CM:
        owner_result = await db.execute(select(User).where(User.id == specialist_id))
        owner = owner_result.scalar_one_or_none()
        if owner is None or owner.cm_id != current_user.id:
            raise _matrix_not_found(instance)

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


def _sub_item_not_found(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/sub-item-not-found",
            "title": "Sub-item not found",
            "status": 404,
            "detail": "Competency sub-item not found or does not belong to this specialist's matrix",
            "instance": instance,
        },
    )


def _matrix_not_editable(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/matrix-not-editable",
            "title": "Matrix not editable",
            "status": 409,
            "detail": "Matrix cannot be modified after submission",
            "instance": instance,
        },
    )


def _matrix_already_submitted(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/matrix-already-submitted",
            "title": "Matrix already submitted",
            "status": 409,
            "detail": "Matrix has already been submitted for review",
            "instance": instance,
        },
    )


async def flag_sub_item(
    specialist_id: UUID,
    sub_item_id: UUID,
    note: str | None,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencySubItem:
    await verify_specialist_ownership(specialist_id, current_user)

    result = await db.execute(
        select(CompetencySubItem, CompetencyMatrix.status)
        .join(CompetencyCategory, CompetencySubItem.category_id == CompetencyCategory.id)
        .join(CompetencyMatrix, CompetencyCategory.matrix_id == CompetencyMatrix.id)
        .where(CompetencySubItem.id == sub_item_id)
        .where(CompetencyMatrix.specialist_id == specialist_id)
        .with_for_update(of=CompetencyMatrix)
    )
    row = result.first()
    if row is None:
        raise _sub_item_not_found(instance)

    sub_item, matrix_status = row
    if matrix_status != MatrixStatus.PENDING_REVIEW:
        raise _matrix_not_editable(instance)

    sub_item.is_flagged = True
    sub_item.flag_note = note[:500] if note else None  # Truncate to match schema/UI
    await db.commit()
    await db.refresh(sub_item)
    return sub_item


async def unflag_sub_item(
    specialist_id: UUID,
    sub_item_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencySubItem:
    await verify_specialist_ownership(specialist_id, current_user)

    result = await db.execute(
        select(CompetencySubItem, CompetencyMatrix.status)
        .join(CompetencyCategory, CompetencySubItem.category_id == CompetencyCategory.id)
        .join(CompetencyMatrix, CompetencyCategory.matrix_id == CompetencyMatrix.id)
        .where(CompetencySubItem.id == sub_item_id)
        .where(CompetencyMatrix.specialist_id == specialist_id)
        .with_for_update(of=CompetencyMatrix)
    )
    row = result.first()
    if row is None:
        raise _sub_item_not_found(instance)

    sub_item, matrix_status = row
    if matrix_status != MatrixStatus.PENDING_REVIEW:
        raise _matrix_not_editable(instance)

    sub_item.is_flagged = False
    sub_item.flag_note = None
    await db.commit()
    await db.refresh(sub_item)
    return sub_item


async def submit_for_review(
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
        .with_for_update()
    )
    matrix = result.scalar_one_or_none()
    if matrix is None:
        raise _matrix_not_found(instance)
    if matrix.status != MatrixStatus.PENDING_REVIEW:
        raise _matrix_already_submitted(instance)

    matrix.status = MatrixStatus.PENDING_APPROVAL

    specialist = await _load_specialist(specialist_id, db, instance)
    if specialist.cm_id is not None:
        content = f"{specialist.full_name}'s competency matrix is ready for your review"
        notification = Notification(
            user_id=specialist.cm_id,
            type=NotificationType.MATRIX_PENDING_REVIEW,
            content=content[:1000],
        )
        db.add(notification)

    await db.commit()

    eager = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.id == matrix.id)
        .options(
            selectinload(CompetencyMatrix.categories).selectinload(CompetencyCategory.sub_items)
        )
    )
    return eager.scalar_one()


def _matrix_not_pending_approval(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/matrix-not-pending-approval",
            "title": "Matrix not pending approval",
            "status": 409,
            "detail": "Matrix must be in PENDING_APPROVAL status to be approved",
            "instance": instance,
        },
    )


async def approve_matrix(
    specialist_id: UUID,
    request: MatrixApproveRequest,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> CompetencyMatrix:
    # 1. Deduplicate and validate input IDs
    edit_ids = [e.id for e in request.sub_item_edits]
    remove_ids = request.sub_items_to_remove
    
    if len(set(edit_ids)) != len(edit_ids):
        raise ProblemHTTPException(status_code=422, detail="Duplicate IDs in sub_item_edits")
    if len(set(remove_ids)) != len(remove_ids):
        raise ProblemHTTPException(status_code=422, detail="Duplicate IDs in sub_items_to_remove")
    
    overlap = set(edit_ids) & set(remove_ids)
    if overlap:
        raise ProblemHTTPException(
            status_code=422, 
            detail=f"Sub-item IDs cannot be both edited and removed: {list(overlap)}"
        )

    # 2. Lock and fetch matrix with all sub-items
    result = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.specialist_id == specialist_id)
        .options(
            selectinload(CompetencyMatrix.categories).selectinload(CompetencyCategory.sub_items)
        )
        .with_for_update()
    )
    matrix = result.scalar_one_or_none()
    if matrix is None:
        raise _matrix_not_found(instance)
    
    # 3. Authorization check (inside lock)
    if current_user.role == UserRole.CM:
        owner_result = await db.execute(select(User).where(User.id == specialist_id))
        owner = owner_result.scalar_one_or_none()
        if owner is None or owner.cm_id != current_user.id:
            raise _matrix_not_found(instance)

    if matrix.status != MatrixStatus.PENDING_APPROVAL:
        raise _matrix_not_pending_approval(instance)

    # 4. Build sub-item lookup and validate ownership
    sub_item_map: dict[UUID, CompetencySubItem] = {
        si.id: si
        for cat in matrix.categories
        for si in cat.sub_items
    }
    valid_ids = set(sub_item_map.keys())

    for edit in request.sub_item_edits:
        if edit.id not in valid_ids:
            raise _sub_item_not_found(instance)
        # Validation Decision 1-B: Return 422 instead of silent truncation
        if not edit.name.strip():
            raise ProblemHTTPException(status_code=422, detail="Sub-item name cannot be empty")
        if len(edit.name) > 255:
            raise ProblemHTTPException(status_code=422, detail=f"Sub-item name exceeds 255 chars: {edit.id}")
        if edit.description and len(edit.description) > 1000:
            raise ProblemHTTPException(status_code=422, detail=f"Sub-item description exceeds 1000 chars: {edit.id}")

    for removal_id in request.sub_items_to_remove:
        if removal_id not in valid_ids:
            raise _sub_item_not_found(instance)

    # 5. Apply edits — track changes for audit log
    applied_edits = []
    for edit in request.sub_item_edits:
        si = sub_item_map[edit.id]
        if si.name != edit.name or si.description != edit.description:
            applied_edits.append({
                "id": str(edit.id),
                "name_before": si.name,
                "name_after": edit.name,
                "description_before": si.description,
                "description_after": edit.description,
            })
            si.name = edit.name
            si.description = edit.description

    # 6. Apply removals — track for audit log, then hard delete
    applied_removals = []
    affected_categories = set()
    for removal_id in request.sub_items_to_remove:
        si = sub_item_map[removal_id]
        applied_removals.append({"id": str(removal_id), "name": si.name})
        affected_categories.add(si.category_id)
        await db.delete(si)

    # 7. Re-sequence order (Decision 2-B)
    if affected_categories:
        await db.flush() # Ensure deletes are processed
        for cat in matrix.categories:
            if cat.id in affected_categories:
                # Refresh items to exclude deleted ones
                items_result = await db.execute(
                    select(CompetencySubItem)
                    .where(CompetencySubItem.category_id == cat.id)
                    .order_by(CompetencySubItem.order)
                )
                remaining_items = items_result.scalars().all()
                for i, item in enumerate(remaining_items):
                    item.order = i

    # 8. Write audit log + update status
    matrix.status = MatrixStatus.APPROVED
    matrix.approved_by_id = current_user.id
    matrix.approved_at = datetime.now(timezone.utc)
    matrix.cm_changes = {
        "edits": applied_edits,
        "removals": applied_removals,
    }

    # 9. Notify specialist
    notification = Notification(
        user_id=specialist_id,
        type=NotificationType.MATRIX_APPROVED,
        content="Your competency matrix has been approved — you can start assessments",
    )
    db.add(notification)

    await db.commit()

    approved_matrix = await db.execute(
        select(CompetencyMatrix)
        .where(CompetencyMatrix.id == matrix.id)
        .options(
            selectinload(CompetencyMatrix.categories).selectinload(CompetencyCategory.sub_items)
        )
    )
    return approved_matrix.scalar_one()


async def save_proposal(
    db: AsyncSession, draft: MatrixUpdateProposalDraft
) -> MatrixUpdateProposal | None:
    # Check for existing duplicate pending proposal
    existing_result = await db.execute(
        select(MatrixUpdateProposal).where(
            MatrixUpdateProposal.proposed_change == draft.proposed_change,
            MatrixUpdateProposal.source_url == draft.source_url,
            MatrixUpdateProposal.status == ProposalStatus.PENDING,
        ).limit(1)
    )
    if existing_result.scalar_one_or_none():
        return None

    proposal = MatrixUpdateProposal(
        proposed_change=draft.proposed_change,
        source_name=draft.source_name,
        source_url=draft.source_url,
        source_date=draft.source_date,
        matrix_id=draft.matrix_id,
        status=ProposalStatus.PENDING,
    )
    db.add(proposal)
    await db.flush()
    return proposal
