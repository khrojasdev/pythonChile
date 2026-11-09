"""Registro de desembarque: se hace EN TIERRA, al llegar a la caleta.

Pensado para manos mojadas y poco tiempo: botones grandes, especies con íconos,
pocos campos obligatorios (embarcación, especie, kilos). El precio y el comprador
se pueden completar después si la venta aún no se cierra.
"""
from datetime import date, timedelta

from nicegui import app, ui
from sqlmodel import select

from app import analytics, config, dictado
from app.db import sesion
from app.models import (Calidad, Comprador, Desembarque, Embarcacion, Especie, Origen, Rol)
from app.ui_comun import bote_actual, marco, rol_actual, selector_especies, sin_permiso, tarjeta_veredicto
from app.validation import validar_desembarque


def _linea_vacia():
    return {"especie_id": None, "kg": None, "precio": None, "comprador_id": 0, "origen": Origen.PESADO.value}


@ui.page("/registro")
def registro():
    if r := sin_permiso([Rol.PESCADOR, Rol.REGISTRADORA]):
        return r
    with sesion() as s:
        especies = s.exec(select(Especie).order_by(Especie.id)).all()
        compradores = {c.id: f"{c.nombre} ({c.tipo.value})" for c in s.exec(select(Comprador)).all()}
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion).order_by(Embarcacion.nombre)).all()}

    estado = {"embarcacion_id": bote_actual(), "fecha": date.today().isoformat(),
              "litros": None, "carnada": None, "lineas": [_linea_vacia()]}

    with marco("Anotar desembarque", "/registro", "Se anota en tierra, al llegar. Solo especie y kilos son obligatorios; el precio se puede completar después."):
        _tarjeta_dictado(especies, estado, lambda: lineas.refresh())
        with ui.column().classes("tarjeta"):
            if rol_actual() == Rol.REGISTRADORA.value:
                ui.select(botes, label="Embarcación", with_input=True).bind_value(estado, "embarcacion_id") \
                    .classes("w-full")
            else:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("directions_boat", size="28px").style("color:#1D6A8A")
                    ui.label(botes.get(estado['embarcacion_id'], '')).classes("grande")
            with ui.row().classes("w-full gap-2 items-center"):
                ui.button("Hoy", on_click=lambda: fecha.set_value(date.today().isoformat())).props("outline")
                ui.button("Ayer", on_click=lambda: fecha.set_value((date.today() - timedelta(days=1)).isoformat())) \
                    .props("outline")
                fecha = ui.input("Fecha").props("type=date").bind_value(estado, "fecha").classes("flex-grow")
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.number("Litros de combustible", min=0).props("inputmode=decimal") \
                    .bind_value(estado, "litros").classes("w-1/2")
                ui.number("Carnada ($)", min=0, step=1000).props("inputmode=numeric") \
                    .bind_value(estado, "carnada").classes("w-1/2")

        @ui.refreshable
        def lineas():
            for i, ln in enumerate(estado["lineas"]):
                with ui.column().classes("tarjeta gap-2"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"Especie {i + 1}").classes("font-bold")
                        if len(estado["lineas"]) > 1:
                            ui.button(icon="delete", on_click=lambda i=i: (estado["lineas"].pop(i), lineas.refresh())) \
                                .props("flat round color=negative")
                    selector_especies(especies, ln["especie_id"],
                                      lambda e, ln=ln: ln.update(especie_id=e.value))
                    with ui.row().classes("w-full gap-2 no-wrap"):
                        ui.number("Kilos", min=0).props("inputmode=decimal").bind_value(ln, "kg").classes("w-1/2")
                        ui.number("Precio $/kg", min=0, step=10).props("inputmode=numeric") \
                            .bind_value(ln, "precio").classes("w-1/2")
                    ui.select({0: "Aún no vendo", **compradores}, label="¿A quién?") \
                        .bind_value(ln, "comprador_id").classes("w-full")
                    ui.toggle({Origen.PESADO.value: "Pesado en balanza", Origen.ESTIMADO.value: "Estimado a ojo"}) \
                        .props("no-caps spread").bind_value(ln, "origen").classes("w-full")

        lineas()
        ui.button("Agregar otra especie", icon="add", on_click=lambda: (estado["lineas"].append(_linea_vacia()), lineas.refresh())) \
            .props("outline").classes("w-full")

        resultado = ui.column().classes("w-full gap-3")

        async def guardar():
            await _guardar(estado, resultado, lineas)

        ui.button("Guardar desembarque", icon="save", on_click=guardar).classes("w-full text-lg") \
            .props("size=lg unelevated")


JS_DICTAR = """
(() => {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) { emitEvent('dictado_error', 'sin_soporte'); return; }
  const r = new R(); r.lang = 'es-CL'; r.interimResults = false; r.maxAlternatives = 1;
  r.onresult = (e) => emitEvent('dictado', e.results[0][0].transcript);
  r.onerror = (e) => emitEvent('dictado_error', e.error);
  r.onend = () => emitEvent('dictado_fin', '');
  r.start();
})();
"""


def _tarjeta_dictado(especies, estado, refrescar):
    """Dictar en vez de tocar: «merluza noventa kilos a mil trescientos»."""
    nombres = [e.nombre for e in especies]
    por_nombre = {e.nombre: e.id for e in especies}

    def aplicar(texto: str):
        frase.value = texto
        res = dictado.interpretar(texto, nombres)
        if not res.lineas and not res.litros:
            ui.notify("No reconocí ninguna especie. Prueba: «merluza noventa kilos a mil trescientos».",
                      type="warning", multi_line=True)
            return
        lineas = [ln for ln in estado["lineas"] if ln["especie_id"]]
        for ln in res.lineas:
            lineas.append({"especie_id": por_nombre[ln.especie], "kg": ln.kg, "precio": ln.precio,
                           "comprador_id": 0,
                           "origen": Origen.ESTIMADO.value if ln.estimado else Origen.PESADO.value})
        estado["lineas"] = lineas or [_linea_vacia()]
        if res.litros:
            estado["litros"] = res.litros
        refrescar()
        entendido.text = "Entendí: " + res.resumen() + ". Revisa y aprieta «Guardar desembarque»."
        entendido.set_visibility(True)

    def error(e):
        boton.props(remove="loading")
        motivo = {"sin_soporte": "Este navegador no permite dictar. Usa Chrome en Android, o escribe la frase.",
                  "not-allowed": "No hay permiso para el micrófono. Actívalo o escribe la frase.",
                  "no-speech": "No escuché nada. Inténtalo de nuevo, más cerca del celular."}
        ui.notify(motivo.get(e.args, f"No se pudo dictar ({e.args}). Escribe la frase."), type="warning",
                  multi_line=True)

    def escuchar():
        boton.props("loading")
        ui.run_javascript(JS_DICTAR)

    ui.on("dictado", lambda e: (boton.props(remove="loading"), aplicar(e.args)))
    ui.on("dictado_error", error)
    ui.on("dictado_fin", lambda: boton.props(remove="loading"))

    with ui.column().classes("tarjeta gap-2").style("border-left:6px solid #F2A900"):
        with ui.row().classes("items-center gap-3 no-wrap w-full"):
            boton = ui.button(icon="mic", on_click=escuchar).props("round unelevated size=lg color=accent "
                                                                  "text-color=dark").mark("dictar") \
                .props('aria-label="Dictar desembarque"')
            with ui.column().classes("gap-0"):
                ui.label("Dictar en vez de escribir").classes("font-bold text-lg")
                ui.label("Di, por ejemplo: «merluza noventa kilos a mil trescientos, y reineta cuarenta kilos»")\
                    .classes("text-sm tenue")
        with ui.row().classes("w-full gap-2 items-end no-wrap"):
            frase = ui.input("…o escribe la frase").classes("flex-1").mark("frase-dictado") \
                .on("keydown.enter", lambda: aplicar(frase.value or ""))
            ui.button("Entender", on_click=lambda: aplicar(frase.value or "")).props("outline").mark("entender")
        entendido = ui.label("").classes("font-bold").style("color:#2E7D4F").mark("entendido")
        entendido.set_visibility(False)


async def _guardar(estado, resultado, lineas):
    resultado.clear()
    if not estado["embarcacion_id"]:
        ui.notify("Falta la embarcación", type="warning")
        return
    try:
        fecha = date.fromisoformat(estado["fecha"])
    except (TypeError, ValueError):
        ui.notify("Fecha no válida", type="warning")
        return
    lineas_ok = [ln for ln in estado["lineas"] if ln["especie_id"]]
    if not lineas_ok:
        ui.notify("Elige al menos una especie", type="warning")
        return

    with sesion() as s:
        validaciones = []
        for k, ln in enumerate(lineas_ok):
            esp = s.get(Especie, ln["especie_id"])
            ref = analytics.precio_referencia(s, esp.id, fecha)
            duplicado = s.exec(select(Desembarque).where(
                Desembarque.fecha == fecha, Desembarque.embarcacion_id == estado["embarcacion_id"],
                Desembarque.especie_id == esp.id)).first() is not None
            res = validar_desembarque(fecha=fecha, especie=esp, kg=ln["kg"], precio_kg=ln["precio"],
                                      litros=estado["litros"] if k == 0 else None,
                                      referencia=ref.para_validacion(), es_duplicado=duplicado)
            validaciones.append((ln, esp, ref, res))

        errores = [(esp, res) for _, esp, _, res in validaciones if res.calidad == Calidad.ERROR]
        if errores:
            for esp, res in errores:
                ui.notify(f"{esp.nombre}: {res.texto}", type="negative", multi_line=True, timeout=8000)
            return

        advertencias = [(esp, res) for _, esp, _, res in validaciones if res.calidad == Calidad.ADVERTENCIA]
        if advertencias:
            with ui.dialog() as dlg, ui.card():
                ui.label("Revisa antes de guardar").classes("grande")
                for esp, res in advertencias:
                    ui.label(f"{esp.nombre}: {res.texto}")
                ui.label("Si está bien, se guarda igual y queda marcado para revisión.").classes("text-sm")
                with ui.row():
                    ui.button("Corregir", on_click=lambda: dlg.submit(False)).props("outline")
                    ui.button("Guardar igual", on_click=lambda: dlg.submit(True)).props("unelevated")
            if not await dlg:
                return

        quien = app.storage.user.get("bote_nombre") or rol_actual()
        for k, (ln, esp, ref, res) in enumerate(validaciones):
            s.add(Desembarque(
                fecha=fecha, embarcacion_id=estado["embarcacion_id"], especie_id=esp.id, kg=ln["kg"],
                precio_kg=int(ln["precio"]) if ln["precio"] else None, comprador_id=ln["comprador_id"] or None,
                litros_combustible=estado["litros"] if k == 0 else None,
                precio_litro=config.PRECIO_LITRO_DEFECTO if k == 0 and estado["litros"] else None,
                costo_carnada=int(estado["carnada"]) if k == 0 and estado["carnada"] else None,
                origen=Origen(ln["origen"]), calidad=res.calidad, notas_calidad=res.texto,
                registrado_por=quien))
        s.commit()

        # ---- retroalimentación inmediata: ¿fue buen precio?
        kg_total = sum(ln["kg"] or 0 for ln, *_ in validaciones)
        costo = (estado["litros"] or 0) * config.PRECIO_LITRO_DEFECTO + (estado["carnada"] or 0)
        piso = costo / kg_total if costo and kg_total else None
        with resultado:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle", size="30px").classes("text-positive")
                ui.label("Desembarque guardado").classes("grande text-positive")
            for ln, esp, ref, _ in validaciones:
                if ln["precio"]:
                    v = analytics.evaluar_oferta(ref, ln["precio"], piso)
                    tarjeta_veredicto(v.color, f"{esp.nombre} a {analytics.clp(ln['precio'])}: {v.titulo}",
                                      v.razones)
                else:
                    tarjeta_veredicto("gris", f"{esp.nombre}: precio pendiente",
                                      [f"Referencia del mes: entre {analytics.clp(ref.p25)} y {analytics.clp(ref.p75)}/kg."
                                       if ref.n else "Sin precios recientes de referencia."])
            if piso:
                ui.label(f"Con lo que gastaste hoy, cada kilo debe venderse sobre {analytics.clp(piso)}.") \
                    .classes("text-base")
    estado.update(lineas=[_linea_vacia()], litros=None, carnada=None)
    lineas.refresh()
    ui.run_javascript(f"document.getElementById('c{resultado.id}').scrollIntoView({{behavior:'smooth'}})")
