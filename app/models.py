"""Modelos de datos de Mar Adentro.

Todas las entidades usan SQLModel (Pydantic + SQLAlchemy): la misma clase sirve
para validar datos de entrada y para guardarlos en la base de datos.

Todos los datos de la aplicación son FICTICIOS (condición del hackatón).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------- enumeraciones
class Origen(str, Enum):
    """De dónde viene el dato: define cuánto confiar en él."""
    PESADO = "pesado"          # pesado en balanza al desembarcar
    ESTIMADO = "estimado"      # el pescador lo estimó (cajas, ojo)
    CUADERNO = "cuaderno"      # reconstruido desde un cuaderno antiguo


class Calidad(str, Enum):
    OK = "ok"
    ADVERTENCIA = "advertencia"   # se guarda, pero queda marcado para revisión
    ERROR = "error"               # no se usa en los cálculos
    RECHAZADO = "rechazado"       # la directiva lo anuló al revisarlo: no se usa


# calidades que NO entran a ningún cálculo
EXCLUIDAS = (Calidad.ERROR, Calidad.RECHAZADO)


class TipoComprador(str, Enum):
    INTERMEDIARIO = "intermediario"
    PESCADERIA = "pescadería"
    RESTAURANTE = "restaurante"
    VENTA_DIRECTA = "venta directa"


class TipoTrabajo(str, Enum):
    ENCARNADO = "encarnado"     # unidad: anzuelos encarnados
    FILETEO = "fileteo"         # unidad: kg fileteados
    VENTA = "venta"             # unidad: horas en el puesto
    LIMPIEZA = "limpieza"       # unidad: horas (limpieza, hielo, cajas)


class Rol(str, Enum):
    PESCADOR = "pescador"
    REGISTRADORA = "registradora"
    SINDICATO = "sindicato"


# ---------------------------------------------------------------- catálogos
class Embarcacion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True)
    matricula: str                       # ficticia
    patron: str                          # nombre ficticio del patrón
    litros_por_salida: float = 60.0      # consumo típico de combustible
    activa: bool = True


class Especie(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True, unique=True)
    icono: str = "🐟"
    # rangos plausibles por salida y por kg: se usan para validar
    kg_max_salida: float = 400.0
    precio_min: int = 500                # CLP/kg
    precio_max: int = 6000               # CLP/kg
    # veda: meses (1-12) en que no se puede extraer. None = sin veda
    veda_mes_inicio: Optional[int] = None
    veda_mes_fin: Optional[int] = None
    cuota_anual_kg: Optional[float] = None   # cuota de la caleta


class Comprador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    tipo: TipoComprador


class PersonaTierra(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    rol_principal: TipoTrabajo
    activa: bool = True


# ---------------------------------------------------------------- registros
class Desembarque(SQLModel, table=True):
    """Una línea de captura: una especie de una salida de una embarcación."""
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha: date = Field(index=True)
    embarcacion_id: int = Field(foreign_key="embarcacion.id", index=True)
    especie_id: int = Field(foreign_key="especie.id", index=True)
    kg: Optional[float] = None
    precio_kg: Optional[int] = None          # puede faltar: se vende después
    comprador_id: Optional[int] = Field(default=None, foreign_key="comprador.id")
    litros_combustible: Optional[float] = None   # solo en la primera línea de la salida
    precio_litro: Optional[int] = None
    costo_carnada: Optional[int] = None
    origen: Origen = Origen.PESADO
    calidad: Calidad = Calidad.OK
    notas_calidad: str = ""                  # motivos de la advertencia/error
    registrado_por: str = ""
    revisado_por: str = ""                   # quién aprobó/rechazó
    revisado_en: Optional[datetime] = None
    calidad_original: Optional[str] = None   # para poder deshacer una revisión
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrabajoTierra(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha: date = Field(index=True)
    persona_id: int = Field(foreign_key="personatierra.id", index=True)
    tipo: TipoTrabajo
    cantidad: float                          # anzuelos, kg u horas según tipo
    horas: float
    embarcacion_id: Optional[int] = Field(default=None, foreign_key="embarcacion.id")
    calidad: Calidad = Calidad.OK
    notas_calidad: str = ""
    registrado_por: str = ""
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CondicionMar(SQLModel, table=True):
    """Estado del mar diario (SIMULADO). En producción vendría de un pronóstico."""
    fecha: date = Field(primary_key=True)
    ola_m: float
    viento_nudos: float
    es_pronostico: bool = False


class Aviso(SQLModel, table=True):
    """Comunicado que la directiva publica para toda la caleta."""
    id: Optional[int] = Field(default=None, primary_key=True)
    titulo: str
    cuerpo: str
    tipo: str = "info"              # info | alerta | reunion
    fijado: bool = False
    publicado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autor: str = "Directiva"


class Meta(SQLModel, table=True):
    """Versión del esquema: si cambia, la base de demo se regenera."""
    clave: str = Field(primary_key=True)
    valor: str
