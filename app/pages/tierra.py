"""Trabajo en tierra: encarnado, fileteo, venta y limpieza.

Responde a «en ningún papel aparece cuánto aportamos»: cada registro se
valoriza en pesos con una tarifa referencial que define el sindicato.
"""
from datetime import date, timedelta

from nicegui import app, ui
from sqlmodel import select

from app import analytics, config
from app.db import sesion
from app.models import Calidad, Embarcacion, PersonaTierra, Rol, TipoTrabajo, TrabajoTierra
from app.ui_comun import kpi, marco, rol_actual, sin_permiso
from app.validation import validar_trabajo_tierra

ICONOS = {TipoTrabajo.ENCARNADO: "🪝", TipoTrabajo.FILETEO: "🔪", TipoTrabajo.VENTA: "🛒",
          TipoTrabajo.LIMPIEZA: "🧊"}


@ui.page("/tierra")
def tierra():
    if r := sin_permiso([Rol.REGISTRADORA, Rol.SINDICATO]):
        return r
    with sesion() as s:
        personas = {p.id: p.nombre for p in s.exec(select(PersonaTierra).order_by(PersonaTierra.nombre)).all()}
        rol_de = {p.id: p.rol_principal.value for p in s.exec(select(PersonaTierra)).all()}
        botes = {0: "Para la caleta (general)",
                 **{b.id: b.nombre for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}}

    estado = {"persona_id": None, "tipo": TipoTrabajo.ENCARNADO.value, "cantidad": None, "horas": None,
              "fecha": date.today().isoformat(), "embarcacion_id": 0}

    with marco("Trabajo en tierra"):
        resumen = ui.row().classes("w-full")
        with ui.column().classes("tarjeta"):
            def al_elegir_persona(e):
                if e.value in rol_de:
                    estado["tipo"] = rol_de[e.value]
                    tipo_toggle.update()
                    actualizar_unidad()
            ui.select(personas, label="Persona", with_input=True, on_change=al_elegir_persona) \
                .bind_value(estado, "persona_id").classes("w-full")
            tipo_toggle = ui.toggle({t.value: f"{ICONOS[t]} {t.value.capitalize()}" for t in TipoTrabajo}) \
                .props("no-caps toggle-color=secondary").bind_value(estado, "tipo").classes("flex-wrap")
            with ui.row().classes("w-full gap-2 no-wrap"):
                cantidad = ui.number("Cantidad", min=0).props("inputmode=decimal") \
                    .bind_value(estado, "cantidad").classes("w-1/2")
                ui.number("Horas", min=0, max=24, step=0.5).props("inputmode=decimal") \
                    .bind_value(estado, "horas").classes("w-1/2")
            valor = ui.label("").classes("text-base text-secondary")
            ui.input("Fecha").props("type=date").bind_value(estado, "fecha").classes("w-full")
            ui.select(botes, label="¿Para qué embarcación?", with_input=True) \
                .bind_value(estado, "embarcacion_id").classes("w-full")

            def actualizar_unidad():
                unidad, tarifa = config.TARIFA_TIERRA[TipoTrabajo(estado["tipo"])]
                cantidad.props(f'label="Cantidad ({unidad})"')
                if estado["tipo"] in (TipoTrabajo.VENTA.value, TipoTrabajo.LIMPIEZA.value):
                    cantidad.props(f'label="Horas de {estado["tipo"]}"')
                if estado["cantidad"]:
                    valor.text = f"Este trabajo vale aprox. {analytics.clp(estado['cantidad'] * tarifa)} " \
                                 f"(tarifa referencial {analytics.clp(tarifa)} por {unidad[:-1] if unidad.endswith('s') else unidad})"
                else:
                    valor.text = ""
            cantidad.on_value_change(lambda _: actualizar_unidad())
            tipo_toggle.on_value_change(lambda _: actualizar_unidad())
            actualizar_unidad()

        def guardar():
            if not estado["persona_id"]:
                ui.notify("Elige a la persona", type="warning")
                return
            try:
                f = date.fromisoformat(estado["fecha"])
            except (TypeError, ValueError):
                ui.notify("Fecha no válida", type="warning")
                return
            res = validar_trabajo_tierra(fecha=f, cantidad=estado["cantidad"], horas=estado["horas"])
            if res.calidad == Calidad.ERROR:
                ui.notify(res.texto, type="negative", multi_line=True)
                return
            with sesion() as s:
                s.add(TrabajoTierra(fecha=f, persona_id=estado["persona_id"], tipo=TipoTrabajo(estado["tipo"]),
                                    cantidad=estado["cantidad"], horas=estado["horas"],
                                    embarcacion_id=estado["embarcacion_id"] or None, calidad=res.calidad,
                                    notas_calidad=res.texto, registrado_por=rol_actual() or ""))
                s.commit()
            ui.notify(f"✅ Guardado: {personas[estado['persona_id']]}"
                      + (f" ({res.texto})" if res.motivos else ""), type="positive")
            estado.update(persona_id=None, cantidad=None, horas=None)
            pintar_resumen()

        ui.button("💾 Guardar", on_click=guardar).classes("w-full").props("size=lg")

        def pintar_resumen():
            resumen.clear()
            hoy = date.today()
            with sesion() as s:
                df = analytics.tierra_df(s, desde=hoy - timedelta(days=30), hasta=hoy)
            with resumen:
                with ui.grid(columns=3).classes("w-full gap-2"):
                    kpi(f"{df['persona_id'].nunique() if not df.empty else 0}", "personas (30 días)")
                    kpi(f"{df['horas'].sum():,.0f}".replace(",", ".") if not df.empty else "0", "horas (30 días)")
                    kpi(analytics.clp_corto(df["valor"].sum()) if not df.empty else "$0", "valor del trabajo")
        pintar_resumen()
