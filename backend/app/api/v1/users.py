from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db_session
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
            Notification.is_read == False
        )
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()
