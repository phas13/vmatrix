from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from jose import jwt

from app.core.config import settings
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

async def test_admin_status_uses_single_db_query_for_role_check(async_client):
    """AC2: `require_role` performs no DB lookup beyond the user fetch.

    Uses `/admin/status` (Pattern-B route — no business-logic query in the
    handler) so the only `db.execute` call is the user lookup inside
    `get_current_user`. If `require_role` ever added a role-check DB query,
    `call_count` would become 2 and this test would fail.
    """
    admin = _make_user(UserRole.ADMIN)
    override, mock_db = _db_returning(admin)
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
    assert mock_db.execute.call_count == 1


# ─── AC2 supporting: cm/team performs exactly user-lookup + team-query (2 calls) ─

async def test_cm_team_uses_single_user_lookup_plus_team_query(async_client):
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
    # First execute: get_current_user user lookup. Second execute: cm/team specialist query.
    # No extra DB call for role check.
    assert mock_db.execute.call_count == 2


# ─── AC3: CM team returns only CM's assigned specialists ──────────────────────

async def test_cm_team_returns_only_assigned_specialists(async_client):
    from datetime import datetime, timezone
    from unittest.mock import patch
    from uuid import uuid4 as _uuid4
    from app.models.user import SpecialistLevel
    from app.schemas.cm import SpecialistCardRead

    cm = _make_user(UserRole.CM)
    specialist = _make_user(UserRole.SPECIALIST)
    specialist.cm_id = cm.id

    card = SpecialistCardRead(
        id=specialist.id,
        full_name=specialist.full_name,
        specialist_level=SpecialistLevel.JUNIOR,
        overall_percentage=60,
        last_activity_at=datetime.now(timezone.utc),
    )

    override, _ = _db_returning(cm)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        with patch("app.services.cm_service.get_team_overview", new=AsyncMock(return_value=[card])):
            response = await async_client.get(
                "/api/v1/cm/team",
                cookies={"access_token": token},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(specialist.id)
    assert data[0]["full_name"] == specialist.full_name


# ─── AC4: Cross-Specialist access → 404 (resource existence not revealed) ─────

async def test_verify_specialist_ownership_own_resource_passes(async_client):
    from app.core.dependencies import verify_specialist_ownership

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


async def test_hr_status_accessible_by_admin(async_client):
    """ADMIN is a global superuser — must have access to HR-scoped endpoints."""
    admin = _make_user(UserRole.ADMIN)
    override, _ = _db_returning(admin)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.get(
            "/api/v1/hr/status",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "hr_only"


# ─── AC3 strengthening: verify the cm_id WHERE clause is actually applied ─────

async def test_cm_team_query_filters_by_cm_id(async_client):
    """AC3 isolation invariant: the team query MUST include `cm_id == current_user.id`.

    The other AC3 test mocks the DB to return whatever specialists we choose,
    so the filter could be silently removed without breaking it. This test
    captures the actual SQL statement and asserts the filter is present.
    """
    cm = _make_user(UserRole.CM)
    captured_stmts = []

    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = cm
    mock_result_list = MagicMock()
    mock_result_list.scalars.return_value.all.return_value = []

    async def execute_side_effect(stmt, *args, **kwargs):
        captured_stmts.append(stmt)
        return mock_result_user if len(captured_stmts) == 1 else mock_result_list

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.get("/api/v1/cm/team", cookies={"access_token": token})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(captured_stmts) == 2
    team_sql = str(captured_stmts[1])
    assert "cm_id" in team_sql, f"Team query is missing cm_id filter: {team_sql}"
    assert "role" in team_sql, f"Team query is missing role filter: {team_sql}"


# ─── AC5 hardening: malformed/missing JWT claims must produce 401 RFC 7807 ────

def _signed_jwt(payload: dict) -> str:
    """Build a JWT signed with the app secret but with arbitrary payload."""
    data = payload.copy()
    data.setdefault("exp", datetime.now(timezone.utc) + timedelta(minutes=5))
    return jwt.encode(data, settings.SECRET_KEY, algorithm="HS256")


async def test_jwt_missing_sub_returns_401(async_client):
    """Token signed but missing `sub` claim must yield 401 (not 500)."""
    token = _signed_jwt({"role": UserRole.SPECIALIST.value})
    response = await async_client.get(
        "/api/v1/cm/team",
        cookies={"access_token": token},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for key in ("type", "title", "status", "detail", "instance"):
        assert key in body
    assert body["status"] == 401


async def test_jwt_malformed_sub_returns_401(async_client):
    """Token signed but `sub` is not a valid UUID must yield 401 (not 500)."""
    token = _signed_jwt({"sub": "not-a-uuid", "role": UserRole.SPECIALIST.value})
    response = await async_client.get(
        "/api/v1/cm/team",
        cookies={"access_token": token},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 401


async def test_inactive_user_returns_401(async_client):
    """Authenticated user with `is_active=False` must be rejected with 401."""
    specialist = _make_user(UserRole.SPECIALIST)
    specialist.is_active = False
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

    assert response.status_code == 401
    assert response.json()["status"] == 401
