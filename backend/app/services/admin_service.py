from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProblemHTTPException
from app.core.security import hash_password
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


async def create_user(body: UserCreate, db: AsyncSession) -> User:
    user = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        hashed_password=hash_password(body.password),
        specialist_level=body.specialist_level,
        cm_id=body.cm_id,
    )
    db.add(user)

    if body.role == UserRole.SPECIALIST and body.cm_id is not None:
        notification = Notification(
            user_id=body.cm_id,
            type=NotificationType.NEW_CM_ASSIGNMENT,
            content=f"{body.full_name} has been assigned to you — begin initialization",
        )
        db.add(notification)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_users_email" in str(exc.orig):
            raise ProblemHTTPException(
                status_code=409,
                detail={
                    "type": "https://vmatrix.app/errors/user-email-conflict",
                    "title": "Email already in use",
                    "status": 409,
                    "detail": "A user with this email already exists",
                    "instance": "/api/v1/admin/users",
                },
            )
        raise

    await db.refresh(user)
    return user


async def list_users(page: int, per_page: int, db: AsyncSession) -> tuple[list[User], int]:
    per_page = min(per_page, 100)

    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar_one()

    offset = (page - 1) * per_page
    result = await db.execute(select(User).offset(offset).limit(per_page))
    users = list(result.scalars().all())

    return users, total
