"""Ventas por completar: desembarques con kilos pero sin precio (la venta se cerró después)."""
from datetime import date, timedelta

from nicegui import ui
from sqlmodel import select

from app import analytics
from app.analytics import clp, dec
from app.db import sesion
from app.ilustraciones import especie_svg
from app.models import Calidad, Comprador, Desembarque, Embarcacion, Especie, Rol
from app.ui_comun import bote_actual, marco, quien, rol_actual, sin_permiso, vacio
from app.validation import validar_desembarque

DIAS = 60


@ui.page("/pendientes")
def pendientes():
    if r := sin_permiso([Rol.PESCADOR, Rol.REGISTRADORA]):
        return r
    es_pescador = rol_actual() == Rol.PESCADOR.value
    with sesion() as s:
        compradores = {c.id: f"{c.nombre} ({c.tipo.value})" for c in s.exec(select(Comprador)).all()}
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
        especies = {e.id: e for e in s.exec(select(Especie)).all()}

    with marco("Ventas por completar", "/pendientes",
               "Capturas anotadas sin precio. Completa el precio cuando cierres la venta."):
        lista = ui.column().classes("w-full gap-3")

    def cargar():
        with sesion() as s:
            q = select(Desembarque).where(Desembarque.precio_kg == None, Desembarque.kg > 0,  # noqa: E711
                                          Desembarque.fecha >= date.today() - timedelta(days=DIAS),
                                          Desembarque.calidad.notin_([Calidad.ERROR, Calidad.RECHAZADO])) \
                .order_by(Desembarque.fecha.desc())
            if es_pescador:
                q = q.where(Desembarque.embarcacion_id == bote_actual())
            return s.exec(q.limit(40)).all()

    def guardar(id_, precio, comprador, fila):
        if not precio:
            ui.notify("Escribe el precio por kilo", type="warning")
            return
        with sesion() as s:
            d = s.get(Desembarque, id_)
            esp = especies[d.especie_id]
            ref = analytics.precio_referencia(s, esp.id, d.fecha)
            res = validar_desembarque(fecha=d.fecha, especie=esp, kg=d.kg, precio_kg=precio,
                                      litros=d.litros_combustible, referencia=ref.para_validacion())
            if res.calidad == Calidad.ERROR:
                ui.notify(res.texto, type="negative")
                return
            d.precio_kg, d.comprador_id = int(precio), comprador or None
            d.calidad, d.notas_calidad = res.calidad, res.texto
            d.registrado_por = d.registrado_por or quien()
            s.add(d)
            s.commit()
            v = analytics.evaluar_oferta(ref, precio)
        ui.notify(f"Precio guardado: {v.titulo.lower()} (mediana del mes {clp(ref.mediana)})",
                  type="positive" if v.color == "verde" else "info", multi_line=True)
        fila.delete()

    def pintar():
        lista.clear()
        filas = cargar()
        with lista:
            if not filas:
                vacio("No tienes ventas pendientes. Todo al día.", "task_alt")
                return
            ui.label(f"{len(filas)} venta{'s' if len(filas) > 1 else ''} sin precio en los últimos {DIAS} días") \
                .classes("font-bold")
            for d in filas:
                esp = especies[d.especie_id]
                with ui.column().classes("tarjeta gap-2") as fila:
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        ui.html(especie_svg(esp.nombre, 46))
                        with ui.column().classes("gap-0"):
                            titulo = esp.nombre if es_pescador else f"{esp.nombre}, {botes.get(d.embarcacion_id)}"
                            ui.label(titulo).classes("font-bold text-lg")
                            ui.label(f"{d.fecha:%d-%m-%Y} · {dec(d.kg)} kg").classes("text-sm")
                    with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                        precio = ui.number("Precio $/kg", min=0, step=10).props("inputmode=numeric") \
                            .classes("flex-1").mark(f"precio-{d.id}")
                        comp = ui.select({0: "Sin indicar", **compradores}, value=0, label="¿A quién?") \
                            .classes("flex-1")
                        ui.button("Guardar", icon="save",
                                  on_click=lambda i=d.id, p=precio, c=comp, f=fila: guardar(i, p.value, c.value, f)) \
                            .props("unelevated").mark(f"guardar-{d.id}")
    pintar()
