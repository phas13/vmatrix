import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_csrf_token,
    hash_token,
    verify_password,
)
from app.models.usage_event import UsageEventAction
from app.models.user import RefreshToken, User
from app.services import usage_service

logger = logging.getLogger(__name__)


def _auth_refresh_401() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": "Unauthorized",
            "status": 401,
            "detail": "Refresh token is invalid, expired, or revoked",
            "instance": "/api/v1/auth/refresh",
        },
    )


async def login(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # NOTE: timing oracle — when user is absent, verify_password is skipped.
    # Proper equalization requires a pre-computed dummy hash; deferred until passlib/bcrypt
    # compatibility is resolved (see deferred-work.md: timing equalization placeholder).
    if not user or not verify_password(password, user.hashed_password):
        logger.warning("login failed email=%s", email)
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid email or password",
                "instance": "/api/v1/auth/login",
            },
        )

    if not user.is_active:
        logger.warning("login rejected inactive user_id=%s", user.id)
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid email or password",
                "instance": "/api/v1/auth/login",
            },
        )

    logger.info("login success user_id=%s", user.id)
    return user


async def create_session(user: User, db: AsyncSession) -> tuple[str, str, str]:
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_raw = create_refresh_token()
    csrf_token = generate_csrf_token()

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_raw),
        expires_at=expires_at,
        family_id=uuid4(),
    )
    db.add(rt)
    await usage_service.record_event(db, user.id, UsageEventAction.USER_LOGIN)
    await db.commit()

    logger.info("session created user_id=%s", user.id)
    return access_token, refresh_raw, csrf_token


async def rotate_refresh_token(
    refresh_token_raw: str,
    csrf_header: str | None,
    csrf_cookie: str | None,
    db: AsyncSession,
) -> tuple[str, str, str]:
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        logger.warning("CSRF token missing or invalid on /auth/refresh")
        raise HTTPException(
            status_code=403,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Forbidden",
                "status": 403,
                "detail": "CSRF token missing or invalid",
                "instance": "/api/v1/auth/refresh",
            },
        )

    if not refresh_token_raw:
        raise _auth_refresh_401()

    token_hash = hash_token(refresh_token_raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not rt:
        raise _auth_refresh_401()

    expires_at = rt.expires_at if rt.expires_at.tzinfo else rt.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise _auth_refresh_401()

    if rt.revoked_at is not None:
        # Token reuse detected — potential theft signal. Revoke the entire family.
        logger.warning(
            "token reuse detected, revoking family_id=%s user_id=%s", rt.family_id, rt.user_id
        )
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Session invalidated — possible token theft detected",
                "instance": "/api/v1/auth/refresh",
            },
        )

    # Fetch and validate user BEFORE revoking the old token.
    result = await db.execute(select(User).where(User.id == rt.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise _auth_refresh_401()

    rt.revoked_at = now

    new_access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    new_refresh_raw = create_refresh_token()
    new_csrf_token = generate_csrf_token()

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        family_id=rt.family_id,
    )
    db.add(new_rt)
    await db.commit()

    logger.info("refresh success user_id=%s", user.id)
    return new_access_token, new_refresh_raw, new_csrf_token


async def revoke_session(refresh_token_raw: str, db: AsyncSession) -> None:
    if not refresh_token_raw:
        return

    token_hash = hash_token(refresh_token_raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()

    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("session revoked token_hash_prefix=%s", token_hash[:8])
