from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_csrf_token,
    hash_token,
    verify_password,
)
from app.models.user import RefreshToken, User


async def login(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
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

    return user


async def create_session(
    user: User, db: AsyncSession
) -> tuple[str, str, str]:
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_raw = create_refresh_token()
    csrf_token = generate_csrf_token()

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_raw),
        expires_at=expires_at,
    )
    db.add(rt)

    return access_token, refresh_raw, csrf_token


async def rotate_refresh_token(
    refresh_token_raw: str,
    csrf_header: str | None,
    csrf_cookie: str | None,
    db: AsyncSession,
) -> tuple[str, str, str]:
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
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

    token_hash = hash_token(refresh_token_raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not rt or rt.expires_at.replace(tzinfo=timezone.utc) <= now or rt.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://tools.ietf.org/html/rfc7807",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Refresh token is invalid, expired, or revoked",
                "instance": "/api/v1/auth/refresh",
            },
        )

    rt.revoked_at = now

    result = await db.execute(select(User).where(User.id == rt.user_id))
    user = result.scalar_one_or_none()

    new_access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    new_refresh_raw = create_refresh_token()
    new_csrf_token = generate_csrf_token()

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)

    return new_access_token, new_refresh_raw, new_csrf_token


async def revoke_session(refresh_token_raw: str, db: AsyncSession) -> None:
    if not refresh_token_raw:
        return

    token_hash = hash_token(refresh_token_raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()

    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)
