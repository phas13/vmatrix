from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.usage_event import UsageEventAction, UsageEventResourceType
from app.services.usage_service import record_event


@pytest.mark.asyncio
async def test_record_event_adds_usage_event_to_db():
    db = MagicMock()
    db.add = MagicMock()
    user_id = uuid4()

    await record_event(db, user_id, UsageEventAction.USER_LOGIN)

    db.add.assert_called_once()
    event = db.add.call_args[0][0]
    assert event.user_id == user_id
    assert event.action_type == UsageEventAction.USER_LOGIN
    assert event.resource_id is None
    assert event.resource_type is None


@pytest.mark.asyncio
async def test_record_event_sets_resource_fields():
    db = MagicMock()
    db.add = MagicMock()
    user_id = uuid4()
    session_id = uuid4()

    await record_event(db, user_id, UsageEventAction.SESSION_CREATED,
                       resource_id=session_id, resource_type=UsageEventResourceType.SESSION)

    event = db.add.call_args[0][0]
    assert event.resource_id == session_id
    assert event.resource_type == UsageEventResourceType.SESSION


@pytest.mark.asyncio
async def test_record_event_does_not_commit():
    """record_event must NOT commit — caller owns the transaction."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    await record_event(db, uuid4(), UsageEventAction.ANSWER_SUBMITTED)

    db.commit.assert_not_called()
