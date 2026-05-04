from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db_session
from app.core.exceptions import ProblemHTTPException
from app.models.user import User
from app.models.notification import Notification
from app.schemas.user import SpecialistSummary

router = APIRouter()


@router.get("/me", response_model=SpecialistSummary)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/notifications/unread")
async def get_unread_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False)
        )
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


@router.post("/me/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise ProblemHTTPException(
            status_code=404,
            detail={
                "type": "https://vmatrix.app/errors/notification-not-found",
                "title": "Notification not found",
                "status": 404,
                "detail": "Notification not found or belongs to another user",
                "instance": f"/api/v1/users/me/notifications/{notification_id}/read",
            },
        )
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
