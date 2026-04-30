"""EPUB 翻译公共辅助方法，供根级翻译脚本共享使用"""
import re
import asyncio
from typing import Optional, List, Tuple, Callable


class EPUBTranslateHelper:
    """EPUB 翻译共享逻辑"""

    def __init__(self, provider, log_callback: Optional[Callable] = None):
        self.provider = provider
        self._log_callback = log_callback

    def log(self, level: str, msg: str):
        """统一的日志回调"""
        if self._log_callback:
            self._log_callback(level, msg)
        else:
            print(f"[{level}] {msg}")

    def extract_translatable_nodes(self, html_content: str) -> List[Tuple[str, int, int]]:
        """从 HTML 中提取可翻译文本节点"""
        pattern = r'>([^<]{10,})<'
        matches = []

        for match in re.finditer(pattern, html_content):
            text = match.group(1).strip()
            if text and len(text) > 10 and re.search(r'[a-zA-Z]{3,}', text):
                start = match.start(1)
                end = match.end(1)
                matches.append((text, start, end))

        return matches

    async def translate_text(self, text: str) -> Optional[str]:
        """使用 provider 翻译单个文本"""
        prompt = f"""Translate the following English text to Chinese. Output ONLY the Chinese translation, no explanations or notes.

{text}"""

        try:
            response = await self.provider.generate(
                prompt=prompt,
                timeout=120,
                system_prompt="You are a professional translator. Translate English to Chinese accurately."
            )

            if response and response.content:
                translation = response.content.strip()
                if not translation:
                    return None

                # 移除可能的引号包围
                if translation.startswith('"') and translation.endswith('"'):
                    translation = translation[1:-1]
                elif translation.startswith("'") and translation.endswith("'"):
                    translation = translation[1:-1]

                return translation
        except Exception as e:
            print(f"    ❌ Translation error: {e}")

        return None

    @staticmethod
    def replace_in_html(html_content: str, replacements: list) -> str:
        """在 HTML 中执行批量文本替换"""
        result = html_content
        for orig, trans, start, end in sorted(replacements, key=lambda x: -x[3]):
            result = result[:start] + trans + result[end:]
        return result
