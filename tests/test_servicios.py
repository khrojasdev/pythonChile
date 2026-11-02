"""Revisión, exportaciones, clima y noticias (sin internet: se prueban los parsers y los respaldos)."""
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlmodel import select

from app import exportar, revision
from app.db import sesion
from app.models import Calidad, Desembarque
from app.seed import generar
from app.servicios import clima, noticias


@pytest.fixture(scope="module", autouse=True)
def datos():
    generar(verbose=False)


def _uno(calidad):
    with sesion() as s:
        return s.exec(select(Desembarque).where(Desembarque.calidad == calidad)).first().id


def test_aprobar_y_deshacer():
    i = _uno(Calidad.ADVERTENCIA)
    with sesion() as s:
        d = revision.aprobar(s, i, "Directiva")
        assert d.calidad == Calidad.OK and d.revisado_por == "Directiva"
        d = revision.deshacer(s, i)
        assert d.calidad == Calidad.ADVERTENCIA and d.revisado_por == ""


def test_rechazar_saca_de_los_calculos():
    from app import analytics
    i = _uno(Calidad.ADVERTENCIA)
    with sesion() as s:
        revision.rechazar(s, i, "Directiva", "duplicado")
        df = analytics.desembarques_df(s)
        assert i not in set(df["id"])


def test_error_no_se_aprueba_tal_cual_pero_se_corrige():
    i = _uno(Calidad.ERROR)
    with sesion() as s:
        with pytest.raises(revision.RevisionError):
            revision.aprobar(s, i, "Directiva")
        _, motivo = revision.corregir(s, i, "Directiva", -5, 1500)
        assert motivo                                   # sigue con error: no se guarda
        d, motivo = revision.corregir(s, i, "Directiva", 50, 1500)
        assert not motivo and d.calidad == Calidad.OK and "Corregido" in d.notas_calidad


def test_exportar_pdf_y_csv():
    df = pd.DataFrame({"Fecha": [date.today()], "Especie": ["Merluza"], "Kg": [12.5]})
    assert exportar.a_pdf(df, "Prueba").startswith(b"%PDF")
    assert exportar.a_pdf(df.iloc[0:0], "Vacío").startswith(b"%PDF")
    assert b"12,5" in exportar.a_csv(df)
    assert exportar.plantilla_cuaderno_pdf().startswith(b"%PDF")


def test_parsear_open_meteo():
    hoy = date.today()
    f = [(hoy + timedelta(days=k)).isoformat() for k in range(2)]
    meteo = {"current": {"temperature_2m": 15.2, "weather_code": 3, "wind_speed_10m": 9},
             "daily": {"time": f, "weather_code": [3, 61], "temperature_2m_max": [18, 16],
                       "temperature_2m_min": [11, 10], "precipitation_probability_max": [5, 80],
                       "wind_speed_10m_max": [12, 27], "wind_gusts_10m_max": [20, 35]}}
    marino = {"current": {"wave_height": 1.4},
              "daily": {"time": f, "wave_height_max": [1.5, 2.9], "wave_period_max": [10, 12]}}
    p = clima._parsear(meteo, marino)
    assert p.real and p.temp_actual == 15.2
    assert p.dias[0].estado_mar == "verde" and p.dias[1].estado_mar == "rojo"
    assert p.dias[1].descripcion == "Lluvia débil"


def test_clima_sin_internet_usa_simulado():
    p = clima.simulado("sin red")
    assert not p.real and p.dias


def test_parsear_rss():
    xml = """<rss><channel><item><title>Pescadores celebran buena temporada - Diario X</title>
    <link>https://ejemplo.cl/n1</link><pubDate>Sun, 01 Nov 2026 12:00:00 GMT</pubDate>
    <source url="https://ejemplo.cl">Diario X</source></item></channel></rss>"""
    n = noticias.parsear_rss(xml)[0]
    assert n.titulo == "Pescadores celebran buena temporada" and n.fuente == "Diario X"
