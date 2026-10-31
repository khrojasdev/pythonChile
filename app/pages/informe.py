"""Informe PDF para fondos y autoridades."""
from datetime import date

from nicegui import run, ui

from app.models import Rol
from app.reports import generar_pdf
from app.ui_comun import marco, sin_permiso


@ui.page("/informe")
def informe():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    with marco("Informe para fondos"):
        with ui.column().classes("tarjeta"):
            ui.label("📄 Ficha de producción de la caleta").classes("grande")
            ui.label("Lo que piden los fondos de apoyo, listo en un clic:")
            for t in ["Desembarque mensual por especie (12 meses)",
                      "Salidas y salidas que no cubren costos",
                      "Trabajo en tierra valorizado (encarnado, fileteo, venta)",
                      "Variación de precios de playa",
                      "Calidad y origen de los datos, con sus límites"]:
                ui.label(f"• {t}")
            ui.label("🔒 Sin datos individuales de embarcaciones ni zonas de pesca.").classes("text-sm text-gray-600")

            async def descargar():
                boton.props("loading")
                pdf = await run.io_bound(generar_pdf)
                boton.props(remove="loading")
                ui.download.content(pdf, f"informe_caleta_{date.today():%Y%m%d}.pdf", "application/pdf")
            boton = ui.button("Descargar PDF", icon="download", on_click=descargar).classes("w-full").props("size=lg")
