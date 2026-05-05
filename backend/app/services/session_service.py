import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProblemHTTPException
from app.models.user import User
from app.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_SESSION = 10


def _llm_unavailable(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=503,
        detail={
            "type": "https://vmatrix.app/errors/llm-unavailable",
            "title": "LLM unavailable",
            "status": 503,
            "detail": "Assessment service is temporarily unavailable. Please try again.",
            "instance": instance,
        },
    )


def _session_not_found(instance: str) -> ProblemHTTPException:
    return ProblemHTTPException(
        status_code=404,
        detail={
            "type": "https://vmatrix.app/errors/session-not-found",
            "title": "Session not found",
            "status": 404,
            "detail": "Assessment session not found",
            "instance": instance,
        },
    )


async def create_session(
    specialist_id: UUID,
    category_id: UUID,
    db: AsyncSession,
    *,
    current_user: User,
    instance: str,
) -> "AssessmentSession":  # noqa: F821
    """
    Story 4.1: skeleton with LLM pre-flight check.
    Story 4.2: adds category validation, session creation, question generation.
    """
    # LLM pre-flight — raise 503 before touching DB if provider unreachable
    get_llm_provider()
    # Actual validation + session creation added in Story 4.2
    raise NotImplementedError("Session creation logic added in Story 4.2")
