from sqlalchemy.future import select
import unicodedata
from sqlalchemy import update,delete
from fastapi import HTTPException
from models import *
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List
from sqlmodel import Session
from sqlalchemy import func, text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload # Asegúrate de importar esto

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
    # Normalizar el nombre del nuevo equipo
    nombre_normalizado_nuevo = normalizar_nombre(equipo.nombre)

    # Verificar si ya existe un equipo con nombre similar (normalizado)
    result = await session.execute(select(EquipoSQL))
    equipos_existentes = result.scalars().all()

    for eq in equipos_existentes:
        if normalizar_nombre(eq.nombre) == nombre_normalizado_nuevo:
            raise HTTPException(status_code=409, detail=f"Ya existe un equipo con un nombre equivalente: {eq.nombre}")

    # Crear una nueva instancia sin ID (la base de datos lo asignará automáticamente)
    equipo_db = EquipoSQL.model_validate(equipo, from_attributes=True)
    equipo_db.id = None  # Asegúrate de que no estás forzando el ID

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

async def actualizar_grupo_y_puntos_equipo(
    session: AsyncSession,
    equipo_id: int,
    nuevo_grupo: str,
    nuevos_puntos: int
) -> EquipoSQL:
    """
    Actualiza el grupo y los puntos de un equipo específico.
    """
    equipo = await session.get(EquipoSQL, equipo_id)

    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    equipo.grupo = nuevo_grupo
    equipo.puntos = nuevos_puntos

    session.add(equipo)
    await session.commit()
    await session.refresh(equipo)
    return equipo

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


async def eliminar_equipo_sql(session: AsyncSession, equipo_id: int) -> bool:
    equipo = await session.get(EquipoSQL, equipo_id)
    if not equipo:
        return False # El equipo no existe


    raise HTTPException(status_code=404, detail="Equipo no encontrado para eliminar.")

    await session.delete(equipo)
    await session.commit()
    return True


async def obtener_equipo_y_manejar_error(session: AsyncSession, equipo_id: int) -> EquipoSQL:
    print(f"DEBUG (operations): obtener_equipo_y_manejar_error - Recibido ID: '{equipo_id}' (tipo: {type(equipo_id)})")


    if not isinstance(equipo_id, int):
        print(f"ERROR (operations): equipo_id no es un entero: {equipo_id}")
        raise HTTPException(status_code=400, detail="ID de equipo inválido.")

    equipo = await session.get(EquipoSQL, equipo_id)

    if not equipo:
        print(f"DEBUG (operations): Equipo con ID '{equipo_id}' NO ENCONTRADO en la DB.")
        raise HTTPException(status_code=404, detail="Equipo no encontrado con ese ID.")

    print(f"DEBUG (operations): Equipo con ID '{equipo_id}' ENCONTRADO: {equipo.nombre}.")
    return equipo


async def eliminar_equipo_sql(session: AsyncSession, equipo_id: int):
    print(f"DEBUG (operations): eliminar_equipo_sql - Iniciando eliminación para ID: {equipo_id}")

    equipo = await obtener_equipo_y_manejar_error(session, equipo_id)


    await session.delete(equipo)
    await session.commit()
    print(f"DEBUG (operations): Equipo con ID '{equipo_id}' eliminado y cambios committeados.")
    return True
# --------------------------------------------------------- operations Partido -----------------------------------------------------------------------------

async def create_partido_sql(session: AsyncSession, partido: PartidoSQL):

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
    local.goles_a_favor += partido.goles_local
    local.goles_en_contra += partido.goles_visitante
    local.tarjetas_amarillas += partido.tarjetas_amarillas_local or 0  # CORREGIDO
    local.tarjetas_rojas += partido.tarjetas_rojas_local or 0  # CORREGIDO
    local.tiros_esquina += partido.tiros_esquina_local or 0  # CORREGIDO
    local.tiros_libres += partido.tiros_libres_local or 0  # CORREGIDO
    local.faltas += partido.faltas_local or 0  # CORREGIDO
    local.fueras_de_juego += partido.fueras_de_juego_local or 0  # CORREGIDO
    local.pases += partido.pases_local or 0  # CORREGIDO

    # Actualizar estadísticas del equipo visitante
    visitante.goles_a_favor += partido.goles_visitante
    visitante.goles_en_contra += partido.goles_local
    visitante.tarjetas_amarillas += partido.tarjetas_amarillas_visitante or 0  # CORREGIDO
    visitante.tarjetas_rojas += partido.tarjetas_rojas_visitante or 0  # CORREGIDO
    visitante.tiros_esquina += partido.tiros_esquina_visitante or 0  # CORREGIDO
    visitante.tiros_libres += partido.tiros_libres_visitante or 0  # CORREGIDO
    visitante.faltas += partido.faltas_visitante or 0  # CORREGIDO
    visitante.fueras_de_juego += partido.fueras_de_juego_visitante or 0  # CORREGIDO
    visitante.pases += partido.pases_visitante or 0

    session.add(local)
    session.add(visitante)

    await session.commit()
    await session.refresh(partido_db)
    return partido_db



async def obtener_todos_los_partidos(session: AsyncSession) -> List[PartidoSQL]:
    # Cargamos los equipos relacionados (local y visitante) para acceder a sus nombres y logos
    result = await session.execute(
        select(PartidoSQL).options(
            selectinload(PartidoSQL.equipo_local),
            selectinload(PartidoSQL.equipo_visitante)
        )
    )
    return result.scalars().all()


async def obtener_partido_por_id(session: AsyncSession, partido_id: int) -> Optional[PartidoSQL]:
    """
    Obtiene un partido por su ID, cargando los objetos de equipo local y visitante.
    """
    print(f"DEBUG (operations): Buscando partido con ID: {partido_id}")
    result = await session.execute(
        select(PartidoSQL)
        .where(PartidoSQL.id == partido_id)
        .options(
            selectinload(PartidoSQL.equipo_local),
            selectinload(PartidoSQL.equipo_visitante)
        )
    )
    partido = result.scalar_one_or_none()
    if partido:
        print(f"DEBUG (operations): Partido encontrado: ID {partido.id}, Fase {partido.fase}")
    else:
        print(f"DEBUG (operations): Partido con ID {partido_id} no encontrado.")
    return partido


async def eliminar_partido_sql(session: AsyncSession, partido_id: int) -> bool:
    print(f"DEBUG (operations): Intentando eliminar partido con ID: {partido_id}")

    result = await session.execute(
        select(PartidoSQL)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
        .where(PartidoSQL.id == partido_id)
    )
    partido_a_eliminar = result.scalars().first()

    if not partido_a_eliminar:
        print(f"DEBUG (operations): Partido con ID {partido_id} no encontrado para eliminar.")
        return False

    local_id = partido_a_eliminar.equipo_local_id
    visitante_id = partido_a_eliminar.equipo_visitante_id

    # Eliminar el partido
    await session.execute(
        delete(PartidoSQL).where(PartidoSQL.id == partido_id)
    )
    await session.commit()

    # Recalcular las estadísticas de los equipos involucrados
    # Es importante que estos equipos aún existan en la base de datos
    await recalcular_estadisticas_equipo(session, local_id)
    await recalcular_estadisticas_equipo(session, visitante_id)

    print(
        f"DEBUG (operations): Partido con ID {partido_id} eliminado exitosamente y estadísticas de equipos recalculadas.")
    return True


async def recalcular_estadisticas_equipo(session: AsyncSession, equipo_id: int):
    print(f"DEBUG (operations): Recalculando estadísticas para Equipo ID: {equipo_id}")
    equipo = await session.get(EquipoSQL, equipo_id)
    if not equipo:
        print(f"ADVERTENCIA: Equipo con ID {equipo_id} no encontrado para recalcular estadísticas.")
        return

    # Obtener todos los partidos donde el equipo es local o visitante
    result = await session.execute(
        select(PartidoSQL).where(
            (PartidoSQL.equipo_local_id == equipo_id) |
            (PartidoSQL.equipo_visitante_id == equipo_id)
        )
    )
    partidos_del_equipo: List[PartidoSQL] = result.scalars().all()

    total_goles_a_favor = 0
    total_goles_en_contra = 0
    total_tarjetas_amarillas = 0
    total_tarjetas_rojas = 0
    total_faltas = 0
    total_fueras_de_juego = 0
    total_tiros_esquina = 0
    total_tiros_libres = 0
    total_pases = 0

    for p in partidos_del_equipo:
        if p.equipo_local_id == equipo_id:
            total_goles_a_favor += p.goles_local
            total_goles_en_contra += p.goles_visitante
            total_tarjetas_amarillas += p.tarjetas_amarillas_local
            total_tarjetas_rojas += p.tarjetas_rojas_local
            total_faltas += p.faltas_local
            total_fueras_de_juego += p.fueras_de_juego_local
            total_tiros_esquina += p.tiros_esquina_local
            total_tiros_libres += p.tiros_libres_local
            total_pases += p.pases_local
        elif p.equipo_visitante_id == equipo_id:
            total_goles_a_favor += p.goles_visitante
            total_goles_en_contra += p.goles_local
            total_tarjetas_amarillas += p.tarjetas_amarillas_visitante
            total_tarjetas_rojas += p.tarjetas_rojas_visitante
            total_faltas += p.faltas_visitante
            total_fueras_de_juego += p.fueras_de_juego_visitante
            total_tiros_esquina += p.tiros_esquina_visitante
            total_tiros_libres += p.tiros_libres_visitante
            total_pases += p.pases_visitante

    # Actualizar el equipo con las nuevas estadísticas
    equipo.goles_a_favor = total_goles_a_favor
    equipo.goles_en_contra = total_goles_en_contra
    equipo.tarjetas_amarillas = total_tarjetas_amarillas
    equipo.tarjetas_rojas = total_tarjetas_rojas
    equipo.faltas = total_faltas
    equipo.fueras_de_juego = total_fueras_de_juego
    equipo.tiros_esquina = total_tiros_esquina
    equipo.tiros_libres = total_tiros_libres
    equipo.pases = total_pases

    session.add(equipo)
    await session.commit()
    await session.refresh(equipo)
    print(f"DEBUG (operations): Estadísticas para Equipo ID: {equipo_id} actualizadas.")


async def actualizar_partido_sql(session: AsyncSession, partido_id: int, datos_actualizados: Dict[str, Any]) -> \
Optional[PartidoSQL]:
    """
    Actualiza un partido existente y recalcula las estadísticas de los equipos involucrados.
    No modifica los puntos de los equipos.
    """
    print(f"DEBUG (operations): Intentando actualizar partido con ID: {partido_id}")
    partido_existente = await session.get(PartidoSQL, partido_id)

    if not partido_existente:
        print(f"DEBUG (operations): Partido con ID {partido_id} no encontrado para actualizar.")
        return None

    # Guardar las estadísticas originales del partido antes de la actualización
    # Esto es necesario para calcular las diferencias para los equipos
    stats_originales = {
        "goles_local": partido_existente.goles_local,
        "goles_visitante": partido_existente.goles_visitante,
        "tarjetas_amarillas_local": partido_existente.tarjetas_amarillas_local,
        "tarjetas_amarillas_visitante": partido_existente.tarjetas_amarillas_visitante,
        "tarjetas_rojas_local": partido_existente.tarjetas_rojas_local,
        "tarjetas_rojas_visitante": partido_existente.tarjetas_rojas_visitante,
        "tiros_esquina_local": partido_existente.tiros_esquina_local,
        "tiros_esquina_visitante": partido_existente.tiros_esquina_visitante,
        "tiros_libres_local": partido_existente.tiros_libres_local,
        "tiros_libres_visitante": partido_existente.tiros_libres_visitante,
        "faltas_local": partido_existente.faltas_local,
        "faltas_visitante": partido_existente.faltas_visitante,
        "fueras_de_juego_local": partido_existente.fueras_de_juego_local,
        "fueras_de_juego_visitante": partido_existente.fueras_de_juego_visitante,
        "pases_local": partido_existente.pases_local,
        "pases_visitante": partido_existente.pases_visitante,
    }

    # Actualizar los campos del objeto partido_existente
    for key, value in datos_actualizados.items():
        if hasattr(partido_existente, key) and key not in ['id', 'equipo_local_id', 'equipo_visitante_id',
                                                           'equipo_local', 'equipo_visitante']:
            if key == 'fase':
                if value in [fase.value for fase in Fases]:
                    setattr(partido_existente, key, Fases(value))
                else:
                    print(f"ADVERTENCIA: Valor de fase inválido '{value}' para el partido {partido_id}.")
                    continue
            elif key == 'fecha':
                if isinstance(value, str):  # Si la fecha viene como string del formulario
                    try:
                        setattr(partido_existente, key, datetime.strptime(value, '%Y-%m-%d').date())
                    except ValueError:
                        print(f"ADVERTENCIA: Formato de fecha inválido '{value}' para el partido {partido_id}.")
                        continue
                elif isinstance(value, date):  # Si ya viene como date object
                    setattr(partido_existente, key, value)
            else:
                setattr(partido_existente, key, value)

    session.add(partido_existente)
    await session.commit()
    await session.refresh(partido_existente)  # Asegura que el objeto tenga los datos más recientes

    # Después de actualizar el partido, recalcular las estadísticas de los equipos
    await recalcular_estadisticas_equipo(session, partido_existente.equipo_local_id)
    await recalcular_estadisticas_equipo(session, partido_existente.equipo_visitante_id)

    print(
        f"DEBUG (operations): Partido con ID {partido_id} y estadísticas de equipos relacionados actualizados exitosamente.")
    return partido_existente


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

