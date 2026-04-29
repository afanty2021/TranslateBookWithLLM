#!/usr/bin/env python3
"""
完整 EPUB 翻译脚本 - 使用调整后的重复检测阈值
"""
import sys
import os
import asyncio
import zipfile
import re
from pathlib import Path
from typing import Optional, Callable

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.llm.providers.mlx import MLXProvider
from src.config import OLLAMA_NUM_CTX
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class EPUBFullTranslator:
    """完整 EPUB 翻译器"""

    def __init__(self, model: str, endpoint: str, api_key: str = None):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("MLX_API_KEY", "")
        self.provider = None
        self.translated_count = 0
        self.error_count = 0

    async def init_provider(self):
        """初始化 MLX Provider"""
        self.provider = MLXProvider(
            api_endpoint=self.endpoint,
            model=self.model,
            api_key=self.api_key,
            context_window=OLLAMA_NUM_CTX,
            log_callback=self._log_callback
        )
        print(f"✓ Provider initialized: {self.model}")

    def _log_callback(self, level: str, msg: str):
        """日志回调"""
        if level == "mlx_thinking_detected":
            print(f"  🧠 {msg}")
        elif level == "mlx_repetition":
            print(f"  ⚠️ {msg}")
        elif level == "llm_error":
            print(f"  ❌ {msg}")
        elif level == "llm_rate_limit":
            print(f"  🔄 {msg}")

    def _extract_translatable_nodes(self, html_content: str) -> list:
        """
        提取可翻译的文本节点

        返回: [(original_text, start_pos, end_pos), ...]
        """
        # 匹配不包含子标签的文本内容
        # 模式：>文本<，其中文本不包含<
        pattern = r'>([^<]{10,})<'
        matches = []

        for match in re.finditer(pattern, html_content):
            text = match.group(1).strip()
            # 过滤掉纯数字、空格等
            if text and len(text) > 10 and re.search(r'[a-zA-Z]{3,}', text):
                start = match.start(1)
                end = match.end(1)
                matches.append((text, start, end))

        return matches

    async def _translate_text(self, text: str) -> Optional[str]:
        """
        翻译单个文本片段

        使用简化的提示词，减少不必要的输出
        """
        prompt = f"""Translate the following English text to Chinese. Output ONLY the Chinese translation, no explanations or notes.

{text}"""

        try:
            response = await self.provider.generate(
                prompt=prompt,
                timeout=120,
                system_prompt="You are a professional translator. Translate English to Chinese accurately."
            )

            if response and response.content:
                # 清理输出
                translation = response.content.strip()

                # 检查是否为空
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

    def _replace_in_html(self, html_content: str, replacements: list) -> str:
        """
        在 HTML 中进行替换

        replacements: [(original, translation, start, end), ...]
        按位置倒序替换，避免位置偏移
        """
        result = html_content

        # 按位置倒序排序
        for orig, trans, start, end in sorted(replacements, key=lambda x: -x[3]):
            result = result[:start] + trans + result[end:]

        return result

    async def translate_epub(self, input_path: str, output_path: str):
        """
        翻译整个 EPUB 文件

        Args:
            input_path: 输入 EPUB 路径
            output_path: 输出 EPUB 路径
        """
        print("=" * 70)
        print("📚 EPUB 完整翻译")
        print("=" * 70)
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"模型: {self.model}")
        print("=" * 70)
        print()

        await self.init_provider()

        # 读取 EPUB
        print("📖 读取 EPUB 文件...")
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            html_files = [f for f in file_list
                         if f.endswith(('.html', '.xhtml'))
                         and not f.startswith('META-INF')]

            print(f"找到 {len(html_files)} 个文件")
            print()

            # 创建新的 ZIP
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                # 先复制 mimetype（必须第一个，无压缩）
                if 'mimetype' in file_list:
                    content = zip_ref.read('mimetype')
                    zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

                # 处理每个文件
                for idx, file_path in enumerate(html_files, 1):
                    print(f"--- 文件 {idx}/{len(html_files)}: {file_path} ---")

                    # 读取文件内容
                    content = zip_ref.read(file_path).decode('utf-8')

                    # 提取可翻译节点
                    nodes = self._extract_translatable_nodes(content)
                    print(f"  找到 {len(nodes)} 个可翻译节点")

                    if not nodes:
                        # 没有可翻译内容，直接复制
                        zip_out.writestr(file_path, content)
                        continue

                    # 翻译每个节点
                    replacements = []
                    translated = 0

                    for node_idx, (text, start, end) in enumerate(nodes, 1):  # 翻译所有节点
                        print(f"  翻译: {text[:50]}...")

                        translation = await self._translate_text(text)

                        if translation:
                            replacements.append((text, translation, start, end))
                            translated += 1
                            self.translated_count += 1
                            print(f"    → {translation[:50]}")
                        else:
                            self.error_count += 1
                            print(f"    ❌ 翻译失败")

                        # 避免请求过快
                        await asyncio.sleep(0.5)

                    print(f"  翻译了 {translated} 个节点")

                    # 替换内容
                    if replacements:
                        new_content = self._replace_in_html(content, replacements)
                        zip_out.writestr(file_path, new_content.encode('utf-8'))
                    else:
                        zip_out.writestr(file_path, content.encode('utf-8'))

                # 复制其他非 HTML 文件
                for file_path in file_list:
                    if file_path.endswith(('.html', '.xhtml')) or file_path == 'mimetype':
                        continue
                    content = zip_ref.read(file_path)
                    zip_out.writestr(file_path, content)

        print()
        print("=" * 70)
        print("✅ 翻译完成!")
        print(f"输出文件: {output_path}")
        print(f"总翻译节点: {self.translated_count}")
        print(f"错误数量: {self.error_count}")
        print("=" * 70)


async def main():
    """主函数"""
    translator = EPUBFullTranslator(
        model="Qwen3.6-35B-A3B-4bit",
        endpoint="http://localhost:8000/v1/chat/completions"
    )

    await translator.translate_epub(
        input_path="/Users/berton/Downloads/The Great Mathematical Problems (Ian Stewart) .epub",
        output_path="/Users/berton/Github/TranslateBookWithLLM/translated_files/The Great Mathematical Problems (Chinese) v5.epub"
    )


if __name__ == "__main__":
    asyncio.run(main())
