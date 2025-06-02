from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from shutil import copyfileobj
import uuid
import os
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from utils.connection_db import *
from contextlib import asynccontextmanager
from models import *
from operations import *


# Configuración de plantilla Jinja2
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


templates = Jinja2Templates(directory="templates")
app = FastAPI(lifespan=lifespan)

# Archivos estáticos (CSS, imágenes, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ----------- VISTAS HTML (Jinja2) --------------
@app.get("/inicio", response_class=HTMLResponse)
async def mostrar_inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@app.get("/formulario-equipo", response_class=HTMLResponse)
async def formulario_equipo(request: Request):
    return templates.TemplateResponse("formulario_equipo.html", {"request": request})


@app.get("/equipos-html", response_class=HTMLResponse)
async def mostrar_equipos(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session)
    return templates.TemplateResponse("equipos.html", {"request": request, "equipos": equipos})


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
async def crear_equipo_con_logo(
    nombre: str = Form(...),
    pais: str = Form(...),
    grupo: str = Form(...),
    puntos: int = Form(...),
    logo: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    # Verificar tipo de archivo
    if logo.content_type not in ["image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Formato de imagen no válido (solo .png o .jpg)")

    # Crear nombre único para el archivo
    extension = os.path.splitext(logo.filename)[1]
    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    ruta_archivo = os.path.join("static", "img", nombre_archivo)

    # Guardar imagen
    os.makedirs("static/img", exist_ok=True)
    with open(ruta_archivo, "wb") as buffer:
        copyfileobj(logo.file, buffer)

    # Crear instancia del modelo
    equipo_db = EquipoSQL(
        nombre=nombre,
        pais=pais,
        grupo=grupo,
        puntos=puntos,
        logo_url=f"img/{nombre_archivo}",  # ruta relativa desde /static
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


@app.put("/equipos/{equipo_id}/actualizar-grupo-puntos")
async def actualizar_equipo(
    equipo_id: int,
    grupo: Optional[str] = None,
    puntos: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    equipo_actualizado = await actualizar_datos_equipo(
        session, equipo_id, nuevo_grupo=grupo, nuevos_puntos=puntos
    )
    return equipo_actualizado


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


@app.put("/partidos/{partido_id}/fase")
async def actualizar_partido_endpoint(
    partido_id: int,
    fase: str,
    session: AsyncSession = Depends(get_session)
):
    partido_actualizado = await actualizar_partidos(session, partido_id, fase)
    return partido_actualizado


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
