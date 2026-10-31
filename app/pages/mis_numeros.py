"""Mis números: lo que ve SOLO el dueño de la embarcación (privacidad por nivel)."""
from nicegui import ui

from app import analytics
from app.db import sesion
from app.models import Rol
from app.ui_comun import bote_actual, kpi, marco, sin_permiso


@ui.page("/mis-numeros")
def mis_numeros():
    if r := sin_permiso([Rol.PESCADOR]):
        return r
    estado = {"dias": 30}
    with marco("Mis números"):
        periodo = ui.toggle({30: "30 días", 90: "3 meses", 365: "1 año"}) \
            .props("no-caps spread").bind_value(estado, "dias").classes("w-full")
        zona = ui.column().classes("w-full gap-3")

        def pintar():
            zona.clear()
            with sesion() as s:
                m = analytics.mis_numeros(s, bote_actual(), dias=estado["dias"])
            with zona:
                if not m.get("salidas"):
                    ui.label("Aún no hay salidas registradas en este periodo.")
                    return
                with ui.grid(columns=2).classes("w-full gap-2"):
                    kpi(str(m["salidas"]), "salidas")
                    kpi(f"{m['kg']:,.0f} kg".replace(",", "."), "capturados")
                    kpi(analytics.clp(m["ingreso"]), "vendido")
                    kpi(analytics.clp(m["margen"]), "ganancia (salidas completas)")
                with ui.column().classes("tarjeta"):
                    ui.label(f"⛽ {m['no_cubre']} de {m['evaluables']} salidas no cubrieron el combustible y la carnada.")
                    if m["pendientes"]:
                        ui.label(f"📝 {m['pendientes']} salidas tienen precio pendiente: complétalas para que "
                                 f"tus números sean exactos.").classes("text-warning")
                with ui.column().classes("tarjeta"):
                    ui.label("Precio que te pagaron, por tipo de comprador").classes("font-bold")
                    for _, f in m["por_comprador"].iterrows():
                        ui.label(f"• {str(f['comprador_tipo']).capitalize()}: {analytics.clp(f['precio_kg'])}/kg (mediana)")
                    ui.label("Mezcla especies distintas: compáralo dentro de la misma especie en «¿Es buen precio?».") \
                        .classes("text-sm text-gray-600")
                ui.label("🔒 Estos números solo los ves tú. El sindicato ve totales de la caleta, sin nombres.") \
                    .classes("text-sm text-gray-600")
        pintar()
        periodo.on_value_change(lambda _: pintar())
