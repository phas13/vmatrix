import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus, MatrixUpdateProposal, ProposalStatus
from app.models.notification import Notification, NotificationType
from app.models.session import AssessmentSession, DisputeStatus, SessionDispute, SpecialistScore
from app.models.system_settings import SystemSettings
from app.models.usage_event import UsageEventAction, UsageEventResourceType
from app.models.user import User, UserRole, SpecialistLevel
import logging

from app.schemas.cm import (
    DisputeDecision,
    DisputeDetailRead,
    DisputeResolveRequest,
    DisputeResolveResponse,
    MatrixProposalDecideResponse,
    MatrixProposalDetailRead,
    PendingActionRead,
    PendingActionType,
    PendingActionsResponse,
    PromotionDecideRequest,
    PromotionDecideResponse,
    PromotionDetailRead,
    QuestionResponseItem,
    SpecialistCardRead,
    SpecialistDetailRead,
)

logger = logging.getLogger(__name__)
from app.services import level_service, session_service, usage_service


async def get_team_overview(cm_id: UUID, db: AsyncSession) -> list[SpecialistCardRead]:
    specialists_result = await db.execute(
        select(User).where(
            User.role == UserRole.SPECIALIST,
            User.cm_id == cm_id,
            User.is_active.is_(True),
        )
    )
    specialists = specialists_result.scalars().all()

    if not specialists:
        return []

    spec_ids = [s.id for s in specialists]

    activity_result = await db.execute(
        select(
            SpecialistScore.specialist_id,
            func.max(SpecialistScore.last_assessed_at).label("last_activity_at"),
        )
        .where(SpecialistScore.specialist_id.in_(spec_ids))
        .group_by(SpecialistScore.specialist_id)
    )
    last_activity_map: dict[UUID, object] = {
        row.specialist_id: row.last_activity_at for row in activity_result.all()
    }

    percentage_map = await level_service.calculate_bulk_percentages(spec_ids, db)

    cards: list[SpecialistCardRead] = []
    for specialist in specialists:
        cards.append(
            SpecialistCardRead(
                id=specialist.id,
                full_name=specialist.full_name,
                specialist_level=specialist.specialist_level,
                overall_percentage=percentage_map.get(specialist.id, 0),
                last_activity_at=last_activity_map.get(specialist.id),
            )
        )
    return cards


async def get_specialist_detail(
    cm_id: UUID,
    specialist_id: UUID,
    db: AsyncSession,
    page: int,
    per_page: int,
) -> SpecialistDetailRead:
    specialist = await db.get(User, specialist_id)
    if (
        not specialist
        or not specialist.is_active
        or specialist.cm_id != cm_id
        or specialist.role != UserRole.SPECIALIST
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specialist not found")

    dashboard = await level_service.get_dashboard_data(specialist_id, db)
    sessions = await session_service.list_sessions(specialist_id, page, per_page, db)

    return SpecialistDetailRead(
        id=specialist.id,
        full_name=specialist.full_name,
        specialist_level=dashboard.specialist_level,
        overall_percentage=dashboard.overall_percentage,
        category_scores=dashboard.category_scores,
        sessions=sessions,
    )


async def get_pending_actions(cm_id: UUID, db: AsyncSession) -> PendingActionsResponse:
    specialists_result = await db.execute(
        select(User).where(
            User.cm_id == cm_id,
            User.role == UserRole.SPECIALIST,
            User.is_active.is_(True),
        )
    )
    specialists = specialists_result.scalars().all()
    spec_ids = [s.id for s in specialists]
    spec_name_map: dict[UUID, str] = {s.id: s.full_name for s in specialists}

    disputes: list[PendingActionRead] = []
    matrix_approvals: list[PendingActionRead] = []

    if spec_ids:
        disputes_result = await db.execute(
            select(SessionDispute, AssessmentSession.specialist_id)
            .join(AssessmentSession, SessionDispute.session_id == AssessmentSession.id)
            .where(
                AssessmentSession.specialist_id.in_(spec_ids),
                SessionDispute.status == DisputeStatus.OPEN,
            )
        )
        for dispute, specialist_id in disputes_result.all():
            disputes.append(
                PendingActionRead(
                    id=dispute.id,
                    type=PendingActionType.DISPUTE,
                    specialist_id=specialist_id,
                    specialist_name=spec_name_map.get(specialist_id, "Unknown"),
                    description="Assessment dispute pending review",
                    date=dispute.submitted_at,
                )
            )

        matrices_result = await db.execute(
            select(CompetencyMatrix).where(
                CompetencyMatrix.specialist_id.in_(spec_ids),
                CompetencyMatrix.status == MatrixStatus.PENDING_APPROVAL,
            )
        )
        for matrix in matrices_result.scalars().all():
            matrix_approvals.append(
                PendingActionRead(
                    id=matrix.id,
                    type=PendingActionType.MATRIX_APPROVAL,
                    specialist_id=matrix.specialist_id,
                    specialist_name=spec_name_map.get(matrix.specialist_id, "Unknown"),
                    description="Competency matrix awaiting approval",
                    date=matrix.updated_at,
                )
            )

    promos_result = await db.execute(
        select(Notification).where(
            Notification.user_id == cm_id,
            Notification.type == NotificationType.PROMOTION_SUGGESTION,
            Notification.is_read.is_(False),
        )
    )
    promotions: list[PendingActionRead] = []
    for notification in promos_result.scalars().all():
        match = _uuid_pattern.search(notification.content)
        if not match:
            continue
        try:
            specialist_id = UUID(match.group(1))
        except ValueError:
            continue
        promotions.append(
            PendingActionRead(
                id=notification.id,
                type=PendingActionType.PROMOTION,
                specialist_id=specialist_id,
                specialist_name=spec_name_map.get(specialist_id, "Unknown specialist"),
                description="Promotion threshold reached — review required",
                date=notification.created_at,
            )
        )

    update_proposals: list[PendingActionRead] = []
    proposals_result = await db.execute(
        select(MatrixUpdateProposal).where(
            MatrixUpdateProposal.status == ProposalStatus.PENDING
        )
    )
    for proposal in proposals_result.scalars().all():
        update_proposals.append(
            PendingActionRead(
                id=proposal.id,
                type=PendingActionType.UPDATE_PROPOSAL,
                specialist_id=UUID("00000000-0000-0000-0000-000000000000"),
                specialist_name=proposal.source_name,
                description=proposal.proposed_change[:200],
                date=proposal.created_at,
            )
        )

    total = len(disputes) + len(promotions) + len(matrix_approvals) + len(update_proposals)
    return PendingActionsResponse(
        disputes=disputes,
        promotions=promotions,
        matrix_approvals=matrix_approvals,
        update_proposals=update_proposals,
        total=total,
    )


_DISPUTE_NOT_FOUND = "Dispute not found"
_uuid_pattern = re.compile(r'\[([a-f0-9-]{36})\]')
_LEVEL_PROGRESSION: dict[SpecialistLevel, SpecialistLevel | None] = {
    SpecialistLevel.JUNIOR: SpecialistLevel.MIDDLE,
    SpecialistLevel.MIDDLE: SpecialistLevel.SENIOR,
    SpecialistLevel.SENIOR: None,
}


async def get_dispute_detail(cm_id: UUID, dispute_id: UUID, db: AsyncSession) -> DisputeDetailRead:
    dispute = await db.get(SessionDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    session = await db.get(AssessmentSession, dispute.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    specialist = await db.get(User, session.specialist_id)
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    full_session = await session_service.get_session_for_review(dispute.session_id, db)

    response_map = {r.question_id: r for r in full_session.responses}
    transcript: list[QuestionResponseItem] = []
    for question in sorted(full_session.questions, key=lambda q: q.order):
        resp = response_map.get(question.id)
        transcript.append(
            QuestionResponseItem(
                question_id=question.id,
                question_text=question.text,
                question_type=question.question_type.value if hasattr(question.question_type, "value") else str(question.question_type),
                order=question.order,
                response_text=resp.response_text if resp else None,
                ai_rationale=resp.ai_rationale if resp else None,
            )
        )

    return DisputeDetailRead(
        id=dispute.id,
        session_id=dispute.session_id,
        specialist_id=session.specialist_id,
        specialist_name=specialist.full_name,
        category_id=session.category_id,
        category_name=full_session.category_name,
        status=dispute.status.value,
        specialist_explanation=dispute.specialist_explanation,
        submitted_at=dispute.submitted_at,
        cm_decision=dispute.cm_decision,
        ai_score=session.final_score,
        transcript=transcript,
    )


async def resolve_dispute(
    cm_id: UUID,
    dispute_id: UUID,
    body: DisputeResolveRequest,
    db: AsyncSession,
) -> DisputeResolveResponse:
    dispute_result = await db.execute(
        select(SessionDispute)
        .where(SessionDispute.id == dispute_id)
        .with_for_update()
    )
    dispute = dispute_result.scalar_one_or_none()
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    # Lock the session row separately so `session.final_score` mutation is race-safe.
    session_result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.id == dispute.session_id)
        .with_for_update()
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    specialist = await db.get(User, session.specialist_id)
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DISPUTE_NOT_FOUND)

    if dispute.status != DisputeStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://vmatrix.app/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": "Dispute has already been resolved",
            },
        )

    now = datetime.now(timezone.utc)
    dispute.status = DisputeStatus.RESOLVED
    dispute.cm_decision = body.decision.value
    dispute.cm_note = body.cm_note
    dispute.resolved_at = now
    dispute.cm_id = cm_id

    if body.decision == DisputeDecision.OVERRIDDEN:
        # CM override always wins, regardless of whether a newer assessment
        # session has produced a different score for this (specialist, category).
        # Product decision: dispute-resolution is authoritative.
        if body.override_score == session.final_score:
            logger.info(
                "resolve_dispute: override score %s is identical to current score %s for session %s",
                body.override_score,
                session.final_score,
                session.id,
            )
        
        session.final_score = body.override_score

        # Idempotent upsert via PostgreSQL ON CONFLICT against
        # `uq_specialist_scores_spec_cat` — eliminates the SELECT-then-INSERT
        # race between concurrent dispute resolutions for the same pair.
        upsert_stmt = (
            pg_insert(SpecialistScore)
            .values(
                specialist_id=session.specialist_id,
                category_id=session.category_id,
                score=body.override_score,
                last_assessed_at=now,
            )
            .on_conflict_do_update(
                index_elements=["specialist_id", "category_id"],
                set_={"score": body.override_score, "last_assessed_at": now},
            )
        )
        await db.execute(upsert_stmt)

    cat_result = await db.execute(
        select(CompetencyCategory.name).where(CompetencyCategory.id == session.category_id)
    )
    category_name = cat_result.scalar() or "Unknown Category"

    db.add(Notification(
        user_id=session.specialist_id,
        type=NotificationType.DISPUTE_RESOLVED,
        content=f"Your dispute for {category_name} has been reviewed — see result",
    ))
    await usage_service.record_event(
        db, cm_id, UsageEventAction.DISPUTE_RESOLVED,
        resource_id=dispute_id, resource_type=UsageEventResourceType.DISPUTE
    )

    await db.commit()

    return DisputeResolveResponse(
        id=dispute.id,
        status=dispute.status.value,
        cm_decision=dispute.cm_decision,
        cm_note=dispute.cm_note,
        resolved_at=dispute.resolved_at,
        updated_score=session.final_score if body.decision == DisputeDecision.OVERRIDDEN else None,
    )


async def get_promotion_detail(
    cm_id: UUID,
    notification_id: UUID,
    db: AsyncSession,
    page: int = 1,
    per_page: int = 10,
) -> PromotionDetailRead:
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != cm_id or notification.type != NotificationType.PROMOTION_SUGGESTION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    match = _uuid_pattern.search(notification.content)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    try:
        specialist_id = UUID(match.group(1))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    specialist = await db.get(User, specialist_id)
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    settings_result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    threshold = settings.promotion_threshold if settings else 90

    dashboard = await level_service.get_dashboard_data(specialist_id, db)
    sessions = await session_service.list_sessions(specialist_id, page, per_page, db)

    next_level_enum = _LEVEL_PROGRESSION.get(specialist.specialist_level) if specialist.specialist_level else None
    current_level = specialist.specialist_level.value if specialist.specialist_level else None
    next_level = next_level_enum.value if next_level_enum else None

    # Parse decision and note if decided
    decision = None
    cm_note = None
    if notification.is_read:
        if notification.content.startswith("[APPROVED]"):
            decision = "approved"
        elif notification.content.startswith("[REJECTED]"):
            decision = "rejected"
        
        # Extract note if exists: "[REJECTED] content: note"
        if ": " in notification.content:
            cm_note = notification.content.split(": ", 1)[1]

    return PromotionDetailRead(
        notification_id=notification.id,
        specialist_id=specialist.id,
        specialist_name=specialist.full_name,
        current_level=current_level,
        next_level=next_level,
        overall_percentage=dashboard.overall_percentage,
        threshold=threshold,
        category_scores=dashboard.category_scores,
        sessions=sessions,
        is_decided=notification.is_read,
        decision=decision,
        cm_note=cm_note,
    )


async def approve_promotion(
    cm_id: UUID,
    notification_id: UUID,
    body: PromotionDecideRequest,
    db: AsyncSession,
) -> PromotionDecideResponse:
    notif_result = await db.execute(
        select(Notification).where(Notification.id == notification_id).with_for_update()
    )
    notification = notif_result.scalar_one_or_none()
    if notification is None or notification.user_id != cm_id or notification.type != NotificationType.PROMOTION_SUGGESTION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    if notification.is_read:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://vmatrix.app/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": "Promotion has already been decided",
            },
        )

    match = _uuid_pattern.search(notification.content)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    try:
        specialist_id = UUID(match.group(1))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    spec_result = await db.execute(
        select(User).where(User.id == specialist_id).with_for_update()
    )
    specialist = spec_result.scalar_one_or_none()
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    new_level = _LEVEL_PROGRESSION.get(specialist.specialist_level) if specialist.specialist_level else None
    if new_level:
        specialist.specialist_level = new_level
    else:
        logger.warning(
            "approve_promotion: specialist %s is already at senior level or has no level set",
            specialist_id,
        )

    now = datetime.now(timezone.utc)
    notification.is_read = True
    notification.read_at = now
    notification.content = f"[APPROVED] {notification.content}"
    if body.cm_note and body.cm_note.strip():
        notification.content += f": {body.cm_note.strip()}"

    if new_level:
        level_label = new_level.value.capitalize()
        content = f"Congratulations — you've been promoted to {level_label}"
    else:
        content = "Your promotion was approved, but you are already at the highest level (Senior)"
    
    db.add(Notification(
        user_id=specialist_id,
        type=NotificationType.PROMOTION_APPROVED,
        content=content,
    ))
    await usage_service.record_event(
        db, cm_id, UsageEventAction.PROMOTION_APPROVED,
        resource_id=notification_id, resource_type=UsageEventResourceType.PROMOTION
    )

    await db.commit()

    return PromotionDecideResponse(
        notification_id=notification.id,
        decision="approved",
        new_level=new_level.value if new_level else None,
    )


async def reject_promotion(
    cm_id: UUID,
    notification_id: UUID,
    body: PromotionDecideRequest,
    db: AsyncSession,
) -> PromotionDecideResponse:
    notif_result = await db.execute(
        select(Notification).where(Notification.id == notification_id).with_for_update()
    )
    notification = notif_result.scalar_one_or_none()
    if notification is None or notification.user_id != cm_id or notification.type != NotificationType.PROMOTION_SUGGESTION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    if notification.is_read:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://vmatrix.app/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": "Promotion has already been decided",
            },
        )

    match = _uuid_pattern.search(notification.content)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    try:
        specialist_id = UUID(match.group(1))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    now = datetime.now(timezone.utc)
    notification.is_read = True
    notification.read_at = now
    notification.content = f"[REJECTED] {notification.content}"
    if body.cm_note and body.cm_note.strip():
        notification.content += f": {body.cm_note.strip()}"

    content = "Your promotion request was reviewed — see CM feedback"
    if body.cm_note and body.cm_note.strip():
        content += f": {body.cm_note.strip()}"

    db.add(Notification(
        user_id=specialist_id,
        type=NotificationType.PROMOTION_REJECTED,
        content=content,
    ))
    await usage_service.record_event(
        db, cm_id, UsageEventAction.PROMOTION_REJECTED,
        resource_id=notification_id, resource_type=UsageEventResourceType.PROMOTION
    )

    await db.commit()

    return PromotionDecideResponse(
        notification_id=notification.id,
        decision="rejected",
        new_level=None,
    )


async def get_matrix_proposal_detail(
    cm_id: UUID, proposal_id: UUID, db: AsyncSession
) -> MatrixProposalDetailRead:
    proposal = await db.get(MatrixUpdateProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return MatrixProposalDetailRead(
        id=proposal.id,
        proposed_change=proposal.proposed_change,
        source_name=proposal.source_name,
        source_url=proposal.source_url,
        source_date=proposal.source_date,
        status=proposal.status,
        is_decided=proposal.status != ProposalStatus.PENDING,
        created_at=proposal.created_at,
    )


async def _get_pending_matrix_proposal(proposal_id: UUID, db: AsyncSession) -> MatrixUpdateProposal:
    result = await db.execute(
        select(MatrixUpdateProposal).where(MatrixUpdateProposal.id == proposal_id).with_for_update()
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://vmatrix.app/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": "Proposal has already been decided",
            },
        )
    return proposal


async def approve_matrix_proposal(
    cm_id: UUID, proposal_id: UUID, db: AsyncSession
) -> MatrixProposalDecideResponse:
    proposal = await _get_pending_matrix_proposal(proposal_id, db)
    proposal.status = ProposalStatus.APPROVED
    proposal.decided_by_cm_id = cm_id
    proposal.decided_at = datetime.now(timezone.utc)
    await usage_service.record_event(
        db, cm_id, UsageEventAction.MATRIX_UPDATE_APPROVED,
        resource_id=proposal_id, resource_type=UsageEventResourceType.MATRIX_PROPOSAL
    )
    await db.commit()
    from app.schemas.cm import MatrixProposalDecision
    return MatrixProposalDecideResponse(proposal_id=proposal.id, decision=MatrixProposalDecision.APPROVED)


async def reject_matrix_proposal(
    cm_id: UUID, proposal_id: UUID, db: AsyncSession
) -> MatrixProposalDecideResponse:
    proposal = await _get_pending_matrix_proposal(proposal_id, db)
    proposal.status = ProposalStatus.REJECTED
    proposal.decided_by_cm_id = cm_id
    proposal.decided_at = datetime.now(timezone.utc)
    await usage_service.record_event(
        db, cm_id, UsageEventAction.MATRIX_UPDATE_REJECTED,
        resource_id=proposal_id, resource_type=UsageEventResourceType.MATRIX_PROPOSAL
    )
    await db.commit()
    from app.schemas.cm import MatrixProposalDecision
    return MatrixProposalDecideResponse(proposal_id=proposal.id, decision=MatrixProposalDecision.REJECTED)
