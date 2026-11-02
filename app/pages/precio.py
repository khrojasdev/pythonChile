"""¿Es buen precio? Compara la oferta del comprador con lo que se pagó el último mes.

Responde a Don Pedro: «El que compra pone el precio». Con un rango de referencia
el pescador sabe si la oferta está bajo lo normal y quién está pagando mejor.
"""
import pandas as pd
from nicegui import ui
from sqlmodel import select

from app import analytics
from app.db import sesion
from app.models import Especie, Rol
from datetime import date, timedelta

from app.ilustraciones import especie_svg
from app.ui_comun import COLORES, MAR, marco, rol_actual, selector_especies, sin_permiso, tarjeta_veredicto


def pizarra(especies) -> None:
    """Resumen de todas las especies: lo que la registradora anota en la pizarra del muelle."""
    hoy = date.today()
    with sesion() as s:
        df = analytics.desembarques_df(s, desde=hoy - timedelta(days=60), hasta=hoy)
    df = df[df["precio_kg"].notna() & (df["calidad"] == "ok")]
    reciente = df[df["fecha"] >= pd.Timestamp(hoy - timedelta(days=7))]
    anterior = df[(df["fecha"] < pd.Timestamp(hoy - timedelta(days=7))) &
                  (df["fecha"] >= pd.Timestamp(hoy - timedelta(days=37)))]
    with ui.column().classes("tarjeta gap-2"):
        ui.html("<h2>Pizarra de precios: últimos 7 días</h2>")
        ui.label("Mediana y rango normal por especie, comparado con las 4 semanas anteriores.").classes("tenue")
        for e in especies:
            r = reciente.loc[reciente["especie_id"] == e.id, "precio_kg"]
            a = anterior.loc[anterior["especie_id"] == e.id, "precio_kg"]
            with ui.row().classes("w-full items-center no-wrap gap-3 py-1").style("border-bottom:1px solid #EEF3F6"):
                ui.html(especie_svg(e.nombre, 42))
                ui.label(e.nombre).classes("font-bold w-24")
                if r.empty:
                    ui.label("Sin ventas esta semana").classes("tenue flex-1")
                    continue
                ui.label(analytics.clp(r.median())).classes("grande w-28").style(f"color:{MAR}")
                ui.label(f"{analytics.clp(r.quantile(.25))} a {analytics.clp(r.quantile(.75))} · n = {len(r)}") \
                    .classes("text-sm flex-1")
                if not a.empty:
                    cambio = (r.median() / a.median() - 1) * 100
                    color = COLORES["verde"] if cambio > 3 else COLORES["rojo"] if cambio < -3 else "#56697A"
                    icono = "trending_up" if cambio > 3 else "trending_down" if cambio < -3 else "trending_flat"
                    with ui.row().classes("items-center gap-1 no-wrap"):
                        ui.icon(icono).style(f"color:{color}")
                        ui.label(f"{cambio:+.0f}%").style(f"color:{color}").classes("font-bold")


@ui.page("/precio")
def precio():
    if r := sin_permiso(list(Rol)):
        return r
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
    estado = {"especie_id": especies[0].id, "precio": None}

    es_pescador = rol_actual() == Rol.PESCADOR.value
    titulo = "¿Es buen precio?" if es_pescador else ("Pizarra de precios" if rol_actual() == Rol.REGISTRADORA.value
                                                      else "Precios de playa")
    with marco(titulo, "/precio", "Compara una oferta con lo que se pagó en la caleta el último mes."):
        if not es_pescador:
            pizarra(especies)
        with ui.column().classes("tarjeta gap-3"):
            ui.html("<h2>Evaluar una oferta</h2>")
            selector_especies(especies, estado["especie_id"], lambda e: (estado.update(especie_id=e.value), mostrar()))
            ui.number("¿Cuánto te ofrecen? ($/kg)", min=0, step=10).props("inputmode=numeric") \
                .bind_value(estado, "precio").classes("w-full")
            ui.button("Evaluar oferta", icon="price_check", on_click=lambda: mostrar()).classes("w-full") \
                .props("unelevated")
        zona = ui.column().classes("w-full gap-3")

        def mostrar():
            zona.clear()
            if not estado["especie_id"]:
                return
            with sesion() as s:
                ref = analytics.precio_referencia(s, estado["especie_id"])
            with zona:
                if estado["precio"]:
                    v = analytics.evaluar_oferta(ref, estado["precio"])
                    tarjeta_veredicto(v.color, v.titulo, v.razones)
                if ref.n == 0:
                    ui.label("No hay precios de esta especie en los últimos 30 días (puede estar fuera de temporada).")
                    return
                with ui.column().classes("tarjeta"):
                    ui.html(f"<h2>Precio de playa de {ref.especie}, últimos 30 días</h2>")
                    ui.label(f"Mediana {analytics.clp(ref.mediana)} · el precio varió {analytics.dec(ref.variacion)} veces "
                             f"entre el día más barato y el más caro · n = {ref.n}").classes("text-sm")
                    serie = ref.serie
                    fechas = serie["fecha"].dt.strftime("%d-%m").tolist()
                    opciones = {
                        "grid": {"left": 50, "right": 12, "top": 16, "bottom": 60},
                        "tooltip": {"trigger": "axis"},
                        "legend": {"bottom": 0, "textStyle": {"fontSize": 11}},
                        "xAxis": {"type": "category", "data": fechas},
                        "yAxis": {"type": "value", "scale": True},
                        "series": [
                            {"name": "más bajo", "type": "line", "data": serie["min"].tolist(), "symbol": "none",
                             "lineStyle": {"width": 1, "type": "dashed"}, "color": "#90A4AE"},
                            {"name": "mediana del día", "type": "line", "data": serie["median"].tolist(),
                             "color": "#1D6A8A", "lineStyle": {"width": 3}},
                            {"name": "más alto", "type": "line", "data": serie["max"].tolist(), "symbol": "none",
                             "lineStyle": {"width": 1, "type": "dashed"}, "color": "#90A4AE"},
                        ],
                    }
                    if estado["precio"]:
                        opciones["series"].append({
                            "name": "te ofrecen", "type": "line", "data": [estado["precio"]] * len(fechas),
                            "symbol": "none", "color": COLORES["rojo"], "lineStyle": {"width": 2}})
                    ui.echart(opciones).classes("w-full h-64")
                with ui.column().classes("tarjeta"):
                    ui.html("<h2>¿Quién pagó mejor este mes?</h2>")
                    for _, fila in ref.por_comprador.iterrows():
                        ui.label(f"• {fila['comprador_tipo'].capitalize()}: mediana {analytics.clp(fila['median'])} "
                                 f"({int(fila['count'])} ventas)")
                    ui.label("Ojo: los restaurantes compran poco volumen; no siempre pueden llevarse toda la captura.") \
                        .classes("tenue")
        mostrar()
