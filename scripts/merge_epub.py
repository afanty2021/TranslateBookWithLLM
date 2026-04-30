#!/usr/bin/env python3
"""
EPUB 合并工具 - 将多个独立翻译的 EPUB 部分合并为一个完整的 EPUB

用法：
    python3 merge_epub.py --input translated_files/v6_part*.epub --output translated_files/v6_complete.epub
"""
import sys
import os
import zipfile
import argparse
from pathlib import Path


class EPUBMerger:
    """EPUB 合并器"""

    def __init__(self):
        self.html_files = {}  # {file_path: content}
        self.resource_files = {}  # {file_path: content}
        self.mimetype = None

    def read_epub(self, epub_path: str):
        """读取 EPUB 文件内容"""
        print(f"📖 读取: {epub_path}")

        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()

            # 读取 mimetype（只读取一次）
            if self.mimetype is None and 'mimetype' in file_list:
                self.mimetype = zip_ref.read('mimetype')

            # 读取 HTML/XHTML 文件
            for file_path in file_list:
                if file_path.endswith(('.html', '.xhtml')) and not file_path.startswith('META-INF'):
                    if file_path not in self.html_files:
                        content = zip_ref.read(file_path)
                        self.html_files[file_path] = content
                        print(f"  ✓ {file_path}")

            # 读取资源文件（只读取不存在的）
            for file_path in file_list:
                if not file_path.endswith(('.html', '.xhtml')) and file_path != 'mimetype':
                    if file_path not in self.resource_files:
                        content = zip_ref.read(file_path)
                        self.resource_files[file_path] = content

    def merge_epubs(self, input_files: list, output_path: str):
        """合并多个 EPUB 文件"""
        print("=" * 70)
        print("🔀 EPUB 合并工具")
        print("=" * 70)
        print(f"输入文件: {len(input_files)} 个")
        for i, f in enumerate(input_files, 1):
            print(f"  {i}. {f}")
        print(f"输出文件: {output_path}")
        print("=" * 70)
        print()

        # 读取所有 EPUB 文件
        for epub_file in input_files:
            if not os.path.exists(epub_file):
                print(f"⚠️  文件不存在: {epub_file}")
                continue
            self.read_epub(epub_file)

        print()
        print(f"📊 统计:")
        print(f"  HTML 文件: {len(self.html_files)} 个")
        print(f"  资源文件: {len(self.resource_files)} 个")
        print()

        # 创建合并后的 EPUB
        print(f"💾 创建合并文件: {output_path}")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            # 1. 写入 mimetype（必须第一个，无压缩）
            if self.mimetype:
                zip_out.writestr('mimetype', self.mimetype, zipfile.ZIP_STORED)

            # 2. 写入资源文件
            for file_path, content in sorted(self.resource_files.items()):
                zip_out.writestr(file_path, content)

            # 3. 写入 HTML 文件
            for file_path, content in sorted(self.html_files.items()):
                zip_out.writestr(file_path, content)

        print()
        print("=" * 70)
        print("✅ 合并完成!")
        print(f"输出文件: {output_path}")
        print(f"文件大小: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
        print(f"包含文件: {len(self.html_files) + len(self.resource_files) + 1} 个")
        print("=" * 70)

    def verify_epub(self, epub_path: str):
        """验证 EPUB 文件完整性"""
        print()
        print(f"🔍 验证 EPUB 文件: {epub_path}")

        try:
            with zipfile.ZipFile(epub_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"  ✓ 文件可读取")
                print(f"  ✓ 包含 {len(file_list)} 个文件")

                # 检查必要文件
                if 'mimetype' in file_list:
                    print(f"  ✓ mimetype 存在")
                else:
                    print(f"  ⚠️  mimetype 缺失")

                html_count = len([f for f in file_list if f.endswith(('.html', '.xhtml'))])
                print(f"  ✓ HTML 文件: {html_count} 个")

        except Exception as e:
            print(f"  ❌ 验证失败: {e}")
            return False

        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='EPUB 合并工具')
    parser.add_argument('--input', nargs='+', required=True,
                       help='输入 EPUB 文件（支持通配符）')
    parser.add_argument('--output', required=True,
                       help='输出 EPUB 文件')
    parser.add_argument('--verify', action='store_true',
                       help='验证输出文件')

    args = parser.parse_args()

    # 展开通配符
    input_files = []
    for pattern in args.input:
        if '*' in pattern:
            # 手动展开通配符
            from glob import glob
            matched = glob(pattern)
            if matched:
                input_files.extend(sorted(matched))
        else:
            input_files.append(pattern)

    if not input_files:
        print("❌ 错误: 没有找到输入文件")
        return

    # 创建合并器并执行合并
    merger = EPUBMerger()
    merger.merge_epubs(input_files, args.output)

    # 验证输出文件
    if args.verify:
        merger.verify_epub(args.output)


if __name__ == "__main__":
    main()
