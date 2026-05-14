from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matrix import CompetencyCategory
from app.models.session import SpecialistScore
from app.models.user import User, UserRole
from app.schemas.hr import CompetencyAreaStat, HRStatsResponse


async def get_hr_stats(db: AsyncSession) -> HRStatsResponse:
    level_rows = await db.execute(
        select(User.specialist_level, func.count(User.id))
        .where(User.role == UserRole.SPECIALIST, User.is_active == True)  # noqa: E712
        .group_by(User.specialist_level)
    )
    level_distribution = {row[0].value: row[1] for row in level_rows if row[0]}

    avg_rows = await db.execute(
        select(User.specialist_level, func.avg(SpecialistScore.score).cast(Integer))
        .join(SpecialistScore, SpecialistScore.specialist_id == User.id)
        .where(User.role == UserRole.SPECIALIST, User.is_active == True)  # noqa: E712
        .group_by(User.specialist_level)
    )
    avg_progress = {row[0].value: int(row[1] or 0) for row in avg_rows if row[0]}

    strongest_rows = await db.execute(
        select(CompetencyCategory.name, func.avg(SpecialistScore.score).cast(Integer).label("avg_score"))
        .join(SpecialistScore, SpecialistScore.category_id == CompetencyCategory.id)
        .join(User, User.id == SpecialistScore.specialist_id)
        .where(User.role == UserRole.SPECIALIST, User.is_active == True)  # noqa: E712
        .group_by(CompetencyCategory.name)
        .order_by(func.avg(SpecialistScore.score).desc())
        .limit(5)
    )
    strongest = [CompetencyAreaStat(category_name=r[0], avg_score=int(r[1])) for r in strongest_rows]

    weakest_rows = await db.execute(
        select(CompetencyCategory.name, func.avg(SpecialistScore.score).cast(Integer).label("avg_score"))
        .join(SpecialistScore, SpecialistScore.category_id == CompetencyCategory.id)
        .join(User, User.id == SpecialistScore.specialist_id)
        .where(User.role == UserRole.SPECIALIST, User.is_active == True)  # noqa: E712
        .group_by(CompetencyCategory.name)
        .order_by(func.avg(SpecialistScore.score).asc())
        .limit(5)
    )
    weakest = [CompetencyAreaStat(category_name=r[0], avg_score=int(r[1])) for r in weakest_rows]

    return HRStatsResponse(
        level_distribution=level_distribution,
        avg_progress_per_level=avg_progress,
        strongest_areas=strongest,
        weakest_areas=weakest,
    )
