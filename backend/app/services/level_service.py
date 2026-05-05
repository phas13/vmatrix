import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def calculate_percentage(specialist_id: UUID, db: AsyncSession) -> int:
    """Story 4.3: calculate overall level percentage from SpecialistScore records."""
    raise NotImplementedError("Implemented in Story 4.3")


async def check_threshold(specialist_id: UUID, db: AsyncSession) -> bool:
    """Story 5.3: check if specialist reached promotion threshold."""
    raise NotImplementedError("Implemented in Story 5.3")
