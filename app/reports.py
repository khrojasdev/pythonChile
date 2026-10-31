"""Informe PDF para postular a fondos o mostrar a autoridades y compradores.

Solo incluye totales de la caleta: ningún dato individual por embarcación
(tensión del caso: registrar ayuda, pero puede exponer a los pescadores).
"""
from __future__ import annotations

from datetime import date, timedelta

from fpdf import FPDF
from fpdf.fonts import FontFace

from app import analytics, config
from app.db import sesion

AZUL = (11, 60, 93)
MAR = (29, 106, 138)
GRIS = (110, 110, 110)


def _miles(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


class Informe(FPDF):
    def header(self):
        self.set_fill_color(*AZUL)
        self.rect(0, 0, 210, 14, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(10, 4)
        self.cell(0, 6, f"Mar Adentro - {config.NOMBRE_CALETA}")
        self.set_text_color(0, 0, 0)
        self.ln(14)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRIS)
        self.cell(0, 6, "Datos ficticios construidos para el Hackatón Python Chile - Duoc UC Valparaíso. "
                        f"Página {self.page_no()}", align="C")

    def titulo(self, texto: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*AZUL)
        self.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)

    def parrafo(self, texto: str, tam: int = 10):
        self.set_font("Helvetica", "", tam)
        self.multi_cell(0, 5, texto, new_x="LMARGIN", new_y="NEXT")

    def tabla(self, encabezado: list[str], filas: list[list[str]], anchos=None):
        self.set_font("Helvetica", "", 8.5)
        estilo = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=MAR)
        alineacion = tuple(["LEFT"] + ["RIGHT"] * (len(encabezado) - 1))
        self.set_fill_color(255, 255, 255)
        self.set_text_color(0, 0, 0)
        with self.table(col_widths=anchos, headings_style=estilo, line_height=5.5, text_align=alineacion,
                        borders_layout="HORIZONTAL_LINES", cell_fill_color=(240, 245, 249),
                        cell_fill_mode="ROWS", width=sum(anchos) if anchos else None,
                        align="LEFT") as t:
            r = t.row()
            for h in encabezado:
                r.cell(h)
            for fila in filas:
                r = t.row()
                for c in fila:
                    r.cell(str(c))

    def barras(self, etiquetas: list[str], valores: list[float], alto: float = 45):
        """Gráfico de barras simple dibujado con rectángulos (sin dependencias extra)."""
        x0, y0, ancho = self.l_margin, self.get_y() + 2, self.w - self.l_margin - self.r_margin
        maximo = max(valores) or 1
        paso = ancho / len(valores)
        self.set_font("Helvetica", "", 7)
        for i, (et, v) in enumerate(zip(etiquetas, valores)):
            h = v / maximo * alto
            self.set_fill_color(*MAR)
            self.rect(x0 + i * paso + 1.5, y0 + alto - h, paso - 3, h, "F")
            self.set_xy(x0 + i * paso, y0 + alto + 1)
            self.cell(paso, 4, et, align="C")
            self.set_xy(x0 + i * paso, y0 + alto - h - 4)
            self.cell(paso, 4, f"{v / 1000:.0f}t", align="C")
        self.set_y(y0 + alto + 7)


def generar_pdf(hoy: date | None = None) -> bytes:
    hoy = hoy or date.today()
    with sesion() as s:
        k = analytics.kpis_caleta(s, hoy)
        prod = analytics.produccion_mensual(s, hoy)
        tierra_m = analytics.tierra_mensual(s, hoy)
        tierra = analytics.tierra_df(s, desde=hoy - timedelta(days=365), hasta=hoy)
        cal = analytics.resumen_calidad(s)
        var = analytics.variacion_precios(s, hoy)
        df = analytics.desembarques_df(s, desde=hoy - timedelta(days=365), hasta=hoy)

    pdf = Informe()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 10, "Ficha de producción de la caleta", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*GRIS)
    pdf.set_font("Helvetica", "", 10)
    desde = hoy - timedelta(days=365)
    pdf.cell(0, 6, f"Periodo: {desde:%d-%m-%Y} a {hoy:%d-%m-%Y}  ·  Emitido el {hoy:%d-%m-%Y}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    pdf.titulo("1. Resumen de los últimos 12 meses")
    ingreso = df["ingreso"].sum()
    pdf.tabla(["Indicador", "Valor"], [
        ["Embarcaciones con actividad", str(k["botes_activos"])],
        ["Salidas registradas", _miles(k["salidas_anio"])],
        ["Desembarque total", f"{_miles(k['kg_anio'])} kg"],
        ["Ventas registradas", f"${_miles(ingreso)}"],
        ["Salidas que no cubrieron combustible y carnada", f"{k['pct_no_cubre']:.0f}% (de {_miles(k['n_evaluables'])} con datos completos)"],
        ["Personas en trabajo de tierra", str(tierra["persona_id"].nunique())],
        ["Valor estimado del trabajo en tierra", f"${_miles(tierra['valor'].sum())}"],
    ], anchos=(110, 70))

    pdf.titulo("2. Desembarque mensual (kg)")
    totales = prod.sum(axis=1)
    pdf.barras([m[2:] for m in prod.index], totales.tolist())
    filas = [[m] + [_miles(v) for v in prod.loc[m]] + [_miles(totales[m])] for m in prod.index]
    filas.append(["Total"] + [_miles(v) for v in prod.sum()] + [_miles(totales.sum())])
    pdf.tabla(["Mes"] + list(prod.columns) + ["Total"], filas)

    pdf.add_page()
    pdf.titulo("3. Trabajo en tierra (encarnado, fileteo, venta, limpieza)")
    pdf.parrafo("Valorizado con tarifas referenciales definidas por el sindicato. Este trabajo, realizado "
                "mayoritariamente por mujeres de la caleta, sostiene cada salida y antes no aparecía en ningún registro.")
    por_tipo = tierra.groupby("tipo").agg(personas=("persona_id", "nunique"), horas=("horas", "sum"),
                                          cantidad=("cantidad", "sum"), valor=("valor", "sum"))
    unidades = {t.value: u for t, (u, _) in config.TARIFA_TIERRA.items()}
    pdf.tabla(["Tipo", "Personas", "Horas", "Cantidad", "Valor estimado"],
              [[t.capitalize(), str(int(f.personas)), _miles(f.horas), f"{_miles(f.cantidad)} {unidades[t]}",
                f"${_miles(f.valor)}"] for t, f in por_tipo.iterrows()])
    pdf.ln(2)
    pdf.tabla(["Mes"] + [c.capitalize() for c in tierra_m.columns] + ["Total"],
              [[m] + [f"${_miles(v)}" for v in tierra_m.loc[m]] + [f"${_miles(tierra_m.loc[m].sum())}"]
               for m in tierra_m.index])

    pdf.titulo("4. Precios de playa")
    pdf.tabla(["Especie", "Variación máxima dentro de un mes"],
              [[f.especie, f"{f.variacion_max:.1f} veces".replace(".", ",")] for f in var.itertuples()],
              anchos=(50, 70))

    pdf.titulo("5. Calidad y origen de los datos")
    pc, po = cal["por_calidad"], cal["por_origen"]
    pdf.tabla(["", "Registros", "%"], [
        ["Validados sin observaciones", _miles(pc.get("ok", 0)), f"{pc.get('ok', 0) / cal['total'] * 100:.0f}%"],
        ["Con observaciones (se usan, marcados)", _miles(pc.get("advertencia", 0)),
         f"{pc.get('advertencia', 0) / cal['total'] * 100:.0f}%"],
        ["Con error (excluidos de las cifras)", _miles(pc.get("error", 0)), f"{pc.get('error', 0) / cal['total'] * 100:.0f}%"],
        ["Origen: cuadernos digitalizados", _miles(po.get("cuaderno", 0)), f"{po.get('cuaderno', 0) / cal['total'] * 100:.0f}%"],
        ["Origen: pesado en balanza", _miles(po.get("pesado", 0)), f"{po.get('pesado', 0) / cal['total'] * 100:.0f}%"],
        ["Origen: estimado por el pescador", _miles(po.get("estimado", 0)), f"{po.get('estimado', 0) / cal['total'] * 100:.0f}%"],
    ], anchos=(90, 30, 20))
    pdf.ln(2)
    pdf.parrafo("Notas para quien lee este informe: (1) las cifras de meses antiguos vienen de cuadernos "
                "transcritos y pueden estar incompletas; (2) el informe no contiene datos individuales de "
                "embarcaciones ni zonas de pesca; (3) una baja en el desembarque de un mes no indica por sí sola "
                "menos esfuerzo: puede deberse a mal tiempo, vedas o menos salidas.", tam=9)
    return bytes(pdf.output())
