"""Portada pública: clima del día, pronóstico, noticias de pesca y avisos. Botón para ingresar."""
from datetime import datetime
from pathlib import Path

from nicegui import ui
from sqlmodel import select

from app.analytics import dec
from app.db import sesion
from app.models import Aviso
from app.servicios import clima, noticias
from app.ui_comun import BOYA, COLORES, MARINO, estilos, logo, rol_actual

TEXTO_MAR = {"verde": "Mar tranquilo", "amarillo": "Mar regular", "rojo": "Mar malo", "gris": "Sin dato de oleaje"}

# Foto: «Wiki Tour - Caleta Portales 01», Nereidas, CC BY-SA 3.0, Wikimedia Commons.
# Si existe app/static/caleta_portales.jpg se usa la copia local (no depende de internet).
FOTO_REMOTA = ("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Wiki_Tour_-_Caleta_Portales_01.JPG/"
               "1920px-Wiki_Tour_-_Caleta_Portales_01.JPG")
FOTO_LOCAL = Path(__file__).resolve().parent.parent / "static" / "caleta_portales.jpg"
FOTO_PAGINA = "https://commons.wikimedia.org/wiki/File:Wiki_Tour_-_Caleta_Portales_01.JPG"
FOTO_CREDITO = "Foto: Caleta Portales, Valparaíso · Nereidas · CC BY-SA 3.0"


def url_foto() -> str:
    return "/static/caleta_portales.jpg" if FOTO_LOCAL.exists() else FOTO_REMOTA


CSS_PORTADA = """
<style>
  .hero { position:relative; width:100%; min-height:600px; color:white; overflow:hidden;
          background:#0B3C5D var(--foto) center 78% / cover no-repeat; }
  .hero::before { content:""; position:absolute; inset:0;
     background: linear-gradient(100deg, rgba(6,33,54,.92) 0%, rgba(8,45,72,.72) 38%, rgba(8,45,72,.18) 68%,
                 rgba(8,45,72,0) 100%),
                 linear-gradient(0deg, rgba(6,33,54,.85) 0%, rgba(6,33,54,0) 34%); }
  .hero-nav { position:relative; max-width:1120px; margin:0 auto; padding:18px 20px; display:flex;
              align-items:center; gap:12px; }
  .marca-nombre { font-family:'Archivo',system-ui,sans-serif; font-weight:800; font-size:22px; line-height:1;
                  font-stretch:87%; }
  .marca-sub { font-size:13px; opacity:.8; }
  .hero-capa { position:relative; max-width:1120px; margin:0 auto; padding:56px 20px 120px; display:flex;
               gap:32px; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; }
  .hero h1 { font-size:56px !important; color:white; max-width:600px; line-height:1 !important;
             text-wrap:balance; text-shadow:0 2px 18px rgba(0,0,0,.25); }
  .hero-bajada { font-size:19px; max-width:520px; opacity:.95; }
  .clima-hoy { background:rgba(255,255,255,.95); color:#16242F; border-radius:18px; padding:18px 22px;
               width:380px; max-width:100%; box-shadow:0 12px 40px rgba(0,0,0,.25); }
  .temp { font-family:'Archivo'; font-size:54px; font-weight:800; line-height:1; color:#0B3C5D; }
  .credito { position:absolute; right:12px; bottom:8px; font-size:11px; color:rgba(255,255,255,.8);
             text-decoration:none; }
  .credito:hover { text-decoration:underline; }
  .tira-panel { position:relative; max-width:1120px; margin:-72px auto 0; padding:0 20px; z-index:2; }
  .tira-caja { background:white; border-radius:18px; padding:16px 18px; box-shadow:0 10px 30px rgba(11,60,93,.14); }
  .dia-pron { background:#F4F8FA; border-radius:12px; padding:10px 12px; min-width:124px; }
  .tira { overflow-x:auto; flex-wrap:nowrap; padding-bottom:4px; }
  .noticia { border-bottom:1px solid #E1EAEF; padding:12px 0; }
  .noticia:last-child { border-bottom:0; }
  .noticia a { color:#0B3C5D; font-weight:700; text-decoration:none; }
  .noticia a:hover { text-decoration:underline; }
  @media (max-width:700px) {
    .hero { min-height:0; background-position:62% center; }
    .hero::before { background: linear-gradient(180deg, rgba(6,33,54,.85) 0%, rgba(6,33,54,.65) 45%,
                    rgba(6,33,54,.9) 100%); }
    .hero h1 { font-size:36px !important; }
    .hero-capa { padding:28px 16px 96px; }
    .temp { font-size:44px; }
    .tira-panel { padding:0 14px; }
  }
</style>
"""


@ui.page("/")
async def portada():
    estilos()
    ui.add_head_html(CSS_PORTADA)
    ui.add_head_html(f'<link rel="preload" as="image" href="{url_foto()}">')
    destino = "/inicio" if rol_actual() else "/ingresar"

    with ui.element("section").classes("hero").style(f"--foto:url('{url_foto()}')"):
        with ui.element("nav").classes("hero-nav"):
            logo(44)
            with ui.column().classes("gap-0"):
                ui.label("Mar Adentro").classes("marca-nombre")
                ui.label("Caleta digital").classes("marca-sub")
            ui.space()
            ui.button("Pizarra del muelle", icon="tv", on_click=lambda: ui.navigate.to("/pizarra")) \
                .props("flat color=white no-caps").classes("gt-xs").mark("boton-pizarra")
            ui.button("Ir a mi panel" if rol_actual() else "Ingresar", icon="login",
                      on_click=lambda: ui.navigate.to(destino)) \
                .props("color=accent text-color=dark unelevated").mark("boton-ingresar")
        with ui.element("div").classes("hero-capa"):
            with ui.column().classes("gap-3"):
                ui.html("<h1>Cada salida al mar, con datos que ayudan a decidir</h1>")
                ui.label("Capturas, precios de playa y trabajo en tierra de la caleta, en un solo lugar.") \
                    .classes("hero-bajada")
                ui.button("Ingresar a la caleta", icon="arrow_forward", on_click=lambda: ui.navigate.to(destino)) \
                    .props("color=white text-color=primary unelevated size=lg").classes("mt-2")
            caja_clima = ui.column().classes("clima-hoy gap-1")
            with caja_clima:
                ui.skeleton().classes("w-64 h-24")

    with ui.element("div").classes("tira-panel"):
        with ui.column().classes("tira-caja gap-2"):
            with ui.row().classes("w-full items-end justify-between"):
                ui.html("<h2>Próximos días</h2>")
                fuente_clima = ui.label("").classes("tenue")
            tira = ui.row().classes("tira w-full gap-2")
            with tira:
                for _ in range(5):
                    ui.skeleton().classes("w-28 h-32")

    with ui.column().classes("contenedor"):

        with ui.row().classes("fila-resp items-start"):
            with ui.column().classes("tarjeta gap-0 flex-[3]").style("min-width:0"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.html("<h2>Noticias de pesca</h2>")
                    aviso_noticias = ui.label("").classes("tenue")
                lista = ui.column().classes("w-full gap-0")
                with lista:
                    for _ in range(4):
                        ui.skeleton().classes("w-full h-12 my-2")
            with ui.column().classes("tarjeta gap-2 flex-[2]").style("min-width:0"):
                ui.html("<h2>Avisos de la directiva</h2>")
                with sesion() as s:
                    avisos = s.exec(select(Aviso).order_by(Aviso.fijado.desc(), Aviso.publicado_en.desc())
                                    .limit(3)).all()
                for a in avisos:
                    color = {"alerta": COLORES["rojo"], "reunion": BOYA}.get(a.tipo, "#5FA8D3")
                    with ui.column().classes("tarjeta-plana gap-0").style(f"border-left:5px solid {color}"):
                        ui.label(a.titulo).classes("font-bold")
                        ui.label(a.cuerpo).classes("text-sm")
                ui.button("Ingresar a la caleta", icon="login", on_click=lambda: ui.navigate.to(destino)) \
                    .classes("w-full mt-2").props("unelevated color=primary size=lg")

        ui.label("Los datos de la caleta son ficticios (Hackatón Python Chile · Duoc UC Valparaíso). "
                 "Clima y oleaje: Open-Meteo. Noticias: Google Noticias. Para navegar, sigue siempre "
                 "los avisos oficiales de la Capitanía de Puerto.").classes("tenue text-center w-full mt-4")
        with ui.row().classes("w-full justify-center"):
            ui.link(f"{FOTO_CREDITO} (Wikimedia Commons)", FOTO_PAGINA, new_tab=True).classes("tenue text-xs")

    # ------- se cargan después de mostrar la página: así nunca queda "pegada"
    await ui.context.client.connected()
    p = await clima.obtener()
    caja_clima.clear()
    hoy = p.dias[0] if p.dias else None
    with caja_clima:
        with ui.row().classes("items-center gap-4 no-wrap"):
            icono = clima.describir(p.codigo_actual)[1] if p.real else "waves"
            ui.icon(icono, size="54px").style(f"color:{BOYA if icono == 'wb_sunny' else '#1D6A8A'}")
            with ui.column().classes("gap-0"):
                if p.temp_actual is not None:
                    ui.label(f"{p.temp_actual:.0f}°").classes("temp")
                    ui.label(clima.describir(p.codigo_actual)[0]).classes("font-bold")
                else:
                    ui.label("Hoy en el mar").classes("grande")
        if hoy:
            estado = hoy.estado_mar
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.element("div").style(f"width:14px;height:14px;border-radius:50%;background:{COLORES[estado]}")
                partes = [TEXTO_MAR[estado]]
                if hoy.ola_m is not None:
                    partes.append(f"ola {dec(hoy.ola_m)} m")
                if hoy.viento_kn is not None:
                    partes.append(f"viento {hoy.viento_kn:.0f} nudos")
                ui.label(", ".join(partes)).classes("font-bold")
        ui.label(f"Fuente: {p.fuente}" + (f" · {p.error}" if p.error else "")
                 + f" · {datetime.now():%H:%M}").classes("tenue text-xs")
    fuente_clima.text = "Pronóstico de Open-Meteo" if p.real else "Pronóstico simulado (sin conexión a la API)"
    tira.clear()
    with tira:
        for d in p.dias[:7]:
            with ui.column().classes("dia-pron gap-0 items-start").style(
                    f"border-top:5px solid {COLORES[d.estado_mar]}"):
                ui.label(d.nombre).classes("font-bold")
                if d.codigo is not None:
                    ui.icon(d.icono, size="30px").style("color:#1D6A8A")
                    ui.label(f"{d.tmax:.0f}° / {d.tmin:.0f}°").classes("text-sm")
                if d.ola_m is not None:
                    ui.label(f"Ola {dec(d.ola_m)} m").classes("text-sm font-bold")
                if d.viento_kn is not None:
                    ui.label(f"Viento {d.viento_kn:.0f} kn").classes("text-sm")
                if d.lluvia_pct is not None:
                    ui.label(f"Lluvia {d.lluvia_pct:.0f}%").classes("text-xs tenue")

    items, reales = await noticias.obtener()
    lista.clear()
    aviso_noticias.text = "Google Noticias, últimos 30 días" if reales else "Sin conexión: novedades de demo"
    with lista:
        for n in items:
            with ui.column().classes("noticia w-full gap-0"):
                if n.enlace:
                    ui.link(n.titulo, n.enlace, new_tab=True)
                else:
                    ui.label(n.titulo).classes("font-bold").style(f"color:{MARINO}")
                ui.label(" · ".join(x for x in [n.fuente, n.hace] if x)).classes("tenue text-sm")
