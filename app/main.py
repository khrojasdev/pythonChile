"""Punto de entrada.  Local:  python -m app.main   ·   Render: ver render.yaml"""
import os
from pathlib import Path

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from app import config
from app.ilustraciones import LOGO
from app.pages import (avisos_clima, comprobantes, cuaderno, gestion, informes, ingresar, inicio,  # noqa: F401
                       limites, mis_numeros, pendientes, pizarra, portada, precio, registro, revision, salir,
                       tierra, ventas_conjuntas, zarpe)
from app.seed import asegurar_datos

app.add_static_files("/static", Path(__file__).parent / "static")
asegurar_datos()   # en Render el disco es temporal: si la base está vacía, genera datos ficticios


@app.get("/salud")
def salud():
    """Render la consulta para saber si la app está viva."""
    return {"ok": True}


# Rutas antiguas -> nuevas (por si alguien guardó un enlace)
def _redirigir(destino: str):
    return lambda: RedirectResponse(destino)


for vieja, nueva in {"/panel": "/inicio", "/calidad": "/revision", "/informe": "/informes"}.items():
    app.add_api_route(vieja, _redirigir(nueva))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Mar Adentro",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        storage_secret=config.STORAGE_SECRET,
        language="es",
        favicon=LOGO,
        reload=False,
        show=False,
        # Si la señal se corta unos segundos (celular, wifi del muelle), la página espera y se
        # reconecta sola en vez de perder lo escrito.
        reconnect_timeout=30,
    )
