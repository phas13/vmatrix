from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_role
from app.models.user import User, UserRole
from app.schemas.user import SpecialistSummary

router = APIRouter()


@router.get("/team", response_model=list[SpecialistSummary])
async def get_cm_team(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM, UserRole.ADMIN)),
):
    result = await db.execute(
        select(User).where(User.role == UserRole.SPECIALIST, User.cm_id == current_user.id)
    )
    return result.scalars().all()
