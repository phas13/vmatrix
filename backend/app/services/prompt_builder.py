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
