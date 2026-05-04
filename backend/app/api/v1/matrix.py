from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_csrf, require_role
from app.models.user import User, UserRole
from app.schemas.matrix import MatrixRead, SubItemFlagRequest, SubItemRead
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


@router.post(
    "/{specialist_id}/sub-items/{sub_item_id}/actions/flag",
    response_model=SubItemRead,
    dependencies=[Depends(require_csrf)],
)
async def flag_sub_item(
    specialist_id: UUID,
    sub_item_id: UUID,
    body: SubItemFlagRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SPECIALIST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    return await matrix_service.flag_sub_item(
        specialist_id,
        sub_item_id,
        body.note,
        db,
        current_user=current_user,
        instance=str(request.url.path),
    )


@router.post(
    "/{specialist_id}/sub-items/{sub_item_id}/actions/unflag",
    response_model=SubItemRead,
    dependencies=[Depends(require_csrf)],
)
async def unflag_sub_item(
    specialist_id: UUID,
    sub_item_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SPECIALIST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    return await matrix_service.unflag_sub_item(
        specialist_id,
        sub_item_id,
        db,
        current_user=current_user,
        instance=str(request.url.path),
    )


@router.post(
    "/{specialist_id}/actions/submit",
    response_model=MatrixRead,
    dependencies=[Depends(require_csrf)],
)
async def submit_matrix(
    specialist_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SPECIALIST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    return await matrix_service.submit_for_review(
        specialist_id,
        db,
        current_user=current_user,
        instance=str(request.url.path),
    )
