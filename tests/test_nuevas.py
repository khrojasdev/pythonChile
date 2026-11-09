"""Pruebas de las funciones nuevas: venta conjunta, zarpe, dictado, comprobante y lista para fondos."""
from datetime import date, datetime, timedelta

import pytest
from sqlmodel import select

from app import comprobante, dictado, fondos, lotes, zarpes
from app.db import sesion
from app.models import Comprador, Desembarque, Embarcacion, Especie, EstadoLote, TipoComprador
from app.seed import generar

ESPECIES = ["Merluza", "Reineta", "Jibia", "Congrio", "Corvina", "Sierra"]


@pytest.fixture(scope="module", autouse=True)
def datos():
    generar(verbose=False)


# ------------------------------------------------------------------ dictado
@pytest.mark.parametrize("frase, esperado", [
    ("merluza noventa kilos a mil trescientos", [("Merluza", 90, 1300)]),
    ("Merluza 90 kilos a $1.300 y reineta 45 kilos", [("Merluza", 90, 1300), ("Reineta", 45, None)]),
    ("reineta cuarenta y cinco kilos a dos mil quinientos pesos", [("Reineta", 45, 2500)]),
    ("jibia trescientos veinte kilos a 850", [("Jibia", 320, 850)]),
    ("corvina 30 kg a dos lucas", [("Corvina", 30, 2000)]),
    ("sierra setenta y dos y medio kilos", [("Sierra", 72.5, None)]),
    ("CONGRIO doce kilos", [("Congrio", 12, None)]),
])
def test_dictado_entiende_frases(frase, esperado):
    r = dictado.interpretar(frase, ESPECIES)
    assert [(ln.especie, ln.kg, ln.precio) for ln in r.lineas] == esperado


def test_dictado_litros_y_estimado():
    r = dictado.interpretar("merluza 80 kilos estimado, gasté 60 litros", ESPECIES)
    assert r.litros == 60 and r.lineas[0].estimado and r.lineas[0].kg == 80


def test_dictado_sin_especie():
    assert dictado.interpretar("hola cómo estás", ESPECIES).lineas == []


# ------------------------------------------------------------------ venta conjunta
def test_reparto_proporcional():
    r = lotes.repartir([(1, "A", 60), (2, "B", 40)], 2000)
    assert [a.monto for a in r] == [120_000, 80_000]
    assert [round(a.porcentaje) for a in r] == [60, 40]


def test_venta_conjunta_completa_desembarques():
    with sesion() as s:
        merluza = s.exec(select(Especie).where(Especie.nombre == "Merluza")).one()
        b1, b2 = s.exec(select(Embarcacion).limit(2)).all()
        comp = s.exec(select(Comprador).where(Comprador.tipo == TipoComprador.PESCADERIA)).first()
        hoy = date.today() + timedelta(days=0)
        lt = lotes.crear_lote(s, merluza.id, 2000, fecha=hoy, quien="test")
        lotes.sumarse(s, lt.id, b1.id, 100)
        lotes.sumarse(s, lt.id, b2.id, 50)
        lotes.sumarse(s, lt.id, b2.id, 60)           # actualiza, no duplica
        with pytest.raises(ValueError):
            lotes.cerrar_venta(s, lt.id, comp.id, 1500)   # bajo el mínimo
        r = lotes.cerrar_venta(s, lt.id, comp.id, 2200, "test")
        assert r.lote.estado == EstadoLote.VENDIDO
        assert r.kg_total == 160 and r.total_venta == 160 * 2200
        filas = s.exec(select(Desembarque).where(Desembarque.fecha == hoy, Desembarque.especie_id == merluza.id,
                                                 Desembarque.notas_calidad.contains(f"#{lt.id}"))).all()
        assert {d.embarcacion_id for d in filas} >= {b1.id, b2.id}
        assert all(d.precio_kg == 2200 for d in filas)
        with pytest.raises(ValueError):
            lotes.sumarse(s, lt.id, b1.id, 10)           # ya cerrada


def test_precio_minimo_fuera_de_rango():
    with sesion() as s:
        with pytest.raises(ValueError):
            lotes.crear_lote(s, 1, 10)


# ------------------------------------------------------------------ zarpe
def test_zarpe_atraso_y_regreso():
    with sesion() as s:
        bote = s.exec(select(Embarcacion).where(Embarcacion.nombre == "Lobito")).first()
        t0 = datetime(2026, 11, 8, 6, 0)
        z = zarpes.registrar_zarpe(s, bote.id, 5, 2, ahora=t0)
        with pytest.raises(ValueError):
            zarpes.registrar_zarpe(s, bote.id, 5, 2, ahora=t0)      # ya tiene uno abierto
        assert zarpes.estado(z, t0 + timedelta(hours=5, minutes=20))[0] is False   # dentro de la tolerancia
        atr, minutos, _ = zarpes.estado(z, t0 + timedelta(hours=6))
        assert atr and minutos == 60
        nombres = [e.bote for e in zarpes.en_el_mar(s, t0 + timedelta(hours=6)) if e.atrasado]
        assert "Lobito" in nombres
        zarpes.registrar_regreso(s, z.id, t0 + timedelta(hours=6))
        assert zarpes.zarpe_abierto(s, bote.id, t0 + timedelta(hours=7)) is None


def test_zarpe_valida_datos():
    with sesion() as s:
        with pytest.raises(ValueError):
            zarpes.registrar_zarpe(s, 1, 30, 2)
        with pytest.raises(ValueError):
            zarpes.registrar_zarpe(s, 1, 4, 0)


# ------------------------------------------------------------------ comprobante y fondos
def test_comprobante_pdf():
    hoy = date.today()
    df = comprobante.detalle(1, hoy - timedelta(days=60), hoy)
    assert not df.empty and (df["persona_id"] == 1).all()
    pdf = comprobante.comprobante_pdf(1, hoy - timedelta(days=60), hoy)
    assert pdf[:4] == b"%PDF" and len(pdf) > 2000


def test_lista_fondos():
    with sesion() as s:
        reqs = fondos.revisar(s)
    ok, total = fondos.puntaje(reqs)
    assert total == 6 and 0 < ok < total          # los datos de demo cumplen algunos y otros no
    assert all(0 <= r.avance <= 1 for r in reqs)
