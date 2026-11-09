"""Comprobante de trabajo en tierra: PDF por persona y periodo."""
from __future__ import annotations

from datetime import date, timedelta

from nicegui import ui
from sqlmodel import select

from app import comprobante
from app.analytics import clp, dec
from app.db import sesion
from app.models import PersonaTierra, Rol
from app.ui_comun import MAR, NOMBRE_ROL, kpi, marco, rol_actual, sin_permiso, vacio


def _periodos(hoy: date) -> dict[str, tuple[date, date]]:
    inicio_mes = hoy.replace(day=1)
    fin_ant = inicio_mes - timedelta(days=1)
    return {"Este mes": (inicio_mes, hoy), "Mes pasado": (fin_ant.replace(day=1), fin_ant),
            "Últimos 3 meses": (hoy - timedelta(days=90), hoy), "Último año": (hoy - timedelta(days=365), hoy)}


@ui.page("/comprobantes")
def comprobantes():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    hoy = date.today()
    periodos = _periodos(hoy)
    with sesion() as s:
        personas = {p.id: f"{p.nombre} ({p.rol_principal.value})"
                    for p in s.exec(select(PersonaTierra).order_by(PersonaTierra.nombre)).all()}
    estado = {"persona": next(iter(personas), None), "periodo": "Mes pasado"}

    with marco("Comprobante de trabajo en tierra", "/comprobantes",
               "Un documento para cada persona con los días, horas y el valor estimado de su trabajo. Le sirve "
               "para postular a subsidios, cursos o demostrar su actividad."):
        with ui.column().classes("tarjeta gap-2"):
            sel = ui.select(personas, label="Persona", with_input=True) \
                .bind_value(estado, "persona").classes("w-full").mark("comp-persona")
            tog = ui.toggle(list(periodos)).props("no-caps spread") \
                .bind_value(estado, "periodo").classes("w-full").mark("comp-periodo")

        @ui.refreshable
        def vista():
            if not estado["persona"]:
                return
            desde, hasta = periodos[estado["periodo"]]
            df = comprobante.detalle(estado["persona"], desde, hasta)
            ui.label(f"{personas[estado['persona']]} · {desde:%d-%m-%Y} a {hasta:%d-%m-%Y}").classes("font-bold")
            if df.empty:
                vacio("Sin trabajo registrado en este periodo.", "event_busy")
                return
            with ui.element("div").classes("rejilla"):
                kpi(str(df["fecha"].nunique()), "días trabajados", "event_available")
                kpi(dec(df["horas"].sum(), 0), "horas", "schedule")
                kpi(clp(df["valor"].sum()), "valor estimado", "payments")
            res = comprobante.resumen_por_tipo(df)
            ui.table(columns=[{"name": c, "label": c, "field": c, "align": "left" if i == 0 else "right"}
                              for i, c in enumerate(res.columns)],
                     rows=[{c: (clp(v) if c == "Valor estimado" else f"{v:,.0f}".replace(",", ".")
                                if isinstance(v, (int, float)) else v)
                            for c, v in fila.items()} for fila in res.to_dict("records")]) \
                .props("flat dense").classes("w-full tarjeta")

            def bajar():
                pdf = comprobante.comprobante_pdf(estado["persona"], desde, hasta,
                                                  NOMBRE_ROL.get(rol_actual(), "Registradora"))
                nombre = personas[estado["persona"]].split(" (")[0].replace(" ", "_")
                ui.download.content(pdf, f"comprobante_{nombre}_{desde:%Y%m}.pdf", "application/pdf")
            ui.button("Descargar comprobante (PDF)", icon="picture_as_pdf", on_click=bajar) \
                .props("unelevated size=lg").classes("w-full").mark("bajar-comprobante")
            ui.label("Incluye espacio para la firma de la registradora y de la directiva. El valor es "
                     "referencial: no es una liquidación de sueldo.").classes("tenue text-sm") \
                .style(f"border-left:4px solid {MAR}; padding-left:8px")

        vista()
        sel.on_value_change(vista.refresh)
        tog.on_value_change(vista.refresh)
