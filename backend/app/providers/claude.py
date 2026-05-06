import logging
import time

import anthropic

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError
from app.providers.base import (
    AssessmentQuestionDraft,
    CategoryDraft,
    MatrixGenerationContext,
    QuestionFeedback,
    QuestionGenerationContext,
    ResponseEvaluationContext,
    SessionEvaluationResult,
    SubItemDraft,
)

logger = logging.getLogger(__name__)

_MATRIX_TOOL = {
    "name": "return_competency_matrix",
    "description": "Return the generated competency matrix as structured data",
    "input_schema": {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "sub_items": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["name", "description"],
                            },
                        },
                    },
                    "required": ["name", "description", "sub_items"],
                },
            }
        },
        "required": ["categories"],
    },
}

_QUESTIONS_TOOL = {
    "name": "return_assessment_questions",
    "description": "Return the generated assessment questions as structured data",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "question_type": {"type": "string", "enum": ["theoretical", "practical"]},
                    },
                    "required": ["text", "question_type"],
                },
            }
        },
        "required": ["questions"],
    },
}

_EVALUATION_TOOL = {
    "name": "return_evaluation_result",
    "description": "Return the evaluation result as structured data",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "strengths": {"type": "string"},
            "areas_for_growth": {"type": "string"},
            "per_question_feedback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_order": {"type": "integer"},
                        "commentary": {"type": "string"},
                    },
                    "required": ["question_order", "commentary"],
                },
            },
        },
        "required": ["score", "strengths", "areas_for_growth", "per_question_feedback"],
    },
}


class ClaudeProvider:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS
        )

    async def health_check(self) -> None:
        """Verifies connectivity to Anthropic API with a minimal token request."""
        try:
            # We use a very small max_tokens call to check if the API is responsive.
            # This detects both config issues and network/service outages.
            await self._client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "health check"}],
            )
        except Exception as exc:
            logger.error("Claude health check failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

    async def generate_initial_matrix(

        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]:
        """
        Returns (categories, latency_ms, tokens_used).
        Raises LLMUnavailableError on any upstream or parsing failure.
        """
        from app.services.prompt_builder import build_matrix_generation_prompt

        prompt = build_matrix_generation_prompt(level=context.level, domain=context.domain)
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=4096,
                tools=[_MATRIX_TOOL],
                tool_choice={"type": "tool", "name": "return_competency_matrix"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("Claude API failure during matrix generation: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            usage = getattr(response, "usage", None)
            tokens_used = (
                (getattr(usage, "input_tokens", 0) or 0)
                + (getattr(usage, "output_tokens", 0) or 0)
            )

            tool_block = next(
                (b for b in response.content if b.type == "tool_use"), None
            )
            if tool_block is None:
                raise LLMUnavailableError("Claude returned no tool_use block for matrix generation")

            raw = tool_block.input
            if not isinstance(raw, dict):
                raise LLMUnavailableError(
                    f"Claude tool_use input is not a dict: {type(raw).__name__}"
                )

            raw_categories = raw.get("categories")
            if not isinstance(raw_categories, list) or len(raw_categories) == 0:
                raise LLMUnavailableError(
                    "Claude returned no categories in matrix generation response"
                )

            categories: list[CategoryDraft] = []
            for cat in raw_categories:
                if not isinstance(cat, dict):
                    raise LLMUnavailableError("Claude returned a non-dict category entry")
                cat_name = cat.get("name")
                cat_description = cat.get("description")
                if not cat_name or not cat_description:
                    raise LLMUnavailableError(
                        "Claude returned a category with missing name or description"
                    )
                raw_sub_items = cat.get("sub_items") or []
                if not isinstance(raw_sub_items, list) or len(raw_sub_items) == 0:
                    raise LLMUnavailableError(
                        f"Claude returned empty sub_items for category {cat_name!r}"
                    )
                sub_items: list[SubItemDraft] = []
                for s in raw_sub_items:
                    if not isinstance(s, dict):
                        raise LLMUnavailableError("Claude returned a non-dict sub_item entry")
                    s_name = s.get("name")
                    s_description = s.get("description")
                    if not s_name or not s_description:
                        raise LLMUnavailableError(
                            "Claude returned a sub_item with missing name or description"
                        )
                    sub_items.append(SubItemDraft(name=s_name, description=s_description))
                categories.append(
                    CategoryDraft(
                        name=cat_name,
                        description=cat_description,
                        sub_items=sub_items,
                    )
                )
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.error("Claude response parsing failure: %s", exc)
            raise LLMUnavailableError(f"Malformed Claude response: {exc}") from exc

        return categories, latency_ms, tokens_used

    async def generate_questions(
        self, context: QuestionGenerationContext
    ) -> tuple[list[AssessmentQuestionDraft], int, int]:
        from app.services.prompt_builder import build_question_generation_prompt

        prompt = build_question_generation_prompt(context)
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=4096,
                tools=[_QUESTIONS_TOOL],
                tool_choice={"type": "tool", "name": "return_assessment_questions"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("Claude API failure during question generation: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        usage = getattr(response, "usage", None)
        tokens_used = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0)
        )

        try:
            tool_block = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_block is None:
                raise LLMUnavailableError("Claude returned no tool_use block for question generation")
            raw = tool_block.input
            raw_questions = raw.get("questions") or []
            if not isinstance(raw_questions, list) or len(raw_questions) == 0:
                raise LLMUnavailableError("Claude returned no questions")
            questions = [
                AssessmentQuestionDraft(
                    text=q["text"],
                    question_type=q["question_type"],
                    order=i,
                )
                for i, q in enumerate(raw_questions)
            ]
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.error("Claude response parsing failure (questions): %s", exc)
            raise LLMUnavailableError(f"Malformed Claude response: {exc}") from exc

        return questions, latency_ms, tokens_used

    async def evaluate_responses(
        self, context: ResponseEvaluationContext
    ) -> tuple[SessionEvaluationResult, int, int]:
        from app.services.prompt_builder import build_response_evaluation_prompt

        prompt = build_response_evaluation_prompt(context)
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=4096,
                tools=[_EVALUATION_TOOL],
                tool_choice={"type": "tool", "name": "return_evaluation_result"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("Claude API failure during response evaluation: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        usage = getattr(response, "usage", None)
        tokens_used = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0)
        )

        try:
            tool_block = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_block is None:
                raise LLMUnavailableError("Claude returned no tool_use block for evaluation")
            raw = tool_block.input
            feedbacks = [
                QuestionFeedback(
                    question_order=fb["question_order"],
                    commentary=fb["commentary"],
                )
                for fb in (raw.get("per_question_feedback") or [])
            ]
            result = SessionEvaluationResult(
                score=int(raw["score"]),
                strengths=raw["strengths"],
                areas_for_growth=raw["areas_for_growth"],
                per_question_feedback=feedbacks,
            )
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.error("Claude response parsing failure (evaluation): %s", exc)
            raise LLMUnavailableError(f"Malformed Claude response: {exc}") from exc

        return result, latency_ms, tokens_used

    async def propose_matrix_updates(self, context) -> list:
        raise NotImplementedError("Implemented in Story 7.1")
