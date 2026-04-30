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
CSRF_TOKEN = "test-csrf-token-1234"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_user(
    role: UserRole = UserRole.ADMIN,
    specialist_level: SpecialistLevel | None = None,
    cm_id=None,
    is_active: bool = True,
) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = f"{role.value}-{u.id.hex[:6]}@example.com"
    u.full_name = f"Test {role.value.title()}"
    u.role = role
    u.is_active = is_active
    u.hashed_password = FAKE_HASHED
    u.specialist_level = specialist_level
    u.cm_id = cm_id
    u.created_at = _now()
    u.updated_at = _now()
    return u


def _make_jwt(user: MagicMock) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _csrf_cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": CSRF_TOKEN}


def _csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": CSRF_TOKEN}


def _scalar_one_or_none_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_all_result(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _populate_after_insert(obj) -> None:
    """Mimic SQLAlchemy db.refresh() for tests: fill id/timestamps + column defaults."""
    if not hasattr(obj, "id") or obj.id is None:
        obj.id = uuid4()
    if obj.__class__.__name__ == "User":
        if obj.is_active is None:
            obj.is_active = True
    if not getattr(obj, "created_at", None):
        obj.created_at = _now()
    if not getattr(obj, "updated_at", None):
        obj.updated_at = _now()


def _routed_db(*results) -> tuple:
    """Build a mock AsyncSession whose execute() returns each result in order."""
    queue = list(results)
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def fake_refresh(obj):
        _populate_after_insert(obj)

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    added: list = []

    def fake_add(obj):
        added.append(obj)
        _populate_after_insert(obj)

    mock_db.add = MagicMock(side_effect=fake_add)

    async def execute_side_effect(*_args, **_kwargs):
        return queue.pop(0) if queue else _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    return override, mock_db, added


# ─── AC5: Non-admin gets 403 ──────────────────────────────────────────────────

async def test_create_user_requires_admin_role(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@x.com",
                "full_name": "X",
                "role": "hr",
                "password": "password1",
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == 403
    assert "permission" in body["detail"].lower() or "forbidden" in body["title"].lower()


async def test_unauthenticated_returns_401(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/admin/users",
        json={"email": "x@x.com", "full_name": "X", "role": "hr", "password": "password1"},
        cookies={"csrf_token": CSRF_TOKEN},
        headers=_csrf_headers(),
    )
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401


async def test_create_user_csrf_required(async_client: AsyncClient):
    """POST without matching X-CSRF-Token must return 403."""
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={"email": "x@x.com", "full_name": "X", "role": "hr", "password": "password1"},
            cookies={"access_token": token},  # no csrf_token cookie
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    body = response.json()
    assert "csrf" in body["detail"].lower()


# ─── AC1: Admin creates user → 201, hashes password, no leak ─────────────────

async def test_admin_creates_user_returns_201(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    override, _, added = _routed_db(_scalar_one_or_none_result(admin))
    plaintext_passwords: list[str] = []

    def fake_hash(pwd: str) -> str:
        plaintext_passwords.append(pwd)
        return FAKE_HASHED

    with patch("app.services.admin_service.hash_password", side_effect=fake_hash):
        app.dependency_overrides[get_db_session] = override
        try:
            token = _make_jwt(admin)
            response = await async_client.post(
                "/api/v1/admin/users",
                json={
                    "email": "New@Example.com",  # tests lowercase normalization
                    "full_name": "  New Specialist  ",  # tests strip
                    "role": "specialist",
                    "password": "password1",
                    "specialist_level": "junior",
                },
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"  # lowercased
    assert data["full_name"] == "New Specialist"  # stripped
    assert data["specialist_level"] == "junior"
    # Critical security check: response must never include hashed_password
    assert "hashed_password" not in data
    # Critical security check: hash_password must have been called with the plaintext
    assert plaintext_passwords == ["password1"]
    # Critical: hash never leaks via the User object hand-off
    user_objs = [o for o in added if o.__class__.__name__ == "User"]
    assert len(user_objs) == 1
    assert user_objs[0].hashed_password == FAKE_HASHED  # not the plaintext


async def test_email_lowercased_on_create(async_client: AsyncClient):
    """Admin submits mixed-case email; UserCreate normalizes to lowercase before insert."""
    admin = _make_user(role=UserRole.ADMIN)
    override, _, added = _routed_db(_scalar_one_or_none_result(admin))

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        app.dependency_overrides[get_db_session] = override
        try:
            token = _make_jwt(admin)
            response = await async_client.post(
                "/api/v1/admin/users",
                json={
                    "email": "Alice@Example.COM",
                    "full_name": "Alice",
                    "role": "hr",
                    "password": "password1",
                },
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    user_objs = [o for o in added if o.__class__.__name__ == "User"]
    assert len(user_objs) == 1
    assert user_objs[0].email == "alice@example.com"


# ─── AC1: List users returns paginated response ───────────────────────────────

async def test_list_users_returns_paginated(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)

    # admin_service.list_users uses a windowed-count statement: each row is (User, total).
    list_result = MagicMock()
    list_result.all.return_value = [(specialist, 1)]

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),  # get_current_user
        list_result,                         # windowed list+count
    )

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
    assert data["total"] == 1
    assert data["pages"] == 1
    assert len(data["items"]) == 1


# ─── AC2: Duplicate email → 409 RFC 7807 ─────────────────────────────────────

async def test_create_user_duplicate_email_returns_409(async_client: AsyncClient):
    import sqlalchemy.exc

    admin = _make_user(role=UserRole.ADMIN)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(admin))
    # simulate the case-insensitive constraint fired in production
    mock_db.commit = AsyncMock(
        side_effect=sqlalchemy.exc.IntegrityError(
            "INSERT", {}, Exception("duplicate key value violates unique constraint \"uq_users_email_lower\"")
        )
    )
    mock_db.rollback = AsyncMock()
    mock_db.add = MagicMock()

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        app.dependency_overrides[get_db_session] = override
        try:
            token = _make_jwt(admin)
            response = await async_client.post(
                "/api/v1/admin/users",
                json={"email": "dup@example.com", "full_name": "Dup", "role": "hr", "password": "password1"},
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert body["status"] == 409
    assert "already exists" in body["detail"]
    assert body["instance"] == "/api/v1/admin/users"


async def test_create_user_other_integrity_error_returns_422(async_client: AsyncClient):
    """FK violation (e.g., bad cm_id slipped past validation) returns structured 422, not 500."""
    import sqlalchemy.exc

    admin = _make_user(role=UserRole.ADMIN)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(admin))
    mock_db.commit = AsyncMock(
        side_effect=sqlalchemy.exc.IntegrityError(
            "INSERT", {}, Exception("violates foreign key constraint \"fk_users_cm_id\"")
        )
    )
    mock_db.rollback = AsyncMock()
    mock_db.add = MagicMock()

    async def override():
        yield mock_db

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
        app.dependency_overrides[get_db_session] = override
        try:
            token = _make_jwt(admin)
            response = await async_client.post(
                "/api/v1/admin/users",
                json={"email": "x@x.com", "full_name": "X", "role": "hr", "password": "password1"},
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422


# ─── AC3: Specialist creation includes specialist_level in response ────────────

async def test_create_specialist_includes_level(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
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
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["specialist_level"] == "middle"


async def test_specialist_without_level_rejected(async_client: AsyncClient):
    """Pydantic model_validator rejects role=SPECIALIST without specialist_level."""
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "X",
                "role": "specialist",
                "password": "password1",
                # missing specialist_level
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_non_specialist_with_level_rejected(async_client: AsyncClient):
    """Pydantic model_validator rejects role=HR with specialist_level set."""
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "X",
                "role": "hr",
                "password": "password1",
                "specialist_level": "senior",
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


# ─── AC4: Specialist + cm_id → notification, cm_id validation ────────────────

async def test_cm_notification_created_on_specialist_assignment(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    cm = _make_user(role=UserRole.CM)

    override, _, added = _routed_db(
        _scalar_one_or_none_result(admin),  # get_current_user
        _scalar_one_or_none_result(cm),     # CM validation lookup
    )

    with patch("app.services.admin_service.hash_password", return_value=FAKE_HASHED):
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
                    "cm_id": str(cm.id),
                },
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    notification_objects = [o for o in added if isinstance(o, Notification)]
    assert len(notification_objects) == 1
    assert notification_objects[0].user_id == cm.id
    assert "Junior Spec" in notification_objects[0].content


async def test_invalid_cm_id_rejected_with_422(async_client: AsyncClient):
    """cm_id pointing to a non-existent or non-CM user is rejected with 422 RFC 7807."""
    admin = _make_user(role=UserRole.ADMIN)
    not_a_cm = _make_user(role=UserRole.HR)  # exists but wrong role

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),    # get_current_user
        _scalar_one_or_none_result(not_a_cm), # CM validation lookup returns wrong-role user
    )

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "X",
                "role": "specialist",
                "password": "password1",
                "specialist_level": "junior",
                "cm_id": str(not_a_cm.id),
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert "cm" in body["detail"].lower()


async def test_inactive_cm_rejected(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    inactive_cm = _make_user(role=UserRole.CM, is_active=False)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),
        _scalar_one_or_none_result(inactive_cm),
    )

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "X",
                "role": "specialist",
                "password": "password1",
                "specialist_level": "junior",
                "cm_id": str(inactive_cm.id),
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


# ─── Password length boundaries ──────────────────────────────────────────────

async def test_password_too_long_rejected(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "X",
                "role": "hr",
                "password": "a" * 73,  # >72 bcrypt limit
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_full_name_whitespace_only_rejected(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    override, _, _ = _routed_db(_scalar_one_or_none_result(admin))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "full_name": "   ",
                "role": "hr",
                "password": "password1",
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


# ─── Story 2.2: PATCH /admin/users/{user_id} ─────────────────────────────────

PATCH_URL = "/api/v1/admin/users/{user_id}"


async def test_patch_user_requires_admin_role(async_client: AsyncClient):
    """AC4: Non-admin caller → 403."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(specialist)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": None},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


async def test_patch_user_unauthenticated_returns_401(async_client: AsyncClient):
    """AC4: Unauthenticated → 401."""
    response = await async_client.patch(
        PATCH_URL.format(user_id=str(uuid4())),
        json={"cm_id": None},
        cookies={"csrf_token": CSRF_TOKEN},
        headers=_csrf_headers(),
    )
    assert response.status_code == 401


async def test_patch_specialist_cm_updates_only_cm_id(async_client: AsyncClient):
    """AC3: Admin patches specialist cm_id → 200, other fields intact."""
    admin = _make_user(role=UserRole.ADMIN)
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(
        role=UserRole.SPECIALIST,
        specialist_level=SpecialistLevel.JUNIOR,
        cm_id=None,
    )
    specialist.full_name = "Test Specialist"

    override, mock_db, _ = _routed_db(
        _scalar_one_or_none_result(admin),       # get_current_user
        _scalar_one_or_none_result(specialist),  # load target user
        _scalar_one_or_none_result(cm),          # CM validation lookup
    )

    async def fake_refresh(obj):
        _populate_after_insert(obj)

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": str(cm.id)},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "specialist"
    assert data["specialist_level"] == "junior"


async def test_cm_notification_created_on_reassignment(async_client: AsyncClient):
    """AC1: Notification created for new CM on successful reassignment."""
    admin = _make_user(role=UserRole.ADMIN)
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(
        role=UserRole.SPECIALIST,
        specialist_level=SpecialistLevel.MIDDLE,
        cm_id=None,
    )
    specialist.full_name = "Jane Doe"

    override, mock_db, added = _routed_db(
        _scalar_one_or_none_result(admin),       # get_current_user
        _scalar_one_or_none_result(specialist),  # load target user
        _scalar_one_or_none_result(cm),          # CM validation
    )

    async def fake_refresh(obj):
        _populate_after_insert(obj)

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": str(cm.id)},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    notifications = [o for o in added if isinstance(o, Notification)]
    assert len(notifications) == 1
    assert notifications[0].user_id == cm.id
    assert "Jane Doe" in notifications[0].content


async def test_patch_specialist_unassign_cm_no_notification(async_client: AsyncClient):
    """AC1: cm_id=null (unassign) → success, no notification created."""
    admin = _make_user(role=UserRole.ADMIN)
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(
        role=UserRole.SPECIALIST,
        specialist_level=SpecialistLevel.JUNIOR,
        cm_id=cm.id,
    )

    override, mock_db, added = _routed_db(
        _scalar_one_or_none_result(admin),       # get_current_user
        _scalar_one_or_none_result(specialist),  # load target user
        # no CM lookup because cm_id=null
    )

    async def fake_refresh(obj):
        _populate_after_insert(obj)

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": None},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    notifications = [o for o in added if isinstance(o, Notification)]
    assert len(notifications) == 0


async def test_patch_nonexistent_user_returns_404(async_client: AsyncClient):
    """User not found → 404 RFC 7807."""
    admin = _make_user(role=UserRole.ADMIN)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),  # get_current_user
        _scalar_one_or_none_result(None),   # target user not found
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(uuid4())),
            json={"cm_id": None},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == 404
    assert "user-not-found" in body["type"]


async def test_patch_cm_user_returns_422(async_client: AsyncClient):
    """Non-Specialist target → 422 invalid-assignment-target."""
    admin = _make_user(role=UserRole.ADMIN)
    cm_target = _make_user(role=UserRole.CM)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),      # get_current_user
        _scalar_one_or_none_result(cm_target),  # load target user (wrong role)
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(cm_target.id)),
            json={"cm_id": None},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert "invalid-assignment-target" in body["type"]


async def test_patch_invalid_cm_id_returns_422(async_client: AsyncClient):
    """cm_id points to non-CM → 422 invalid-cm-assignment."""
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    not_a_cm = _make_user(role=UserRole.HR)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),      # get_current_user
        _scalar_one_or_none_result(specialist), # load target user
        _scalar_one_or_none_result(not_a_cm),   # CM validation → wrong role
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": str(not_a_cm.id)},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert "invalid-cm-assignment" in body["type"]


async def test_patch_self_cm_assignment_returns_422(async_client: AsyncClient):
    """cm_id == user_id → 422 self-cm-assignment."""
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),      # get_current_user
        _scalar_one_or_none_result(specialist), # load target user
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(admin)
        response = await async_client.patch(
            PATCH_URL.format(user_id=str(specialist.id)),
            json={"cm_id": str(specialist.id)},  # self-assignment
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert "self-cm-assignment" in body["type"]
