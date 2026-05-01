from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.matrix import CompetencyMatrix, CompetencyCategory, CompetencySubItem, MatrixStatus
from app.models.system_settings import SystemSettings
from app.models.user import SpecialistLevel, User, UserRole
from app.providers.base import CategoryDraft, SubItemDraft
from main import app

CSRF_TOKEN = "test-csrf-token-matrix"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_user(role: UserRole = UserRole.SPECIALIST, specialist_level: SpecialistLevel | None = SpecialistLevel.JUNIOR, cm_id=None, is_active: bool = True) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = f"{role.value}-{u.id.hex[:6]}@example.com"
    u.full_name = f"Test {role.value.title()}"
    u.role = role
    u.is_active = is_active
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


def _populate_after_insert(obj) -> None:
    if not hasattr(obj, "id") or obj.id is None:
        obj.id = uuid4()
    if not getattr(obj, "created_at", None):
        obj.created_at = _now()
    if not getattr(obj, "updated_at", None):
        obj.updated_at = _now()


def _make_settings(domain: str = "DevOps") -> MagicMock:
    s = MagicMock(spec=SystemSettings)
    s.id = 1
    s.promotion_threshold = 90
    s.default_competency_domain = domain
    return s


def _make_sub_item(category_id) -> MagicMock:
    si = MagicMock(spec=CompetencySubItem)
    si.id = uuid4()
    si.category_id = category_id
    si.name = "Pipeline design"
    si.description = "Knows how to design a CI pipeline"
    si.order = 0
    si.is_flagged = False
    si.flag_note = None
    si.created_at = _now()
    si.updated_at = _now()
    return si


def _make_category(matrix_id) -> MagicMock:
    c = MagicMock(spec=CompetencyCategory)
    c.id = uuid4()
    c.matrix_id = matrix_id
    c.name = "CI/CD"
    c.description = "Continuous integration and delivery practices"
    c.order = 0
    c.created_at = _now()
    c.updated_at = _now()
    c.sub_items = [_make_sub_item(c.id)]
    return c


def _make_matrix(specialist: MagicMock, status: MatrixStatus = MatrixStatus.PENDING_REVIEW) -> MagicMock:
    m = MagicMock(spec=CompetencyMatrix)
    m.id = uuid4()
    m.specialist_id = specialist.id
    m.domain = "DevOps"
    m.status = status
    m.created_at = _now()
    m.updated_at = _now()
    m.categories = [_make_category(m.id)]
    return m


def _routed_db(*results) -> tuple:
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
    mock_db.flush = AsyncMock()

    async def execute_side_effect(*_args, **_kwargs):
        return queue.pop(0) if queue else _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    return override, mock_db, added


_MOCK_CATEGORIES = [
    CategoryDraft(
        name="CI/CD",
        description="Continuous integration and delivery practices",
        sub_items=[SubItemDraft(name="Pipeline design", description="Knows how to design a CI pipeline")],
    )
]


# ─── POST /matrix/{specialist_id}/actions/generate ────────────────────────────

@pytest.mark.asyncio
async def test_generate_matrix_as_specialist_returns_200(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()
    matrix_mock = _make_matrix(specialist)

    # DB call order:
    # 1. get_current_user lookup
    # 2. check existing matrix → None
    # 3. _load_specialist lookup
    # 4. get_settings
    # 5. get_matrix (after commit) with selectinload
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),     # get_current_user
        _scalar_one_or_none_result(None),           # no existing matrix
        _scalar_one_or_none_result(specialist),     # _load_specialist
        _scalar_one_or_none_result(settings_row),   # get_settings
        _scalar_one_or_none_result(matrix_mock),    # get_matrix eager load
    )
    app.dependency_overrides[get_db_session] = override

    with patch("app.services.matrix_service.get_llm_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_initial_matrix.return_value = (_MOCK_CATEGORIES, 500, 1200)
        mock_factory.return_value = mock_provider
        try:
            token = _make_jwt(specialist)
            response = await async_client.post(
                f"/api/v1/matrix/{specialist.id}/actions/generate",
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_REVIEW"
    assert data["specialist_id"] == str(specialist.id)


@pytest.mark.asyncio
async def test_generate_matrix_returns_409_when_already_exists(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    existing_matrix = _make_matrix(specialist)

    # 1. get_current_user, 2. check existing matrix → found → 409
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),      # get_current_user
        _scalar_one_or_none_result(existing_matrix), # existing matrix found
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/generate",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    data = response.json()
    assert "matrix-already-exists" in data["type"]


@pytest.mark.asyncio
async def test_generate_matrix_as_cm_returns_403(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/generate",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_matrix_without_csrf_returns_403(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/generate",
            cookies={"access_token": token},
            # no CSRF header
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_matrix_llm_unavailable_returns_503(async_client: AsyncClient):
    from app.core.exceptions import LLMUnavailableError

    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()

    # 1. get_current_user, 2. no existing matrix, 3. _load_specialist, 4. get_settings
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),     # get_current_user
        _scalar_one_or_none_result(None),           # no existing matrix
        _scalar_one_or_none_result(specialist),     # _load_specialist
        _scalar_one_or_none_result(settings_row),   # get_settings
    )
    app.dependency_overrides[get_db_session] = override

    with patch("app.services.matrix_service.get_llm_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_initial_matrix.side_effect = LLMUnavailableError("timeout")
        mock_factory.return_value = mock_provider
        try:
            token = _make_jwt(specialist)
            response = await async_client.post(
                f"/api/v1/matrix/{specialist.id}/actions/generate",
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 503
    data = response.json()
    assert "Matrix generation is temporarily unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_generate_matrix_as_different_specialist_returns_404(async_client: AsyncClient):
    specialist_a = _make_user(role=UserRole.SPECIALIST)
    specialist_b = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist_a))
    app.dependency_overrides[get_db_session] = override

    try:
        # specialist_a's JWT but requesting specialist_b's matrix
        token = _make_jwt(specialist_a)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist_b.id}/actions/generate",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


# ─── GET /matrix/{specialist_id} ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_matrix_as_owner_specialist_returns_200(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix_mock = _make_matrix(specialist)

    # 1. get_current_user, 2. get_matrix with selectinload
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),  # get_current_user
        _scalar_one_or_none_result(matrix_mock),  # get_matrix
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["specialist_id"] == str(specialist.id)
    assert data["status"] == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_get_matrix_not_found_returns_404(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)

    # 1. get_current_user, 2. matrix not found → 404
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),  # get_current_user
        _scalar_one_or_none_result(None),        # no matrix
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    data = response.json()
    assert "matrix-not-found" in data["type"]


@pytest.mark.asyncio
async def test_get_matrix_as_different_specialist_returns_404(async_client: AsyncClient):
    specialist_a = _make_user(role=UserRole.SPECIALIST)
    specialist_b = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist_a))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist_a)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist_b.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_matrix_as_cm_returns_200(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix_mock = _make_matrix(specialist)

    # 1. get_current_user (CM), 2. get_matrix
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),            # get_current_user
        _scalar_one_or_none_result(matrix_mock),   # get_matrix
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_matrix_as_admin_returns_200(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix_mock = _make_matrix(specialist)

    # 1. get_current_user (admin), 2. get_matrix
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),         # get_current_user
        _scalar_one_or_none_result(matrix_mock),   # get_matrix
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(admin)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_matrix_as_hr_returns_403(async_client: AsyncClient):
    hr = _make_user(role=UserRole.HR)
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(hr))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(hr)
        response = await async_client.get(
            f"/api/v1/matrix/{specialist.id}",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
