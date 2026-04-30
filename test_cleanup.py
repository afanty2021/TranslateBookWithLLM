"""测试清理功能"""
import asyncio
import os
import sys
from src.core.llm.providers.mlx import MLXProvider
from src.config import OLLAMA_NUM_CTX

MLX_API_KEY = os.getenv('MLX_API_KEY', '')
if not MLX_API_KEY:
    print("Error: MLX_API_KEY environment variable not set")
    sys.exit(1)

async def test_cleanup():
    provider = MLXProvider(
        api_endpoint="http://localhost:8000/v1/chat/completions",
        model="translategemma-12b-it-4bit",
        api_key=MLX_API_KEY,
        context_window=OLLAMA_NUM_CTX
    )
    
    # 测试清理方法
    test_text = "你好，世界！<end_of_turn><end_of_turn><end_of_turn>"
    cleaned = provider._clean_model_artifacts(test_text)
    print(f"原始: {test_text}")
    print(f"清理后: {cleaned}")
    
    # 测试实际翻译
    result = await provider.generate(
        prompt="<<<source>>>english<<<target>>>chinese<<<text>>>Hello",
        timeout=60
    )
    
    if result:
        print(f"\n翻译结果:")
        print(result.content)

asyncio.run(test_cleanup())
