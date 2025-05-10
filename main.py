from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import List
from utils.connection_db import *
from contextlib import asynccontextmanager
from models import EquipoSQL, PartidoSQL, ReporteSQL, EquipoUpdate
from operations import create_equipo_sql, obtener_todos_los_equipos, obtener_equipo_por_id, actualizar_equipo_sql, eliminar_equipo_sql, create_partido_sql, obtener_todos_los_partidos, obtener_partido_por_id, actualizar_partido_sql, eliminar_partido_sql, create_reporte_sql, obtener_todos_los_reportes, obtener_reporte_por_id, actualizar_reporte_sql, eliminar_reporte_sql



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
async def crear_equipo(equipo: EquipoSQL, session: AsyncSession = Depends(get_session)):
    return await create_equipo_sql(session, equipo)


@app.get("/equipos/", response_model=List[EquipoSQL])
async def listar_equipos(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_equipos(session)


@app.get("/equipos/{equipo_id}", response_model=EquipoSQL)
async def obtener_equipo(equipo_id: int, session: AsyncSession = Depends(get_session)):
    equipo = await obtener_equipo_por_id(session, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@app.put("/equipos/{equipo_id}", response_model=EquipoSQL)
async def actualizar_equipo(
    equipo_id: int,
    nuevos_datos: EquipoUpdate,
    session: AsyncSession = Depends(get_session)
):
    datos_dict = nuevos_datos.dict(exclude_unset=True)
    equipo = await actualizar_equipo_sql(session, equipo_id, datos_dict)
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
    return await create_partido_sql(session, partido)


@app.get("/partidos/", response_model=List[PartidoSQL])
async def listar_partidos(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_partidos(session)


@app.get("/partidos/{partido_id}", response_model=PartidoSQL)
async def obtener_partido(partido_id: int, session: AsyncSession = Depends(get_session)):
    partido = await obtener_partido_por_id(session, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


@app.put("/partidos/{partido_id}", response_model=PartidoSQL)
async def actualizar_partido(
    partido_id: int,
    nuevos_datos: dict,  # {"goles_local": ..., "goles_visitante": ..., "fase": ...}
    session: AsyncSession = Depends(get_session)
):
    partido = await actualizar_partido_sql(session, partido_id, nuevos_datos)
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
@app.post("/reportes/", response_model=ReporteSQL)
async def crear_reporte(reporte: ReporteSQL, session: AsyncSession = Depends(get_session)):
    return await create_reporte_sql(session, reporte)


@app.get("/reportes/", response_model=List[ReporteSQL])
async def listar_reportes(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_reportes(session)


@app.get("/reportes/{reporte_id}", response_model=ReporteSQL)
async def obtener_reporte(reporte_id: int, session: AsyncSession = Depends(get_session)):
    reporte = await obtener_reporte_por_id(session, reporte_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return reporte


@app.put("/reportes/{reporte_id}", response_model=ReporteSQL)
async def actualizar_reporte(
    reporte_id: int,
    nuevos_datos: dict,  # {"ruta_archivo": "..."}
    session: AsyncSession = Depends(get_session)
):
    reporte = await actualizar_reporte_sql(session, reporte_id, nuevos_datos)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return reporte


@app.delete("/reportes/{reporte_id}")
async def eliminar_reporte(reporte_id: int, session: AsyncSession = Depends(get_session)):
    eliminado = await eliminar_reporte_sql(session, reporte_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return {"ok": True}

