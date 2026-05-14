from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_role
from app.models.user import User, UserRole
from app.schemas.hr import HRStatsResponse
from app.services import hr_service

router = APIRouter()


@router.get("/stats", response_model=HRStatsResponse)
async def get_hr_stats(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.HR)),
) -> HRStatsResponse:
    return await hr_service.get_hr_stats(db)
