from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from enum import Enum
from pydantic import ConfigDict



# --------- Otros ---------
class EquipoCreate(BaseModel):
    nombre: str
    pais: Paises  # usa el mismo Enum que ya definiste
    grupo: str
    puntos: int

class Fases(str, Enum):
    Play_off = "Play off"
    grupos = "Grupos"
    repechaje = "Repechaje"
    octavos = "Octavos"
    cuartos = "Cuartos"
    semifinal = "Semifinal"
    final = "Final"

class Paises(str, Enum):
    argentina = "Argentina"
    bolivia = "Bolivia"
    brasil = "Brasil"
    chile = "Chile"
    colombia = "Colombia"
    ecuador = "Ecuador"
    paraguay = "Paraguay"
    peru = "Perú"
    uruguay = "Uruguay"
    venezuela = "Venezuela"

# --------- Modelo Equipo ---------
class EquipoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=3, max_length=50)
    pais: Paises = Field(default=Paises.colombia)
    grupo: str = Field(..., min_length=1, max_length=10)
    puntos: int = Field(..., ge=0)
    tarjetas_amarillas: int = Field(ge=0)
    tarjetas_rojas: int = Field(ge=0)
    tiros_esquina: int = Field(ge=0)
    tiros_libres: int = Field(ge=0)
    goles_a_favor: int = Field(..., ge=0)
    goles_en_contra: int = Field(..., ge=0)
    faltas: int = Field(default=0, ge=0)
    fueras_de_juego: int = Field(default=0, ge=0)
    pases: int = Field(default=0, ge=0)

# --------- Modelo Partido ---------
class PartidoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    equipo_local_id: int = Field(foreign_key="equiposql.id")
    equipo_visitante_id: int = Field(foreign_key="equiposql.id")
    tarjetas_amarillas_local: int = Field(ge=0)
    tarjetas_amarillas_visitante: int = Field(ge=0)
    tarjetas_rojas_local: int = Field(ge=0)
    tarjetas_rojas_visitante: int = Field(ge=0)
    tiros_esquina_local: int = Field(ge=0)
    tiros_esquina_visitante: int = Field(ge=0)
    tiros_libres_local: int = Field(ge=0)
    tiros_libres_visitante: int = Field(ge=0)
    faltas_local: int = Field(ge=0)
    faltas_visitante: int = Field(ge=0)
    fueras_de_juego_local: int = Field(ge=0)
    fueras_de_juego_visitante: int = Field(ge=0)
    pases_local: int = Field(ge=0)
    pases_visitante: int = Field(ge=0)
    goles_local: int = Field(..., ge=0)
    goles_visitante: int = Field(..., ge=0)
    fase: Fases = Field(default=Fases.Play_off)


# --------- Modelo Reporte ---------
class ReportePorPaisSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pais: Paises = Field(default=None)
    total_equipos: int = Field(..., ge=0)
    total_puntos: int = Field(..., ge=0)
    promedio_goles_favor: float = Field(..., ge=0)
    promedio_goles_contra: float = Field(..., ge=0)

class ReportePorFaseSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fase: Fases = Field(default=Fases.Play_off)
    total_partidos: int = Field(..., ge=0)
    total_goles: int = Field(..., ge=0)
    promedio_goles_por_partido: float = Field(..., ge=0)

