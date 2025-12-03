import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
import os
import sys
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app


@pytest.mark.asyncio
async def test_login_correcto():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/login", data={
            "nombre_usuario": "admin1",
            "contraseña": "1234"
        })
    assert response.status_code in (200, 303) # redirección correcta


@pytest.mark.asyncio
async def test_login_incorrecto():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/login", data={
            "nombre_usuario": "fake",
            "contraseña": "123"
        })
    assert "Credenciales incorrectas" in response.text