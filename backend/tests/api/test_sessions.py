from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.models.session import AssessmentSession, SessionStatus
from app.models.user import SpecialistLevel, User, UserRole
from app.providers.base import AssessmentQuestionDraft, QuestionFeedback, SessionEvaluationResult


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
