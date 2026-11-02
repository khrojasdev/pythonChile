"""Ilustraciones propias en SVG (sin imágenes externas: funcionan sin internet).

El estilo toma los botes pintados de las caletas: cascos de colores con franja blanca,
cerros con casas y capas de mar.
"""
from __future__ import annotations

MARINO = "#0B3C5D"
MAR = "#1D6A8A"
CELESTE = "#5FA8D3"
ESPUMA = "#EAF2F5"
BOYA = "#F2A900"
CASCO_ROJO = "#C8402F"
ALGA = "#2F7D5B"

LOGO = f"""<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Mar Adentro">
<circle cx="32" cy="32" r="30" fill="{MARINO}" stroke="#fff" stroke-width="2"/>
<path d="M14 34h36l-5 9H19z" fill="{BOYA}"/>
<path d="M17 38h30" stroke="#fff" stroke-width="2"/>
<path d="M31 14v20" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
<path d="M33 16l11 15H33z" fill="#fff"/>
<path d="M8 47c4 0 4-3 8-3s4 3 8 3 4-3 8-3 4 3 8 3 4-3 8-3 4 3 8 3" fill="none" stroke="{CELESTE}"
 stroke-width="2.5" stroke-linecap="round"/>
</svg>"""


def _bote(x: float, y: float, escala: float, casco: str, franja: str = "#fff") -> str:
    w = 120 * escala
    h = 26 * escala
    return (f'<g transform="translate({x},{y})">'
            f'<path d="M0 0h{w}l-{14*escala} {h}H{12*escala}z" fill="{casco}"/>'
            f'<path d="M{4*escala} {7*escala}h{w-8*escala}" stroke="{franja}" stroke-width="{3*escala}"/>'
            f'<rect x="{w*0.42}" y="-{20*escala}" width="{22*escala}" height="{20*escala}" fill="#F7F4EC" rx="{2*escala}"/>'
            f'<rect x="{w*0.42+5*escala}" y="-{15*escala}" width="{6*escala}" height="{6*escala}" fill="{MAR}"/>'
            f'<path d="M{w*0.3} 0V-{44*escala}" stroke="#3B3B3B" stroke-width="{2*escala}"/>'
            f'</g>')


def _casas(x0: float, base: float, n: int, semilla: int) -> str:
    colores = ["#E8B04B", "#D9675A", "#7FB3D5", "#F3E3C3", "#8FBF9F", "#C77DA3", "#F0C987"]
    out, x = [], x0
    for i in range(n):
        w = 26 + (i * semilla) % 18
        h = 22 + (i * 7 + semilla) % 26
        c = colores[(i + semilla) % len(colores)]
        out.append(f'<rect x="{x}" y="{base-h}" width="{w}" height="{h}" fill="{c}"/>'
                   f'<rect x="{x+6}" y="{base-h+7}" width="6" height="7" fill="#3E4A57" opacity=".55"/>'
                   f'<path d="M{x-2} {base-h}l{w/2+2} -10l{w/2+2} 10z" fill="#9C4B3A" opacity=".85"/>')
        x += w + 4
    return "".join(out)


HERO = f"""<svg viewBox="0 175 1200 285" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg"
 role="img" aria-label="Caleta con botes de colores al amanecer">
<defs>
 <linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#9CC9DF"/><stop offset=".62" stop-color="#E6EFF0"/><stop offset="1" stop-color="#F6DDA0"/>
 </linearGradient>
</defs>
<rect width="1200" height="460" fill="#DDEBEF"/>
<circle cx="930" cy="250" r="48" fill="{BOYA}" opacity=".85"/>
<path d="M0 270 Q140 170 300 215 T620 200 T900 225 T1200 190 V320 H0z" fill="#7C9C8E"/>
{_casas(20, 268, 9, 3)}{_casas(330, 252, 8, 5)}{_casas(660, 262, 7, 2)}{_casas(960, 250, 8, 4)}
<path d="M0 300 Q120 280 260 296 T560 292 T880 300 T1200 288 V460 H0z" fill="{CELESTE}"/>
<path d="M0 318 Q150 300 320 316 T650 312 T980 320 T1200 308 V460 H0z" fill="{MAR}"/>
{_bote(150, 312, 1.25, CASCO_ROJO)}{_bote(470, 322, 1.0, BOYA, "#fff")}{_bote(760, 306, 1.4, "#2C5F8A")}
<path d="M0 362 Q160 342 330 360 T680 356 T1010 364 T1200 352 V460 H0z" fill="{MARINO}"/>
<path d="M40 390c30 0 30-8 60-8s30 8 60 8M520 410c30 0 30-8 60-8s30 8 60 8M900 384c30 0 30-8 60-8s30 8 60 8"
 stroke="{CELESTE}" stroke-width="3" fill="none" stroke-linecap="round" opacity=".7"/>
</svg>"""


# ------------------------------------------------------------------ especies
_FORMA_PEZ = ("M6 20 C14 8 34 6 46 14 L58 6 L56 20 L58 34 L46 26 C34 34 14 32 6 20 Z", "M44 15 L44 25")
_FORMAS = {
    "Merluza": ("pez_largo", "#8FA9B8"),
    "Reineta": ("pez_alto", "#B9C3C9"),
    "Jibia": ("calamar", "#D07A6A"),
    "Congrio": ("anguila", "#D48A4E"),
    "Corvina": ("pez", "#9EAF9B"),
    "Sierra": ("pez_largo", "#6E8FA8"),
}


def especie_svg(nombre: str, tam: int = 40) -> str:
    forma, color = _FORMAS.get(nombre, ("pez", "#8FA9B8"))
    ojo = '<circle cx="15" cy="17" r="2.6" fill="#13324A"/>'
    if forma == "calamar":
        cuerpo = (f'<path d="M34 6 C46 12 50 22 44 28 L22 28 C18 22 22 12 34 6Z" fill="{color}"/>'
                  f'<path d="M24 28 C20 34 14 34 10 36 M30 28 C28 35 24 37 20 38 M36 28 C36 35 34 37 32 39 '
                  f'M42 28 C44 34 46 36 48 38" stroke="{color}" stroke-width="3" fill="none" stroke-linecap="round"/>'
                  '<circle cx="30" cy="22" r="2.4" fill="#13324A"/>')
    elif forma == "anguila":
        cuerpo = (f'<path d="M4 22 C12 10 22 30 32 18 S50 12 60 20 C52 26 44 22 34 28 S14 34 4 22Z" fill="{color}"/>'
                  '<circle cx="10" cy="20" r="2.2" fill="#13324A"/>')
    elif forma == "pez_alto":
        cuerpo = (f'<path d="M6 20 C12 4 36 2 46 14 L58 6 L56 20 L58 34 L46 26 C36 38 12 36 6 20Z" fill="{color}"/>'
                  f'<path d="M24 6 L30 0 L34 6" fill="{color}"/>' + ojo)
    elif forma == "pez_largo":
        cuerpo = (f'<path d="M2 20 C12 11 36 10 48 16 L60 8 L58 20 L60 32 L48 24 C36 30 12 29 2 20Z" fill="{color}"/>'
                  '<circle cx="11" cy="18" r="2.4" fill="#13324A"/>')
    else:
        cuerpo = f'<path d="{_FORMA_PEZ[0]}" fill="{color}"/>' + ojo
    return (f'<svg viewBox="0 0 64 40" width="{tam}" height="{int(tam*0.625)}" xmlns="http://www.w3.org/2000/svg" '
            f'aria-hidden="true">{cuerpo}</svg>')


# ------------------------------------------------------------------ roles (tarjetas de ingreso)
def rol_svg(rol: str) -> str:
    if rol == "pescador":
        dibujo = _bote(14, 70, 0.9, CASCO_ROJO)
    elif rol == "registradora":
        dibujo = ('<rect x="38" y="30" width="64" height="70" rx="6" fill="#F7F4EC" stroke="#13324A" stroke-width="3"/>'
                  '<path d="M50 50h40M50 64h40M50 78h26" stroke="#1D6A8A" stroke-width="4" stroke-linecap="round"/>'
                  f'<rect x="58" y="22" width="24" height="14" rx="4" fill="{BOYA}"/>')
    else:
        dibujo = (f'<path d="M30 92h80M36 92V54M56 92V54M84 92V54M104 92V54" stroke="#13324A" stroke-width="5"/>'
                  f'<path d="M24 52L70 26L116 52Z" fill="{BOYA}" stroke="#13324A" stroke-width="3"/>')
    return (f'<svg viewBox="0 0 140 110" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            f'<path d="M0 96 Q35 88 70 96 T140 96 V110 H0z" fill="{CELESTE}" opacity=".5"/>{dibujo}</svg>')
