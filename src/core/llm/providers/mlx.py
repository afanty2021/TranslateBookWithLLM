"""
MLX provider implementation for Apple Silicon.

This module provides MLXProvider for interacting with MLX server (omlox)
which supports OpenAI-compatible API with special chat templates for models
like TranslateGemma.
"""

from typing import Optional, Callable
import asyncio
import httpx

from ..base import LLMProvider, LLMResponse
from ..exceptions import ContextOverflowError, RateLimitError

from src.config import (
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS
)


class MLXProvider(LLMProvider):
    """
    MLX provider for Apple Silicon local inference.

    Supports both standard OpenAI format and TranslateGemma special format.
    TranslateGemma requires content as an array with specific fields:
    - type: "text" or "image"
    - source_lang_code: ISO language code (e.g., "en", "zh")
    - target_lang_code: ISO language code
    - text: the text to translate (if type is "text")
    """

    def __init__(self, api_endpoint: str, model: str, api_key: Optional[str] = None,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_endpoint = self._normalize_endpoint(api_endpoint)
        self.api_key = api_key
        self.context_window = context_window
        self.log_callback = log_callback
        self._is_translategemma = "translategemma" in model.lower()
        self._is_qwen_thinking = any(k in model.lower() for k in ["qwen3", "qwen3.6", "qwq"])
        # MLX provider 使用自己的客户端，避免连接重用问题
        self._mlx_client = None

    async def _get_mlx_client(self) -> httpx.AsyncClient:
        """获取或创建 MLX 专用客户端"""
        if self._mlx_client is None:
            self._mlx_client = httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=2, max_connections=5),
                timeout=httpx.Timeout(600.0, connect=60.0)
            )
        return self._mlx_client

    async def close(self):
        """关闭 MLX 客户端"""
        if self._mlx_client:
            await self._mlx_client.aclose()
            self._mlx_client = None
        # 同时关闭基类客户端
        await super().close()

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """Normalize API endpoint URL."""
        if not endpoint:
            return endpoint
        endpoint = endpoint.rstrip('/')
        if endpoint.endswith('/v1/chat/completions'):
            return endpoint
        if endpoint.endswith('/v1'):
            return endpoint + '/chat/completions'
        return endpoint

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        """
        Build messages array for the API request.

        For TranslateGemma models, use special format with content array.
        For other models, use standard OpenAI format.
        """
        if self._is_translategemma:
            # TranslateGemma requires special format
            # Parse language codes from prompt if in format <<<source>>>xxx<<<target>>>yyy<<<text>>>zzz
            if "<<<source>>>" in prompt and "<<<target>>>" in prompt and "<<<text>>>" in prompt:
                parts = prompt.split("<<<")
                source_lang = "en"
                target_lang = "zh"
                text = prompt

                for i, part in enumerate(parts):
                    if part.startswith("source>>>"):
                        source_lang = part.split(">>>")[1].strip()
                    elif part.startswith("target>>>"):
                        target_lang = part.split(">>>")[1].strip()
                    elif part.startswith("text>>>"):
                        text = part.split(">>>", 1)[1].strip()

                # Convert language names to ISO codes if needed
                source_code = self._language_to_code(source_lang)
                target_code = self._language_to_code(target_lang)

                # Debug output
                if self.log_callback:
                    self.log_callback("mlx_debug", f"Building TranslateGemma request: source={source_lang}->{source_code}, target={target_lang}->{target_code}")

                return [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "source_lang_code": source_code,
                                "target_lang_code": target_code,
                                "text": text
                            }
                        ]
                    }
                ]
            else:
                # Strategy 2: Extract content from <SOURCE_TEXT>...</SOURCE_TEXT> tags (EPUB format)
                # Also detect language from system prompt or user prompt
                source_lang = "en"
                target_lang = "zh"
                text_to_translate = prompt

                # Check for <SOURCE_TEXT>...</SOURCE_TEXT> format
                if "<SOURCE_TEXT>" in prompt and "</SOURCE_TEXT>" in prompt:
                    start_idx = prompt.find("<SOURCE_TEXT>") + len("<SOURCE_TEXT>")
                    end_idx = prompt.find("</SOURCE_TEXT>")
                    if end_idx > start_idx:
                        text_to_translate = prompt[start_idx:end_idx].strip()

                        # Try to extract languages from the prompt content
                        prompt_lower = prompt.lower()

                        # Detect source language
                        for lang_name, lang_code in [
                            ("english", "en"), ("chinese", "zh"), ("french", "fr"),
                            ("german", "de"), ("spanish", "es"), ("japanese", "ja"),
                            ("korean", "ko"), ("russian", "ru"), ("italian", "it"),
                            ("portuguese", "pt"), ("arabic", "ar"), ("hindi", "hi")
                        ]:
                            # Check for patterns like "Translate English to Chinese" or "from English to Chinese"
                            if f"translate {lang_name} to" in prompt_lower or f"from {lang_name} to" in prompt_lower:
                                source_lang = lang_code
                                break

                        # Detect target language
                        for lang_name, lang_code in [
                            ("chinese", "zh"), ("english", "en"), ("french", "fr"),
                            ("german", "de"), ("spanish", "es"), ("japanese", "ja"),
                            ("korean", "ko"), ("russian", "ru"), ("italian", "it"),
                            ("portuguese", "pt"), ("arabic", "ar"), ("hindi", "hi")
                        ]:
                            # Check for patterns like "to Chinese" or "into Chinese"
                            if f"to {lang_name}" in prompt_lower or f"into {lang_name}" in prompt_lower:
                                target_lang = lang_code
                                break

                        # Debug output
                        if self.log_callback:
                            self.log_callback("mlx_debug", f"Extracted from <SOURCE_TEXT>: source={source_lang}, target={target_lang}, text_length={len(text_to_translate)}")

                # Convert language names to ISO codes
                source_code = self._language_to_code(source_lang)
                target_code = self._language_to_code(target_lang)

                return [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "source_lang_code": source_code,
                                "target_lang_code": target_code,
                                "text": text_to_translate
                            }
                        ]
                    }
                ]
        else:
            # Standard OpenAI format for non-TranslateGemma models
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            return messages

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

    def _strip_thinking(self, text: str) -> str:
        """去除 Qwen thinking 输出，保留翻译内容"""
        import re
        # Try to find translation after thinking block
        patterns = [
            r'^Thinking Process:.*?\n\n(.*)',
            r'^<think()>.*?</think()>\s*(.*)',
        ]
        for pat in patterns:
            m = re.match(pat, text, re.DOTALL)
            if m:
                return m.group(1).strip()
        return ""

    def _clean_model_artifacts(self, text: str) -> str:
        """清理模型生成的多余标签和产物"""
        if not text:
            return text

        import re
        # 移除重复的 <end_of_turn> 标签
        text = re.sub(r'(<end_of_turn>)+', '', text)
        # 移除单个 <end_of_turn> 标签
        text = re.sub(r'<end_of_turn>', '', text)
        # 移除其他常见模型产物
        text = re.sub(r'<eos>', '', text)
        text = re.sub(r'<\|im_end\|>', '', text)
        # 清理 Qwen thinking 输出 (Thinking Process:\n...\n)
        text = re.sub(r'^Thinking Process:.*?(?=\n[^\s*]|\Z)', '', text, flags=re.DOTALL)

        return text.strip()

    def _detect_repetition(self, text: str) -> tuple[bool, str]:
        """
        检测 LLM 重复循环并截断。

        调整后的阈值：只检测真正异常的重复循环，避免误判正常翻译。

        Returns:
            (has_repetition, truncated_text)
        """
        if not text or len(text) < 100:
            return False, text

        # 用滑动窗口检测重复短语
        # 调整：更大的窗口（30-80字符），需要重复 5+ 次，且间距很小
        window_sizes = [30, 40, 50, 60, 80]
        for w in window_sizes:
            if len(text) < w * 5:
                continue
            seen = {}
            for i in range(len(text) - w):
                substr = text[i:i + w]
                if substr in seen:
                    seen[substr].append(i)
                else:
                    seen[substr] = [i]

            for substr, positions in seen.items():
                if len(positions) >= 5:
                    # 检查重复之间的间距是否很小（真正的循环）
                    gaps = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                    avg_gap = sum(gaps) / len(gaps) if gaps else 0
                    # 只有当间距很小时（< 200字符）才是真正的循环
                    if avg_gap < 200:
                        # 找到重复：在第 2 次出现处截断
                        cut_pos = positions[1]
                        truncated = text[:cut_pos].strip()
                        return True, truncated

        return False, text

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using MLX server.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (ignored for TranslateGemma)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build messages with appropriate format
        messages = self._build_messages(prompt, system_prompt)

        # Qwen thinking models with prefill need more tokens for translation output
        max_tokens = 2048 if self._is_qwen_thinking else 1024

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens,
            "repetition_penalty": 1.1 if self._is_qwen_thinking else 1.0,
            "frequency_penalty": 0.3 if self._is_qwen_thinking else 0.0,
        }

        client = await self._get_mlx_client()

        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()

                response_json = response.json()
                message = response_json.get("choices", [{}])[0].get("message", {})

                # 方案 D：检查 reasoning_content 字段（零误判）
                reasoning_content = message.get("reasoning_content")
                response_text = message.get("content", "")

                # 如果有 reasoning_content，记录到 thinking 缓存
                if reasoning_content and self.log_callback:
                    self.log_callback("mlx_thinking_detected",
                        f"🧠 Thinking content detected ({len(reasoning_content)} chars)")
                    # 可以在这里缓存 reasoning_content 用于调试

                # Clean up model-generated artifacts
                response_text = self._clean_model_artifacts(response_text)

                # Detect Qwen thinking mode leakage — prefill failed, retry
                if self._is_qwen_thinking and response_text.startswith("Thinking Process:"):
                    if self.log_callback:
                        self.log_callback("mlx_thinking_leak",
                            f"⚠️ Thinking leaked (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}), retrying...")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(1)
                        continue
                    # Last attempt: try to extract any translation after thinking
                    response_text = self._strip_thinking(response_text)

                # Detect repetition loops — truncate and retry
                has_rep, fixed_text = self._detect_repetition(response_text)
                if has_rep:
                    if self.log_callback:
                        self.log_callback("mlx_repetition",
                            f"⚠️ Repetition loop detected (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}), retrying...")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(1)
                        continue
                    # Last attempt: use truncated text
                    response_text = fixed_text

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
                    was_truncated=False
                )

            except httpx.HTTPStatusError as e:
                if hasattr(e, 'response') and e.response.status_code == 429:
                    retry_after_header = e.response.headers.get("Retry-After")
                    wait_time = int(retry_after_header) if retry_after_header else min(2 ** (attempt + 2), 60)
                    if self.log_callback:
                        self.log_callback("llm_rate_limit",
                            f"⚠️ Rate limited (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}), waiting {wait_time}s...")
                    else:
                        print(f"⚠️ Rate limited (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}), waiting {wait_time}s...")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    raise RateLimitError(
                        f"Rate limit exceeded after {MAX_TRANSLATION_ATTEMPTS} attempts",
                        retry_after=wait_time,
                        provider="mlx"
                    )

                # Get error details
                error_message = str(e)
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    try:
                        error_json = e.response.json()
                        if "error" in error_json:
                            if isinstance(error_json["error"], dict):
                                error_message = error_json["error"].get("message", str(e))
                            else:
                                error_message = str(error_json.get("error", e))
                    except:
                        pass

                # Detect context overflow
                context_keywords = ["context_length", "maximum context", "token limit",
                                    "too many tokens", "max_tokens", "context", "truncate"]
                if any(keyword in error_message.lower() for keyword in context_keywords):
                    if self.log_callback:
                        self.log_callback("llm_context_overflow",
                            f"❌ Context size exceeded! Error: {error_message}")
                    raise ContextOverflowError(error_message)

                # Other errors
                if self.log_callback:
                    self.log_callback("llm_http_error",
                        f"⚠️ HTTP error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {error_message}")
                else:
                    print(f"⚠️ HTTP error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {error_message}")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                    continue

                return None

            except Exception as e:
                if self.log_callback:
                    self.log_callback("llm_error",
                        f"⚠️ Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {type(e).__name__}: {e}")
                else:
                    print(f"⚠️ Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {type(e).__name__}: {e}")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                    continue

                return None

        return None

    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response.

        For TranslateGemma models, the response is already the translation
        without any tags, so we return it directly after cleaning.

        For Qwen thinking models with assistant prefill, the response may lack
        the opening <TRANSLATION> tag (since it was in the prefill). Handle this
        by prepending the tag before extraction.

        For other MLX models, fall back to standard tag extraction.

        Args:
            response: Raw LLM response

        Returns:
            Extracted translation or None if not found
        """
        if not response:
            return None

        # For TranslateGemma, the response is already the translation
        # Just clean it and return
        if self._is_translategemma:
            cleaned = self._clean_model_artifacts(response)
            if cleaned and cleaned.strip():
                return cleaned.strip()

        # For Qwen thinking models, assistant prefill contains <TRANSLATION> tag
        # so the response may only have content + closing tag
        if self._is_qwen_thinking:
            from src.config import TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT
            cleaned = self._clean_model_artifacts(response)
            # Try standard extraction first
            result = self._extractor.extract(cleaned)
            if result:
                return result
            # If extraction failed, check if we need to add the opening tag
            if TRANSLATE_TAG_OUT in cleaned and TRANSLATE_TAG_IN not in cleaned:
                return self._extractor.extract(TRANSLATE_TAG_IN + cleaned)
            # No tags at all - return cleaned content directly
            if cleaned and cleaned.strip():
                return cleaned.strip()
            return None

        # For other models, use standard tag extraction
        return self._extractor.extract(response)

    async def get_model_context_size(self) -> int:
        """Return configured context size."""
        return self.context_window
