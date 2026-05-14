from dataclasses import dataclass
from datetime import date
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


# Story 4.1 — Assessment contexts

@dataclass
class SubItemInfo:
    name: str
    description: str


@dataclass
class QuestionGenerationContext:
    specialist_id: UUID
    category_name: str
    category_description: str
    sub_items: list[SubItemInfo]
    level: str          # "junior" | "middle" | "senior"
    num_questions: int  # target count (e.g. 8)


@dataclass
class AssessmentQuestionDraft:
    text: str
    question_type: str  # "theoretical" | "practical"
    order: int


@dataclass
class QuestionFeedback:
    question_order: int
    commentary: str     # AI comment on this specific answer


@dataclass
class QAEntry:
    question_text: str
    question_type: str
    response_text: str | None  # plain text (decrypted before passing to LLM)
    order: int


@dataclass
class ResponseEvaluationContext:
    specialist_id: UUID
    category_name: str
    level: str
    qa_entries: list[QAEntry]


@dataclass
class SessionEvaluationResult:
    score: int                          # 0-100
    strengths: str
    areas_for_growth: str
    per_question_feedback: list[QuestionFeedback]


@dataclass
class SourceContent:
    name: str
    url: str
    content: str


@dataclass
class CurrentSubItem:
    name: str
    description: str


@dataclass
class CurrentCategory:
    name: str
    sub_items: list[CurrentSubItem]


@dataclass
class MatrixMonitoringContext:
    source: SourceContent
    current_categories: list[CurrentCategory]


@dataclass
class MatrixUpdateProposalDraft:
    proposed_change: str
    source_name: str
    source_url: str
    source_date: date | None
    matrix_id: UUID | None = None


class LLMProvider(Protocol):
    async def health_check(self) -> None:
        """Verifies connectivity to the LLM provider.
        Raises LLMUnavailableError if unreachable.
        """
        ...

    async def generate_initial_matrix(
        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]: ...

    async def generate_questions(
        self, context: QuestionGenerationContext
    ) -> tuple[list[AssessmentQuestionDraft], int, int]:
        """Returns (questions, latency_ms, tokens_used)."""
        ...

    async def evaluate_responses(
        self, context: ResponseEvaluationContext
    ) -> tuple[SessionEvaluationResult, int, int]:
        """Returns (result, latency_ms, tokens_used)."""
        ...

    async def propose_matrix_updates(
        self, context: MatrixMonitoringContext
    ) -> list[MatrixUpdateProposalDraft]: ...
