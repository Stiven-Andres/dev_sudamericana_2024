import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import pytest
from httpx import ASGITransport
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_error_personalizado():

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/error")  # endpoint que tú ya tienes
    data = response.json()
    assert response.status_code == 400
    assert data["message"] == "Ocurrió un error"