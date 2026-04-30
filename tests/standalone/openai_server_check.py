#!/usr/bin/env python3
"""Test rapide du serveur OpenAI compatible"""
import requests
import json

# Configuration
ENDPOINT = "http://ai_server.mds.com/v1/chat/completions"
API_KEY = ""  # Laissez vide si pas de clé requise
MODEL = "gpt-3.5-turbo"  # Adaptez selon votre serveur

headers = {
    "Content-Type": "application/json"
}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

# Test 1: Liste des modèles
print("=" * 50)
print("Test 1: Récupération des modèles")
print("=" * 50)
try:
    resp = requests.get(ENDPOINT.replace('/chat/completions', '/models'), 
                        headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        models = resp.json()
        print(f"✅ Serveur accessible!")
        print(f"Modèles disponibles: {len(models.get('data', []))}")
        for m in models.get('data', [])[:5]:
            print(f"  - {m.get('id')}")
    else:
        print(f"❌ Erreur: {resp.text}")
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")

# Test 2: Requête de chat simple
print()
print("=" * 50)
print("Test 2: Requête de chat")
print("=" * 50)
payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "Vous êtes un assistant utile."},
        {"role": "user", "content": "Dites 'Test réussi!' en français."}
    ],
    "temperature": 0.7
}

try:
    resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        message = result['choices'][0]['message']['content']
        print(f"✅ Réponse reçue!")
        print(f"Réponse: {message}")
    else:
        print(f"❌ Erreur: {resp.text}")
except Exception as e:
    print(f"❌ Erreur: {e}")
