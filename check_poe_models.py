import asyncio
import os
import sys
import httpx

POE_API_KEY = os.getenv('POE_API_KEY', '')
if not POE_API_KEY:
    print("Error: POE_API_KEY environment variable not set")
    sys.exit(1)

async def list_poe_models():
    api_key = POE_API_KEY
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                'https://api.poe.com/v1/models',
                headers=headers
            )
            print(f'Status: {response.status_code}')
            if response.status_code == 200:
                data = response.json()
                models = data.get('data', [])
                print(f'Total models: {len(models)}')
                
                # Filtrer les modèles Gemini
                gemini_models = [m for m in models if 'gemini' in m.get('id', '').lower()]
                print(f'\nModèles Gemini disponibles sur POE ({len(gemini_models)}):')
                for m in gemini_models:
                    print(f"  - {m.get('id')}")
                if not gemini_models:
                    print('  (aucun modèle Gemini trouvé)')
                    print('\nTous les modèles disponibles:')
                    for m in models[:30]:  # Limiter à 30
                        print(f"  - {m.get('id')}")
            else:
                print(f'Error: {response.text[:500]}')
        except Exception as e:
            print(f'Exception: {e}')

asyncio.run(list_poe_models())
