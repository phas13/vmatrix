import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security import create_access_token, decrypt_field, encrypt_field
from app.db.session import get_db_session
from app.models.matrix import CompetencyCategory, CompetencyMatrix, CompetencySubItem, MatrixStatus
from app.models.session import (
    AssessmentQuestion,
    AssessmentResponse,
    AssessmentSession,
    SessionStatus,
    SpecialistScore,
)
from app.models.user import SpecialistLevel, User, UserRole
from app.providers.base import AssessmentQuestionDraft, QuestionFeedback, SessionEvaluationResult
from main import app


def _scalars_all_result_simple(values: list) -> MagicMock:
    r = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    r.scalars.return_value = scalars
    return r


def _scalar_one_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_user(
    role: UserRole = UserRole.SPECIALIST,
    specialist_level: SpecialistLevel | None = SpecialistLevel.JUNIOR,
) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.role = role
    u.is_active = True
    u.specialist_level = specialist_level
    u.email = f"test-{u.id.hex[:6]}@example.com"
    u.full_name = "Test User"
    return u


def _make_jwt(user: MagicMock) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _make_session(specialist: MagicMock) -> MagicMock:
    s = MagicMock(spec=AssessmentSession)
    s.id = uuid4()
    s.specialist_id = specialist.id
    s.category_id = uuid4()
    s.status = SessionStatus.IN_PROGRESS
    s.created_at = _now()
    s.updated_at = _now()
    return s


# ─── LLM Provider interface tests ─────────────────────────────────────────────

def test_question_generation_context_dataclass_importable():
    from app.providers.base import QuestionGenerationContext, SubItemInfo
    ctx = QuestionGenerationContext(
        specialist_id=uuid4(),
        category_name="CI/CD",
        category_description="Continuous delivery practices",
        sub_items=[SubItemInfo(name="Pipeline design", description="CI pipeline knowledge")],
        level="junior",
        num_questions=8,
    )
    assert ctx.num_questions == 8


def test_response_evaluation_context_dataclass_importable():
    from app.providers.base import QAEntry, ResponseEvaluationContext
    ctx = ResponseEvaluationContext(
        specialist_id=uuid4(),
        category_name="CI/CD",
        level="junior",
        qa_entries=[QAEntry(
            question_text="What is CI?",
            question_type="theoretical",
            response_text="CI is...",
            order=0,
        )],
    )
    assert len(ctx.qa_entries) == 1


def test_mock_llm_provider_fixture_has_all_methods(mock_llm_provider):
    assert hasattr(mock_llm_provider, "generate_questions")
    assert hasattr(mock_llm_provider, "evaluate_responses")
    assert hasattr(mock_llm_provider, "generate_initial_matrix")
    assert hasattr(mock_llm_provider, "propose_matrix_updates")


@pytest.mark.asyncio
async def test_mock_llm_provider_generate_questions_is_async(mock_llm_provider):
    from app.providers.base import QuestionGenerationContext
    ctx = QuestionGenerationContext(
        specialist_id=uuid4(),
        category_name="CI/CD",
        category_description="desc",
        sub_items=[],
        level="junior",
        num_questions=8,
    )
    mock_llm_provider.generate_questions.return_value = (
        [AssessmentQuestionDraft(text="Test?", question_type="theoretical", order=0)],
        100,
        500,
    )
    result, latency, tokens = await mock_llm_provider.generate_questions(ctx)
    assert len(result) == 1
    assert result[0].question_type == "theoretical"


def test_factory_returns_claude_provider_by_default():
    from app.providers.claude import ClaudeProvider
    from app.providers.factory import get_llm_provider
    provider = get_llm_provider()
    assert isinstance(provider, ClaudeProvider)


def test_assessment_question_draft_dataclass():
    draft = AssessmentQuestionDraft(text="Explain CI/CD", question_type="theoretical", order=0)
    assert draft.text == "Explain CI/CD"
    assert draft.order == 0


def test_session_evaluation_result_dataclass():
    feedback = QuestionFeedback(question_order=0, commentary="Good answer")
    result = SessionEvaluationResult(
        score=85,
        strengths="Clear explanations",
        areas_for_growth="More depth on edge cases",
        per_question_feedback=[feedback],
    )
    assert result.score == 85
    assert len(result.per_question_feedback) == 1


def test_session_status_enum_values():
    assert SessionStatus.IN_PROGRESS == "in_progress"
    assert SessionStatus.EVALUATION_PENDING == "evaluation_pending"
    assert SessionStatus.COMPLETED == "completed"
    assert SessionStatus.ABANDONED == "abandoned"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _scalar_one_or_none_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _populate_after_insert(obj) -> None:
    if not hasattr(obj, "id") or obj.id is None:
        object.__setattr__(obj, "id", uuid4())
    if not getattr(obj, "created_at", None):
        try:
            obj.created_at = _now()
        except Exception:
            pass
    if not getattr(obj, "updated_at", None):
        try:
            obj.updated_at = _now()
        except Exception:
            pass


def _make_sub_item(category_id) -> MagicMock:
    si = MagicMock(spec=CompetencySubItem)
    si.id = uuid4()
    si.category_id = category_id
    si.name = "Pipeline design"
    si.description = "Knows how to design a CI pipeline"
    si.order = 0
    return si


def _make_category(matrix_id) -> MagicMock:
    c = MagicMock(spec=CompetencyCategory)
    c.id = uuid4()
    c.matrix_id = matrix_id
    c.name = "CI/CD"
    c.description = "Continuous integration and delivery practices"
    c.order = 0
    c.sub_items = [_make_sub_item(c.id)]
    return c


def _make_matrix(specialist: MagicMock, status: MatrixStatus = MatrixStatus.APPROVED) -> MagicMock:
    m = MagicMock(spec=CompetencyMatrix)
    m.id = uuid4()
    m.specialist_id = specialist.id
    m.domain = "DevOps"
    m.status = status
    return m


def _make_routed_db(*results) -> tuple:
    queue = list(results)
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.flush = AsyncMock()

    added: list = []

    def fake_add(obj):
        added.append(obj)
        _populate_after_insert(obj)

    async def fake_refresh(obj):
        _populate_after_insert(obj)

    mock_db.add = MagicMock(side_effect=fake_add)
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    async def execute_side_effect(*_args, **_kwargs):
        return queue.pop(0) if queue else _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    return override, mock_db, added


CSRF_TOKEN = "test-csrf-token-sessions"


def _csrf_cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": CSRF_TOKEN}


def _csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": CSRF_TOKEN}


# ─── Story 4.2: create_session_stream service unit tests ─────────────────────

def _make_mock_llm_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.health_check = AsyncMock(return_value=None)
    provider.generate_questions = AsyncMock(return_value=([], 200, 1000))
    return provider


@pytest.mark.asyncio
async def test_create_session_stream_validates_matrix_approved():
    """Matrix with non-APPROVED status → _matrix_not_approved (422)."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import create_session_stream

    specialist = _make_user()
    matrix = _make_matrix(specialist, status=MatrixStatus.PENDING_REVIEW)

    _, mock_db, _ = _make_routed_db(
        _scalar_one_or_none_result(matrix),
    )

    mock_provider = _make_mock_llm_provider()
    with patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        with pytest.raises(ProblemHTTPException) as exc_info:
            await create_session_stream(
                specialist_id=specialist.id,
                category_id=uuid4(),
                db=mock_db,
                current_user=specialist,
                instance="/api/v1/sessions",
            )

    assert exc_info.value.status_code == 422
    assert "matrix-not-approved" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_create_session_stream_validates_category_belongs_to_matrix():
    """Category from a different matrix → _category_not_found (404)."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import create_session_stream

    specialist = _make_user()
    matrix = _make_matrix(specialist, status=MatrixStatus.APPROVED)

    _, mock_db, _ = _make_routed_db(
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(None),
    )

    mock_provider = _make_mock_llm_provider()
    with patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        with pytest.raises(ProblemHTTPException) as exc_info:
            await create_session_stream(
                specialist_id=specialist.id,
                category_id=uuid4(),
                db=mock_db,
                current_user=specialist,
                instance="/api/v1/sessions",
            )

    assert exc_info.value.status_code == 404
    assert "category-not-found" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_create_session_stream_prevents_concurrent_sessions():
    """Existing IN_PROGRESS session → _session_conflict (409)."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import create_session_stream

    specialist = _make_user()
    matrix = _make_matrix(specialist)
    category = _make_category(matrix.id)
    existing_session = _make_session(specialist)
    existing_session.category_id = category.id

    _, mock_db, _ = _make_routed_db(
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(category),
        _scalar_one_or_none_result(existing_session),
    )

    mock_provider = _make_mock_llm_provider()
    with patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        with pytest.raises(ProblemHTTPException) as exc_info:
            await create_session_stream(
                specialist_id=specialist.id,
                category_id=category.id,
                db=mock_db,
                current_user=specialist,
                instance="/api/v1/sessions",
            )

    assert exc_info.value.status_code == 409
    assert "session-conflict" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_create_session_stream_calls_llm_and_persists_questions():
    """Happy path: mock returns 2 questions → session + questions persisted, SSE events yielded."""
    from app.services.session_service import create_session_stream

    specialist = _make_user()
    matrix = _make_matrix(specialist)
    category = _make_category(matrix.id)

    mock_provider = _make_mock_llm_provider()
    mock_provider.generate_questions = AsyncMock(return_value=(
        [
            AssessmentQuestionDraft(text="What is CI?", question_type="theoretical", order=0),
            AssessmentQuestionDraft(text="Write a pipeline", question_type="practical", order=1),
        ],
        200,
        1000,
    ))

    _, mock_db, added = _make_routed_db(
        _scalar_one_or_none_result(matrix),
        _scalar_one_or_none_result(category),
        _scalar_one_or_none_result(None),
    )

    with patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        generator = await create_session_stream(
            specialist_id=specialist.id,
            category_id=category.id,
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions",
        )

    events = []
    async for chunk in generator:
        line = chunk.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    assert mock_db.commit.called
    event_types = [e["type"] for e in events]
    assert event_types[0] == "session"
    assert event_types[-1] == "done"
    question_events = [e for e in events if e["type"] == "question"]
    assert len(question_events) == 2
    assert question_events[0]["order"] == 0
    assert question_events[1]["order"] == 1


# ─── Story 4.2: HTTP integration tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_answer_stores_encrypted_response(async_client, mock_llm_provider):
    """submit-answer stores encrypted response_text (not plaintext)."""
    specialist = _make_user()
    jwt = _make_jwt(specialist)

    session_id = uuid4()
    question_id = uuid4()
    raw_answer = "My detailed answer about CI/CD pipelines"

    mock_session = _make_session(specialist)
    mock_session.id = session_id
    mock_session.status = SessionStatus.IN_PROGRESS

    mock_question = MagicMock(spec=AssessmentQuestion)
    mock_question.id = question_id
    mock_question.session_id = session_id

    mock_response = MagicMock(spec=AssessmentResponse)
    mock_response.id = uuid4()
    mock_response.session_id = session_id
    mock_response.question_id = question_id
    mock_response.created_at = _now()
    mock_response.updated_at = _now()

    captured_add: list = []

    def fake_add(obj):
        captured_add.append(obj)
        _populate_after_insert(obj)

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock(side_effect=fake_add)
    mock_db.refresh = AsyncMock(side_effect=lambda obj: _populate_after_insert(obj))

    call_count = 0

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # get_current_user
            return _scalar_one_or_none_result(specialist)
        if call_count == 2:
            # session lookup with lock
            return _scalar_one_or_none_result(mock_session)
        if call_count == 3:
            # question lookup
            return _scalar_one_or_none_result(mock_question)
        if call_count == 4:
            # duplicate check → no duplicate
            return _scalar_one_or_none_result(None)
        return _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.post(
            f"/api/v1/sessions/{session_id}/actions/submit-answer",
            json={"question_id": str(question_id), "response_text": raw_answer},
            cookies=_csrf_cookies(jwt),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 201
    # Verify that stored response_text is encrypted (not plaintext)
    stored_responses = [obj for obj in captured_add if isinstance(obj, AssessmentResponse)]
    assert len(stored_responses) == 1
    stored_text = stored_responses[0].response_text
    assert stored_text != raw_answer
    decrypted = decrypt_field(stored_text)
    assert decrypted == raw_answer


@pytest.mark.asyncio
async def test_submit_answer_rejects_duplicate(async_client, mock_llm_provider):
    """Submit same question_id twice → 409."""
    specialist = _make_user()
    jwt = _make_jwt(specialist)

    session_id = uuid4()
    question_id = uuid4()

    mock_session = _make_session(specialist)
    mock_session.id = session_id
    mock_session.status = SessionStatus.IN_PROGRESS

    mock_question = MagicMock(spec=AssessmentQuestion)
    mock_question.id = question_id
    mock_question.session_id = session_id

    mock_existing_response = MagicMock(spec=AssessmentResponse)

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()

    call_count = 0

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_one_or_none_result(specialist)
        if call_count == 2:
            return _scalar_one_or_none_result(mock_session)
        if call_count == 3:
            return _scalar_one_or_none_result(mock_question)
        if call_count == 4:
            return _scalar_one_or_none_result(mock_existing_response)
        return _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.post(
            f"/api/v1/sessions/{session_id}/actions/submit-answer",
            json={"question_id": str(question_id), "response_text": "My answer"},
            cookies=_csrf_cookies(jwt),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 409
    assert "answer-conflict" in response.json()["type"]


@pytest.mark.asyncio
async def test_submit_answer_rejects_wrong_session(async_client, mock_llm_provider):
    """Submit to session belonging to different specialist → 404."""
    specialist = _make_user()
    other_specialist = _make_user()
    jwt = _make_jwt(specialist)

    session_id = uuid4()
    question_id = uuid4()

    # Session belongs to other_specialist
    mock_session = _make_session(other_specialist)
    mock_session.id = session_id

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()

    call_count = 0

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_one_or_none_result(specialist)
        if call_count == 2:
            return _scalar_one_or_none_result(mock_session)
        return _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.post(
            f"/api/v1/sessions/{session_id}/actions/submit-answer",
            json={"question_id": str(question_id), "response_text": "My answer"},
            cookies=_csrf_cookies(jwt),
            headers=_csrf_headers(),
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_returns_questions_sorted_by_order(async_client, mock_llm_provider):
    """GET /sessions/{id} returns session with questions sorted ascending by order."""
    specialist = _make_user()
    jwt = _make_jwt(specialist)
    session_id = uuid4()

    q1 = MagicMock(spec=AssessmentQuestion)
    q1.id = uuid4()
    q1.session_id = session_id
    q1.text = "Second question"
    q1.question_type = "practical"
    q1.order = 1
    q1.created_at = _now()
    q1.updated_at = _now()

    q0 = MagicMock(spec=AssessmentQuestion)
    q0.id = uuid4()
    q0.session_id = session_id
    q0.text = "First question"
    q0.question_type = "theoretical"
    q0.order = 0
    q0.created_at = _now()
    q0.updated_at = _now()

    mock_session = MagicMock(spec=AssessmentSession)
    mock_session.id = session_id
    mock_session.specialist_id = specialist.id
    mock_session.category_id = uuid4()
    mock_session.status = SessionStatus.IN_PROGRESS
    mock_session.final_score = None
    mock_session.previous_score = None
    mock_session.strengths = None
    mock_session.areas_for_growth = None
    mock_session.created_at = _now()
    mock_session.updated_at = _now()
    mock_session.questions = [q1, q0]  # intentionally unsorted
    mock_session.responses = []
    mock_session.dispute = None

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    call_count = 0

    def _scalar_result(value) -> MagicMock:
        r = MagicMock()
        r.scalar.return_value = value
        return r

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_one_or_none_result(specialist)
        if call_count == 2:
            return _scalar_one_or_none_result(mock_session)
        if call_count == 3:
            # category name lookup — uses result.scalar()
            return _scalar_result(None)
        if call_count == 4:
            # calculate_percentage → matrix query
            return _scalar_one_or_none_result(None)
        return _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            f"/api/v1/sessions/{session_id}",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(session_id)
    questions = data["questions"]
    assert len(questions) == 2
    assert questions[0]["order"] == 0
    assert questions[1]["order"] == 1


# ─── Story 4.3: evaluate_session service unit tests ───────────────────────────

def _scalars_all_result(values: list) -> MagicMock:
    r = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    r.scalars.return_value = scalars
    return r


def _make_session_with_qa(specialist: MagicMock) -> tuple:
    """Returns (session, question, response) mocks with one answered question."""
    session = _make_session(specialist)
    session.final_score = None
    session.previous_score = None
    session.strengths = None
    session.areas_for_growth = None

    question = MagicMock(spec=AssessmentQuestion)
    question.id = uuid4()
    question.session_id = session.id
    question.text = "What is CI?"
    question.question_type = "theoretical"
    question.order = 0

    resp = MagicMock(spec=AssessmentResponse)
    resp.id = uuid4()
    resp.session_id = session.id
    resp.question_id = question.id
    resp.response_text = encrypt_field("CI is continuous integration")
    resp.ai_rationale = None

    session.questions = [question]
    session.responses = [resp]
    return session, question, resp


@pytest.mark.asyncio
async def test_evaluate_session_success():
    """Happy path: all answers present, LLM returns result → score/status dict returned."""
    from unittest.mock import patch as mock_patch
    from app.services.session_service import evaluate_session

    specialist = _make_user()
    session, question, resp = _make_session_with_qa(specialist)
    category = _make_category(uuid4())

    mock_eval_result = SessionEvaluationResult(
        score=78,
        strengths="Strong understanding of pipeline fundamentals.",
        areas_for_growth="Could improve knowledge of advanced caching strategies.",
        per_question_feedback=[QuestionFeedback(question_order=0, commentary="Good answer.")],
    )

    matrix = _make_matrix(specialist)

    _, mock_db, _ = _make_routed_db(
        _scalar_one_or_none_result(session),    # session FOR UPDATE
        _scalar_one_or_none_result(category),   # category lookup
        _scalar_one_or_none_result(None),        # no prior SpecialistScore
        # calculate_percentage (step 10)
        _scalar_one_or_none_result(matrix),      # 1. matrix query
        _scalars_all_result([category.id]),      # 2. categories query
        _scalars_all_result([78]),               # 3. scores query
        # check_threshold (step 11)
        _scalar_one_or_none_result(None),        # SystemSettings (fallback 90, 78 < 90 → False)
    )
    mock_provider = AsyncMock()
    mock_provider.evaluate_responses = AsyncMock(return_value=(mock_eval_result, 1200, 4000))

    with mock_patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        result = await evaluate_session(
            session_id=session.id,
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/evaluate",
        )

    assert result["final_score"] == 78
    assert result["previous_score"] is None
    assert result["level_percentage"] == 78
    assert result["status"] == SessionStatus.COMPLETED
    assert mock_db.commit.called
    mock_provider.evaluate_responses.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_session_llm_failure():
    """LLM raises LLMUnavailableError → 503 exception raised, session set to EVALUATION_PENDING."""
    from unittest.mock import patch as mock_patch
    from app.core.exceptions import LLMUnavailableError, ProblemHTTPException
    from app.services.session_service import evaluate_session

    specialist = _make_user()
    session, _, _ = _make_session_with_qa(specialist)
    category = _make_category(uuid4())

    _, mock_db, _ = _make_routed_db(
        _scalar_one_or_none_result(session),
        _scalar_one_or_none_result(category),
    )

    mock_provider = AsyncMock()
    mock_provider.evaluate_responses = AsyncMock(
        side_effect=LLMUnavailableError("claude timeout")
    )

    with mock_patch("app.services.session_service.get_llm_provider", return_value=mock_provider):
        with pytest.raises(ProblemHTTPException) as exc_info:
            await evaluate_session(
                session_id=session.id,
                db=mock_db,
                current_user=specialist,
                instance="/api/v1/sessions/test/actions/evaluate",
            )

    assert exc_info.value.status_code == 503
    assert "llm-unavailable" in exc_info.value.detail["type"]
    assert session.status == SessionStatus.EVALUATION_PENDING
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_evaluate_session_incomplete():
    """Not all questions answered → 422 before LLM call."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import evaluate_session

    specialist = _make_user()
    session = _make_session(specialist)
    session.final_score = None
    session.previous_score = None

    extra_question = MagicMock(spec=AssessmentQuestion)
    extra_question.id = uuid4()
    session.questions = [extra_question]
    session.responses = []  # no answers

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await evaluate_session(
            session_id=session.id,
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/evaluate",
        )

    assert exc_info.value.status_code == 422
    assert "incomplete-session" in exc_info.value.detail["type"]
    assert not mock_db.commit.called


@pytest.mark.asyncio
async def test_evaluate_session_already_completed():
    """Session already COMPLETED → 409."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import evaluate_session

    specialist = _make_user()
    session, _, _ = _make_session_with_qa(specialist)
    session.status = SessionStatus.COMPLETED

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await evaluate_session(
            session_id=session.id,
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/evaluate",
        )

    assert exc_info.value.status_code == 409
    assert "session-already-evaluated" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_evaluate_session_wrong_owner():
    """Session belongs to different specialist → 404 (information hiding)."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import evaluate_session

    specialist = _make_user()
    other_specialist = _make_user()
    session, _, _ = _make_session_with_qa(other_specialist)

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await evaluate_session(
            session_id=session.id,
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/evaluate",
        )

    assert exc_info.value.status_code == 404
    assert "session-not-found" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_get_session_returns_ai_rationale(async_client, mock_llm_provider):
    """GET /sessions/{id} returns decrypted ai_rationale in responses after evaluation."""
    specialist = _make_user()
    jwt = _make_jwt(specialist)
    session_id = uuid4()
    question_id = uuid4()

    raw_rationale = "Based on your responses: Good answer."

    mock_q = MagicMock(spec=AssessmentQuestion)
    mock_q.id = question_id
    mock_q.session_id = session_id
    mock_q.text = "What is CI?"
    mock_q.question_type = "theoretical"
    mock_q.order = 0
    mock_q.created_at = _now()
    mock_q.updated_at = _now()

    mock_resp = MagicMock(spec=AssessmentResponse)
    mock_resp.id = uuid4()
    mock_resp.session_id = session_id
    mock_resp.question_id = question_id
    mock_resp.response_text = encrypt_field("My answer")
    mock_resp.ai_rationale = encrypt_field(raw_rationale)
    mock_resp.created_at = _now()
    mock_resp.updated_at = _now()

    mock_session = MagicMock(spec=AssessmentSession)
    mock_session.id = session_id
    mock_session.specialist_id = specialist.id
    mock_session.category_id = uuid4()
    mock_session.status = SessionStatus.COMPLETED
    mock_session.final_score = 78
    mock_session.previous_score = None
    mock_session.strengths = encrypt_field("Strong skills.")
    mock_session.areas_for_growth = encrypt_field("Improve edge cases.")
    mock_session.created_at = _now()
    mock_session.updated_at = _now()
    mock_session.questions = [mock_q]
    mock_session.responses = [mock_resp]
    mock_session.dispute = None

    mock_db = AsyncMock()
    call_count = 0

    def _scalar_result(value) -> MagicMock:
        r = MagicMock()
        r.scalar.return_value = value
        return r

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_one_or_none_result(specialist)
        if call_count == 2:
            return _scalar_one_or_none_result(mock_session)
        if call_count == 3:
            # category name lookup — uses result.scalar()
            return _scalar_result(None)
        if call_count == 4:
            # calculate_percentage → matrix query
            return _scalar_one_or_none_result(None)
        return _scalar_one_or_none_result(None)

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            f"/api/v1/sessions/{session_id}",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data["final_score"] == 78
    assert data["strengths"] == "Strong skills."
    assert data["areas_for_growth"] == "Improve edge cases."
    assert len(data["responses"]) == 1
    assert data["responses"][0]["ai_rationale"] == raw_rationale


# ─── Story 4.4: submit_dispute ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_dispute_success():
    """Happy path: creates SessionDispute and Notification, returns 201."""
    from app.services.session_service import submit_dispute

    specialist = _make_user()
    specialist.cm_id = uuid4()
    session = _make_session(specialist)
    session.status = SessionStatus.COMPLETED
    session.dispute = None

    override, mock_db, added = _make_routed_db(_scalar_one_or_none_result(session))

    await submit_dispute(
        session_id=session.id,
        specialist_explanation="I disagree with the evaluation.",
        db=mock_db,
        current_user=specialist,
        instance="/api/v1/sessions/test/actions/submit-dispute",
    )

    mock_db.commit.assert_called_once()
    assert len(added) == 3  # dispute + notification + usage event
    from app.models.usage_event import UsageEvent, UsageEventAction
    usage_event = next(x for x in added if isinstance(x, UsageEvent))
    assert usage_event.action_type == UsageEventAction.DISPUTE_SUBMITTED


@pytest.mark.asyncio
async def test_submit_dispute_duplicate():
    """Session already has dispute → 409."""
    from app.core.exceptions import ProblemHTTPException
    from app.models.session import SessionDispute as SessionDisputeModel, DisputeStatus
    from app.services.session_service import submit_dispute

    specialist = _make_user()
    session = _make_session(specialist)
    session.status = SessionStatus.COMPLETED
    existing_dispute = MagicMock(spec=SessionDisputeModel)
    existing_dispute.status = DisputeStatus.OPEN
    session.dispute = existing_dispute

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await submit_dispute(
            session_id=session.id,
            specialist_explanation="Still disagree.",
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/submit-dispute",
        )

    assert exc_info.value.status_code == 409
    assert "dispute-already-exists" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_submit_dispute_session_not_completed():
    """Session not COMPLETED → 422."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import submit_dispute

    specialist = _make_user()
    session = _make_session(specialist)
    session.status = SessionStatus.IN_PROGRESS
    session.dispute = None

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await submit_dispute(
            session_id=session.id,
            specialist_explanation="I disagree.",
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/submit-dispute",
        )

    assert exc_info.value.status_code == 422
    assert "session-not-completed" in exc_info.value.detail["type"]


@pytest.mark.asyncio
async def test_submit_dispute_wrong_owner():
    """Session belongs to different specialist → 404 (information hiding)."""
    from app.core.exceptions import ProblemHTTPException
    from app.services.session_service import submit_dispute

    specialist = _make_user()
    other_specialist = _make_user()
    session = _make_session(other_specialist)
    session.status = SessionStatus.COMPLETED
    session.dispute = None

    _, mock_db, _ = _make_routed_db(_scalar_one_or_none_result(session))

    with pytest.raises(ProblemHTTPException) as exc_info:
        await submit_dispute(
            session_id=session.id,
            specialist_explanation="I disagree.",
            db=mock_db,
            current_user=specialist,
            instance="/api/v1/sessions/test/actions/submit-dispute",
        )

    assert exc_info.value.status_code == 404
    assert "session-not-found" in exc_info.value.detail["type"]


# ─── Story 5.2: list_sessions ──────────────────────────────────────────────────

def _make_completed_session(specialist: MagicMock) -> MagicMock:
    s = MagicMock(spec=AssessmentSession)
    s.id = uuid4()
    s.specialist_id = specialist.id
    s.category_id = uuid4()
    s.status = SessionStatus.COMPLETED
    s.final_score = 75
    s.previous_score = 60
    s.created_at = _now()
    s.updated_at = _now()
    s.dispute = None
    return s


@pytest.mark.asyncio
async def test_list_sessions_returns_paginated_completed_sessions(async_client, mock_llm_provider):
    specialist = _make_user(role=UserRole.SPECIALIST)
    token = _make_jwt(specialist)

    completed_session = _make_completed_session(specialist)

    mock_db = AsyncMock()
    count_mock = _scalar_one_result(1)
    sessions_mock = _scalars_all_result_simple([completed_session])
    cats_mock = _scalars_all_result_simple([])
    mock_db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none_result(specialist),  # get_current_user
        count_mock,
        sessions_mock,
        cats_mock,
    ])

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.get(
            '/api/v1/sessions',
            cookies={'access_token': token},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body['total'] == 1
    assert len(body['items']) == 1
    assert body['items'][0]['final_score'] == 75
    assert body['page'] == 1
    assert body['per_page'] == 20


@pytest.mark.asyncio
async def test_list_sessions_empty_for_no_sessions(async_client, mock_llm_provider):
    specialist = _make_user(role=UserRole.SPECIALIST)
    token = _make_jwt(specialist)

    mock_db = AsyncMock()
    count_mock = _scalar_one_result(0)
    sessions_mock = _scalars_all_result_simple([])
    mock_db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none_result(specialist),
        count_mock,
        sessions_mock,
    ])

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.get(
            '/api/v1/sessions',
            cookies={'access_token': token},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body['items'] == []
    assert body['total'] == 0
    assert body['page'] == 1
    assert body['per_page'] == 20
    assert body['pages'] == 1


@pytest.mark.asyncio
async def test_list_sessions_forbidden_for_cm_and_hr(async_client, mock_llm_provider):
    for role in (UserRole.CM, UserRole.HR):
        user = _make_user(role=role)
        token = _make_jwt(user)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

        async def override():
            yield mock_db

        app.dependency_overrides[get_db_session] = override

        try:
            resp = await async_client.get(
                '/api/v1/sessions',
                cookies={'access_token': token},
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

        assert resp.status_code == 403, f"Expected 403 for role {role}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_list_sessions_isolates_specialist_data(async_client, mock_llm_provider):
    specialist_a = _make_user(role=UserRole.SPECIALIST)
    specialist_b = _make_user(role=UserRole.SPECIALIST)
    token_a = _make_jwt(specialist_a)

    session_a = _make_completed_session(specialist_a)
    session_b = _make_completed_session(specialist_b)
    _ = session_b  # created but should NOT appear in specialist_a's results

    mock_db = AsyncMock()
    count_mock = _scalar_one_result(1)
    sessions_mock = _scalars_all_result_simple([session_a])
    cats_mock = _scalars_all_result_simple([])
    mock_db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none_result(specialist_a),
        count_mock,
        sessions_mock,
        cats_mock,
    ])

    async def override():
        yield mock_db

    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.get(
            '/api/v1/sessions',
            cookies={'access_token': token_a},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body['total'] == 1
    assert len(body['items']) == 1
    assert body['items'][0]['id'] == str(session_a.id)
