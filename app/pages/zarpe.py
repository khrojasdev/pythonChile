"""Zarpe y regreso (pescador) y «En el mar ahora» (registradora y directiva)."""
from __future__ import annotations

from nicegui import ui
from sqlmodel import select

from app import zarpes
from app.db import sesion
from app.models import Embarcacion, Rol
from app.ui_comun import BOYA, COLORES, MAR, bote_actual, marco, quien, rol_actual, sin_permiso, vacio

HORAS = {3: "3 h", 5: "5 h", 8: "8 h", 12: "12 h"}


def tarjeta_en_el_mar(compacta: bool = True) -> None:
    """Resumen para los paneles: cuántos botes están afuera y si alguno se atrasó."""
    with sesion() as s:
        lista = zarpes.en_el_mar(s)
    atrasados = [e for e in lista if e.atrasado]
    color = COLORES["rojo"] if atrasados else MAR
    with ui.row().classes("tarjeta items-center justify-between no-wrap gap-3") \
            .style(f"border-left:8px solid {color}").mark("tarjeta-en-el-mar"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.icon("sailing" if not atrasados else "warning", size="34px").style(f"color:{color}")
            with ui.column().classes("gap-0"):
                ui.label(f"{len(lista)} bote{'s' if len(lista) != 1 else ''} en el mar ahora").classes("grande")
                if atrasados:
                    ui.label("Atrasado: " + ", ".join(f"{e.bote} ({zarpes.texto_duracion(e.minutos_atraso)})"
                                                      for e in atrasados)).classes("font-bold") \
                        .style(f"color:{COLORES['rojo']}")
                else:
                    ui.label("Nadie atrasado respecto de su hora de vuelta.").classes("tenue")
        ui.button("Ver", on_click=lambda: ui.navigate.to("/en-el-mar")).props("unelevated")


@ui.page("/zarpe")
def zarpe():
    if r := sin_permiso([Rol.PESCADOR]):
        return r
    bote = bote_actual()
    with sesion() as s:
        nombre = s.get(Embarcacion, bote).nombre

    with marco("Aviso de zarpe", "/zarpe",
               "Avisa cuando sales y cuando vuelves. Si te atrasas, la registradora y la directiva lo ven. "
               "No se registra dónde pescas."):
        caja = ui.column().classes("w-full gap-3")

    def pintar():
        caja.clear()
        with sesion() as s:
            z = zarpes.zarpe_abierto(s, bote)
        ahora = zarpes.ahora_local()
        with caja:
            if z:
                atr, min_atr, faltan = zarpes.estado(z, ahora)
                color = COLORES["rojo"] if atr else COLORES["verde"]
                with ui.column().classes("tarjeta gap-2").style(f"border-left:8px solid {color}"):
                    ui.label(f"{nombre} está en el mar").classes("grande")
                    ui.label(f"Salió a las {z.salida_en:%H:%M} con {z.tripulantes} persona"
                             f"{'s' if z.tripulantes > 1 else ''}. Vuelta estimada: {z.regreso_estimado:%H:%M}"
                             f"{' del ' + format(z.regreso_estimado, '%d-%m') if z.regreso_estimado.date() != ahora.date() else ''}.")
                    if atr:
                        ui.label(f"Van {zarpes.texto_duracion(min_atr)} de atraso.").classes("font-bold") \
                            .style(f"color:{COLORES['rojo']}")
                    else:
                        ui.label(f"Faltan {zarpes.texto_duracion(faltan)} para la hora estimada.").classes("tenue")
                    ui.button("Ya volví a tierra", icon="anchor", on_click=lambda: volver(z.id)) \
                        .props("unelevated size=lg color=positive").classes("w-full").mark("ya-volvi")
                return
            form = {"horas": 5, "tripulantes": 2, "contacto": ""}
            with ui.column().classes("tarjeta gap-3"):
                ui.label(f"Salida de {nombre}").classes("grande")
                ui.label("¿En cuántas horas piensas volver?").classes("font-bold")
                ui.toggle(HORAS).props("no-caps spread size=lg").bind_value(form, "horas").classes("w-full") \
                    .mark("zarpe-horas")
                ui.number("Personas a bordo", min=1, max=12, step=1).props("inputmode=numeric") \
                    .bind_value(form, "tripulantes").classes("w-full").mark("zarpe-tripulantes")
                ui.input("¿A quién avisar en tierra? (opcional)").bind_value(form, "contacto").classes("w-full")
                ui.button("Avisar zarpe", icon="sailing", on_click=lambda: salir(form)) \
                    .props("unelevated size=lg").classes("w-full").mark("avisar-zarpe")
            with ui.row().classes("tarjeta-plana items-start gap-2 no-wrap"):
                ui.icon("info", size="22px").style(f"color:{MAR}")
                ui.label("Esto no reemplaza el zarpe oficial ante la Capitanía de Puerto: es un aviso entre "
                         "compañeros, para que alguien note si no vuelves a tiempo.").classes("text-sm")

    def salir(form):
        try:
            with sesion() as s:
                z = zarpes.registrar_zarpe(s, bote, float(form["horas"]), int(form["tripulantes"] or 0),
                                           form["contacto"], quien())
            ui.notify(f"Zarpe avisado. Vuelta estimada a las {z.regreso_estimado:%H:%M}.", type="positive")
        except ValueError as e:
            ui.notify(str(e), type="warning")
        pintar()

    def volver(zid):
        with sesion() as s:
            zarpes.registrar_regreso(s, zid)
        ui.notify("Bienvenido de vuelta. Regreso anotado.", type="positive")
        pintar()

    pintar()


@ui.page("/en-el-mar")
def en_el_mar():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    with sesion() as s:
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}

    with marco("En el mar ahora", "/en-el-mar",
               "Botes que avisaron su zarpe y aún no vuelven. Se marca en rojo quien pasa 30 minutos de su "
               "hora estimada. La lista se actualiza sola cada minuto."):
        resumen = ui.row().classes("w-full gap-2")
        lista = ui.column().classes("w-full gap-3")
        if rol_actual() == Rol.REGISTRADORA.value:
            with ui.expansion("Anotar el zarpe de un bote", icon="add").classes("tarjeta w-full"):
                form = {"bote": None, "horas": 5, "tripulantes": 2}
                ui.select(botes, label="Embarcación", with_input=True).bind_value(form, "bote").classes("w-full") \
                    .mark("zarpe-bote")
                ui.toggle(HORAS).props("no-caps spread").bind_value(form, "horas").classes("w-full")
                ui.number("Personas a bordo", min=1, max=12, step=1).bind_value(form, "tripulantes").classes("w-full")
                ui.button("Anotar zarpe", icon="sailing", on_click=lambda: anotar(form)).props("unelevated") \
                    .mark("anotar-zarpe")

    def anotar(form):
        if not form["bote"]:
            ui.notify("Elige la embarcación", type="warning")
            return
        try:
            with sesion() as s:
                zarpes.registrar_zarpe(s, form["bote"], float(form["horas"]), int(form["tripulantes"] or 0),
                                       "Registradora en el muelle", "Registradora")
            ui.notify(f"Zarpe de {botes[form['bote']]} anotado", type="positive")
        except ValueError as e:
            ui.notify(str(e), type="warning")
        pintar()

    def volvio(zid, nombre):
        with sesion() as s:
            zarpes.registrar_regreso(s, zid)
        ui.notify(f"{nombre}: regreso anotado", type="positive")
        pintar()

    def pintar():
        with sesion() as s:
            filas = zarpes.en_el_mar(s)
            vueltos = zarpes.volvieron_hoy(s)
        atrasados = sum(e.atrasado for e in filas)
        resumen.clear()
        with resumen:
            for valor, texto, color in [(len(filas), "en el mar", MAR),
                                        (atrasados, "atrasados", COLORES["rojo"] if atrasados else MAR),
                                        (sum(e.zarpe.tripulantes for e in filas), "personas a bordo", MAR),
                                        (vueltos, "volvieron hoy", COLORES["verde"])]:
                with ui.column().classes("tarjeta gap-0 flex-1").style("min-width:140px"):
                    ui.label(str(valor)).classes("kpi-valor").style(f"color:{color}")
                    ui.label(texto).classes("kpi-label")
        lista.clear()
        with lista:
            if not filas:
                vacio("No hay botes en el mar ahora.", "anchor")
            for e in filas:
                z = e.zarpe
                color = COLORES["rojo"] if e.atrasado else (BOYA if e.minutos_para_volver < 60 else COLORES["verde"])
                with ui.row().classes("tarjeta items-center justify-between gap-3 flex-wrap") \
                        .style(f"border-left:8px solid {color}"):
                    with ui.column().classes("gap-0"):
                        ui.label(e.bote).classes("grande")
                        ui.label(f"Salió {z.salida_en:%H:%M} · vuelta estimada {z.regreso_estimado:%H:%M} · "
                                 f"{z.tripulantes} a bordo").classes("text-sm")
                        if e.atrasado:
                            ui.label(f"Atrasado {zarpes.texto_duracion(e.minutos_atraso)}. Llamar al bote"
                                     + (f" o a su contacto ({z.contacto})" if z.contacto else "")
                                     + "; si no responde, avisar a la Capitanía de Puerto.").classes("font-bold text-sm").style(f"color:{COLORES['rojo']}")
                        else:
                            ui.label(f"Vuelve en {zarpes.texto_duracion(e.minutos_para_volver)}").classes("tenue")
                    ui.button("Volvió", icon="anchor", on_click=lambda zid=z.id, n=e.bote: volvio(zid, n)) \
                        .props("outline color=positive").mark(f"volvio-{z.id}")

    pintar()
    ui.timer(60, pintar, immediate=False)
