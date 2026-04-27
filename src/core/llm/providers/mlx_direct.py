"""
Direct MLX provider that bypasses omlx API and uses mlx-lm directly.

This provider is needed for TranslateGemma which requires special chat template
format that omlx doesn't support properly.
"""

from typing import Optional, Callable
import asyncio
import subprocess
import json
import httpx

from ..base import LLMProvider, LLMResponse
from ..exceptions import ContextOverflowError, RateLimitError

from src.config import (
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS
)


class MLXDirectProvider(LLMProvider):
    """
    Direct MLX provider using mlx-lm CLI or Python API.

    This provider bypasses omlx's OpenAI-compatible API and directly uses
    mlx-lm for models with special chat templates like TranslateGemma.
    """

    def __init__(self, model: str, api_key: Optional[str] = None,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_key = api_key  # Not used for direct MLX
        self.context_window = context_window
        self.log_callback = log_callback
        self._is_translategemma = "translategemma" in model.lower()

    def _build_translategemma_prompt(self, source_lang: str, target_lang: str, text: str) -> str:
        """Build prompt for TranslateGemma model."""
        # Get ISO codes
        source_code = self._language_to_code(source_lang)
        target_code = self._language_to_code(target_lang)

        # TranslateGemma chat template format
        # We need to manually construct the prompt since we're calling mlx-lm directly
        return f"<start_of_turn>user\nYou are a professional {source_lang} ({source_code}) to {target_lang} ({target_code}) translator. Your goal is to accurately convey the meaning and nuances of the original {source_lang} text while adhering to {target_lang} grammar, vocabulary, and cultural sensitivities.\n\nProduce only the {target_lang} translation, without any additional explanations or commentary. Please translate the following {source_lang} text into {target_lang}:\n\n\n{text}<end_of_turn>\n<start_of_turn>model\n"

    def _language_to_code(self, lang: str) -> str:
        """Convert language name to ISO code."""
        lang_map = {
            "english": "en",
            "chinese": "zh",
            "french": "fr",
            "german": "de",
            "spanish": "es",
            "japanese": "ja",
            "korean": "ko",
            "russian": "ru",
            "italian": "it",
            "portuguese": "pt",
            "arabic": "ar",
            "hindi": "hi",
        }
        lang_lower = lang.lower()
        return lang_map.get(lang_lower, lang_lower)

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using MLX directly.

        For TranslateGemma, parses the special <<<source>>>...<<<target>>>...<<<text>>>... format
        and constructs the appropriate prompt.
        """
        if self._is_translategemma:
            return await self._generate_translategemma(prompt, timeout)
        else:
            return await self._generate_standard(prompt, system_prompt, timeout)

    async def _generate_translategemma(self, prompt: str, timeout: int) -> Optional[LLMResponse]:
        """Generate using TranslateGemma format via omlx API with correct content format."""
        # Parse language codes from prompt
        source_lang = "en"
        target_lang = "zh"
        text = prompt

        if "<<<source>>>" in prompt and "<<<target>>>" in prompt and "<<<text>>>" in prompt:
            parts = prompt.split("<<<")
            for part in parts:
                if part.startswith("source>>>"):
                    source_lang = part.split(">>>")[1].strip()
                elif part.startswith("target>>>"):
                    target_lang = part.split(">>>")[1].strip()
                elif part.startswith("text>>>"):
                    text = part.split(">>>", 1)[1].strip()

        # Build the prompt manually for TranslateGemma
        full_prompt = self._build_translategemma_prompt(source_lang, target_lang, text)

        # Use mlx-lm generate command
        try:
            cmd = [
                "mlx_lm.generate",
                "--model", self.model,
                "--prompt", full_prompt,
                "--max-tokens", "2048",
                "--temp", "0.0"
            ]

            if self.log_callback:
                self.log_callback("mlx_debug", f"Running: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    if self.log_callback:
                        self.log_callback("mlx_error", f"mlx_lm.generate failed: {error_msg}")
                    return None

                result = stdout.decode('utf-8', errors='ignore').strip()

                # Remove the prompt from the result to get only the translation
                if result.startswith(full_prompt):
                    result = result[len(full_prompt):].strip()

                return LLMResponse(
                    content=result,
                    prompt_tokens=0,  # mlx_lm.generate doesn't return token counts
                    completion_tokens=0,
                    context_used=0,
                    context_limit=self.context_window,
                    was_truncated=False
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                if self.log_callback:
                    self.log_callback("mlx_timeout", f"mlx_lm.generate timeout after {timeout}s")
                return None

        except FileNotFoundError:
            if self.log_callback:
                self.log_callback("mlx_not_found", "mlx_lm command not found. Install with: pip install mlx-lm")
            return None
        except Exception as e:
            if self.log_callback:
                self.log_callback("mlx_error", f"mlx_lm.generate error: {e}")
            return None

    async def _generate_standard(self, prompt: str, system_prompt: Optional[str], timeout: int) -> Optional[LLMResponse]:
        """Generate using standard format (fallback)."""
        # Build prompt with system message if provided
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        try:
            cmd = [
                "mlx_lm.generate",
                "--model", self.model,
                "--prompt", full_prompt,
                "--max-tokens", "2048",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                if process.returncode != 0:
                    return None

                result = stdout.decode('utf-8', errors='ignore').strip()

                if result.startswith(full_prompt):
                    result = result[len(full_prompt):].strip()

                return LLMResponse(
                    content=result,
                    prompt_tokens=0,
                    completion_tokens=0,
                    context_used=0,
                    context_limit=self.context_window,
                    was_truncated=False
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return None

        except Exception as e:
            if self.log_callback:
                self.log_callback("mlx_error", f"mlx_lm.generate error: {e}")
            return None

    async def get_model_context_size(self) -> int:
        """Return configured context size."""
        return self.context_window
