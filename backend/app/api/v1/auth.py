from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db_session
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter()


def _problem_response(exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        media_type="application/problem+json",
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db_session)):
    try:
        user = await auth_service.login(body.email, body.password, db)
    except HTTPException as exc:
        return _problem_response(exc)

    access_token, refresh_raw, csrf_token = await auth_service.create_session(user, db)

    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        "refresh_token", refresh_raw,
        httponly=True, secure=True, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.set_cookie(
        "csrf_token", csrf_token,
        httponly=False, secure=True, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(id=user.id, role=user.role.value, email=user.email, full_name=user.full_name)


@router.post("/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    refresh_token_raw = request.cookies.get("refresh_token", "")
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get("csrf_token")

    try:
        access_token, refresh_raw, csrf_token = await auth_service.rotate_refresh_token(
            refresh_token_raw, csrf_header, csrf_cookie, db
        )
    except HTTPException as exc:
        return _problem_response(exc)

    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        "refresh_token", refresh_raw,
        httponly=True, secure=True, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.set_cookie(
        "csrf_token", csrf_token,
        httponly=False, secure=True, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {"message": "Token refreshed"}


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    refresh_token_raw = request.cookies.get("refresh_token", "")
    await auth_service.revoke_session(refresh_token_raw, db)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")

    return {"message": "Logged out"}
