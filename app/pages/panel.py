"""Panel del sindicato: totales de la caleta, sin datos individuales de cada bote."""
from nicegui import ui

from app import analytics
from app.db import sesion
from app.models import Rol
from app.ui_comun import kpi, marco, sin_permiso

PALETA = ["#0B3C5D", "#1D6A8A", "#5FA8D3", "#E4A951", "#C2703D", "#7A9E7E"]


def _barras_apiladas(df, titulo_y: str) -> dict:
    return {
        "color": PALETA,
        "grid": {"left": 62, "right": 10, "top": 20, "bottom": 70},
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 11}},
        "xAxis": {"type": "category", "data": [m[2:] for m in df.index]},
        "yAxis": {"type": "value"},
        "series": [{"name": c, "type": "bar", "stack": "t", "data": df[c].round(0).tolist()} for c in df.columns],
    }


@ui.page("/panel")
def panel():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    with sesion() as s:
        k = analytics.kpis_caleta(s)
        prod = analytics.produccion_mensual(s)
        tierra = analytics.tierra_mensual(s)
        cuotas = analytics.cuotas(s)
        var = analytics.variacion_precios(s)
        cal = analytics.resumen_calidad(s)

    with marco("Panel de la caleta"):
        with ui.grid(columns=2).classes("w-full gap-2"):
            kpi(f"{k['kg_30'] / 1000:,.1f} t".replace(",", "X").replace(".", ",").replace("X", "."), "desembarcado (30 días)")
            kpi(analytics.clp_corto(k["ingreso_30"]), "vendido (30 días)")
            kpi(f"1 de cada {100 / k['pct_no_cubre']:.0f}" if k["pct_no_cubre"] else "—",
                f"salidas no cubre costos ({k['pct_no_cubre']:.0f}%, n={k['n_evaluables']})")
            kpi(analytics.clp_corto(k["valor_tierra_30"]), f"trabajo en tierra · {k['personas_tierra_30']} personas (30 días)")

        with ui.column().classes("tarjeta"):
            ui.label("Producción mensual por especie (kg)").classes("font-bold")
            ui.echart(_barras_apiladas(prod, "kg")).classes("w-full h-72")

        with ui.column().classes("tarjeta"):
            ui.label("Aporte del trabajo en tierra, valorizado ($)").classes("font-bold")
            ui.label("Encarnado, fileteo, venta y limpieza: el trabajo que antes no aparecía en ningún papel.") \
                .classes("text-sm text-gray-600")
            ui.echart(_barras_apiladas(tierra, "$")).classes("w-full h-72")

        with ui.column().classes("tarjeta"):
            ui.label("Cuotas del año").classes("font-bold")
            for c in cuotas:
                color = "negative" if c["alerta"] else "positive"
                ui.label(f"{c['icono']} {c['especie']}: {c['usado']:,.0f} de {c['cuota']:,.0f} kg "
                         f"({c['pct']:.0f}%)".replace(",", ".") + ("  ⚠️ sobre 80%" if c["alerta"] else ""))
                ui.linear_progress(min(c["pct"] / 100, 1), show_value=False, size="14px").props(f"color={color}")

        with ui.column().classes("tarjeta"):
            ui.label("¿Cuánto varió el precio dentro de un mismo mes?").classes("font-bold")
            for _, f in var.iterrows():
                ui.label(f"• {f['especie']}: hasta {f['variacion_max']:.1f} veces".replace(".", ","))
            ui.label("Si el precio de un mismo pescado puede más que duplicarse en un mes, "
                     "conocer el rango ayuda a no vender en el día malo.").classes("text-sm text-gray-600")

        with ui.column().classes("tarjeta"):
            ui.label("Calidad de los datos").classes("font-bold")
            pc = cal["por_calidad"]
            ui.label(f"{cal['total']:,} registros · ✅ {pc.get('ok', 0):,} ok · ⚠️ {pc.get('advertencia', 0):,} "
                     f"por revisar · ❌ {pc.get('error', 0):,} con error (no se usan)".replace(",", "."))
            ui.label(f"{cal['pct_papel']:.0f}% viene de cuadernos digitalizados · "
                     f"{cal['sin_precio']} ventas sin precio · {cal['sin_kg']} sin kilos").classes("text-sm")
            ui.button("Revisar datos", on_click=lambda: ui.navigate.to("/calidad")).props("outline no-caps")
