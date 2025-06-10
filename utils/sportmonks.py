import httpx
import os

SPORTMONKS_API_TOKEN = "EhV0Y8rSu6qiN6HzC95YL1Fm0SpWauK8lcWZ2Ugxkiy3QMMjfDdGfNJNSjiV"  # reemplaza con tu token real
BASE_URL = "https://api.sportmonks.com/v3/football"

headers = {
    "Authorization": f"Bearer {SPORTMONKS_API_TOKEN}"
}

async def get_equipos_copa_sudamericana():
    url = f"{BASE_URL}/teams?include=country&filters[season]=21657"  # ajusta el ID del torneo
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()