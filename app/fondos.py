"""«¿Estamos listos para postular a un fondo?»

Los fondos para pesca artesanal (equipamiento, fomento productivo, comercialización) piden
demostrar producción con datos ordenados. Esta lista revisa, con los datos de la caleta,
lo que un evaluador suele mirar, y dice qué falta para llegar.
Es una guía interna: los requisitos reales dependen de cada convocatoria.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlmodel import Session

from app import analytics


@dataclass
class Requisito:
    titulo: str
    cumple: bool
    valor: str          # lo que hay hoy
    meta: str           # lo que se busca
    consejo: str        # qué hacer si falta
    avance: float       # 0 a 1


def revisar(s: Session, hoy: Optional[date] = None) -> list[Requisito]:
    hoy = hoy or date.today()
    desde = hoy - timedelta(days=365)
    todos = analytics.desembarques_df(s, desde=desde, hasta=hoy, incluir_errores=True)
    validos = analytics.desembarques_df(s, desde=desde, hasta=hoy)
    tierra = analytics.tierra_df(s, desde=desde, hasta=hoy)
    out: list[Requisito] = []

    meses = validos["fecha"].dt.to_period("M").nunique() if not validos.empty else 0
    out.append(Requisito("Historia de producción", meses >= 12, f"{meses} meses con registros", "12 meses seguidos",
                         "Sigan anotando cada desembarque; digitalicen los cuadernos de los meses que faltan.",
                         min(1, meses / 12)))

    pesado = (validos["origen"] == "pesado").mean() * 100 if not validos.empty else 0
    out.append(Requisito("Datos medidos, no estimados", pesado >= 60, f"{pesado:.0f} % pesado en balanza",
                         "60 % o más", "Pesen en la balanza del muelle al llegar: un dato pesado vale más.",
                         min(1, pesado / 60)))

    con_kg = validos[validos["kg"].fillna(0) > 0]
    con_precio = con_kg["precio_kg"].notna().mean() * 100 if not con_kg.empty else 0
    out.append(Requisito("Ventas con precio", con_precio >= 85, f"{con_precio:.0f} % de las capturas con precio",
                         "85 % o más", "Completen las «Ventas por completar» cuando se cierre cada venta.",
                         min(1, con_precio / 85)))

    pendientes = int((todos["calidad"] == "advertencia").sum()) if not todos.empty else 0
    limpio = 100 - (pendientes / len(todos) * 100 if len(todos) else 0)
    out.append(Requisito("Datos revisados por la directiva", limpio >= 97,
                         f"{limpio:.0f} % sin observaciones ({pendientes:,} por revisar)".replace(",", "."),
                         "97 % o más",
                         "Entren a «Revisión de datos» y aprueben, corrijan o rechacen lo marcado "
                         "(se puede aprobar en bloque).", min(1, limpio / 97)))

    botes = validos["embarcacion_id"].nunique() if not validos.empty else 0
    out.append(Requisito("Participación de la caleta", botes >= 25, f"{botes} de 41 embarcaciones registran",
                         "25 o más", "La registradora puede anotar por quienes no usan celular.",
                         min(1, botes / 25)))

    personas = tierra["persona_id"].nunique() if not tierra.empty else 0
    out.append(Requisito("Trabajo en tierra visible", personas >= 30, f"{personas} personas con registro",
                         "30 o más", "Anoten el encarnado y el fileteo diario: es aporte que hoy no se ve.",
                         min(1, personas / 30)))
    return out


def puntaje(reqs: list[Requisito]) -> tuple[int, int]:
    return sum(r.cumple for r in reqs), len(reqs)


def tabla(reqs: list[Requisito]) -> pd.DataFrame:
    return pd.DataFrame([{"Requisito": r.titulo, "Cumple": "Sí" if r.cumple else "No", "Hoy": r.valor,
                          "Meta": r.meta, "Qué hacer": r.consejo} for r in reqs])
