"""Páginas de administración: vedas y cuotas, embarcaciones, personas en tierra, aporte en tierra."""
from datetime import date, timedelta

import pandas as pd
from nicegui import ui
from sqlmodel import select

from app import analytics, config, exportar
from app.analytics import clp, dec
from app.db import sesion
from app.ilustraciones import especie_svg
from app.models import Embarcacion, Especie, PersonaTierra, Rol, TipoTrabajo
from app.ui_comun import COLORES, MAR, boton_descargas, kpi, marco, sin_permiso

MESES = {0: "Sin veda", **{i: m for i, m in enumerate(
    ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"], start=1)}}


# ------------------------------------------------------------------ vedas y cuotas
@ui.page("/cuotas")
def cuotas():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
        uso = {c["especie"]: c for c in analytics.cuotas(s)}
    with marco("Vedas y cuotas", "/cuotas",
               "Son reglas externas: la plataforma no las cambia, solo avisa. Actualízalas cuando la autoridad "
               "publique nuevas resoluciones."):
        for e in especies:
            with ui.column().classes("tarjeta gap-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.html(especie_svg(e.nombre, 50))
                    ui.label(e.nombre).classes("grande")
                    c = uso.get(e.nombre)
                    if c:
                        ui.badge(f"{c['pct']:.0f}% de la cuota usada").props(
                            f"color={'negative' if c['alerta'] else 'positive'}")
                with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                    ini = ui.select(MESES, value=e.veda_mes_inicio or 0, label="Veda desde").classes("w-36")
                    fin = ui.select(MESES, value=e.veda_mes_fin or 0, label="Veda hasta").classes("w-36")
                    cuota = ui.number("Cuota anual (kg)", value=e.cuota_anual_kg, min=0, step=1000) \
                        .classes("w-48").props("clearable")
                    kgmax = ui.number("Máx. kg por salida", value=e.kg_max_salida, min=1).classes("w-40")

                    def guardar(eid=e.id, ini=ini, fin=fin, cuota=cuota, kgmax=kgmax):
                        if bool(ini.value) != bool(fin.value):
                            ui.notify("La veda necesita mes de inicio y de término (o ambos «Sin veda»)",
                                      type="warning")
                            return
                        with sesion() as s:
                            x = s.get(Especie, eid)
                            x.veda_mes_inicio, x.veda_mes_fin = ini.value or None, fin.value or None
                            x.cuota_anual_kg = cuota.value or None
                            x.kg_max_salida = kgmax.value or x.kg_max_salida
                            s.add(x)
                            s.commit()
                        ui.notify("Guardado", type="positive")
                    ui.button("Guardar", icon="save", on_click=guardar).props("unelevated")


# ------------------------------------------------------------------ embarcaciones
@ui.page("/embarcaciones")
def embarcaciones():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    hoy = date.today()
    with marco("Embarcaciones", "/embarcaciones",
               "Socios de la caleta. La actividad se muestra como cantidad de salidas, no como ingresos."):
        with ui.column().classes("tarjeta gap-2"):
            ui.html("<h2>Agregar embarcación</h2>")
            with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                nombre = ui.input("Nombre").classes("flex-1")
                patron = ui.input("Patrón").classes("flex-1")
                matricula = ui.input("Matrícula").classes("w-36")
                litros = ui.number("Litros por salida", value=60, min=1).classes("w-40")
                ui.button("Agregar", icon="add", on_click=lambda: agregar()).props("unelevated")
        lista = ui.column().classes("w-full gap-2")

    def agregar():
        if not (nombre.value and patron.value):
            ui.notify("Falta el nombre del bote o del patrón", type="warning")
            return
        with sesion() as s:
            s.add(Embarcacion(nombre=nombre.value.strip(), patron=patron.value.strip(),
                              matricula=matricula.value or "S/M", litros_por_salida=litros.value or 60))
            s.commit()
        ui.notify(f"{nombre.value} agregada", type="positive")
        nombre.value = patron.value = matricula.value = ""
        pintar()

    def cambiar(bid, activa):
        with sesion() as s:
            b = s.get(Embarcacion, bid)
            b.activa = activa
            s.add(b)
            s.commit()
        ui.notify("Actualizado", type="positive")

    def pintar():
        with sesion() as s:
            botes = s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()
            df = analytics.desembarques_df(s, desde=hoy - timedelta(days=90))
        salidas = df.groupby("embarcacion_id")["fecha"].nunique() if not df.empty else pd.Series(dtype=int)
        lista.clear()
        with lista:
            ui.label(f"{sum(b.activa for b in botes)} activas de {len(botes)}").classes("font-bold")
            with ui.element("div").classes("rejilla"):
                for b in botes:
                    with ui.row().classes("tarjeta items-center no-wrap gap-3 py-3"):
                        ui.icon("directions_boat", size="30px").style(f"color:{MAR if b.activa else '#9AA9B4'}")
                        with ui.column().classes("gap-0 flex-1 min-w-0"):
                            ui.label(b.nombre).classes("font-bold")
                            ui.label(f"{b.patron} · {b.matricula} · {int(salidas.get(b.id, 0))} salidas en 90 días") \
                                .classes("text-sm tenue")
                        ui.switch(value=b.activa, on_change=lambda e, i=b.id: cambiar(i, e.value)) \
                            .props('aria-label="Activa"')
    pintar()


# ------------------------------------------------------------------ personas en tierra
@ui.page("/personas")
def personas():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    hoy = date.today()
    with marco("Personas en tierra", "/personas",
               "Quienes encarnan, filetean, venden y limpian. Aparecen en la lista al anotar trabajo en tierra."):
        with ui.column().classes("tarjeta gap-2"):
            ui.html("<h2>Agregar persona</h2>")
            with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                nombre = ui.input("Nombre y apellido").classes("flex-1")
                rol = ui.select({t.value: t.value.capitalize() for t in TipoTrabajo},
                                value=TipoTrabajo.ENCARNADO.value, label="Trabajo principal").classes("w-48")
                ui.button("Agregar", icon="person_add", on_click=lambda: agregar()).props("unelevated")
        filtro = ui.input("Buscar", on_change=lambda: pintar()).props("clearable").classes("w-full") \
            .props('prepend-icon="search"')
        lista = ui.column().classes("w-full gap-2")

    def agregar():
        if not (nombre.value or "").strip():
            ui.notify("Escribe el nombre", type="warning")
            return
        with sesion() as s:
            s.add(PersonaTierra(nombre=nombre.value.strip(), rol_principal=TipoTrabajo(rol.value)))
            s.commit()
        ui.notify(f"{nombre.value} agregada", type="positive")
        nombre.value = ""
        pintar()

    def cambiar(pid, activa):
        with sesion() as s:
            p = s.get(PersonaTierra, pid)
            p.activa = activa
            s.add(p)
            s.commit()

    def pintar():
        with sesion() as s:
            gente = s.exec(select(PersonaTierra).order_by(PersonaTierra.nombre)).all()
            df = analytics.tierra_df(s, desde=hoy - timedelta(days=30))
        dias = df.groupby("persona_id")["fecha"].nunique() if not df.empty else pd.Series(dtype=int)
        texto = (filtro.value or "").lower()
        lista.clear()
        with lista:
            visibles = [p for p in gente if texto in p.nombre.lower()]
            ui.label(f"{len(visibles)} personas").classes("font-bold")
            with ui.element("div").classes("rejilla"):
                for p in visibles:
                    with ui.row().classes("tarjeta items-center no-wrap gap-3 py-2"):
                        with ui.column().classes("gap-0 flex-1 min-w-0"):
                            ui.label(p.nombre).classes("font-bold")
                            ui.label(f"{p.rol_principal.value.capitalize()} · {int(dias.get(p.id, 0))} días "
                                     f"trabajados (30 días)").classes("text-sm tenue")
                        ui.switch(value=p.activa, on_change=lambda e, i=p.id: cambiar(i, e.value)) \
                            .props('aria-label="Activa"')
    pintar()


# ------------------------------------------------------------------ aporte en tierra (directiva)
@ui.page("/aporte-tierra")
def aporte_tierra():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    hoy = date.today()
    estado = {"dias": 30}
    with marco("Aporte en tierra", "/aporte-tierra",
               "El trabajo que sostiene cada salida, valorizado con tarifas referenciales de la directiva."):
        ui.toggle({30: "30 días", 90: "3 meses", 365: "1 año"}, value=30,
                  on_change=lambda e: (estado.update(dias=e.value), pintar())).props("spread unelevated") \
            .classes("w-full border rounded-lg")
        zona = ui.column().classes("w-full gap-3")
        with ui.column().classes("tarjeta gap-1"):
            ui.html("<h2>Tarifas referenciales</h2>")
            for t, (unidad, tarifa) in config.TARIFA_TIERRA.items():
                ui.label(f"{t.value.capitalize()}: {clp(tarifa)} por {unidad.rstrip('s') if unidad != 'kg' else 'kg'}")
            ui.label("Se ajustan en config.py. Son una referencia para valorizar, no un sueldo.").classes("tenue")

    def tabla(desde):
        with sesion() as s:
            df = analytics.tierra_df(s, desde=desde, hasta=hoy)
        if df.empty:
            return df
        return (df.groupby(["persona", "tipo"]).agg(Días=("fecha", "nunique"), Horas=("horas", "sum"),
                                                    Valor=("valor", "sum")).reset_index()
                .rename(columns={"persona": "Persona", "tipo": "Trabajo"}).sort_values("Valor", ascending=False))

    def pintar():
        desde = hoy - timedelta(days=estado["dias"])
        t = tabla(desde)
        zona.clear()
        with zona:
            if t.empty:
                ui.label("Sin registros en el periodo.")
                return
            with ui.element("div").classes("rejilla"):
                kpi(str(t["Persona"].nunique()), "personas", "groups")
                kpi(f"{t['Horas'].sum():,.0f}".replace(",", "."), "horas", "schedule")
                kpi(analytics.clp_corto(t["Valor"].sum()), "valor estimado", "payments", COLORES["verde"])
            por_tipo = t.groupby("Trabajo")["Valor"].sum().sort_values()
            with ui.column().classes("tarjeta"):
                ui.html("<h2>Por tipo de trabajo</h2>")
                ui.echart({"grid": {"left": 90, "right": 20, "top": 10, "bottom": 30},
                           "xAxis": {"type": "value"}, "tooltip": {},
                           "yAxis": {"type": "category", "data": [x.capitalize() for x in por_tipo.index]},
                           "series": [{"type": "bar", "data": por_tipo.round(0).tolist(), "color": MAR}]}) \
                    .classes("w-full h-56")
            with ui.column().classes("tarjeta gap-2"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.html("<h2>Por persona</h2>")
                    boton_descargas(f"aporte_tierra_{estado['dias']}d", lambda: exportar.a_csv(t),
                                    lambda: exportar.a_pdf(t, "Aporte en tierra por persona",
                                                           f"Últimos {estado['dias']} días"))
                vista = t.head(40).copy()
                vista["Horas"] = vista["Horas"].map(lambda x: dec(x, 0))
                vista["Valor"] = vista["Valor"].map(clp)
                ui.table(rows=vista.to_dict("records"),
                         columns=[{"name": c, "label": c, "field": c, "align": "left"} for c in vista.columns],
                         pagination=10).classes("w-full").props("flat bordered dense")
    pintar()
