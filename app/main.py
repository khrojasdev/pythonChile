"""Punto de entrada.  Local:  python -m app.main   ·   Render: ver render.yaml"""
import os

from nicegui import ui

from app import config
from app.pages import (calidad, informe, inicio, limites, mis_numeros, panel, precio,  # noqa: F401
                       registro, salir, tierra)
from app.seed import asegurar_datos

asegurar_datos()   # en Render el disco es temporal: si la base está vacía, genera datos ficticios

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Mar Adentro",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        storage_secret=config.STORAGE_SECRET,
        language="es",
        favicon="🌊",
        reload=False,
        show=False,
    )
