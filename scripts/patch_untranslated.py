#!/usr/bin/env python3
"""
断点续译脚本 - 检测并精准重译未翻译段落
"""
import sys
import os
import asyncio
import re
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from src.core.llm.providers.mlx import MLXProvider
from src.core.epub.epub_translate_helpers import EPUBTranslateHelper
from src.config import OLLAMA_NUM_CTX


def detect_untranslated_paragraphs(content: str) -> list:
    """
    检测未翻译的段落

    返回: [(段落完整内容, 开始位置, 结束位置), ...]
    """
    pattern = r'(<p[^>]*>.*?</p>)'
    untranslated = []

    for match in re.finditer(pattern, content, re.DOTALL):
        para_html = match.group(0)
        start = match.start()
        end = match.end()

        # 提取纯文本
        text_only = re.sub(r'<[^>]+>', ' ', para_html)
        text_only = re.sub(r'\s+', ' ', text_only).strip()

        # 跳过短文本
        if len(text_only) < 50:
            continue

        # 检查中英文比例
        chinese_chars = len(re.findall(r'[一-鿿]', text_only))
        english_chars = len(re.findall(r'[a-zA-Z]', text_only))
        total_chars = chinese_chars + english_chars

        if total_chars == 0:
            continue

        english_ratio = english_chars / total_chars

        # 如果英文占比超过80%且文本较长，判定为未翻译
        if english_ratio > 0.8 and len(text_only) > 100:
            untranslated.append((para_html, start, end))

    return untranslated


async def patch_file(file_path: str, helper: EPUBTranslateHelper) -> dict:
    """
    修复单个文件的未翻译段落

    返回: {"file": 文件名, "detected": 检测到的数量, "translated": 成功翻译的数量}
    """
    print(f"\n{'='*60}")
    print(f"检查文件: {Path(file_path).name}")
    print(f"{'='*60}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检测未翻译段落
    untranslated = detect_untranslated_paragraphs(content)

    if not untranslated:
        print("✅ 无未翻译段落")
        return {
            "file": Path(file_path).name,
            "detected": 0,
            "translated": 0
        }

    print(f"⚠️  发现 {len(untranslated)} 个未翻译段落")

    # 翻译未翻译的段落
    replacements = []
    success_count = 0

    for idx, (para_html, start, end) in enumerate(untranslated, 1):
        text_preview = re.sub(r'<[^>]+>', ' ', para_html)
        text_preview = re.sub(r'\s+', ' ', text_preview).strip()[:60]

        print(f"\n  段落 {idx}/{len(untranslated)}: {text_preview}...")

        translated_para = await helper.translate_paragraph(para_html)

        if translated_para:
            replacements.append((para_html, start, end, translated_para))
            success_count += 1
            print(f"    ✅ 成功 ({success_count}/{len(untranslated)})")
        else:
            print(f"    ❌ 失败")

        await asyncio.sleep(0.5)  # 避免过载

    # 合并翻译结果
    if replacements:
        # 从后往前替换，避免位置偏移
        result = content
        for orig_html, start, end, translated_html in sorted(replacements, key=lambda x: -x[1]):
            result = result[:start] + translated_html + result[end:]

        # 备份原文件
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n  💾 原文件已备份至: {backup_path}")

        # 写入修复后的文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"  ✅ 修复完成: {success_count}/{len(untranslated)} 个段落已翻译")
    else:
        print(f"  ⚠️  无段落翻译成功")

    return {
        "file": Path(file_path).name,
        "detected": len(untranslated),
        "translated": success_count
    }


async def main():
    """主函数"""
    print("=" * 60)
    print("断点续译脚本 - 检测并修复未翻译段落")
    print("=" * 60)
    print()

    # 初始化
    print("初始化翻译助手...")
    provider = MLXProvider(
        api_endpoint='http://localhost:8000/v1/chat/completions',
        model='Qwen3.6-35B-A3B-4bit',
        api_key='siRfoz-giffab-muqko4',
        context_window=OLLAMA_NUM_CTX
    )
    helper = EPUBTranslateHelper(provider, lambda lvl, msg: print(f"[{lvl}] {msg}"))

    # 查找已翻译的文件
    translated_dir = Path('translated/chapters')
    translated_files = sorted(translated_dir.glob('*.translated'))

    if not translated_files:
        print("❌ 未找到翻译文件")
        return

    print(f"找到 {len(translated_files)} 个翻译文件")
    print()

    # 统计信息
    total_detected = 0
    total_translated = 0
    files_with_issues = []

    # 逐个文件检查和修复
    for file_path in translated_files:
        result = await patch_file(str(file_path), helper)

        total_detected += result['detected']
        total_translated += result['translated']

        if result['detected'] > 0:
            files_with_issues.append(result['file'])

    # 汇总报告
    print()
    print("=" * 60)
    print("📊 修复汇总报告")
    print("=" * 60)
    print(f"扫描文件数: {len(translated_files)}")
    print(f"发现问题文件: {len(files_with_issues)}")
    print(f"检测到未翻译: {total_detected} 个段落")
    print(f"成功翻译: {total_translated} 个段落")
    print(f"成功率: {(total_translated/total_detected*100) if total_detected > 0 else 100:.1f}%")
    print()

    if files_with_issues:
        print("问题文件列表:")
        for f in files_with_issues:
            print(f"  - {f}")
    else:
        print("✅ 所有文件完美，无需修复")

    await provider.close()

    print()
    print("✅ 断点续译完成!")


if __name__ == "__main__":
    asyncio.run(main())
