from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.db.session import get_db_session
from app.models.notification import Notification
from app.models.user import SpecialistLevel, User, UserRole
from app.schemas.session import CategoryScoreRead, SpecialistDashboardRead
from main import app

# Reuse helpers from test_matrix if needed, but for simplicity:
def _make_user(role=UserRole.SPECIALIST):
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.role = role
    u.is_active = True
    return u

def _make_jwt(user):
    from app.core.security import create_access_token
    return create_access_token({"sub": str(user.id), "role": user.role.value})

def _scalar_one_or_none_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r

_DASHBOARD_RESPONSE = SpecialistDashboardRead(
    specialist_level=SpecialistLevel.JUNIOR,
    overall_percentage=61,
    category_scores=[
        CategoryScoreRead(
            category_id=uuid4(),
            category_name="Kubernetes",
            score=61,
            previous_score=55,
            last_assessed_at=None,
        )
    ],
)


@pytest.mark.asyncio
async def test_get_specialist_dashboard_returns_200_for_specialist(async_client: AsyncClient):
    user = _make_user(role=UserRole.SPECIALIST)
    from tests.api.test_matrix import _routed_db
    override, mock_db, _ = _routed_db(_scalar_one_or_none_result(user))
    mock_db.get = AsyncMock(return_value=user)
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(user)
        with patch("app.services.level_service.get_dashboard_data", AsyncMock(return_value=_DASHBOARD_RESPONSE)):
            response = await async_client.get(
                "/api/v1/users/me/dashboard",
                cookies={"access_token": token},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_percentage"] == 61
        assert data["specialist_level"] == "junior"
        assert len(data["category_scores"]) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("role", [UserRole.CM, UserRole.HR, UserRole.ADMIN])
@pytest.mark.asyncio
async def test_get_specialist_dashboard_returns_403_for_non_specialist(
    async_client: AsyncClient, role: UserRole
):
    user = _make_user(role=role)
    from tests.api.test_matrix import _routed_db
    override, _, _ = _routed_db(_scalar_one_or_none_result(user))
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(user)
        response = await async_client.get(
            "/api/v1/users/me/dashboard",
            cookies={"access_token": token},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mark_notification_read_idempotent(async_client: AsyncClient):
    user = _make_user()
    notification = MagicMock(spec=Notification)
    notification.id = uuid4()
    notification.user_id = user.id
    notification.is_read = False
    notification.read_at = None

    # Mock DB calls: Each call needs (1. user lookup, 2. notification lookup)
    from tests.api.test_matrix import _routed_db
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(user),         # 1st call: user
        _scalar_one_or_none_result(notification), # 1st call: notification
        _scalar_one_or_none_result(user),         # 2nd call: user
        _scalar_one_or_none_result(notification), # 2nd call: notification
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(user)
        # First call: marks as read
        response = await async_client.post(
            f"/api/v1/users/me/notifications/{notification.id}/read",
            cookies={"access_token": token}
        )
        assert response.status_code == 200
        assert notification.is_read is True
        assert notification.read_at is not None
        
        first_read_at = notification.read_at
        
        # Second call: should not overwrite
        response = await async_client.post(
            f"/api/v1/users/me/notifications/{notification.id}/read",
            cookies={"access_token": token}
        )
        assert response.status_code == 200
        assert notification.read_at == first_read_at
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_unread_notifications_paginated(async_client: AsyncClient):
    user = _make_user()
    notif1 = MagicMock(spec=Notification)
    notif1.id = uuid4()
    notif1.user_id = user.id
    from app.models.notification import NotificationType
    notif1.type = NotificationType.NEW_CM_ASSIGNMENT
    notif1.content = "Test content"
    notif1.is_read = False
    notif1.read_at = None
    notif1.created_at = datetime.now()
    notif1.updated_at = datetime.now()

    # Mocking rows: (notification_obj, total_count)
    rows = [(notif1, 1)]
    
    from tests.api.test_matrix import _routed_db
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    
    override, _, _ = _routed_db(
        _scalar_one_or_none_result(user), # auth me
        mock_result,                      # notifications query
    )
    app.dependency_overrides[get_db_session] = override

    try:
        token = _make_jwt(user)
        response = await async_client.get(
            "/api/v1/users/me/notifications/unread?page=1&per_page=10",
            cookies={"access_token": token}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 1
        assert data["page"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(notif1.id)
    finally:
        app.dependency_overrides.clear()
