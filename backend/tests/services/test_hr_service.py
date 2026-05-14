from unittest.mock import AsyncMock

import pytest

from app.models.user import SpecialistLevel
from app.services.hr_service import get_hr_stats


def _make_db(*result_rows_per_call):
    """Returns AsyncMock db where each execute() call returns the next rows list."""
    queue = [list(rows) for rows in result_rows_per_call]

    async def fake_execute(*_args, **_kwargs):
        return iter(queue.pop(0))

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=fake_execute)
    return db


@pytest.mark.asyncio
async def test_get_hr_stats_empty_when_no_specialists():
    """All sections are empty when there are no active specialists."""
    db = _make_db(
        [],  # level distribution — no rows
        [],  # avg progress — no rows
        [],  # strongest areas — no rows
        [],  # weakest areas — no rows
    )

    result = await get_hr_stats(db)

    assert result.level_distribution == {}
    assert result.avg_progress_per_level == {}
    assert result.strongest_areas == []
    assert result.weakest_areas == []


@pytest.mark.asyncio
async def test_get_hr_stats_level_distribution():
    """Level distribution counts are mapped correctly per level."""
    db = _make_db(
        [
            (SpecialistLevel.JUNIOR, 3),
            (SpecialistLevel.MIDDLE, 5),
            (SpecialistLevel.SENIOR, 2),
        ],
        [],  # avg progress
        [],  # strongest
        [],  # weakest
    )

    result = await get_hr_stats(db)

    assert result.level_distribution == {"junior": 3, "middle": 5, "senior": 2}


@pytest.mark.asyncio
async def test_get_hr_stats_avg_progress_per_level():
    """Average progress per level is computed and mapped correctly."""
    db = _make_db(
        [(SpecialistLevel.JUNIOR, 2)],          # level distribution
        [(SpecialistLevel.JUNIOR, 42)],          # avg progress
        [],
        [],
    )

    result = await get_hr_stats(db)

    assert result.avg_progress_per_level == {"junior": 42}


@pytest.mark.asyncio
async def test_get_hr_stats_strongest_and_weakest_areas():
    """Strongest areas use desc order, weakest use asc order; both mapped to CompetencyAreaStat."""
    db = _make_db(
        [],  # level distribution
        [],  # avg progress
        [("Docker", 90), ("Kubernetes", 85), ("CI/CD", 80)],  # strongest
        [("Security", 30), ("Networking", 35)],               # weakest
    )

    result = await get_hr_stats(db)

    assert len(result.strongest_areas) == 3
    assert result.strongest_areas[0].category_name == "Docker"
    assert result.strongest_areas[0].avg_score == 90

    assert len(result.weakest_areas) == 2
    assert result.weakest_areas[0].category_name == "Security"
    assert result.weakest_areas[0].avg_score == 30


@pytest.mark.asyncio
async def test_get_hr_stats_null_level_skipped():
    """Rows with None specialist_level are excluded from distribution and avg_progress."""
    db = _make_db(
        [(None, 1), (SpecialistLevel.MIDDLE, 4)],   # one row has null level
        [(None, 50), (SpecialistLevel.MIDDLE, 65)],
        [],
        [],
    )

    result = await get_hr_stats(db)

    assert "middle" in result.level_distribution
    assert None not in result.level_distribution
    assert "middle" in result.avg_progress_per_level
    assert None not in result.avg_progress_per_level


@pytest.mark.asyncio
async def test_get_hr_stats_never_queries_forbidden_tables_or_columns():
    """AC2 security invariant: hr_service MUST NEVER reference
    `assessment_responses`, `response_text`, or `ai_rationale` in any SQL.
    Enforced structurally so regressions cannot slip through code review."""
    db = _make_db([], [], [], [])

    await get_hr_stats(db)

    forbidden = ("assessment_responses", "response_text", "ai_rationale")
    for call in db.execute.call_args_list:
        # The compiled SQL statement is the first positional arg
        sql_str = str(call.args[0]).lower()
        for term in forbidden:
            assert term not in sql_str, (
                f"AC2 violation: hr_service SQL referenced forbidden symbol '{term}'.\n"
                f"Query: {sql_str}"
            )


@pytest.mark.asyncio
async def test_get_hr_stats_dedupes_overlap_between_strongest_and_weakest():
    """When ≤5 distinct categories exist, weakest must not duplicate strongest entries."""
    db = _make_db(
        [],
        [],
        [("Docker", 90), ("K8s", 80), ("CI/CD", 70)],   # strongest
        [("Docker", 90), ("K8s", 80), ("CI/CD", 70)],   # weakest (same — full overlap)
    )

    result = await get_hr_stats(db)

    strongest_names = {s.category_name for s in result.strongest_areas}
    for w in result.weakest_areas:
        assert w.category_name not in strongest_names, (
            f"Category '{w.category_name}' appears in both strongest and weakest"
        )
