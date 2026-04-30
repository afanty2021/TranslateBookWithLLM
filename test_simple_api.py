"""
Simple test for MLX API call.
"""
import asyncio
import os
import sys
import httpx
import json

MLX_API_KEY = os.getenv('MLX_API_KEY', '')
if not MLX_API_KEY:
    print("Error: MLX_API_KEY environment variable not set")
    sys.exit(1)

async def test_api():
    """Test API call directly."""
    url = "http://localhost:8000/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MLX_API_KEY}"
    }

    # Test with TranslateGemma format
    payload = {
        "model": "translategemma-12b-it-4bit",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "source_lang_code": "en",
                        "target_lang_code": "zh",
                        "text": "Hello, world!"
                    }
                ]
            }
        ],
        "max_tokens": 100,
        "stream": False
    }

    print(f"Sending request to {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            print(f"\nResponse status: {response.status_code}")
            print(f"Response keys: {result.keys()}")

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                print(f"\nTranslated content:\n{content}")
            else:
                print(f"\nFull response:\n{json.dumps(result, indent=2)}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api())
