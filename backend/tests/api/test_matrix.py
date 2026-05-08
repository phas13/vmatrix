from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import LLMUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.llm_call_log import LLMCallLog, LLMOperation
from app.models.matrix import CompetencyMatrix, CompetencyCategory, CompetencySubItem, MatrixStatus
from app.models.notification import Notification
from app.models.system_settings import SystemSettings
from app.models.user import SpecialistLevel, User, UserRole
from app.providers.base import CategoryDraft, MatrixGenerationContext, SubItemDraft
from main import app
from tests._helpers import (
    _now,
    _populate_after_insert,
    _routed_db,
    _scalar_one_or_none_result,
    _scalar_one_result,
    _scalars_result,
)

CSRF_TOKEN = "test-csrf-token-matrix"


def _make_user(
    role: UserRole = UserRole.SPECIALIST,
    specialist_level: SpecialistLevel | None = SpecialistLevel.JUNIOR,
    cm_id=None,
    is_active: bool = True,
) -> MagicMock:
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
    m.approved_by_id = None
    m.approved_at = None
    m.cm_changes = None
    return m


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
    # 4. SystemSettings direct read (no bootstrap)
    # 5. eager-load select after commit
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),     # get_current_user
        _scalar_one_or_none_result(None),           # no existing matrix
        _scalar_one_or_none_result(specialist),     # _load_specialist
        _scalar_one_or_none_result(settings_row),   # SystemSettings read
        _scalar_one_result(matrix_mock),            # eager-load select after commit
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
async def test_generate_matrix_provider_called_with_expected_context(async_client: AsyncClient):
    """Regression guard: matrix service must hand the LLM provider the
    correct (specialist_id, level, domain) tuple — wrong values would
    silently produce a mismatched matrix."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.MIDDLE)
    settings_row = _make_settings(domain="DevOps")
    matrix_mock = _make_matrix(specialist)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
        _scalar_one_result(matrix_mock),
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
    mock_provider.generate_initial_matrix.assert_called_once()
    (call_arg,) = mock_provider.generate_initial_matrix.call_args.args
    assert isinstance(call_arg, MatrixGenerationContext)
    assert call_arg.specialist_id == specialist.id
    assert call_arg.level == "middle"
    assert call_arg.domain == "DevOps"


@pytest.mark.asyncio
async def test_generate_matrix_logs_call_on_success(async_client: AsyncClient):
    """Hard architectural rule: every LLM call must persist an LLMCallLog row."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()
    matrix_mock = _make_matrix(specialist)

    override, _, added = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
        _scalar_one_result(matrix_mock),
    )
    app.dependency_overrides[get_db_session] = override

    with patch("app.services.matrix_service.get_llm_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_initial_matrix.return_value = (_MOCK_CATEGORIES, 500, 1200)
        mock_factory.return_value = mock_provider
        try:
            token = _make_jwt(specialist)
            await async_client.post(
                f"/api/v1/matrix/{specialist.id}/actions/generate",
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    log_entries = [obj for obj in added if isinstance(obj, LLMCallLog)]
    assert len(log_entries) == 1
    log = log_entries[0]
    assert log.operation == LLMOperation.MATRIX_GENERATION
    assert log.specialist_id == specialist.id
    assert log.error is None
    assert log.tokens_used == 1200
    assert log.latency_ms is not None
    assert log.request_payload is not None  # encrypted prompt body present


@pytest.mark.asyncio
async def test_generate_matrix_returns_409_when_already_exists(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    existing_matrix = _make_matrix(specialist)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(existing_matrix),
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
async def test_generate_matrix_concurrent_commit_returns_409(async_client: AsyncClient):
    """Race: another worker inserts the matrix between our SELECT-not-found
    and our INSERT. The unique constraint fires on commit; service must
    catch IntegrityError and return 409 instead of leaking 500."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()

    override, mock_db, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),           # no existing matrix at SELECT time
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
    )
    mock_db.commit.side_effect = [
        IntegrityError("INSERT", {}, Exception("uq_matrices_specialist_id"))
    ]
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

    assert response.status_code == 409
    data = response.json()
    assert "matrix-already-exists" in data["type"]
    mock_db.rollback.assert_awaited()


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
async def test_generate_matrix_as_hr_returns_403(async_client: AsyncClient):
    hr = _make_user(role=UserRole.HR)
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(hr))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(hr)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/generate",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_matrix_admin_targets_non_specialist_returns_404(async_client: AsyncClient):
    """ADMIN cannot generate a matrix for a non-Specialist user (CM, HR,
    another ADMIN). _load_specialist must reject by role, not just by
    is_active."""
    admin = _make_user(role=UserRole.ADMIN, specialist_level=None)
    cm_target = _make_user(role=UserRole.CM, specialist_level=None)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),       # get_current_user
        _scalar_one_or_none_result(None),        # no existing matrix
        _scalar_one_or_none_result(cm_target),   # _load_specialist → not a specialist
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            f"/api/v1/matrix/{cm_target.id}/actions/generate",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    data = response.json()
    assert "specialist-not-found" in data["type"]


@pytest.mark.asyncio
async def test_generate_matrix_without_level_returns_422(async_client: AsyncClient):
    """Specialist whose `specialist_level` is NULL must not be silently
    coerced to 'junior'; the service must fail explicitly."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=None)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
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

    assert response.status_code == 422
    data = response.json()
    assert "specialist-level-required" in data["type"]


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
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_matrix_llm_unavailable_returns_503(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
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
    assert data["type"] == "https://vmatrix.app/errors/llm-unavailable"
    assert "Matrix generation is temporarily unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_generate_matrix_empty_categories_returns_503(async_client: AsyncClient):
    """If the provider returns an empty list (slip past schema validation),
    the service must treat it as LLM-unavailable rather than silently
    creating an empty matrix that the user is then locked out of via 409."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()

    override, _, added = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
    )
    app.dependency_overrides[get_db_session] = override

    with patch("app.services.matrix_service.get_llm_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_initial_matrix.return_value = ([], 100, 50)
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
    assert data["type"] == "https://vmatrix.app/errors/llm-unavailable"
    log_entries = [obj for obj in added if isinstance(obj, LLMCallLog)]
    assert len(log_entries) == 1
    assert "no categories" in (log_entries[0].error or "")


@pytest.mark.asyncio
async def test_generate_matrix_llm_unavailable_logs_call_with_error(async_client: AsyncClient):
    """LLM failure must still write an LLMCallLog row with the error text —
    audit trail must not be skipped on the failure path."""
    specialist = _make_user(role=UserRole.SPECIALIST, specialist_level=SpecialistLevel.JUNIOR)
    settings_row = _make_settings()

    override, mock_db, added = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(settings_row),
    )
    app.dependency_overrides[get_db_session] = override

    with patch("app.services.matrix_service.get_llm_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_initial_matrix.side_effect = LLMUnavailableError("upstream timeout")
        mock_factory.return_value = mock_provider
        try:
            token = _make_jwt(specialist)
            await async_client.post(
                f"/api/v1/matrix/{specialist.id}/actions/generate",
                cookies=_csrf_cookies(token),
                headers=_csrf_headers(),
            )
        finally:
            app.dependency_overrides.clear()

    log_entries = [obj for obj in added if isinstance(obj, LLMCallLog)]
    assert len(log_entries) == 1
    log = log_entries[0]
    assert log.error == "upstream timeout"
    assert log.tokens_used is None
    assert log.latency_ms is not None
    # Service must rollback before committing the failure log to avoid
    # leaking pending writes from the same session.
    mock_db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_generate_matrix_as_different_specialist_returns_404(async_client: AsyncClient):
    specialist_a = _make_user(role=UserRole.SPECIALIST)
    specialist_b = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist_a))
    app.dependency_overrides[get_db_session] = override

    try:
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

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(matrix_mock),
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

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
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
async def test_get_matrix_as_cm_in_team_returns_200(async_client: AsyncClient):
    """CM may read a matrix for a Specialist they are assigned to."""
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix_mock = _make_matrix(specialist)

    # 1. get_current_user, 2. specialist lookup (cm-team check), 3. matrix select
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(matrix_mock),
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
async def test_get_matrix_as_cm_outside_team_returns_404(async_client: AsyncClient):
    """A CM who is NOT assigned to this Specialist must get 404 — never
    leak the existence of a cross-team matrix."""
    cm = _make_user(role=UserRole.CM)
    other_cm_id = uuid4()
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=other_cm_id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(specialist),
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

    assert response.status_code == 404
    data = response.json()
    assert "matrix-not-found" in data["type"]


@pytest.mark.asyncio
async def test_get_matrix_as_admin_returns_200(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix_mock = _make_matrix(specialist)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),
        _scalar_one_or_none_result(matrix_mock),
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


# ─── Helpers for Story 3.2 tests ──────────────────────────────────────────────

def _make_sub_item_with_matrix(specialist_id) -> tuple:
    """Returns (matrix, category, sub_item) all with consistent foreign keys."""
    matrix = MagicMock(spec=CompetencyMatrix)
    matrix.id = uuid4()
    matrix.specialist_id = specialist_id
    matrix.domain = "DevOps"
    matrix.status = MatrixStatus.PENDING_REVIEW
    matrix.created_at = _now()
    matrix.updated_at = _now()
    matrix.categories = []

    category = MagicMock(spec=CompetencyCategory)
    category.id = uuid4()
    category.matrix_id = matrix.id

    sub_item = MagicMock(spec=CompetencySubItem)
    sub_item.id = uuid4()
    sub_item.category_id = category.id
    sub_item.name = "Pipeline design"
    sub_item.description = "Knows CI/CD"
    sub_item.order = 0
    sub_item.is_flagged = False
    sub_item.flag_note = None
    sub_item.created_at = _now()
    sub_item.updated_at = _now()
    return matrix, category, sub_item


def _first_result(row) -> MagicMock:
    r = MagicMock()
    r.first.return_value = row
    return r


# ─── POST /matrix/{specialist_id}/sub-items/{sub_item_id}/actions/flag ────────

@pytest.mark.asyncio
async def test_flag_sub_item_returns_200_with_is_flagged_true(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)
    sub_item.is_flagged = True
    sub_item.flag_note = "This item seems outdated"

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),                              # get_current_user
        _first_result((sub_item, MatrixStatus.PENDING_REVIEW)),              # JOIN query
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/flag",
            json={"note": "This item seems outdated"},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["is_flagged"] is True
    assert data["flag_note"] == "This item seems outdated"


@pytest.mark.asyncio
async def test_flag_sub_item_without_csrf_returns_403(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/flag",
            json={"note": "note"},
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_flag_sub_item_as_cm_returns_403(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)

    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/flag",
            json={"note": "note"},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_flag_sub_item_not_found_returns_404(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    unknown_id = uuid4()

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),   # get_current_user
        _first_result(None),                       # JOIN returns nothing
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{unknown_id}/actions/flag",
            json={"note": "note"},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "sub-item-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_flag_sub_item_on_pending_approval_matrix_returns_409(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _first_result((sub_item, MatrixStatus.PENDING_APPROVAL)),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/flag",
            json={"note": "note"},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-not-editable" in response.json()["type"]


@pytest.mark.asyncio
async def test_flag_sub_item_on_approved_matrix_returns_409(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _first_result((sub_item, MatrixStatus.APPROVED)),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/flag",
            json={"note": "note"},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-not-editable" in response.json()["type"]


# ─── POST /matrix/{specialist_id}/sub-items/{sub_item_id}/actions/unflag ──────

@pytest.mark.asyncio
async def test_unflag_sub_item_returns_200_with_is_flagged_false(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)
    sub_item.is_flagged = False
    sub_item.flag_note = None

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _first_result((sub_item, MatrixStatus.PENDING_REVIEW)),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/unflag",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["is_flagged"] is False
    assert data["flag_note"] is None


@pytest.mark.asyncio
async def test_unflag_sub_item_without_csrf_returns_403(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    _, _, sub_item = _make_sub_item_with_matrix(specialist.id)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{sub_item.id}/actions/unflag",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unflag_sub_item_not_found_returns_404(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    unknown_id = uuid4()

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _first_result(None),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/sub-items/{unknown_id}/actions/unflag",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "sub-item-not-found" in response.json()["type"]


# ─── POST /matrix/{specialist_id}/actions/submit ──────────────────────────────

@pytest.mark.asyncio
async def test_submit_matrix_returns_200_with_pending_approval(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix(specialist, status=MatrixStatus.PENDING_REVIEW)
    matrix_after = _make_matrix(specialist, status=MatrixStatus.PENDING_APPROVAL)

    override, _, added = _routed_db(
        _scalar_one_or_none_result(specialist),    # get_current_user
        _scalar_one_or_none_result(matrix),        # matrix lookup
        _scalar_one_or_none_result(specialist),    # _load_specialist for notification
        _scalar_one_result(matrix_after),          # eager reload after commit
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_APPROVAL"
    notifications = [obj for obj in added if isinstance(obj, Notification)]
    assert len(notifications) == 1
    assert notifications[0].user_id == cm.id


@pytest.mark.asyncio
async def test_submit_matrix_without_csrf_returns_403(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_matrix_as_cm_returns_403(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_matrix_already_submitted_returns_409(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix = _make_matrix(specialist, status=MatrixStatus.PENDING_APPROVAL)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(matrix),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-already-submitted" in response.json()["type"]


@pytest.mark.asyncio
async def test_submit_matrix_approved_returns_409(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix = _make_matrix(specialist, status=MatrixStatus.APPROVED)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(matrix),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-already-submitted" in response.json()["type"]


@pytest.mark.asyncio
async def test_submit_matrix_not_found_returns_404(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(specialist),
        _scalar_one_or_none_result(None),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "matrix-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_submit_matrix_no_cm_assigned_skips_notification(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=None)
    matrix = _make_matrix(specialist, status=MatrixStatus.PENDING_REVIEW)
    matrix_after = _make_matrix(specialist, status=MatrixStatus.PENDING_APPROVAL)

    override, _, added = _routed_db(
        _scalar_one_or_none_result(specialist),    # get_current_user
        _scalar_one_or_none_result(matrix),        # matrix lookup
        _scalar_one_or_none_result(specialist),    # _load_specialist
        _scalar_one_result(matrix_after),          # eager reload
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/submit",
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    notifications = [obj for obj in added if isinstance(obj, Notification)]
    assert len(notifications) == 0


# ─── Helpers for Story 3.3 tests ──────────────────────────────────────────────

def _make_matrix_pa(specialist: MagicMock) -> MagicMock:
    """Matrix in PENDING_APPROVAL status with approval audit fields."""
    m = _make_matrix(specialist, status=MatrixStatus.PENDING_APPROVAL)
    m.approved_by_id = None
    m.approved_at = None
    m.cm_changes = None
    return m


def _make_approved_matrix(specialist: MagicMock, cm_id) -> MagicMock:
    """Matrix in APPROVED status."""
    m = _make_matrix(specialist, status=MatrixStatus.APPROVED)
    m.approved_by_id = cm_id
    m.approved_at = _now()
    m.cm_changes = {"edits": [], "removals": []}
    return m


# ─── POST /matrix/{specialist_id}/actions/approve ────────────────────────────

@pytest.mark.asyncio
async def test_approve_matrix_returns_200_with_approved_status(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    matrix_approved = _make_approved_matrix(specialist, cm.id)

    # DB call order for CM:
    # 1. get_current_user (CM)
    # 2. matrix with selectinload + for_update
    # 3. CM ownership check (specialist lookup)
    # 4. eager reload after commit
    override, _, added = _routed_db(
        _scalar_one_or_none_result(cm),           # get_current_user
        _scalar_one_or_none_result(matrix),       # matrix fetch
        _scalar_one_or_none_result(specialist),   # CM ownership check
        _scalar_one_result(matrix_approved),      # eager reload
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    notifications = [obj for obj in added if isinstance(obj, Notification)]
    assert len(notifications) == 1
    assert notifications[0].user_id == specialist.id


@pytest.mark.asyncio
async def test_approve_matrix_with_edits_updates_sub_items(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item = matrix.categories[0].sub_items[0]
    sub_item_id = sub_item.id
    matrix_approved = _make_approved_matrix(specialist, cm.id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(specialist),
        _scalar_one_result(matrix_approved),
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [
                    {"id": str(sub_item_id), "name": "Updated name", "description": "Updated desc"}
                ],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_approve_matrix_with_removals_deletes_sub_items(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item = matrix.categories[0].sub_items[0]
    sub_item_id = sub_item.id
    matrix_approved = _make_approved_matrix(specialist, cm.id)

    override, mock_db, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
        _scalars_result([]),                      # 4. re-sequencing
        _scalar_one_result(matrix_approved),      # 5. final reload
    )
    mock_db.delete = AsyncMock()
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [],
                "sub_items_to_remove": [str(sub_item_id)],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_db.delete.assert_awaited_once_with(sub_item)


@pytest.mark.asyncio
async def test_approve_matrix_records_cm_changes(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item = matrix.categories[0].sub_items[0]
    sub_item_id = sub_item.id
    # Add a second sub-item to remove
    sub_item2 = _make_sub_item(matrix.categories[0].id)
    matrix.categories[0].sub_items.append(sub_item2)
    matrix_approved = _make_approved_matrix(specialist, cm.id)

    override, mock_db, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
        _scalars_result([sub_item]),              # 4. re-sequencing
        _scalar_one_result(matrix_approved),      # 5. final reload
    )
    mock_db.delete = AsyncMock()
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [
                    {"id": str(sub_item_id), "name": "New name", "description": "New desc"}
                ],
                "sub_items_to_remove": [str(sub_item2.id)],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    # Verify cm_changes was set on the matrix object
    assert len(matrix.cm_changes["edits"]) == 1
    assert len(matrix.cm_changes["removals"]) == 1


@pytest.mark.asyncio
async def test_approve_matrix_as_admin_returns_200(async_client: AsyncClient):
    admin = _make_user(role=UserRole.ADMIN)
    specialist = _make_user(role=UserRole.SPECIALIST)
    matrix = _make_matrix_pa(specialist)
    matrix_approved = _make_approved_matrix(specialist, admin.id)

    # DB call order for Admin:
    # 1. get_current_user (Admin)
    # 2. matrix fetch
    # 3. eager reload
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(admin),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),          # 2. matrix fetch
        _scalar_one_result(matrix_approved),         # 3. final reload
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(admin)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_approve_matrix_without_csrf_returns_403(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)

    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies={"access_token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_approve_matrix_as_specialist_returns_403(async_client: AsyncClient):
    specialist = _make_user(role=UserRole.SPECIALIST)

    override, _, _ = _routed_db(_scalar_one_or_none_result(specialist))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(specialist)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_approve_matrix_cm_not_owner_returns_404(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    other_cm_id = uuid4()
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=other_cm_id)
    matrix = _make_matrix_pa(specialist)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup (cm_id mismatch)
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "matrix-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_pending_review_returns_409(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix(specialist, status=MatrixStatus.PENDING_REVIEW)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-not-pending-approval" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_already_approved_returns_409(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_approved_matrix(specialist, cm.id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "matrix-not-pending-approval" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_foreign_sub_item_edit_returns_404(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    foreign_id = uuid4()

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [
                    {"id": str(foreign_id), "name": "X", "description": "Y"}
                ],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "sub-item-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_foreign_sub_item_removal_returns_404(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    foreign_id = uuid4()

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(matrix),       # 2. matrix fetch
        _scalar_one_or_none_result(specialist),   # 3. owner lookup
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [],
                "sub_items_to_remove": [str(foreign_id)],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "sub-item-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_not_found_returns_404(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),           # 1. get_current_user
        _scalar_one_or_none_result(None),         # 2. matrix fetch (None)
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={"sub_item_edits": [], "sub_items_to_remove": []},
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "matrix-not-found" in response.json()["type"]


@pytest.mark.asyncio
async def test_approve_matrix_duplicate_edit_ids_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    item_id = uuid4()
    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{uuid4()}/actions/approve",
            json={
                "sub_item_edits": [
                    {"id": str(item_id), "name": "A", "description": "B"},
                    {"id": str(item_id), "name": "C", "description": "D"},
                ],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Duplicate IDs in sub_item_edits" in response.text


@pytest.mark.asyncio
async def test_approve_matrix_duplicate_removal_ids_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    item_id = uuid4()
    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{uuid4()}/actions/approve",
            json={
                "sub_item_edits": [],
                "sub_items_to_remove": [str(item_id), str(item_id)],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Duplicate IDs in sub_items_to_remove" in response.text


@pytest.mark.asyncio
async def test_approve_matrix_overlap_ids_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    item_id = uuid4()
    override, _, _ = _routed_db(_scalar_one_or_none_result(cm))
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{uuid4()}/actions/approve",
            json={
                "sub_item_edits": [{"id": str(item_id), "name": "A", "description": "B"}],
                "sub_items_to_remove": [str(item_id)],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "cannot be both edited and removed" in response.text


@pytest.mark.asyncio
async def test_approve_matrix_empty_name_edit_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item_id = matrix.categories[0].sub_items[0].id

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(specialist),
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [{"id": str(sub_item_id), "name": "  ", "description": "B"}],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Sub-item name cannot be empty" in response.text


@pytest.mark.asyncio
async def test_approve_matrix_long_name_edit_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item_id = matrix.categories[0].sub_items[0].id

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(specialist),
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [{"id": str(sub_item_id), "name": "A" * 256, "description": "B"}],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Sub-item name exceeds 255 chars" in response.text


@pytest.mark.asyncio
async def test_approve_matrix_long_description_edit_returns_422(async_client: AsyncClient):
    cm = _make_user(role=UserRole.CM)
    specialist = _make_user(role=UserRole.SPECIALIST, cm_id=cm.id)
    matrix = _make_matrix_pa(specialist)
    sub_item_id = matrix.categories[0].sub_items[0].id

    override, _, _ = _routed_db(
        _scalar_one_or_none_result(cm),
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(specialist),
    )
    app.dependency_overrides[get_db_session] = override
    try:
        token = _make_jwt(cm)
        response = await async_client.post(
            f"/api/v1/matrix/{specialist.id}/actions/approve",
            json={
                "sub_item_edits": [{"id": str(sub_item_id), "name": "A", "description": "B" * 1001}],
                "sub_items_to_remove": [],
            },
            cookies=_csrf_cookies(token),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Sub-item description exceeds 1000 chars" in response.text
