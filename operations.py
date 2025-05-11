from sqlalchemy.future import select
from sqlalchemy import update
from models import EquipoSQL, PartidoSQL
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

    # Buscar equipos
    local = await session.get(EquipoSQL, partido.equipo_local_id)
    visitante = await session.get(EquipoSQL, partido.equipo_visitante_id)

    if local:
        local.tarjetas_amarillas += partido.tarjetas_amarillas_local
        local.tarjetas_rojas += partido.tarjetas_rojas_local
        local.tiros_esquina += partido.tiros_esquina_local
        local.tiros_libres += partido.tiros_libres_local
        local.goles_a_favor += partido.goles_local
        local.goles_en_contra += partido.goles_visitante
        local.faltas += partido.faltas_local
        local.fueras_de_juego += partido.fueras_de_juego_local
        local.pases += partido.pases_local

    if visitante:
        visitante.tarjetas_amarillas += partido.tarjetas_amarillas_visitante
        visitante.tarjetas_rojas += partido.tarjetas_rojas_visitante
        visitante.tiros_esquina += partido.tiros_esquina_visitante
        visitante.tiros_libres += partido.tiros_libres_visitante
        visitante.goles_a_favor += partido.goles_visitante
        visitante.goles_en_contra += partido.goles_local
        visitante.faltas += partido.faltas_visitante
        visitante.fueras_de_juego += partido.fueras_de_juego_visitante
        visitante.pases += partido.pases_visitante

    # Guardar cambios
    session.add_all([local, visitante])
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
