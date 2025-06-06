from sqlmodel import SQLModel, Field
from typing import Optional
from sqlmodel import Relationship
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from pydantic import ConfigDict



# --------- Otros ---------
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

class EquipoCreate(BaseModel):
    id: Optional[int] = None
    nombre: str
    pais: Paises
    grupo: str
    puntos: int

class EquipoMenosGoleadoReporte(BaseModel):
    id: Optional[int] = None
    nombre: str
    pais: Paises
    grupo: str
    logo_url: Optional[str]
    goles_en_contra: int
# --------- Modelo Equipo ---------
class EquipoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=3, max_length=50)
    pais: Paises = Field(default=Paises.colombia)
    grupo: str = Field(..., min_length=1, max_length=10)
    puntos: int = Field(..., ge=0)
    logo_url: Optional[str] = Field(default="img/shield.png")
    tarjetas_amarillas: int = Field(ge=0)
    tarjetas_rojas: int = Field(ge=0)
    tiros_esquina: int = Field(ge=0)
    tiros_libres: int = Field(ge=0)
    goles_a_favor: int = Field(..., ge=0)
    goles_en_contra: int = Field(..., ge=0)
    faltas: int = Field(default=0, ge=0)
    fueras_de_juego: int = Field(default=0, ge=0)
    pases: int = Field(default=0, ge=0)
    esta_activo: bool = Field(default=True)

    # Añade estas relaciones inversas, especificando qué columna de PartidoSQL
    # apunta a este equipo cuando es local y cuando es visitante.
    partidos_como_local: List["PartidoSQL"] = Relationship(
        back_populates="equipo_local",
        sa_relationship_kwargs={"foreign_keys": "PartidoSQL.equipo_local_id"}
    )
    partidos_como_visitante: List["PartidoSQL"] = Relationship(
        back_populates="equipo_visitante",
        sa_relationship_kwargs={"foreign_keys": "PartidoSQL.equipo_visitante_id"}
    )


# --------- Modelo Partido ---------
class PartidoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    equipo_local_id: int = Field(foreign_key="equiposql.id")
    equipo_visitante_id: int = Field(foreign_key="equiposql.id")

    # ¡ACTUALIZA ESTAS LÍNEAS!
    equipo_local: Optional[EquipoSQL] = Relationship(
        back_populates="partidos_como_local",
        sa_relationship_kwargs={
            "foreign_keys": "[PartidoSQL.equipo_local_id]", # <-- Especifica la clave foránea aquí
            "lazy": "joined"
        }
    )
    equipo_visitante: Optional[EquipoSQL] = Relationship(
        back_populates="partidos_como_visitante",
        sa_relationship_kwargs={
            "foreign_keys": "[PartidoSQL.equipo_visitante_id]", # <-- Especifica la clave foránea aquí
            "lazy": "joined"
        }
    )
    # Fin de las líneas actualizadas

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    esta_activo: bool = Field(default=True)
# --------- Modelo Reporte ---------
class ReportePorPaisSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pais: Paises = Field(unique=True)
    total_equipos: int = Field(..., ge=0)
    total_puntos: int = Field(..., ge=0)
    promedio_goles_favor: float = Field(..., ge=0)
    promedio_goles_contra: float = Field(..., ge=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})

class ReportePorFaseSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fase: Fases = Field(unique=True) # Ensure uniqueness for each phase's report
    total_partidos: int
    total_goles_local: int
    total_goles_visitante: int
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})
