from fastapi import APIRouter, Depends

from app.core.dependencies import require_role
from app.models.user import UserRole

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_status():
    return {"status": "admin_only"}
