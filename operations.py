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


async def actualizar_equipo_sql(session: AsyncSession, equipo_id: int, nuevos_datos: dict):
    query = select(EquipoSQL).where(EquipoSQL.id == equipo_id)
    result = await session.execute(query)
    equipo = result.scalar_one_or_none()

    if equipo is None:
        return None

    # Solo permitir actualizar estos campos
    campos_permitidos = {"puntos", "goles_a_favor", "goles_en_contra"}
    for key in campos_permitidos:
        if key in nuevos_datos:
            setattr(equipo, key, nuevos_datos[key])

    session.add(equipo)
    await session.commit()
    await session.refresh(equipo)
    return equipo


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


async def actualizar_partido_sql(session: AsyncSession, partido_id: int, nuevos_datos: dict):
    query = select(PartidoSQL).where(PartidoSQL.id == partido_id)
    result = await session.execute(query)
    partido = result.scalar_one_or_none()

    if partido is None:
        return None

    # Solo permitir actualizar estos campos
    campos_permitidos = {"goles_local", "goles_visitante", "fase"}
    for key in campos_permitidos:
        if key in nuevos_datos:
            setattr(partido, key, nuevos_datos[key])

    session.add(partido)
    await session.commit()
    await session.refresh(partido)
    return partido


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
async def create_reporte_sql(session: AsyncSession, reporte: ReporteSQL):
    reporte.created_at = remove_tzinfo(reporte.created_at)

    reporte_db = ReporteSQL.model_validate(reporte, from_attributes=True)
    reporte_db.created_at = datetime.utcnow()

    session.add(reporte_db)
    await session.commit()
    await session.refresh(reporte_db)
    return reporte_db


async def obtener_todos_los_reportes(session: AsyncSession):
    query = select(ReporteSQL)
    result = await session.execute(query)
    return result.scalars().all()


async def obtener_reporte_por_id(session: AsyncSession, reporte_id: int):
    query = select(ReporteSQL).where(ReporteSQL.id == reporte_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def actualizar_reporte_sql(session: AsyncSession, reporte_id: int, nuevos_datos: dict):
    query = select(ReporteSQL).where(ReporteSQL.id == reporte_id)
    result = await session.execute(query)
    reporte = result.scalar_one_or_none()

    if reporte is None:
        return None

    # Solo permitir actualizar este campo
    if "ruta_archivo" in nuevos_datos:
        reporte.ruta_archivo = nuevos_datos["ruta_archivo"]

        session.add(reporte)
        await session.commit()
        await session.refresh(reporte)

    return reporte


async def eliminar_reporte_sql(session: AsyncSession, reporte_id: int):
    query = select(ReporteSQL).where(ReporteSQL.id == reporte_id)
    result = await session.execute(query)
    reporte = result.scalar_one_or_none()

    if reporte is None:
        return False

    await session.delete(reporte)
    await session.commit()
    return True