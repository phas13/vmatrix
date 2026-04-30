import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProblemHTTPException
from app.core.security import hash_password
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def _email_conflict(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=409,
        detail={
            "type": "https://vmatrix.app/errors/user-email-conflict",
            "title": "Email already in use",
            "status": 409,
            "detail": "A user with this email already exists",
            "instance": instance,
        },
    )


def _invalid_cm(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/invalid-cm-assignment",
            "title": "Invalid CM assignment",
            "status": 422,
            "detail": "Selected CM does not exist or is not an active Competency Manager",
            "instance": instance,
        },
    )


def _constraint_violation(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=422,
        detail={
            "type": "https://vmatrix.app/errors/constraint-violation",
            "title": "Constraint violation",
            "status": 422,
            "detail": "The request violates a database constraint",
            "instance": instance,
        },
    )


async def create_user(
    body: UserCreate,
    db: AsyncSession,
    *,
    actor_id: UUID,
    instance: str = "/api/v1/admin/users",
) -> User:
    if body.cm_id is not None:
        cm_lookup = await db.execute(select(User).where(User.id == body.cm_id))
        cm_user = cm_lookup.scalar_one_or_none()
        if cm_user is None or cm_user.role != UserRole.CM or not cm_user.is_active:
            raise _invalid_cm(instance)

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
        constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
        exc_text = str(exc.orig)
        if constraint_name in {"uq_users_email", "uq_users_email_lower"} or (
            "uq_users_email" in exc_text or "uq_users_email_lower" in exc_text
        ):
            raise _email_conflict(instance)
        raise _constraint_violation(instance)

    await db.refresh(user)
    logger.info(
        "admin user created actor_id=%s new_user_id=%s role=%s",
        actor_id,
        user.id,
        user.role.value,
    )
    return user


async def update_specialist_cm(
    user_id: UUID,
    cm_id: UUID | None,
    db: AsyncSession,
    *,
    actor_id: UUID,
    instance: str,
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ProblemHTTPException(
            status_code=404,
            detail={
                "type": "https://vmatrix.app/errors/user-not-found",
                "title": "User not found",
                "status": 404,
                "detail": f"User {user_id} does not exist",
                "instance": instance,
            },
        )

    if user.role != UserRole.SPECIALIST:
        raise ProblemHTTPException(
            status_code=422,
            detail={
                "type": "https://vmatrix.app/errors/invalid-assignment-target",
                "title": "Invalid assignment target",
                "status": 422,
                "detail": "CM assignment can only be updated for Specialist accounts",
                "instance": instance,
            },
        )

    if cm_id is not None and cm_id == user_id:
        raise ProblemHTTPException(
            status_code=422,
            detail={
                "type": "https://vmatrix.app/errors/self-cm-assignment",
                "title": "Self-assignment not allowed",
                "status": 422,
                "detail": "A user cannot be assigned as their own CM",
                "instance": instance,
            },
        )

    if cm_id is not None:
        cm_result = await db.execute(select(User).where(User.id == cm_id))
        cm_user = cm_result.scalar_one_or_none()
        if cm_user is None or cm_user.role != UserRole.CM or not cm_user.is_active:
            raise _invalid_cm(instance)

    user.cm_id = cm_id

    if cm_id is not None:
        notification = Notification(
            user_id=cm_id,
            type=NotificationType.NEW_CM_ASSIGNMENT,
            content=f"{user.full_name} has been assigned to you",
        )
        db.add(notification)

    await db.commit()
    await db.refresh(user)
    logger.info(
        "admin cm reassignment actor_id=%s specialist_id=%s new_cm_id=%s",
        actor_id,
        user_id,
        cm_id,
    )
    return user


async def list_users(
    page: int,
    per_page: int,
    db: AsyncSession,
    *,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    per_page = min(per_page, 500)
    offset = (page - 1) * per_page

    stmt = select(User, func.count().over().label("total"))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    stmt = stmt.order_by(User.created_at.desc(), User.id).offset(offset).limit(per_page)

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        # Page is empty — fall back to a count-only query so total reflects
        # filter-matching rows even when the requested page is past the end.
        count_stmt = select(func.count()).select_from(User)
        if role is not None:
            count_stmt = count_stmt.where(User.role == role)
        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active == is_active)
        total = (await db.execute(count_stmt)).scalar_one()
        return [], total

    users = [row[0] for row in rows]
    total = rows[0][1]
    return users, total
