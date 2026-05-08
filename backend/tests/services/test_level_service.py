from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.matrix import CompetencyCategory, CompetencyMatrix, MatrixStatus
from app.models.notification import Notification, NotificationType
from app.models.session import AssessmentSession, SessionStatus, SpecialistScore
from app.models.system_settings import SystemSettings
from app.models.user import SpecialistLevel, User
from app.services.level_service import check_threshold, get_dashboard_data
from tests._helpers import _now, _scalar_one_or_none_result, _scalars_result


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


# ─── check_threshold tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_threshold_below_threshold_returns_false():
    specialist_id = uuid4()

    score = MagicMock(spec=SpecialistScore)
    score.score = 80

    settings = MagicMock(spec=SystemSettings)
    settings.promotion_threshold = 90

    db = AsyncMock()
    execute_results = [
        _scalar_one_or_none_result(settings),  # SystemSettings
    ]
    db.execute = AsyncMock(side_effect=lambda *a, **k: execute_results.pop(0))

    result = await check_threshold(specialist_id, 80, db)

    assert result is False
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_check_threshold_reached_no_cm_returns_true():
    specialist_id = uuid4()

    score = MagicMock(spec=SpecialistScore)
    score.score = 95

    settings = MagicMock(spec=SystemSettings)
    settings.promotion_threshold = 90

    specialist = MagicMock(spec=User)
    specialist.cm_id = None

    db = AsyncMock()
    db.get.return_value = specialist
    execute_results = [
        _scalar_one_or_none_result(settings),  # SystemSettings
    ]
    db.execute = AsyncMock(side_effect=lambda *a, **k: execute_results.pop(0))

    result = await check_threshold(specialist_id, 95, db)

    assert result is True
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_check_threshold_reached_creates_cm_notification():
    specialist_id = uuid4()
    cm_id = uuid4()

    score = MagicMock(spec=SpecialistScore)
    score.score = 92

    settings = MagicMock(spec=SystemSettings)
    settings.promotion_threshold = 90

    specialist = MagicMock(spec=User)
    specialist.cm_id = cm_id
    specialist.full_name = "Ivan Lysenko"

    db = AsyncMock()
    db.get.return_value = specialist
    execute_results = [
        _scalar_one_or_none_result(settings),        # SystemSettings
        _scalar_one_or_none_result(None),            # dedup check → no existing notification
    ]
    db.execute = AsyncMock(side_effect=lambda *a, **k: execute_results.pop(0))

    added = []
    db.add = MagicMock(side_effect=added.append)

    result = await check_threshold(specialist_id, 92, db)

    assert result is True
    assert len(added) == 1
    notif = added[0]
    assert notif.type == NotificationType.PROMOTION_SUGGESTION
    assert notif.user_id == cm_id
    assert str(specialist_id) in notif.content


@pytest.mark.asyncio
async def test_check_threshold_deduplicates_existing_notification():
    specialist_id = uuid4()
    cm_id = uuid4()

    score = MagicMock(spec=SpecialistScore)
    score.score = 95

    settings = MagicMock(spec=SystemSettings)
    settings.promotion_threshold = 90

    specialist = MagicMock(spec=User)
    specialist.cm_id = cm_id
    specialist.full_name = "Ivan Lysenko"

    existing_notif = MagicMock(spec=Notification)

    db = AsyncMock()
    db.get.return_value = specialist
    execute_results = [
        _scalar_one_or_none_result(settings),              # SystemSettings
        _scalar_one_or_none_result(existing_notif),        # dedup check → already notified
    ]
    db.execute = AsyncMock(side_effect=lambda *a, **k: execute_results.pop(0))

    added = []
    db.add = MagicMock(side_effect=added.append)

    result = await check_threshold(specialist_id, 95, db)

    assert result is True
    assert len(added) == 0
