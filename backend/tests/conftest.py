from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_llm_provider():
    """Patches get_llm_provider() globally.

    Returns a pre-configured AsyncMock provider with all LLMProvider methods
    as AsyncMock. Tests set return values per-scenario.
    """
    with patch("app.providers.factory.get_llm_provider") as mock_factory:
        provider = AsyncMock()
        provider.generate_initial_matrix = AsyncMock(return_value=([], 100, 500))
        provider.generate_questions = AsyncMock(return_value=([], 200, 1000))
        provider.evaluate_responses = AsyncMock(return_value=(None, 300, 2000))
        provider.propose_matrix_updates = AsyncMock(return_value=[])
        mock_factory.return_value = provider
        yield provider
