"""
Test EPUB translation using MLX provider with TranslateGemma model.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.llm.providers.mlx import MLXProvider
from src.config import OLLAMA_NUM_CTX


async def test_mlx_translation():
    """Test MLX provider with TranslateGemma model."""

    print("=" * 60)
    print("Testing MLX Provider with TranslateGemma")
    print("=" * 60)

    # Initialize MLX provider
    mlx_api_key = os.getenv('MLX_API_KEY', '')
    if not mlx_api_key:
        print("Error: MLX_API_KEY environment variable not set")
        sys.exit(1)

    provider = MLXProvider(
        api_endpoint="http://localhost:8000/v1/chat/completions",
        model="translategemma-12b-it-4bit",
        api_key=mlx_api_key,
        context_window=OLLAMA_NUM_CTX,
        log_callback=lambda level, msg: print(f"[{level}] {msg}")
    )

    print(f"\n✓ Provider initialized")
    print(f"  Model: {provider.model}")
    print(f"  Context window: {provider.context_window}")

    # Test text
    test_text = """
    Chapter 1: The Beginning

    This is a test of the translation system. The quick brown fox jumps over the lazy dog.
    We need to verify that the TranslateGemma model can properly translate English text to Chinese.
    """

    print(f"\n{'=' * 60}")
    print("Test Text:")
    print("=" * 60)
    print(test_text)

    print(f"\n{'=' * 60}")
    print("Sending translation request...")
    print("=" * 60)

    try:
        # Test translation
        result = await provider.generate(
            prompt=f"<<<source>>>english<<<target>>>chinese<<<text>>>{test_text}",
            timeout=120,
            system_prompt="You are a professional translator."
        )

        if result and result.content:
            print(f"\n{'=' * 60}")
            print("Translation Result:")
            print("=" * 60)
            print(result.content)

            print(f"\n{'=' * 60}")
            print("Metadata:")
            print("=" * 60)
            print(f"  Prompt tokens: {result.prompt_tokens}")
            print(f"  Completion tokens: {result.completion_tokens}")
            print(f"  Context used: {result.context_used}")
            print(f"  Context limit: {result.context_limit}")
            print(f"  Was truncated: {result.was_truncated}")

            print(f"\n✓ Translation test PASSED")
            return True
        else:
            print(f"\n✗ Translation FAILED: No result returned")
            return False

    except Exception as e:
        print(f"\n✗ Translation FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test entry point."""
    success = await test_mlx_translation()

    print(f"\n{'=' * 60}")
    if success:
        print("OVERALL RESULT: ✓ ALL TESTS PASSED")
    else:
        print("OVERALL RESULT: ✗ TESTS FAILED")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
