"""
LLM Utility Modules

Shared utilities used across multiple providers.

Components:
    - extraction: Translation extraction from LLM responses
    - context_detection: Model context size detection
    - language: Language name to ISO code mapping
    - logging: Unified LLM logging with TTY color detection
"""

from .context_detection import ContextDetector
from .language import language_to_code, LANG_MAP
from .logging import LLMLogger

__all__ = ['ContextDetector', 'language_to_code', 'LANG_MAP', 'LLMLogger']
