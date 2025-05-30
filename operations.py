from sqlalchemy.future import select
import unicodedata
from sqlalchemy import update
from fastapi import HTTPException
from models import *
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlmodel import Session
from sqlalchemy import func, text
from sqlmodel.ext.asyncio.session import AsyncSession

def normalizar_nombre(nombre: str) -> str:
    nombre = nombre.lower()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))  # Elimina tildes
    return nombre

def remove_tzinfo(dt: Optional[datetime | str]) -> Optional[datetime]:
    if isinstance(dt, str):
        # Reemplaza 'Z' por '+00:00' para que sea compatible con fromisoformat
        if dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt)
    if isinstance(dt, datetime) and dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt



def restar_valor(valor_actual, valor_a_restar):
    return max(0, valor_actual - valor_a_restar)


async def create_equipo_sql(session: AsyncSession, equipo: EquipoSQL):
    if equipo.id <= 0:
        raise HTTPException(status_code=400, detail="El ID del equipo no puede ser 0 o negativo")

    # Verificar si ya existe un equipo con ese ID
    existente = await session.get(EquipoSQL, equipo.id)
    if existente:
        raise HTTPException(status_code=409, detail=f"Ya existe un equipo con ID {equipo.id}")

    # Normalizar el nombre del nuevo equipo
    nombre_normalizado_nuevo = normalizar_nombre(equipo.nombre)

    # Verificar si ya existe un equipo con nombre similar (normalizado)
    result = await session.execute(select(EquipoSQL))
    equipos_existentes = result.scalars().all()

    for eq in equipos_existentes:
        if normalizar_nombre(eq.nombre) == nombre_normalizado_nuevo:
            raise HTTPException(status_code=409, detail=f"Ya existe un equipo con un nombre equivalente: {eq.nombre}")

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

async def actualizar_datos_equipo(
    session: AsyncSession,
    equipo_id: int,
    nuevo_grupo: Optional[str] = None,
    nuevos_puntos: Optional[int] = None
):
    equipo = await session.get(EquipoSQL, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    if nuevo_grupo is not None:
        equipo.grupo = nuevo_grupo

    if nuevos_puntos is not None:
        equipo.puntos = nuevos_puntos

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
    # Verificación de ID válido
    if partido.id is None or partido.id <= 0:
        raise HTTPException(status_code=400, detail="El ID del partido debe ser mayor que 0")

    # Verificar si el partido ya existe
    existente = await session.get(PartidoSQL, partido.id)
    if existente:
        raise HTTPException(status_code=409, detail=f"Ya existe un partido con ID {partido.id}")

    # ⚠️ Validar que los equipos no sean el mismo
    if partido.equipo_local_id == partido.equipo_visitante_id:
        raise HTTPException(status_code=400, detail="El equipo local y el equipo visitante no pueden ser el mismo")

    def default(value):
        return value if value is not None else 0

    partido.created_at = remove_tzinfo(partido.created_at)
    partido.updated_at = remove_tzinfo(partido.updated_at)


    partido_db = PartidoSQL.model_validate(partido, from_attributes=True)
    partido_db.created_at = datetime.now()
    session.add(partido_db)

    # Obtener los equipos
    local = await session.get(EquipoSQL, partido.equipo_local_id)
    visitante = await session.get(EquipoSQL, partido.equipo_visitante_id)

    if not local or not visitante:
        raise HTTPException(status_code=404, detail="Equipo local o visitante no encontrado")

    # Actualizar estadísticas
    local.tarjetas_amarillas += default(partido.tarjetas_amarillas_local)
    local.tarjetas_rojas += default(partido.tarjetas_rojas_local)
    local.tiros_esquina += default(partido.tiros_esquina_local)
    local.tiros_libres += default(partido.tiros_libres_local)
    local.goles_a_favor += default(partido.goles_local)
    local.goles_en_contra += default(partido.goles_visitante)
    local.faltas += default(partido.faltas_local)
    local.fueras_de_juego += default(partido.fueras_de_juego_local)
    local.pases += default(partido.pases_local)

    visitante.tarjetas_amarillas += default(partido.tarjetas_amarillas_visitante)
    visitante.tarjetas_rojas += default(partido.tarjetas_rojas_visitante)
    visitante.tiros_esquina += default(partido.tiros_esquina_visitante)
    visitante.tiros_libres += default(partido.tiros_libres_visitante)
    visitante.goles_a_favor += default(partido.goles_visitante)
    visitante.goles_en_contra += default(partido.goles_local)
    visitante.faltas += default(partido.faltas_visitante)
    visitante.fueras_de_juego += default(partido.fueras_de_juego_visitante)
    visitante.pases += default(partido.pases_visitante)

    session.add(local)
    session.add(visitante)

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



async def eliminar_partido_sql(session: AsyncSession, partido_id: int):
    query = select(PartidoSQL).where(PartidoSQL.id == partido_id)
    result = await session.execute(query)
    partido = result.scalar_one_or_none()

    if partido is None:
        return False

    # Obtener los equipos involucrados
    equipo_local = await session.get(EquipoSQL, partido.equipo_local_id)
    equipo_visitante = await session.get(EquipoSQL, partido.equipo_visitante_id)

    if not equipo_local or not equipo_visitante:
        return False

    # Revertir estadísticas del equipo local
    equipo_local.goles_a_favor = restar_valor(equipo_local.goles_a_favor, partido.goles_local)
    equipo_local.goles_en_contra = restar_valor(equipo_local.goles_en_contra, partido.goles_visitante)
    equipo_local.tarjetas_amarillas = restar_valor(equipo_local.tarjetas_amarillas, partido.tarjetas_amarillas_local)
    equipo_local.tarjetas_rojas = restar_valor(equipo_local.tarjetas_rojas, partido.tarjetas_rojas_local)
    equipo_local.tiros_esquina = restar_valor(equipo_local.tiros_esquina, partido.tiros_esquina_local)
    equipo_local.tiros_libres = restar_valor(equipo_local.tiros_libres, partido.tiros_libres_local)
    equipo_local.faltas = restar_valor(equipo_local.faltas, partido.faltas_local)
    equipo_local.fueras_de_juego = restar_valor(equipo_local.fueras_de_juego, partido.fueras_de_juego_local)
    equipo_local.pases = restar_valor(equipo_local.pases, partido.pases_local)

    # Revertir estadísticas del equipo visitante
    equipo_visitante.goles_a_favor = restar_valor(equipo_visitante.goles_a_favor, partido.goles_visitante)
    equipo_visitante.goles_en_contra = restar_valor(equipo_visitante.goles_en_contra, partido.goles_local)
    equipo_visitante.tarjetas_amarillas = restar_valor(equipo_visitante.tarjetas_amarillas, partido.tarjetas_amarillas_visitante)
    equipo_visitante.tarjetas_rojas = restar_valor(equipo_visitante.tarjetas_rojas, partido.tarjetas_rojas_visitante)
    equipo_visitante.tiros_esquina = restar_valor(equipo_visitante.tiros_esquina, partido.tiros_esquina_visitante)
    equipo_visitante.tiros_libres = restar_valor(equipo_visitante.tiros_libres, partido.tiros_libres_visitante)
    equipo_visitante.faltas = restar_valor(equipo_visitante.faltas, partido.faltas_visitante)
    equipo_visitante.fueras_de_juego = restar_valor(equipo_visitante.fueras_de_juego, partido.fueras_de_juego_visitante)
    equipo_visitante.pases = restar_valor(equipo_visitante.pases, partido.pases_visitante)

    session.add_all([equipo_local, equipo_visitante])

    # Eliminar el partido
    await session.delete(partido)
    await session.commit()
    return True


async def actualizar_partidos(
    session: AsyncSession,
    partido_id: int,
    nueva_fase: str
):
    partido = await session.get(PartidoSQL, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    partido.fase = nueva_fase
    session.add(partido)
    await session.commit()
    await session.refresh(partido)

    return partido


# --------------------------------------------------------- operations Reporte -----------------------------------------------------------------------------
async def generar_reportes_por_pais(session: AsyncSession, pais: Paises):
    # Obtener todos los equipos del país
    equipos = await session.execute(select(EquipoSQL).where(EquipoSQL.pais == pais))
    equipos = equipos.scalars().all()  # Ahora esperamos el resultado y obtenemos los equipos.

    if not equipos:
        raise HTTPException(status_code=404, detail=f"No hay equipos para el país {pais}")

    # Contar el total de equipos y puntos
    total_equipos = len(equipos)
    total_puntos = sum([equipo.puntos for equipo in equipos])

    # Calcular promedios de goles a favor y en contra
    total_goles_favor = sum([equipo.goles_a_favor for equipo in equipos])
    total_goles_contra = sum([equipo.goles_en_contra for equipo in equipos])

    promedio_goles_favor = total_goles_favor / total_equipos if total_equipos > 0 else 0
    promedio_goles_contra = total_goles_contra / total_equipos if total_equipos > 0 else 0

    # Verificar si ya existe el reporte para este país
    reporte_existente = await session.execute(
        select(ReportePorPaisSQL).where(ReportePorPaisSQL.pais == pais)
    )
    reporte_existente = reporte_existente.scalar_one_or_none()

    if reporte_existente:
        # Si existe, actualizar el reporte
        reporte_existente.total_equipos = total_equipos
        reporte_existente.total_puntos = total_puntos
        reporte_existente.promedio_goles_favor = promedio_goles_favor
        reporte_existente.promedio_goles_contra = promedio_goles_contra
        session.add(reporte_existente)
    else:
        # Si no existe, crear uno nuevo
        nuevo_reporte = ReportePorPaisSQL(
            pais=pais,
            total_equipos=total_equipos,
            total_puntos=total_puntos,
            promedio_goles_favor=promedio_goles_favor,
            promedio_goles_contra=promedio_goles_contra,
        )
        session.add(nuevo_reporte)

    await session.commit()

    # Esperamos la ejecución de la consulta para obtener el reporte actualizado
    result = await session.execute(
        select(ReportePorPaisSQL).where(ReportePorPaisSQL.pais == pais)
    )

    return result.scalars().all()  # Ahora puedes obtener los resultados.

