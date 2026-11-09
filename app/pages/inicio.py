"""Inicio según el perfil: "Mi día" (pescador), "Jornada de hoy" (registradora), panel (directiva)."""
from datetime import date, timedelta

import pandas as pd
from nicegui import ui
from sqlmodel import func, select

from app import analytics
from app.analytics import clp, clp_corto, dec
from app.db import sesion
from app.models import Aviso, Calidad, Desembarque, Embarcacion, Especie, Rol
from app.servicios import clima
from app.pages.ventas_conjuntas import tarjeta_lotes_abiertos
from app.pages.zarpe import tarjeta_en_el_mar
from app.ui_comun import BOYA, COLORES, MAR, MARINO, bote_actual, kpi, marco, rol_actual, sin_permiso, \
    tarjeta_veredicto, vacio

PALETA = ["#0B3C5D", "#1D6A8A", "#5FA8D3", "#E4A951", "#C8402F", "#2F7D5B"]


def barras_apiladas(df, unidad: str) -> dict:
    return {
        "color": PALETA, "textStyle": {"fontFamily": "Atkinson Hyperlegible"},
        "grid": {"left": 64, "right": 10, "top": 16, "bottom": 64},
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 12}},
        "xAxis": {"type": "category", "data": [m[2:] for m in df.index]},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}" + unidad}},
        "series": [{"name": str(c).capitalize(), "type": "bar", "stack": "t", "data": df[c].round(0).tolist()}
                   for c in df.columns],
    }


def tarjeta_avisos(limite: int = 2) -> None:
    with sesion() as s:
        avisos = s.exec(select(Aviso).order_by(Aviso.fijado.desc(), Aviso.publicado_en.desc()).limit(limite)).all()
    if not avisos:
        return
    with ui.column().classes("tarjeta gap-2"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.html("<h2>Avisos de la directiva</h2>")
            ui.button("Ver todos", on_click=lambda: ui.navigate.to("/avisos")).props("flat")
        for a in avisos:
            color = {"alerta": COLORES["rojo"], "reunion": BOYA}.get(a.tipo, "#5FA8D3")
            with ui.column().classes("tarjeta-plana gap-0").style(f"border-left:5px solid {color}"):
                ui.label(a.titulo).classes("font-bold")
                ui.label(a.cuerpo).classes("text-sm")


async def tarjeta_clima_corta(contenedor) -> clima.Pronostico:
    p = await clima.obtener()
    contenedor.clear()
    with contenedor:
        with ui.row().classes("w-full items-center justify-between"):
            ui.html("<h2>Mar y tiempo</h2>")
            ui.button("Pronóstico completo", on_click=lambda: ui.navigate.to("/clima")).props("flat")
        with ui.row().classes("gap-2 w-full no-wrap"):
            for d in p.dias[:3]:
                with ui.column().classes("tarjeta-plana gap-0 flex-1").style(
                        f"border-top:5px solid {COLORES[d.estado_mar]}"):
                    ui.label(d.nombre).classes("font-bold")
                    if d.codigo is not None:
                        ui.label(d.descripcion).classes("text-sm")
                    ui.label(f"Ola {dec(d.ola_m)} m" if d.ola_m is not None else "Ola sin dato").classes("text-sm")
                    if d.viento_kn is not None:
                        ui.label(f"Viento {d.viento_kn:.0f} kn").classes("text-sm")
        ui.label(f"Fuente: {p.fuente}").classes("tenue text-xs")
    return p


@ui.page("/inicio")
async def inicio():
    rol = rol_actual()
    if rol is None:
        return sin_permiso([])
    if rol == Rol.PESCADOR.value:
        await _mi_dia()
    elif rol == Rol.REGISTRADORA.value:
        await _jornada()
    else:
        await _panel()


# ------------------------------------------------------------------ pescador
async def _mi_dia():
    bote = bote_actual()
    hoy = date.today()
    with sesion() as s:
        b = s.get(Embarcacion, bote)
        df = analytics.desembarques_df(s, desde=hoy - timedelta(days=60), embarcacion_id=bote)
        pendientes = int(((df["precio_kg"].isna()) & (df["kg"].fillna(0) > 0)).sum()) if not df.empty else 0
        especie_id = int(df["especie_id"].mode().iloc[0]) if not df.empty else 1
        especie = s.get(Especie, especie_id)
        ult = df.sort_values("fecha", ascending=False).head(5) if not df.empty else df
        m = analytics.mis_numeros(s, bote, dias=30)
    with marco(f"Hola, {b.patron.split()[0]}", "/inicio", f"{b.nombre} · resumen de tu día"):
        with ui.row().classes("fila-resp gap-2"):
            ui.button("Anotar desembarque", icon="add_circle", on_click=lambda: ui.navigate.to("/registro")) \
                .classes("flex-1").props("unelevated size=lg")
            ui.button("Aviso de zarpe", icon="sailing", on_click=lambda: ui.navigate.to("/zarpe")) \
                .classes("flex-1").props("unelevated size=lg color=secondary")
        tarjeta_lotes_abiertos()
        if pendientes:
            with ui.row().classes("tarjeta items-center justify-between no-wrap gap-3") \
                    .style(f"border-left:8px solid {BOYA}"):
                with ui.column().classes("gap-0"):
                    ui.label(f"Tienes {pendientes} venta{'s' if pendientes > 1 else ''} sin precio").classes("grande")
                    ui.label("Complétalas para que tus números sean exactos.").classes("tenue")
                ui.button("Completar", on_click=lambda: ui.navigate.to("/pendientes")).props("unelevated color=accent text-color=dark")
        semaforo = ui.column().classes("w-full")
        with semaforo:
            ui.skeleton().classes("w-full h-40")
        caja_clima = ui.column().classes("tarjeta gap-2")
        with caja_clima:
            ui.skeleton().classes("w-full h-24")
        if m.get("salidas"):
            with ui.element("div").classes("rejilla"):
                kpi(str(m["salidas"]), "salidas (30 días)", "sailing")
                kpi(clp_corto(m["ingreso"]), "vendido", "payments")
                kpi(f"{m['no_cubre']}/{m['evaluables']}", "no cubrieron costos", "trending_down",
                    COLORES["rojo"] if m["no_cubre"] else MARINO)
        with ui.column().classes("tarjeta gap-1"):
            ui.html("<h2>Tus últimos desembarques</h2>")
            if ult.empty:
                ui.label("Aún no anotas desembarques.").classes("tenue")
            for _, f in ult.iterrows():
                with ui.row().classes("w-full justify-between no-wrap py-1").style("border-bottom:1px solid #EEF3F6"):
                    ui.label(f"{f['fecha']:%d-%m} · {f['especie']}")
                    ui.label(f"{dec(f['kg'] or 0, 0)} kg · {clp(f['precio_kg']) if pd.notna(f['precio_kg']) else 'sin precio'}") \
                        .classes("font-bold")
        tarjeta_avisos()

    from nicegui import context
    await context.client.connected()
    p = await tarjeta_clima_corta(caja_clima)
    manana = p.dia(hoy + timedelta(days=1))
    with sesion() as s:
        sem = analytics.semaforo_salida(s, bote, especie.id, hoy + timedelta(days=1),
                                        mar=(manana.ola_m, manana.viento_kn) if manana else None,
                                        fuente_mar=p.fuente)
    semaforo.clear()
    with semaforo:
        tarjeta_veredicto(sem.color, f"Mañana con {especie.nombre.lower()}: {sem.titulo.lower()}", sem.razones)
        ui.button("Ver el detalle o elegir otra especie", on_click=lambda: ui.navigate.to("/salir")).props("flat")


# ------------------------------------------------------------------ registradora
async def _jornada():
    hoy = date.today()
    with sesion() as s:
        df = analytics.desembarques_df(s, desde=hoy - timedelta(days=1), incluir_errores=True)
        botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
        tierra = analytics.tierra_df(s, desde=hoy, hasta=hoy)
        pendientes = s.exec(select(func.count()).select_from(Desembarque).where(
            Desembarque.precio_kg == None, Desembarque.kg > 0,  # noqa: E711
            Desembarque.fecha >= hoy - timedelta(days=14),
            Desembarque.calidad.notin_([Calidad.ERROR, Calidad.RECHAZADO]))).one()
    df_hoy = df[df["fecha"] == pd.Timestamp(hoy)] if not df.empty else df
    df_ayer = df[df["fecha"] == pd.Timestamp(hoy - timedelta(days=1))] if not df.empty else df

    with marco("Jornada de hoy", "/inicio", f"{hoy:%d-%m-%Y} · lo que va pasando en el muelle"):
        with ui.row().classes("fila-resp gap-2"):
            ui.button("Anotar desembarque", icon="add_circle", on_click=lambda: ui.navigate.to("/registro")) \
                .classes("flex-1").props("unelevated size=lg")
            ui.button("Anotar trabajo en tierra", icon="front_hand", on_click=lambda: ui.navigate.to("/tierra")) \
                .classes("flex-1").props("unelevated size=lg color=secondary")
        tarjeta_en_el_mar()
        tarjeta_lotes_abiertos()
        with ui.element("div").classes("rejilla"):
            kpi(str(df_hoy["embarcacion_id"].nunique() if not df_hoy.empty else 0), "botes llegaron hoy",
                "directions_boat")
            kpi(f"{dec(df_hoy['kg'].sum() if not df_hoy.empty else 0, 0)} kg", "desembarcados hoy", "scale")
            kpi(str(tierra["persona_id"].nunique() if not tierra.empty else 0), "personas en tierra hoy", "groups")
            kpi(str(pendientes), "ventas sin precio (14 días)", "pending_actions",
                COLORES["amarillo"] if pendientes else MARINO)
        with ui.column().classes("tarjeta gap-1"):
            ui.html("<h2>Desembarques de hoy</h2>")
            if df_hoy.empty:
                ui.label("Todavía no llega ningún bote hoy. Ayer se anotaron "
                         f"{df_ayer['embarcacion_id'].nunique() if not df_ayer.empty else 0} botes y "
                         f"{dec(df_ayer['kg'].sum() if not df_ayer.empty else 0, 0)} kg.").classes("tenue")
            for _, f in df_hoy.sort_values("creado_en", ascending=False).iterrows():
                with ui.row().classes("w-full justify-between no-wrap py-1").style("border-bottom:1px solid #EEF3F6"):
                    ui.label(f"{botes.get(f['embarcacion_id'])} · {f['especie']}")
                    ui.label(f"{dec(f['kg'] or 0, 0)} kg").classes("font-bold")
        with ui.column().classes("tarjeta gap-2"):
            ui.html("<h2>Pendientes de la registradora</h2>")
            for texto, icono, ruta in [("Completar precios de ventas cerradas", "pending_actions", "/pendientes"),
                                       ("Transcribir hojas o cuadernos del muelle", "menu_book", "/cuaderno"),
                                       ("Actualizar la lista de personas en tierra", "groups", "/personas")]:
                with ui.row().classes("tarjeta-plana items-center gap-3 no-wrap cursor-pointer") \
                        .on("click", lambda _, r=ruta: ui.navigate.to(r)):
                    ui.icon(icono, size="26px").style(f"color:{MAR}")
                    ui.label(texto).classes("font-bold flex-1")
                    ui.icon("chevron_right")
        caja_clima = ui.column().classes("tarjeta gap-2")
        with caja_clima:
            ui.skeleton().classes("w-full h-24")
        tarjeta_avisos()
    from nicegui import context
    await context.client.connected()
    await tarjeta_clima_corta(caja_clima)


# ------------------------------------------------------------------ directiva
async def _panel():
    with sesion() as s:
        k = analytics.kpis_caleta(s)
        prod = analytics.produccion_mensual(s)
        tierra = analytics.tierra_mensual(s)
        cuotas = analytics.cuotas(s)
        var = analytics.variacion_precios(s)
        cal = analytics.resumen_calidad(s)
    pc = cal["por_calidad"]
    with marco("Panel de la caleta", "/inicio", "Totales de la caleta, sin datos individuales de cada bote."):
        tarjeta_en_el_mar()
        if pc.get("advertencia", 0):
            with ui.row().classes("tarjeta items-center justify-between no-wrap gap-3") \
                    .style(f"border-left:8px solid {BOYA}"):
                with ui.column().classes("gap-0"):
                    ui.label(f"{pc['advertencia']:,} registros esperan revisión".replace(",", ".")).classes("grande")
                    ui.label("Apruébalos, corrígelos o recházalos para que las cifras sean confiables.") \
                        .classes("tenue")
                ui.button("Revisar", icon="fact_check", on_click=lambda: ui.navigate.to("/revision")) \
                    .props("unelevated color=accent text-color=dark")
        with ui.element("div").classes("rejilla"):
            kpi(f"{dec(k['kg_30'] / 1000)} t", "desembarcado (30 días)", "scale")
            kpi(clp_corto(k["ingreso_30"]), "vendido (30 días)", "payments")
            kpi(f"1 de cada {100 / k['pct_no_cubre']:.0f}" if k["pct_no_cubre"] else "—",
                f"salidas no cubren costos ({k['pct_no_cubre']:.0f}%, n = {k['n_evaluables']:,})".replace(",", "."),
                "trending_down", COLORES["rojo"])
            kpi(clp_corto(k["valor_tierra_30"]), f"trabajo en tierra, {k['personas_tierra_30']} personas (30 días)",
                "front_hand")
        with ui.column().classes("tarjeta"):
            ui.html("<h2>Producción mensual por especie</h2>")
            ui.echart(barras_apiladas(prod / 1000, " t")).classes("w-full h-80")
        with ui.row().classes("fila-resp"):
            with ui.column().classes("tarjeta flex-1"):
                ui.html("<h2>Cuotas del año</h2>")
                for c in cuotas:
                    color = "negative" if c["alerta"] else "positive"
                    ui.label(f"{c['especie']}: {c['usado']:,.0f} de {c['cuota']:,.0f} kg ({c['pct']:.0f}%)"
                             .replace(",", ".")).classes("font-bold")
                    ui.linear_progress(min(c["pct"] / 100, 1), show_value=False, size="14px") \
                        .props(f"color={color} rounded")
                    if c["alerta"]:
                        ui.label("Sobre el 80 %: coordinar salidas.").classes("text-sm text-negative")
                ui.button("Administrar vedas y cuotas", on_click=lambda: ui.navigate.to("/cuotas")).props("flat")
            with ui.column().classes("tarjeta flex-1"):
                ui.html("<h2>Variación del precio en un mes</h2>")
                for _, f in var.iterrows():
                    with ui.row().classes("w-full justify-between"):
                        ui.label(f["especie"])
                        ui.label(f"hasta {dec(f['variacion_max'])} veces").classes("font-bold")
                ui.label("Si el precio puede más que duplicarse en un mes, conocer el rango ayuda a no vender "
                         "en el día malo.").classes("tenue")
        with ui.column().classes("tarjeta"):
            ui.html("<h2>Aporte del trabajo en tierra</h2>")
            ui.label("Encarnado, fileteo, venta y limpieza, valorizados con tarifas que define la directiva.") \
                .classes("tenue")
            ui.echart(barras_apiladas(tierra / 1_000_000, " M")).classes("w-full h-72")
        with ui.column().classes("tarjeta gap-1"):
            ui.html("<h2>Calidad de los datos</h2>")
            with ui.row().classes("gap-6"):
                for etiqueta, clave, color in [("aprobados u OK", "ok", COLORES["verde"]),
                                               ("por revisar", "advertencia", COLORES["amarillo"]),
                                               ("con error", "error", COLORES["rojo"]),
                                               ("rechazados", "rechazado", COLORES["gris"])]:
                    with ui.column().classes("gap-0"):
                        ui.label(f"{pc.get(clave, 0):,}".replace(",", ".")).classes("kpi-valor").style(f"color:{color}")
                        ui.label(etiqueta).classes("kpi-label")
            ui.label(f"{cal['pct_papel']:.0f}% viene de cuadernos digitalizados; {cal['sin_precio']} ventas sin "
                     f"precio y {cal['sin_kg']} registros sin kilos.").classes("tenue")
        tarjeta_avisos()
