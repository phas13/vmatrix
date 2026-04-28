from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole
from main import app


def _make_user(role: UserRole, user_id=None) -> User:
    user = MagicMock(spec=User)
    user.id = user_id or uuid4()
    user.email = f"{role.value}@example.com"
    user.full_name = f"Test {role.value.title()}"
    user.role = role
    user.is_active = True
    user.cm_id = None
    return user


def _make_jwt(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _db_returning(user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override():
        yield mock_db

    return override, mock_db


# ─── AC5: No cookie → 401 RFC 7807 ───────────────────────────────────────────

async def test_unauthenticated_request_returns_401_rfc7807(async_client):
    response = await async_client.get("/api/v1/cm/team")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for key in ("type", "title", "status", "detail", "instance"):
        assert key in body, f"Missing RFC 7807 key: {key}"
    assert body["status"] == 401


# ─── AC5b: Expired/invalid JWT → 401 RFC 7807 ────────────────────────────────

async def test_invalid_jwt_returns_401_rfc7807(async_client):
    response = await async_client.get(
        "/api/v1/cm/team",
        cookies={"access_token": "this.is.not.valid.jwt"},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 401


# ─── AC1: Specialist calling CM endpoint → 403 RFC 7807 ──────────────────────

async def test_specialist_cannot_access_cm_team_returns_403(async_client):
    specialist = _make_user(UserRole.SPECIALIST)
    override, _ = _db_returning(specialist)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            "/api/v1/cm/team",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 403
    assert body["title"] == "Forbidden"


# ─── AC2: DB queried exactly once per request (role from JWT, not extra query) ─

async def test_cm_team_db_queried_once_for_user_lookup(async_client):
    cm = _make_user(UserRole.CM)

    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = cm
    mock_result_list = MagicMock()
    mock_result_list.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_result_user, mock_result_list])

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.get(
            "/api/v1/cm/team",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    # First execute call: get_current_user user lookup
    # Second execute call: cm/team specialist query
    assert mock_db.execute.call_count == 2


# ─── AC3: CM team returns only CM's assigned specialists ──────────────────────

async def test_cm_team_returns_only_assigned_specialists(async_client):
    cm = _make_user(UserRole.CM)
    specialist = _make_user(UserRole.SPECIALIST)
    specialist.cm_id = cm.id

    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = cm
    mock_result_list = MagicMock()
    mock_result_list.scalars.return_value.all.return_value = [specialist]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_result_user, mock_result_list])

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.get(
            "/api/v1/cm/team",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == specialist.email


# ─── AC4: Cross-Specialist access → 404 (resource existence not revealed) ─────

async def test_verify_specialist_ownership_own_resource_passes(async_client):
    from uuid import uuid4 as _uuid4
    from app.core.dependencies import verify_specialist_ownership
    from app.core.exceptions import ProblemHTTPException

    specialist = _make_user(UserRole.SPECIALIST)
    # Accessing own resource — should not raise
    await verify_specialist_ownership(specialist.id, specialist)


async def test_verify_specialist_ownership_other_resource_raises_404(async_client):
    from app.core.dependencies import verify_specialist_ownership
    from app.core.exceptions import ProblemHTTPException

    specialist = _make_user(UserRole.SPECIALIST)
    other_id = uuid4()

    with pytest.raises(ProblemHTTPException) as exc_info:
        await verify_specialist_ownership(other_id, specialist)

    assert exc_info.value.status_code == 404


async def test_verify_specialist_ownership_cm_can_access_any_specialist(async_client):
    from app.core.dependencies import verify_specialist_ownership

    cm = _make_user(UserRole.CM)
    specialist_id = uuid4()

    # CM accessing any specialist resource — should not raise
    await verify_specialist_ownership(specialist_id, cm)


# ─── GET /api/v1/users/me ─────────────────────────────────────────────────────

async def test_users_me_returns_current_user(async_client):
    specialist = _make_user(UserRole.SPECIALIST)
    override, _ = _db_returning(specialist)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            "/api/v1/users/me",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == specialist.email
    assert data["role"] == UserRole.SPECIALIST.value


async def test_users_me_unauthenticated_returns_401(async_client):
    response = await async_client.get("/api/v1/users/me")
    assert response.status_code == 401


# ─── Admin / HR placeholder endpoints ─────────────────────────────────────────

async def test_admin_status_requires_admin_role(async_client):
    specialist = _make_user(UserRole.SPECIALIST)
    override, _ = _db_returning(specialist)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            "/api/v1/admin/status",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


async def test_admin_status_accessible_by_admin(async_client):
    admin = _make_user(UserRole.ADMIN)
    override, _ = _db_returning(admin)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.get(
            "/api/v1/admin/status",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "admin_only"


async def test_hr_status_requires_hr_role(async_client):
    specialist = _make_user(UserRole.SPECIALIST)
    override, _ = _db_returning(specialist)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            "/api/v1/hr/status",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


async def test_hr_status_accessible_by_hr(async_client):
    hr = _make_user(UserRole.HR)
    override, _ = _db_returning(hr)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(hr)
        response = await async_client.get(
            "/api/v1/hr/status",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "hr_only"
