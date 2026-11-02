"""Avisos de la directiva (todos leen; la directiva publica) y pronóstico de clima y mar."""
from datetime import timezone

from nicegui import ui
from sqlmodel import select

from app.analytics import dec
from app.db import sesion
from app.models import Aviso, Rol
from app.servicios import clima
from app.ui_comun import BOYA, COLORES, MAR, marco, rol_actual, sin_permiso, vacio

TIPOS = {"info": ("Información", "#5FA8D3", "info"), "alerta": ("Alerta", COLORES["rojo"], "warning"),
         "reunion": ("Reunión", BOYA, "groups")}


@ui.page("/avisos")
def avisos():
    if r := sin_permiso(list(Rol)):
        return r
    es_directiva = rol_actual() == Rol.SINDICATO.value
    titulo = "Avisos a la caleta" if es_directiva else "Avisos"
    with marco(titulo, "/avisos", "Lo que la directiva comunica a todos los socios."):
        if es_directiva:
            with ui.column().classes("tarjeta gap-2"):
                ui.html("<h2>Publicar aviso</h2>")
                t = ui.input("Título").classes("w-full").mark("aviso-titulo")
                c = ui.textarea("Mensaje").classes("w-full").props("autogrow").mark("aviso-cuerpo")
                with ui.row().classes("items-center gap-3"):
                    tipo = ui.toggle({k: v[0] for k, v in TIPOS.items()}, value="info").props("unelevated")
                    fijar = ui.checkbox("Fijar arriba")
                    ui.button("Publicar", icon="campaign", on_click=lambda: publicar()).props("unelevated") \
                        .mark("aviso-publicar")
        lista = ui.column().classes("w-full gap-2")

    def publicar():
        if not (t.value or "").strip() or not (c.value or "").strip():
            ui.notify("Escribe título y mensaje", type="warning")
            return
        with sesion() as s:
            s.add(Aviso(titulo=t.value.strip(), cuerpo=c.value.strip(), tipo=tipo.value, fijado=fijar.value))
            s.commit()
        ui.notify("Aviso publicado", type="positive")
        t.value = c.value = ""
        pintar()

    def borrar(aid):
        with sesion() as s:
            s.delete(s.get(Aviso, aid))
            s.commit()
        ui.notify("Aviso retirado", type="positive")
        pintar()

    def pintar():
        with sesion() as s:
            filas = s.exec(select(Aviso).order_by(Aviso.fijado.desc(), Aviso.publicado_en.desc())).all()
        lista.clear()
        with lista:
            if not filas:
                vacio("No hay avisos publicados.", "campaign")
            for a in filas:
                nombre, color, icono = TIPOS.get(a.tipo, TIPOS["info"])
                fecha = a.publicado_en.replace(tzinfo=a.publicado_en.tzinfo or timezone.utc).astimezone()
                with ui.row().classes("tarjeta no-wrap gap-3 items-start").style(f"border-left:6px solid {color}"):
                    ui.icon(icono, size="28px").style(f"color:{color}")
                    with ui.column().classes("gap-0 flex-1"):
                        ui.label(a.titulo).classes("font-bold text-lg")
                        ui.label(a.cuerpo)
                        ui.label(f"{nombre} · {fecha:%d-%m-%Y %H:%M}" + (" · fijado" if a.fijado else "")) \
                            .classes("tenue text-sm")
                    if es_directiva:
                        ui.button(icon="delete", on_click=lambda i=a.id: borrar(i)).props(
                            'flat round color=negative aria-label="Retirar aviso"')
    pintar()


@ui.page("/clima")
async def pagina_clima():
    if r := sin_permiso(list(Rol)):
        return r
    with marco("Clima y mar", "/clima", "Pronóstico para la caleta. Antes de zarpar, revisa siempre el estado "
                                        "de puerto que informa la Capitanía."):
        cabecera = ui.label("Consultando pronóstico…").classes("tenue")
        zona = ui.column().classes("w-full gap-2")
        with zona:
            for _ in range(4):
                ui.skeleton().classes("w-full h-20")
        with ui.column().classes("tarjeta gap-1"):
            ui.html("<h2>Cómo leer el color</h2>")
            for c, txt in [("verde", "Ola bajo 1,8 m y viento bajo 25 nudos."),
                           ("amarillo", "Ola entre 1,8 y 2,5 m: salir con cuidado."),
                           ("rojo", "Ola sobre 2,5 m o viento sobre 25 nudos: no se recomienda salir.")]:
                with ui.row().classes("items-center gap-2"):
                    ui.element("div").style(f"width:14px;height:14px;border-radius:50%;background:{COLORES[c]}")
                    ui.label(txt)
    from nicegui import context
    await context.client.connected()
    p = await clima.obtener()
    cabecera.text = f"Fuente: {p.fuente}" + (f". {p.error}." if p.error else "")
    zona.clear()
    with zona:
        if not p.dias:
            vacio("No hay pronóstico disponible.", "cloud_off")
        for d in p.dias:
            with ui.row().classes("tarjeta items-center no-wrap gap-4 py-3") \
                    .style(f"border-left:8px solid {COLORES[d.estado_mar]}"):
                ui.icon(d.icono if d.codigo is not None else "waves", size="36px").style(f"color:{MAR}")
                with ui.column().classes("gap-0 w-32"):
                    ui.label(d.nombre).classes("font-bold text-lg")
                    if d.codigo is not None:
                        ui.label(d.descripcion).classes("text-sm")
                with ui.row().classes("gap-5 flex-1 flex-wrap"):
                    for valor, etiqueta in [
                            (f"{dec(d.ola_m)} m" if d.ola_m is not None else "—", "ola máx."),
                            (f"{d.viento_kn:.0f} kn" if d.viento_kn is not None else "—", "viento"),
                            (f"{d.racha_kn:.0f} kn" if d.racha_kn is not None else None, "rachas"),
                            (f"{d.tmax:.0f}° / {d.tmin:.0f}°" if d.tmax is not None else None, "temperatura"),
                            (f"{d.lluvia_pct:.0f}%" if d.lluvia_pct is not None else None, "lluvia")]:
                        if valor:
                            with ui.column().classes("gap-0"):
                                ui.label(valor).classes("font-bold text-lg")
                                ui.label(etiqueta).classes("text-xs tenue")
