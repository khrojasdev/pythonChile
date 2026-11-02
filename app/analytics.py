"""Analítica para decidir. Todo es estadística simple y explicable:
medianas, percentiles y conteos, siempre mostrando cuántos datos hay detrás (n).

Por qué no un modelo de ML: con datos ficticios, un modelo solo "aprendería"
lo que el equipo inventó. Con datos reales y suficientes, el paso siguiente
sería un modelo de precio, y estas funciones serían su línea base.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app import config
from app.models import (EXCLUIDAS, Calidad, Comprador, CondicionMar, Desembarque, Embarcacion,
                        Especie, Origen, PersonaTierra, TipoTrabajo, TrabajoTierra)
from app.validation import ReferenciaPrecio, en_veda


def clp(valor: Optional[float]) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    return f"${valor:,.0f}".replace(",", ".")


def clp_corto(valor: Optional[float]) -> str:
    """$23,8 M en vez de $23.810.226 (cabe en una tarjeta de celular)."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    if abs(valor) >= 1_000_000:
        return f"${valor / 1_000_000:.1f} M".replace(".", ",")
    return clp(valor)


def dec(valor: float, d: int = 1) -> str:
    return f"{valor:.{d}f}".replace(".", ",")


# ------------------------------------------------------------------ caché
# Calcular con pandas sobre toda la tabla cada vez que se abre una página bloqueaba
# el servidor varios segundos (en Render gratis, aún más) y el navegador mostraba
# "sin conexión". Ahora las tablas se cargan UNA vez y se reutilizan hasta que alguien
# guarda algo: cada commit en la base invalida el caché (ver db.py).
_cache: dict = {}


def invalidar() -> None:
    _cache.clear()


def _memo(clave, fn):
    if clave not in _cache:
        _cache[clave] = fn()
    return _cache[clave]


def _valor_enum(enum_cls, v):
    """SQLite guarda el NOMBRE del enum (OK); lo pasamos a su valor ("ok")."""
    if v is None:
        return None
    if isinstance(v, enum_cls):
        return v.value
    try:
        return enum_cls[v].value
    except KeyError:
        return enum_cls(v).value


def _base_desembarques(s: Session) -> pd.DataFrame:
    def cargar():
        df = pd.read_sql(select(Desembarque), s.connection())
        if df.empty:
            return df
        especies = {e.id: e.nombre for e in s.exec(select(Especie)).all()}
        compradores = {c.id: c.tipo.value for c in s.exec(select(Comprador)).all()}
        df["calidad"] = df["calidad"].map(lambda v: _valor_enum(Calidad, v))
        df["origen"] = df["origen"].map(lambda v: _valor_enum(Origen, v))
        df["especie"] = df["especie_id"].map(especies)
        df["comprador_tipo"] = df["comprador_id"].map(compradores)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["ingreso"] = df["kg"] * df["precio_kg"]
        return df
    return _memo("desembarques", cargar)


def desembarques_df(s: Session, desde: Optional[date] = None, hasta: Optional[date] = None,
                    embarcacion_id: Optional[int] = None, incluir_errores: bool = False) -> pd.DataFrame:
    df = _base_desembarques(s)
    if df.empty:
        return df.copy()
    m = pd.Series(True, index=df.index)
    if desde:
        m &= df["fecha"] >= pd.Timestamp(desde)
    if hasta:
        m &= df["fecha"] <= pd.Timestamp(hasta)
    if embarcacion_id:
        m &= df["embarcacion_id"] == embarcacion_id
    if not incluir_errores:
        m &= ~df["calidad"].isin([c.value for c in EXCLUIDAS])
    return df[m].copy()


def salidas_df(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa líneas por salida (fecha + embarcación) y calcula ingreso vs costo."""
    if df.empty:
        return df
    claves = [df["fecha"], df["embarcacion_id"]]
    g = df.groupby(claves)
    out = pd.DataFrame({
        "kg": g["kg"].sum(),
        "ingreso": g["ingreso"].sum(min_count=1),
        "precio_faltante": df["precio_kg"].isna().groupby(claves).any(),
        "litros": g["litros_combustible"].sum(min_count=1),
        "precio_litro": g["precio_litro"].max(),
        "carnada": g["costo_carnada"].sum(min_count=1),
    }).reset_index()
    out["costo"] = out["litros"] * out["precio_litro"].fillna(config.PRECIO_LITRO_DEFECTO) + out["carnada"].fillna(0)
    out["margen"] = out["ingreso"] - out["costo"]
    # solo se puede juzgar una salida si tiene ingreso y costo completos
    out["evaluable"] = out["ingreso"].notna() & out["litros"].notna() & ~out["precio_faltante"]
    out["no_cubre"] = out["evaluable"] & (out["margen"] < 0)
    return out


# ------------------------------------------------------------------ precios
@dataclass
class RefPrecio:
    especie: str
    n: int
    p25: Optional[float] = None
    mediana: Optional[float] = None
    p75: Optional[float] = None
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    mad: Optional[float] = None
    variacion: Optional[float] = None          # máximo / mínimo del periodo
    serie: pd.DataFrame = field(default_factory=pd.DataFrame)
    por_comprador: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def confiable(self) -> bool:
        return self.n >= config.N_MINIMO_CONFIABLE

    def para_validacion(self) -> ReferenciaPrecio:
        return ReferenciaPrecio(self.n, self.mediana, self.mad)


def precio_referencia(s: Session, especie_id: int, hoy: Optional[date] = None,
                      dias: int = config.DIAS_REFERENCIA) -> RefPrecio:
    hoy = hoy or date.today()
    especie = s.get(Especie, especie_id)
    df = desembarques_df(s, desde=hoy - timedelta(days=dias), hasta=hoy)
    if not df.empty:
        df = df[(df["especie_id"] == especie_id) & df["precio_kg"].notna() & (df["calidad"] == "ok")]
    if df.empty:
        return RefPrecio(especie.nombre, 0)
    p = df["precio_kg"].astype(float)
    serie = df.groupby("fecha")["precio_kg"].agg(["median", "min", "max", "count"]).reset_index()
    por_comp = (df.groupby("comprador_tipo")["precio_kg"].agg(["median", "count"])
                .sort_values("median", ascending=False).reset_index())
    return RefPrecio(
        especie=especie.nombre, n=len(p), p25=p.quantile(.25), mediana=p.median(),
        p75=p.quantile(.75), minimo=p.min(), maximo=p.max(),
        mad=float(np.median(np.abs(p - p.median()))),
        variacion=p.max() / p.min() if p.min() > 0 else None,
        serie=serie, por_comprador=por_comp)


@dataclass
class Veredicto:
    color: str        # "verde" | "amarillo" | "rojo" | "gris"
    titulo: str
    razones: list[str]


def evaluar_oferta(ref: RefPrecio, precio_ofrecido: float, precio_piso: Optional[float] = None) -> Veredicto:
    razones = []
    if ref.n == 0:
        return Veredicto("gris", "Sin datos suficientes", ["No hay precios registrados en los últimos 30 días."])
    razones.append(f"En los últimos 30 días la mitad de las ventas fue entre {clp(ref.p25)} y {clp(ref.p75)} "
                   f"(mediana {clp(ref.mediana)}, n = {ref.n}).")
    if not ref.confiable:
        razones.append(f"⚠️ Ojo: son pocos datos (menos de {config.N_MINIMO_CONFIABLE}), tómalo como referencia débil.")
    if precio_piso is not None and precio_ofrecido < precio_piso:
        razones.append(f"Con ese precio no cubres los costos de la salida (necesitas al menos {clp(precio_piso)}/kg).")
        return Veredicto("rojo", "No cubre tus costos", razones)
    if precio_ofrecido < ref.p25:
        if not ref.por_comprador.empty:
            mejor = ref.por_comprador.iloc[0]
            razones.append(f"Quienes mejor pagaron este mes: {mejor['comprador_tipo']} "
                           f"(mediana {clp(mejor['median'])}).")
        return Veredicto("rojo", "Está bajo lo normal", razones)
    if precio_ofrecido < ref.mediana:
        return Veredicto("amarillo", "Algo bajo, pero dentro de lo normal", razones)
    return Veredicto("verde", "Es un buen precio", razones)


# ------------------------------------------------------------------ semáforo de salida
@dataclass
class Semaforo(Veredicto):
    kg_esperado: Optional[float] = None
    precio_esperado: Optional[float] = None
    costo_esperado: Optional[float] = None
    margen_esperado: Optional[float] = None
    precio_piso: Optional[float] = None
    ola: Optional[float] = None
    viento: Optional[float] = None


def semaforo_salida(s: Session, embarcacion_id: int, especie_id: int, fecha: date,
                    hoy: Optional[date] = None, mar: Optional[tuple] = None,
                    fuente_mar: str = "simulado") -> Semaforo:
    """`mar` = (ola_m, viento_nudos) del pronóstico real; si es None se usa el simulado."""
    hoy = hoy or date.today()
    bote = s.get(Embarcacion, embarcacion_id)
    especie = s.get(Especie, especie_id)
    razones: list[str] = []
    color = "verde"

    def empeorar(nuevo: str) -> None:
        nonlocal color
        orden = ["verde", "amarillo", "rojo"]
        if orden.index(nuevo) > orden.index(color):
            color = nuevo

    # 1) reglas externas
    if en_veda(especie, fecha):
        return Semaforo("rojo", f"{especie.nombre} está en veda", [
            "La veda es una regla externa: la plataforma no la puede cambiar.",
            "Revisa otra especie disponible para esa fecha."])

    # 2) estado del mar (simulado)
    if mar is None:
        sim = s.get(CondicionMar, fecha)
        mar = (sim.ola_m, sim.viento_nudos) if sim else None
    ola = viento = None
    if mar and mar[0] is not None:
        ola, viento = mar[0], mar[1] or 0
        if ola >= config.OLA_ROJO_M or viento >= config.VIENTO_ROJO_NUDOS:
            empeorar("rojo")
            razones.append(f"🌊 Mar malo: ola {dec(ola)} m, viento {viento:.0f} nudos.")
        elif ola >= config.OLA_AMARILLO_M:
            empeorar("amarillo")
            razones.append(f"🌊 Mar regular: ola {dec(ola)} m, viento {viento:.0f} nudos.")
        else:
            razones.append(f"🌊 Mar bueno: ola {dec(ola)} m, viento {viento:.0f} nudos.")
        razones[-1] = razones[-1].rstrip(".") + f" (fuente: {fuente_mar})."
    else:
        empeorar("amarillo")
        razones.append("🌊 No hay pronóstico para esa fecha.")

    # 3) economía de la salida
    df = desembarques_df(s, desde=hoy - timedelta(days=60), hasta=hoy)
    propio = df[(df["embarcacion_id"] == embarcacion_id) & (df["especie_id"] == especie_id)] if not df.empty else df
    caleta = df[df["especie_id"] == especie_id] if not df.empty else df
    if len(propio) >= 4:
        kg_esp, fuente = propio["kg"].median(), f"tus últimas {len(propio)} salidas"
    elif len(caleta) >= 4:
        kg_esp, fuente = caleta["kg"].median(), f"{len(caleta)} salidas de la caleta"
    else:
        kg_esp, fuente = None, ""

    ref = precio_referencia(s, especie_id, hoy)
    sal = salidas_df(desembarques_df(s, desde=hoy - timedelta(days=60), hasta=hoy, embarcacion_id=embarcacion_id))
    carnada = sal["carnada"].median() if not sal.empty and sal["carnada"].notna().any() else 15000
    costo = bote.litros_por_salida * config.PRECIO_LITRO_DEFECTO + carnada

    sem = Semaforo(color, "", razones, ola=ola, viento=viento, costo_esperado=costo)
    if kg_esp is None or ref.n == 0:
        sem.razones.append("📒 Pocos registros de esta especie: no se puede estimar la ganancia.")
        empeorar("amarillo")
    else:
        ingreso = kg_esp * ref.mediana
        margen = ingreso - costo
        sem.kg_esperado, sem.precio_esperado, sem.margen_esperado = kg_esp, ref.mediana, margen
        sem.precio_piso = costo / kg_esp if kg_esp > 0 else None
        razones.append(f"🐟 Captura típica: {kg_esp:.0f} kg (según {fuente}).")
        razones.append(f"💲 Precio típico del mes: {clp(ref.mediana)}/kg (n = {ref.n}).")
        razones.append(f"⛽ Costo estimado de la salida: {clp(costo)} (combustible + carnada).")
        if margen < 0:
            empeorar("rojo")
            razones.append(f"📉 Con lo típico, la salida pierde {clp(-margen)}.")
        elif margen < costo * config.MARGEN_AMARILLO:
            empeorar("amarillo")
            razones.append(f"📊 Ganancia esperada baja: {clp(margen)}.")
        else:
            razones.append(f"📈 Ganancia esperada: {clp(margen)}.")
        if sem.precio_piso:
            razones.append(f"🎯 Para no perder plata, vende sobre {clp(sem.precio_piso)}/kg.")

    # 4) lo que pasó en días con mar parecido (historia de toda la caleta)
    if ola is not None:
        def historia():
            h = salidas_df(desembarques_df(s, desde=hoy - timedelta(days=365), hasta=hoy))
            mares = {pd.Timestamp(m.fecha): m.ola_m for m in s.exec(
                select(CondicionMar).where(CondicionMar.es_pronostico == False)).all()}  # noqa: E712
            if not h.empty:
                h["ola"] = h["fecha"].map(mares)
            return h
        hist = _memo(("historia_mar", hoy), historia)
        if not hist.empty:
            parecido = hist[hist["evaluable"] & ((hist["ola"] - ola).abs() <= 0.3)]
            if len(parecido) >= 10:
                pct = parecido["no_cubre"].mean() * 100
                razones.append(f"📚 En días con ola parecida, {pct:.0f}% de las salidas no cubrió costos "
                               f"(n = {len(parecido)}).")

    sem.color = color
    sem.titulo = {"verde": "Conviene salir", "amarillo": "Salir con cuidado",
                  "rojo": "No conviene salir"}[color]
    return sem


# ------------------------------------------------------------------ panel del sindicato
def kpis_caleta(s: Session, hoy: Optional[date] = None) -> dict:
    hoy = hoy or date.today()
    df = desembarques_df(s, desde=hoy - timedelta(days=365), hasta=hoy)
    sal = salidas_df(df)
    ult30 = df[df["fecha"] >= pd.Timestamp(hoy - timedelta(days=30))]
    tierra = tierra_df(s, desde=hoy - timedelta(days=30), hasta=hoy)
    return dict(
        kg_anio=df["kg"].sum(),
        kg_30=ult30["kg"].sum(),
        ingreso_30=ult30["ingreso"].sum(),
        salidas_anio=len(sal),
        pct_no_cubre=sal.loc[sal["evaluable"], "no_cubre"].mean() * 100 if len(sal) else 0,
        n_evaluables=int(sal["evaluable"].sum()) if len(sal) else 0,
        botes_activos=df["embarcacion_id"].nunique(),
        horas_tierra_30=tierra["horas"].sum() if not tierra.empty else 0,
        valor_tierra_30=tierra["valor"].sum() if not tierra.empty else 0,
        personas_tierra_30=tierra["persona_id"].nunique() if not tierra.empty else 0,
    )


def _inicio_12_meses(hoy: date) -> date:
    """Primer día del mes, 11 meses atrás: 12 meses completos (evita un mes cortado)."""
    return (pd.Timestamp(hoy).to_period("M") - 11).start_time.date()


def produccion_mensual(s: Session, hoy: Optional[date] = None) -> pd.DataFrame:
    hoy = hoy or date.today()
    df = desembarques_df(s, desde=_inicio_12_meses(hoy), hasta=hoy)
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    return df.pivot_table(index="mes", columns="especie", values="kg", aggfunc="sum", fill_value=0)


def variacion_precios(s: Session, hoy: Optional[date] = None) -> pd.DataFrame:
    """Para cada especie y mes: cuántas veces varió el precio (máx/mín)."""
    hoy = hoy or date.today()
    df = desembarques_df(s, desde=hoy - timedelta(days=365), hasta=hoy)
    df = df[df["precio_kg"].notna() & (df["calidad"] == "ok")]
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    v = df.groupby(["especie", "mes"])["precio_kg"].agg(lambda x: x.max() / x.min())
    return v.groupby("especie").max().round(1).sort_values(ascending=False).reset_index(name="variacion_max")


def cuotas(s: Session, hoy: Optional[date] = None) -> list[dict]:
    hoy = hoy or date.today()
    inicio_anio = date(hoy.year, 1, 1)
    df = desembarques_df(s, desde=inicio_anio, hasta=hoy)
    out = []
    for e in s.exec(select(Especie).where(Especie.cuota_anual_kg != None)).all():  # noqa: E711
        usado = df.loc[df["especie_id"] == e.id, "kg"].sum() if not df.empty else 0
        pct = usado / e.cuota_anual_kg * 100
        out.append(dict(especie=e.nombre, icono=e.icono, usado=usado, cuota=e.cuota_anual_kg, pct=pct,
                        alerta=pct >= 80))
    return out


# ------------------------------------------------------------------ trabajo en tierra
def tierra_df(s: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> pd.DataFrame:
    def cargar():
        df = pd.read_sql(select(TrabajoTierra), s.connection())
        if df.empty:
            return df
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["tipo"] = df["tipo"].map(lambda v: _valor_enum(TipoTrabajo, v))
        df["calidad"] = df["calidad"].map(lambda v: _valor_enum(Calidad, v))
        tarifa = {t.value: config.TARIFA_TIERRA[t][1] for t in TipoTrabajo}
        df["valor"] = df["cantidad"] * df["tipo"].map(tarifa)
        nombres = {p.id: p.nombre for p in s.exec(select(PersonaTierra)).all()}
        df["persona"] = df["persona_id"].map(nombres)
        return df
    df = _memo("tierra", cargar)
    if df.empty:
        return df.copy()
    m = ~df["calidad"].isin([c.value for c in EXCLUIDAS])
    if desde:
        m &= df["fecha"] >= pd.Timestamp(desde)
    if hasta:
        m &= df["fecha"] <= pd.Timestamp(hasta)
    return df[m].copy()


def valorizar(tipo, cantidad: float) -> float:
    _unidad, tarifa = config.TARIFA_TIERRA[TipoTrabajo(tipo)]
    return cantidad * tarifa


def tierra_mensual(s: Session, hoy: Optional[date] = None) -> pd.DataFrame:
    hoy = hoy or date.today()
    df = tierra_df(s, desde=_inicio_12_meses(hoy), hasta=hoy)
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    return df.pivot_table(index="mes", columns="tipo", values="valor", aggfunc="sum", fill_value=0)


def personas_tierra(s: Session) -> int:
    return len(s.exec(select(PersonaTierra)).all())


# ------------------------------------------------------------------ calidad de datos
def resumen_calidad(s: Session) -> dict:
    df = desembarques_df(s, incluir_errores=True)
    total = len(df)
    return dict(
        total=total,
        por_calidad=df["calidad"].value_counts().to_dict(),
        por_origen=df["origen"].value_counts().to_dict(),
        sin_precio=int((df["precio_kg"].isna() & (df["kg"].fillna(0) > 0)).sum()),
        sin_kg=int(df["kg"].isna().sum()),
        pct_papel=(df["origen"] == "cuaderno").mean() * 100 if total else 0,
    )


# ------------------------------------------------------------------ mis números (pescador)
def mis_numeros(s: Session, embarcacion_id: int, dias: int = 30, hoy: Optional[date] = None) -> dict:
    hoy = hoy or date.today()
    df = desembarques_df(s, desde=hoy - timedelta(days=dias), hasta=hoy, embarcacion_id=embarcacion_id)
    sal = salidas_df(df)
    if sal.empty:
        return dict(salidas=0)
    ev = sal[sal["evaluable"]]
    return dict(
        salidas=len(sal), kg=df["kg"].sum(), ingreso=df["ingreso"].sum(),
        costo=sal["costo"].sum(), margen=ev["margen"].sum(),
        no_cubre=int(ev["no_cubre"].sum()), evaluables=len(ev),
        pendientes=int(sal["precio_faltante"].sum()),
        por_especie=df.groupby("especie").agg(kg=("kg", "sum"), precio=("precio_kg", "median")).reset_index(),
        por_comprador=df.groupby("comprador_tipo")["precio_kg"].median().round(0).reset_index(),
    )
