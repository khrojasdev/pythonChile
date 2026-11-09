"""Informes y descargas (directiva): ficha para fondos y tablas en PDF o CSV."""
from datetime import date, timedelta

import pandas as pd
from nicegui import run, ui
from sqlmodel import select

from app import analytics, exportar, fondos
from app.db import sesion
from app.models import Embarcacion, Rol
from app.reports import generar_pdf
from app.ui_comun import BOYA, COLORES, MAR, marco, sin_permiso


def _desembarques(desde: date, hasta: date) -> pd.DataFrame:
    with sesion() as s:
        df = analytics.desembarques_df(s, desde=desde, hasta=hasta, incluir_errores=True)
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
    if df.empty:
        return df
    df = df.sort_values("fecha")
    return pd.DataFrame({
        "Fecha": df["fecha"].dt.date, "Embarcación": df["embarcacion_id"].map(botes), "Especie": df["especie"],
        "Kg": df["kg"], "Precio $/kg": df["precio_kg"], "Comprador": df["comprador_tipo"],
        "Origen": df["origen"], "Estado": df["calidad"]})


def _tierra(desde: date, hasta: date) -> pd.DataFrame:
    with sesion() as s:
        df = analytics.tierra_df(s, desde=desde, hasta=hasta)
    if df.empty:
        return df
    return (df.groupby(["persona", "tipo"]).agg(Días=("fecha", "nunique"), Horas=("horas", "sum"),
                                                Cantidad=("cantidad", "sum"), Valor=("valor", "sum"))
            .reset_index().rename(columns={"persona": "Persona", "tipo": "Trabajo"})
            .sort_values("Valor", ascending=False))


def _resumen_mensual(desde: date, hasta: date) -> pd.DataFrame:
    with sesion() as s:
        df = analytics.desembarques_df(s, desde=desde, hasta=hasta)
    if df.empty:
        return df
    df["Mes"] = df["fecha"].dt.to_period("M").astype(str)
    t = df.groupby(["Mes", "especie"]).agg(Kg=("kg", "sum"), Ventas=("ingreso", "sum"),
                                          Precio_mediano=("precio_kg", "median")).reset_index()
    return t.rename(columns={"especie": "Especie", "Precio_mediano": "Precio mediano $/kg"})


@ui.page("/informes")
def informes():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    hoy = date.today()
    estado = {"desde": (hoy - timedelta(days=90)).isoformat(), "hasta": hoy.isoformat()}

    def rango():
        try:
            return date.fromisoformat(estado["desde"]), date.fromisoformat(estado["hasta"])
        except (TypeError, ValueError):
            return hoy - timedelta(days=90), hoy

    with marco("Informes y descargas", "/informes",
               "PDF para imprimir o enviar; CSV para abrir en Excel. Los informes para terceros no incluyen "
               "nombres de embarcaciones."):
        with ui.column().classes("tarjeta gap-2").style(f"border-top:6px solid {MAR}"):
            ui.html("<h2>Ficha de producción para fondos</h2>")
            ui.label("Últimos 12 meses: desembarque mensual, trabajo en tierra valorizado, precios y calidad de los "
                     "datos, con sus límites explicados. Sin nombres de embarcaciones.").classes("text-sm")

            async def ficha():
                b.props("loading")
                pdf = await run.io_bound(generar_pdf)
                b.props(remove="loading")
                ui.download.content(pdf, f"ficha_caleta_{hoy:%Y%m%d}.pdf", "application/pdf")
            b = ui.button("Descargar ficha (PDF)", icon="picture_as_pdf", on_click=ficha).props("unelevated size=lg")

        _lista_fondos()

        with ui.column().classes("tarjeta gap-3"):
            ui.html("<h2>Tablas del periodo</h2>")
            with ui.row().classes("gap-2 items-center"):
                ui.input("Desde").props("type=date").bind_value(estado, "desde")
                ui.input("Hasta").props("type=date").bind_value(estado, "hasta")
                for dias, txt in [(30, "30 días"), (90, "3 meses"), (365, "1 año")]:
                    ui.button(txt, on_click=lambda d=dias: estado.update(
                        desde=(hoy - timedelta(days=d)).isoformat(), hasta=hoy.isoformat())).props("flat")
            for titulo, texto, fn, nombre, uso_interno in [
                    ("Resumen mensual por especie", "Kilos, ventas y precio mediano.", _resumen_mensual,
                     "resumen_mensual", False),
                    ("Desembarques detallados", "Cada línea registrada, con su origen y estado de revisión.",
                     _desembarques, "desembarques", True),
                    ("Trabajo en tierra por persona", "Días, horas y valor estimado de cada persona.",
                     _tierra, "trabajo_tierra", True)]:
                with ui.row().classes("tarjeta-plana items-center justify-between gap-2 flex-wrap"):
                    with ui.column().classes("gap-0"):
                        ui.label(titulo).classes("font-bold")
                        ui.label(texto + (" Uso interno: incluye nombres." if uso_interno else "")) \
                            .classes("text-sm tenue")
                    with ui.row().classes("gap-2"):
                        ui.button("PDF", icon="picture_as_pdf", on_click=lambda f=fn, t=titulo, n=nombre: ui.download
                                  .content(exportar.a_pdf(f(*rango()), t, f"Periodo {rango()[0]:%d-%m-%Y} a "
                                                                          f"{rango()[1]:%d-%m-%Y}"),
                                           f"{n}.pdf", "application/pdf")).props("outline").mark(f"pdf-{nombre}")
                        ui.button("CSV", icon="table_view", on_click=lambda f=fn, n=nombre: ui.download.content(
                            exportar.a_csv(f(*rango())), f"{n}.csv", "text/csv")).props("outline") \
                            .mark(f"csv-{nombre}")


def _lista_fondos():
    """¿Listos para postular a un fondo? Revisa los datos y dice qué falta."""
    with sesion() as s:
        reqs = fondos.revisar(s)
    ok, total = fondos.puntaje(reqs)
    color = COLORES["verde"] if ok == total else BOYA if ok >= total - 2 else COLORES["rojo"]
    with ui.column().classes("tarjeta gap-3").style(f"border-top:6px solid {color}").mark("lista-fondos"):
        with ui.row().classes("w-full items-center justify-between gap-2"):
            with ui.column().classes("gap-0"):
                ui.html("<h2>¿Listos para postular a un fondo?</h2>")
                ui.label("Lo que un evaluador suele mirar, revisado con los datos de los últimos 12 meses.") \
                    .classes("text-sm tenue")
            ui.label(f"{ok} de {total}").classes("kpi-valor").style(f"color:{color}")
        for r in reqs:
            with ui.row().classes("tarjeta-plana items-start gap-3 no-wrap"):
                ui.icon("check_circle" if r.cumple else "radio_button_unchecked", size="28px") \
                    .style(f"color:{COLORES['verde'] if r.cumple else BOYA}")
                with ui.column().classes("gap-1 flex-1"):
                    with ui.row().classes("w-full justify-between gap-2"):
                        ui.label(r.titulo).classes("font-bold")
                        ui.label(f"{r.valor} · meta: {r.meta}").classes("text-sm")
                    ui.linear_progress(r.avance, show_value=False, size="8px") \
                        .props(f"color={'positive' if r.cumple else 'warning'} rounded")
                    if not r.cumple:
                        ui.label(r.consejo).classes("text-sm")
        with ui.row().classes("gap-2 items-center"):
            ui.label("Guía interna: cada convocatoria tiene sus propias bases.").classes("tenue text-sm")
            ui.button("Descargar lista (PDF)", icon="picture_as_pdf", on_click=lambda: ui.download.content(
                exportar.a_pdf(fondos.tabla(reqs), "¿Listos para postular a un fondo?",
                               f"{ok} de {total} requisitos cumplidos. Datos de los últimos 12 meses."),
                "lista_fondos.pdf", "application/pdf")).props("outline")
