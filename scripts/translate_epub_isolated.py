#!/usr/bin/env python3
"""
EPUB 独立进程翻译脚本 - 每个进程输出独立的 EPUB 文件

特性：
1. 每个进程独立输出完整的 EPUB 文件
2. 包含所有必要文件（mimetype, 样式, 图片等）
3. 进程隔离，互不影响
4. 翻译完成后可单独验证每个部分
"""
import sys
import os
import asyncio
import zipfile
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from src.core.llm.providers.mlx import MLXProvider
from src.core.epub.epub_translate_helpers import EPUBTranslateHelper
from src.config import OLLAMA_NUM_CTX
from dotenv import load_dotenv

# 加载环境变量（从项目根目录）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))


class IsolatedEPUBTranslator:
    """独立进程 EPUB 翻译器 - 输出完整独立的 EPUB 文件"""

    def __init__(self, model: str, endpoint: str, api_key: str = None,
                 start_file: int = 1, end_file: int = None, part_id: str = "part1"):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("MLX_API_KEY", "")
        self.provider = None
        self.translated_count = 0
        self.error_count = 0
        self.start_file = start_file
        self.end_file = end_file
        self.part_id = part_id

    async def init_provider(self):
        """初始化 MLX Provider"""
        self.provider = MLXProvider(
            api_endpoint=self.endpoint,
            model=self.model,
            api_key=self.api_key,
            context_window=OLLAMA_NUM_CTX,
            log_callback=self._log_callback
        )
        self._helper = EPUBTranslateHelper(self.provider, self._log_callback)
        print(f"✓ Worker {self.part_id}: Provider initialized")

    def _log_callback(self, level: str, msg: str):
        """日志回调"""
        if level == "mlx_thinking_detected":
            print(f"  [{self.part_id}] 🧠 {msg}")
        elif level == "mlx_repetition":
            print(f"  [{self.part_id}] ⚠️ {msg}")
        elif level == "llm_error":
            print(f"  [{self.part_id}] ❌ {msg}")
        elif level == "llm_rate_limit":
            print(f"  [{self.part_id}] 🔄 {msg}")

    async def translate_epub(self, input_path: str, output_path: str):
        """
        翻译 EPUB 文件 - 输出独立完整的 EPUB

        Args:
            input_path: 输入 EPUB 路径
            output_path: 输出 EPUB 路径（独立完整文件）
        """
        print("=" * 70)
        print(f"📚 Worker {self.part_id}: EPUB 独立翻译")
        print("=" * 70)
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"模型: {self.model}")
        print(f"文件范围: {self.start_file}-{self.end_file or '末尾'}")
        print("=" * 70)
        print()

        await self.init_provider()

        # 读取 EPUB
        print(f"📖 [{self.part_id}] 读取 EPUB 文件...")
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
            print(f"本批次: {len(target_files)} 个文件")
            print()

            # 创建新的独立 EPUB 文件
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                # 1. 先复制 mimetype（必须第一个，无压缩）
                if 'mimetype' in file_list:
                    content = zip_ref.read('mimetype')
                    zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

                # 2. 复制所有必要的资源文件（样式、图片、字体等）
                resource_files = [f for f in file_list
                                 if not f.endswith(('.html', '.xhtml'))
                                 and f != 'mimetype']
                for resource_file in resource_files:
                    content = zip_ref.read(resource_file)
                    zip_out.writestr(resource_file, content)
                print(f"  [{self.part_id}] 已复制 {len(resource_files)} 个资源文件")

                # 3. 翻译指定范围的 HTML 文件
                for idx, file_path in enumerate(target_files, self.start_file):
                    print(f"--- [{self.part_id}] 文件 {idx}/{len(html_files)}: {file_path} ---")

                    # 读取文件内容
                    content = zip_ref.read(file_path).decode('utf-8')

                    # 提取可翻译节点
                    nodes = self._helper.extract_translatable_nodes(content)
                    print(f"  [{self.part_id}] 找到 {len(nodes)} 个可翻译节点")

                    if not nodes:
                        # 没有可翻译内容，直接复制
                        zip_out.writestr(file_path, content.encode('utf-8'))
                        continue

                    # 翻译每个节点
                    replacements = []
                    translated = 0

                    for node_idx, (text, start, end) in enumerate(nodes, 1):
                        print(f"  [{self.part_id}] 翻译: {text[:50]}...")

                        translation = await self._helper.translate_text(text)

                        if translation:
                            replacements.append((text, translation, start, end))
                            translated += 1
                            self.translated_count += 1
                            print(f"    [{self.part_id}] → {translation[:50]}")
                        else:
                            self.error_count += 1
                            print(f"    [{self.part_id}] ❌ 翻译失败")

                        # 避免请求过快
                        await asyncio.sleep(0.5)

                    print(f"  [{self.part_id}] 翻译了 {translated} 个节点")

                    # 替换内容并写入
                    if replacements:
                        new_content = self._helper.replace_in_html(content, replacements)
                        zip_out.writestr(file_path, new_content.encode('utf-8'))
                    else:
                        zip_out.writestr(file_path, content.encode('utf-8'))

                    # ⚡ 每个 HTML 文件写入后立即刷新到磁盘
                    zip_out.fp.flush()

        print()
        print("=" * 70)
        print(f"✅ [{self.part_id}] 翻译完成!")
        print(f"输出文件: {output_path}")
        print(f"翻译节点: {self.translated_count}")
        print(f"错误数量: {self.error_count}")
        print(f"文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")
        print("=" * 70)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 独立进程翻译')
    parser.add_argument('--start', type=int, required=True, help='起始文件索引 (1-31)')
    parser.add_argument('--end', type=int, required=True, help='结束文件索引 (不包含)')
    parser.add_argument('--part-id', type=str, required=True, help='部分 ID (part1, part2, etc.)')
    parser.add_argument('--model', type=str, default='Qwen3.6-35B-A3B-4bit', help='模型名称')
    parser.add_argument('--endpoint', type=str,
                       default='http://localhost:8000/v1/chat/completions',
                       help='API 端点')
    parser.add_argument('--output-dir', type=str,
                       default="translated_files",
                       help='输出目录')
    parser.add_argument('--input', type=str, required=True,
                       help='输入 EPUB 文件路径')

    args = parser.parse_args()

    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    output_file = os.path.join(args.output_dir, f"{base_name}_{args.part_id}.epub")

    translator = IsolatedEPUBTranslator(
        model=args.model,
        endpoint=args.endpoint,
        start_file=args.start,
        end_file=args.end,
        part_id=args.part_id
    )

    await translator.translate_epub(
        input_path=args.input,
        output_path=output_file
    )


if __name__ == "__main__":
    asyncio.run(main())
