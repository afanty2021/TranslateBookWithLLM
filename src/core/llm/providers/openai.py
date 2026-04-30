"""
OpenAI-compatible provider implementation.

This module provides the OpenAICompatibleProvider class for interacting with
OpenAI API and compatible endpoints (llama.cpp, LM Studio, vLLM, OpenAI, etc.).
"""

from typing import Optional, Callable
import asyncio
import json
import httpx

from ..base import LLMProvider, LLMResponse
from ..exceptions import ContextOverflowError, RateLimitError
from ..utils.context_detection import ContextDetector
from ..utils.logging import LLMLogger

from src.config import (
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS
)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with llama.cpp, LM Studio, vLLM, OpenAI, etc.)"""

    def __init__(self, api_endpoint: str, model: str, api_key: Optional[str] = None,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_endpoint = self._normalize_endpoint(api_endpoint)
        self.api_key = api_key
        self.context_window = context_window
        self.log_callback = log_callback
        self._llm_logger = LLMLogger("OpenAI-compatible", log_callback=log_callback)
        self._detected_context_size: Optional[int] = None
        self._context_detector = ContextDetector()

    def _is_official_openai_endpoint(self) -> bool:
        """Check if the endpoint is the official OpenAI API."""
        return "api.openai.com" in self.api_endpoint

    def _is_local_endpoint(self) -> bool:
        """Check if the endpoint is a local server (llama.cpp, vLLM, LM Studio, etc.)."""
        return "localhost" in self.api_endpoint or "127.0.0.1" in self.api_endpoint

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """
        Normalize API endpoint URL for OpenAI-compatible APIs.
        
        Automatically adds '/chat/completions' if the URL ends with '/v1' or '/v1/'
        but not with the full path. This handles common user mistakes like:
        - http://localhost:11434/v1 -> http://localhost:11434/v1/chat/completions
        - https://api.example.com/v1/ -> https://api.example.com/v1/chat/completions
        
        Args:
            endpoint: Raw endpoint URL provided by user
            
        Returns:
            Normalized endpoint URL with complete path
        """
        if not endpoint:
            return endpoint
        
        # Remove trailing slash for consistent processing
        endpoint = endpoint.rstrip('/')
        
        # If already ends with /v1/chat/completions, keep as-is
        if endpoint.endswith('/v1/chat/completions'):
            return endpoint
        
        # If ends with /v1, append /chat/completions
        if endpoint.endswith('/v1'):
            return endpoint + '/chat/completions'
        
        # Otherwise return as-is (user provided custom path)
        return endpoint

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using an OpenAI compatible API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build messages array with optional system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        # Only add thinking-disable params for local servers (llama.cpp, vLLM, LM Studio)
        # Skip for official OpenAI API and cloud providers (NVIDIA NIM, etc.)
        if not self._is_official_openai_endpoint() and self._is_local_endpoint():
            payload["thinking"] = False
            payload["enable_thinking"] = False
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()

                response_json = response.json()
                response_text = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Extract token usage if available
                usage = response_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=self.context_window,
                    was_truncated=False  # OpenAI API doesn't provide truncation info
                )

            except httpx.TimeoutException as e:
                self._llm_logger.timeout(attempt, MAX_TRANSLATION_ATTEMPTS, self.api_endpoint)

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    self._llm_logger.retry_hint()
                    await asyncio.sleep(2)
                    continue

                # All retry attempts exhausted
                self._llm_logger.all_retries_exhausted()

                return None
            except httpx.HTTPStatusError as e:
                error_message = str(e)
                error_body = ""
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    error_body = e.response.text[:500]
                    try:
                        # Try to parse JSON error for better messages
                        error_json = e.response.json()
                        if "error" in error_json:
                            if isinstance(error_json["error"], dict):
                                error_message = error_json["error"].get("message", str(e))
                            else:
                                error_message = str(error_json.get("error", e))
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).debug(f"Suppressed error: {e}")
                        error_message = f"{e} - {error_body}"

                # Handle rate limiting (429)
                if self._is_rate_limited(e.response.status_code):
                    wait_time = self._get_retry_wait(attempt, dict(e.response.headers))
                    self._llm_logger.rate_limit(attempt, MAX_TRANSLATION_ATTEMPTS, wait_time)
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    raise RateLimitError(
                        f"Rate limit exceeded after {MAX_TRANSLATION_ATTEMPTS} attempts",
                        retry_after=wait_time,
                        provider="openai-compatible"
                    )

                # Detect context overflow errors
                if self._is_context_overflow(error_message):
                    self._llm_logger.error(
                        f"Context size exceeded!\n"
                        f"   Prompt is too large for model's context window\n"
                        f"   Current context window: {self.context_window} tokens\n"
                        f"   Error: {error_message}\n"
                        f"   Solutions:\n"
                        f"   1. Reduce max_tokens_per_chunk (current chunk may be too large)\n"
                        f"   2. Increase context size in server configuration\n"
                        f"   3. Use a model with larger context window\n"
                        f"   4. For llama.cpp: increase -c/--ctx-size parameter"
                    )
                    raise ContextOverflowError(error_message)

                # Handle other HTTP errors with detailed information
                status_code = e.response.status_code if e.response else 'unknown'
                self._llm_logger.http_error(attempt, MAX_TRANSLATION_ATTEMPTS, status_code, error_message, self.api_endpoint)
                if error_body:
                    self._llm_logger.warning(f"   Response: {error_body[:200]}...")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    self._llm_logger.retry_hint()
                    await asyncio.sleep(2)
                    continue

                # All retries exhausted
                self._llm_logger.all_retries_exhausted()

                return None
            except json.JSONDecodeError as e:
                self._llm_logger.warning(
                    f"Invalid JSON response from LLM (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS})\n"
                    f"   Endpoint: {self.api_endpoint}\n"
                    f"   Model: {self.model}\n"
                    f"   Error: {str(e)}\n"
                    f"   This may indicate:\n"
                    f"   - Server returned malformed response\n"
                    f"   - llama.cpp server crashed mid-response\n"
                    f"   - API endpoint incompatibility\n"
                    f"   - Server configuration issues"
                )

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    self._llm_logger.retry_hint()
                    await asyncio.sleep(2)
                    continue

                self._llm_logger.all_retries_exhausted()

                return None
            except Exception as e:
                self._llm_logger.warning(
                    f"Unexpected error during LLM request (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS})\n"
                    f"   Endpoint: {self.api_endpoint}\n"
                    f"   Model: {self.model}\n"
                    f"   Error type: {type(e).__name__}\n"
                    f"   Error: {str(e)}"
                )

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    self._llm_logger.retry_hint()
                    await asyncio.sleep(2)
                    continue

                self._llm_logger.all_retries_exhausted()

                return None

        return None

    async def get_model_context_size(self) -> int:
        """Query server to get model's context size using ContextDetector."""
        if self._detected_context_size:
            return self._detected_context_size

        client = await self._get_client()
        ctx = await self._context_detector.detect(
            client=client,
            model=self.model,
            endpoint=self.api_endpoint,
            api_key=self.api_key,
            log_callback=self.log_callback
        )

        self._detected_context_size = ctx
        return ctx
