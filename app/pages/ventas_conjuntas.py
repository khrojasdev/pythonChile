"""Venta conjunta: los botes juntan kilos de una especie para negociar mejor."""
from __future__ import annotations

from nicegui import ui
from sqlmodel import select

from app import lotes
from app.analytics import clp, dec
from app.db import sesion
from app.ilustraciones import especie_svg
from app.models import Comprador, Embarcacion, Especie, EstadoLote, Rol, TipoComprador
from app.ui_comun import BOYA, COLORES, MAR, bote_actual, marco, quien, rol_actual, sin_permiso, vacio


def tarjeta_lotes_abiertos() -> None:
    """Para los paneles: ventas conjuntas abiertas hoy."""
    with sesion() as s:
        abiertos = lotes.lotes(s, EstadoLote.ABIERTO, limite=3)
    if not abiertos:
        return
    with ui.row().classes("tarjeta items-center justify-between no-wrap gap-3").style(f"border-left:8px solid {BOYA}"):
        with ui.column().classes("gap-0"):
            ui.label(f"Venta conjunta abierta: {', '.join(r.especie.lower() for r in abiertos)}").classes("grande")
            r = abiertos[0]
            ui.label(f"{r.especie}: {dec(r.kg_total, 0)} kg de {r.botes} botes, mínimo {clp(r.lote.precio_minimo)}/kg"
                     ).classes("tenue")
        ui.button("Ver", on_click=lambda: ui.navigate.to("/ventas-conjuntas")).props("unelevated color=accent text-color=dark")


@ui.page("/ventas-conjuntas")
def ventas_conjuntas():
    if r := sin_permiso([Rol.PESCADOR, Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    es_pescador = rol_actual() == Rol.PESCADOR.value
    mi_bote = bote_actual() if es_pescador else None
    with sesion() as s:
        especies = {e.id: e.nombre for e in s.exec(select(Especie).order_by(Especie.id)).all()}
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}
        compradores = {c.id: f"{c.nombre} ({c.tipo.value})" for c in s.exec(select(Comprador)).all()
                       if c.tipo != TipoComprador.INTERMEDIARIO}

    with marco("Venta conjunta", "/ventas-conjuntas",
               "Un bote solo vende al precio que le ponen. Juntos, los botes ofrecen volumen a pescaderías y "
               "restaurantes, con un precio mínimo acordado. El pago se reparte según los kilos de cada uno."):
        abiertos = ui.column().classes("w-full gap-3")
        with ui.expansion("Proponer una venta conjunta", icon="add").classes("tarjeta w-full").mark("proponer-lote"):
            nuevo = {"especie": None, "precio": None, "nota": ""}
            ui.select(especies, label="Especie").bind_value(nuevo, "especie").classes("w-full").mark("lote-especie")
            ui.number("Precio mínimo $/kg (bajo esto no se vende)", min=0, step=50).props("inputmode=numeric") \
                .bind_value(nuevo, "precio").classes("w-full").mark("lote-minimo")
            ui.input("Nota (ej.: la pescadería pidió 300 kg)").bind_value(nuevo, "nota").classes("w-full")
            ui.button("Abrir venta conjunta", icon="groups", on_click=lambda: proponer(nuevo)).props("unelevated") \
                .mark("abrir-lote")
        ui.html("<h2>Ventas cerradas</h2>").classes("mt-2")
        cerrados = ui.column().classes("w-full gap-3")

    def proponer(nuevo):
        try:
            with sesion() as s:
                lt = lotes.crear_lote(s, nuevo["especie"], int(nuevo["precio"] or 0), quien=quien(), nota=nuevo["nota"])
            ui.notify(f"Venta conjunta #{lt.id} abierta. Ahora los botes pueden sumarse.", type="positive")
            nuevo.update(especie=None, precio=None, nota="")
        except ValueError as e:
            ui.notify(str(e), type="warning")
        pintar()

    def sumar(lote_id, bote, kg):
        if not bote:
            ui.notify("Elige la embarcación", type="warning")
            return
        try:
            with sesion() as s:
                lotes.sumarse(s, lote_id, bote, kg)
            ui.notify(f"{botes[bote]} suma {dec(kg, 0)} kg", type="positive")
        except (ValueError, TypeError) as e:
            ui.notify(str(e) if isinstance(e, ValueError) else "Escribe los kilos", type="warning")
        pintar()

    def retirar(lote_id, bote):
        with sesion() as s:
            lotes.retirarse(s, lote_id, bote)
        ui.notify("Saliste de la venta conjunta", type="info")
        pintar()

    async def cerrar(lote_id, form):
        try:
            with sesion() as s:
                r = lotes.cerrar_venta(s, lote_id, form["comprador"], int(form["precio"] or 0), quien())
            ui.notify(f"Venta cerrada: {clp(r.total_venta)} repartidos entre {r.botes} botes. "
                      "El precio quedó anotado en el desembarque de cada uno.", type="positive", multi_line=True)
        except ValueError as e:
            ui.notify(str(e), type="warning", multi_line=True)
        pintar()

    def cancelar(lote_id):
        with sesion() as s:
            lotes.cancelar(s, lote_id, quien())
        ui.notify("Venta conjunta cancelada", type="info")
        pintar()

    def tabla_reparto(r: lotes.ResumenLote):
        filas = [{"bote": a.bote, "kg": dec(a.kg, 0), "pct": f"{a.porcentaje:.0f} %",
                  "monto": clp(a.monto)} for a in r.aportes
                 if not es_pescador or a.embarcacion_id == mi_bote]
        if es_pescador and not filas:
            return
        ui.table(columns=[{"name": "bote", "label": "Embarcación", "field": "bote", "align": "left"},
                          {"name": "kg", "label": "Kilos", "field": "kg"},
                          {"name": "pct", "label": "Parte", "field": "pct"},
                          {"name": "monto", "label": "Le toca" if r.lote.precio_venta else "Estimado al mínimo",
                           "field": "monto"}],
                 rows=filas).props("flat dense").classes("w-full")

    def pintar():
        with sesion() as s:
            ab = lotes.lotes(s, EstadoLote.ABIERTO)
            ce = [x for x in lotes.lotes(s, limite=12) if x.lote.estado != EstadoLote.ABIERTO]
        abiertos.clear()
        with abiertos:
            if not ab:
                vacio("No hay ventas conjuntas abiertas. Propón una abajo.", "groups")
            for r in ab:
                lt = r.lote
                with ui.column().classes("tarjeta gap-3").style(f"border-top:6px solid {BOYA}").mark(f"lote-{lt.id}"):
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        ui.html(especie_svg(r.especie, 54))
                        with ui.column().classes("gap-0"):
                            ui.label(f"{r.especie} · venta #{lt.id}").classes("grande")
                            ui.label(f"Abierta el {lt.fecha:%d-%m} por {lt.creado_por or 'la caleta'}"
                                     + (f" · {lt.nota}" if lt.nota else "")).classes("text-sm tenue")
                    with ui.row().classes("gap-2 w-full"):
                        for valor, texto in [(f"{dec(r.kg_total, 0)} kg", "juntos"), (str(r.botes), "botes"),
                                             (clp(lt.precio_minimo), "mínimo por kilo")]:
                            with ui.column().classes("tarjeta-plana gap-0 flex-1").style("min-width:96px"):
                                ui.label(valor).classes("titulo text-2xl font-extrabold no-wrap") \
                                    .style("color:#0B3C5D")
                                ui.label(texto).classes("kpi-label")
                    if r.ganancia_vs_intermediario is not None:
                        g = r.ganancia_vs_intermediario
                        ui.label(f"Al precio mínimo, la caleta recibe {clp(abs(g))} "
                                 f"{'más' if g >= 0 else 'menos'} que vendiendo cada uno al intermediario "
                                 f"(mediana del mes: {clp(r.precio_intermediario)}/kg).") \
                            .classes("font-bold").style(f"color:{COLORES['verde'] if g >= 0 else COLORES['rojo']}")
                    tabla_reparto(r)

                    # sumarse
                    with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                        ya = next((a for a in r.aportes if a.embarcacion_id == mi_bote), None) if es_pescador else None
                        f = {"bote": mi_bote, "kg": ya.kg if ya else None}
                        if not es_pescador:
                            ui.select(botes, label="Embarcación", with_input=True).bind_value(f, "bote") \
                                .classes("flex-1").style("min-width:180px").mark(f"lote-bote-{lt.id}")
                        ui.number("Kilos que aporto" if es_pescador else "Kilos", min=0).props("inputmode=decimal") \
                            .bind_value(f, "kg").classes("flex-1").style("min-width:140px").mark(f"lote-kg-{lt.id}")
                        ui.button("Actualizar mis kilos" if ya else "Sumarme" if es_pescador else "Sumar bote",
                                  icon="add", on_click=lambda i=lt.id, f=f: sumar(i, f["bote"], f["kg"])) \
                            .props("unelevated").mark(f"sumar-{lt.id}")
                        if ya:
                            ui.button("Salirme", on_click=lambda i=lt.id: retirar(i, mi_bote)).props("flat color=negative")

                    # cerrar venta (registradora / directiva)
                    if not es_pescador:
                        with ui.row().classes("tarjeta-plana w-full gap-2 items-end flex-wrap"):
                            cf = {"comprador": None, "precio": lt.precio_minimo}
                            ui.select(compradores, label="¿A quién se vendió?").bind_value(cf, "comprador") \
                                .classes("flex-1").style("min-width:200px").mark(f"lote-comprador-{lt.id}")
                            ui.number("Precio acordado $/kg", min=0, step=50).bind_value(cf, "precio") \
                                .classes("flex-1").style("min-width:140px").mark(f"lote-precio-{lt.id}")
                            ui.button("Cerrar venta y repartir", icon="handshake",
                                      on_click=lambda i=lt.id, cf=cf: cerrar(i, cf)).props("unelevated color=positive") \
                                .mark(f"cerrar-{lt.id}")
                            ui.button("Cancelar", on_click=lambda i=lt.id: cancelar(i)).props("flat color=negative")
        cerrados.clear()
        with cerrados:
            if not ce:
                ui.label("Aún no hay ventas cerradas.").classes("tenue")
            for r in ce:
                lt = r.lote
                vendido = lt.estado == EstadoLote.VENDIDO
                with ui.column().classes("tarjeta gap-2").style(
                        f"border-left:6px solid {COLORES['verde'] if vendido else COLORES['gris']}"):
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        ui.html(especie_svg(r.especie, 40))
                        with ui.column().classes("gap-0"):
                            if vendido:
                                ui.label(f"{r.especie} · {dec(r.kg_total, 0)} kg a {clp(lt.precio_venta)}/kg = "
                                         f"{clp(r.total_venta)}").classes("font-bold text-lg")
                                ui.label(f"{lt.fecha:%d-%m-%Y} · {r.comprador} · {r.botes} botes").classes("text-sm")
                            else:
                                ui.label(f"{r.especie} · venta #{lt.id} cancelada").classes("font-bold")
                    if vendido and r.ganancia_vs_intermediario is not None:
                        g = r.ganancia_vs_intermediario
                        ui.label(f"{'+' if g >= 0 else '−'}{clp(abs(g))} frente a vender al intermediario") \
                            .classes("font-bold").style(f"color:{COLORES['verde'] if g >= 0 else COLORES['rojo']}")
                    if vendido:
                        tabla_reparto(r)

    pintar()
