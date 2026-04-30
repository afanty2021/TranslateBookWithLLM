#!/usr/bin/env python3
"""
章节合并工具 - 将翻译后的章节合并为完整的 EPUB

用法：
    python3 merge_chapters_to_epub.py
"""
import sys
import os
import zipfile
import json
from pathlib import Path


def merge_chapters_to_epub(
    input_epub: str,
    chapter_dir: str,
    output_epub: str
):
    """
    将翻译后的章节合并到 EPUB 文件中

    Args:
        input_epub: 原始 EPUB 文件
        chapter_dir: 翻译章节目录
        output_epub: 输出 EPUB 文件
    """
    print("=" * 70)
    print("🔀 章节合并工具")
    print("=" * 70)
    print(f"原始 EPUB: {input_epub}")
    print(f"章节目录: {chapter_dir}")
    print(f"输出 EPUB: {output_epub}")
    print("=" * 70)
    print()

    # 读取翻译进度
    progress_file = os.path.join(chapter_dir, "progress.json")
    progress = {}

    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)

    print(f"📊 翻译进度:")
    completed = [k for k, v in progress.items() if v.get("status") == "completed"]
    print(f"  已完成: {len(completed)} 个章节")
    print()

    if not completed:
        print("❌ 错误: 没有找到已翻译的章节")
        return

    # 读取原始 EPUB
    print(f"📖 读取原始 EPUB...")
    with zipfile.ZipFile(input_epub, 'r') as zip_ref:
        file_list = zip_ref.namelist()

        # 创建新的 EPUB
        print(f"💾 创建合并后的 EPUB...")
        with zipfile.ZipFile(output_epub, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            # 1. 写入 mimetype
            if 'mimetype' in file_list:
                content = zip_ref.read('mimetype')
                zip_out.writestr('mimetype', content, zipfile.ZIP_STORED)

            # 2. 写入资源文件
            resource_count = 0
            for file_path in file_list:
                if file_path.endswith(('.html', '.xhtml')) or file_path == 'mimetype':
                    continue
                content = zip_ref.read(file_path)
                zip_out.writestr(file_path, content)
                resource_count += 1
            print(f"  已复制 {resource_count} 个资源文件")

            # 3. 写入 HTML 文件（使用翻译版本或原始版本）
            html_count = 0
            translated_count = 0

            for file_path in file_list:
                if not file_path.endswith(('.html', '.xhtml')) or file_path.startswith('META-INF'):
                    continue

                # 检查是否有翻译版本
                chapter_file = os.path.join(chapter_dir, f"{file_path.replace('/', '_')}.translated")

                if os.path.exists(chapter_file):
                    # 使用翻译版本
                    with open(chapter_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    zip_out.writestr(file_path, content.encode('utf-8'))
                    translated_count += 1
                else:
                    # 使用原始版本
                    content = zip_ref.read(file_path)
                    zip_out.writestr(file_path, content)

                html_count += 1

            print(f"  已处理 {html_count} 个 HTML 文件")
            print(f"  其中 {translated_count} 个使用翻译版本")

    print()
    print("=" * 70)
    print("✅ 合并完成!")
    print(f"输出文件: {output_epub}")
    print(f"文件大小: {os.path.getsize(output_epub) / 1024 / 1024:.2f} MB")
    print("=" * 70)


def verify_epub(epub_path: str):
    """验证 EPUB 文件"""
    print()
    print(f"🔍 验证 EPUB 文件: {epub_path}")

    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            print(f"  ✓ 文件可读取")
            print(f"  ✓ 包含 {len(file_list)} 个文件")

            if 'mimetype' in file_list:
                print(f"  ✓ mimetype 存在")

            html_files = [f for f in file_list if f.endswith(('.html', '.xhtml'))]
            print(f"  ✓ HTML 文件: {len(html_files)} 个")

        return True

    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        return False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='章节合并工具')
    parser.add_argument('--input', type=str, required=True,
                       help='原始 EPUB 文件')
    parser.add_argument('--chapter-dir', type=str,
                       default="translated/chapters",
                       help='翻译章节目录')
    parser.add_argument('--output', type=str, required=True,
                       help='输出 EPUB 文件')
    parser.add_argument('--verify', action='store_true',
                       help='验证输出文件')

    args = parser.parse_args()

    # 执行合并
    merge_chapters_to_epub(
        input_epub=args.input,
        chapter_dir=args.chapter_dir,
        output_epub=args.output
    )

    # 验证
    if args.verify:
        verify_epub(args.output)


if __name__ == "__main__":
    main()
