"""Noticias de pesca desde el RSS público de Google Noticias (sin clave).

Si no hay internet, se muestran novedades de DEMO de la caleta (ficticias),
marcadas como tales. Se guardan 1 hora en memoria.
"""
from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx

from app import config

TTL = 60 * 60
_cache: dict = {"t": 0.0, "dato": None}
BUSQUEDAS = ["pesca artesanal Chile", "caleta pescadores Valparaíso", "Sernapesca veda"]


@dataclass
class Noticia:
    titulo: str
    enlace: str
    fuente: str
    fecha: Optional[datetime]
    real: bool = True

    @property
    def hace(self) -> str:
        if not self.fecha:
            return ""
        horas = (datetime.now(self.fecha.tzinfo) - self.fecha).total_seconds() / 3600
        if horas < 1:
            return "hace minutos"
        if horas < 24:
            return f"hace {int(horas)} h"
        dias = int(horas // 24)
        return "ayer" if dias == 1 else f"hace {dias} días"


DEMO = [
    Noticia("Caleta organiza jornada de capacitación en registro digital de capturas",
            "", "Novedades de la caleta (demo)", None, real=False),
    Noticia("Mujeres encarnadoras proponen tarifa común para el trabajo en tierra",
            "", "Novedades de la caleta (demo)", None, real=False),
    Noticia("Restaurantes del puerto buscan comprar pescado directo a pescadores",
            "", "Novedades de la caleta (demo)", None, real=False),
]


def parsear_rss(xml_texto: str, limite: int = 8) -> list[Noticia]:
    raiz = ET.fromstring(xml_texto)
    out = []
    for item in raiz.iter("item"):
        titulo = html.unescape(item.findtext("title") or "").strip()
        fuente = (item.findtext("source") or "").strip()
        if fuente and titulo.endswith(f" - {fuente}"):
            titulo = titulo[: -len(fuente) - 3]
        elif not fuente and " - " in titulo:
            titulo, fuente = titulo.rsplit(" - ", 1)
        try:
            fecha = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            fecha = None
        out.append(Noticia(re.sub(r"\s+", " ", titulo), item.findtext("link") or "", fuente, fecha))
    return out[:limite]


async def obtener(limite: int = 6) -> tuple[list[Noticia], bool]:
    """Devuelve (noticias, son_reales)."""
    if not config.NOTICIAS_REALES:
        return DEMO, False
    if _cache["dato"] is not None and time.time() - _cache["t"] < TTL:
        return _cache["dato"]
    vistas, todas = set(), []
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True) as cli:
            for q in BUSQUEDAS:
                r = await cli.get("https://news.google.com/rss/search",
                                  params=dict(q=q + " when:30d", hl="es-419", gl="CL", ceid="CL:es-419"))
                r.raise_for_status()
                for n in parsear_rss(r.text):
                    clave = n.titulo.lower()[:60]
                    if clave not in vistas:
                        vistas.add(clave)
                        todas.append(n)
    except (httpx.HTTPError, ET.ParseError):
        pass
    if not todas:
        _cache.update(t=time.time() - TTL + 120, dato=(DEMO, False))
        return DEMO, False
    todas.sort(key=lambda n: n.fecha.timestamp() if n.fecha else 0, reverse=True)
    res = (todas[:limite], True)
    _cache.update(t=time.time(), dato=res)
    return res
