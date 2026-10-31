"""¿Es buen precio? Compara la oferta del comprador con lo que se pagó el último mes.

Responde a Don Pedro: «El que compra pone el precio». Con un rango de referencia
el pescador sabe si la oferta está bajo lo normal y quién está pagando mejor.
"""
from nicegui import ui
from sqlmodel import select

from app import analytics
from app.db import sesion
from app.models import Especie, Rol
from app.ui_comun import COLORES, marco, selector_especies, sin_permiso, tarjeta_veredicto


@ui.page("/precio")
def precio():
    if r := sin_permiso(list(Rol)):
        return r
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
    estado = {"especie_id": especies[0].id, "precio": None}

    with marco("¿Es buen precio?"):
        with ui.column().classes("tarjeta"):
            selector_especies(especies, estado["especie_id"], lambda e: (estado.update(especie_id=e.value), mostrar()))
            ui.number("¿Cuánto te ofrecen? ($/kg)", min=0, step=10).props("inputmode=numeric") \
                .bind_value(estado, "precio").classes("w-full")
            ui.button("Evaluar", on_click=lambda: mostrar()).classes("w-full")
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
                    ui.label(f"Precio de playa de {ref.especie} ($/kg) · últimos 30 días").classes("font-bold")
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
                    ui.label("¿Quién pagó mejor este mes?").classes("font-bold")
                    for _, fila in ref.por_comprador.iterrows():
                        ui.label(f"• {fila['comprador_tipo'].capitalize()}: mediana {analytics.clp(fila['median'])} "
                                 f"({int(fila['count'])} ventas)")
                    ui.label("Ojo: los restaurantes compran poco volumen; no siempre pueden llevarse toda la captura.") \
                        .classes("text-sm text-gray-600")
        mostrar()
