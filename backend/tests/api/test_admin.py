from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.notification import Notification
from app.models.user import SpecialistLevel, User, UserRole
from main import app

FAKE_HASHED = "$2b$12$fakehashedpassword0000000000000000000000000000000000000"
NOW = datetime.now(timezone.utc)


def _make_user(
    role: UserRole = UserRole.ADMIN,
    specialist_level: SpecialistLevel | None = None,
    cm_id=None,
) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = f"{role.value}@example.com"
    u.full_name = f"Test {role.value.title()}"
    u.role = role
    u.is_active = True
    u.hashed_password = FAKE_HASHED
    u.specialist_level = specialist_level
    u.cm_id = cm_id
    u.created_at = NOW
    u.updated_at = NOW
    return u


def _make_jwt(user: MagicMock) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _db_returning_user(user: MagicMock):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override():
        yield mock_db

    return override, mock_db


# ─── AC5: Non-admin gets 403 ──────────────────────────────────────────────────

async def test_create_user_requires_admin_role(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    override, _ = _db_returning_user(specialist)
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={"email": "x@x.com", "full_name": "X", "role": "specialist", "password": "password1"},
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == 403


# ─── AC5 unauthenticated: 401 ─────────────────────────────────────────────────

async def test_unauthenticated_returns_401(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/admin/users",
        json={"email": "x@x.com", "full_name": "X", "role": "specialist", "password": "password1"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401


# ─── AC1: Admin creates user → 201 + UserRead ─────────────────────────────────

async def test_admin_creates_user_returns_201(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    created = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    created.email = "new@example.com"
    created.full_name = "New Specialist"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        with patch("app.services.admin_service.User", return_value=created):
            app.dependency_overrides[get_db_session] = override
            try:
                token = _make_jwt(admin)
                response = await async_client.post(
                    "/api/v1/admin/users",
                    json={
                        "email": "new@example.com",
                        "full_name": "New Specialist",
                        "role": "specialist",
                        "password": "password1",
                        "specialist_level": "junior",
                    },
                    cookies={"access_token": token},
                )
            finally:
                app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["specialist_level"] == "junior"


# ─── AC1: List users returns paginated response ───────────────────────────────

async def test_list_users_returns_paginated(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST)

    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1
    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = [specialist]
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = admin

    call_count = {"n": 0}

    async def execute_side_effect(stmt, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return mock_user_result  # get_current_user lookup
        if call_count["n"] == 2:
            return mock_count_result  # count query
        return mock_list_result  # list query

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.get(
            "/api/v1/admin/users",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "pages" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1


# ─── AC2: Duplicate email → 409 RFC 7807 ─────────────────────────────────────

async def test_create_user_duplicate_email_returns_409(async_client: AsyncClient):
    import sqlalchemy.exc

    admin = _make_user(role=UserRole.ADMIN)

    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = admin
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_user_result)
    mock_db.commit = AsyncMock(
        side_effect=sqlalchemy.exc.IntegrityError(
            "INSERT", {}, Exception("uq_users_email")
        )
    )
    mock_db.rollback = AsyncMock()

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        app.dependency_overrides[get_db_session] = override
        try:
            token = _make_jwt(admin)
            response = await async_client.post(
                "/api/v1/admin/users",
                json={"email": "dup@example.com", "full_name": "Dup", "role": "hr", "password": "password1"},
                cookies={"access_token": token},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert body["status"] == 409
    assert "already exists" in body["detail"]


# ─── AC3: Specialist creation includes specialist_level in response ────────────

async def test_create_specialist_includes_level(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    created = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.MIDDLE)
    created.email = "spec@example.com"
    created.full_name = "Mid Spec"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        with patch("app.services.admin_service.User", return_value=created):
            app.dependency_overrides[get_db_session] = override
            try:
                token = _make_jwt(admin)
                response = await async_client.post(
                    "/api/v1/admin/users",
                    json={
                        "email": "spec@example.com",
                        "full_name": "Mid Spec",
                        "role": "specialist",
                        "password": "password1",
                        "specialist_level": "middle",
                    },
                    cookies={"access_token": token},
                )
            finally:
                app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["specialist_level"] == "middle"


# ─── AC4: Creating Specialist with cm_id → notification created ───────────────

async def test_cm_notification_created_on_specialist_assignment(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    cm_id = uuid4()
    created = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR, cm_id=cm_id)
    created.email = "spec2@example.com"
    created.full_name = "Junior Spec"

    added_objects = []

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    def capture_add(obj):
        added_objects.append(obj)

    mock_db.add = MagicMock(side_effect=capture_add)

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        with patch("app.services.admin_service.User", return_value=created):
            app.dependency_overrides[get_db_session] = override
            try:
                token = _make_jwt(admin)
                response = await async_client.post(
                    "/api/v1/admin/users",
                    json={
                        "email": "spec2@example.com",
                        "full_name": "Junior Spec",
                        "role": "specialist",
                        "password": "password1",
                        "specialist_level": "junior",
                        "cm_id": str(cm_id),
                    },
                    cookies={"access_token": token},
                )
            finally:
                app.dependency_overrides.clear()

    assert response.status_code == 201
    notification_objects = [o for o in added_objects if isinstance(o, Notification)]
    assert len(notification_objects) == 1
    assert notification_objects[0].user_id == cm_id
    assert "Junior Spec" in notification_objects[0].content
