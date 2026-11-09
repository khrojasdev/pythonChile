"""Diseño común: colores, tipografía, menú lateral por rol y componentes reutilizables."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterable, Optional

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from app.ilustraciones import LOGO, especie_svg
from app.models import Rol

# ------------------------------------------------------------------ tokens
MARINO = "#0B3C5D"      # fondo marino: encabezados, menú
MAR = "#1D6A8A"         # acciones secundarias
ESPUMA = "#EAF2F5"      # fondo de la app
BOYA = "#F2A900"        # acento: lo que está activo o pide atención
TINTA = "#16242F"       # texto
COLORES = {"verde": "#2E7D4F", "amarillo": "#D99A00", "rojo": "#C8402F", "gris": "#78909C"}
# compatibilidad con código anterior
AZUL, ARENA = MARINO, ESPUMA

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,500..800'
           '&family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet" media="print" '
           'onload="this.media=\'all\'">')   # no bloquea la página si la red del muelle es lenta

CSS = f"""
<style>
  :root {{ --marino:{MARINO}; --mar:{MAR}; --espuma:{ESPUMA}; --boya:{BOYA}; --tinta:{TINTA}; }}
  body {{ background:{ESPUMA}; color:{TINTA}; font-family:'Atkinson Hyperlegible', system-ui, sans-serif;
         font-size:17px; line-height:1.45; }}
  h1, h2, h3, .titulo, .kpi-valor, .grande {{ font-family:'Archivo', system-ui, sans-serif; font-stretch:87%; }}
  h1 {{ font-size:30px !important; font-weight:800 !important; line-height:1.1 !important; margin:0 !important;
        letter-spacing:-.01em !important; }}
  h2 {{ font-size:21px !important; font-weight:750 !important; line-height:1.25 !important; margin:0 !important;
        letter-spacing:0 !important; }}
  .rejilla {{ display:grid; gap:10px; width:100%; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); }}
  .fila-resp {{ display:flex; gap:16px; width:100%; align-items:stretch; }}
  .fila-resp > * {{ flex:1 1 0; min-width:0; }}
  @media (max-width: 760px) {{ .fila-resp {{ flex-direction:column; }} }}
  .q-btn {{ min-height:46px; text-transform:none; font-weight:700; letter-spacing:0; border-radius:10px; }}
  .tarjeta {{ background:white; border-radius:14px; padding:18px; width:100%;
              border:1px solid #D6E3EA; }}
  .tarjeta-plana {{ background:#F6FAFB; border-radius:10px; padding:12px 14px; width:100%; }}
  .kpi-valor {{ font-size:28px; font-weight:800; color:{MARINO}; line-height:1.05; word-break:break-word; }}
  .kpi-label {{ font-size:14px; color:#4B5E6B; }}
  .grande {{ font-size:22px; font-weight:750; }}
  .tenue {{ color:#56697A; font-size:14px; }}
  .contenedor {{ width:100%; max-width:980px; margin:0 auto; padding:20px 18px 64px; gap:16px; }}
  .q-field__native, .q-field__input {{ font-size:19px !important; }}
  .menu .q-item {{ border-radius:10px; margin:2px 10px; color:#D7E6EE; min-height:46px; }}
  .menu .q-item.activo {{ background:rgba(255,255,255,.1); color:white; box-shadow:inset 4px 0 0 {BOYA}; }}
  .menu .q-item .q-icon {{ color:#9CC3D8; }}
  .menu .q-item.activo .q-icon {{ color:{BOYA}; }}
  .chip-especie {{ background:white; border:2px solid #D6E3EA; border-radius:12px; padding:6px 10px 4px;
                   min-width:92px; cursor:pointer; color:{TINTA}; }}
  .chip-especie.sel {{ border-color:{MARINO}; background:#E3EEF4; box-shadow:inset 0 -4px 0 {BOYA}; }}
  .chip-especie:focus-visible, .q-btn:focus-visible {{ outline:3px solid {BOYA}; outline-offset:2px; }}
  .semaforo {{ width:46px; height:46px; border-radius:50%; flex-shrink:0;
               box-shadow: inset 0 -5px 0 rgba(0,0,0,.18); }}
  .franja-encabezado {{ border-bottom:1px solid #D6E3EA; padding-bottom:12px; width:100%; }}
  .nicegui-content {{ padding:0; }}
  @media (max-width: 600px) {{ h1 {{ font-size:25px !important; }} .kpi-valor {{ font-size:23px; }}
    .rejilla {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }} .contenedor {{ padding:16px 14px 56px; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; animation:none !important; }} }}
</style>
"""

NOMBRE_ROL = {Rol.PESCADOR.value: "Pescador", Rol.REGISTRADORA.value: "Registradora",
              Rol.SINDICATO.value: "Directiva"}

# (texto, ícono Material, ruta) — cada rol ve SOLO lo que necesita
MENUS = {
    Rol.PESCADOR.value: [
        ("Mi día", "today", "/inicio"),
        ("Aviso de zarpe", "sailing", "/zarpe"),
        ("Anotar desembarque", "add_circle", "/registro"),
        ("Ventas por completar", "pending_actions", "/pendientes"),
        ("Venta conjunta", "groups", "/ventas-conjuntas"),
        ("¿Salgo mañana?", "explore", "/salir"),
        ("¿Es buen precio?", "price_check", "/precio"),
        ("Mis números", "insights", "/mis-numeros"),
        ("Clima y mar", "waves", "/clima"),
        ("Avisos", "campaign", "/avisos"),
    ],
    Rol.REGISTRADORA.value: [
        ("Jornada de hoy", "today", "/inicio"),
        ("Anotar desembarque", "add_circle", "/registro"),
        ("En el mar ahora", "sailing", "/en-el-mar"),
        ("Trabajo en tierra", "front_hand", "/tierra"),
        ("Ventas por completar", "pending_actions", "/pendientes"),
        ("Venta conjunta", "handshake", "/ventas-conjuntas"),
        ("Comprobantes", "badge", "/comprobantes"),
        ("Personas en tierra", "groups", "/personas"),
        ("Digitalizar cuaderno", "menu_book", "/cuaderno"),
        ("Pizarra de precios", "price_check", "/precio"),
        ("Clima y mar", "waves", "/clima"),
        ("Avisos", "campaign", "/avisos"),
    ],
    Rol.SINDICATO.value: [
        ("Panel de la caleta", "space_dashboard", "/inicio"),
        ("Revisión de datos", "fact_check", "/revision"),
        ("Informes y fondos", "download", "/informes"),
        ("En el mar ahora", "sailing", "/en-el-mar"),
        ("Venta conjunta", "handshake", "/ventas-conjuntas"),
        ("Aporte en tierra", "front_hand", "/aporte-tierra"),
        ("Comprobantes", "badge", "/comprobantes"),
        ("Vedas y cuotas", "gavel", "/cuotas"),
        ("Embarcaciones", "directions_boat", "/embarcaciones"),
        ("Precios de playa", "price_check", "/precio"),
        ("Clima y mar", "waves", "/clima"),
        ("Avisos a la caleta", "campaign", "/avisos"),
    ],
}


def rol_actual() -> Optional[str]:
    return app.storage.user.get("rol")


def bote_actual() -> Optional[int]:
    return app.storage.user.get("embarcacion_id")


def quien() -> str:
    rol = rol_actual()
    if rol == Rol.PESCADOR.value:
        return app.storage.user.get("bote_nombre", "pescador")
    return NOMBRE_ROL.get(rol, "")


def sin_permiso(roles: Iterable[Rol]) -> Optional[RedirectResponse]:
    """Privacidad por rol: quien no tiene el rol vuelve a la pantalla de ingreso.
    Uso:  if (r := sin_permiso([...])): return r"""
    if rol_actual() not in {r.value for r in roles}:
        return RedirectResponse("/ingresar")
    return None


def estilos() -> None:
    ui.add_head_html(FUENTES + CSS)
    ui.colors(primary=MARINO, secondary=MAR, accent=BOYA, positive=COLORES["verde"],
              negative=COLORES["rojo"], warning=COLORES["amarillo"])


def logo(tam: int = 36) -> None:
    ui.html(LOGO).style(f"width:{tam}px;height:{tam}px;flex-shrink:0")


def salir_sesion() -> None:
    app.storage.user.clear()
    ui.navigate.to("/")


@contextmanager
def marco(titulo: str, ruta: Optional[str] = None, bajada: Optional[str] = None):
    """Encabezado + menú lateral del rol + contenedor de la página."""
    estilos()
    rol = rol_actual()
    menu = MENUS.get(rol, [])
    with ui.left_drawer(value=False, fixed=True).props("width=272 breakpoint=1000 show-if-above") \
            .style(f"background:{MARINO}").classes("p-0") as cajon:
        with ui.row().classes("items-center gap-3 no-wrap px-5 pt-5 pb-3"):
            logo(40)
            with ui.column().classes("gap-0"):
                ui.label("Mar Adentro").classes("titulo text-white text-xl font-extrabold")
                ui.label(quien()).classes("text-sm").style("color:#9CC3D8")
        with ui.list().classes("menu w-full"):
            for texto, icono, destino in menu:
                with ui.item(on_click=lambda d=destino: ui.navigate.to(d)) \
                        .classes("activo" if destino == ruta else "").props("clickable"):
                    with ui.item_section().props("avatar").classes("min-w-0"):
                        ui.icon(icono, size="22px")
                    ui.item_section(texto)
            ui.separator().style("background:rgba(255,255,255,.12); margin:10px 16px")
            for texto, icono, accion in [("Cómo usamos los datos", "info", lambda: ui.navigate.to("/limites")),
                                         ("Pizarra del muelle", "tv", lambda: ui.navigate.to("/pizarra")),
                                         ("Portada", "home", lambda: ui.navigate.to("/")),
                                         ("Cambiar de perfil", "logout", salir_sesion)]:
                with ui.item(on_click=accion).classes("activo" if ruta == "/limites" and icono == "info" else "") \
                        .props("clickable"):
                    with ui.item_section().props("avatar").classes("min-w-0"):
                        ui.icon(icono, size="22px")
                    ui.item_section(texto)
    with ui.header().classes("items-center no-wrap gap-2 px-3 py-2").style(f"background:{MARINO}"):
        ui.button(icon="menu", on_click=cajon.toggle).props("flat round color=white").classes("lt-md") \
            .props('aria-label="Abrir menú"')
        with ui.row().classes("items-center gap-2 no-wrap gt-sm"):
            logo(28)
            ui.label("Mar Adentro").classes("titulo text-lg font-bold text-white")
        ui.label(titulo).classes("titulo text-lg font-bold text-white ellipsis lt-md")
        ui.space()
        if rol:
            ui.badge(NOMBRE_ROL.get(rol, rol)).props("color=accent text-color=dark").classes("text-sm px-2 py-1")
    with ui.column().classes("contenedor") as c:
        with ui.column().classes("franja-encabezado gap-1"):
            ui.html(f"<h1>{titulo}</h1>")
            if bajada:
                ui.label(bajada).classes("tenue")
        yield c


# ------------------------------------------------------------------ componentes
def kpi(valor: str, etiqueta: str, icono: Optional[str] = None, color: str = MARINO) -> None:
    with ui.column().classes("tarjeta gap-1 items-start"):
        if icono:
            ui.icon(icono, size="24px").style(f"color:{color}")
        ui.label(valor).classes("kpi-valor").style(f"color:{color}")
        ui.label(etiqueta).classes("kpi-label")


ICONO_RAZON = {"🌊": "waves", "🐟": "set_meal", "💲": "sell", "⛽": "local_gas_station", "📉": "trending_down",
               "📊": "show_chart", "📈": "trending_up", "🎯": "flag", "📚": "history", "📒": "edit_note",
               "⚠️": "warning"}


def tarjeta_veredicto(color: str, titulo: str, razones: list[str]) -> None:
    with ui.column().classes("tarjeta gap-2").style(f"border-left: 8px solid {COLORES[color]}"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.element("div").classes("semaforo").style(f"background:{COLORES[color]}")
            ui.label(titulo).classes("grande").style(f"color:{COLORES[color]}")
        for r in razones:
            icono = next((v for k, v in ICONO_RAZON.items() if r.startswith(k)), None)
            texto = r
            if icono:
                texto = r.split(" ", 1)[1] if " " in r else r
            with ui.row().classes("items-start gap-2 no-wrap"):
                ui.icon(icono or "chevron_right", size="20px").style(f"color:{MAR}; margin-top:2px")
                ui.label(texto).classes("text-base")


def selector_especies(especies, valor, al_cambiar: Callable) -> ui.row:
    """Botones grandes con el dibujo de cada especie (fáciles de tocar con las manos mojadas)."""
    estado = {"valor": valor}
    fila = ui.row().classes("gap-2 w-full")
    botones = {}

    def elegir(eid):
        estado["valor"] = eid
        for k, b in botones.items():
            b.classes(add="sel") if k == eid else b.classes(remove="sel")
        al_cambiar(type("Evento", (), {"value": eid})())

    with fila:
        for e in especies:
            with ui.column().classes("chip-especie items-center gap-0" + (" sel" if e.id == valor else "")) \
                    .on("click", lambda _, eid=e.id: elegir(eid)).props(f'tabindex=0 role=button '
                                                                      f'aria-label="{e.nombre}"') \
                    .mark(f"especie-{e.nombre}") as b:
                ui.html(especie_svg(e.nombre, 44))
                ui.label(e.nombre).classes("text-sm font-bold")
            b.on("keydown.enter", lambda _, eid=e.id: elegir(eid))
            botones[e.id] = b
    fila.elegir = elegir  # para pruebas
    return fila


def boton_descargas(nombre: str, generar_csv: Callable[[], bytes], generar_pdf: Callable[[], bytes],
                    etiqueta: str = "Descargar") -> None:
    """Par de botones CSV / PDF."""
    with ui.row().classes("gap-2 items-center"):
        ui.label(etiqueta).classes("tenue")
        ui.button("PDF", icon="picture_as_pdf",
                  on_click=lambda: ui.download.content(generar_pdf(), f"{nombre}.pdf", "application/pdf")) \
            .props("outline color=primary")
        ui.button("CSV", icon="table_view",
                  on_click=lambda: ui.download.content(generar_csv(), f"{nombre}.csv", "text/csv")) \
            .props("outline color=primary")


def vacio(texto: str, icono: str = "inbox") -> None:
    with ui.column().classes("tarjeta items-center gap-1 py-8"):
        ui.icon(icono, size="40px").style("color:#9CB3C2")
        ui.label(texto).classes("tenue text-center")
