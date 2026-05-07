from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.session import AssessmentSession, SessionStatus, SpecialistScore
from app.models.user import SpecialistLevel, User
from app.services.level_service import get_dashboard_data


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scalars_result(values) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _scalar_one_or_none_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


@pytest.mark.asyncio
async def test_get_dashboard_data_no_matrix():
    """Returns empty scores and zero percentage when no approved matrix exists."""
    specialist_id = uuid4()
    db = AsyncMock()

    user = MagicMock(spec=User)
    user.specialist_level = SpecialistLevel.JUNIOR
    db.get.return_value = user

    execute_results = [
        _scalar_one_or_none_result(None),  # matrix query → no approved matrix
    ]

    async def fake_execute(*_args, **_kwargs):
        return execute_results.pop(0)

    db.execute = AsyncMock(side_effect=fake_execute)

    result = await get_dashboard_data(specialist_id, db)

    assert result.overall_percentage == 0
    assert result.category_scores == []
    assert result.specialist_level == SpecialistLevel.JUNIOR


@pytest.mark.asyncio
async def test_get_dashboard_data_with_scored_categories():
    """Returns correct score, previous_score, and last_assessed_at for assessed categories."""
    specialist_id = uuid4()
    db = AsyncMock()

    user = MagicMock(spec=User)
    user.specialist_level = SpecialistLevel.MIDDLE
    db.get.return_value = user

    matrix = MagicMock(spec=CompetencyMatrix)
    matrix.id = uuid4()
    matrix.specialist_id = specialist_id
    matrix.status = MatrixStatus.APPROVED

    cat = MagicMock(spec=CompetencyCategory)
    cat.id = uuid4()
    cat.name = "Kubernetes"
    cat.order = 0

    spec_score = MagicMock(spec=SpecialistScore)
    spec_score.specialist_id = specialist_id
    spec_score.category_id = cat.id
    spec_score.score = 78
    spec_score.last_assessed_at = _now()

    last_session = MagicMock(spec=AssessmentSession)
    last_session.previous_score = 71
    last_session.status = SessionStatus.COMPLETED

    execute_results = [
        _scalar_one_or_none_result(matrix),       # matrix query
        _scalars_result([cat]),                    # categories query
        _scalars_result([spec_score]),             # specialist scores
        _scalar_one_or_none_result(last_session),  # last session for cat
        _scalars_result([spec_score]),             # calculate_percentage reuses SpecialistScore
    ]

    async def fake_execute(*_args, **_kwargs):
        return execute_results.pop(0)

    db.execute = AsyncMock(side_effect=fake_execute)

    result = await get_dashboard_data(specialist_id, db)

    assert result.specialist_level == SpecialistLevel.MIDDLE
    assert result.overall_percentage == 78
    assert len(result.category_scores) == 1
    cs = result.category_scores[0]
    assert cs.category_id == cat.id
    assert cs.category_name == "Kubernetes"
    assert cs.score == 78
    assert cs.previous_score == 71
    assert cs.last_assessed_at == spec_score.last_assessed_at


@pytest.mark.asyncio
async def test_get_dashboard_data_unassessed_category():
    """Unassessed category is included with score=None, previous_score=None, last_assessed_at=None."""
    specialist_id = uuid4()
    db = AsyncMock()

    user = MagicMock(spec=User)
    user.specialist_level = SpecialistLevel.JUNIOR
    db.get.return_value = user

    matrix = MagicMock(spec=CompetencyMatrix)
    matrix.id = uuid4()
    matrix.specialist_id = specialist_id
    matrix.status = MatrixStatus.APPROVED

    cat = MagicMock(spec=CompetencyCategory)
    cat.id = uuid4()
    cat.name = "Docker"
    cat.order = 0

    execute_results = [
        _scalar_one_or_none_result(matrix),  # matrix query
        _scalars_result([cat]),               # categories query
        _scalars_result([]),                  # no specialist scores
        _scalars_result([]),                  # calculate_percentage: no scores → 0
    ]

    async def fake_execute(*_args, **_kwargs):
        return execute_results.pop(0)

    db.execute = AsyncMock(side_effect=fake_execute)

    result = await get_dashboard_data(specialist_id, db)

    assert result.overall_percentage == 0
    assert len(result.category_scores) == 1
    cs = result.category_scores[0]
    assert cs.category_name == "Docker"
    assert cs.score is None
    assert cs.previous_score is None
    assert cs.last_assessed_at is None
