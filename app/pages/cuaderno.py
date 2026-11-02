"""Digitalizar cuadernos: hoja para imprimir (PDF), planilla (CSV) y carga con revisión fila por fila."""
import pandas as pd
from nicegui import events, ui

from app import exportar, importar
from app.db import sesion
from app.models import Rol
from app.ui_comun import COLORES, MAR, marco, sin_permiso


@ui.page("/cuaderno")
def cuaderno():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    with marco("Digitalizar cuaderno", "/cuaderno",
               "Para pasar al sistema los cuadernos antiguos o las hojas llenadas a mano en el muelle."):
        with ui.row().classes("fila-resp"):
            for paso, titulo, texto, icono in [
                    (1, "Imprime la hoja", "Si no hay celular a mano, se anota en papel en el muelle.", "print"),
                    (2, "Transcribe", "Pasa el cuaderno a la planilla CSV, con las mismas columnas.", "edit_note"),
                    (3, "Sube y revisa", "El sistema revisa cada fila antes de guardar nada.", "upload_file")]:
                with ui.column().classes("tarjeta flex-1 gap-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(str(paso)).classes("grande").style(f"color:{MAR}")
                        ui.icon(icono, size="26px").style(f"color:{MAR}")
                    ui.label(titulo).classes("font-bold text-lg")
                    ui.label(texto).classes("text-sm")
        with ui.column().classes("tarjeta gap-2"):
            ui.html("<h2>Plantillas</h2>")
            with ui.row().classes("gap-2"):
                ui.button("Hoja para imprimir (PDF)", icon="picture_as_pdf",
                          on_click=lambda: ui.download.content(exportar.plantilla_cuaderno_pdf(),
                                                               "hoja_desembarque.pdf", "application/pdf")) \
                    .props("unelevated")
                ui.button("Planilla para transcribir (CSV)", icon="table_view",
                          on_click=lambda: ui.download.content(importar.PLANTILLA.encode("utf-8-sig"),
                                                               "plantilla_cuaderno.csv", "text/csv")) \
                    .props("outline")
        with ui.column().classes("tarjeta gap-2"):
            ui.html("<h2>Subir planilla</h2>")
            ui.upload(on_upload=lambda e: al_subir(e), auto_upload=True, label="Elegir archivo CSV") \
                .props('accept=".csv" flat bordered color=primary').classes("w-full")
            reporte = ui.column().classes("w-full gap-2")

    async def al_subir(e: events.UploadEventArguments):
        reporte.clear()
        contenido = await e.file.read()
        with sesion() as s:
            try:
                rep = importar.revisar(s, importar.leer_csv(contenido))
            except Exception as ex:  # archivo ilegible o columnas faltantes
                with reporte:
                    ui.label(f"No se pudo leer el archivo: {ex}. Revisa que use las columnas de la plantilla.") \
                        .classes("text-negative")
                return
        buenas = sum(r["estado"] == "ok" for r in rep)
        dudosas = sum(r["estado"] == "advertencia" for r in rep)
        malas = sum(r["estado"] == "error" for r in rep)
        tabla = pd.DataFrame([{k: v for k, v in r.items() if k != "datos"} for r in rep])
        with reporte:
            with ui.row().classes("gap-4"):
                for n, txt, c in [(buenas, "sin observaciones", "verde"), (dudosas, "dudosas", "amarillo"),
                                  (malas, "con error", "rojo")]:
                    with ui.column().classes("gap-0"):
                        ui.label(str(n)).classes("kpi-valor").style(f"color:{COLORES[c]}")
                        ui.label(txt).classes("kpi-label")
            ui.table(columns=[{"name": k, "label": k.capitalize(), "field": k, "align": "left"}
                              for k in ("fila", "fecha", "embarcacion", "especie", "kg", "motivos")],
                     rows=tabla.to_dict("records"), row_key="fila", pagination=8) \
                .classes("w-full").props("dense wrap-cells flat bordered")
            with ui.row().classes("gap-2 items-center"):
                ui.label("Reporte de la revisión:").classes("tenue")
                ui.button("PDF", icon="picture_as_pdf", on_click=lambda: ui.download.content(
                    exportar.a_pdf(tabla, "Revisión de cuaderno", f"{len(rep)} filas"), "revision_cuaderno.pdf",
                    "application/pdf")).props("outline")
                ui.button("CSV", icon="table_view", on_click=lambda: ui.download.content(
                    exportar.a_csv(tabla), "revision_cuaderno.csv", "text/csv")).props("outline")

            def confirmar():
                with sesion() as s:
                    n = importar.guardar(s, rep)
                ui.notify(f"{n} filas guardadas. {malas} con error quedaron fuera: corrígelas en el CSV y súbelo "
                          "de nuevo.", type="positive", multi_line=True)
                reporte.clear()
            with ui.row().classes("gap-2"):
                ui.button("Cancelar", on_click=reporte.clear).props("flat")
                ui.button(f"Guardar {buenas + dudosas} filas", icon="save", on_click=confirmar) \
                    .props(f"unelevated {'disable' if buenas + dudosas == 0 else ''}")
