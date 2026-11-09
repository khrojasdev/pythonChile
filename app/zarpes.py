"""Zarpe y regreso: saber quién está en el mar y avisar si alguien se atrasa.

Es lo que hoy se hace de palabra en el muelle («¿volvió el Gaviota?»). No se guarda la
zona de pesca: solo la hora de salida, la hora estimada de vuelta y cuántas personas van.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.models import Embarcacion, Zarpe

ZONA = ZoneInfo("America/Santiago")
TOLERANCIA = timedelta(minutes=30)     # pasado esto sin volver, se marca como atrasado
VENTANA = timedelta(hours=36)          # zarpes más antiguos sin regreso no se muestran como "en el mar"


def ahora_local() -> datetime:
    """Hora de la caleta, sin zona (así se guarda en la base)."""
    return datetime.now(ZONA).replace(tzinfo=None)


@dataclass
class EnElMar:
    zarpe: Zarpe
    bote: str
    atrasado: bool
    minutos_atraso: int
    minutos_para_volver: int


def estado(z: Zarpe, ahora: datetime) -> tuple[bool, int, int]:
    """(atrasado, minutos de atraso, minutos que faltan para la hora estimada)."""
    diff = (ahora - z.regreso_estimado).total_seconds() / 60
    return ahora > z.regreso_estimado + TOLERANCIA, max(0, int(diff)), max(0, int(-diff))


def zarpe_abierto(s: Session, embarcacion_id: int, ahora: Optional[datetime] = None) -> Optional[Zarpe]:
    ahora = ahora or ahora_local()
    return s.exec(select(Zarpe).where(Zarpe.embarcacion_id == embarcacion_id, Zarpe.regreso_en == None,  # noqa: E711
                                      Zarpe.salida_en >= ahora - VENTANA)
                  .order_by(Zarpe.salida_en.desc())).first()


def registrar_zarpe(s: Session, embarcacion_id: int, horas_fuera: float, tripulantes: int,
                    contacto: str = "", quien: str = "", ahora: Optional[datetime] = None) -> Zarpe:
    ahora = (ahora or ahora_local()).replace(second=0, microsecond=0)
    if not 0.5 <= horas_fuera <= 24:
        raise ValueError("La vuelta estimada debe estar entre media hora y 24 horas.")
    if not 1 <= tripulantes <= 12:
        raise ValueError("Indica cuántas personas van a bordo (1 a 12).")
    if zarpe_abierto(s, embarcacion_id, ahora):
        raise ValueError("Esta embarcación ya tiene un zarpe abierto. Marca el regreso primero.")
    z = Zarpe(embarcacion_id=embarcacion_id, salida_en=ahora, regreso_estimado=ahora + timedelta(hours=horas_fuera),
              tripulantes=tripulantes, contacto=contacto.strip(), registrado_por=quien)
    s.add(z)
    s.commit()
    s.refresh(z)
    return z


def registrar_regreso(s: Session, zarpe_id: int, ahora: Optional[datetime] = None) -> Zarpe:
    z = s.get(Zarpe, zarpe_id)
    if z is None:
        raise ValueError("No existe ese zarpe.")
    if z.regreso_en is None:
        z.regreso_en = (ahora or ahora_local()).replace(second=0, microsecond=0)
        s.add(z)
        s.commit()
        s.refresh(z)
    return z


def en_el_mar(s: Session, ahora: Optional[datetime] = None) -> list[EnElMar]:
    """Botes con zarpe abierto, los atrasados primero."""
    ahora = ahora or ahora_local()
    botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
    filas = s.exec(select(Zarpe).where(Zarpe.regreso_en == None, Zarpe.salida_en >= ahora - VENTANA)).all()  # noqa: E711
    lista = []
    for z in filas:
        atr, min_atr, min_faltan = estado(z, ahora)
        lista.append(EnElMar(z, botes.get(z.embarcacion_id, "?"), atr, min_atr, min_faltan))
    return sorted(lista, key=lambda e: (not e.atrasado, e.zarpe.regreso_estimado))


def volvieron_hoy(s: Session, ahora: Optional[datetime] = None) -> int:
    ahora = ahora or ahora_local()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    return len(s.exec(select(Zarpe).where(Zarpe.regreso_en >= inicio)).all())


def texto_duracion(minutos: int) -> str:
    h, m = divmod(int(minutos), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"
