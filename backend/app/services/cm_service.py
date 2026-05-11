import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.notification import Notification, NotificationType
from app.models.session import AssessmentSession, DisputeStatus, SessionDispute, SpecialistScore
from app.models.user import User, UserRole
from app.schemas.cm import (
    DisputeDecision,
    DisputeDetailRead,
    DisputeResolveRequest,
    DisputeResolveResponse,
    PendingActionRead,
    PendingActionType,
    PendingActionsResponse,
    QuestionResponseItem,
    SpecialistCardRead,
    SpecialistDetailRead,
)
from app.services import level_service, session_service


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
    _uuid_pattern = re.compile(r'\[([a-f0-9-]{36})\]')
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
                id=specialist_id,
                type=PendingActionType.PROMOTION,
                specialist_id=specialist_id,
                specialist_name=spec_name_map.get(specialist_id, "Unknown specialist"),
                description="Promotion threshold reached — review required",
                date=notification.created_at,
            )
        )

    update_proposals: list[PendingActionRead] = []

    total = len(disputes) + len(promotions) + len(matrix_approvals) + len(update_proposals)
    return PendingActionsResponse(
        disputes=disputes,
        promotions=promotions,
        matrix_approvals=matrix_approvals,
        update_proposals=update_proposals,
        total=total,
    )


async def get_dispute_detail(cm_id: UUID, dispute_id: UUID, db: AsyncSession) -> DisputeDetailRead:
    dispute = await db.get(SessionDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    session = await db.get(AssessmentSession, dispute.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    specialist = await db.get(User, session.specialist_id)
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

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
    result = await db.execute(
        select(SessionDispute)
        .where(SessionDispute.id == dispute_id)
        .options(selectinload(SessionDispute.session))
        .with_for_update()
    )
    dispute = result.scalar_one_or_none()
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    session = dispute.session
    specialist = await db.get(User, session.specialist_id)
    if specialist is None or specialist.cm_id != cm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

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
        session.final_score = body.override_score

        existing_result = await db.execute(
            select(SpecialistScore).where(
                SpecialistScore.specialist_id == session.specialist_id,
                SpecialistScore.category_id == session.category_id,
            )
        )
        existing_score = existing_result.scalar_one_or_none()
        if existing_score:
            existing_score.score = body.override_score
            existing_score.last_assessed_at = now
        else:
            db.add(SpecialistScore(
                specialist_id=session.specialist_id,
                category_id=session.category_id,
                score=body.override_score,
                last_assessed_at=now,
            ))

    cat_result = await db.execute(
        select(CompetencyCategory.name).where(CompetencyCategory.id == session.category_id)
    )
    category_name = cat_result.scalar() or "Unknown Category"

    db.add(Notification(
        user_id=session.specialist_id,
        type=NotificationType.DISPUTE_RESOLVED,
        content=f"Your dispute for {category_name} has been reviewed — see result",
    ))

    await db.commit()

    return DisputeResolveResponse(
        id=dispute.id,
        status=dispute.status.value,
        cm_decision=dispute.cm_decision,
        cm_note=dispute.cm_note,
        resolved_at=dispute.resolved_at,
        updated_score=session.final_score if body.decision == DisputeDecision.OVERRIDDEN else None,
    )
