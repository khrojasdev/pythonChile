"""Mis números: lo que ve SOLO el dueño de la embarcación (privacidad por nivel)."""
from nicegui import ui

from datetime import date, timedelta

import pandas as pd

from app import analytics, exportar
from app.db import sesion
from app.models import Rol
from app.ui_comun import COLORES, bote_actual, boton_descargas, kpi, marco, quien, sin_permiso


def _mis_desembarques(dias: int) -> pd.DataFrame:
    hoy = date.today()
    with sesion() as s:
        df = analytics.desembarques_df(s, desde=hoy - timedelta(days=dias), hasta=hoy, embarcacion_id=bote_actual())
    if df.empty:
        return df
    df = df.sort_values("fecha")
    return pd.DataFrame({"Fecha": df["fecha"].dt.date, "Especie": df["especie"], "Kg": df["kg"],
                         "Precio $/kg": df["precio_kg"], "Venta $": df["ingreso"], "Comprador": df["comprador_tipo"],
                         "Litros": df["litros_combustible"], "Origen": df["origen"]})


@ui.page("/mis-numeros")
def mis_numeros():
    if r := sin_permiso([Rol.PESCADOR]):
        return r
    estado = {"dias": 30}
    with marco("Mis números", "/mis-numeros", "Solo tú ves estos números. La directiva ve totales de la caleta."):
        periodo = ui.toggle({30: "30 días", 90: "3 meses", 365: "1 año"}) \
            .props("spread unelevated").classes("border rounded-lg").bind_value(estado, "dias").classes("w-full")
        zona = ui.column().classes("w-full gap-3")

        def pintar():
            zona.clear()
            with sesion() as s:
                m = analytics.mis_numeros(s, bote_actual(), dias=estado["dias"])
            with zona:
                if not m.get("salidas"):
                    ui.label("Aún no hay salidas registradas en este periodo.")
                    return
                boton_descargas(f"mis_desembarques_{estado['dias']}d",
                                lambda: exportar.a_csv(_mis_desembarques(estado["dias"])),
                                lambda: exportar.a_pdf(_mis_desembarques(estado["dias"]),
                                                       f"Desembarques de {quien()}",
                                                       f"Últimos {estado['dias']} días"),
                                "Descargar mis registros")
                with ui.element("div").classes("rejilla"):
                    kpi(str(m["salidas"]), "salidas", "sailing")
                    kpi(f"{m['kg']:,.0f} kg".replace(",", "."), "capturados", "scale")
                    kpi(analytics.clp_corto(m["ingreso"]), "vendido", "payments")
                    kpi(analytics.clp_corto(m["margen"]), "ganancia (salidas completas)", "savings",
                        COLORES["verde"] if m["margen"] >= 0 else COLORES["rojo"])
                with ui.column().classes("tarjeta"):
                    ui.label(f"{m['no_cubre']} de {m['evaluables']} salidas no cubrieron el combustible y la carnada.") \
                        .classes("font-bold")
                    if m["pendientes"]:
                        ui.label(f"{m['pendientes']} salidas tienen precio pendiente: complétalas para que "
                                 f"tus números sean exactos.").classes("text-warning")
                with ui.column().classes("tarjeta"):
                    ui.html("<h2>Precio que te pagaron, por tipo de comprador</h2>")
                    for _, f in m["por_comprador"].iterrows():
                        ui.label(f"• {str(f['comprador_tipo']).capitalize()}: {analytics.clp(f['precio_kg'])}/kg (mediana)")
                    ui.label("Mezcla especies distintas: compáralo dentro de la misma especie en «¿Es buen precio?».") \
                        .classes("text-sm text-gray-600")
        pintar()
        periodo.on_value_change(lambda _: pintar())
