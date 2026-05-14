from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.matrix import MatrixUpdateProposal, ProposalStatus
from app.providers.base import MatrixUpdateProposalDraft
from tests._helpers import _now


def _make_draft(
    proposed_change: str = "Add Kubernetes operator pattern",
    source_name: str = "CNCF Landscape",
    source_url: str = "https://landscape.cncf.io/",
    source_date: date | None = date(2026, 1, 1),
) -> MatrixUpdateProposalDraft:
    return MatrixUpdateProposalDraft(
        proposed_change=proposed_change,
        source_name=source_name,
        source_url=source_url,
        source_date=source_date,
    )


def _make_session_ctx(db: AsyncMock) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_run_monitoring_job_creates_proposals():
    """Successful fetch + LLM response → proposals written to DB and committed."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    saved_proposals: list[MatrixUpdateProposal] = []

    def fake_add(obj):
        if isinstance(obj, MatrixUpdateProposal):
            obj.id = uuid4()
            obj.created_at = _now()
            obj.updated_at = _now()
            saved_proposals.append(obj)

    mock_db.add = MagicMock(side_effect=fake_add)
    mock_db.flush = AsyncMock()

    matrix_result = MagicMock()
    matrix_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=matrix_result)

    mock_provider = AsyncMock()
    draft = _make_draft()
    mock_provider.propose_matrix_updates = AsyncMock(return_value=[draft])

    with (
        patch(
            "app.services.monitoring_service.async_session_factory",
            return_value=_make_session_ctx(mock_db),
        ),
        patch(
            "app.services.monitoring_service.get_llm_provider",
            return_value=mock_provider,
        ),
        patch(
            "app.services.monitoring_service._fetch_source",
            new=AsyncMock(return_value="<html>content</html>"),
        ),
        patch(
            "app.services.monitoring_service.MONITORING_SOURCES",
            [{"name": "CNCF Landscape", "url": "https://landscape.cncf.io/"}],
        ),
    ):
        from app.services.monitoring_service import run_monitoring_job

        await run_monitoring_job()

    assert len(saved_proposals) == 1
    assert saved_proposals[0].proposed_change == draft.proposed_change
    assert saved_proposals[0].source_name == draft.source_name
    assert saved_proposals[0].status == ProposalStatus.PENDING
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_monitoring_job_skips_failed_source_continues_others():
    """A fetch failure on one source is isolated — other sources are still processed."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    saved_proposals: list[MatrixUpdateProposal] = []

    def fake_add(obj):
        if isinstance(obj, MatrixUpdateProposal):
            obj.id = uuid4()
            obj.created_at = _now()
            saved_proposals.append(obj)

    mock_db.add = MagicMock(side_effect=fake_add)

    matrix_result = MagicMock()
    matrix_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=matrix_result)

    mock_provider = AsyncMock()
    mock_provider.propose_matrix_updates = AsyncMock(return_value=[_make_draft(source_name="Good Source")])

    call_count = 0

    async def fetch_side_effect(url: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Network error")
        return "<html>content</html>"

    with (
        patch(
            "app.services.monitoring_service.async_session_factory",
            return_value=_make_session_ctx(mock_db),
        ),
        patch(
            "app.services.monitoring_service.get_llm_provider",
            return_value=mock_provider,
        ),
        patch(
            "app.services.monitoring_service._fetch_source",
            new=AsyncMock(side_effect=fetch_side_effect),
        ),
        patch(
            "app.services.monitoring_service.MONITORING_SOURCES",
            [
                {"name": "Failing Source", "url": "https://fail.example.com/"},
                {"name": "Good Source", "url": "https://good.example.com/"},
            ],
        ),
    ):
        from app.services.monitoring_service import run_monitoring_job

        await run_monitoring_job()

    assert len(saved_proposals) == 1
    assert saved_proposals[0].source_name == "Good Source"
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_run_monitoring_job_llm_failure_no_exception_propagated():
    """LLM unavailability is logged and swallowed — job does not raise."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    matrix_result = MagicMock()
    matrix_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=matrix_result)

    from app.core.exceptions import LLMUnavailableError

    mock_provider = AsyncMock()
    mock_provider.propose_matrix_updates = AsyncMock(
        side_effect=LLMUnavailableError("LLM down")
    )

    with (
        patch(
            "app.services.monitoring_service.async_session_factory",
            return_value=_make_session_ctx(mock_db),
        ),
        patch(
            "app.services.monitoring_service.get_llm_provider",
            return_value=mock_provider,
        ),
        patch(
            "app.services.monitoring_service._fetch_source",
            new=AsyncMock(return_value="<html>content</html>"),
        ),
        patch(
            "app.services.monitoring_service.MONITORING_SOURCES",
            [{"name": "CNCF Landscape", "url": "https://landscape.cncf.io/"}],
        ),
    ):
        from app.services.monitoring_service import run_monitoring_job

        await run_monitoring_job()

    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_run_monitoring_job_empty_llm_response_no_db_records():
    """Empty LLM proposal list → no DB records created, no error."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    matrix_result = MagicMock()
    matrix_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=matrix_result)

    mock_provider = AsyncMock()
    mock_provider.propose_matrix_updates = AsyncMock(return_value=[])

    with (
        patch(
            "app.services.monitoring_service.async_session_factory",
            return_value=_make_session_ctx(mock_db),
        ),
        patch(
            "app.services.monitoring_service.get_llm_provider",
            return_value=mock_provider,
        ),
        patch(
            "app.services.monitoring_service._fetch_source",
            new=AsyncMock(return_value="<html>minimal content</html>"),
        ),
        patch(
            "app.services.monitoring_service.MONITORING_SOURCES",
            [{"name": "CNCF Landscape", "url": "https://landscape.cncf.io/"}],
        ),
    ):
        from app.services.monitoring_service import run_monitoring_job

        await run_monitoring_job()

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_run_monitoring_job_deduplicates_proposals():
    """If the same proposal exists in PENDING status, skip saving it again."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    
    # First call to execute: get current matrix state (returns None)
    # Second call to execute: check for existing duplicate (returns an existing proposal)
    existing_proposal = MatrixUpdateProposal(id=uuid4(), proposed_change="Duplicate")
    
    matrix_result = MagicMock()
    matrix_result.scalar_one_or_none.return_value = None
    
    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none.return_value = existing_proposal
    
    mock_db.execute = AsyncMock(side_effect=[matrix_result, duplicate_result])
    mock_db.add = MagicMock()

    mock_provider = AsyncMock()
    draft = _make_draft(proposed_change="Duplicate")
    mock_provider.propose_matrix_updates = AsyncMock(return_value=[draft])

    with (
        patch(
            "app.services.monitoring_service.async_session_factory",
            return_value=_make_session_ctx(mock_db),
        ),
        patch(
            "app.services.monitoring_service.get_llm_provider",
            return_value=mock_provider,
        ),
        patch(
            "app.services.monitoring_service._fetch_source",
            new=AsyncMock(return_value="<html>duplicate</html>"),
        ),
        patch(
            "app.services.monitoring_service.MONITORING_SOURCES",
            [{"name": "CNCF Landscape", "url": "https://landscape.cncf.io/"}],
        ),
    ):
        from app.services.monitoring_service import run_monitoring_job
        await run_monitoring_job()

    # Should NOT have called add or commit because it was a duplicate
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
