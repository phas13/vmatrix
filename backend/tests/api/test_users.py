import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from httpx import AsyncClient

from app.models.user import User, UserRole
from app.models.notification import Notification
from app.db.session import get_db_session
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
