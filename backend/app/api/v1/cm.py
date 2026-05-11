from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_role
from app.models.user import User, UserRole
from app.schemas.cm import DisputeDetailRead, DisputeResolveRequest, DisputeResolveResponse, PendingActionsResponse, SpecialistCardRead, SpecialistDetailRead
from app.services import cm_service

router = APIRouter()


@router.get("/team", response_model=list[SpecialistCardRead])
async def get_cm_team(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> list[SpecialistCardRead]:
    return await cm_service.get_team_overview(current_user.id, db)


@router.get("/specialists/{specialist_id}", response_model=SpecialistDetailRead)
async def get_specialist_detail(
    specialist_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> SpecialistDetailRead:
    return await cm_service.get_specialist_detail(current_user.id, specialist_id, db, page, per_page)


@router.get("/pending", response_model=PendingActionsResponse)
async def get_cm_pending(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> PendingActionsResponse:
    return await cm_service.get_pending_actions(current_user.id, db)


@router.get("/disputes/{dispute_id}", response_model=DisputeDetailRead)
async def get_cm_dispute(
    dispute_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> DisputeDetailRead:
    return await cm_service.get_dispute_detail(current_user.id, dispute_id, db)


@router.post("/disputes/{dispute_id}/actions/resolve", response_model=DisputeResolveResponse)
async def resolve_cm_dispute(
    dispute_id: UUID,
    body: DisputeResolveRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> DisputeResolveResponse:
    return await cm_service.resolve_dispute(current_user.id, dispute_id, body, db)
