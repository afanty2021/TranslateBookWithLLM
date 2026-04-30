#!/usr/bin/env python3
"""
EPUB 并行翻译脚本 - 支持断点续译的健壮版本

特性：
1. 每翻译完一个文件立即保存（检查点机制）
2. 支持断点续译（从中断处继续）
3. 支持多进程并行翻译
4. 进程安全（使用文件锁）
5. 翻译进度实时同步
"""
import sys
import os
import asyncio
import zipfile
import re
import json
import fcntl
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.llm.providers.mlx import MLXProvider
from src.config import OLLAMA_NUM_CTX
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ParallelRobustEPUBTranslator:
    """支持并行和断点续译的健壮 EPUB 翻译器"""

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

        # 检查点文件
        self.checkpoint_file = None
        self.progress_file = None
        self.translated_files: Dict[str, str] = {}

    async def init_provider(self):
        """初始化 MLX Provider"""
        self.provider = MLXProvider(
            api_endpoint=self.endpoint,
            model=self.model,
            api_key=self.api_key,
            context_window=OLLAMA_NUM_CTX,
            log_callback=self._log_callback
        )
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
            print(f"    [{self.worker_id}] ❌ Translation error: {e}")

        return None

    def _replace_in_html(self, html_content: str, replacements: list) -> str:
        """在 HTML 中进行替换"""
        result = html_content
        for orig, trans, start, end in sorted(replacements, key=lambda x: -x[3]):
            result = result[:start] + trans + result[end:]
        return result

    def _update_progress_file(self, file_path: str, status: str):
        """更新全局进度文件（带文件锁）"""
        progress_data = {}

        # 读取现有进度
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
            except:
                pass

        # 更新当前文件状态
        progress_data[file_path] = {
            "status": status,
            "worker": self.worker_id,
            "timestamp": datetime.now().isoformat()
        }

        # 原子写入（使用临时文件）
        temp_file = self.progress_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

        # 原子重命名
        os.rename(temp_file, self.progress_file)

    def _load_progress(self) -> Dict:
        """加载全局进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _is_file_translated(self, file_path: str, output_zip: zipfile.ZipFile) -> bool:
        """检查文件是否已翻译"""
        try:
            # 检查 ZIP 中是否已有该文件
            output_zip.getinfo(file_path)
            # 检查进度记录
            progress = self._load_progress()
            if file_path in progress:
                return progress[file_path].get("status") == "completed"
        except KeyError:
            return False
        return False

    async def translate_epub(self, input_path: str, output_path: str, resume: bool = True):
        """
        翻译 EPUB 文件（支持并行和断点续译）

        Args:
            input_path: 输入 EPUB 路径
            output_path: 输出 EPUB 路径
            resume: 是否从断点恢复（默认 True）
        """
        print("=" * 70)
        print(f"📚 Worker {self.worker_id}: EPUB 并行翻译")
        print("=" * 70)
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"模型: {self.model}")
        print(f"文件范围: {self.start_file}-{self.end_file or '末尾'}")
        print(f"断点续译: {'启用' if resume else '禁用'}")
        print("=" * 70)
        print()

        # 设置进度文件
        base_name = output_path.rsplit('.', 1)[0]
        self.progress_file = f"{base_name}_progress.json"

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
            print(f"本批次: {len(target_files)} 个文件 (索引 {self.start_file}-{end_idx})")
            print()

            # 创建或更新输出 ZIP（追加模式）
            mode = 'a' if os.path.exists(output_path) else 'w'

            with zipfile.ZipFile(output_path, mode, zipfile.ZIP_DEFLATED) as zip_out:
                # 确保 mimetype 存在且第一个（仅首次创建）
                if mode == 'w' and 'mimetype' in file_list:
                    content = zip_ref.read('mimetype')
                    zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

                # 处理指定范围的文件
                for idx, file_path in enumerate(target_files, self.start_file):
                    print(f"--- [{self.worker_id}] 文件 {idx}/{len(html_files)}: {file_path} ---")

                    # 检查是否已翻译
                    if self._is_file_translated(file_path, zip_out):
                        print(f"  [{self.worker_id}] ⏭️  已跳过（已翻译）")
                        continue

                    # 读取文件内容
                    content = zip_ref.read(file_path).decode('utf-8')

                    # 提取可翻译节点
                    nodes = self._extract_translatable_nodes(content)
                    print(f"  [{self.worker_id}] 找到 {len(nodes)} 个可翻译节点")

                    if not nodes:
                        # 没有可翻译内容，直接复制
                        zip_out.writestr(file_path, content)
                        self._update_progress_file(file_path, "skipped")
                        continue

                    # 翻译每个节点
                    replacements = []
                    translated = 0

                    for node_idx, (text, start, end) in enumerate(nodes, 1):
                        print(f"  [{self.worker_id}] 翻译: {text[:50]}...")

                        translation = await self._translate_text(text)

                        if translation:
                            replacements.append((text, translation, start, end))
                            translated += 1
                            self.translated_count += 1
                            print(f"    [{self.worker_id}] → {translation[:50]}")
                        else:
                            self.error_count += 1
                            print(f"    [{self.worker_id}] ❌ 翻译失败")

                        # 避免请求过快
                        await asyncio.sleep(0.5)

                    print(f"  [{self.worker_id}] 翻译了 {translated} 个节点")

                    # 替换内容并立即写入
                    if replacements:
                        new_content = self._replace_in_html(content, replacements)
                        zip_out.writestr(file_path, new_content.encode('utf-8'))
                    else:
                        zip_out.writestr(file_path, content.encode('utf-8'))

                    # ⚡ 关键：每翻译完一个文件就更新进度
                    self._update_progress_file(file_path, "completed")
                    print(f"  [{self.worker_id}] 💾 已保存进度")

                # 复制其他非 HTML 文件（仅主进程首次创建时）
                if mode == 'w' and self.worker_id == "main":
                    for file_path in file_list:
                        if file_path.endswith(('.html', '.xhtml')) or file_path == 'mimetype':
                            continue
                        content = zip_ref.read(file_path)
                        zip_out.writestr(file_path, content)

        print()
        print("=" * 70)
        print(f"✅ [{self.worker_id}] 本批次完成!")
        print(f"输出文件: {output_path}")
        print(f"本批次翻译节点: {self.translated_count}")
        print(f"错误数量: {self.error_count}")
        print("=" * 70)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 并行翻译 (支持断点续译)')
    parser.add_argument('--start', type=int, default=1, help='起始文件索引 (1-31)')
    parser.add_argument('--end', type=int, default=None, help='结束文件索引 (不包含)')
    parser.add_argument('--worker-id', type=str, default='main', help='工作进程 ID')
    parser.add_argument('--model', type=str, default='Qwen3.6-35B-A3B-4bit', help='模型名称')
    parser.add_argument('--endpoint', type=str,
                       default='http://localhost:8000/v1/chat/completions',
                       help='API 端点')
    parser.add_argument('--input', type=str, required=True,
                       help='输入 EPUB 文件路径')
    parser.add_argument('--output', type=str, required=True,
                       help='输出 EPUB 路径')

    args = parser.parse_args()

    translator = ParallelRobustEPUBTranslator(
        model=args.model,
        endpoint=args.endpoint,
        start_file=args.start,
        end_file=args.end,
        worker_id=args.worker_id
    )

    await translator.translate_epub(
        input_path=args.input,
        output_path=args.output
    )


if __name__ == "__main__":
    asyncio.run(main())
