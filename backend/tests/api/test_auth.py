from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient

from app.core.security import hash_token
from app.db.session import get_db_session
from app.models.user import RefreshToken, User, UserRole
from main import app

FAKE_HASHED_PASSWORD = "$2b$12$fakehashedpasswordfortest000000000000000000000000000000"


def _make_mock_user(
    email="test@example.com",
    full_name="Test User",
    role=UserRole.SPECIALIST,
    is_active=True,
) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = email
    user.hashed_password = FAKE_HASHED_PASSWORD
    user.full_name = full_name
    user.role = role
    user.is_active = is_active
    return user


def _make_mock_db(user_result=None, rt_result=None) -> AsyncMock:
    mock_user_scalar = MagicMock()
    mock_user_scalar.scalar_one_or_none.return_value = user_result

    mock_rt_scalar = MagicMock()
    mock_rt_scalar.scalar_one_or_none.return_value = rt_result

    mock_db = AsyncMock()

    async def execute_side_effect(stmt, *args, **kwargs):
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True})) if hasattr(stmt, "compile") else str(stmt)
        if "refresh_tokens" in stmt_str:
            return mock_rt_scalar
        return mock_user_scalar

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    mock_db.add = MagicMock()
    return mock_db


def _override_db(mock_db):
    async def _override():
        yield mock_db
    return _override


# ─── AC #1: Successful login sets cookies and returns user info ───────────────

async def test_login_success_returns_user_info(async_client: AsyncClient):
    mock_user = _make_mock_user()
    mock_db = _make_mock_db(user_result=mock_user)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        with patch("app.services.auth_service.verify_password", return_value=True):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "secret"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "specialist"
    assert data["full_name"] == "Test User"
    assert "id" in data


async def test_login_success_sets_httponly_cookies(async_client: AsyncClient):
    mock_user = _make_mock_user()
    mock_db = _make_mock_db(user_result=mock_user)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        with patch("app.services.auth_service.verify_password", return_value=True):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "secret"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert "csrf_token" in response.cookies


async def test_login_persists_refresh_token_to_db(async_client: AsyncClient):
    mock_user = _make_mock_user()
    mock_db = _make_mock_db(user_result=mock_user)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        with patch("app.services.auth_service.verify_password", return_value=True):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "secret"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, RefreshToken)
    assert added.token_hash
    assert len(added.token_hash) == 64  # SHA-256 hex digest


# ─── AC #2: Token refresh rotates tokens ──────────────────────────────────────

async def test_refresh_rotates_tokens(async_client: AsyncClient):
    mock_user = _make_mock_user()
    raw_token = "some-uuid-refresh-token"
    token_hash = hash_token(raw_token)

    mock_rt = MagicMock(spec=RefreshToken)
    mock_rt.token_hash = token_hash
    mock_rt.user_id = mock_user.id
    mock_rt.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    mock_rt.revoked_at = None

    mock_db = _make_mock_db(user_result=mock_user, rt_result=mock_rt)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": raw_token, "csrf_token": "my-csrf"},
            headers={"X-CSRF-Token": "my-csrf"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert mock_rt.revoked_at is not None  # old token revoked


async def test_refresh_issues_new_refresh_token_to_db(async_client: AsyncClient):
    mock_user = _make_mock_user()
    raw_token = "another-uuid-token"

    mock_rt = MagicMock(spec=RefreshToken)
    mock_rt.token_hash = hash_token(raw_token)
    mock_rt.user_id = mock_user.id
    mock_rt.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    mock_rt.revoked_at = None

    mock_db = _make_mock_db(user_result=mock_user, rt_result=mock_rt)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": raw_token, "csrf_token": "csrf-val"},
            headers={"X-CSRF-Token": "csrf-val"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, RefreshToken)


# ─── AC #3: CSRF protection on /refresh ──────────────────────────────────────

async def test_refresh_without_csrf_header_returns_403(async_client: AsyncClient):
    app.dependency_overrides[get_db_session] = _override_db(AsyncMock())
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "some-token", "csrf_token": "my-csrf"},
            # No X-CSRF-Token header
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    data = response.json()
    assert data["status"] == 403
    assert "CSRF" in data["detail"]


async def test_refresh_csrf_mismatch_returns_403(async_client: AsyncClient):
    app.dependency_overrides[get_db_session] = _override_db(AsyncMock())
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "some-token", "csrf_token": "cookie-csrf"},
            headers={"X-CSRF-Token": "different-csrf"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_refresh_without_csrf_cookie_returns_403(async_client: AsyncClient):
    app.dependency_overrides[get_db_session] = _override_db(AsyncMock())
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "some-token"},
            headers={"X-CSRF-Token": "some-csrf"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


# ─── AC #4: Invalid credentials → 401 RFC 7807 ───────────────────────────────

async def test_login_wrong_password_returns_401_problem_details(async_client: AsyncClient):
    mock_user = _make_mock_user()
    mock_db = _make_mock_db(user_result=mock_user)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        with patch("app.services.auth_service.verify_password", return_value=False):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrong-password"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    data = response.json()
    assert data["status"] == 401
    assert data["title"] == "Unauthorized"
    assert "type" in data
    assert "instance" in data
    assert "detail" in data


async def test_login_nonexistent_user_returns_401(async_client: AsyncClient):
    mock_db = _make_mock_db(user_result=None)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "any"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


# ─── AC #5: Logout revokes refresh token and clears cookies ──────────────────

async def test_logout_revokes_refresh_token(async_client: AsyncClient):
    raw_token = "logout-token"

    mock_rt = MagicMock(spec=RefreshToken)
    mock_rt.token_hash = hash_token(raw_token)
    mock_rt.revoked_at = None

    mock_db = _make_mock_db(rt_result=mock_rt)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post(
            "/api/v1/auth/logout",
            cookies={"refresh_token": raw_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert mock_rt.revoked_at is not None


async def test_logout_clears_cookies(async_client: AsyncClient):
    mock_db = _make_mock_db(rt_result=None)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post(
            "/api/v1/auth/logout",
            cookies={"refresh_token": "some-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    # delete_cookie sets max-age=0 — verify all three cookies are cleared
    set_cookie_str = " ".join(v for k, v in response.headers.items() if k.lower() == "set-cookie")
    assert "access_token" in set_cookie_str
    assert "refresh_token" in set_cookie_str
    assert "csrf_token" in set_cookie_str


async def test_logout_without_cookie_is_idempotent(async_client: AsyncClient):
    mock_db = _make_mock_db(rt_result=None)

    app.dependency_overrides[get_db_session] = _override_db(mock_db)
    try:
        response = await async_client.post("/api/v1/auth/logout")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
