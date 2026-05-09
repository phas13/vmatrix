from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import SpecialistScore
from app.models.user import User, UserRole
from app.schemas.cm import SpecialistCardRead, SpecialistDetailRead
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

    cards: list[SpecialistCardRead] = []
    for specialist in specialists:
        percentage = await level_service.calculate_percentage(specialist.id, db)
        cards.append(
            SpecialistCardRead(
                id=specialist.id,
                full_name=specialist.full_name,
                specialist_level=specialist.specialist_level,
                overall_percentage=percentage,
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
    if not specialist or specialist.cm_id != cm_id or specialist.role != UserRole.SPECIALIST:
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
