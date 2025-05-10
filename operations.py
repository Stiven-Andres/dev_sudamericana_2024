from sqlalchemy.future import select
from sqlalchemy import update
from models import EquipoSQL, PartidoSQL, ReporteSQL
from datetime import datetime
from typing import Dict, Any, Optional
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

def remove_tzinfo(dt: Optional[datetime | str]) -> Optional[datetime]:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)  # convierte string a datetime
    if isinstance(dt, datetime) and dt.tzinfo:
        return dt.replace(tzinfo=None)
    return dt

async def create_equipo_sql(session: AsyncSession, equipo: EquipoSQL):
    equipo_db = EquipoSQL.model_validate(equipo, from_attributes=True)
    session.add(equipo_db)
    await session.commit()
    await session.refresh(equipo_db)
    return equipo_db


async def obtener_todos_los_equipos(session: AsyncSession):
    query = select(EquipoSQL)
    result = await session.execute(query)
    return result.scalars().all()


async def obtener_equipo_por_id(session: AsyncSession, equipo_id: int):
    query = select(EquipoSQL).where(EquipoSQL.id == equipo_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

#--------------------------actualizar equipo


async def eliminar_equipo_sql(session: AsyncSession, equipo_id: int):
    query = select(EquipoSQL).where(EquipoSQL.id == equipo_id)
    result = await session.execute(query)
    equipo = result.scalar_one_or_none()

    if equipo is None:
        return False

    await session.delete(equipo)
    await session.commit()
    return True

# --------------------------------------------------------- operations Partido -----------------------------------------------------------------------------

async def create_partido_sql(session: AsyncSession, partido: PartidoSQL):
    partido.created_at = remove_tzinfo(partido.created_at)

    partido_db = PartidoSQL.model_validate(partido, from_attributes=True)
    partido_db.created_at = datetime.utcnow()

    session.add(partido_db)
    await session.commit()
    await session.refresh(partido_db)
    return partido_db


async def obtener_todos_los_partidos(session: AsyncSession):
    query = select(PartidoSQL)
    result = await session.execute(query)
    return result.scalars().all()


async def obtener_partido_por_id(session: AsyncSession, partido_id: int):
    query = select(PartidoSQL).where(PartidoSQL.id == partido_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


#--------------------------actualizar partido


async def eliminar_partido_sql(session: AsyncSession, partido_id: int):
    query = select(PartidoSQL).where(PartidoSQL.id == partido_id)
    result = await session.execute(query)
    partido = result.scalar_one_or_none()

    if partido is None:
        return False

    await session.delete(partido)
    await session.commit()
    return True

# --------------------------------------------------------- operations Reporte -----------------------------------------------------------------------------
