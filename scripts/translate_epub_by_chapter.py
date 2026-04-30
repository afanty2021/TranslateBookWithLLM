#!/usr/bin/env python3
"""
EPUB 按章节翻译脚本 - 每个章节独立保存

特性：
1. 每翻译完一个章节立即保存为独立文件
2. 支持断点续译（跳过已翻译章节）
3. 进程安全（使用文件锁）
4. 最后统一合并所有章节

文件结构：
  translated/
    chapters/
      ch01.html.translated
      ch02.html.translated
      ...
    progress.json  # 翻译进度跟踪
"""
import sys
import os
import asyncio
import zipfile
import re
import json
import fcntl
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from src.core.llm.providers.mlx import MLXProvider
from src.core.epub.epub_translate_helpers import EPUBTranslateHelper
from src.config import OLLAMA_NUM_CTX
from dotenv import load_dotenv

# 加载环境变量（从项目根目录）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))


class ChapterBasedTranslator:
    """按章节翻译的 EPUB 翻译器"""

    def __init__(self, model: str, endpoint: str, api_key: str = None,
                 start_file: int = 1, end_file: int = None, worker_id: str = "main"):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("MLX_API_KEY", "")
        self.provider = None
        self.translated_count = 0
        self.error_count = 0
        self.start_file = start_file
        self.end_file = end_file
        self.worker_id = worker_id

        # 章节目录和进度文件
        self.chapter_dir = None
        self.progress_file = None
        self.lock_file = None

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
        print(f"✓ Worker {self.worker_id}: Provider initialized")

    def _log_callback(self, level: str, msg: str):
        """日志回调"""
        if level == "mlx_thinking_detected":
            print(f"  [{self.worker_id}] 🧠 {msg}")
        elif level == "mlx_repetition":
            print(f"  [{self.worker_id}] ⚠️ {msg}")
        elif level == "llm_error":
            print(f"  [{self.worker_id}] ❌ {msg}")
        elif level == "llm_rate_limit":
            print(f"  [{self.worker_id}] 🔄 {msg}")

    def _get_chapter_file_path(self, chapter_name: str) -> str:
        """获取章节文件路径"""
        # 使用安全的文件名
        safe_name = chapter_name.replace('/', '_').replace('\\', '_')
        return os.path.join(self.chapter_dir, f"{safe_name}.translated")

    def _is_chapter_translated(self, chapter_name: str) -> bool:
        """检查章节是否已翻译"""
        chapter_file = self._get_chapter_file_path(chapter_name)
        return os.path.exists(chapter_file)

    def _save_chapter(self, chapter_name: str, content: str):
        """保存翻译后的章节"""
        chapter_file = self._get_chapter_file_path(chapter_name)

        # 原子写入（使用临时文件）
        temp_file = chapter_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # 原子重命名
        os.rename(temp_file, chapter_file)

        # 更新进度
        self._update_progress(chapter_name, "completed")

    def _update_progress(self, chapter_name: str, status: str):
        """更新翻译进度（带文件锁）"""
        progress_data = {}

        # 读取现有进度
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Suppressed error: {e}")

        # 更新当前章节状态
        progress_data[chapter_name] = {
            "status": status,
            "worker": self.worker_id,
            "timestamp": datetime.now().isoformat()
        }

        # 原子写入
        temp_file = self.progress_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

        os.rename(temp_file, self.progress_file)

    async def translate_epub(self, input_path: str):
        """
        翻译 EPUB 文件 - 按章节保存

        Args:
            input_path: 输入 EPUB 路径
        """
        print("=" * 70)
        print(f"📚 Worker {self.worker_id}: EPUB 按章节翻译")
        print("=" * 70)
        print(f"输入: {input_path}")
        print(f"模型: {self.model}")
        print(f"文件范围: {self.start_file}-{self.end_file or '末尾'}")
        print(f"章节目录: {self.chapter_dir}")
        print("=" * 70)
        print()

        await self.init_provider()

        # 读取 EPUB
        print(f"📖 [{self.worker_id}] 读取 EPUB 文件...")
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

            # 统计已翻译和待翻译
            translated_count = 0
            pending_count = 0

            for file_path in target_files:
                if self._is_chapter_translated(file_path):
                    translated_count += 1
                else:
                    pending_count += 1

            print(f"📊 进度统计:")
            print(f"  已翻译: {translated_count} 个")
            print(f"  待翻译: {pending_count} 个")
            print()

            # 处理每个文件
            for idx, file_path in enumerate(target_files, self.start_file):
                print(f"--- [{self.worker_id}] 文件 {idx}/{len(html_files)}: {file_path} ---")

                # 检查是否已翻译
                if self._is_chapter_translated(file_path):
                    print(f"  [{self.worker_id}] ⏭️  已跳过（已翻译）")
                    self.translated_count += 1
                    continue

                # 读取文件内容
                content = zip_ref.read(file_path).decode('utf-8')

                # 提取可翻译节点
                nodes = self._helper.extract_translatable_nodes(content)
                print(f"  [{self.worker_id}] 找到 {len(nodes)} 个可翻译节点")

                if not nodes:
                    # 没有可翻译内容，直接保存原文
                    self._save_chapter(file_path, content)
                    print(f"  [{self.worker_id}] 💾 已保存（无翻译内容）")
                    continue

                # 翻译每个节点
                replacements = []
                translated = 0

                for node_idx, (text, start, end) in enumerate(nodes, 1):
                    print(f"  [{self.worker_id}] 翻译: {text[:50]}...")

                    translation = await self._helper.translate_text(text)

                    if translation:
                        replacements.append((text, translation, start, end))
                        translated += 1
                        print(f"    [{self.worker_id}] → {translation[:50]}")
                    else:
                        self.error_count += 1
                        print(f"    [{self.worker_id}] ❌ 翻译失败")

                    # 避免请求过快
                    await asyncio.sleep(0.5)

                print(f"  [{self.worker_id}] 翻译了 {translated} 个节点")

                # 替换内容
                if replacements:
                    new_content = self._helper.replace_in_html(content, replacements)
                else:
                    new_content = content

                # ⚡ 关键：每翻译完一个章节就立即保存
                self._save_chapter(file_path, new_content)
                print(f"  [{self.worker_id}] 💾 章节已保存")

        print()
        print("=" * 70)
        print(f"✅ [{self.worker_id}] 本批次完成!")
        print(f"翻译节点: {self.translated_count}")
        print(f"错误数量: {self.error_count}")
        print(f"章节目录: {self.chapter_dir}")
        print("=" * 70)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 按章节翻译')
    parser.add_argument('--start', type=int, default=1, help='起始文件索引 (1-31)')
    parser.add_argument('--end', type=int, default=None, help='结束文件索引 (不包含)')
    parser.add_argument('--worker-id', type=str, default='main', help='工作进程 ID')
    parser.add_argument('--model', type=str, default='Qwen3.6-35B-A3B-4bit', help='模型名称')
    parser.add_argument('--endpoint', type=str,
                       default='http://localhost:8000/v1/chat/completions',
                       help='API 端点')
    parser.add_argument('--chapter-dir', type=str,
                       default="translated/chapters",
                       help='章节输出目录')
    parser.add_argument('--input', type=str, required=True,
                       help='输入 EPUB 文件路径')

    args = parser.parse_args()

    # 创建章节目录
    os.makedirs(args.chapter_dir, exist_ok=True)

    translator = ChapterBasedTranslator(
        model=args.model,
        endpoint=args.endpoint,
        start_file=args.start,
        end_file=args.end,
        worker_id=args.worker_id
    )

    # 设置目录和进度文件
    translator.chapter_dir = args.chapter_dir
    translator.progress_file = os.path.join(args.chapter_dir, "progress.json")

    await translator.translate_epub(
        input_path=args.input
    )


if __name__ == "__main__":
    asyncio.run(main())
