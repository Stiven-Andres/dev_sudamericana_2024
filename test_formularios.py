import io
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
import pytest
from main import app
from httpx import AsyncClient
from httpx import ASGITransport
from asgi_lifespan import LifespanManager




@pytest.mark.asyncio
async def test_crear_equipo():
    fake_image = io.BytesIO(b"fake image content")
    fake_image.name = "logo.png"

    data = {
        "nombre": "EquipoPrueba",
        "pais": "Argentina",
        "grupo": "A",
        "puntos": "5",
        "esta_activo": "true",
    }

    files = {
        "logo": ("logo.png", fake_image, "image/png"),
    }

    transport = ASGITransport(app=app)

    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/equipos/", data=data, files=files)

    assert response.status_code == 303


@pytest.mark.asyncio
async def test_actualizar_equipo_no_existe():
    transport = ASGITransport(app=app)
    equipo_id = 9999

    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put(
                f"/equipos/{equipo_id}/actualizar-grupo-puntos",
                params={"grupo": "B", "puntos": 6}
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_eliminar_equipo_inexistente():
    transport = ASGITransport(app=app)
    equipo_id = 9999

    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.delete(f"/equipos/{equipo_id}")

    assert response.status_code == 404