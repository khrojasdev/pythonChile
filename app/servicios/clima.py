"""Pronóstico del tiempo y del mar.

Fuente: Open-Meteo (https://open-meteo.com), API gratuita y sin clave:
  - api.open-meteo.com/v1/forecast         -> temperatura, lluvia, viento
  - marine-api.open-meteo.com/v1/marine    -> altura y periodo de ola
Si no hay internet o la API falla, se usa el estado del mar SIMULADO de la base,
y la pantalla lo dice claramente. Para decisiones reales de navegación, la
fuente oficial en Chile es el SHOA / Armada (avisos de puerto cerrado).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlmodel import select

from app import config
from app.db import sesion
from app.models import CondicionMar

TTL_SEGUNDOS = 30 * 60
_cache: dict = {"t": 0.0, "dato": None}

# Códigos WMO -> (descripción, ícono Material)
CODIGOS = {
    0: ("Despejado", "wb_sunny"), 1: ("Mayormente despejado", "wb_sunny"),
    2: ("Parcialmente nublado", "partly_cloudy_day"), 3: ("Nublado", "cloud"),
    45: ("Neblina", "foggy"), 48: ("Neblina helada", "foggy"),
    51: ("Llovizna débil", "grain"), 53: ("Llovizna", "grain"), 55: ("Llovizna intensa", "grain"),
    61: ("Lluvia débil", "rainy"), 63: ("Lluvia", "rainy"), 65: ("Lluvia intensa", "rainy"),
    80: ("Chubascos", "rainy"), 81: ("Chubascos", "rainy"), 82: ("Chubascos fuertes", "thunderstorm"),
    95: ("Tormenta", "thunderstorm"), 96: ("Tormenta", "thunderstorm"), 99: ("Tormenta", "thunderstorm"),
}
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def describir(codigo: Optional[int]) -> tuple[str, str]:
    if codigo is None:
        return ("Sin dato", "help_outline")
    return CODIGOS.get(int(codigo), ("Variable", "partly_cloudy_day"))


@dataclass
class Dia:
    fecha: date
    codigo: Optional[int] = None
    tmax: Optional[float] = None
    tmin: Optional[float] = None
    lluvia_pct: Optional[float] = None
    viento_kn: Optional[float] = None
    racha_kn: Optional[float] = None
    ola_m: Optional[float] = None
    periodo_s: Optional[float] = None

    @property
    def descripcion(self) -> str:
        return describir(self.codigo)[0]

    @property
    def icono(self) -> str:
        return describir(self.codigo)[1]

    @property
    def nombre(self) -> str:
        hoy = date.today()
        if self.fecha == hoy:
            return "Hoy"
        if self.fecha == hoy + timedelta(days=1):
            return "Mañana"
        return f"{DIAS[self.fecha.weekday()]} {self.fecha.day}"

    @property
    def estado_mar(self) -> str:
        """Lectura simple para el pescador, con los mismos umbrales del semáforo."""
        if self.ola_m is None:
            return "gris"
        if self.ola_m >= config.OLA_ROJO_M or (self.viento_kn or 0) >= config.VIENTO_ROJO_NUDOS:
            return "rojo"
        if self.ola_m >= config.OLA_AMARILLO_M:
            return "amarillo"
        return "verde"


@dataclass
class Pronostico:
    fuente: str                 # "Open-Meteo" | "simulado"
    real: bool
    temp_actual: Optional[float] = None
    codigo_actual: Optional[int] = None
    viento_actual_kn: Optional[float] = None
    ola_actual_m: Optional[float] = None
    dias: list[Dia] = field(default_factory=list)
    error: str = ""

    def dia(self, f: date) -> Optional[Dia]:
        return next((d for d in self.dias if d.fecha == f), None)


def _parsear(meteo: dict, marino: Optional[dict]) -> Pronostico:
    d, cur = meteo["daily"], meteo.get("current", {})
    ola = {}
    ola_actual = None
    if marino:
        md = marino.get("daily", {})
        for i, f in enumerate(md.get("time", [])):
            ola[f] = (md["wave_height_max"][i], (md.get("wave_period_max") or [None] * len(md["time"]))[i])
        ola_actual = (marino.get("current") or {}).get("wave_height")
    dias = []
    for i, f in enumerate(d["time"]):
        h, per = ola.get(f, (None, None))
        dias.append(Dia(
            fecha=date.fromisoformat(f), codigo=d["weather_code"][i],
            tmax=d["temperature_2m_max"][i], tmin=d["temperature_2m_min"][i],
            lluvia_pct=(d.get("precipitation_probability_max") or [None] * len(d["time"]))[i],
            viento_kn=d["wind_speed_10m_max"][i], racha_kn=(d.get("wind_gusts_10m_max") or [None] * len(d["time"]))[i],
            ola_m=h, periodo_s=per))
    return Pronostico(fuente="Open-Meteo", real=True, temp_actual=cur.get("temperature_2m"),
                      codigo_actual=cur.get("weather_code"), viento_actual_kn=cur.get("wind_speed_10m"),
                      ola_actual_m=ola_actual, dias=dias)


def simulado(error: str = "") -> Pronostico:
    hoy = date.today()
    with sesion() as s:
        filas = s.exec(select(CondicionMar).where(CondicionMar.fecha >= hoy)
                       .order_by(CondicionMar.fecha)).all()
    dias = [Dia(fecha=m.fecha, ola_m=m.ola_m, viento_kn=m.viento_nudos) for m in filas]
    p = Pronostico(fuente="simulado", real=False, dias=dias, error=error)
    if dias:
        p.ola_actual_m, p.viento_actual_kn = dias[0].ola_m, dias[0].viento_kn
    return p


async def obtener() -> Pronostico:
    """Pronóstico de 7 días. Guarda el resultado 30 minutos para no llamar la API en cada página."""
    if not config.CLIMA_REAL:
        return simulado()
    if _cache["dato"] is not None and time.time() - _cache["t"] < TTL_SEGUNDOS:
        return _cache["dato"]
    params = dict(latitude=config.LATITUD, longitude=config.LONGITUD, timezone="America/Santiago",
                  wind_speed_unit="kn", forecast_days=7,
                  current="temperature_2m,weather_code,wind_speed_10m",
                  daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                        "wind_speed_10m_max,wind_gusts_10m_max")
    params_mar = dict(latitude=config.LATITUD_MAR, longitude=config.LONGITUD_MAR, timezone="America/Santiago",
                      forecast_days=7, current="wave_height",
                      daily="wave_height_max,wave_period_max")
    try:
        async with httpx.AsyncClient(timeout=6) as cli:
            r = await cli.get("https://api.open-meteo.com/v1/forecast", params=params)
            r.raise_for_status()
            marino = None
            try:
                rm = await cli.get("https://marine-api.open-meteo.com/v1/marine", params=params_mar)
                rm.raise_for_status()
                marino = rm.json()
            except httpx.HTTPError:
                pass
        p = _parsear(r.json(), marino)
        if not marino:   # sin oleaje real: se completa con el simulado
            sim = {d.fecha: d for d in simulado().dias}
            for d in p.dias:
                if d.fecha in sim:
                    d.ola_m = sim[d.fecha].ola_m
            p.fuente = "Open-Meteo (oleaje simulado)"
    except (httpx.HTTPError, KeyError, ValueError) as e:
        p = simulado(error=f"No se pudo consultar Open-Meteo ({type(e).__name__})")
        _cache.update(t=time.time() - TTL_SEGUNDOS + 120, dato=p)   # reintenta en 2 minutos
        return p
    _cache.update(t=time.time(), dato=p)
    return p
