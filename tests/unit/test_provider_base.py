import os
import sys

import pytest

# Ensure project root is on sys.path so `src` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.llm.base import LLMProvider


class _MinimalProvider(LLMProvider):
    """Smallest concrete subclass so we can test base-class helpers."""

    async def generate(self, prompt, timeout=30, system_prompt=None):
        return None


class TestProviderBaseHelpers:
    def _make_provider(self):
        return _MinimalProvider(model="test")

    # -- _is_context_overflow ------------------------------------------

    def test_is_context_overflow_true(self):
        p = self._make_provider()
        assert p._is_context_overflow("context_length_exceeded")
        assert p._is_context_overflow("too many tokens in input")
        assert p._is_context_overflow("Maximum Context Length Exceeded")

    def test_is_context_overflow_false(self):
        p = self._make_provider()
        assert not p._is_context_overflow("network error")
        assert not p._is_context_overflow("invalid api key")

    # -- _is_rate_limited ----------------------------------------------

    def test_is_rate_limited(self):
        p = self._make_provider()
        assert p._is_rate_limited(429)
        assert not p._is_rate_limited(200)
        assert not p._is_rate_limited(500)

    # -- _get_retry_wait -----------------------------------------------

    def test_get_retry_wait_with_header(self):
        p = self._make_provider()
        assert p._get_retry_wait(0, {"Retry-After": "30"}) == 30

    def test_get_retry_wait_default(self):
        p = self._make_provider()
        # default_retry_wait: 2^(attempt+2)
        assert p._get_retry_wait(0) == 4
        assert p._get_retry_wait(1) == 8

    def test_get_retry_wait_invalid_header(self):
        p = self._make_provider()
        assert p._get_retry_wait(0, {"Retry-After": "abc"}) == 4
