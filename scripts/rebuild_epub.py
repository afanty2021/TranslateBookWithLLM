#!/usr/bin/env python3
"""
重新组装翻译后的EPUB文件
"""
import os
import shutil
import zipfile
from pathlib import Path


def rebuild_epub():
    """重新组装EPUB"""
    print("=" * 60)
    print("重新组装翻译后的EPUB")
    print("=" * 60)

    project_root = Path(__file__).parent.parent
    translated_dir = project_root / 'translated' / 'chapters'
    rebuild_dir = project_root / 'rebuild_epub'
    output_dir = project_root / 'translated_books'
    output_dir.mkdir(exist_ok=True)

    # 复制翻译文件到EPUB结构
    print("\n1. 复制翻译文件...")
    xhtml_dir = rebuild_dir / 'ops' / 'xhtml'

    for translated_file in sorted(translated_dir.glob('*.translated')):
        # 提取原始文件名
        # ops_xhtml_ch01.html.translated -> ch01.html
        name_without_ext = translated_file.name.replace('.translated', '')
        if name_without_ext.startswith('ops_xhtml_'):
            original_name = name_without_ext.replace('ops_xhtml_', '')
        elif name_without_ext.startswith('ops_'):
            original_name = name_without_ext.replace('ops_', '')
        else:
            original_name = name_without_ext

        target_path = xhtml_dir / original_name

        # 读取翻译内容
        with open(translated_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 写入目标文件
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ {original_name}")

    print(f"\n  共复制 {len(list(translated_dir.glob('*.translated')))} 个文件")

    # 打包EPUB
    print("\n2. 打包EPUB...")
    output_epub = output_dir / '伟大的数学问题 (中文翻译).epub'

    # 删除旧文件
    if output_epub.exists():
        output_epub.unlink()

    # 创建ZIP文件（EPUB就是ZIP）
    with zipfile.ZipFile(output_epub, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加mimetype（必须第一个且无压缩）
        mimetype_path = rebuild_dir / 'mimetype'
        with open(mimetype_path, 'rb') as f:
            zf.writestr('mimetype', f.read())

        # 添加其他文件
        for root, dirs, files in os.walk(rebuild_dir):
            # 跳过mimetype（已添加）
            if 'mimetype' in files:
                files.remove('mimetype')

            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(rebuild_dir)
                zf.write(file_path, arcname)

    print(f"  ✓ EPUB已创建: {output_epub}")
    print(f"  文件大小: {output_epub.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 60)
    print("✅ EPUB重新组装完成！")
    print("=" * 60)

    return output_epub


if __name__ == "__main__":
    rebuild_epub()
