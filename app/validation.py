"""Reglas de calidad de datos.

Principio: un dato dudoso NO se borra ni se corrige a escondidas.
- ERROR       -> no se usa en los cálculos (ej: kg negativo, fecha futura).
- ADVERTENCIA -> se guarda y se usa, pero queda marcado para que alguien lo revise.
- OK          -> pasa todas las reglas.

Las funciones son puras (no consultan la BD) para poder probarlas con pytest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.models import Calidad, Especie


@dataclass
class Resultado:
    calidad: Calidad = Calidad.OK
    motivos: list[str] = field(default_factory=list)

    def error(self, motivo: str) -> None:
        self.calidad = Calidad.ERROR
        self.motivos.append(f"❌ {motivo}")

    def advertencia(self, motivo: str) -> None:
        if self.calidad != Calidad.ERROR:
            self.calidad = Calidad.ADVERTENCIA
        self.motivos.append(f"⚠️ {motivo}")

    @property
    def texto(self) -> str:
        return " | ".join(self.motivos)


@dataclass
class ReferenciaPrecio:
    """Resumen de precios recientes de una especie (ver analytics.precio_referencia)."""
    n: int
    mediana: Optional[float] = None
    mad: Optional[float] = None       # desviación absoluta mediana (robusta a errores)


def en_veda(especie: Especie, fecha: date) -> bool:
    ini, fin = especie.veda_mes_inicio, especie.veda_mes_fin
    if ini is None or fin is None:
        return False
    m = fecha.month
    if ini <= fin:
        return ini <= m <= fin
    return m >= ini or m <= fin            # veda que cruza el año (ej: nov-feb)


def validar_desembarque(
    *,
    fecha: date,
    especie: Especie,
    kg: Optional[float],
    precio_kg: Optional[float],
    litros: Optional[float] = None,
    referencia: Optional[ReferenciaPrecio] = None,
    es_duplicado: bool = False,
    hoy: Optional[date] = None,
) -> Resultado:
    r = Resultado()
    hoy = hoy or date.today()

    # --- fecha
    if fecha > hoy:
        r.error("La fecha está en el futuro")
    if en_veda(especie, fecha):
        r.advertencia(f"{especie.nombre} está en veda en esta fecha: verificar")

    # --- kilos
    if kg is None:
        r.error("Faltan los kilos")
    elif kg < 0:
        r.error("Kilos negativos")
    elif kg > especie.kg_max_salida * 10:
        r.error(f"{kg:.0f} kg es imposible para una salida (¿error de tipeo?)")
    elif kg > especie.kg_max_salida:
        r.advertencia(f"{kg:.0f} kg es más de lo habitual (máx. {especie.kg_max_salida:.0f} kg)")

    # --- precio
    if precio_kg is None:
        if kg:   # con captura y sin precio: venta pendiente
            r.advertencia("Falta el precio (¿venta pendiente?)")
    elif precio_kg <= 0 or precio_kg > especie.precio_max * 3:
        r.error(f"Precio ${precio_kg:,.0f}/kg no es posible".replace(",", "."))
    else:
        if not (especie.precio_min <= precio_kg <= especie.precio_max):
            r.advertencia(
                f"Precio fuera del rango esperado para {especie.nombre} "
                f"(${especie.precio_min:,}–${especie.precio_max:,})".replace(",", ".")
            )
        if referencia and referencia.n >= 8 and referencia.mediana and referencia.mad:
            limite = 3 * 1.4826 * referencia.mad
            if abs(precio_kg - referencia.mediana) > limite:
                r.advertencia(
                    f"Precio muy distinto a lo normal del último mes "
                    f"(mediana ${referencia.mediana:,.0f})".replace(",", ".")
                )

    # --- combustible
    if litros is not None:
        if litros < 0:
            r.error("Litros de combustible negativos")
        elif litros > 400:
            r.advertencia(f"{litros:.0f} litros es mucho para una salida")

    if es_duplicado:
        r.advertencia("Ya existe un registro igual (misma fecha, bote y especie)")
    return r


def validar_trabajo_tierra(*, fecha: date, cantidad: Optional[float], horas: Optional[float],
                           hoy: Optional[date] = None) -> Resultado:
    r = Resultado()
    hoy = hoy or date.today()
    if fecha > hoy:
        r.error("La fecha está en el futuro")
    if cantidad is None or cantidad < 0:
        r.error("Falta la cantidad o es negativa")
    if horas is None or horas <= 0:
        r.error("Faltan las horas trabajadas")
    elif horas > 16:
        r.advertencia(f"{horas:.0f} horas en un día es mucho: revisar")
    return r
