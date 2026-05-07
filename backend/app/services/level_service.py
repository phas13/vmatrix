import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import SpecialistScore

logger = logging.getLogger(__name__)


async def calculate_percentage(specialist_id: UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(SpecialistScore).where(SpecialistScore.specialist_id == specialist_id)
    )
    scores = result.scalars().all()
    if not scores:
        return 0
    return round(sum(s.score for s in scores) / len(scores))


async def check_threshold(specialist_id: UUID, db: AsyncSession) -> bool:
    """Story 5.3: check if specialist reached promotion threshold."""
    raise NotImplementedError("Implemented in Story 5.3")
