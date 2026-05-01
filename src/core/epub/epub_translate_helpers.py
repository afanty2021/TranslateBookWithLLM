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

    def extract_paragraphs(self, html_content: str) -> List[Tuple[str, int, int]]:
        """
        从 HTML 中提取完整的 <p> 段落。

        返回: [(段落完整内容, 开始位置, 结束位置), ...]
        """
        # 匹配 <p> 标签及其所有内容（包括嵌套标签）
        # 使用非贪婪匹配，但确保匹配完整的段落
        pattern = r'(<p[^>]*>.*?</p>)'
        matches = []

        for match in re.finditer(pattern, html_content, re.DOTALL):
            para_html = match.group(0)
            start = match.start()
            end = match.end()

            # 提取纯文本检查是否需要翻译
            text_only = re.sub(r'<[^>]+>', ' ', para_html).strip()
            # 检查是否包含足够的英文内容
            if text_only and len(text_only) > 15 and re.search(r'[a-zA-Z]{5,}', text_only):
                matches.append((para_html, start, end))

        return matches

    async def translate_paragraph(self, para_html: str) -> Optional[str]:
        """
        翻译单个段落（保留HTML结构）。

        策略：提取纯文本 -> 翻译 -> 重建HTML结构
        """
        # 提取纯文本
        text_only = re.sub(r'<[^>]+>', ' ', para_html).strip()
        text_only = re.sub(r'\s+', ' ', text_only)  # 合并多个空格

        # 对于URL，保持原样
        # 检查是否是真正的URL（以http/https开头，或包含常见域名模式）
        if (text_only.startswith(('http://', 'https://', 'www.')) or
            re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$', text_only)):  # 简单域名如 example.com
            return para_html

        # 对于太短的文本，跳过
        if len(text_only) < 15:
            return None

        prompt = f"""直接翻译为中文：{text_only}

要求：只输出中文翻译，不要任何解释、分析或额外说明。"""

        try:
            response = await self.provider.generate(
                prompt=prompt,
                timeout=120,
                system_prompt="你是专业翻译。只输出翻译结果，不要思考过程、解释或额外内容。"
            )

            if response and response.content:
                translation = response.content.strip()
                if not translation:
                    self.log("warn", f"空翻译结果: {text_only[:50]}")
                    return None

                # 清理：移除明显的额外解释和标记
                # 移除markdown格式（**加粗**、`代码`等）
                translation = re.sub(r'\*\*([^*]+)\*\*', r'\1', translation)
                translation = re.sub(r'`([^`]+)`', r'\1', translation)

                # 移除明显的提示前缀（如 "💡", "Note:", "Explanation:" 等）
                translation = re.sub(r'^(💡|Note:|Explanation:|注释：|解释：)\s*', '', translation, flags=re.IGNORECASE)
                translation = re.sub(r'💡.*', '', translation, flags=re.DOTALL)  # 移除提示部分

                # 移除常见的思考过程残留
                translation = re.sub(r'^（.*?）', '', translation)  # 括号中的说明
                translation = re.sub(r'^\[.*?\]', '', translation)  # 方括号中的说明

                translation = translation.strip()

                # 简单的HTML重建：将翻译文本放入 <p> 标签
                tag_match = re.match(r'(<p[^>]*>).*?(</p>)', para_html, re.DOTALL)
                if tag_match:
                    opening_tag = tag_match.group(1)
                    closing_tag = tag_match.group(2)
                    return f"{opening_tag}{translation}{closing_tag}"

                return translation
            else:
                self.log("warn", f"API返回空响应: {text_only[:50]}")
        except Exception as e:
            self.log("error", f"Translation error: {e}")

        return None

    @staticmethod
    def replace_paragraphs(html_content: str, replacements: List[Tuple[str, int, int, str]]) -> str:
        """
        在 HTML 中替换已翻译的段落。

        replacements: [(原始HTML, 开始位置, 结束位置, 翻译后的HTML), ...]
        """
        result = html_content
        # 从后往前替换，避免位置偏移
        for orig_html, start, end, translated_html in sorted(replacements, key=lambda x: -x[1]):
            result = result[:start] + translated_html + result[end:]
        return result
