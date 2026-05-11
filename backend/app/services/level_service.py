import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.session import AssessmentSession, SessionStatus, SpecialistScore
from app.models.user import User
from app.schemas.session import CategoryScoreRead, SpecialistDashboardRead

logger = logging.getLogger(__name__)


async def calculate_percentage(specialist_id: UUID, db: AsyncSession) -> int:
    # Get approved matrix for this specialist
    matrix_result = await db.execute(
        select(CompetencyMatrix).where(
            CompetencyMatrix.specialist_id == specialist_id,
            CompetencyMatrix.status == MatrixStatus.APPROVED,
        )
    )
    matrix = matrix_result.scalar_one_or_none()
    if not matrix:
        return 0

    # Get categories for this matrix
    cats_result = await db.execute(
        select(CompetencyCategory.id).where(CompetencyCategory.matrix_id == matrix.id)
    )
    category_ids = cats_result.scalars().all()
    if not category_ids:
        return 0

    # Get scores only for these categories
    scores_result = await db.execute(
        select(SpecialistScore.score).where(
            SpecialistScore.specialist_id == specialist_id,
            SpecialistScore.category_id.in_(category_ids)
        )
    )
    scores = scores_result.scalars().all()
    if not scores:
        return 0

    return round(sum(scores) / len(category_ids))


async def calculate_bulk_percentages(specialist_ids: list[UUID], db: AsyncSession) -> dict[UUID, int]:
    """Calculate overall percentages for multiple specialists in bulk to avoid N+1 queries."""
    if not specialist_ids:
        return {}

    # 1. Get approved matrices for these specialists
    matrices_result = await db.execute(
        select(CompetencyMatrix).where(
            CompetencyMatrix.specialist_id.in_(specialist_ids),
            CompetencyMatrix.status == MatrixStatus.APPROVED,
        )
    )
    matrices = matrices_result.scalars().all()
    if not matrices:
        return {sid: 0 for sid in specialist_ids}

    matrix_map = {m.id: m.specialist_id for m in matrices}
    spec_to_matrix_id = {m.specialist_id: m.id for m in matrices}

    # 2. Get category counts per matrix
    cats_result = await db.execute(
        select(CompetencyCategory.matrix_id, func.count(CompetencyCategory.id).label("cat_count"))
        .where(CompetencyCategory.matrix_id.in_(spec_to_matrix_id.values()))
        .group_by(CompetencyCategory.matrix_id)
    )
    cat_counts = {row.matrix_id: row.cat_count for row in cats_result.all()}

    # 3. Get sum of scores per specialist for categories in their approved matrix
    # We join with CompetencyCategory to ensure we only sum scores for the specialist's current matrix
    scores_result = await db.execute(
        select(
            SpecialistScore.specialist_id,
            func.sum(SpecialistScore.score).label("total_score")
        )
        .join(CompetencyCategory, CompetencyCategory.id == SpecialistScore.category_id)
        .where(
            SpecialistScore.specialist_id.in_(specialist_ids),
            CompetencyCategory.matrix_id.in_(spec_to_matrix_id.values())
        )
        .group_by(SpecialistScore.specialist_id)
    )
    total_scores = {row.specialist_id: row.total_score for row in scores_result.all()}

    # 4. Assemble results
    results: dict[UUID, int] = {}
    for sid in specialist_ids:
        matrix_id = spec_to_matrix_id.get(sid)
        cat_count = cat_counts.get(matrix_id, 0) if matrix_id else 0
        total_score = total_scores.get(sid, 0)
        
        if cat_count > 0:
            results[sid] = round(total_score / cat_count)
        else:
            results[sid] = 0
            
    return results


async def get_dashboard_data(specialist_id: UUID, db: AsyncSession) -> SpecialistDashboardRead:
    user = await db.get(User, specialist_id)
    specialist_level = user.specialist_level if user else None

    matrix_result = await db.execute(
        select(CompetencyMatrix).where(
            CompetencyMatrix.specialist_id == specialist_id,
            CompetencyMatrix.status == MatrixStatus.APPROVED,
        )
    )
    matrix = matrix_result.scalar_one_or_none()
    if matrix is None:
        return SpecialistDashboardRead(
            specialist_level=specialist_level,
            overall_percentage=0,
            category_scores=[],
        )

    cats_result = await db.execute(
        select(CompetencyCategory)
        .where(CompetencyCategory.matrix_id == matrix.id)
        .order_by(CompetencyCategory.order)
    )
    categories = cats_result.scalars().all()

    scores_result = await db.execute(
        select(SpecialistScore).where(SpecialistScore.specialist_id == specialist_id)
    )
    scores: dict[UUID, SpecialistScore] = {s.category_id: s for s in scores_result.scalars().all()}

    category_scores: list[CategoryScoreRead] = []
    in_matrix_score_values: list[int] = []
    for cat in categories:
        spec_score = scores.get(cat.id)
        if spec_score is None:
            category_scores.append(CategoryScoreRead(
                category_id=cat.id,
                category_name=cat.name,
                score=None,
                previous_score=None,
                last_assessed_at=None,
            ))
        else:
            session_result = await db.execute(
                select(AssessmentSession)
                .where(
                    AssessmentSession.specialist_id == specialist_id,
                    AssessmentSession.category_id == cat.id,
                    AssessmentSession.status == SessionStatus.COMPLETED,
                )
                .order_by(AssessmentSession.created_at.desc())
                .limit(1)
            )
            last_session = session_result.scalar_one_or_none()
            category_scores.append(CategoryScoreRead(
                category_id=cat.id,
                category_name=cat.name,
                score=spec_score.score,
                previous_score=last_session.previous_score if last_session else None,
                last_assessed_at=spec_score.last_assessed_at,
            ))
            in_matrix_score_values.append(spec_score.score)

    overall_percentage = (
        round(sum(in_matrix_score_values) / len(categories))
        if categories
        else 0
    )

    return SpecialistDashboardRead(
        specialist_level=specialist_level,
        overall_percentage=overall_percentage,
        category_scores=category_scores,
    )


async def check_threshold(specialist_id: UUID, percentage: int, db: AsyncSession) -> bool:
    from app.models.notification import Notification, NotificationType
    from app.models.system_settings import SystemSettings

    settings_result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    threshold = settings.promotion_threshold if settings else 90

    if percentage < threshold:
        return False

    specialist = await db.get(User, specialist_id)
    if not specialist or not specialist.cm_id:
        return True

    existing_result = await db.execute(
        select(Notification).where(
            Notification.user_id == specialist.cm_id,
            Notification.type == NotificationType.PROMOTION_SUGGESTION,
            Notification.is_read.is_(False),
            Notification.content.contains(str(specialist_id)),
        )
    )
    if existing_result.scalar_one_or_none():
        return True

    notification = Notification(
        user_id=specialist.cm_id,
        type=NotificationType.PROMOTION_SUGGESTION,
        content=f"Specialist {specialist.full_name} has reached the promotion threshold — review pending [{specialist_id}]",
    )
    db.add(notification)
    return True
