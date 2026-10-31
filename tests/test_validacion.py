"""Pruebas de las reglas de calidad de datos (no necesitan base de datos)."""
from datetime import date

from app.importar import _numero
from app.models import Calidad, Especie
from app.validation import ReferenciaPrecio, en_veda, validar_desembarque, validar_trabajo_tierra

HOY = date(2026, 10, 31)
MERLUZA = Especie(id=1, nombre="Merluza", kg_max_salida=350, precio_min=900, precio_max=3500,
                  veda_mes_inicio=9, veda_mes_fin=9)


def validar(**kw):
    base = dict(fecha=date(2026, 10, 20), especie=MERLUZA, kg=100, precio_kg=1800, hoy=HOY)
    base.update(kw)
    return validar_desembarque(**base)


def test_registro_normal_es_ok():
    assert validar().calidad == Calidad.OK


def test_kilos_faltantes_o_negativos_son_error():
    assert validar(kg=None).calidad == Calidad.ERROR
    assert validar(kg=-5).calidad == Calidad.ERROR


def test_coma_corrida_es_advertencia_y_absurdo_es_error():
    assert validar(kg=1000).calidad == Calidad.ADVERTENCIA      # 10x lo habitual: revisar
    assert validar(kg=99_999).calidad == Calidad.ERROR


def test_precio_faltante_queda_pendiente_no_error():
    r = validar(precio_kg=None)
    assert r.calidad == Calidad.ADVERTENCIA
    assert "pendiente" in r.texto


def test_salida_sin_captura_no_pide_precio():
    assert validar(kg=0, precio_kg=None).calidad == Calidad.OK


def test_precio_atipico_respecto_al_mes():
    ref = ReferenciaPrecio(n=40, mediana=1800, mad=150)
    assert validar(precio_kg=3400, referencia=ref).calidad == Calidad.ADVERTENCIA
    # con pocos datos no se juzga contra la mediana
    assert validar(precio_kg=3400, referencia=ReferenciaPrecio(n=3, mediana=1800, mad=150)).calidad == Calidad.OK


def test_fecha_futura_y_veda():
    assert validar(fecha=date(2026, 11, 5)).calidad == Calidad.ERROR
    assert validar(fecha=date(2026, 9, 10)).calidad == Calidad.ADVERTENCIA


def test_veda_que_cruza_el_anio():
    e = Especie(nombre="X", veda_mes_inicio=11, veda_mes_fin=2)
    assert en_veda(e, date(2026, 12, 1)) and en_veda(e, date(2026, 1, 15))
    assert not en_veda(e, date(2026, 6, 1))


def test_duplicado():
    assert validar(es_duplicado=True).calidad == Calidad.ADVERTENCIA


def test_trabajo_tierra():
    assert validar_trabajo_tierra(fecha=HOY, cantidad=500, horas=5, hoy=HOY).calidad == Calidad.OK
    assert validar_trabajo_tierra(fecha=HOY, cantidad=500, horas=None, hoy=HOY).calidad == Calidad.ERROR
    assert validar_trabajo_tierra(fecha=HOY, cantidad=500, horas=20, hoy=HOY).calidad == Calidad.ADVERTENCIA


def test_numeros_formato_chileno():
    assert _numero("1.850,5") == 1850.5
    assert _numero("$1850") == 1850
    assert _numero("") is None
