"""Límites y decisiones: lo que el equipo decidió y lo que los datos NO permiten concluir."""
from nicegui import ui

from app.ui_comun import marco

SECCIONES = {
    "¿Quién ingresa los datos y cuándo?": [
        "En tierra, al desembarcar: en el mar no hay señal y no hay manos secas.",
        "El pescador en 3 toques, o la registradora de la caleta si él no quiere usar el celular.",
        "El precio y el comprador se pueden completar después, si la venta se cierra más tarde.",
        "El trabajo en tierra lo anota la registradora al final de la jornada.",
    ],
    "¿Qué pasa cuando faltan datos o vienen con errores?": [
        "Cada registro dice de dónde viene: pesado, estimado o reconstruido de un cuaderno.",
        "Reglas por especie: kilos y precios fuera de rango, fechas futuras, duplicados y vedas.",
        "Los datos dudosos se guardan marcados y alguien los revisa; los con error no entran a los cálculos.",
        "Nunca se rellenan datos faltantes a escondidas: se muestran como pendientes.",
    ],
    "Conclusiones que NO se deben sacar": [
        "«Este mes se pescó menos, así que se trabajó menos»: pudo ser mal tiempo, veda o menos salidas.",
        "«Los restaurantes siempre pagan mejor»: compran poco volumen y no pueden llevarse toda la captura.",
        "«El martes es el mejor día»: con pocos datos por día, las diferencias suelen ser azar.",
        "Toda cifra se muestra con su n (cuántos datos hay detrás). Bajo 8 datos, se avisa que es débil.",
    ],
    "Privacidad: quién ve qué": [
        "El pescador ve sus propios números. Nadie más ve los datos de su embarcación.",
        "El sindicato ve totales de la caleta, sin nombres.",
        "Los informes para terceros no incluyen embarcaciones ni zonas de pesca.",
        "No se registran zonas de pesca: evita que todos salgan al mismo lugar.",
    ],
    "Lo que no puede cambiar": [
        "Vedas y cuotas son reglas externas: la plataforma solo avisa y lleva la cuenta.",
        "Todos los datos de esta demostración son ficticios, incluido el estado del mar.",
    ],
}


@ui.page("/limites")
def limites():
    with marco("Límites y decisiones"):
        for titulo, puntos in SECCIONES.items():
            with ui.column().classes("tarjeta gap-1"):
                ui.label(titulo).classes("font-bold text-lg")
                for p in puntos:
                    ui.label(f"• {p}")
