"""
LLM Provider unified logging utility.

Provides a consistent logging interface for all LLM providers with
automatic TTY detection for color output.
"""

import sys
import logging
from typing import Optional, Callable


class LLMLogger:
    """Unified LLM logging utility with automatic TTY color detection.

    Routes log messages through either a log_callback (for UI integration)
    or Python's standard logging module as a fallback.
    """

    def __init__(self, provider_name: str, log_callback: Optional[Callable] = None):
        """
        Initialize the LLM logger.

        Args:
            provider_name: Name of the provider (used for logger naming and messages).
            log_callback: Optional callback for UI integration.  Signature: (level, message).
        """
        self.provider_name = provider_name
        self.log_callback = log_callback
        self._logger = logging.getLogger(f"llm.{provider_name}")
        self._is_tty = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()

    def _colorize(self, text: str, color_code: str) -> str:
        """Apply ANSI color only when stderr is a TTY."""
        if self._is_tty:
            return f"\033[{color_code}m{text}\033[0m"
        return text

    # ------------------------------------------------------------------
    # Core logging methods
    # ------------------------------------------------------------------

    def warning(self, msg: str):
        """Log a warning message (yellow)."""
        colored = self._colorize(f"⚠️ {msg}", "93")
        if self.log_callback:
            self.log_callback("llm_warning", colored)
        else:
            self._logger.warning(msg)

    def error(self, msg: str):
        """Log an error message (red)."""
        colored = self._colorize(f"❌ {msg}", "91")
        if self.log_callback:
            self.log_callback("llm_error", colored)
        else:
            self._logger.error(msg)

    def info(self, msg: str):
        """Log an info message (green)."""
        colored = self._colorize(msg, "92")
        if self.log_callback:
            self.log_callback("llm_info", colored)
        else:
            self._logger.info(msg)

    # ------------------------------------------------------------------
    # Convenience methods for common LLM provider patterns
    # ------------------------------------------------------------------

    def rate_limit(self, attempt: int, max_attempts: int, wait_time: int):
        """Log a rate-limit warning with attempt counter."""
        self.warning(
            f"{self.provider_name} rate limited "
            f"(attempt {attempt + 1}/{max_attempts}), waiting {wait_time}s..."
        )

    def timeout(self, attempt: int, max_attempts: int, endpoint: str = ""):
        """Log a request-timeout warning."""
        parts = [
            f"{self.provider_name} request timeout "
            f"(attempt {attempt + 1}/{max_attempts})"
        ]
        if endpoint:
            parts.append(f"Endpoint: {endpoint}")
        self.warning("\n   ".join(parts))

    def all_retries_exhausted(self, provider_name: Optional[str] = None):
        """Log that all retry attempts have been exhausted."""
        name = provider_name or self.provider_name
        self.error(
            f"All retry attempts exhausted for {name}. Translation failed."
        )

    def http_error(self, attempt: int, max_attempts: int, status_code, error_message: str, endpoint: str = ""):
        """Log an HTTP error with attempt counter."""
        parts = [
            f"HTTP error from {self.provider_name} "
            f"(attempt {attempt + 1}/{max_attempts})"
        ]
        if status_code:
            parts.append(f"Status: {status_code}")
        if endpoint:
            parts.append(f"Endpoint: {endpoint}")
        parts.append(f"Error: {error_message}")
        self.warning("\n   ".join(parts))

    def retry_hint(self):
        """Log a retry hint message."""
        if self.log_callback:
            self.log_callback("llm_retry", "   Retrying in 2 seconds...")
