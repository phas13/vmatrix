from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass
class SubItemDraft:
    name: str
    description: str


@dataclass
class CategoryDraft:
    name: str
    description: str
    sub_items: list[SubItemDraft]


@dataclass
class MatrixGenerationContext:
    specialist_id: UUID
    level: str
    domain: str


class LLMProvider(Protocol):
    async def generate_initial_matrix(
        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]: ...

    # Implemented in Epic 4 (Story 4.1)
    async def generate_questions(self, context) -> list: ...
    async def evaluate_responses(self, context) -> object: ...

    # Implemented in Epic 7 (Story 7.1)
    async def propose_matrix_updates(self, context) -> list: ...
