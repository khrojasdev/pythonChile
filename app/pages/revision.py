"""Revisión de datos (directiva): aprobar, corregir, rechazar o deshacer, uno a uno o varios a la vez."""
from nicegui import ui
from sqlmodel import func, select

from app import revision
from app.analytics import clp, dec
from app.db import sesion
from app.ilustraciones import especie_svg
from app.models import Calidad, Desembarque, Embarcacion, Especie, Rol
from app.ui_comun import BOYA, COLORES, kpi, marco, quien, sin_permiso, vacio

PASO = 12
PESTANAS = {
    "advertencia": ("Por revisar", "Se usan en los cálculos, pero alguien debe confirmarlos."),
    "error": ("Con error", "No se usan en ningún cálculo hasta que se corrijan."),
    "historial": ("Ya revisados", "Lo aprobado, corregido o rechazado. Se puede deshacer."),
}


def _contar(s):
    filas = s.exec(select(Desembarque.calidad, func.count()).group_by(Desembarque.calidad)).all()
    c = {(k.value if hasattr(k, "value") else k): n for k, n in filas}
    c["historial"] = s.exec(select(func.count()).select_from(Desembarque)
                            .where(Desembarque.revisado_por != "")).one()
    return c


def _registros(pestana: str, limite: int, bote: int | None):
    with sesion() as s:
        q = select(Desembarque)
        if pestana == "historial":
            q = q.where(Desembarque.revisado_por != "").order_by(Desembarque.revisado_en.desc())
        else:
            q = q.where(Desembarque.calidad == Calidad(pestana)).order_by(Desembarque.fecha.desc())
        if bote:
            q = q.where(Desembarque.embarcacion_id == bote)
        filas = s.exec(q.limit(limite + 1)).all()
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
        esp = {e.id: e.nombre for e in s.exec(select(Especie)).all()}
        return [dict(id=d.id, fecha=d.fecha, bote=botes.get(d.embarcacion_id, "?"), especie=esp[d.especie_id],
                     kg=d.kg, precio=d.precio_kg, origen=d.origen.value, motivos=d.notas_calidad,
                     calidad=d.calidad.value, revisado_por=d.revisado_por, registrado_por=d.registrado_por)
                for d in filas[:limite]], len(filas) > limite


@ui.page("/revision")
def pagina_revision():
    if r := sin_permiso([Rol.SINDICATO]):
        return r
    with sesion() as s:
        botes = {0: "Todas las embarcaciones", **{b.id: b.nombre for b in
                                                  s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}}
    estado = {"pestana": "advertencia", "limite": PASO, "bote": 0, "sel": set()}

    with marco("Revisión de datos", "/revision",
               "Nada se borra ni se corrige a escondidas: cada decisión queda registrada con quién la tomó."):
        contadores = ui.row().classes("w-full")
        with ui.row().classes("w-full items-center gap-3 flex-wrap"):
            pestanas = ui.toggle({k: v[0] for k, v in PESTANAS.items()}, value="advertencia") \
                .props("unelevated toggle-color=primary color=white text-color=primary spread") \
                .classes("flex-1 border rounded-lg")
            ui.select(botes, value=0, with_input=True, label="Embarcación",
                      on_change=lambda e: (estado.update(bote=e.value, limite=PASO), refrescar())) \
                .classes("w-64")
        explicacion = ui.label("").classes("tenue")
        barra = ui.row().classes("tarjeta items-center gap-2 no-wrap sticky top-16 z-10 flex-wrap") \
            .style(f"border-left:6px solid {BOYA}")
        lista = ui.column().classes("w-full gap-3")
        mas = ui.button("Ver más registros", icon="expand_more",
                        on_click=lambda: (estado.update(limite=estado["limite"] + PASO), refrescar())) \
            .props("flat").classes("w-full")

    # ---------------------------------------------------------------- acciones
    def ejecutar(fn, *args, ok: str):
        try:
            with sesion() as s:
                fn(s, *args)
        except revision.RevisionError as e:
            ui.notify(str(e), type="warning")
            return False
        if ok:
            ui.notify(ok, type="positive")
        return True

    async def accion_corregir(f):
        with ui.dialog() as dlg, ui.card().classes("w-[420px] max-w-full gap-3"):
            ui.html(f"<h2>Corregir: {f['especie']}, {f['bote']}</h2>")
            ui.label(f["motivos"]).classes("text-sm")
            kg = ui.number("Kilos", value=f["kg"], min=0).props("inputmode=decimal").classes("w-full")
            precio = ui.number("Precio $/kg", value=f["precio"], min=0).props("inputmode=numeric").classes("w-full")
            ui.label("Al guardar, el registro queda aprobado con los valores nuevos.").classes("tenue")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancelar", on_click=lambda: dlg.submit(None)).props("flat")
                ui.button("Guardar corrección", icon="save",
                          on_click=lambda: dlg.submit((kg.value, precio.value))).props("unelevated")
        datos = await dlg
        if datos is None:
            return
        with sesion() as s:
            _, motivo = revision.corregir(s, f["id"], quien(), datos[0], datos[1])
        if motivo:
            ui.notify(f"No se guardó: {motivo}", type="negative", multi_line=True)
        else:
            ui.notify("Corrección guardada y aprobada", type="positive")
            refrescar()

    async def accion_rechazar(ids: list[int]):
        with ui.dialog() as dlg, ui.card().classes("w-[420px] max-w-full gap-3"):
            ui.html(f"<h2>Rechazar {len(ids)} registro{'s' if len(ids) > 1 else ''}</h2>")
            ui.label("Saldrán de todos los cálculos. Podrás deshacerlo desde «Ya revisados».")
            motivo = ui.input("Motivo (opcional)", placeholder="Ej: dato duplicado del cuaderno").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancelar", on_click=lambda: dlg.submit(None)).props("flat")
                ui.button("Rechazar", icon="block", on_click=lambda: dlg.submit(motivo.value or "")) \
                    .props("unelevated color=negative")
        m = await dlg
        if m is None:
            return
        for i in ids:
            ejecutar(revision.rechazar, i, quien(), m, ok="")
        ui.notify(f"{len(ids)} rechazado{'s' if len(ids) > 1 else ''}", type="positive")
        estado["sel"].clear()
        refrescar()

    async def aprobar_varios():
        ids = list(estado["sel"])
        with ui.dialog() as dlg, ui.card().classes("gap-3"):
            ui.html(f"<h2>Aprobar {len(ids)} registros</h2>")
            ui.label("Confirmas que los valores son correctos tal como están.")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancelar", on_click=lambda: dlg.submit(False)).props("flat")
                ui.button("Aprobar", icon="check", on_click=lambda: dlg.submit(True)).props("unelevated color=positive")
        if not await dlg:
            return
        n = 0
        with sesion() as s:
            for i in ids:
                try:
                    revision.aprobar(s, i, quien())
                    n += 1
                except revision.RevisionError:
                    pass
        ui.notify(f"{n} registros aprobados", type="positive")
        estado["sel"].clear()
        refrescar()

    # ---------------------------------------------------------------- pintar
    def pintar_barra():
        barra.clear()
        n = len(estado["sel"])
        barra.set_visibility(estado["pestana"] != "historial")
        with barra:
            ui.label(f"{n} seleccionado{'s' if n != 1 else ''}" if n else
                     "Marca varios para decidir de una vez").classes("font-bold flex-1")
            if estado["pestana"] == "advertencia":
                ui.button("Aprobar", icon="check", on_click=aprobar_varios) \
                    .props(f"unelevated color=positive {'disable' if not n else ''}")
            ui.button("Rechazar", icon="block", on_click=lambda: accion_rechazar(list(estado["sel"]))) \
                .props(f"outline color=negative {'disable' if not n else ''}")
            if n:
                ui.button("Quitar selección", on_click=lambda: (estado["sel"].clear(), refrescar())).props("flat")

    def tarjeta(f):
        color = {"advertencia": COLORES["amarillo"], "error": COLORES["rojo"], "ok": COLORES["verde"],
                 "rechazado": COLORES["gris"]}[f["calidad"]]
        with ui.column().classes("tarjeta gap-2").style(f"border-left:6px solid {color}").mark(f"reg-{f['id']}"):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                if estado["pestana"] != "historial":
                    ui.checkbox(value=f["id"] in estado["sel"],
                                on_change=lambda e, i=f["id"]: (estado["sel"].add(i) if e.value
                                                                else estado["sel"].discard(i), pintar_barra())) \
                        .props(f'aria-label="Seleccionar registro {f["id"]}"')
                ui.html(especie_svg(f["especie"], 46))
                with ui.column().classes("gap-0 flex-1 min-w-0"):
                    ui.label(f"{f['especie']}, {f['bote']}").classes("font-bold text-lg")
                    ui.label(f"{f['fecha']:%d-%m-%Y} · {'—' if f['kg'] is None else dec(f['kg'])} kg · "
                             f"{clp(f['precio'])}/kg · {f['origen']}").classes("text-sm")
            ui.label((f["motivos"] or "Sin observaciones").replace(" || Antes: ", ". Motivo original: ")).classes("text-sm")
            with ui.row().classes("w-full justify-end gap-1"):
                if estado["pestana"] == "historial":
                    ui.label(f"Estado: {f['calidad']}").classes("tenue mr-auto self-center")
                    ui.button("Deshacer", icon="undo",
                              on_click=lambda i=f["id"]: ejecutar(revision.deshacer, i, ok="Revisión deshecha")
                              and refrescar()).props("flat")
                    return
                if f["calidad"] == "advertencia":
                    ui.button("Aprobar", icon="check",
                              on_click=lambda i=f["id"]: ejecutar(revision.aprobar, i, quien(), ok="Aprobado")
                              and refrescar()).props("unelevated color=positive").mark(f"aprobar-{f['id']}")
                ui.button("Corregir", icon="edit", on_click=lambda f=f: accion_corregir(f)).props("outline") \
                    .mark(f"corregir-{f['id']}")
                ui.button("Rechazar", icon="block", on_click=lambda i=f["id"]: accion_rechazar([i])) \
                    .props("flat color=negative").mark(f"rechazar-{f['id']}")

    def refrescar():
        with sesion() as s:
            c = _contar(s)
        contadores.clear()
        with contadores, ui.element("div").classes("rejilla"):
            kpi(f"{c.get('advertencia', 0):,}".replace(",", "."), "por revisar", "pending", COLORES["amarillo"])
            kpi(f"{c.get('error', 0):,}".replace(",", "."), "con error", "error", COLORES["rojo"])
            kpi(f"{c.get('historial', 0):,}".replace(",", "."), "ya revisados", "task_alt", COLORES["verde"])
        explicacion.text = PESTANAS[estado["pestana"]][1]
        filas, hay_mas = _registros(estado["pestana"], estado["limite"], estado["bote"] or None)
        estado["sel"] &= {f["id"] for f in filas}
        lista.clear()
        with lista:
            if not filas:
                vacio("No hay registros en esta categoría.", "task_alt")
            for f in filas:
                tarjeta(f)
        mas.set_visibility(hay_mas)
        pintar_barra()

    pestanas.on_value_change(lambda e: (estado.update(pestana=e.value, limite=PASO), estado["sel"].clear(),
                                        refrescar()))
    refrescar()
