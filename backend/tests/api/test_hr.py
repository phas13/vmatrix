from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.hr import CompetencyAreaStat, HRStatsResponse
from main import app


def _make_user(role: UserRole) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.role = role
    u.is_active = True
    u.email = f"{role.value}-{u.id.hex[:6]}@example.com"
    return u


def _make_jwt(user: MagicMock) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _make_auth_db(user: MagicMock):
    mock_db = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = user
    mock_db.execute = AsyncMock(return_value=r)

    async def override():
        yield mock_db

    return override, mock_db


_SAMPLE_STATS = HRStatsResponse(
    level_distribution={"junior": 3, "middle": 5, "senior": 2},
    avg_progress_per_level={"junior": 42, "middle": 67, "senior": 85},
    strongest_areas=[CompetencyAreaStat(category_name="Docker", avg_score=90)],
    weakest_areas=[CompetencyAreaStat(category_name="K8s", avg_score=30)],
)


@pytest.mark.asyncio
async def test_hr_stats_hr_user_gets_200(async_client):
    hr = _make_user(UserRole.HR)
    jwt = _make_jwt(hr)
    override, _ = _make_auth_db(hr)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.hr_service.get_hr_stats",
            new=AsyncMock(return_value=_SAMPLE_STATS),
        ):
            response = await async_client.get(
                "/api/v1/hr/stats",
                cookies={"access_token": jwt},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert "level_distribution" in data
    assert "avg_progress_per_level" in data
    assert "strongest_areas" in data
    assert "weakest_areas" in data
    assert data["level_distribution"] == {"junior": 3, "middle": 5, "senior": 2}


@pytest.mark.asyncio
async def test_hr_stats_specialist_gets_403(async_client):
    specialist = _make_user(UserRole.SPECIALIST)
    jwt = _make_jwt(specialist)
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            "/api/v1/hr/stats",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_hr_stats_cm_gets_403(async_client):
    cm = _make_user(UserRole.CM)
    jwt = _make_jwt(cm)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            "/api/v1/hr/stats",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_hr_stats_admin_gets_403(async_client):
    """Admin must get 403 — HR endpoint is HR-only (AC3 critical difference from old placeholder)."""
    admin = _make_user(UserRole.ADMIN)
    jwt = _make_jwt(admin)
    override, _ = _make_auth_db(admin)
    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            "/api/v1/hr/stats",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403
