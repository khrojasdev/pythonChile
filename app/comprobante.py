"""Comprobante de trabajo en tierra: un PDF por persona y periodo.

El trabajo de encarnar, filetear o vender casi nunca queda escrito. Este comprobante le
sirve a la persona para mostrar lo que hizo (postular a un subsidio, a un curso, a la
cotización como trabajadora independiente) y a la caleta para reconocer ese aporte.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from fpdf.fonts import FontFace

from app import analytics, config
from app.db import sesion
from app.exportar import MAR, MARINO, _Pdf, _texto
from app.models import PersonaTierra, TipoTrabajo


def detalle(persona_id: int, desde: date, hasta: date) -> pd.DataFrame:
    with sesion() as s:
        df = analytics.tierra_df(s, desde=desde, hasta=hasta)
    if df.empty:
        return df
    df = df[df["persona_id"] == persona_id].sort_values("fecha")
    return df


def resumen_por_tipo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Trabajo", "Días", "Horas", "Cantidad", "Unidad", "Valor estimado"])
    t = df.groupby("tipo").agg(Días=("fecha", "nunique"), Horas=("horas", "sum"), Cantidad=("cantidad", "sum"),
                               Valor=("valor", "sum")).reset_index()
    t["Unidad"] = t["tipo"].map(lambda v: config.TARIFA_TIERRA[TipoTrabajo(v)][0])
    t = t.rename(columns={"tipo": "Trabajo", "Valor": "Valor estimado"})
    return t[["Trabajo", "Días", "Horas", "Cantidad", "Unidad", "Valor estimado"]]


def comprobante_pdf(persona_id: int, desde: date, hasta: date, emitido_por: str = "Registradora") -> bytes:
    with sesion() as s:
        p = s.get(PersonaTierra, persona_id)
        nombre = p.nombre if p else "?"
    df = detalle(persona_id, desde, hasta)
    res = resumen_por_tipo(df)

    pdf = _Pdf()
    pdf.titulo_doc = "Comprobante de trabajo en tierra"
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*MARINO)
    pdf.cell(0, 9, "Comprobante de trabajo en tierra", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.multi_cell(0, 5.5, f"{config.NOMBRE_CALETA} deja constancia de que {nombre} trabajó en tierra para la "
                           f"caleta entre el {desde:%d-%m-%Y} y el {hasta:%d-%m-%Y}, según los registros diarios "
                           "anotados por la registradora del muelle.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    dias = int(df["fecha"].nunique()) if not df.empty else 0
    horas = float(df["horas"].sum()) if not df.empty else 0
    valor = float(df["valor"].sum()) if not df.empty else 0
    pdf.set_fill_color(234, 242, 247)
    y = pdf.get_y()
    for k, (cifra, etiqueta) in enumerate([(str(dias), "días trabajados"), (_texto(horas), "horas"),
                                           (analytics.clp(valor), "valor estimado del aporte")]):
        x = 10 + k * 64
        pdf.rect(x, y, 60, 22, "F")
        pdf.set_xy(x + 4, y + 3)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*MARINO)
        pdf.cell(52, 8, cifra)
        pdf.set_xy(x + 4, y + 12)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(52, 6, etiqueta)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + 28)

    estilo = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=MAR)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*MARINO)
    pdf.cell(0, 8, "Resumen por tipo de trabajo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    if res.empty:
        pdf.cell(0, 7, "Sin registros en este periodo.", new_x="LMARGIN", new_y="NEXT")
    else:
        with pdf.table(headings_style=estilo, line_height=6, borders_layout="HORIZONTAL_LINES",
                       text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "LEFT", "RIGHT")) as t:
            fila = t.row()
            for c in res.columns:
                fila.cell(c)
            for _, r in res.iterrows():
                fila = t.row()
                for c in res.columns:
                    fila.cell(analytics.clp(r[c]) if c == "Valor estimado" else _texto(r[c]))
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*MARINO)
        pdf.cell(0, 8, "Detalle diario", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8.5)
        with pdf.table(headings_style=estilo, line_height=5, borders_layout="HORIZONTAL_LINES",
                       cell_fill_color=(240, 245, 249), cell_fill_mode="ROWS",
                       text_align=("LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT")) as t:
            fila = t.row()
            for c in ["Fecha", "Trabajo", "Cantidad", "Horas", "Valor"]:
                fila.cell(c)
            for _, r in df.iterrows():
                fila = t.row()
                for v in [r["fecha"], r["tipo"], r["cantidad"], r["horas"], analytics.clp(r["valor"])]:
                    fila.cell(_texto(v))

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(90, 90, 90)
    tarifas = "; ".join(f"{t.value}: {analytics.clp(v[1])} por {v[0][:-1] if v[0].endswith('s') else v[0]}"
                        for t, v in config.TARIFA_TIERRA.items())
    pdf.multi_cell(0, 4.5, "El valor es una estimación con tarifas referenciales que fija el sindicato "
                           f"({tarifas}). No es una liquidación de sueldo ni reemplaza un contrato.",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(85, 6, "_______________________________")
    pdf.cell(20)
    pdf.cell(85, 6, "_______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(85, 6, f"Emitido por: {emitido_por}")
    pdf.cell(20)
    pdf.cell(85, 6, "Directiva del sindicato", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
