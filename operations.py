from sqlalchemy.future import select
import unicodedata
from sqlalchemy import update, delete  # delete seguirá siendo útil para eliminación física si la necesitas
from fastapi import HTTPException
from models import *
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List
from sqlmodel import Session
from sqlalchemy import func, text, case
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
import os
from dotenv import load_dotenv
import httpx

load_dotenv()
API_TOKEN = os.getenv("SPORTMONKS_API_TOKEN")

def normalizar_nombre(nombre: str) -> str:
    nombre = nombre.lower()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))  # Elimina tildes
    return nombre


def remove_tzinfo(dt: Optional[datetime | str]) -> Optional[datetime]:
    if isinstance(dt, str):
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
    equipo.nombre = normalizar_nombre(equipo.nombre)

    # Verificar si ya existe un equipo activo con el mismo nombre normalizado
    existing_equipo = await session.execute(
        select(EquipoSQL).where(EquipoSQL.nombre == equipo.nombre, EquipoSQL.esta_activo == True)
        # <-- Filtra por activo
    )
    if existing_equipo.first():
        raise HTTPException(status_code=400, detail=f"El equipo '{equipo.nombre}' ya existe y está activo.")

    session.add(equipo)
    await session.commit()
    await session.refresh(equipo)
    print(f"DEBUG (operations): Equipo '{equipo.nombre}' creado con ID {equipo.id}.")
    await actualizar_reporte_por_pais(session, equipo.pais)
    return equipo


async def restaurar_equipo_sql(session: AsyncSession, equipo_id: int) -> Optional[EquipoSQL]:
    """
    Restaura un equipo (cambia su campo 'esta_activo' a True).
    Retorna el equipo restaurado o None si no se encuentra.
    """
    try:
        # 1. Obtener el equipo por su ID
        result = await session.execute(
            select(EquipoSQL).where(EquipoSQL.id == equipo_id)
        )
        equipo = result.scalar_one_or_none()

        if not equipo:
            return None  # El equipo no fue encontrado

        # 2. Cambiar el estado a True
        equipo.esta_activo = True

        # 3. Añadir el objeto modificado a la sesión y hacer commit
        session.add(equipo)
        await session.commit()
        await session.refresh(equipo)  # Refrescar el objeto para obtener los datos más recientes de la DB

        return equipo
    except Exception as e:
        print(f"Error al restaurar equipo con ID {equipo_id}: {e}")
        await session.rollback() # En caso de error, hacer rollback de la transacción
        raise HTTPException(status_code=500, detail=f"Error interno al restaurar el equipo: {e}")



async def obtener_todos_los_equipos_inactivos(session: AsyncSession) -> List[EquipoSQL]:
    """
    Obtiene todos los equipos cuyo campo 'esta_activo' es False.
    """
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.esta_activo == False)
    )
    return result.scalars().all()

async def obtener_equipo_por_id(session: AsyncSession, equipo_id: int) -> Optional[EquipoSQL]:
    """Obtiene un equipo por ID, solo si está activo."""
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.id == equipo_id, EquipoSQL.esta_activo == True)  # <-- Filtra por activo
    )
    return result.scalars().first()


async def obtener_todos_los_equipos(session: AsyncSession) -> List[EquipoSQL]:
    """Obtiene todos los equipos activos."""
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.esta_activo == True)  # <-- Filtra por activo
    )
    return list(result.scalars().all())


async def obtener_equipos_por_pais(session: AsyncSession, pais: str) -> List[EquipoSQL]:
    """Obtiene equipos por país, solo si están activos."""
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.pais == pais, EquipoSQL.esta_activo == True)  # <-- Filtra por activo
    )
    return list(result.scalars().all())


async def obtener_equipo_por_nombre(session: AsyncSession, nombre: str) -> Optional[EquipoSQL]:
    """Obtiene un equipo por nombre normalizado, solo si está activo."""
    nombre_normalizado = normalizar_nombre(nombre)
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.nombre == nombre_normalizado, EquipoSQL.esta_activo == True)
        # <-- Filtra por activo
    )
    return result.scalars().first()


async def actualizar_equipo_sql(session: AsyncSession, equipo_id: int, datos_actualizados: Dict[str, Any]) -> Optional[
    EquipoSQL]:
    print(f"DEBUG (operations): Intentando actualizar equipo con ID: {equipo_id}")
    equipo_existente = await session.get(EquipoSQL, equipo_id)

    if not equipo_existente or not equipo_existente.esta_activo:  # <-- Verifica que esté activo
        print(f"DEBUG (operations): Equipo con ID {equipo_id} no encontrado o inactivo para actualizar.")
        return None

    pais_anterior = equipo_existente.pais  # Guardar para posible recálculo de reporte

    for key, value in datos_actualizados.items():
        if hasattr(equipo_existente, key) and key not in ['id', 'puntos', 'logo_url', 'goles_a_favor',
                                                          'goles_en_contra', 'tarjetas_amarillas', 'tarjetas_rojas',
                                                          'faltas', 'fueras_de_juego', 'tiros_esquina', 'tiros_libres',
                                                          'pases', 'esta_activo']:
            if key == 'nombre':
                value = normalizar_nombre(value)
                # Verificar si el nuevo nombre ya está tomado por un equipo ACTIVO diferente
                existing_by_name = await session.execute(
                    select(EquipoSQL).where(EquipoSQL.nombre == value, EquipoSQL.id != equipo_id,
                                            EquipoSQL.esta_activo == True)  # <-- Filtra por activo
                )
                if existing_by_name.first():
                    raise HTTPException(status_code=400,
                                        detail=f"El nombre '{value}' ya está en uso por otro equipo activo.")
            setattr(equipo_existente, key, value)

    session.add(equipo_existente)
    await session.commit()
    await session.refresh(equipo_existente)

    # Si el país del equipo cambió, actualizar los reportes de ambos países
    if pais_anterior != equipo_existente.pais:
        await actualizar_reporte_por_pais(session, pais_anterior)  # Recalcular el viejo país
        await actualizar_reporte_por_pais(session, equipo_existente.pais)  # Recalcular el nuevo país
    else:
        await actualizar_reporte_por_pais(session, equipo_existente.pais)  # Recalcular solo el país actual si no cambió

    print(f"DEBUG (operations): Equipo con ID {equipo_id} actualizado exitosamente.")
    return equipo_existente


# --- Eliminación suave de Equipo ---
async def eliminar_equipo_sql(session: AsyncSession, equipo_id: int) -> bool:
    print(f"DEBUG (operations): Intentando marcar equipo con ID: {equipo_id} como inactivo.")
    equipo = await session.get(EquipoSQL, equipo_id)

    if not equipo or not equipo.esta_activo:
        print(f"DEBUG (operations): Equipo con ID {equipo_id} no encontrado o ya inactivo.")
        return False

    # Guardar el país antes de marcarlo como inactivo para el reporte
    pais_equipo = equipo.pais

    # Marcar el equipo como inactivo
    equipo.esta_activo = False
    session.add(equipo)

    # Marcar todos los partidos donde este equipo sea local o visitante como inactivos
    # Es importante que estos partidos no contribuyan a las estadísticas de otros equipos
    # a menos que esos otros equipos también sean inactivos.

    # Opción 1: Marcar los partidos del equipo como inactivos
    # Obtener partidos donde el equipo es local o visitante
    result_partidos = await session.execute(
        select(PartidoSQL).where(
            (PartidoSQL.equipo_local_id == equipo_id) |
            (PartidoSQL.equipo_visitante_id == equipo_id),
            PartidoSQL.esta_activo == True  # Solo marca partidos que están activos
        )
    )
    partidos_afectados = result_partidos.scalars().all()

    equipos_a_recalcular = set()  # Para evitar recalcular el mismo equipo varias veces

    for p in partidos_afectados:
        p.esta_activo = False  # Marca el partido como inactivo
        session.add(p)
        # Añadir el otro equipo del partido para recalcular sus estadísticas
        if p.equipo_local_id != equipo_id:
            equipos_a_recalcular.add(p.equipo_local_id)
        if p.equipo_visitante_id != equipo_id:
            equipos_a_recalcular.add(p.equipo_visitante_id)

    await session.commit()
    await session.refresh(equipo)  # Refrescar el equipo para asegurar que tiene el nuevo estado

    # Recalcular estadísticas para los equipos afectados (los que no son el que se eliminó)
    for id_equipo_recalcular in equipos_a_recalcular:
        # Solo recalcular si el otro equipo sigue activo
        otro_equipo = await session.get(EquipoSQL, id_equipo_recalcular)
        if otro_equipo and otro_equipo.esta_activo:
            await recalcular_estadisticas_equipo(session, id_equipo_recalcular)

    # Recalcular el reporte del país del equipo eliminado
    await actualizar_reporte_por_pais(session, pais_equipo)

    print(
        f"DEBUG (operations): Equipo con ID {equipo_id} marcado como inactivo exitosamente y partidos asociados actualizados.")
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

async def actualizar_grupo_y_puntos_equipo(
    session: AsyncSession,
    equipo_id: int,
    nuevo_grupo: str,
    nuevos_puntos: int
) -> EquipoSQL:
    equipo = await session.get(EquipoSQL, equipo_id)

    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    equipo.grupo = nuevo_grupo
    equipo.puntos = nuevos_puntos

    session.add(equipo)
    await session.commit()
    await session.refresh(equipo)
    return equipo

# --- Modificaciones para PartidoSQL ---

async def obtener_todos_los_partidos(session: AsyncSession) -> List[PartidoSQL]:
    # Cargamos los equipos relacionados (local y visitante) para acceder a sus nombres y logos
    result = await session.execute(
        select(PartidoSQL).options(
            selectinload(PartidoSQL.equipo_local),
            selectinload(PartidoSQL.equipo_visitante)
        )
    )
    return result.scalars().all()

async def obtener_todos_los_partidos_inactivos(session: AsyncSession) -> List[PartidoSQL]:
    result = await session.execute(
        select(PartidoSQL).where(PartidoSQL.esta_activo == False)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
    )
    return result.scalars().unique().all()

async def obtener_partido_por_id(session: AsyncSession, partido_id: int) -> Optional[PartidoSQL]:
    """
    Busca un partido por su ID, cargando los equipos relacionados.
    """
    print(f"DEBUG: [operations.py] Buscando partido con ID: {partido_id}")
    try:
        result = await session.execute(
            select(PartidoSQL)
            .where(PartidoSQL.id == partido_id)
            .options(selectinload(PartidoSQL.equipo_local),
                     selectinload(PartidoSQL.equipo_visitante))
        )
        partido = result.scalar_one_or_none()
        if partido:
            print(f"DEBUG: [operations.py] Partido ENCONTRADO: ID={partido.id}, Goles Local={partido.goles_local}, Goles Visitante={partido.goles_visitante}")
        else:
            print(f"DEBUG: [operations.py] Partido NO encontrado para ID: {partido_id}")
        return partido
    except Exception as e:
        print(f"ERROR: [operations.py] Error en buscar_partido_por_id para ID {partido_id}: {e}")
        # Re-lanzar o manejar el error según sea necesario
        raise # Vuelve a lanzar la excepción para que sea capturada en main.py


async def create_partido_sql(session: AsyncSession, partido: PartidoSQL) -> PartidoSQL:
    if partido.equipo_local_id == partido.equipo_visitante_id:
        raise HTTPException(
            status_code=400,
            detail="El equipo local y el equipo visitante no pueden ser el mismo en un partido."
        )

    # Establecer esta_activo a True por defecto si no se especificó (o explícitamente)
    partido.esta_activo = True
    session.add(partido)
    await session.commit()
    await session.refresh(partido)
    print(f"DEBUG (operations): Partido creado con ID {partido.id}.")

    # Actualizar estadísticas de equipos involucrados si el partido es activo
    if partido.esta_activo:
        await recalcular_estadisticas_equipo(session, partido.equipo_local_id)
        await recalcular_estadisticas_equipo(session, partido.equipo_visitante_id)

    return partido


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


# --- Eliminación suave de Partido ---
async def eliminar_partido_sql(session: AsyncSession, partido_id: int) -> bool:
    partido = await session.execute(
        select(PartidoSQL)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
        .where(PartidoSQL.id == partido_id, PartidoSQL.esta_activo == True)
    )
    partido = partido.scalar_one_or_none()

    if not partido:
        return False

    equipo_local = partido.equipo_local
    equipo_visitante = partido.equipo_visitante

    if equipo_local and equipo_visitante:
        # Revert points
        if partido.goles_local > partido.goles_visitante:
            equipo_local.puntos = restar_valor(equipo_local.puntos, 3)
        elif partido.goles_visitante > partido.goles_local:
            equipo_visitante.puntos = restar_valor(equipo_visitante.puntos, 3)
        else:
            equipo_local.puntos = restar_valor(equipo_local.puntos, 1)
            equipo_visitante.puntos = restar_valor(equipo_visitante.puntos, 1)

        # Revert other statistics for local team
        equipo_local.goles_a_favor = restar_valor(equipo_local.goles_a_favor, partido.goles_local)
        equipo_local.goles_en_contra = restar_valor(equipo_local.goles_en_contra, partido.goles_visitante)
        equipo_local.tarjetas_amarillas = restar_valor(equipo_local.tarjetas_amarillas, partido.tarjetas_amarillas_local)
        equipo_local.tarjetas_rojas = restar_valor(equipo_local.tarjetas_rojas, partido.tarjetas_rojas_local)
        equipo_local.tiros_esquina = restar_valor(equipo_local.tiros_esquina, partido.tiros_esquina_local)
        equipo_local.tiros_libres = restar_valor(equipo_local.tiros_libres, partido.tiros_libres_local)
        equipo_local.faltas = restar_valor(equipo_local.faltas, partido.faltas_local)
        equipo_local.fueras_de_juego = restar_valor(equipo_local.fueras_de_juego, partido.fueras_de_juego_local)
        equipo_local.pases = restar_valor(equipo_local.pases, partido.pases_local)

        # Revert other statistics for visiting team
        equipo_visitante.goles_a_favor = restar_valor(equipo_visitante.goles_a_favor, partido.goles_visitante)
        equipo_visitante.goles_en_contra = restar_valor(equipo_visitante.goles_en_contra, partido.goles_local)
        equipo_visitante.tarjetas_amarillas = restar_valor(equipo_visitante.tarjetas_amarillas, partido.tarjetas_amarillas_visitante)
        equipo_visitante.tarjetas_rojas = restar_valor(equipo_visitante.tarjetas_rojas, partido.tarjetas_rojas_visitante)
        equipo_visitante.tiros_esquina = restar_valor(equipo_visitante.tiros_esquina, partido.tiros_esquina_visitante)
        equipo_visitante.tiros_libres = restar_valor(equipo_visitante.tiros_libres, partido.tiros_libres_visitante)
        equipo_visitante.faltas = restar_valor(equipo_visitante.faltas, partido.faltas_visitante)
        equipo_visitante.fueras_de_juego = restar_valor(equipo_visitante.fueras_de_juego, partido.fueras_de_juego_visitante)
        equipo_visitante.pases = restar_valor(equipo_visitante.pases, partido.pases_visitante)


        session.add(equipo_local)
        session.add(equipo_visitante)
        await session.commit()
        await session.refresh(equipo_local)
        await session.refresh(equipo_visitante)

    partido.esta_activo = False
    session.add(partido)
    await session.commit()
    await session.refresh(partido)
    return True


# --- Recalcular estadísticas del equipo: Asegúrate de que solo suma partidos activos ---
async def recalcular_estadisticas_equipo(session: AsyncSession, equipo_id: int):
    print(f"DEBUG (operations): Recalculando estadísticas para Equipo ID: {equipo_id}")
    equipo = await session.get(EquipoSQL, equipo_id)
    if not equipo or not equipo.esta_activo:  # Solo recalcular si el equipo está activo
        print(f"ADVERTENCIA: Equipo con ID {equipo_id} no encontrado o inactivo para recalcular estadísticas.")
        return

    # Obtener todos los partidos ACTIVOS donde el equipo es local o visitante
    result = await session.execute(
        select(PartidoSQL).where(
            (PartidoSQL.equipo_local_id == equipo_id) |
            (PartidoSQL.equipo_visitante_id == equipo_id),
            PartidoSQL.esta_activo == True  # <-- Filtra por activo
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

# NEW FUNCTION: obtener_partido_inactivo_por_id (for restoration)
async def obtener_partido_inactivo_por_id(session: AsyncSession, partido_id: int) -> Optional[PartidoSQL]:
    result = await session.execute(
        select(PartidoSQL).where(PartidoSQL.id == partido_id, PartidoSQL.esta_activo == False)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
    )
    return result.scalar_one_or_none()

async def restaurar_partido_sql(session: AsyncSession, partido_id: int) -> bool:
    partido = await obtener_partido_inactivo_por_id(session, partido_id) # Use the new function to get inactive match
    if not partido:
        return False

    equipo_local = partido.equipo_local
    equipo_visitante = partido.equipo_visitante

    if equipo_local and equipo_visitante:
        # Re-add points
        if partido.goles_local > partido.goles_visitante:
            equipo_local.puntos += 3
        elif partido.goles_visitante > partido.goles_local:
            equipo_visitante.puntos += 3
        else:
            equipo_local.puntos += 1
            equipo_visitante.puntos += 1

        # Re-add other statistics for local team
        equipo_local.goles_a_favor += partido.goles_local
        equipo_local.goles_en_contra += partido.goles_visitante
        equipo_local.tarjetas_amarillas += partido.tarjetas_amarillas_local
        equipo_local.tarjetas_rojas += partido.tarjetas_rojas_local
        equipo_local.tiros_esquina += partido.tiros_esquina_local
        equipo_local.tiros_libres += partido.tiros_libres_local
        equipo_local.faltas += partido.faltas_local
        equipo_local.fueras_de_juego += partido.fueras_de_juego_local
        equipo_local.pases += partido.pases_local

        # Re-add other statistics for visiting team
        equipo_visitante.goles_a_favor += partido.goles_visitante
        equipo_visitante.goles_en_contra += partido.goles_local
        equipo_visitante.tarjetas_amarillas += partido.tarjetas_amarillas_visitante
        equipo_visitante.tarjetas_rojas += partido.tarjetas_rojas_visitante
        equipo_visitante.tiros_esquina += partido.tiros_esquina_visitante
        equipo_visitante.tiros_libres += partido.tiros_libres_visitante
        equipo_visitante.faltas += partido.faltas_visitante
        equipo_visitante.fueras_de_juego += partido.fueras_de_juego_visitante
        equipo_visitante.pases += partido.pases_visitante

        session.add(equipo_local)
        session.add(equipo_visitante)
        await session.commit()
        await session.refresh(equipo_local)
        await session.refresh(equipo_visitante)

    partido.esta_activo = True  # Mark as active
    session.add(partido)
    await session.commit()
    await session.refresh(partido)
    return True

# --- Recalcular Reporte por País: Asegúrate de que solo suma equipos activos ---
async def actualizar_reporte_por_pais(session: AsyncSession, pais: Paises):
    """
    Recalcula el reporte estadístico para un país específico basándose solo en equipos activos.
    """
    print(f"DEBUG (operations): Actualizando reporte para país: {pais.value}")

    # Obtener solo equipos activos para el cálculo
    equipos = await session.execute(
        select(EquipoSQL).where(EquipoSQL.pais == pais, EquipoSQL.esta_activo == True)  # <-- Filtra por activo
    )
    equipos = equipos.scalars().all()

    total_equipos = len(equipos)
    total_puntos = sum([equipo.puntos for equipo in equipos])
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
    print(f"DEBUG (operations): Reporte para país: {pais.value} actualizado.")


async def obtener_todos_los_reportes_por_pais(session: AsyncSession) -> List[ReportePorPaisSQL]:
    """Obtiene todos los reportes por país."""
    result = await session.execute(select(ReportePorPaisSQL))
    return list(result.scalars().all())

async def generar_reportes_por_pais(session: AsyncSession, pais: Paises):
    # Consulta para obtener equipos activos de un país específico
    equipos_del_pais_query = await session.execute(
        select(EquipoSQL).where(EquipoSQL.pais == pais, EquipoSQL.esta_activo == True)
    )
    equipos_del_pais = equipos_del_pais_query.scalars().all()

    total_equipos = len(equipos_del_pais)
    total_puntos = sum(equipo.puntos for equipo in equipos_del_pais)
    total_goles_favor = sum(equipo.goles_a_favor for equipo in equipos_del_pais)
    total_goles_contra = sum(equipo.goles_en_contra for equipo in equipos_del_pais)

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
    await session.refresh(reporte_existente if reporte_existente else nuevo_reporte) # Refresh to get updated values/ID
    return reporte_existente if reporte_existente else nuevo_reporte

async def obtener_reporte_por_pais(session: AsyncSession, pais: Paises) -> Optional[ReportePorPaisSQL]:
    result = await session.execute(
        select(ReportePorPaisSQL).where(ReportePorPaisSQL.pais == pais)
    )
    return result.scalar_one_or_none()

async def obtener_todos_los_reportes_por_pais(session: AsyncSession) -> List[ReportePorPaisSQL]:
    result = await session.execute(
        select(ReportePorPaisSQL)
    )
    return result.scalars().all()

async def generar_reportes_por_fase(session: AsyncSession, fase: Fases):
    # Consulta para obtener partidos activos de una fase específica
    partidos_de_la_fase_query = await session.execute(
        select(PartidoSQL).where(PartidoSQL.fase == fase, PartidoSQL.esta_activo == True)
    )
    partidos_de_la_fase = partidos_de_la_fase_query.scalars().all()

    total_partidos = len(partidos_de_la_fase)
    total_goles_local = sum(partido.goles_local for partido in partidos_de_la_fase)
    total_goles_visitante = sum(partido.goles_visitante for partido in partidos_de_la_fase)

    # Verificar si ya existe el reporte para esta fase
    reporte_existente = await session.execute(
        select(ReportePorFaseSQL).where(ReportePorFaseSQL.fase == fase)
    )
    reporte_existente = reporte_existente.scalar_one_or_none()

    if reporte_existente:
        # Si existe, actualizar el reporte
        reporte_existente.total_partidos = total_partidos
        reporte_existente.total_goles_local = total_goles_local
        reporte_existente.total_goles_visitante = total_goles_visitante
        session.add(reporte_existente)
    else:
        # Si no existe, crear uno nuevo
        nuevo_reporte = ReportePorFaseSQL(
            fase=fase,
            total_partidos=total_partidos,
            total_goles_local=total_goles_local,
            total_goles_visitante=total_goles_visitante,
        )
        session.add(nuevo_reporte)

    await session.commit()
    await session.refresh(reporte_existente if reporte_existente else nuevo_reporte)
    return reporte_existente if reporte_existente else nuevo_reporte

async def obtener_reporte_por_fase(session: AsyncSession, fase: Fases) -> Optional[ReportePorFaseSQL]:
    result = await session.execute(
        select(ReportePorFaseSQL).where(ReportePorFaseSQL.fase == fase)
    )
    return result.scalar_one_or_none()

async def obtener_todos_los_reportes_por_fase(session: AsyncSession) -> List[ReportePorFaseSQL]:
    result = await session.execute(
        select(ReportePorFaseSQL)
    )
    return result.scalars().all()


async def obtener_equipos_menos_goleados(session: AsyncSession) -> List[EquipoMenosGoleadoReporte]:
    # Subquery para sumar goles recibidos como local
    goles_contra_local_subquery = (
        select(
            PartidoSQL.equipo_local_id.label("equipo_id"),
            func.sum(PartidoSQL.goles_visitante).label("goles_en_contra_local")
        )
        .group_by(PartidoSQL.equipo_local_id)
        .subquery("gcl") # Nombre explícito para el subquery
    )

    # Subquery para sumar goles recibidos como visitante
    goles_contra_visitante_subquery = (
        select(
            PartidoSQL.equipo_visitante_id.label("equipo_id"),
            func.sum(PartidoSQL.goles_local).label("goles_en_contra_visitante")
        )
        .group_by(PartidoSQL.equipo_visitante_id)
        .subquery("gcv") # Nombre explícito para el subquery
    )

    # Consulta interna para calcular los goles en contra por equipo
    # Esta subconsulta ya tendrá una fila por equipo con su total de goles recibidos
    base_query_for_ranking = (
        select(
            EquipoSQL.id,
            EquipoSQL.nombre,
            EquipoSQL.pais,
            EquipoSQL.grupo,
            EquipoSQL.logo_url,
            (
                func.coalesce(goles_contra_local_subquery.c.goles_en_contra_local, 0) +
                func.coalesce(goles_contra_visitante_subquery.c.goles_en_contra_visitante, 0)
            ).label("goles_en_contra")
        )
        .join(goles_contra_local_subquery, EquipoSQL.id == goles_contra_local_subquery.c.equipo_id, isouter=True)
        .join(goles_contra_visitante_subquery, EquipoSQL.id == goles_contra_visitante_subquery.c.equipo_id, isouter=True)
        # No se necesita un GROUP BY explícito aquí si EquipoSQL.id es la clave primaria
        # y las subconsultas ya agregan por equipo_id.
    ).subquery("ranked_teams_pre") # Convertir esta parte en un subquery

    # Consulta final que selecciona de la subconsulta y aplica el ORDER BY y LIMIT
    query = (
        select(
            base_query_for_ranking.c.id,
            base_query_for_ranking.c.nombre,
            base_query_for_ranking.c.pais,
            base_query_for_ranking.c.grupo,
            base_query_for_ranking.c.logo_url,
            base_query_for_ranking.c.goles_en_contra
        )
        .order_by(base_query_for_ranking.c.goles_en_contra.asc()) # Ordenar por la columna ya calculada
        .limit(6) # Limitar a los 6 primeros
    )

    result = await session.execute(query)
    equipos_data = result.all()

    # Reconstruir objetos usando el modelo EquipoMenosGoleadoReporte
    equipos_con_goles = []
    for data in equipos_data:
        equipo = EquipoMenosGoleadoReporte(
            id=data.id,
            nombre=data.nombre,
            pais=data.pais,
            grupo=data.grupo,
            logo_url=data.logo_url,
            goles_en_contra=data.goles_en_contra,
        )
        equipos_con_goles.append(equipo)
    return equipos_con_goles

# NUEVA FUNCIÓN: Generar reporte de tabla de posiciones por grupo
async def generar_reporte_por_grupos(session: AsyncSession) -> Dict[Grupos, List[PosicionEquipoReporte]]:
    """
    Genera un reporte de tabla de posiciones para cada grupo.
    Calcula dinámicamente las estadísticas de cada equipo (partidos jugados, victorias, etc.)
    y los ordena dentro de cada grupo.
    """
    print("DEBUG (operations): Generando reporte por grupos...")

    # Obtener todos los equipos activos con sus IDs
    equipos_query = await session.execute(
        select(EquipoSQL.id, EquipoSQL.nombre, EquipoSQL.grupo, EquipoSQL.logo_url).where(EquipoSQL.esta_activo == True)
    )
    equipos_activos = equipos_query.all()

    # Obtener todos los partidos activos
    partidos_query = await session.execute(
        select(PartidoSQL)
        .where(PartidoSQL.esta_activo == True)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
    )
    partidos_activos: List[PartidoSQL] = partidos_query.scalars().all()

    # Inicializar estadísticas para cada equipo
    stats_equipos: Dict[int, Dict[str, Any]] = {}
    for equipo_id, nombre, grupo, logo_url in equipos_activos:
        stats_equipos[equipo_id] = {
            "id": equipo_id,
            "nombre": nombre,
            "grupo": grupo,
            "puntos": 0,
            "partidos_jugados": 0,
            "victorias": 0,
            "empates": 0,
            "derrotas": 0,
            "goles_a_favor": 0,
            "goles_en_contra": 0,
            "diferencia_goles": 0,
            "logo_url": logo_url
        }

    # Procesar cada partido para acumular estadísticas
    for partido in partidos_activos:
        local_id = partido.equipo_local_id
        visitante_id = partido.equipo_visitante_id

        # Asegurarse de que ambos equipos del partido existen y están activos en nuestras estadísticas
        if local_id in stats_equipos and visitante_id in stats_equipos:
            # Equipo Local
            stats_equipos[local_id]["partidos_jugados"] += 1
            stats_equipos[local_id]["goles_a_favor"] += partido.goles_local
            stats_equipos[local_id]["goles_en_contra"] += partido.goles_visitante

            # Equipo Visitante
            stats_equipos[visitante_id]["partidos_jugados"] += 1
            stats_equipos[visitante_id]["goles_a_favor"] += partido.goles_visitante
            stats_equipos[visitante_id]["goles_en_contra"] += partido.goles_local

            # Determinar resultado y asignar puntos/victorias/empates/derrotas
            if partido.goles_local > partido.goles_visitante:
                # Gana local
                stats_equipos[local_id]["puntos"] += 3
                stats_equipos[local_id]["victorias"] += 1
                stats_equipos[visitante_id]["derrotas"] += 1
            elif partido.goles_local < partido.goles_visitante:
                # Gana visitante
                stats_equipos[visitante_id]["puntos"] += 3
                stats_equipos[visitante_id]["victorias"] += 1
                stats_equipos[local_id]["derrotas"] += 1
            else:
                # Empate
                stats_equipos[local_id]["puntos"] += 1
                stats_equipos[local_id]["empates"] += 1
                stats_equipos[visitante_id]["puntos"] += 1
                stats_equipos[visitante_id]["empates"] += 1

    # Calcular diferencia de goles
    for equipo_id in stats_equipos:
        stats_equipos[equipo_id]["diferencia_goles"] = (
            stats_equipos[equipo_id]["goles_a_favor"] - stats_equipos[equipo_id]["goles_en_contra"]
        )

    # Agrupar y ordenar equipos por grupo
    reporte_por_grupos: Dict[Grupos, List[PosicionEquipoReporte]] = {grupo: [] for grupo in Grupos}

    for equipo_data in stats_equipos.values():
        equipo_reporte = PosicionEquipoReporte(**equipo_data)
        reporte_por_grupos[equipo_reporte.grupo].append(equipo_reporte)

    # Ordenar cada grupo: Puntos (desc), Diferencia de Goles (desc), Goles a Favor (desc), Nombre (asc)
    for grupo, equipos_lista in reporte_por_grupos.items():
        equipos_lista.sort(
            key=lambda x: (x.puntos, x.diferencia_goles, x.goles_a_favor, x.nombre),
            reverse=True # Puntos, DG, GF en orden descendente. Nombre en ascendente se maneja con `-x.nombre` o sin `reverse`
        )
        # Para el nombre en ascendente, necesitas una segunda pasada de ordenación si el resto es descendente
        # o un truco como invertir el valor al ordenar
        # La solución más limpia es ordenar múltiples veces si tienes diferentes órdenes de ASc/DESC
        # o usar un "cmp_to_key" si python 3.4 o menos.
        # Para simplificar aquí, ordenamos primero por nombre, luego por GF, luego DG, luego Puntos
        equipos_lista.sort(key=lambda x: x.nombre) # Nombre ascendente
        equipos_lista.sort(key=lambda x: x.goles_a_favor, reverse=True) # Goles a favor descendente
        equipos_lista.sort(key=lambda x: x.diferencia_goles, reverse=True) # Diferencia de goles descendente
        equipos_lista.sort(key=lambda x: x.puntos, reverse=True) # Puntos descendente


    print("DEBUG (operations): Reporte por grupos generado y ordenado.")
    return reporte_por_grupos

