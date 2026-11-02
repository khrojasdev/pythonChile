"""Informes y descargas (directiva): ficha para fondos y tablas en PDF o CSV."""
from datetime import date, timedelta

import pandas as pd
from nicegui import run, ui
from sqlmodel import select

from app import analytics, exportar
from app.db import sesion
from app.models import Embarcacion, Rol
from app.reports import generar_pdf
from app.ui_comun import MAR, marco, sin_permiso


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
