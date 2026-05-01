import logging
import time

import anthropic

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError
from app.providers.base import CategoryDraft, MatrixGenerationContext, SubItemDraft

logger = logging.getLogger(__name__)

_MATRIX_TOOL = {
    "name": "return_competency_matrix",
    "description": "Return the generated competency matrix as structured data",
    "input_schema": {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "sub_items": {
                            "type": "array",
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


class ClaudeProvider:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate_initial_matrix(
        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]:
        """
        Returns (categories, latency_ms, tokens_used).
        Raises LLMUnavailableError on any upstream failure.
        """
        from app.services.prompt_builder import build_matrix_generation_prompt

        prompt = build_matrix_generation_prompt(level=context.level, domain=context.domain)
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model="claude-opus-4-7",
                max_tokens=4096,
                tools=[_MATRIX_TOOL],
                tool_choice={"type": "tool", "name": "return_competency_matrix"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("Claude API failure during matrix generation: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            raise LLMUnavailableError("Claude returned no tool_use block for matrix generation")

        raw = tool_block.input
        categories: list[CategoryDraft] = []
        for cat in raw.get("categories", []):
            sub_items = [
                SubItemDraft(name=s["name"], description=s["description"])
                for s in cat.get("sub_items", [])
            ]
            categories.append(
                CategoryDraft(
                    name=cat["name"],
                    description=cat["description"],
                    sub_items=sub_items,
                )
            )
        return categories, latency_ms, tokens_used

    async def generate_questions(self, context) -> list:
        raise NotImplementedError("Implemented in Story 4.1")

    async def evaluate_responses(self, context) -> object:
        raise NotImplementedError("Implemented in Story 4.3")

    async def propose_matrix_updates(self, context) -> list:
        raise NotImplementedError("Implemented in Story 7.1")
