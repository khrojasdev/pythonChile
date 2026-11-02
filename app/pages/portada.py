"""Portada pública: clima del día, pronóstico, noticias de pesca y avisos. Botón para ingresar."""
from datetime import datetime

from nicegui import ui
from sqlmodel import select

from app.analytics import dec
from app.db import sesion
from app.ilustraciones import HERO
from app.models import Aviso
from app.servicios import clima, noticias
from app.ui_comun import BOYA, COLORES, MARINO, estilos, logo, rol_actual

TEXTO_MAR = {"verde": "Mar tranquilo", "amarillo": "Mar regular", "rojo": "Mar malo", "gris": "Sin dato de oleaje"}

CSS_PORTADA = f"""
<style>
  .hero {{ width:100%; background:linear-gradient(180deg,#A9D0E3 0%,#DDEBEF 100%); }}
  .hero-capa {{ max-width:1080px; margin:0 auto; padding:40px 20px 24px; display:flex; gap:28px;
               align-items:flex-end; justify-content:space-between; flex-wrap:wrap; }}
  .hero h1 {{ font-size:48px !important; color:{MARINO}; max-width:580px; line-height:1.02 !important; }}
  .hero-paisaje {{ height:clamp(130px, 24vw, 300px); width:100%; display:block; margin-top:-8px; }}
  .hero-paisaje svg {{ width:100%; height:100%; display:block; }}
  .clima-hoy {{ background:rgba(255,255,255,.94); border-radius:16px; padding:16px 20px; width:400px; max-width:100%;
                border:1px solid rgba(11,60,93,.15); }}
  .temp {{ font-family:'Archivo'; font-size:52px; font-weight:800; line-height:1; color:{MARINO}; }}
  .dia-pron {{ background:white; border:1px solid #D6E3EA; border-radius:12px; padding:10px 12px; min-width:118px; }}
  .tira {{ overflow-x:auto; flex-wrap:nowrap; padding-bottom:6px; }}
  .noticia {{ border-bottom:1px solid #E1EAEF; padding:12px 0; }}
  .noticia:last-child {{ border-bottom:0; }}
  .noticia a {{ color:{MARINO}; font-weight:700; text-decoration:none; }}
  .noticia a:hover {{ text-decoration:underline; }}
  @media (max-width:600px) {{ .hero h1 {{ font-size:33px !important; }} .temp {{ font-size:42px; }}
    .hero-capa {{ padding:24px 16px 18px; }} }}
</style>
"""


@ui.page("/")
async def portada():
    estilos()
    ui.add_head_html(CSS_PORTADA)
    with ui.header().classes("items-center no-wrap px-4 py-2").style(f"background:{MARINO}"):
        logo(34)
        ui.label("Mar Adentro").classes("titulo text-white text-xl font-extrabold")
        ui.space()
        destino = "/inicio" if rol_actual() else "/ingresar"
        ui.button("Ir a mi panel" if rol_actual() else "Ingresar", icon="login",
                  on_click=lambda: ui.navigate.to(destino)).props("color=accent text-color=dark unelevated") \
            .mark("boton-ingresar")

    with ui.element("section").classes("hero"):
        with ui.element("div").classes("hero-capa"):
            with ui.column().classes("gap-2"):
                ui.html("<h1>Cada salida al mar, con datos que ayudan a decidir</h1>")
                ui.label("Registro de capturas, precios de playa y trabajo en tierra de la caleta.") \
                    .classes("text-lg").style(f"color:{MARINO}; max-width:520px")
            caja_clima = ui.column().classes("clima-hoy gap-1")
            with caja_clima:
                ui.skeleton().classes("w-64 h-24")
        ui.html(HERO).classes("hero-paisaje")

    with ui.column().classes("contenedor"):
        with ui.row().classes("w-full items-end justify-between"):
            ui.html("<h2>Próximos días</h2>")
            fuente_clima = ui.label("").classes("tenue")
        tira = ui.row().classes("tira w-full gap-2")
        with tira:
            for _ in range(5):
                ui.skeleton().classes("w-28 h-36")

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
