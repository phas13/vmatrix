from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _populate_after_insert(obj) -> None:
    if not hasattr(obj, "id") or obj.id is None:
        obj.id = uuid4()
    if not getattr(obj, "created_at", None):
        obj.created_at = _now()
    if not getattr(obj, "updated_at", None):
        obj.updated_at = _now()


def _scalar_one_or_none_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalar_one_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


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
