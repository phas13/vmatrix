from app.providers.base import (
    AssessmentQuestionDraft,
    CategoryDraft,
    MatrixGenerationContext,
    QuestionGenerationContext,
    ResponseEvaluationContext,
    SessionEvaluationResult,
)


class GeminiProvider:
    async def generate_initial_matrix(
        self, context: MatrixGenerationContext
    ) -> tuple[list[CategoryDraft], int, int]:
        raise NotImplementedError("Gemini matrix generation not yet implemented")

    async def generate_questions(
        self, context: QuestionGenerationContext
    ) -> tuple[list[AssessmentQuestionDraft], int, int]:
        raise NotImplementedError("Gemini question generation not yet implemented")

    async def evaluate_responses(
        self, context: ResponseEvaluationContext
    ) -> tuple[SessionEvaluationResult, int, int]:
        raise NotImplementedError("Gemini response evaluation not yet implemented")

    async def propose_matrix_updates(self, context) -> list:
        raise NotImplementedError("Gemini matrix monitoring not yet implemented")
