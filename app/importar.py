"""Importar cuadernos antiguos digitados en una planilla (CSV).

Responde al presidente del sindicato: «nos piden datos de producción de los
últimos años... están en cuadernos que nadie entiende». Alguien (por ejemplo un
pescador joven) transcribe el cuaderno a una planilla y la plataforma revisa
fila por fila qué está bien, qué es dudoso y qué no se puede usar.
"""
from __future__ import annotations

import io
import unicodedata
from datetime import date
from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from app.models import Calidad, Comprador, Desembarque, Embarcacion, Especie, Origen
from app.validation import validar_desembarque

COLUMNAS = ["fecha", "embarcacion", "especie", "kg", "precio_kg", "comprador", "litros"]

PLANTILLA = (
    "fecha;embarcacion;especie;kg;precio_kg;comprador;litros\n"
    "14-03-2025;Gaviota;Merluza;120,5;1850;Intermediario Norte;55\n"
    "14-03-2025;Gaviota;Reineta;40;;;\n"
    "15-03-2025;Pelicano;jibia;300;900;Venta en caleta;70\n"
)


def _norm(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return texto.strip().lower()


def _numero(valor) -> Optional[float]:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or str(valor).strip() == "":
        return None
    txt = str(valor).strip().replace("$", "").replace(" ", "")
    if "," in txt:                       # formato chileno: 1.850,5
        txt = txt.replace(".", "").replace(",", ".")
    return float(txt)


def leer_csv(contenido: bytes) -> pd.DataFrame:
    texto = contenido.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str)
    df.columns = [_norm(c) for c in df.columns]
    return df


def revisar(s: Session, df: pd.DataFrame, hoy: Optional[date] = None) -> list[dict]:
    """Devuelve una fila de reporte por cada fila del CSV, con su estado y motivos."""
    faltan = [c for c in ("fecha", "embarcacion", "especie", "kg") if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(faltan)}")

    botes = {}
    for b in s.exec(select(Embarcacion)).all():
        botes[_norm(b.nombre)] = b
        botes[_norm(b.matricula)] = b
    especies = {_norm(e.nombre): e for e in s.exec(select(Especie)).all()}
    compradores = {_norm(c.nombre): c for c in s.exec(select(Comprador)).all()}

    reporte = []
    vistos = set()
    for i, fila in df.iterrows():
        motivos, datos = [], None
        try:
            fecha = pd.to_datetime(fila["fecha"], dayfirst=True).date()
        except (ValueError, TypeError):
            fecha = None
        bote = botes.get(_norm(fila.get("embarcacion", "")))
        esp = especies.get(_norm(fila.get("especie", "")))
        try:
            kg = _numero(fila.get("kg"))
            precio = _numero(fila.get("precio_kg"))
            litros = _numero(fila.get("litros"))
        except ValueError:
            kg = precio = litros = None
            motivos.append("❌ Hay un número que no se entiende")
        comp_txt = fila.get("comprador")
        comp = compradores.get(_norm(comp_txt)) if isinstance(comp_txt, str) and comp_txt.strip() else None

        if fecha is None:
            motivos.append("❌ Fecha ilegible")
        if bote is None:
            motivos.append(f"❌ Embarcación desconocida: «{fila.get('embarcacion')}»")
        if esp is None:
            motivos.append(f"❌ Especie desconocida: «{fila.get('especie')}»")
        if isinstance(comp_txt, str) and comp_txt.strip() and comp is None:
            motivos.append(f"⚠️ Comprador desconocido: «{comp_txt}» (se guarda sin comprador)")

        calidad = Calidad.ERROR if motivos and any(m.startswith("❌") for m in motivos) else \
            (Calidad.ADVERTENCIA if motivos else Calidad.OK)
        if calidad != Calidad.ERROR:
            clave = (fecha, bote.id, esp.id)
            existe = clave in vistos or s.exec(select(Desembarque).where(
                Desembarque.fecha == fecha, Desembarque.embarcacion_id == bote.id,
                Desembarque.especie_id == esp.id)).first() is not None
            vistos.add(clave)
            res = validar_desembarque(fecha=fecha, especie=esp, kg=kg, precio_kg=precio, litros=litros,
                                      es_duplicado=existe, hoy=hoy)
            motivos += res.motivos
            if res.calidad == Calidad.ERROR:
                calidad = Calidad.ERROR
            elif res.calidad == Calidad.ADVERTENCIA:
                calidad = Calidad.ADVERTENCIA
            datos = dict(fecha=fecha, embarcacion_id=bote.id, especie_id=esp.id, kg=kg,
                         precio_kg=int(precio) if precio else None, comprador_id=comp.id if comp else None,
                         litros_combustible=litros, origen=Origen.CUADERNO, calidad=calidad,
                         notas_calidad=" | ".join(motivos), registrado_por="importación de cuaderno")
        reporte.append(dict(fila=int(i) + 2, fecha=str(fila.get("fecha", "")), embarcacion=str(fila.get("embarcacion", "")),
                            especie=str(fila.get("especie", "")), kg=fila.get("kg"),
                            estado=calidad.value, motivos=" | ".join(motivos) or "✅ ok", datos=datos))
    return reporte


def guardar(s: Session, reporte: list[dict]) -> int:
    """Guarda las filas sin error. Las con error se quedan en el reporte para corregir el CSV."""
    n = 0
    for r in reporte:
        if r["datos"] and r["estado"] != Calidad.ERROR.value:
            s.add(Desembarque(**r["datos"]))
            n += 1
    s.commit()
    return n
