"""Revisar datos: registros dudosos, corrección y carga de cuadernos antiguos."""
from datetime import date

from nicegui import events, ui
from sqlmodel import select

from app import analytics, importar
from app.db import sesion
from app.models import Calidad, Desembarque, Embarcacion, Especie, Rol
from app.ui_comun import kpi, marco, rol_actual, sin_permiso
from app.validation import validar_desembarque


def _filas(filtro: str) -> list[dict]:
    with sesion() as s:
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
        esp = {e.id: e for e in s.exec(select(Especie)).all()}
        q = select(Desembarque).where(Desembarque.calidad == Calidad(filtro)) \
            .order_by(Desembarque.fecha.desc()).limit(300)
        return [dict(id=d.id, fecha=d.fecha.strftime("%d-%m-%y"), bote=botes.get(d.embarcacion_id, "?"),
                     especie=f"{esp[d.especie_id].icono} {esp[d.especie_id].nombre}",
                     kg=d.kg, precio=d.precio_kg, origen=d.origen.value, motivos=d.notas_calidad)
                for d in s.exec(q).all()]


@ui.page("/calidad")
def calidad():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    estado = {"filtro": Calidad.ADVERTENCIA.value, "limite": 15}

    with marco("Revisar datos"):
        resumen = ui.row().classes("w-full")

        def pintar_resumen():
            resumen.clear()
            with sesion() as s:
                c = analytics.resumen_calidad(s)
            with resumen, ui.grid(columns=3).classes("w-full gap-2"):
                kpi(f"{c['por_calidad'].get('ok', 0):,}".replace(",", "."), "✅ ok")
                kpi(f"{c['por_calidad'].get('advertencia', 0):,}".replace(",", "."), "⚠️ por revisar")
                kpi(f"{c['por_calidad'].get('error', 0):,}".replace(",", "."), "❌ con error")
        pintar_resumen()

        ui.label("Un dato dudoso no se borra ni se corrige a escondidas: se marca, alguien lo revisa y queda "
                 "anotado quién lo revisó. Los registros con error no se usan en ningún cálculo.") \
            .classes("text-sm text-gray-700")

        with ui.column().classes("tarjeta"):
            filtro = ui.toggle({Calidad.ADVERTENCIA.value: "⚠️ Por revisar", Calidad.ERROR.value: "❌ Con error"}) \
                .props("no-caps spread").bind_value(estado, "filtro").classes("w-full")
            lista = ui.column().classes("w-full gap-2")
            mas = ui.button("Ver más", on_click=lambda: (estado.update(limite=estado["limite"] + 15), refrescar())) \
                .props("flat no-caps").classes("w-full")

        def refrescar():
            filas = _filas(estado["filtro"])
            lista.clear()
            with lista:
                if not filas:
                    ui.label("No hay registros en esta categoría. 🎉")
                for fila in filas[:estado["limite"]]:
                    with ui.column().classes("w-full gap-0 p-3 rounded-lg").style("background:#F7F9FB"):
                        with ui.row().classes("w-full justify-between items-center no-wrap"):
                            ui.label(f"{fila['especie']} · {fila['bote']}").classes("font-bold")
                            ui.label(fila["fecha"]).classes("text-sm text-gray-600")
                        kg = "—" if fila["kg"] is None else analytics.dec(fila["kg"])
                        ui.label(f"{kg} kg · {analytics.clp(fila['precio'])}/kg · {fila['origen']}").classes("text-sm")
                        ui.label(fila["motivos"]).classes("text-sm")
                        ui.button("✏️ Revisar", on_click=lambda f=fila: corregir(f)) \
                            .props("flat dense no-caps").classes("self-end")
            mas.set_visibility(len(filas) > estado["limite"])
            pintar_resumen()

        async def corregir(fila):
            with ui.dialog() as dlg, ui.card().classes("w-full"):
                ui.label(f"{fila['bote']} · {fila['especie']} · {fila['fecha']}").classes("font-bold")
                ui.label(fila["motivos"]).classes("text-sm")
                kg = ui.number("Kilos", value=fila["kg"]).props("inputmode=decimal").classes("w-full")
                precio = ui.number("Precio $/kg", value=fila["precio"]).props("inputmode=numeric").classes("w-full")
                ui.label("Si el dato está bien, confirma sin cambiarlo.").classes("text-xs text-gray-600")
                with ui.row():
                    ui.button("Cancelar", on_click=lambda: dlg.submit(None)).props("outline")
                    ui.button("Confirmar revisión", on_click=lambda: dlg.submit((kg.value, precio.value)))
            datos = await dlg
            if datos is None:
                return
            with sesion() as s:
                d = s.get(Desembarque, fila["id"])
                d.kg, d.precio_kg = datos[0], int(datos[1]) if datos[1] else None
                res = validar_desembarque(fecha=d.fecha, especie=s.get(Especie, d.especie_id), kg=d.kg,
                                          precio_kg=d.precio_kg, litros=d.litros_combustible)
                d.calidad = res.calidad if res.calidad == Calidad.ERROR else Calidad.OK
                d.notas_calidad = (f"Revisado por {rol_actual()} el {date.today():%d-%m-%Y}. "
                                   f"Antes: {fila['motivos']}") if d.calidad == Calidad.OK else res.texto
                s.add(d)
                s.commit()
            ui.notify("✅ Revisado" if d.calidad == Calidad.OK else f"Sigue con error: {res.texto}",
                      type="positive" if d.calidad == Calidad.OK else "negative")
            refrescar()

        refrescar()
        filtro.on_value_change(lambda _: (estado.update(limite=15), refrescar()))

        # ---------------------------------------------------- importar cuaderno
        with ui.column().classes("tarjeta"):
            ui.label("📒 Digitalizar un cuaderno antiguo").classes("font-bold")
            ui.label("Transcribe el cuaderno en una planilla con las columnas de la plantilla y súbela. "
                     "Se revisa fila por fila antes de guardar.").classes("text-sm")
            ui.button("Descargar plantilla", icon="download",
                      on_click=lambda: ui.download.content(importar.PLANTILLA.encode("utf-8-sig"),
                                                           "plantilla_cuaderno.csv")).props("outline no-caps")
            reporte_zona = ui.column().classes("w-full")

            async def al_subir(e: events.UploadEventArguments):
                reporte_zona.clear()
                contenido = await e.file.read()
                with sesion() as s:
                    try:
                        rep = importar.revisar(s, importar.leer_csv(contenido))
                    except Exception as ex:  # archivo ilegible o columnas faltantes
                        with reporte_zona:
                            ui.label(f"❌ No se pudo leer el archivo: {ex}").classes("text-negative")
                        return
                buenas = sum(r["estado"] == "ok" for r in rep)
                dudosas = sum(r["estado"] == "advertencia" for r in rep)
                malas = sum(r["estado"] == "error" for r in rep)
                with reporte_zona:
                    ui.label(f"{len(rep)} filas: ✅ {buenas} ok · ⚠️ {dudosas} dudosas · ❌ {malas} con error")
                    ui.table(columns=[{"name": k, "label": k.capitalize(), "field": k, "align": "left"}
                                      for k in ("fila", "fecha", "embarcacion", "especie", "kg", "motivos")],
                             rows=[{k: v for k, v in r.items() if k != "datos"} for r in rep],
                             row_key="fila", pagination=6).classes("w-full").props("dense wrap-cells")

                    def confirmar():
                        with sesion() as s:
                            n = importar.guardar(s, rep)
                        ui.notify(f"✅ {n} filas guardadas. Las {malas} con error quedaron fuera.", type="positive")
                        reporte_zona.clear()
                        refrescar()
                    ui.button(f"Guardar {buenas + dudosas} filas (sin las con error)", on_click=confirmar) \
                        .classes("w-full").props(f"{'disable' if buenas + dudosas == 0 else ''}")

            ui.upload(on_upload=al_subir, auto_upload=True, label="Subir planilla CSV") \
                .props('accept=".csv" flat bordered').classes("w-full")
