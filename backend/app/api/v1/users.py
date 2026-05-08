from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db_session, require_role
from app.core.exceptions import ProblemHTTPException
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.schemas.notification import NotificationRead
from app.schemas.pagination import PaginatedResponse
from app.schemas.session import SpecialistDashboardRead
from app.schemas.user import SpecialistSummary
from app.services import level_service

router = APIRouter()


@router.get("/me", response_model=SpecialistSummary)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/dashboard", response_model=SpecialistDashboardRead)
async def get_specialist_dashboard(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.SPECIALIST)),
) -> SpecialistDashboardRead:
    return await level_service.get_dashboard_data(current_user.id, db)


@router.get("/me/notifications/unread", response_model=PaginatedResponse[NotificationRead])
async def get_unread_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Standard pagination logic
    from sqlalchemy import func
    offset = (page - 1) * per_page

    stmt = select(Notification, func.count().over().label("total")).where(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False)
    ).order_by(Notification.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return PaginatedResponse(items=[], total=0, page=page, per_page=per_page, pages=0)

    notifications = [row[0] for row in rows]
    total = rows[0][1]
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse(items=notifications, total=total, page=page, per_page=per_page, pages=pages)


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
    
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        
    return {"ok": True}
