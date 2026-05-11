import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matrix import CompetencyMatrix, MatrixStatus
from app.models.notification import Notification, NotificationType
from app.models.session import AssessmentSession, DisputeStatus, SessionDispute, SpecialistScore
from app.models.user import User, UserRole
from app.schemas.cm import (
    PendingActionRead,
    PendingActionType,
    PendingActionsResponse,
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
