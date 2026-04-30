"""
LLM-specific exceptions.

This module defines custom exceptions used in the LLM provider system.
Shared exceptions (ContextOverflowError, RepetitionLoopError) are imported
from the adapters module which owns the authoritative exception hierarchy.
"""

# Import unified exceptions from adapters (authoritative source)
from src.core.adapters.exceptions import ContextOverflowError, RepetitionLoopError  # noqa: F401


class RateLimitError(Exception):
    """
    Raised when the API returns HTTP 429 (Too Many Requests) and all retry
    attempts with backoff have been exhausted.

    This signals the translation pipeline to auto-pause and save a checkpoint
    so the user can resume later.

    Attributes:
        retry_after: Suggested wait time in seconds (from Retry-After header),
                     or None if not provided by the API.
        provider: Name of the LLM provider that was rate-limited.
    """

    def __init__(self, message: str, retry_after: int = None, provider: str = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.provider = provider
