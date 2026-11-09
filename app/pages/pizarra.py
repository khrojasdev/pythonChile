"""Pizarra del muelle: pantalla pública para un televisor o un celular, sin ingresar.

Muestra lo que todos en la caleta necesitan saber al llegar: el estado del mar, los
precios de referencia de la semana, las ventas conjuntas abiertas y cuántos botes hay
en el mar. No muestra nada individual de ningún bote.
"""
from __future__ import annotations

from datetime import date

from nicegui import ui
from sqlmodel import select

from app import analytics, config, lotes, zarpes
from app.analytics import clp, dec
from app.db import sesion
from app.ilustraciones import especie_svg
from app.models import Aviso, Especie, EstadoLote
from app.servicios import clima
from app.ui_comun import BOYA, COLORES, estilos, logo

CSS = """
<style>
  body { background:#082032 !important; }
  .piz { color:#F4F7F8; padding:24px clamp(16px,3vw,40px) 40px; max-width:1600px; margin:0 auto; }
  .piz h2 { color:#F4F7F8; font-size:26px !important; margin:0; }
  .piz-caja { background:#0F3550; border-radius:20px; padding:20px 22px; width:100%; }
  .piz-grid { display:grid; grid-template-columns: 1.4fr 1fr; gap:20px; width:100%; }
  .piz-especie { width:100%; display:grid; grid-template-columns: 56px 1fr auto; align-items:center; gap:14px;
                 padding:10px 0; border-bottom:1px solid #24506E; }
  .piz-especie:last-child { border-bottom:0; }
  .piz-precio { font-family:'Archivo',system-ui,sans-serif; font-weight:800; font-size:34px; line-height:1; }
  .piz-sub { color:#9FBBCB; font-size:16px; }
  .piz-grande { font-family:'Archivo',system-ui,sans-serif; font-weight:800; font-size:64px; line-height:1; }
  .piz-reloj { font-family:'Archivo',system-ui,sans-serif; font-weight:800; font-size:40px; }
  @media (max-width:900px) { .piz-grid { grid-template-columns:1fr; } .piz-grande { font-size:48px; } }
</style>
"""


@ui.page("/pizarra")
async def pizarra():
    estilos()
    ui.add_head_html(CSS)
    hoy = date.today()
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
        refs = []
        for e in especies:                     # semana; si no hubo ventas, el último mes
            r = analytics.precio_referencia(s, e.id, hoy, dias=7)
            refs.append((e, r, 7) if r.n else (e, analytics.precio_referencia(s, e.id, hoy, dias=30), 30))
        abiertos = lotes.lotes(s, EstadoLote.ABIERTO, limite=3)
        mar = zarpes.en_el_mar(s)
        aviso = s.exec(select(Aviso).order_by(Aviso.fijado.desc(), Aviso.publicado_en.desc())).first()

    with ui.column().classes("piz w-full gap-5"):
        with ui.row().classes("w-full items-center gap-4 no-wrap"):
            logo(56)
            with ui.column().classes("gap-0"):
                ui.label("Pizarra del muelle").classes("titulo text-3xl font-extrabold")
                ui.label(config.NOMBRE_CALETA).classes("piz-sub")
            ui.space()
            reloj = ui.label(zarpes.ahora_local().strftime("%H:%M")).classes("piz-reloj")
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=white") \
                .props('aria-label="Volver a la portada"')

        with ui.element("div").classes("piz-grid"):
            with ui.column().classes("piz-caja gap-0"):
                ui.html("<h2>Precio de playa esta semana</h2>")
                ui.label("Mediana pagada por kilo en los últimos 7 días (o 30 si hubo pocas ventas), y el rango habitual.").classes("piz-sub mb-2")
                for e, r, dias in refs:
                    with ui.element("div").classes("piz-especie"):
                        ui.html(especie_svg(e.nombre, 52))
                        with ui.column().classes("gap-0"):
                            ui.label(e.nombre).classes("text-2xl font-bold")
                            ui.label((f"entre {clp(r.p25)} y {clp(r.p75)} · {r.n} ventas"
                                      + (" (último mes)" if dias == 30 else "")) if r.n
                                     else "sin ventas en el último mes").classes("piz-sub")
                        ui.label(clp(r.mediana) if r.n else "—").classes("piz-precio") \
                            .style(f"color:{BOYA if r.n else '#9FBBCB'}")
            with ui.column().classes("gap-5 w-full"):
                caja_mar = ui.column().classes("piz-caja gap-1")
                with caja_mar:
                    ui.html("<h2>El mar hoy</h2>")
                    ui.skeleton().classes("w-full h-16").props("dark")
                with ui.column().classes("piz-caja gap-1"):
                    ui.html("<h2>En el mar ahora</h2>")
                    atr = sum(z.atrasado for z in mar)
                    with ui.row().classes("items-end gap-3"):
                        ui.label(str(len(mar))).classes("piz-grande")
                        ui.label(f"bote{'s' if len(mar) != 1 else ''} · "
                                 f"{sum(z.zarpe.tripulantes for z in mar)} personas").classes("text-xl mb-2")
                    if atr:
                        ui.label(f"{atr} con atraso: la registradora está coordinando.").classes("text-lg font-bold") \
                            .style(f"color:#FF8A70")
                with ui.column().classes("piz-caja gap-2"):
                    ui.html("<h2>Venta conjunta abierta</h2>")
                    if not abiertos:
                        ui.label("No hay ventas conjuntas abiertas hoy.").classes("piz-sub")
                    for r in abiertos:
                        with ui.row().classes("items-center gap-3 no-wrap"):
                            ui.html(especie_svg(r.especie, 44))
                            with ui.column().classes("gap-0"):
                                ui.label(f"{r.especie}: {dec(r.kg_total, 0)} kg de {r.botes} botes") \
                                    .classes("text-xl font-bold")
                                ui.label(f"Mínimo {clp(r.lote.precio_minimo)}/kg. Súmate con la registradora.") \
                                    .classes("piz-sub")
        if aviso:
            with ui.row().classes("piz-caja items-center gap-3 no-wrap").style(f"border-left:8px solid {BOYA}"):
                ui.icon("campaign", size="34px").style(f"color:{BOYA}")
                with ui.column().classes("gap-0"):
                    ui.label(aviso.titulo).classes("text-xl font-bold")
                    ui.label(aviso.cuerpo).classes("piz-sub")
        ui.label("Datos de la caleta ficticios (Hackatón Python Chile). Clima: Open-Meteo. Para navegar, siga "
                 "los avisos oficiales de la Capitanía de Puerto. Se actualiza sola cada 5 minutos.") \
            .classes("piz-sub text-center w-full")

    ui.timer(30, immediate=False, callback=lambda: reloj.set_text(zarpes.ahora_local().strftime("%H:%M")))
    ui.timer(300, ui.navigate.reload, immediate=False)

    await ui.context.client.connected()
    p = await clima.obtener()
    caja_mar.clear()
    with caja_mar:
        ui.html("<h2>El mar hoy</h2>")
        d = p.dias[0] if p.dias else None
        if d:
            estado = d.estado_mar
            texto = {"verde": "Mar tranquilo", "amarillo": "Mar regular", "rojo": "Mar malo",
                     "gris": "Sin dato de oleaje"}[estado]
            with ui.row().classes("items-center gap-3 no-wrap"):
                ui.element("div").style(f"width:38px;height:38px;border-radius:50%;background:{COLORES[estado]}")
                ui.label(texto).classes("text-3xl font-extrabold")
            partes = []
            if d.ola_m is not None:
                partes.append(f"ola {dec(d.ola_m)} m")
            if d.viento_kn is not None:
                partes.append(f"viento {d.viento_kn:.0f} nudos")
            if p.temp_actual is not None:
                partes.append(f"{p.temp_actual:.0f}°")
            ui.label(" · ".join(partes)).classes("text-xl")
            ui.label(f"Fuente: {p.fuente}").classes("piz-sub")
