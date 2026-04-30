#!/usr/bin/env python3
"""
PDF 翻译辅助工具

提取 PDF 文本并使用 MLX Provider 进行翻译测试。
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def install_pdf_library():
    """安装 PDF 处理库"""
    import subprocess
    print("📦 安装 pdfplumber 库...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    print("✅ 安装完成")


def extract_pdf_text(pdf_path: str, max_pages: int = None) -> str:
    """
    从 PDF 文件中提取文本

    Args:
        pdf_path: PDF 文件路径
        max_pages: 最大提取页数（用于测试）

    Returns:
        提取的文本内容
    """
    try:
        import pdfplumber
    except ImportError:
        install_pdf_library()
        import pdfplumber

    print(f"📖 读取 PDF 文件: {pdf_path}")
    print()

    extracted_text = []
    total_pages = 0

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"📄 总页数: {total_pages}")
        print()

        # 限制页数用于测试
        if max_pages:
            pages_to_process = min(max_pages, total_pages)
            print(f"🔍 测试模式: 仅处理前 {pages_to_process} 页")
            print()
        else:
            pages_to_process = total_pages

        for i, page in enumerate(pdf.pages[:pages_to_process], 1):
            text = page.extract_text()
            if text:
                extracted_text.append(f"--- 第 {i} 页 ---\n\n{text}\n")
            print(f"✓ 已处理第 {i}/{pages_to_process} 页")

    print()
    print("✅ 文本提取完成")
    print()

    return "\n".join(extracted_text)


async def translate_with_mlx(text: str, source_lang: str = "English", target_lang: str = "Chinese"):
    """
    使用 MLX Provider 翻译文本

    Args:
        text: 要翻译的文本
        source_lang: 源语言
        target_lang: 目标语言

    Returns:
        翻译结果
    """
    from src.core.llm import create_llm_provider
    from src.config import MLX_API_ENDPOINT, MLX_MODEL, MLX_API_KEY

    print("🤖 初始化 MLX Provider...")
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

        # 构建翻译提示词（TranslateGemma 格式）
        prompt = f"<<<source>>>{source_lang}<<<target>>>{target_lang}<<<text>>>{text}"

        print("🌍 开始翻译...")
        print()

        response = await provider.generate(
            prompt,
            system_prompt="You are a professional translator specializing in technical and financial content."
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
        print()
        print("💡 请检查:")
        print("   1. MLX 服务器是否正在运行")
        print("   2. 模型是否已加载")
        print("   3. API 配置是否正确")
        return None


def save_translation(text: str, output_path: str):
    """保存翻译结果到文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"💾 翻译已保存到: {output_path}")
    print()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='PDF 翻译测试工具')
    parser.add_argument('input_file', nargs='?', help='输入 PDF 文件路径')

    args = parser.parse_args()

    print("=" * 60)
    print("📚 PDF 翻译测试工具")
    print("=" * 60)
    print()

    if not args.input_file:
        parser.error('input_file is required')

    # PDF 文件路径
    pdf_path = args.input_file

    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return 1

    # 提取文本（测试模式：仅前 3 页）
    print("📝 步骤 1: 提取 PDF 文本")
    print("-" * 60)
    extracted_text = extract_pdf_text(pdf_path, max_pages=3)

    if not extracted_text:
        print("❌ 无法提取 PDF 文本")
        return 1

    # 保存提取的文本
    txt_path = pdf_path.replace('.pdf', '_extracted.txt')
    save_translation(extracted_text, txt_path)

    # 翻译测试
    print("🌍 步骤 2: 翻译测试")
    print("-" * 60)

    # 取第一页内容进行翻译测试
    first_page = extracted_text.split('---')[1] if '---' in extracted_text else extracted_text

    print("📄 翻译内容（第一页前 500 字符）:")
    print(f"   {first_page[:500]}...")
    print()

    translation = await translate_with_mlx(first_page, source_lang="English", target_lang="Chinese")

    if translation:
        print("📖 翻译结果:")
        print("=" * 60)
        print(translation)
        print("=" * 60)
        print()

        # 保存翻译结果
        output_path = pdf_path.replace('.pdf', '_translated.txt')
        save_translation(translation, output_path)

        print("🎉 测试完成!")
        print()
        print("💡 下一步:")
        print("   - 如果翻译质量满意，可以翻译完整文档")
        print("   - 调整提示词以优化特定领域的翻译")
        print("   - 使用 TranslateBook Web UI 进行完整翻译")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
