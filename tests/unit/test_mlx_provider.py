#!/usr/bin/env python3
"""
MLX Provider 测试脚本

用于验证 MLX Provider 配置是否正确工作。
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest

from src.core.llm import create_llm_provider
from src.config import MLX_API_ENDPOINT, MLX_MODEL, MLX_API_KEY


@pytest.mark.asyncio
async def test_mlx_provider():
    """测试 MLX Provider 连接和基本功能"""

    print("=" * 60)
    print("🧪 MLX Provider 测试")
    print("=" * 60)
    print()

    # 显示配置
    print("📋 当前配置:")
    print(f"   API Endpoint: {MLX_API_ENDPOINT}")
    print(f"   Model: {MLX_MODEL}")
    print(f"   API Key: {'***' + MLX_API_KEY[-4:] if MLX_API_KEY else '(未设置)'}")
    print()

    # 创建 provider
    print("🔧 创建 MLX Provider...")
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
        print()
        print("💡 请检查:")
        print("   1. MLX 服务器是否正在运行")
        print("   2. API endpoint 是否正确")
        print("   3. 网络连接是否正常")
        return False

    # 测试简单翻译
    print("🌍 测试翻译功能...")
    test_prompt = "<<<source>>>English<<<target>>>Chinese<<<text>>>Hello, world!"

    try:
        response = await provider.generate(
            test_prompt,
            system_prompt="You are a professional translator."
        )

        if response and response.content:
            print("✅ 翻译测试成功")
            print()
            print("📝 翻译结果:")
            print(f"   原文: Hello, world!")
            print(f"   译文: {response.content}")
            print()

            # 显示 token 使用情况
            if hasattr(response, 'usage') and response.usage:
                print("📊 Token 使用:")
                for key, value in response.usage.items():
                    print(f"   {key}: {value}")
            print()

            return True
        else:
            print("❌ 翻译测试失败: 无响应内容")
            return False

    except Exception as e:
        print(f"❌ 翻译测试失败: {e}")
        print()
        print("💡 可能的原因:")
        print("   1. 模型未正确加载")
        print("   2. API key 不正确（如果需要）")
        print("   3. 请求超时")
        return False


@pytest.mark.asyncio
async def test_standard_format():
    """测试标准翻译提示词格式"""

    print("=" * 60)
    print("📝 测试标准提示词格式")
    print("=" * 60)
    print()

    from prompts.prompts import generate_translategemma_prompt

    # 生成测试提示词
    prompt_pair = generate_translategemma_prompt(
        main_content="The quick brown fox jumps over the lazy dog.",
        source_language="English",
        target_language="Chinese"
    )

    print("✅ TranslateGemma 提示词生成成功")
    print()
    print("📋 系统提示词（前 200 字符）:")
    print(f"   {prompt_pair.system[:200]}...")
    print()
    print("📋 用户提示词:")
    print(f"   {prompt_pair.user}")
    print()

    return True


async def main():
    """主测试流程"""

    # 测试 1: MLX Provider
    provider_ok = await test_mlx_provider()

    # 测试 2: 提示词格式
    prompt_ok = await test_standard_format()

    # 总结
    print("=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print()
    print(f"   MLX Provider: {'✅ 通过' if provider_ok else '❌ 失败'}")
    print(f"   提示词格式:   {'✅ 通过' if prompt_ok else '❌ 失败'}")
    print()

    if provider_ok and prompt_ok:
        print("🎉 所有测试通过！MLX Provider 已准备就绪。")
        print()
        print("💡 下一步:")
        print("   1. 启动 MLX 服务器（如果还没启动）:")
        print("      mlx_lm.server --model mlx-community/translategemma-12b-it-4bit --port 8080")
        print()
        print("   2. 在 .env 文件中设置:")
        print("      LLM_PROVIDER=mlx")
        print()
        print("   3. 启动 TranslateBook with LLM:")
        print("      python translation_api.py")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
