"""Piezas de interfaz compartidas: estilos, encabezado, control de acceso por rol."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Optional

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from app.models import Rol

AZUL = "#0B3C5D"
MAR = "#1D6A8A"
ARENA = "#F4EBDD"
COLORES = {"verde": "#2E7D32", "amarillo": "#F2A900", "rojo": "#C62828", "gris": "#78909C"}

CSS = f"""
<style>
  body {{ background: {ARENA}; font-size: 17px; }}
  .q-btn {{ min-height: 48px; }}
  .tarjeta {{ background: white; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
              padding: 16px; width: 100%; }}
  .tile {{ border-radius: 18px; min-height: 104px; width: 100%; text-transform: none;
           font-size: 18px; font-weight: 600; line-height: 1.2; }}
  .kpi-valor {{ font-size: 22px; word-break: break-word; font-weight: 700; color: {AZUL}; line-height: 1.1; }}
  .kpi-label {{ font-size: 13px; color: #555; }}
  .grande {{ font-size: 22px; font-weight: 700; }}
  .contenedor {{ width: 100%; max-width: 760px; margin: 0 auto; padding: 12px 16px 48px; gap: 14px; }}
  .q-field__native, .q-field__input {{ font-size: 20px !important; }}
  .especies .q-btn {{ font-size: 17px; }}
</style>
"""

NOMBRE_ROL = {Rol.PESCADOR.value: "Pescador", Rol.REGISTRADORA.value: "Registradora",
              Rol.SINDICATO.value: "Sindicato"}


def rol_actual() -> Optional[str]:
    return app.storage.user.get("rol")


def bote_actual() -> Optional[int]:
    return app.storage.user.get("embarcacion_id")


def sin_permiso(roles: Iterable[Rol]) -> Optional[RedirectResponse]:
    """Privacidad por rol: si el usuario no tiene el rol, se le devuelve al inicio.
    Uso en una página:  if (r := sin_permiso([...])): return r"""
    if rol_actual() not in {r.value for r in roles}:
        return RedirectResponse("/")
    return None


@contextmanager
def marco(titulo: str, volver: bool = True):
    """Encabezado y contenedor comunes de todas las páginas."""
    ui.add_head_html(CSS)
    ui.colors(primary=AZUL, secondary=MAR, positive=COLORES["verde"], negative=COLORES["rojo"],
              warning=COLORES["amarillo"])
    rol = rol_actual()
    with ui.header().classes("items-center justify-between no-wrap").style(f"background:{AZUL}"):
        with ui.row().classes("items-center gap-1 no-wrap min-w-0"):
            if volver:
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=white")
            ui.label(titulo).classes("text-lg font-bold ellipsis")
        if rol:
            texto = NOMBRE_ROL.get(rol, rol)
            if rol == Rol.PESCADOR.value and app.storage.user.get("bote_nombre"):
                texto = f"🛶 {app.storage.user['bote_nombre']}"
            ui.badge(texto).props("color=white text-color=primary").classes("text-sm")
    with ui.column().classes("contenedor") as c:
        yield c


def kpi(valor: str, etiqueta: str) -> None:
    with ui.column().classes("tarjeta gap-0 items-start"):
        ui.label(valor).classes("kpi-valor")
        ui.label(etiqueta).classes("kpi-label")


def tarjeta_veredicto(color: str, titulo: str, razones: list[str]) -> None:
    with ui.column().classes("tarjeta gap-2").style(f"border-left: 10px solid {COLORES[color]}"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.element("div").style(
                f"width:44px;height:44px;border-radius:50%;background:{COLORES[color]};flex-shrink:0")
            ui.label(titulo).classes("grande").style(f"color:{COLORES[color]}")
        for r in razones:
            ui.label(r).classes("text-base")


def selector_especies(especies, valor, al_cambiar) -> ui.toggle:
    opciones = {e.id: f"{e.icono} {e.nombre}" for e in especies}
    return (ui.toggle(opciones, value=valor, on_change=al_cambiar)
            .props("no-caps toggle-color=secondary glossy=false").classes("flex-wrap especies"))
