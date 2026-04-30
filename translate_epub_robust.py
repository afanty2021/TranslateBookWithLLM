#!/usr/bin/env python3
"""
EPUB 翻译脚本 - 支持断点续译的健壮版本

特性：
1. 每翻译完一个文件立即保存（检查点机制）
2. 支持断点续译（从中断处继续）
3. 翻译进度持久化
4. 进程安全（可中断可恢复）
"""
import sys
import os
import asyncio
import zipfile
import re
import json
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


class RobustEPUBTranslator:
    """支持断点续译的健壮 EPUB 翻译器"""

    def __init__(self, model: str, endpoint: str, api_key: str = None):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("MLX_API_KEY", "")
        self.provider = None
        self.translated_count = 0
        self.error_count = 0

        # 检查点文件
        self.checkpoint_file = None
        self.translated_files: Dict[str, str] = {}  # {file_path: translation_status}

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

    def _save_checkpoint(self, file_path: str, status: str):
        """保存检查点"""
        self.translated_files[file_path] = {
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        checkpoint_data = {
            "model": self.model,
            "translated_files": self.translated_files,
            "translated_count": self.translated_count,
            "error_count": self.error_count,
            "last_update": datetime.now().isoformat()
        }

        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

    def _load_checkpoint(self) -> Dict:
        """加载检查点"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _is_file_translated(self, file_path: str, output_zip: zipfile.ZipFile) -> bool:
        """检查文件是否已翻译"""
        try:
            # 检查 ZIP 中是否已有该文件
            output_zip.getinfo(file_path)
            # 检查检查点记录
            if file_path in self.translated_files:
                return self.translated_files[file_path].get("status") == "completed"
        except KeyError:
            return False
        return False

    async def translate_epub(self, input_path: str, output_path: str, resume: bool = True):
        """
        翻译 EPUB 文件（支持断点续译）

        Args:
            input_path: 输入 EPUB 路径
            output_path: 输出 EPUB 路径
            resume: 是否从断点恢复（默认 True）
        """
        print("=" * 70)
        print("📚 EPUB 翻译 (支持断点续译)")
        print("=" * 70)
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"模型: {self.model}")
        print(f"断点续译: {'启用' if resume else '禁用'}")
        print("=" * 70)
        print()

        # 设置检查点文件
        self.checkpoint_file = output_path + ".checkpoint.json"

        # 加载之前的进度
        if resume:
            checkpoint = self._load_checkpoint()
            if checkpoint:
                self.translated_files = checkpoint.get("translated_files", {})
                self.translated_count = checkpoint.get("translated_count", 0)
                self.error_count = checkpoint.get("error_count", 0)
                print(f"📋 恢复进度: 已翻译 {len(self.translated_files)} 个文件")
                print()

        await self.init_provider()

        # 读取 EPUB
        print("📖 读取 EPUB 文件...")
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            html_files = [f for f in file_list
                         if f.endswith(('.html', '.xhtml'))
                         and not f.startswith('META-INF')]

            print(f"总文件数: {len(html_files)}")
            print()

            # 创建或更新输出 ZIP
            mode = 'a' if (resume and os.path.exists(output_path)) else 'w'

            with zipfile.ZipFile(output_path, mode, zipfile.ZIP_DEFLATED) as zip_out:
                # 确保 mimetype 存在且第一个
                if 'mimetype' in file_list:
                    try:
                        zip_out.getinfo('mimetype')
                    except KeyError:
                        content = zip_ref.read('mimetype')
                        zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

                # 处理每个文件
                for idx, file_path in enumerate(html_files, 1):
                    print(f"--- 文件 {idx}/{len(html_files)}: {file_path} ---")

                    # 检查是否已翻译
                    if self._is_file_translated(file_path, zip_out):
                        print(f"  ⏭️  已跳过（已翻译）")
                        continue

                    # 读取文件内容
                    content = zip_ref.read(file_path).decode('utf-8')

                    # 提取可翻译节点
                    nodes = self._extract_translatable_nodes(content)
                    print(f"  找到 {len(nodes)} 个可翻译节点")

                    if not nodes:
                        # 没有可翻译内容，直接复制
                        zip_out.writestr(file_path, content)
                        self._save_checkpoint(file_path, "skipped")
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

                    # 替换内容并立即写入
                    if replacements:
                        new_content = self._replace_in_html(content, replacements)
                        zip_out.writestr(file_path, new_content.encode('utf-8'))
                    else:
                        zip_out.writestr(file_path, content.encode('utf-8'))

                    # ⚡ 关键：每翻译完一个文件就保存检查点
                    self._save_checkpoint(file_path, "completed")
                    print(f"  💾 已保存到检查点")

                # 复制其他非 HTML 文件（仅在首次创建时）
                if mode == 'w':
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
        print(f"检查点文件: {self.checkpoint_file}")
        print("=" * 70)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 翻译 (支持断点续译)')
    parser.add_argument('--input', type=str, required=True,
                       help='输入 EPUB 路径')
    parser.add_argument('--output', type=str, required=True,
                       help='输出 EPUB 路径')
    parser.add_argument('--model', type=str, default='Qwen3.6-35B-A3B-4bit', help='模型名称')
    parser.add_argument('--endpoint', type=str,
                       default='http://localhost:8000/v1/chat/completions',
                       help='API 端点')
    parser.add_argument('--no-resume', action='store_true',
                       help='不使用断点续译（重新开始）')

    args = parser.parse_args()

    translator = RobustEPUBTranslator(
        model=args.model,
        endpoint=args.endpoint
    )

    await translator.translate_epub(
        input_path=args.input,
        output_path=args.output,
        resume=not args.no_resume
    )


if __name__ == "__main__":
    asyncio.run(main())
