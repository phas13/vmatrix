from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_csrf, require_role
from app.models.user import User, UserRole
from app.schemas.matrix import MatrixRead
from app.services import matrix_service

router = APIRouter()


@router.post(
    "/{specialist_id}/actions/generate",
    response_model=MatrixRead,
    dependencies=[Depends(require_csrf)],
)
async def generate_matrix(
    specialist_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SPECIALIST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    return await matrix_service.generate_initial_matrix(
        specialist_id,
        db,
        current_user=current_user,
        instance=str(request.url.path),
    )


@router.get(
    "/{specialist_id}",
    response_model=MatrixRead,
)
async def get_matrix(
    specialist_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SPECIALIST, UserRole.CM, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    return await matrix_service.get_matrix(
        specialist_id,
        db,
        current_user=current_user,
        instance=str(request.url.path),
    )
