import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from main import app
from app.db.session import get_db_session


@pytest.mark.asyncio
async def test_health_returns_ok_with_db_connected():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_calls_db_select():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/api/v1/health")

    app.dependency_overrides.clear()

    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == "SELECT 1"
