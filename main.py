from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from shutil import copyfileobj
from sqlalchemy.orm import selectinload
from models import *
import uuid
import os
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from utils.connection_db import *
from contextlib import asynccontextmanager
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

@app.get("/formulario_equipo", response_class=HTMLResponse)
async def mostrar_formulario_equipo(request: Request):
    return templates.TemplateResponse("formulario_equipo.html", {"request": request})

@app.get("/equipo-agregado", name="mostrar_equipo_agregado", response_class=HTMLResponse)
async def mostrar_equipo_agregado(request: Request, nombre: str, grupo: str, pais: str, logo_url: str):
    return templates.TemplateResponse("equipo_agregado.html", {
        "request": request,
        "nombre": nombre,
        "grupo": grupo,
        "pais": pais,
        "logo_url": logo_url,
    })


@app.get("/formulario-actualizar-equipo", response_class=HTMLResponse)
async def mostrar_formulario_actualizar_equipo(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session)
    return templates.TemplateResponse("formulario_actualizar_equipo.html", {"request": request, "equipos": equipos})

@app.get("/formulario-buscar-equipo", response_class=HTMLResponse)
async def mostrar_formulario_buscar_equipo(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session) # Se usa para el select del formulario
    return templates.TemplateResponse("formulario_buscar_equipo.html", {"request": request, "equipos": equipos})

@app.post("/buscar-equipo/", response_class=HTMLResponse)
async def buscar_equipo_html(
    request: Request,
    equipo_id: int = Form(...),
    session: AsyncSession = Depends(get_session) # Inyecta la sesión aquí también
):
    try:
        # LLAMADA A LA NUEVA FUNCIÓN DE OPERATIONS.PY
        equipo = await obtener_equipo_y_manejar_error(session, equipo_id)

        # Si la función no lanzó una excepción, el equipo fue encontrado
        return templates.TemplateResponse(
            "equipo_encontrado.html",
            {
                "request": request,
                "equipo": equipo
            }
        )
    except HTTPException as e:
        # Captura la excepción lanzada por obtener_equipo_y_manejar_error
        # y renderiza el formulario con el mensaje de error.
        equipos = await obtener_todos_los_equipos(session)
        return templates.TemplateResponse(
            "formulario_buscar_equipo.html",
            {"request": request, "equipos": equipos, "error_message": e.detail}
        )
    except Exception as e:
        # Para cualquier otro error inesperado
        equipos = await obtener_todos_los_equipos(session)
        return templates.TemplateResponse(
            "formulario_buscar_equipo.html",
            {"request": request, "equipos": equipos, "error_message": f"Error interno del servidor: {e}"}
        )

@app.post("/actualizar-equipo/", response_class=HTMLResponse)
async def actualizar_equipo_html(
    request: Request,
    equipo_id: int = Form(...),
    nuevo_grupo: str = Form(...),
    nuevos_puntos: int = Form(...)
):
    async with AsyncSession(engine) as session:
        try:
            equipo_actualizado = await actualizar_grupo_y_puntos_equipo(
                session,
                equipo_id=equipo_id,
                nuevo_grupo=nuevo_grupo,
                nuevos_puntos=nuevos_puntos
            )
            # --- CAMBIO AQUÍ ---
            # En lugar de redirigir, renderiza la plantilla de confirmación con los datos del equipo
            return templates.TemplateResponse(
                "equipo_actualizado.html",
                {
                    "request": request,
                    "nombre": equipo_actualizado.nombre,
                    "grupo": equipo_actualizado.grupo,
                    "puntos": equipo_actualizado.puntos,
                    "pais": equipo_actualizado.pais,  # Asegúrate de pasar el país
                    "logo_url": equipo_actualizado.logo_url
                }
            )
            # --- FIN DEL CAMBIO ---
        except HTTPException as e:
            equipos = await obtener_todos_los_equipos(session)
            return templates.TemplateResponse(
                "formulario_actualizar_equipo.html",
                {"request": request, "equipos": equipos, "error_message": e.detail}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")



@app.get("/partido/formulario", response_class=HTMLResponse)
async def mostrar_formulario_partido(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EquipoSQL))
    equipos = result.scalars().all()
    return templates.TemplateResponse("formulario_partido.html", {"request": request, "equipos": equipos})

@app.get("/equipos-html", response_class=HTMLResponse)
async def mostrar_equipos(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session)
    return templates.TemplateResponse("equipos.html", {"request": request, "equipos": equipos})


# NUEVA RUTA para mostrar todos los partidos en un template HTML
@app.get("/partidos/", response_class=HTMLResponse)
async def mostrar_partidos(request: Request, session: AsyncSession = Depends(get_session)):
    partidos = await obtener_todos_los_partidos(session)
    return templates.TemplateResponse("partidos.html", {"request": request, "partidos": partidos})



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
@app.post("/equipos/", response_class=HTMLResponse)
async def crear_equipo_con_logo(
    request: Request,
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
        logo_url=f"img/{nombre_archivo}",
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

    # Guardar en base de datos
    await create_equipo_sql(session, equipo_db)

    # Redireccionar al HTML con modal
    url = str(request.url_for("mostrar_equipo_agregado")) + \
          f"?nombre={nombre}&grupo={grupo}&pais={pais}&logo_url={equipo_db.logo_url}"

    return RedirectResponse(url=url, status_code=303)




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
async def crear_partido(
    equipo_local_id: int = Form(...),
    equipo_visitante_id: int = Form(...),
    goles_local: int = Form(...),
    goles_visitante: int = Form(...),
    tarjetas_amarillas_local: int = Form(...),
    tarjetas_amarillas_visitante: int = Form(...),
    tarjetas_rojas_local: int = Form(...),
    tarjetas_rojas_visitante: int = Form(...),
    tiros_esquina_local: int = Form(...),
    tiros_esquina_visitante: int = Form(...),
    tiros_libres_local: int = Form(...),
    tiros_libres_visitante: int = Form(...),
    faltas_local: int = Form(...),
    faltas_visitante: int = Form(...),
    fueras_de_juego_local: int = Form(...),
    fueras_de_juego_visitante: int = Form(...),
    pases_local: int = Form(...),
    pases_visitante: int = Form(...),
    fase: Fases = Form(...),
    session: AsyncSession = Depends(get_session)
):
    partido = PartidoSQL(
        equipo_local_id=equipo_local_id,
        equipo_visitante_id=equipo_visitante_id,
        goles_local=goles_local,
        goles_visitante=goles_visitante,
        tarjetas_amarillas_local=tarjetas_amarillas_local,
        tarjetas_amarillas_visitante=tarjetas_amarillas_visitante,
        tarjetas_rojas_local=tarjetas_rojas_local,
        tarjetas_rojas_visitante=tarjetas_rojas_visitante,
        tiros_esquina_local=tiros_esquina_local,
        tiros_esquina_visitante=tiros_esquina_visitante,
        tiros_libres_local=tiros_libres_local,
        tiros_libres_visitante=tiros_libres_visitante,
        faltas_local=faltas_local,
        faltas_visitante=faltas_visitante,
        fueras_de_juego_local=fueras_de_juego_local,
        fueras_de_juego_visitante=fueras_de_juego_visitante,
        pases_local=pases_local,
        pases_visitante=pases_visitante,
        fase=fase
    )
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
