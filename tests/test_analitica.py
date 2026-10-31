"""Pruebas de la analítica sobre los datos ficticios generados."""
from datetime import date, timedelta

import pytest

from app import analytics, importar
from app.db import sesion
from app.seed import generar


@pytest.fixture(scope="module", autouse=True)
def datos():
    generar(verbose=False)


def test_datos_reflejan_el_caso():
    with sesion() as s:
        k = analytics.kpis_caleta(s)
        var = analytics.variacion_precios(s)
        cal = analytics.resumen_calidad(s)
    assert k["botes_activos"] == 41
    assert 18 <= k["pct_no_cubre"] <= 30                 # ≈ 1 de cada 4
    assert var["variacion_max"].max() <= 2.6              # hasta ≈ 2,3 veces
    assert cal["por_calidad"]["error"] > 0                # hay errores sembrados a propósito


def test_oferta_bajo_lo_normal_es_roja():
    with sesion() as s:
        ref = analytics.precio_referencia(s, 1)
    assert ref.n > 0
    assert analytics.evaluar_oferta(ref, ref.p25 * 0.8).color == "rojo"
    assert analytics.evaluar_oferta(ref, ref.p75 * 1.05).color == "verde"


def test_oferta_bajo_costo_es_roja_aunque_sea_normal():
    with sesion() as s:
        ref = analytics.precio_referencia(s, 1)
    v = analytics.evaluar_oferta(ref, ref.mediana, precio_piso=ref.mediana + 100)
    assert v.color == "rojo" and v.titulo == "No cubre tus costos"


def test_semaforo_entrega_razones_con_n():
    with sesion() as s:
        sem = analytics.semaforo_salida(s, 5, 1, date.today() + timedelta(days=1))
    assert sem.color in {"verde", "amarillo", "rojo"}
    assert any("n =" in r for r in sem.razones)


def test_semaforo_rojo_en_veda():
    with sesion() as s:
        sem = analytics.semaforo_salida(s, 5, 1, date(date.today().year, 9, 15))
    assert sem.color == "rojo"


def test_importar_cuaderno_detecta_errores():
    csv = (b"fecha;embarcacion;especie;kg;precio_kg\n"
           b"02-01-2026;Gaviota;Merluza;120,5;1850\n"
           b"02-01-2026;Bote Inventado;Merluza;50;1800\n"
           b"03-01-2026;Gaviota;pulpo;10;3000\n"
           b"40-01-2026;Gaviota;Merluza;10;1800\n")
    with sesion() as s:
        rep = importar.revisar(s, importar.leer_csv(csv))
    estados = [r["estado"] for r in rep]
    assert estados[1] == estados[2] == estados[3] == "error"
    assert estados[0] in {"ok", "advertencia"}
