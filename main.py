from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import List
from utils.connection_db import *
from contextlib import asynccontextmanager
from models import *
from operations import (create_equipo_sql, obtener_todos_los_equipos, obtener_equipo_por_id, eliminar_equipo_sql, obtener_todos_los_partidos
, obtener_partido_por_id, eliminar_partido_sql, generar_reportes_por_pais)



@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
app = FastAPI(lifespan=lifespan)


# ----------- OTROS --------------
@app.get("/")
async def root():
    return {"message": "Bienvenido a la API de Equipos, Partidos y Reportes"}

@app.get("/hello/{name}")
async def saludar(name: str):
    return {"message": f"Hola {name}"}

@app.exception_handler(HTTPException)
async def manejar_excepciones_http(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": "Ocurrió un error",
            "detail": exc.detail,
            "path": request.url.path
        },
    )

@app.get("/error")
async def lanzar_error():
    raise HTTPException(status_code=400)



# ----------- EQUIPOS --------------
@app.post("/equipos/", response_model=EquipoSQL)
async def crear_equipo(equipo: EquipoCreate, session: AsyncSession = Depends(get_session)):
    equipo_db = EquipoSQL(
        nombre=equipo.nombre,
        pais=equipo.pais,
        grupo=equipo.grupo,
        puntos=equipo.puntos,
        tarjetas_amarillas=0,
        tarjetas_rojas=0,
        tiros_esquina=0,
        tiros_libres=0,
        goles_a_favor=0,
        goles_en_contra=0,
        faltas=0,
        fueras_de_juego=0,
        pases=0
    )
    return await create_equipo_sql(session, equipo_db)


@app.get("/equipos/", response_model=List[EquipoSQL])
async def listar_equipos(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_equipos(session)


@app.get("/equipos/{equipo_id}", response_model=EquipoSQL)
async def obtener_equipo(equipo_id: int, session: AsyncSession = Depends(get_session)):
    equipo = await obtener_equipo_por_id(session, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo





@app.delete("/equipos/{equipo_id}")
async def eliminar_equipo(equipo_id: int, session: AsyncSession = Depends(get_session)):
    eliminado = await eliminar_equipo_sql(session, equipo_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return {"ok": True}

# ----------- PARTIDOS --------------
@app.post("/partidos/", response_model=PartidoSQL)
async def crear_partido(partido: PartidoSQL, session: AsyncSession = Depends(get_session)):
    # Validar y convertir created_at si viene como string
    if isinstance(partido.created_at, str):
        partido.created_at = datetime.fromisoformat(partido.created_at.replace("Z", "+00:00"))

    # Guardar el partido
    session.add(partido)
    await session.commit()
    await session.refresh(partido)

    # Buscar los equipos involucrados
    equipo_local = await session.get(EquipoSQL, partido.equipo_local_id)
    equipo_visitante = await session.get(EquipoSQL, partido.equipo_visitante_id)

    if not equipo_local or not equipo_visitante:
        raise HTTPException(status_code=404, detail="Uno de los equipos no fue encontrado")

    # Actualizar estadísticas del equipo local
    equipo_local.goles_a_favor += partido.goles_local
    equipo_local.goles_en_contra += partido.goles_visitante
    equipo_local.tarjetas_amarillas += partido.tarjetas_amarillas_local
    equipo_local.tarjetas_rojas += partido.tarjetas_rojas_local
    equipo_local.tiros_esquina += partido.tiros_esquina_local
    equipo_local.tiros_libres += partido.tiros_libres_local

    # Actualizar estadísticas del equipo visitante
    equipo_visitante.goles_a_favor += partido.goles_visitante
    equipo_visitante.goles_en_contra += partido.goles_local
    equipo_visitante.tarjetas_amarillas += partido.tarjetas_amarillas_visitante
    equipo_visitante.tarjetas_rojas += partido.tarjetas_rojas_visitante
    equipo_visitante.tiros_esquina += partido.tiros_esquina_visitante
    equipo_visitante.tiros_libres += partido.tiros_libres_visitante

    # Actualizar puntos
    if partido.goles_local > partido.goles_visitante:
        equipo_local.puntos += 3
    elif partido.goles_local < partido.goles_visitante:
        equipo_visitante.puntos += 3
    else:
        equipo_local.puntos += 1
        equipo_visitante.puntos += 1

    session.add_all([equipo_local, equipo_visitante])
    await session.commit()

    return partido

@app.get("/partidos/", response_model=List[PartidoSQL])
async def listar_partidos(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_partidos(session)


@app.get("/partidos/{partido_id}", response_model=PartidoSQL)
async def obtener_partido(partido_id: int, session: AsyncSession = Depends(get_session)):
    partido = await obtener_partido_por_id(session, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido





@app.delete("/partidos/{partido_id}")
async def eliminar_partido(partido_id: int, session: AsyncSession = Depends(get_session)):
    eliminado = await eliminar_partido_sql(session, partido_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return {"ok": True}

# ----------- REPORTES --------------

@app.get("/reportes/pais/{pais}", response_model=List[ReportePorPaisSQL])
async def reporte_por_pais(pais: Paises, session: AsyncSession = Depends(get_session)):
    return await generar_reportes_por_pais(session, pais)