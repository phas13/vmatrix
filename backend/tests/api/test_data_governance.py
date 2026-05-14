"""Data governance verification tests — AC1-AC4 of Story 8.2."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.session import AssessmentResponse, AssessmentSession, SessionDispute
from app.models.llm_call_log import LLMCallLog
from app.models.usage_event import UsageEventAction


# ─── AC3: FK constraint assertions (static, no DB required) ────────────────────

def test_assessment_session_specialist_fk_is_restrict():
    fk = next(iter(AssessmentSession.specialist_id.property.columns[0].foreign_keys))
    assert fk.ondelete == "RESTRICT"


def test_assessment_response_session_fk_is_restrict():
    fk = next(iter(AssessmentResponse.session_id.property.columns[0].foreign_keys))
    assert fk.ondelete == "RESTRICT"


def test_session_dispute_session_fk_is_restrict():
    fk = next(iter(SessionDispute.session_id.property.columns[0].foreign_keys))
    assert fk.ondelete == "RESTRICT"


def test_llm_call_log_specialist_fk_is_set_null():
    fk = next(iter(LLMCallLog.specialist_id.property.columns[0].foreign_keys))
    assert fk.ondelete == "SET NULL"


# ─── AC2: Fernet encryption in submit_answer ────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_answer_encrypts_response_text():
    """response_text is stored encrypted, not plaintext."""
    from app.services.session_service import submit_answer
    from app.models.session import SessionStatus
    from app.models.user import User, UserRole
    from app.core.security import decrypt_field

    plain = "My answer text"
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.SPECIALIST

    session = MagicMock(spec=AssessmentSession)
    session.id = uuid4()
    session.specialist_id = user.id
    session.status = SessionStatus.IN_PROGRESS

    sess_result = MagicMock()
    sess_result.scalar_one_or_none.return_value = session
    q_result = MagicMock()
    q_result.scalar_one_or_none.return_value = MagicMock()
    dup_result = MagicMock()
    dup_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=[sess_result, q_result, dup_result])

    with patch("app.services.usage_service.record_event", new_callable=AsyncMock):
        await submit_answer(
            session_id=session.id,
            question_id=uuid4(),
            response_text=plain,
            db=db,
            current_user=user,
            instance="test",
        )

    db.add.assert_called_once()
    stored_response = db.add.call_args[0][0]
    assert isinstance(stored_response, AssessmentResponse)
    assert stored_response.response_text != plain
    assert decrypt_field(stored_response.response_text) == plain


# ─── AC4: Specialist isolation — cannot access another specialist's session ─────

@pytest.mark.asyncio
async def test_submit_answer_rejects_wrong_specialist():
    """Returns 404 when the session belongs to a different specialist.

    Exercises the ownership-check branch: db returns a session, but
    session.specialist_id != current_user.id. The service must raise 404
    with the same shape as the not-found case (no enumeration via error type).
    """
    from fastapi import HTTPException
    from app.services.session_service import submit_answer
    from app.models.session import SessionStatus
    from app.models.user import User, UserRole

    owner_id = uuid4()
    caller_id = uuid4()

    session = MagicMock(spec=AssessmentSession)
    session.id = uuid4()
    session.specialist_id = owner_id
    session.status = SessionStatus.IN_PROGRESS

    caller = MagicMock(spec=User)
    caller.id = caller_id
    caller.role = UserRole.SPECIALIST

    sess_result = MagicMock()
    sess_result.scalar_one_or_none.return_value = session

    db = AsyncMock()
    db.execute = AsyncMock(return_value=sess_result)

    with pytest.raises(HTTPException) as exc_info:
        await submit_answer(
            session_id=session.id,
            question_id=uuid4(),
            response_text="irrelevant",
            db=db,
            current_user=caller,
            instance="test",
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_answer_returns_404_when_session_not_found():
    """Returns 404 when the session does not exist.

    Exercises the not-found branch: db returns None. Must produce the same
    404 as the wrong-owner case so the response shape does not leak whether
    a session id is real-but-foreign vs. nonexistent.
    """
    from fastapi import HTTPException
    from app.services.session_service import submit_answer
    from app.models.user import User, UserRole

    caller = MagicMock(spec=User)
    caller.id = uuid4()
    caller.role = UserRole.SPECIALIST

    sess_result = MagicMock()
    sess_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=sess_result)

    with pytest.raises(HTTPException) as exc_info:
        await submit_answer(
            session_id=uuid4(),
            question_id=uuid4(),
            response_text="irrelevant",
            db=db,
            current_user=caller,
            instance="test",
        )

    assert exc_info.value.status_code == 404


# ─── AC1: Usage event staged in auth flow ───────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_records_user_login_event():
    """USER_LOGIN event is added to transaction when auth session is created."""
    from app.services.auth_service import create_session
    from app.models.user import User, UserRole

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.SPECIALIST

    db = AsyncMock()
    db.add = MagicMock()

    with patch("app.services.usage_service.record_event", new_callable=AsyncMock) as mock_record:
        await create_session(user, db)

    mock_record.assert_called_once()
    args = mock_record.call_args[0]
    assert args[1] == user.id
    assert args[2] == UsageEventAction.USER_LOGIN
