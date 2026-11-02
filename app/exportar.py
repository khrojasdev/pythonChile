"""Exportar tablas a CSV (para Excel) y PDF (para imprimir o enviar)."""
from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace

from app import config

MARINO = (11, 60, 93)
MAR = (29, 106, 138)


def a_csv(df: pd.DataFrame) -> bytes:
    """CSV con ; y coma decimal: Excel en español lo abre directo."""
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def _texto(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, float):
        return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    if isinstance(v, (pd.Timestamp, date)):
        return v.strftime("%d-%m-%Y")
    return str(v)


class _Pdf(FPDF):
    titulo_doc = ""

    def header(self):
        self.set_fill_color(*MARINO)
        self.rect(0, 0, self.w, 13, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(10, 3.5)
        self.cell(0, 6, f"Mar Adentro - {config.NOMBRE_CALETA}   |   {self.titulo_doc}")
        self.set_text_color(0, 0, 0)
        self.ln(13)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, f"Datos ficticios (Hackatón Python Chile). Emitido el {date.today():%d-%m-%Y}. "
                        f"Página {self.page_no()}", align="C")


def a_pdf(df: pd.DataFrame, titulo: str, subtitulo: str = "", horizontal: bool | None = None,
          max_filas: int = 2000) -> bytes:
    horizontal = len(df.columns) > 6 if horizontal is None else horizontal
    pdf = _Pdf(orientation="L" if horizontal else "P")
    pdf.titulo_doc = titulo
    pdf.set_auto_page_break(True, 16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*MARINO)
    pdf.cell(0, 9, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    if subtitulo:
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(0, 5, subtitulo, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    if df.empty:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "Sin registros para este periodo.")
        return bytes(pdf.output())
    cuerpo = df.head(max_filas)
    pdf.set_font("Helvetica", "", 8)
    estilo = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=MAR)
    num = [pd.api.types.is_numeric_dtype(cuerpo[c]) for c in cuerpo.columns]
    with pdf.table(headings_style=estilo, line_height=5, borders_layout="HORIZONTAL_LINES",
                   cell_fill_color=(240, 245, 249), cell_fill_mode="ROWS",
                   text_align=tuple("RIGHT" if n else "LEFT" for n in num)) as t:
        fila = t.row()
        for c in cuerpo.columns:
            fila.cell(str(c))
        for _, r in cuerpo.iterrows():
            fila = t.row()
            for v in r:
                fila.cell(_texto(v))
    if len(df) > max_filas:
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Se muestran {max_filas} de {len(df)} filas. El CSV trae todas.")
    return bytes(pdf.output())


# ------------------------------------------------------------------ plantilla para el cuaderno
COLUMNAS_CUADERNO: Sequence[tuple[str, int]] = [
    ("Fecha", 24), ("Embarcación", 38), ("Especie", 30), ("Kilos", 20), ("Precio $/kg", 24),
    ("Comprador", 46), ("Litros comb.", 22), ("Pesado / estimado", 30),
]


def plantilla_cuaderno_pdf(filas: int = 22) -> bytes:
    """Hoja para imprimir y llenar a mano en el muelle. Después se transcribe con la plantilla CSV."""
    pdf = _Pdf(orientation="L")
    pdf.titulo_doc = "Hoja de desembarque"
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*MARINO)
    pdf.cell(0, 9, "Hoja de desembarque para imprimir", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(0, 5, "Anota una fila por especie. Si la venta no está cerrada, deja el precio en blanco. "
                         "Fecha como dd-mm-aaaa. Luego se transcribe en la planilla CSV con las mismas columnas.",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*MAR)
    pdf.set_text_color(255, 255, 255)
    for nombre, ancho in COLUMNAS_CUADERNO:
        pdf.cell(ancho, 8, nombre, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    for _ in range(filas):
        for _, ancho in COLUMNAS_CUADERNO:
            pdf.cell(ancho, 7.4, "", border=1)
        pdf.ln()
    return bytes(pdf.output())
