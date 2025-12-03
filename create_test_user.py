import pytest
from sqlmodel import select
from models import UsuarioSQL
from utils.connection_db import async_session  # tu archivo de conexión

@pytest.mark.asyncio
async def crear_usuario_test():
    async with async_session() as session:
        # ¿Existe ya?
        result = await session.execute(
            select(UsuarioSQL).where(UsuarioSQL.nombre_usuario == "admin_test")
        )
        existe = result.scalar_one_or_none()

        if existe:
            return existe  # ya está creado

        usuario = UsuarioSQL(
            nombre_usuario="admin",
            correo="admin@test.com",
            contraseña="admin1234",      # tu login NO usa hashing
            rol="admin"
        )

        session.add(usuario)
        await session.commit()
        await session.refresh(usuario)

        return usuario

