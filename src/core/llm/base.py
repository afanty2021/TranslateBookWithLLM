"""
Base classes and data structures for LLM providers.

This module defines the abstract base class that all LLM providers must implement,
as well as common data structures like LLMResponse.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import httpx

from src.config import TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT, REQUEST_TIMEOUT
from src.utils.telemetry import get_telemetry_headers
from src.core.llm.utils.extraction import TranslationExtractor
from src.core.llm.utils.logging import LLMLogger


@dataclass
class LLMResponse:
    """Response from LLM with token usage information"""
    content: str
    prompt_tokens: int = 0  # Number of tokens in the prompt
    completion_tokens: int = 0  # Number of tokens in the response
    context_used: int = 0  # Total context used (prompt + completion)
    context_limit: int = 0  # Context limit that was set for this request
    was_truncated: bool = False  # True if response was truncated due to context limit


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, model: str):
        """
        Initialize the LLM provider.

        Args:
            model: Model name/identifier
        """
        self.model = model
        self._extractor = TranslationExtractor(TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT)
        self._llm_logger = LLMLogger(model)
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a persistent HTTP client with connection pooling"""
        if self._client is None:
            # Add client identification headers to all requests
            telemetry_headers = get_telemetry_headers()
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                timeout=httpx.Timeout(REQUEST_TIMEOUT),
                headers=telemetry_headers
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional["LLMResponse"]:
        """
        Generate text from prompt.

        Args:
            prompt: The user prompt (content to process)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse object with content and token usage info, or None if failed
        """
        pass

    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response using configured tags with strict validation.

        Returns the content between TRANSLATE_TAG_IN and TRANSLATE_TAG_OUT.
        Prefers responses where tags are at exact boundaries for better reliability.

        NOTE: This method completely ignores content within <think></think> tags,
        as these are used by certain LLMs for internal reasoning and should not
        be searched for translation tags.

        Args:
            response: Raw text response from the LLM

        Returns:
            Extracted translation text, or None if extraction fails
        """
        return self._extractor.extract(response)

    # ------------------------------------------------------------------
    # Reusable error handling helpers
    # ------------------------------------------------------------------

    def _is_context_overflow(self, error_message: str) -> bool:
        """Check whether *error_message* indicates a context overflow.

        Uses the shared ``CONTEXT_OVERFLOW_KEYWORDS`` list from
        :pymod:`src.core.llm.constants`.  Matching is case-insensitive.
        """
        from .constants import CONTEXT_OVERFLOW_KEYWORDS
        msg_lower = error_message.lower()
        return any(kw in msg_lower for kw in CONTEXT_OVERFLOW_KEYWORDS)

    def _is_rate_limited(self, status_code: int) -> bool:
        """Return ``True`` when *status_code* is an HTTP 429."""
        return status_code == 429

    def _get_retry_wait(self, attempt: int, response_headers: dict = None) -> int:
        """Return the number of seconds to wait before retrying.

        If *response_headers* contains a ``Retry-After`` header its integer
        value is used directly.  Otherwise the exponential back-off provided by
        :func:`src.core.llm.constants.default_retry_wait` is used.
        """
        from .constants import default_retry_wait
        if response_headers:
            retry_after = response_headers.get("Retry-After")
            if retry_after:
                try:
                    return int(retry_after)
                except (ValueError, TypeError):
                    pass
        return default_retry_wait(attempt)

    # ------------------------------------------------------------------

    async def translate_text(self, prompt: str) -> Optional[str]:
        """Complete translation workflow: request + extraction"""
        response = await self.generate(prompt)
        if response:
            return self.extract_translation(response.content)
        return None
