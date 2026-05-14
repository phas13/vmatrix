from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent, UsageEventAction, UsageEventResourceType


async def record_event(
    db: AsyncSession,
    user_id: UUID | None,
    action_type: UsageEventAction,
    resource_id: UUID | None = None,
    resource_type: UsageEventResourceType | None = None,
) -> None:
    """Stage a usage event in the current transaction. Caller commits."""
    db.add(UsageEvent(
        user_id=user_id,
        action_type=action_type,
        resource_id=resource_id,
        resource_type=resource_type,
    ))
