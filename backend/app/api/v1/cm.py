from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_role
from app.models.user import User, UserRole
from app.schemas.cm import DisputeDetailRead, DisputeResolveRequest, DisputeResolveResponse, MatrixProposalDecideResponse, MatrixProposalDetailRead, PendingActionsResponse, PromotionDecideRequest, PromotionDecideResponse, PromotionDetailRead, SpecialistCardRead, SpecialistDetailRead
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


@router.get("/promotions/{notification_id}", response_model=PromotionDetailRead)
async def get_cm_promotion(
    notification_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> PromotionDetailRead:
    return await cm_service.get_promotion_detail(current_user.id, notification_id, db, page, per_page)


@router.post("/promotions/{notification_id}/actions/approve", response_model=PromotionDecideResponse)
async def approve_cm_promotion(
    notification_id: UUID,
    body: PromotionDecideRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> PromotionDecideResponse:
    return await cm_service.approve_promotion(current_user.id, notification_id, body, db)


@router.post("/promotions/{notification_id}/actions/reject", response_model=PromotionDecideResponse)
async def reject_cm_promotion(
    notification_id: UUID,
    body: PromotionDecideRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> PromotionDecideResponse:
    return await cm_service.reject_promotion(current_user.id, notification_id, body, db)


@router.get("/matrix-proposals/{proposal_id}", response_model=MatrixProposalDetailRead)
async def get_cm_matrix_proposal(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> MatrixProposalDetailRead:
    return await cm_service.get_matrix_proposal_detail(current_user.id, proposal_id, db)


@router.post("/matrix-proposals/{proposal_id}/actions/approve", response_model=MatrixProposalDecideResponse)
async def approve_cm_matrix_proposal(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> MatrixProposalDecideResponse:
    return await cm_service.approve_matrix_proposal(current_user.id, proposal_id, db)


@router.post("/matrix-proposals/{proposal_id}/actions/reject", response_model=MatrixProposalDecideResponse)
async def reject_cm_matrix_proposal(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.CM)),
) -> MatrixProposalDecideResponse:
    return await cm_service.reject_matrix_proposal(current_user.id, proposal_id, db)
