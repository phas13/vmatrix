from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProblemHTTPException
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole

__all__ = ["get_db_session", "get_current_user", "require_role", "verify_specialist_ownership"]


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise ProblemHTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Authentication required",
                "instance": str(request.url.path),
            },
        )
    try:
        payload = decode_access_token(token)
    except HTTPException:
        raise ProblemHTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid or expired access token",
                "instance": str(request.url.path),
            },
        )
    user_id_str = payload.get("sub")
    result = await db.execute(select(User).where(User.id == UUID(user_id_str)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ProblemHTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "User not found or inactive",
                "instance": str(request.url.path),
            },
        )
    return user


def require_role(*roles: UserRole) -> Callable:
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise ProblemHTTPException(
                status_code=403,
                detail={
                    "type": "https://tools.ietf.org/html/rfc7807",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": "Insufficient permissions for this action",
                    "instance": str(request.url.path),
                },
            )
        return current_user

    return dependency


async def verify_specialist_ownership(specialist_id: UUID, current_user: User) -> None:
    # Prevent cross-Specialist data leakage: return 404 (not 403) so resource existence is not revealed
    if current_user.role == UserRole.SPECIALIST and specialist_id != current_user.id:
        raise ProblemHTTPException(
            status_code=404,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Not Found",
                "status": 404,
                "detail": "Resource not found",
                "instance": "",
            },
        )
