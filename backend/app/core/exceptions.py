from fastapi import HTTPException


class ProblemHTTPException(HTTPException):
    pass


class LLMUnavailableError(Exception):
    """Raised by LLM provider implementations when the upstream API is unreachable or fails."""
    pass
