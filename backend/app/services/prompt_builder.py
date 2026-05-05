from app.providers.base import QuestionGenerationContext, ResponseEvaluationContext


def build_matrix_generation_prompt(level: str, domain: str) -> str:
    level_guidance = {
        "junior": "foundational concepts, basic operational tasks, introductory tooling",
        "middle": "intermediate practices, hands-on project experience, common design patterns",
        "senior": "advanced architecture, system design at scale, mentorship, and org-wide impact",
    }.get(level.lower(), "intermediate practices")

    return (
        f"Generate a competency matrix for a {level.upper()} {domain} specialist.\n\n"
        f"The matrix should cover {level_guidance}.\n\n"
        f"Requirements:\n"
        f"- Return 5 to 8 distinct competency categories relevant to {domain}\n"
        f"- Each category must have 5 to 10 sub-items\n"
        f"- Sub-items should be concrete, assessable skills (not vague goals)\n"
        f"- Descriptions should be 1–2 sentences explaining what mastery looks like at the {level} level\n"
        f"- Do not include soft skills or generic professional skills — focus on {domain}-specific technical competencies\n"
        f"- Use the return_competency_matrix tool to return structured data"
    )


def build_question_generation_prompt(context: QuestionGenerationContext) -> str:
    sub_items_text = "\n".join(
        f"- {si.name}: {si.description}" for si in context.sub_items
    )
    return (
        f"Generate {context.num_questions} assessment questions for a {context.level.upper()} "
        f"{context.category_name} specialist.\n\n"
        f"Category: {context.category_name}\n"
        f"Description: {context.category_description}\n\n"
        f"Competency sub-items covered:\n{sub_items_text}\n\n"
        f"Requirements:\n"
        f"- Mix theoretical questions (understanding concepts) and practical questions (applying skills)\n"
        f"- Questions must be specific to the sub-items listed above\n"
        f"- Each question should be answerable in 2-5 sentences\n"
        f"- Difficulty appropriate for {context.level} level\n"
        f"- Use the return_assessment_questions tool to return structured data"
    )


def build_response_evaluation_prompt(context: ResponseEvaluationContext) -> str:
    qa_text = "\n\n".join(
        f"Q{entry.order + 1} [{entry.question_type}]: {entry.question_text}\n"
        f"Answer: {entry.response_text}"
        for entry in context.qa_entries
    )
    return (
        f"Evaluate the following {context.level.upper()} {context.category_name} assessment.\n\n"
        f"{qa_text}\n\n"
        f"Requirements:\n"
        f"- Score from 0 to 100 reflecting competency for {context.level} level\n"
        f"- Identify specific strengths shown in the answers\n"
        f"- Identify specific areas for growth\n"
        f"- Provide per-question commentary (reference the question by its order number)\n"
        f"- Base evaluation only on the answers provided — no assumptions about unstated knowledge\n"
        f"- Use the return_evaluation_result tool to return structured data"
    )
