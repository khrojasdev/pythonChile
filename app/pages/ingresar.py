"""Elegir perfil: pescador (elige su bote), registradora o directiva (con PIN)."""
from nicegui import app, ui
from sqlmodel import select

from app import config
from app.db import sesion
from app.ilustraciones import rol_svg
from app.models import Embarcacion, Rol
from app.ui_comun import MARINO, estilos, logo

PERFILES = [
    (Rol.PESCADOR, "Pescador", "Anota tu captura, revisa si el precio es justo y decide si salir mañana."),
    (Rol.REGISTRADORA, "Registradora", "Lleva la jornada del muelle: desembarques, trabajo en tierra y cuadernos."),
    (Rol.SINDICATO, "Directiva", "Revisa y aprueba datos, publica avisos y descarga informes para fondos."),
]


def _entrar(rol: Rol, **extra) -> None:
    app.storage.user.clear()
    app.storage.user.update(rol=rol.value, **extra)
    ui.navigate.to("/inicio")


@ui.page("/ingresar")
def ingresar():
    estilos()
    ui.add_head_html("""<style>
      .perfil { background:white; border:2px solid #D6E3EA; border-radius:16px; padding:16px; cursor:pointer; }
      .perfil.sel { border-color:#0B3C5D; box-shadow: inset 0 -6px 0 #F2A900; }
      .perfil svg { width:120px; height:94px; }
    </style>""")
    with ui.header().classes("items-center no-wrap px-4 py-2").style(f"background:{MARINO}"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=white") \
            .props('aria-label="Volver a la portada"')
        logo(32)
        ui.label("Mar Adentro").classes("titulo text-white text-xl font-extrabold")

    with sesion() as s:
        botes = {b.id: f"{b.nombre} ({b.patron})" for b in
                 s.exec(select(Embarcacion).where(Embarcacion.activa == True)  # noqa: E712
                        .order_by(Embarcacion.nombre)).all()}

    with ui.column().classes("contenedor"):
        ui.html("<h1>¿Con qué perfil entras?</h1>")
        ui.label("Cada perfil ve solo lo que necesita. Los datos de cada bote los ve solo su dueño.") \
            .classes("tenue")
        tarjetas = {}
        formularios = {}
        with ui.row().classes("fila-resp"):
            for rol, nombre, texto in PERFILES:
                with ui.column().classes("perfil flex-1 gap-1 items-start") \
                        .on("click", lambda _, r=rol: mostrar(r)).props("tabindex=0 role=button") \
                        .mark(f"perfil-{rol.value}") as t:
                    ui.html(rol_svg(rol.value))
                    ui.label(nombre).classes("grande")
                    ui.label(texto).classes("text-sm")
                t.on("keydown.enter", lambda _, r=rol: mostrar(r))
                tarjetas[rol] = t

        with ui.column().classes("tarjeta gap-3") as f_pesc:
            ui.html("<h2>Pescador</h2>")
            sel = ui.select(botes, label="Mi embarcación", with_input=True).classes("w-full").mark("sel-bote")

            def entrar_pescador():
                if not sel.value:
                    ui.notify("Elige tu embarcación", type="warning")
                    return
                _entrar(Rol.PESCADOR, embarcacion_id=sel.value, bote_nombre=botes[sel.value].split(" (")[0])
            ui.button("Entrar", icon="login", on_click=entrar_pescador).classes("w-full") \
                .props("unelevated size=lg").mark("entrar-pescador")
        formularios[Rol.PESCADOR] = f_pesc

        for rol, pin_ok in [(Rol.REGISTRADORA, config.PIN_REGISTRADORA), (Rol.SINDICATO, config.PIN_SINDICATO)]:
            with ui.column().classes("tarjeta gap-3") as f:
                ui.html(f"<h2>{'Registradora' if rol == Rol.REGISTRADORA else 'Directiva'}</h2>")
                pin = ui.input("PIN", password=True).props("inputmode=numeric").classes("w-full") \
                    .mark(f"pin-{rol.value}")

                def entrar(rol=rol, pin=pin, pin_ok=pin_ok):
                    if pin.value != pin_ok:
                        ui.notify("PIN incorrecto. Revisa los números e intenta de nuevo.", type="negative")
                        return
                    _entrar(rol)
                pin.on("keydown.enter", lambda _, e=entrar: e())
                ui.button("Entrar", icon="login", on_click=entrar).classes("w-full") \
                    .props("unelevated size=lg").mark(f"entrar-{rol.value}")
            formularios[rol] = f

        ui.label(f"PIN de demostración: registradora {config.PIN_REGISTRADORA}, directiva {config.PIN_SINDICATO}") \
            .classes("tenue text-center w-full")

        def mostrar(rol: Rol):
            for r, t in tarjetas.items():
                t.classes(add="sel") if r == rol else t.classes(remove="sel")
            for r, f in formularios.items():
                f.set_visibility(r == rol)
        mostrar(Rol.PESCADOR)
