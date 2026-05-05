from app.providers.base import (
    AssessmentQuestionDraft,
    CategoryDraft,
    MatrixGenerationContext,
    QuestionGenerationContext,
    ResponseEvaluationContext,
    SessionEvaluationResult,
)


class OpenAIProvider:
    async def generate_initial_matrix(
        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]:
        raise NotImplementedError("OpenAI matrix generation not yet implemented")

    async def generate_questions(
        self, context: QuestionGenerationContext
    ) -> tuple[list[AssessmentQuestionDraft], int, int]:
        raise NotImplementedError("OpenAI question generation not yet implemented")

    async def evaluate_responses(
        self, context: ResponseEvaluationContext
    ) -> tuple[SessionEvaluationResult, int, int]:
        raise NotImplementedError("OpenAI response evaluation not yet implemented")

    async def propose_matrix_updates(self, context) -> list:
        raise NotImplementedError("OpenAI matrix monitoring not yet implemented")
