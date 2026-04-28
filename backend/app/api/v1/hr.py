from fastapi import APIRouter, Depends

from app.core.dependencies import require_role
from app.models.user import UserRole

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role(UserRole.HR))])
async def hr_status():
    return {"status": "hr_only"}
