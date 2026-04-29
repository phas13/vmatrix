import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_role
from app.models.user import User, UserRole
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import UserCreate, UserRead
from app.services import admin_service

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_status():
    return {"status": "admin_only"}


@router.get("/users", response_model=PaginatedResponse[UserRead])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    users, total = await admin_service.list_users(page, per_page, db)
    pages = math.ceil(total / per_page) if total else 0
    return PaginatedResponse(items=users, total=total, page=page, per_page=per_page, pages=pages)


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    user = await admin_service.create_user(body, db)
    return user
