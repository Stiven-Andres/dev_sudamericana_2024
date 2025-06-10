from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from shutil import copyfileobj
from sqlalchemy.orm import selectinload
from utils.sportmonks import get_equipos_copa_sudamericana
from operations import create_equipo_sql
from models import EquipoSQL, Paises, Grupos
from sqlmodel.ext.asyncio.session import AsyncSession

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
UPLOAD_DIR = "static/logos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Archivos estáticos (CSS, imágenes, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ----------- VISTAS HTML (Jinja2) --------------
@app.get("/inicio", response_class=HTMLResponse)
async def mostrar_inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@app.get("/formulario-equipo", response_class=HTMLResponse)
async def formulario_equipo(request: Request):
    # Pasa el Enum Paises al template para el dropdown
    return templates.TemplateResponse("formulario_equipo.html", {"request": request, "Paises": Paises})

# NEW ENDPOINT: Display form to restore inactive matches
@app.get("/partidos/restaurar", response_class=HTMLResponse)
async def mostrar_formulario_restaurar_partido(request: Request, session: AsyncSession = Depends(get_session)):
    partidos_inactivos = await obtener_todos_los_partidos_inactivos(session)
    return templates.TemplateResponse("restaurar_partidos.html", {"request": request, "partidos": partidos_inactivos})

@app.get("/formulario_equipo", response_class=HTMLResponse)
async def mostrar_formulario_equipo(request: Request):
    return templates.TemplateResponse("formulario_equipo.html", {"request": request})

@app.get("/partido/formulario", response_class=HTMLResponse)
async def mostrar_formulario_partido(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EquipoSQL))
    equipos = result.scalars().all()
    return templates.TemplateResponse("formulario_partido.html", {"request": request, "equipos": equipos})

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
    return templates.TemplateResponse("Formulario_buscar_equipo.html", {"request": request, "equipos": equipos})

@app.get("/formulario-buscar-partido/", response_class=HTMLResponse)
async def mostrar_formulario_buscar_partido(request: Request, session: AsyncSession = Depends(get_session)):
    # No necesitamos cargar equipos para este formulario, solo el ID
    return templates.TemplateResponse("formulario_buscar_partido.html", {"request": request})

@app.get("/formulario-modificar-partido/", response_class=HTMLResponse)
async def mostrar_formulario_modificar_partido(request: Request):
    return templates.TemplateResponse("formulario_modificar_partido.html", {"request": request})

@app.get("/formulario-eliminar-equipo", response_class=HTMLResponse)
async def mostrar_formulario_eliminar_equipo(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session)  # Necesitamos la lista de equipos para el select
    return templates.TemplateResponse("formulario_eliminar_equipo.html", {"request": request, "equipos": equipos})

@app.get("/formulario-eliminar-partido/", response_class=HTMLResponse)
async def mostrar_formulario_eliminar_partido(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Muestra el formulario para eliminar un partido, con una lista de todos los partidos.
    """
    # Obtener todos los partidos para el selector, cargando equipos para nombres
    partidos = await obtener_todos_los_partidos(session)
    return templates.TemplateResponse("formulario_eliminar_partido.html", {"request": request, "partidos": partidos})

@app.post("/buscar-equipo/", response_class=HTMLResponse)
async def buscar_equipo_html(
    request: Request,
    equipo_id: int = Form(...),
    session: AsyncSession = Depends(get_session) # Inyecta la sesión aquí también
):
    try:
        equipo = await obtener_equipo_y_manejar_error(session, equipo_id)

        return templates.TemplateResponse(
            "equipo_encontrado.html",
            {
                "request": request,
                "equipo": equipo
            }
        )
    except HTTPException as e:
        equipos = await obtener_todos_los_equipos(session)
        return templates.TemplateResponse(
            "formulario_buscar_equipo.html",
            {"request": request, "equipos": equipos, "error_message": e.detail}
        )
    except Exception as e:

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

        except HTTPException as e:
            equipos = await obtener_todos_los_equipos(session)
            return templates.TemplateResponse(
                "formulario_actualizar_equipo.html",
                {"request": request, "equipos": equipos, "error_message": e.detail}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")




@app.post("/partidos/buscar", response_class=HTMLResponse)
async def buscar_partido_por_id_html(request: Request, id_partido: int = Form(...), session: AsyncSession = Depends(get_session)):
    print(f"DEBUG: [main.py] Recibido ID del formulario: {id_partido}, tipo: {type(id_partido)}") # Para depuración
    try:
        partido = await obtener_partido_por_id(session, id_partido)

        if partido:
            print(f"DEBUG: [main.py] Partido encontrado en main.py para ID {id_partido}. Renderizando partido_encontrado.html")
            return templates.TemplateResponse("partido_encontrado.html", {"request": request, "partido": partido})
        else:
            print(f"DEBUG: [main.py] Partido NO encontrado en main.py para ID {id_partido}. Renderizando partido_encontrado.html con partido=None")
            # Si el partido no se encuentra, pasamos 'partido=None' explícitamente.
            # El template 'partido_encontrado.html' ya maneja este caso con el 'else'.
            return templates.TemplateResponse("partido_encontrado.html", {"request": request, "partido": None})

    except Exception as e:
        print(f"ERROR: [main.py] Error al buscar partido en main.py: {e}")
        # Puedes mostrar un mensaje de error más amigable al usuario
        # O redirigir a una página de error
        return templates.TemplateResponse(
            "partido_encontrado.html", # Puedes crear un template específico para errores si prefieres
            {"request": request, "partido": None, "error_message": f"Hubo un error al procesar tu solicitud: {e}"}
        )


@app.post("/partidos/buscar", response_class=HTMLResponse)
async def buscar_partido_por_id_html(request: Request, id_partido: int = Form(...), session: AsyncSession = Depends(get_session)):

    print(f"Recibido ID del formulario: {id_partido}") # Para depuración
    try:
        partido = await obtener_partido_por_id(session, id_partido)
        return templates.TemplateResponse("partido_encontrado.html", {"request": request, "partido": partido})
    except Exception as e:
        print(f"Error al buscar partido: {e}") # Para depuración
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


# NEW ENDPOINT: Handle restoration of inactive match
@app.post("/partidos/restaurar/{partido_id}", response_class=RedirectResponse, status_code=303)
async def restaurar_partido_endpoint(partido_id: int, session: AsyncSession = Depends(get_session)):
    restaurado = await restaurar_partido_sql(session, partido_id)
    if not restaurado:
        raise HTTPException(status_code=404, detail="Partido inactivo no encontrado o ya está activo")
    return RedirectResponse(url="/partidos/activos", status_code=303)

@app.post("/eliminar-equipo/", response_class=HTMLResponse)
async def eliminar_equipo_html(
    request: Request,
    equipo_id: int = Form(...),
    session: AsyncSession = Depends(get_session)
):
    print(f"DEBUG (main): POST /eliminar-equipo/ recibido. ID del formulario: '{equipo_id}' (tipo: {type(equipo_id)})")

    equipo_a_eliminar_temp = None # Para guardar los datos del equipo antes de borrarlo
    try:
        # Primero, obtener los datos del equipo para mostrarlos en el modal de confirmación
        # Si el equipo no existe, la función ya lanzará una HTTPException
        print(f"DEBUG (main): Llamando a obtener_equipo_y_manejar_error para ID: {equipo_id}")
        equipo_a_eliminar_temp = await obtener_equipo_y_manejar_error(session, equipo_id)
        print(f"DEBUG (main): Equipo encontrado en operations: {equipo_a_eliminar_temp.nombre} (ID: {equipo_a_eliminar_temp.id})")

        # Luego, proceder con la eliminación
        print(f"DEBUG (main): Llamando a eliminar_equipo_sql para ID: {equipo_id}")
        await eliminar_equipo_sql(session, equipo_id)
        print(f"DEBUG (main): Equipo eliminado exitosamente en operations.")

        # Si la eliminación fue exitosa, renderiza el modal de confirmación
        return templates.TemplateResponse(
            "equipo_eliminado.html",
            {
                "request": request,
                "eliminado_exitosamente": True, # Asegúrate de pasar esto si tu HTML lo espera
                "nombre": equipo_a_eliminar_temp.nombre,
                "id": equipo_a_eliminar_temp.id,
                "logo_url": equipo_a_eliminar_temp.logo_url,
                "pais": equipo_a_eliminar_temp.pais, # Añadir esto para el modal, si es necesario
                "grupo": equipo_a_eliminar_temp.grupo # Añadir esto para el modal, si es necesario
            }
        )
    except HTTPException as e:
        print(f"DEBUG (main): HTTPException capturada: {e.detail}")
        # Captura la excepción lanzada si el equipo no se encuentra
        equipos = await obtener_todos_los_equipos(session)
        return templates.TemplateResponse(
            "formulario_eliminar_equipo.html",
            {"request": request, "equipos": equipos, "error_message": e.detail}
        )
    except Exception as e:
        print(f"DEBUG (main): ERROR INESPERADO: {e}")
        # Para cualquier otro error inesperado
        equipos = await obtener_todos_los_equipos(session)
        return templates.TemplateResponse(
            "formulario_eliminar_equipo.html",
            {"request": request, "equipos": equipos, "error_message": f"Error interno del servidor: {e}"}
        )

# NEW ENDPOINT: Listar partidos inactivos (HTML)
@app.get("/partidos/inactivos", response_class=HTMLResponse)
async def listar_partidos_inactivos_html(request: Request, session: AsyncSession = Depends(get_session)):
    partidos_inactivos = await obtener_todos_los_partidos_inactivos(session)
    return templates.TemplateResponse("lista_partidos_inactivos.html", {"request": request, "partidos": partidos_inactivos})



@app.get("/equipos-html", response_class=HTMLResponse)
async def mostrar_equipos(request: Request, session: AsyncSession = Depends(get_session)):
    equipos = await obtener_todos_los_equipos(session)
    return templates.TemplateResponse("equipos.html", {"request": request, "equipos": equipos})


@app.get("/partidos/", response_class=HTMLResponse)
async def mostrar_partidos(request: Request, session: AsyncSession = Depends(get_session)):
    partidos = await obtener_todos_los_partidos(session)
    return templates.TemplateResponse("partidos.html", {"request": request, "partidos": partidos})



@app.post("/modificar-partido/buscar", response_class=HTMLResponse)
async def buscar_partido_para_modificar(
        request: Request,
        partido_id: int = Form(...),
        session: AsyncSession = Depends(get_session)
):
    print(f"DEBUG (main): POST /modificar-partido/buscar recibido. ID del formulario: '{partido_id}'")
    try:
        partido = await obtener_partido_por_id(session, partido_id)  # Esta función ya carga relaciones
        if not partido:
            raise HTTPException(status_code=404, detail=f"Partido con ID '{partido_id}' no encontrado.")

        print(f"DEBUG (main): Partido {partido.id} encontrado para modificar.")
        return templates.TemplateResponse(
            "formulario_actualizar_partido_encontrado.html",
            {
                "request": request,
                "partido": partido,
                "fases_disponibles": Fases  # Pasar el Enum de Fases al template
            }
        )
    except HTTPException as e:
        print(f"DEBUG (main): HTTPException al buscar partido para modificar: {e.detail}")
        return templates.TemplateResponse(
            "formulario_modificar_partido.html",
            {"request": request, "error_message": e.detail}
        )
    except Exception as e:
        print(f"DEBUG (main): ERROR INESPERADO al buscar partido para modificar: {e}")
        return templates.TemplateResponse(
            "formulario_modificar_partido.html",
            {"request": request, "error_message": f"Error interno del servidor: {e}"}
        )

@app.get("/partidos/activos", response_class=HTMLResponse)
async def listar_partidos_activos_html(request: Request, session: AsyncSession = Depends(get_session)):
    # This function will fetch active matches and render a template
    # You need a template file named 'lista_partidos_activos.html' (or similar)
    # in your 'templates' directory.
    partidos = await obtener_todos_los_partidos(session) # This should fetch only active ones if implemented in operations.py
    return templates.TemplateResponse("lista_partidos_activos.html", {"request": request, "partidos": partidos})

@app.post("/modificar-partido/{partido_id}", response_class=HTMLResponse)
async def procesar_modificacion_partido(
        request: Request,
        partido_id: int,  # Ya viene en la URL
        goles_local: int = Form(...),
        goles_visitante: int = Form(...),
        tarjetas_amarillas_local: int = Form(0),
        tarjetas_amarillas_visitante: int = Form(0),
        tarjetas_rojas_local: int = Form(0),
        tarjetas_rojas_visitante: int = Form(0),
        tiros_esquina_local: int = Form(0),
        tiros_esquina_visitante: int = Form(0),
        tiros_libres_local: int = Form(0),
        tiros_libres_visitante: int = Form(0),
        faltas_local: int = Form(0),
        faltas_visitante: int = Form(0),
        fueras_de_juego_local: int = Form(0),
        fueras_de_juego_visitante: int = Form(0),
        pases_local: int = Form(0),
        pases_visitante: int = Form(0),
        fecha: str = Form(None),  # Si permites modificar la fecha
        fase: Fases = Form(...),  # Asegúrate de que este Form sea del tipo Fases
        session: AsyncSession = Depends(get_session)
):
    """
    Procesa los datos enviados para actualizar un partido.
    """
    print(f"DEBUG (main): POST /modificar-partido/{partido_id} recibido. Procesando actualización.")

    datos_actualizados = {
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "tarjetas_amarillas_local": tarjetas_amarillas_local,
        "tarjetas_amarillas_visitante": tarjetas_amarillas_visitante,
        "tarjetas_rojas_local": tarjetas_rojas_local,
        "tarjetas_rojas_visitante": tarjetas_rojas_visitante,
        "tiros_esquina_local": tiros_esquina_local,
        "tiros_esquina_visitante": tiros_esquina_visitante,
        "tiros_libres_local": tiros_libres_local,
        "tiros_libres_visitante": tiros_libres_visitante,
        "faltas_local": faltas_local,
        "faltas_visitante": faltas_visitante,
        "fueras_de_juego_local": fueras_de_juego_local,
        "fueras_de_juego_visitante": fueras_de_juego_visitante,
        "pases_local": pases_local,
        "pases_visitante": pases_visitante,
        "fase": fase.value,  # Pasa el valor string del enum
    }

    if fecha:  # Si la fecha se envía y no es None
        # Necesitas una función para convertir string a date/datetime si tu modelo lo requiere
        from datetime import date
        try:
            datos_actualizados["fecha"] = date.fromisoformat(fecha)
        except ValueError:
            print(f"ERROR (main): Formato de fecha inválido para partido {partido_id}: {fecha}")
            # Puedes manejar este error volviendo al formulario con un mensaje
            partido = await obtener_partido_por_id(session, partido_id)
            return templates.TemplateResponse(
                "formulario_actualizar_partido_encontrado.html",
                {
                    "request": request,
                    "partido": partido,
                    "fases_disponibles": Fases,
                    "error_message": "Formato de fecha inválido. Utiliza AAAA-MM-DD."
                }
            )

    try:
        partido_actualizado = await actualizar_partido_sql(session, partido_id, datos_actualizados)

        if not partido_actualizado:
            raise HTTPException(status_code=404, detail=f"Partido con ID '{partido_id}' no encontrado para actualizar.")

        print(f"DEBUG (main): Partido {partido_actualizado.id} actualizado exitosamente.")
        # Redirige a una página de éxito o al mismo formulario con un mensaje de éxito
        return templates.TemplateResponse(
            "formulario_actualizar_partido_encontrado.html",
            {
                "request": request,
                "partido": partido_actualizado,
                "fases_disponibles": Fases,
                "success_message": "Partido actualizado exitosamente!"
            }
        )
    except HTTPException as e:
        print(f"DEBUG (main): HTTPException al procesar modificación de partido: {e.detail}")
        # Recargar el partido para mostrarlo de nuevo en el formulario con el error
        partido = await obtener_partido_por_id(session, partido_id)
        return templates.TemplateResponse(
            "formulario_actualizar_partido_encontrado.html",
            {
                "request": request,
                "partido": partido,
                "fases_disponibles": Fases,
                "error_message": e.detail
            }
        )
    except Exception as e:
        print(f"DEBUG (main): ERROR INESPERADO al procesar modificación de partido: {e}")
        # Recargar el partido para mostrarlo de nuevo en el formulario con el error
        partido = await obtener_partido_por_id(session, partido_id)
        return templates.TemplateResponse(
            "formulario_actualizar_partido_encontrado.html",
            {
                "request": request,
                "partido": partido,
                "fases_disponibles": Fases,
                "error_message": f"Error interno del servidor: {e}"
            }
        )


@app.post("/eliminar-partido/", response_class=HTMLResponse)
async def procesar_eliminar_partido(
        request: Request,
        partido_id: int = Form(...),
        session: AsyncSession = Depends(get_session)
):
    print(f"DEBUG (main): POST /eliminar-partido/ recibido. ID del partido a eliminar: {partido_id}")
    eliminado_exitosamente = False
    try:
        eliminado_exitosamente = await eliminar_partido_sql(session, partido_id)
        if not eliminado_exitosamente:
            raise HTTPException(status_code=404, detail=f"Partido con ID '{partido_id}' no encontrado.")

        print(f"DEBUG (main): Partido {partido_id} eliminado exitosamente.")
        return templates.TemplateResponse(
            "partido_eliminado.html",
            {"request": request, "eliminado_exitosamente": True, "partido_id": partido_id}
        )
    except HTTPException as e:
        print(f"DEBUG (main): HTTPException al eliminar partido: {e.detail}")
        return templates.TemplateResponse(
            "partido_eliminado.html",
            {"request": request, "eliminado_exitosamente": False, "partido_id": partido_id, "error_message": e.detail}
        )
    except Exception as e:
        print(f"DEBUG (main): ERROR INESPERADO al eliminar partido: {e}")
        return templates.TemplateResponse(
            "partido_eliminado.html",
            {"request": request, "eliminado_exitosamente": False, "partido_id": partido_id,
             "error_message": f"Error interno del servidor: {e}"}
        )


# Necesitamos una función para obtener un equipo por ID sin importar su estado para la confirmación de restauración
async def obtener_equipo_por_id_incluir_inactivo(session: AsyncSession, equipo_id: int) -> Optional[EquipoSQL]:
    result = await session.execute(
        select(EquipoSQL).where(EquipoSQL.id == equipo_id)
    )
    return result.scalars().first()


@app.get("/equipos-inactivos/", response_class=HTMLResponse)
async def mostrar_equipos_inactivos(request: Request, session: AsyncSession = Depends(get_session)):
    equipos_inactivos = await obtener_todos_los_equipos_inactivos(session)
    return templates.TemplateResponse("equipos_inactivos.html", {"request": request, "equipos": equipos_inactivos})


@app.get("/formulario-restaurar-equipo/", response_class=HTMLResponse)
async def mostrar_formulario_restaurar_equipo(request: Request, session: AsyncSession = Depends(get_session)):
    equipos_inactivos = await obtener_todos_los_equipos_inactivos(session)  # Solo muestra inactivos para restaurar
    return templates.TemplateResponse("formulario_restaurar_equipo.html",
                                      {"request": request, "equipos": equipos_inactivos})


@app.post("/restaurar-equipo/", response_class=HTMLResponse)
async def restaurar_equipo_post(request: Request, equipo_id: int = Form(...),
                                session: AsyncSession = Depends(get_session)):
    equipo = await obtener_equipo_por_id_incluir_inactivo(session,
                                                          equipo_id)  # Para obtener detalles del equipo antes de restaurar
    if not equipo:
        return templates.TemplateResponse("equipo_restaurado.html",
                                          {"request": request, "restaurado_exitosamente": False, "id": equipo_id,
                                           "nombre": "Desconocido", "pais": "Desconocido", "grupo": "Desconocido",
                                           "logo_url": None})

    restaurado = await restaurar_equipo_sql(session, equipo_id)

    return templates.TemplateResponse("equipo_restaurado.html", {
        "request": request,
        "restaurado_exitosamente": restaurado,
        "id": equipo.id,
        "nombre": equipo.nombre,
        "pais": equipo.pais.value,
        "grupo": equipo.grupo,
        "logo_url": equipo.logo_url
    })


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
async def crear_partido(
    request: Request,
    nombre: str = Form(...),
    pais: str = Form(...),
    grupo: str = Form(...),
    puntos: int = Form(...),
    logo: UploadFile = File(...),
    esta_activo: bool = Form(True),
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
        pases=0,
        esta_activo = esta_activo
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
    equipo_actualizado = await actualizar_equipo_sql(
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
@app.post("/partidos/", response_model=PartidoSQL) # Si esperas un HTMLResponse, cambia esto a HTMLResponse
async def crear_partido(
    request: Request, # <--- ¡IMPORTANTE! Agrega Request aquí
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
    # Asegúrate de incluir la fecha_partido si es un campo de tu modelo PartidoSQL
    fecha_partido: str = Form(...), # Agregado, ya que PartidoSQL lo tiene en models.py
    session: AsyncSession = Depends(get_session)
):
    try:
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
            fase=fase,
            # Asegúrate de pasar la fecha_partido. Usa remove_tzinfo si es necesario.
            fecha_partido=remove_tzinfo(fecha_partido),
            esta_activo=True # Asumo que siempre es True al crear
        )
        # Llama a create_partido_sql con el objeto 'partido'
        await create_partido_sql(session, partido)
        # Redirige a una página de éxito
        return RedirectResponse(url=f"/partido_agregado/{partido.id}", status_code=303)

    except HTTPException as e:
        # Aquí renderizamos el template de error genérico
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": e.detail},  # Pasamos solo el mensaje de error
            status_code=e.status_code  # Aseguramos que la respuesta HTTP sea 400
        )
    except Exception as e:
        # Para cualquier otro error inesperado, también usamos el template de error
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": f"Ocurrió un error inesperado: {e}"},
            status_code=500  # Un error interno del servidor
        )



@app.get("/partido_agregado/{partido_id}", response_class=HTMLResponse)
async def mostrar_partido_agregado(partido_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    partido = await obtener_partido_por_id(session, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # Cargar los equipos relacionados para mostrar sus nombres
    partido_con_equipos = await session.execute(
        select(PartidoSQL)
        .options(selectinload(PartidoSQL.equipo_local), selectinload(PartidoSQL.equipo_visitante))
        .where(PartidoSQL.id == partido_id)
    )
    partido_con_equipos = partido_con_equipos.scalar_one_or_none()

    if not partido_con_equipos:
        raise HTTPException(status_code=404, detail="Partido no encontrado con detalles de equipo")


    return templates.TemplateResponse("partido_agregado.html", {"request": request, "partido": partido_con_equipos})

@app.get("/partidos/", response_model=List[PartidoSQL])
async def listar_partidos(session: AsyncSession = Depends(get_session)):
    return await obtener_todos_los_partidos(session)



@app.post("/buscar-partido/", response_class=HTMLResponse)
async def buscar_partido_html(
        request: Request,
        partido_id: int = Form(...),
        session: AsyncSession = Depends(get_session)
):
    print(f"DEBUG (main): POST /buscar-partido/ recibido. ID del formulario: '{partido_id}' (tipo: {type(partido_id)})")

    partido_encontrado = None
    try:
        partido_encontrado = await obtener_partido_por_id(session, partido_id)
        if not partido_encontrado:
            raise HTTPException(status_code=404, detail=f"Partido con ID '{partido_id}' no encontrado.")

        print(f"DEBUG (main): Partido encontrado: {partido_encontrado.id}, Fase: {partido_encontrado.fase}")
        return templates.TemplateResponse(
            "partido_encontrado.html",
            {"request": request, "partido": partido_encontrado}
        )
    except HTTPException as e:
        print(f"DEBUG (main): HTTPException capturada: {e.detail}")
        return templates.TemplateResponse(
            "formulario_buscar_partido.html",
            {"request": request, "error_message": e.detail}
        )
    except Exception as e:
        print(f"DEBUG (main): ERROR INESPERADO al buscar partido: {e}")
        return templates.TemplateResponse(
            "formulario_buscar_partido.html",
            {"request": request, "error_message": f"Error interno del servidor: {e}"}
        )



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
    partido_actualizado = await actualizar_partido_sql(session, partido_id, fase)
    return partido_actualizado


@app.delete("/partidos/{partido_id}")
async def eliminar_partido(partido_id: int, session: AsyncSession = Depends(get_session)):
    eliminado = await eliminar_partido_sql(session, partido_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return {"ok": True}


# ----------- REPORTES --------------
@app.get("/reportes/pais", response_class=HTMLResponse)
async def mostrar_formulario_reporte_pais(request: Request):
    paises = [p.value for p in Paises] # Get all country names from the Paises Enum
    return templates.TemplateResponse("formulario_reporte_pais.html", {"request": request, "paises": paises})

@app.post("/reportes/pais", response_class=HTMLResponse)
async def generar_reporte_pais_html(
    request: Request,
    pais_seleccionado: Paises = Form(..., alias="pais"), # Use alias to match form field name
    session: AsyncSession = Depends(get_session)
):
    try:
        reporte = await generar_reportes_por_pais(session, pais_seleccionado)
        return RedirectResponse(url=f"/reportes/pais/{pais_seleccionado.value}", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar reporte: {e}")

@app.get("/reportes/pais/{pais_nombre}", response_class=HTMLResponse)
async def ver_reporte_pais_html(
    request: Request,
    pais_nombre: Paises, # FastAPI will automatically convert string to Paises enum
    session: AsyncSession = Depends(get_session)
):
    reporte = await obtener_reporte_por_pais(session, pais_nombre)
    if not reporte:
        try:
            reporte = await generar_reportes_por_pais(session, pais_nombre)
            return templates.TemplateResponse("reporte_pais_detalle.html", {"request": request, "reporte": reporte})
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No se pudo generar ni encontrar el reporte para {pais_nombre.value}: {e}")

    return templates.TemplateResponse("reporte_pais_detalle.html", {"request": request, "reporte": reporte})

@app.get("/reportes/todos", response_class=HTMLResponse)
async def listar_todos_los_reportes_html(request: Request, session: AsyncSession = Depends(get_session)):
    reportes = await obtener_todos_los_reportes_por_pais(session)
    return templates.TemplateResponse("lista_reportes_todos.html", {"request": request, "reportes": reportes})

@app.get("/reportes/fase", response_class=HTMLResponse)
async def mostrar_formulario_reporte_fase(request: Request):
    fases = [f.value for f in Fases] # Get all phase names from the Fases Enum
    return templates.TemplateResponse("formulario_reporte_fase.html", {"request": request, "fases": fases})

@app.get("/reportes/fase/todos", response_class=HTMLResponse)
async def listar_todos_los_reportes_fase_html(request: Request, session: AsyncSession = Depends(get_session)):
    reportes = await obtener_todos_los_reportes_por_fase(session)
    return templates.TemplateResponse("lista_reportes_fase_todos.html", {"request": request, "reportes": reportes})

@app.post("/reportes/fase", response_class=HTMLResponse)
async def generar_reporte_fase_html(
    request: Request,
    fase_seleccionada: Fases = Form(..., alias="fase"), # Use alias to match form field name
    session: AsyncSession = Depends(get_session)
):
    try:
        reporte = await generar_reportes_por_fase(session, fase_seleccionada)
        return RedirectResponse(url=f"/reportes/fase/{fase_seleccionada.value}", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar reporte por fase: {e}")

@app.get("/reportes/fase/{fase_nombre}", response_class=HTMLResponse)
async def ver_reporte_fase_html(
    request: Request,
    fase_nombre: Fases, # FastAPI will automatically convert string to Fases enum
    session: AsyncSession = Depends(get_session)
):

    reporte = await obtener_reporte_por_fase(session, fase_nombre)
    if not reporte:
        # If report doesn't exist, try to generate it on demand
        try:
            reporte = await generar_reportes_por_fase(session, fase_nombre)
            return templates.TemplateResponse("reporte_fase_detalle.html", {"request": request, "reporte": reporte})
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No se pudo generar ni encontrar el reporte para la fase {fase_nombre.value}: {e}")

    return templates.TemplateResponse("reporte_fase_detalle.html", {"request": request, "reporte": reporte})

@app.get("/acerca-de/desarrollador", response_class=HTMLResponse)
async def mostrar_info_desarrollador(request: Request):
    """
    Muestra una página con información sobre el desarrollador.
    """
    # Puedes pasar cualquier información que quieras a la plantilla
    info_desarrollador = {
        "nombre": "Brayan Steven Quintero",
        "email": "brayan.quintero.m@gmail.com",
        "rol": "Desarrollador Full Stack",
        "linkedin": "https://www.linkedin.com/in/brayan-steven-quintero-m/", # Reemplaza con tu perfil real
        "github": "https://github.com/Brayan-Q", # Reemplaza con tu perfil real
        "experiencia": "Desarrollo de aplicaciones web con FastAPI y bases de datos PostgreSQL.",
        "proyecto": "Copa Sudamericana API"
    }
    return templates.TemplateResponse(
        "acerca_de_desarrollador.html",
        {"request": request, "desarrollador": info_desarrollador}
    )

@app.get("/reportes/menos-goleados", response_class=HTMLResponse)
async def mostrar_reporte_menos_goleados(request: Request, session: AsyncSession = Depends(get_session)):
    equipos_menos_goleados = await obtener_equipos_menos_goleados(session)
    return templates.TemplateResponse("reporte_menos_goleados.html", {"request": request, "equipos": equipos_menos_goleados})


# NUEVO: Ruta para mostrar el reporte por grupos
@app.get("/reportes/grupos", response_class=HTMLResponse)
async def mostrar_reporte_por_grupos(request: Request, session: AsyncSession = Depends(get_session)):
    reporte_grupos = await generar_reporte_por_grupos(session)
    return templates.TemplateResponse("reporte_grupos.html", {"request": request, "reporte_grupos": reporte_grupos, "Grupos": Grupos})

# NEW ENDPOINT: Project documentation page
@app.get("/acerca-de-proyecto", response_class=HTMLResponse)
async def acerca_de_proyecto(request: Request):
    """
    Muestra una página con la documentación del proyecto, incluyendo diagramas y mockups.
    """
    return templates.TemplateResponse("acerca_de_proyecto.html", {"request": request})