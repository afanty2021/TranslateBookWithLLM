#!/usr/bin/env python3
"""
EPUB 翻译快速测试脚本 - MLX Provider

使用 MLX Provider 快速测试 EPUB 翻译功能。
"""
import sys
import os
import asyncio
import zipfile
import re
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def extract_epub_main_text(epub_path: str, max_chars: int = 800) -> str:
    """
    从 EPUB 文件中提取主要正文内容

    Args:
        epub_path: EPUB 文件路径
        max_chars: 最大字符数

    Returns:
        提取的正文文本
    """
    print("=" * 60)
    print("📖 EPUB 正文提取")
    print("=" * 60)
    print()

    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            # 优先查找 text 目录下的文件
            html_files = [f for f in zip_ref.namelist()
                         if 'text' in f.lower() and f.endswith(('.html', '.xhtml'))]

            if not html_files:
                html_files = [f for f in zip_ref.namelist()
                             if f.endswith(('.html', '.xhtml')) and not f.startswith('META-INF')]

            print(f"✓ 找到 {len(html_files)} 个内容文件")
            print()

            for html_file in html_files:
                try:
                    with zip_ref.open(html_file) as f:
                        content = f.read().decode('utf-8', errors='ignore')

                        # 移除HTML标签
                        text = re.sub(r'<[^>]+>', ' ', content)
                        text = re.sub(r'\s+', ' ', text).strip()

                        # 过滤掉太短的内容和CSS代码
                        if len(text) > 200 and '@page' not in text and 'margin:0pt' not in text:
                            print(f"✓ 提取正文: {html_file}")
                            print()
                            return text[:max_chars]

                except Exception:
                    continue

        print("⚠️  未找到合适的正文内容")
        return ""

    except Exception as e:
        print(f"❌ EPUB 读取失败: {e}")
        return ""


async def test_mlx_translation(text: str, source_lang: str = "English", target_lang: str = "Chinese"):
    """测试 MLX Provider 翻译"""
    from src.core.llm import create_llm_provider
    from src.config import MLX_API_ENDPOINT, MLX_MODEL, MLX_API_KEY

    print("=" * 60)
    print("🤖 MLX Provider 翻译测试")
    print("=" * 60)
    print()

    print("📋 配置:")
    print(f"   Endpoint: {MLX_API_ENDPOINT}")
    print(f"   Model: {MLX_MODEL}")
    print()

    try:
        provider = create_llm_provider(
            "mlx",
            api_endpoint=MLX_API_ENDPOINT,
            model=MLX_MODEL,
            api_key=MLX_API_KEY
        )
        print("✅ Provider 创建成功")
        print()
    except Exception as e:
        print(f"❌ Provider 创建失败: {e}")
        return None

    # TranslateGemma 特殊格式: <<<source>>>English<<<target>>>Chinese<<<text>>>Hello, world!
    prompt = f"<<<source>>>{source_lang}<<<target>>>{target_lang}<<<text>>>{text}"

    print("🌍 开始翻译...")
    print(f"📝 提示词格式: {prompt[:100]}...")
    print()

    try:
        # MLXProvider 会自动将提示词转换为 TranslateGemma 格式
        response = await provider.generate(
            prompt,
            system_prompt=None  # TranslateGemma 不使用 system prompt
        )

        if response and response.content:
            print("✅ 翻译完成")
            print()
            return response.content
        else:
            print("❌ 翻译失败: 无响应内容")
            return None

    except Exception as e:
        print(f"❌ 翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """主测试流程"""
    import argparse

    parser = argparse.ArgumentParser(description='EPUB 翻译快速测试脚本 - MLX Provider')
    parser.add_argument('input_file', nargs='?', help='输入 EPUB 文件路径')

    args = parser.parse_args()

    print()
    print("🎚️  EPUB 翻译测试 - MLX Provider")
    print()

    if not args.input_file:
        parser.error('input_file is required')

    # EPUB 文件路径
    epub_path = args.input_file

    # 检查文件
    if not os.path.exists(epub_path):
        print(f"❌ 文件不存在: {epub_path}")
        return 1

    # 提取正文
    text = extract_epub_main_text(epub_path, max_chars=800)

    if not text:
        print("❌ 无法提取 EPUB 正文")
        return 1

    print("=" * 60)
    print("📝 翻译测试")
    print("=" * 60)
    print()

    print("📄 原文:")
    print("-" * 60)
    print(text)
    print("-" * 60)
    print()

    translation = await test_mlx_translation(text)

    if translation:
        print("📖 译文:")
        print("-" * 60)
        print(translation)
        print("-" * 60)
        print()

        # 保存测试结果
        output_path = epub_path.replace('.epub', '_mlx_test.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"原文:\n{text}\n\n")
            f.write(f"译文:\n{translation}\n")

        print(f"💾 测试结果已保存到: {output_path}")
        print()
        print("🎉 测试完成!")
        print()
        print("💡 下一步:")
        print("   - 如果翻译质量满意，可以使用 Web UI 进行完整翻译")
        print("   - 启动命令: python translation_api.py")
        print("   - 访问: http://127.0.0.1:5000")

        return 0
    else:
        print("❌ 翻译测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
