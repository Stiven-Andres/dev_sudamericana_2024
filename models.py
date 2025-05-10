from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from enum import Enum
from pydantic import ConfigDict

# --------- Modelo Equipo ---------
class EquipoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=3, max_length=50)
    pais: str = Field(..., min_length=2, max_length=30)
    grupo: str = Field(..., min_length=1, max_length=10)
    puntos: int = Field(..., ge=0)
    goles_a_favor: int = Field(..., ge=0)
    goles_en_contra: int = Field(..., ge=0)

# --------- Modelo Partido ---------
class PartidoSQL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    equipo_local_id: int = Field(foreign_key="equiposql.id")
    equipo_visitante_id: int = Field(foreign_key="equiposql.id")
    goles_local: int = Field(..., ge=0)
    goles_visitante: int = Field(..., ge=0)
    fase: str = Field(..., min_length=3)


# --------- Modelo Reporte ---------
class ReportePorPaisSQL(SQLModel, table=True):
    pais: str = Field(..., min_length=2, max_length=30)
    total_equipos: int = Field(..., ge=0)
    total_puntos: int = Field(..., ge=0)
    promedio_goles_favor: float = Field(..., ge=0)
    promedio_goles_contra: float = Field(..., ge=0)

class ReportePorFechasSQL(SQLModel, table=True):
    fecha_inicio: datetime
    fecha_fin: datetime
    total_partidos: int = Field(..., ge=0)
    total_goles: int = Field(..., ge=0)
    promedio_goles_por_partido: float = Field(..., ge=0)




# --------- Otros ---------
class EquipoUpdate(BaseModel):
    puntos: Optional[int]
    goles_a_favor: Optional[int]
    goles_en_contra: Optional[int]