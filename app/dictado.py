"""Dictado por voz: convierte una frase como «merluza noventa kilos a mil trescientos»
en líneas del formulario de desembarque.

El reconocimiento de voz lo hace el navegador del celular (Web Speech API, en español de
Chile). Aquí solo se interpreta el texto, así que también sirve si la persona lo escribe.
Nada se guarda sin que la persona revise y apriete «Guardar».
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

UNIDADES = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
            "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
            "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
            "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
            "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
            "veintinueve": 29}
DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
           "noventa": 90}
CENTENAS = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300,
            "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
            "seiscientos": 600, "seiscientas": 600, "setecientos": 700, "setecientas": 700,
            "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900}
PALABRAS_NUMERO = set(UNIDADES) | set(DECENAS) | set(CENTENAS) | {"mil", "medio", "media"}

KILOS = {"kilo", "kilos", "kg", "kgs", "kilogramos", "kilogramo", "k"}
PESOS = {"peso", "pesos", "luca", "lucas", "clp"}
LITROS = {"litro", "litros", "lt", "lts"}
MARCA_PRECIO = {"a", "al", "precio", "en", "por"}


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("$", " pesos_antes ")
    t = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", t)            # 1.300 -> 1300
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)                      # 2,5 -> 2.5
    t = re.sub(r"(\d)(kg|kilos?|lts?|litros?)\b", r"\1 \2", t)  # 90kg -> 90 kg
    return re.sub(r"[^\w.\s]", " ", t)


def _leer_numero(tokens: list[str], i: int) -> tuple[Optional[float], int]:
    """Lee un número (en cifras o en palabras) desde tokens[i]. Devuelve (valor, siguiente índice)."""
    tok = tokens[i]
    if re.fullmatch(r"\d+(\.\d+)?", tok):
        valor, j = float(tok), i + 1
        if j + 1 < len(tokens) and tokens[j] == "mil":          # "2 mil"
            valor, j = valor * 1000, j + 1
        if j + 1 < len(tokens) and tokens[j] == "y" and tokens[j + 1] in ("medio", "media"):
            valor, j = valor + 0.5, j + 2
        return valor, j
    if tok not in PALABRAS_NUMERO or tok in ("medio", "media"):
        return None, i
    total, actual, j, ultimo = 0.0, 0.0, i, None
    while j < len(tokens):
        t = tokens[j]
        if t in UNIDADES:
            actual += UNIDADES[t]
            ultimo = "u"
        elif t in DECENAS:
            actual += DECENAS[t]
            ultimo = "d"
        elif t in CENTENAS:
            actual += CENTENAS[t]
            ultimo = "c"
        elif t == "mil":
            total += (actual or 1) * 1000
            actual, ultimo = 0.0, "m"
        elif t == "y" and j + 1 < len(tokens):
            sig = tokens[j + 1]
            if ultimo == "d" and sig in UNIDADES and UNIDADES[sig] < 10:
                j += 1
                continue
            if sig in ("medio", "media"):
                actual += 0.5
                j += 2
                break
            break
        else:
            break
        j += 1
    return total + actual, j


@dataclass
class LineaDictada:
    especie: str
    kg: Optional[float] = None
    precio: Optional[int] = None
    estimado: bool = False


@dataclass
class Dictado:
    lineas: list[LineaDictada] = field(default_factory=list)
    litros: Optional[float] = None
    no_entendido: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        partes = []
        for ln in self.lineas:
            p = ln.especie
            p += f", {ln.kg:g} kg" if ln.kg is not None else ", sin kilos"
            if ln.precio:
                p += ", a $" + f"{ln.precio:,}".replace(",", ".")
            partes.append(p)
        if self.litros:
            partes.append(f"{self.litros:g} litros de combustible")
        return " · ".join(partes) if partes else "No reconocí ninguna especie."


def interpretar(texto: str, especies: list[str]) -> Dictado:
    """Interpreta la frase dictada. `especies` = nombres del catálogo (Merluza, Reineta...)."""
    resultado = Dictado()
    if not texto or not texto.strip():
        return resultado
    tokens = _normalizar(texto).split()
    nombres = {_normalizar(e).strip(): e for e in especies}
    # también en plural simple: "merluzas", "reinetas"
    nombres.update({k + "s": v for k, v in list(nombres.items())})

    actual: Optional[LineaDictada] = None
    numeros: list[tuple[float, str, str]] = []   # (valor, palabra anterior, palabra siguiente)

    def cerrar():
        if actual is None:
            return
        _asignar(actual, numeros, resultado)
        resultado.lineas.append(actual)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in nombres:
            cerrar()
            actual, numeros = LineaDictada(nombres[tok]), []
            i += 1
            continue
        valor, j = _leer_numero(tokens, i)
        if valor is not None and j > i:
            antes = tokens[i - 1] if i else ""
            despues = tokens[j] if j < len(tokens) else ""
            if despues in LITROS or antes in ("bencina", "combustible", "petroleo"):
                resultado.litros = valor
            elif actual is not None:
                numeros.append((valor, antes, despues))
            i = j
            continue
        if actual is not None and tok in ("estimado", "estimados", "ojo", "aprox", "aproximado"):
            actual.estimado = True
        i += 1
    cerrar()
    return resultado


def _asignar(linea: LineaDictada, numeros: list[tuple[float, str, str]], res: Dictado) -> None:
    kg = precio = None
    for valor, antes, despues in numeros:
        if despues in KILOS and kg is None:
            kg = valor
        elif (despues in PESOS or antes in MARCA_PRECIO or antes == "pesos_antes") and precio is None:
            precio = valor
        elif kg is None:
            kg = valor
        elif precio is None:
            precio = valor
    if precio is not None and despues_lucas(numeros, precio):
        precio *= 1000
    linea.kg = kg
    linea.precio = int(round(precio)) if precio is not None else None


def despues_lucas(numeros, precio) -> bool:
    """«a dos lucas» = $2.000."""
    return any(v == precio and d in ("luca", "lucas") for v, _, d in numeros) and precio < 100
