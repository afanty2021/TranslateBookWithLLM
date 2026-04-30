#!/usr/bin/env python3
"""
EPUB 范围翻译脚本 - 支持指定文件范围进行并行翻译
"""
import sys
import os
import asyncio
import zipfile
import re
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from src.core.llm.providers.mlx import MLXProvider
from src.config import OLLAMA_NUM_CTX
from dotenv import load_dotenv

# 加载环境变量（从项目根目录）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))


class EPUBRangeTranslator:
    """EPUB 范围翻译器 - 支持指定文件范围"""

    def __init__(self, model: str, endpoint: str, api_key: str = None,
                 start_file: int = 1, end_file: int = None):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("MLX_API_KEY", "")
        self.provider = None
        self.translated_count = 0
        self.error_count = 0
        self.start_file = start_file
        self.end_file = end_file

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
        """提取可翻译的文本节点"""
        pattern = r'>([^<]{10,})<'
        matches = []

        for match in re.finditer(pattern, html_content):
            text = match.group(1).strip()
            if text and len(text) > 10 and re.search(r'[a-zA-Z]{3,}', text):
                start = match.start(1)
                end = match.end(1)
                matches.append((text, start, end))

        return matches

    async def _translate_text(self, text: str) -> Optional[str]:
        """翻译单个文本片段"""
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

    def _replace_in_html(self, html_content: str, replacements: list) -> str:
        """在 HTML 中进行替换"""
        result = html_content
        for orig, trans, start, end in sorted(replacements, key=lambda x: -x[3]):
            result = result[:start] + trans + result[end:]
        return result

    async def translate_epub(self, input_path: str, output_path: str):
        """
        翻译 EPUB 文件的指定范围

        Args:
            input_path: 输入 EPUB 路径
            output_path: 输出 EPUB 路径
        """
        print("=" * 70)
        print(f"📚 EPUB 范围翻译 (文件 {self.start_file}-{self.end_file or '末尾'})")
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

            # 应用文件范围
            start_idx = self.start_file - 1
            end_idx = self.end_file if self.end_file else len(html_files)
            target_files = html_files[start_idx:end_idx]

            print(f"总文件数: {len(html_files)}")
            print(f"本批次: {len(target_files)} 个文件 (索引 {self.start_file}-{end_idx})")
            print()

            # 创建新的 ZIP
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                # 先复制 mimetype（必须第一个，无压缩）
                if 'mimetype' in file_list:
                    content = zip_ref.read('mimetype')
                    zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

                # 处理指定范围的文件
                for idx, file_path in enumerate(target_files, self.start_file):
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

                    for node_idx, (text, start, end) in enumerate(nodes, 1):
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
        print(f"本批次翻译节点: {self.translated_count}")
        print(f"错误数量: {self.error_count}")
        print("=" * 70)


async def main():
    """主函数 - 从命令行参数获取范围"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 范围翻译')
    parser.add_argument('--start', type=int, default=1, help='起始文件索引 (1-31)')
    parser.add_argument('--end', type=int, default=None, help='结束文件索引 (不包含)')
    parser.add_argument('--model', type=str, default='Qwen3.6-35B-A3B-4bit', help='模型名称')
    parser.add_argument('--endpoint', type=str,
                       default='http://localhost:8000/v1/chat/completions',
                       help='API 端点')

    args = parser.parse_args()

    translator = EPUBRangeTranslator(
        model=args.model,
        endpoint=args.endpoint,
        start_file=args.start,
        end_file=args.end
    )

    # 生成输出文件名
    output_suffix = f"_part{args.start}"
    if args.end:
        output_suffix += f"-{args.end}"

    await translator.translate_epub(
        input_path="/Users/berton/Downloads/The Great Mathematical Problems (Ian Stewart) .epub",
        output_path=f"/Users/berton/Github/TranslateBookWithLLM/translated_files/The Great Mathematical Problems (Chinese) v5{output_suffix}.epub"
    )


if __name__ == "__main__":
    asyncio.run(main())
