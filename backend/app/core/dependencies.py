from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProblemHTTPException
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole

__all__ = ["get_db_session", "get_current_user", "require_role", "verify_specialist_ownership"]


def _unauthorized(request: Request, detail: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=401,
        detail={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": "Unauthorized",
            "status": 401,
            "detail": detail,
            "instance": str(request.url.path),
        },
    )


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise _unauthorized(request, "Authentication required")
    try:
        payload = decode_access_token(token)
    except (HTTPException, JWTError, ValueError, TypeError):
        raise _unauthorized(request, "Invalid or expired access token")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized(request, "Invalid or expired access token")
    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise _unauthorized(request, "Invalid or expired access token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise _unauthorized(request, "User not found or inactive")
    return user


def require_role(*roles: UserRole) -> Callable:
    """Build a FastAPI dependency that enforces the caller has one of `roles`.

    Project-wide rule: every `require_role(*roles)` call MUST include
    `UserRole.ADMIN`, because ADMIN is a global superuser that bypasses
    role-scoped restrictions across all endpoints.

    Reads `current_user.role` from the User object already fetched by
    `get_current_user` — no additional DB lookup is performed for the role
    check (AC2 of Story 1.3).
    """
    if not roles:
        raise ValueError("require_role() requires at least one role")
    for role in roles:
        if not isinstance(role, UserRole):
            raise TypeError(f"require_role() expects UserRole values, got {type(role).__name__}")

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
    """Enforce cross-Specialist data isolation (Story 1.3 AC4 / FR39 / NFR10).

    EVERY service-layer function that returns Specialist-specific data MUST
    call this helper. Specialists may only access their own resources;
    attempts to reach another Specialist's data raise 404 (not 403) so the
    very existence of the resource is not revealed.

    CM, ADMIN, and HR roles bypass this check — they have legitimate
    cross-Specialist access scoped by their own RBAC at the route level.
    """
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
