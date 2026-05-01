from app.core.config import settings
from app.providers.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "claude":
        from app.providers.claude import ClaudeProvider
        return ClaudeProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
