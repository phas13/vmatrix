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
    result = await db.execute(
        select(SpecialistScore).where(SpecialistScore.specialist_id == specialist_id)
    )
    scores = result.scalars().all()
    if not scores:
        return 0
    return round(sum(s.score for s in scores) / len(scores))


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
        round(sum(in_matrix_score_values) / len(in_matrix_score_values))
        if in_matrix_score_values
        else 0
    )

    return SpecialistDashboardRead(
        specialist_level=specialist_level,
        overall_percentage=overall_percentage,
        category_scores=category_scores,
    )


async def check_threshold(specialist_id: UUID, db: AsyncSession) -> bool:
    """Story 5.3: check if specialist reached promotion threshold."""
    raise NotImplementedError("Implemented in Story 5.3")
