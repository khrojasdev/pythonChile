"""¿Salgo mañana? Semáforo que junta estado del mar (simulado), veda y economía de la salida."""
from datetime import date, timedelta

from nicegui import ui
from sqlmodel import select

from app import analytics
from app.db import sesion
from app.models import Embarcacion, Especie, Rol
from app.ui_comun import bote_actual, marco, rol_actual, selector_especies, sin_permiso, tarjeta_veredicto

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


@ui.page("/salir")
def salir():
    if r := sin_permiso([Rol.PESCADOR, Rol.SINDICATO]):
        return r
    hoy = date.today()
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}
    fechas = {(hoy + timedelta(days=k)).isoformat(): ("Mañana" if k == 1 else
              f"{DIAS[(hoy + timedelta(days=k)).weekday()]} {(hoy + timedelta(days=k)).day}") for k in (1, 2, 3)}
    estado = {"embarcacion_id": bote_actual() or next(iter(botes)), "especie_id": especies[0].id,
              "fecha": next(iter(fechas))}

    with marco("¿Salgo mañana?"):
        with ui.column().classes("tarjeta"):
            if rol_actual() != Rol.PESCADOR.value:
                sel_bote = ui.select(botes, label="Embarcación", with_input=True) \
                    .bind_value(estado, "embarcacion_id").classes("w-full")
            else:
                sel_bote = None
            sel_fecha = ui.toggle(fechas).props("no-caps spread").bind_value(estado, "fecha").classes("w-full")
            selector_especies(especies, estado["especie_id"],
                              lambda e: (estado.update(especie_id=e.value), mostrar()))
        zona = ui.column().classes("w-full gap-3")

        def mostrar():
            zona.clear()
            if not estado["especie_id"]:
                return
            with sesion() as s:
                sem = analytics.semaforo_salida(s, estado["embarcacion_id"], estado["especie_id"],
                                                date.fromisoformat(estado["fecha"]))
            with zona:
                tarjeta_veredicto(sem.color, sem.titulo, sem.razones)
                with ui.expansion("¿Qué NO considera este semáforo?", icon="help").classes("tarjeta"):
                    for t in [
                        "No sabe a dónde van a ir los otros botes: si todos salen al mismo lugar, "
                        "la captura y el precio pueden bajar para todos.",
                        "El estado del mar es simulado. En la caleta real se conectaría a un pronóstico oficial.",
                        "La captura típica es un promedio: un día puntual puede ser mucho mejor o peor.",
                        "La decisión final es del patrón: él conoce el mar mejor que cualquier dato.",
                    ]:
                        ui.label(f"• {t}")
        mostrar()
        sel_fecha.on_value_change(lambda _: mostrar())
        if sel_bote:
            sel_bote.on_value_change(lambda _: mostrar())
