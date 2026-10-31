"""Inicio: elegir quién eres (rol) y menú de botones grandes según el rol."""
from nicegui import app, ui
from sqlmodel import select

from app import config
from app.db import sesion
from app.models import Embarcacion, Rol
from app.ui_comun import AZUL, MAR, marco, rol_actual

MENU = {
    Rol.PESCADOR.value: [
        ("🛶", "Anotar desembarque", "/registro", AZUL),
        ("🚦", "¿Salgo mañana?", "/salir", MAR),
        ("💲", "¿Es buen precio?", "/precio", MAR),
        ("📒", "Mis números", "/mis-numeros", AZUL),
    ],
    Rol.REGISTRADORA.value: [
        ("🛶", "Anotar desembarque", "/registro", AZUL),
        ("🧺", "Trabajo en tierra", "/tierra", AZUL),
        ("💲", "¿Es buen precio?", "/precio", MAR),
        ("🧹", "Revisar datos", "/calidad", MAR),
    ],
    Rol.SINDICATO.value: [
        ("📊", "Panel de la caleta", "/panel", AZUL),
        ("📄", "Informe para fondos", "/informe", AZUL),
        ("🧹", "Revisar datos", "/calidad", MAR),
        ("🧺", "Trabajo en tierra", "/tierra", MAR),
        ("💲", "Precios", "/precio", MAR),
        ("🚦", "Semáforo de salida", "/salir", MAR),
    ],
}


@ui.page("/")
def inicio():
    with marco("Mar Adentro", volver=False):
        rol = rol_actual()
        if rol is None:
            _elegir_rol()
            return
        with ui.grid(columns=2).classes("w-full gap-3"):
            for icono, texto, ruta, color in MENU[rol]:
                ui.button(f"{icono}\n{texto}", on_click=lambda r=ruta: ui.navigate.to(r)) \
                    .props(f"unelevated color=white text-color=white") \
                    .style(f"background:{color} !important; white-space:pre-line") \
                    .classes("tile")
        with ui.row().classes("w-full justify-between"):
            ui.button("Límites y decisiones", icon="info",
                      on_click=lambda: ui.navigate.to("/limites")).props("flat no-caps")
            ui.button("Cambiar de rol", icon="logout", on_click=_salir).props("flat no-caps")


def _salir():
    app.storage.user.clear()
    ui.navigate.to("/")


def _elegir_rol():
    ui.label("Cada día se sale al mar con mucha experiencia. Aquí juntamos los datos.") \
        .classes("text-lg text-center w-full")
    ui.label("¿Quién eres?").classes("grande w-full text-center")

    with sesion() as s:
        botes = {b.id: f"{b.nombre} ({b.patron})" for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}

    with ui.column().classes("tarjeta"):
        ui.label("🎣 Pescador").classes("grande")
        sel = ui.select(botes, label="Mi embarcación", with_input=True).classes("w-full").mark("sel-bote")

        def entrar_pescador():
            if not sel.value:
                ui.notify("Elige tu embarcación", type="warning")
                return
            app.storage.user.update(rol=Rol.PESCADOR.value, embarcacion_id=sel.value,
                                    bote_nombre=botes[sel.value].split(" (")[0])
            ui.navigate.to("/")
        ui.button("Entrar", on_click=entrar_pescador).classes("w-full").mark("entrar-pescador")

    for rol, icono, pin_ok in [(Rol.REGISTRADORA, "🧺", config.PIN_REGISTRADORA),
                               (Rol.SINDICATO, "🏛️", config.PIN_SINDICATO)]:
        with ui.column().classes("tarjeta"):
            ui.label(f"{icono} {'Registradora de la caleta' if rol == Rol.REGISTRADORA else 'Directiva del sindicato'}") \
                .classes("grande")
            pin = ui.input("PIN", password=True).props('inputmode=numeric').classes("w-full").mark(f"pin-{rol.value}")

            def entrar(rol=rol, pin=pin, pin_ok=pin_ok):
                if pin.value != pin_ok:
                    ui.notify("PIN incorrecto", type="negative")
                    return
                app.storage.user.update(rol=rol.value)
                ui.navigate.to("/")
            ui.button("Entrar", on_click=entrar).classes("w-full").mark(f"entrar-{rol.value}")
    ui.label(f"PIN de demostración: registradora {config.PIN_REGISTRADORA} · sindicato {config.PIN_SINDICATO}") \
        .classes("text-xs text-gray-500 w-full text-center")
