"""Generación del reporte PDF descargable."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .modelos import CON_REGISTRO, SIN_REGISTRO
from .revisor import Reporte

VERDE = colors.HexColor("#1f7a3a")
ROJO = colors.HexColor("#b3261e")
GRIS = colors.HexColor("#6b6b6b")
AZUL = colors.HexColor("#1d3f73")


def _color_estado(estado: str) -> colors.Color:
    return VERDE if estado == CON_REGISTRO else ROJO if estado == SIN_REGISTRO else GRIS


def formato_monto(monto: float | None, moneda: str = "PEN") -> str:
    if monto is None:
        return "-"
    simbolo = "S/" if moneda in ("PEN", "S/", "SOLES", "") else moneda
    return f"{simbolo} {monto:,.2f}"


def generar_pdf(rep: Reporte, proximas: list | None = None) -> bytes:
    """proximas: contrataciones abiertas (objetos con categorias, nomenclatura, entidad,
    descripcion, estado, fecha_publicacion y fin_cotizacion)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="Revisor de licitaciones SEACE", author="Revisor de licitaciones",
    )
    est = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=est["Normal"], fontSize=8, leading=10)
    pequeno = ParagraphStyle("p", parent=normal, fontSize=7, leading=9, textColor=GRIS)
    h1 = ParagraphStyle("h1", parent=est["Title"], fontSize=16, textColor=AZUL, alignment=0)
    h2 = ParagraphStyle("h2", parent=est["Heading2"], fontSize=12, textColor=AZUL, spaceBefore=10,
                        keepWithNext=1)

    def p(texto: object, estilo=normal) -> Paragraph:
        return Paragraph(escape(str(texto or "")), estilo)

    rango = rep.desde.strftime("%d/%m/%Y")
    if rep.hasta != rep.desde:
        rango += " al " + rep.hasta.strftime("%d/%m/%Y")
    historia = [
        Paragraph("Ganadores de licitaciones: avena, arroz símil, arroz fortificado y Vaso de Leche", h1),
        p(f"Buena pro otorgada: {rango}  ·  Generado: {rep.generado:%d/%m/%Y %H:%M}"),
        p("Fuentes: " + ("; ".join(rep.fuentes) or "ninguna")),
        p("Base de registros sanitarios DIGESA: " + (", ".join(rep.base_registros) or "no cargada")),
    ]
    for aviso in rep.avisos:
        historia.append(p("Aviso: " + aviso, pequeno))

    conteo = rep.conteo()
    resumen = Table(
        [["Ganadores", "Con registro sanitario", "Sin registro sanitario", "No verificado"],
         [len(rep.resultados), conteo.get(CON_REGISTRO, 0), conteo.get(SIN_REGISTRO, 0),
          conteo.get("NO VERIFICADO", 0)]],
        colWidths=[5 * cm] * 4,
    )
    resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TEXTCOLOR", (1, 1), (1, 1), VERDE), ("TEXTCOLOR", (2, 1), (2, 1), ROJO),
    ]))
    historia += [Spacer(1, 8), resumen]

    anchos = [3.2 * cm, 4.2 * cm, 5.0 * cm, 4.6 * cm, 2.2 * cm, 2.6 * cm, 4.9 * cm]
    for categoria, resultados in rep.por_categoria().items():
        historia.append(Paragraph(f"{escape(categoria)} ({len(resultados)})", h2))
        if not resultados:
            historia.append(p("Sin ganadores en el periodo.", pequeno))
            continue
        filas = [[p(t) for t in ("Procedimiento", "Entidad", "Descripción", "Ganador / RUC",
                                 "Fecha B.P.", "Monto", "Registro sanitario")]]
        estilos = []
        for i, r in enumerate(resultados, start=1):
            a, v = r.adjudicacion, r.verificacion
            regs = v.relacionados or v.registros
            detalle = "<br/>".join(
                escape(f"{x.codigo} - {x.producto}{' (' + x.marca + ')' if x.marca else ''}"
                       f"{' vence ' + x.fecha_vencimiento.strftime('%d/%m/%Y') if x.fecha_vencimiento else ''}"
                       f"{' [VENCIDO/NO VIGENTE]' if x.vigente is False else ''}")
                for x in regs[:4]
            )
            if len(regs) > 4:
                detalle += f"<br/>… y {len(regs) - 4} más"
            color = _color_estado(v.estado).hexval()[2:]
            celda_rs = f'<font color="#{color}"><b>{escape(v.estado)}</b></font>'
            if detalle:
                celda_rs += "<br/>" + detalle
            if v.nota:
                celda_rs += f'<br/><font color="#6b6b6b">{escape(v.nota)}</font>'
            filas.append([
                p(a.nomenclatura), p(a.entidad), p(a.descripcion[:300]),
                Paragraph(f"<b>{escape(a.ganador)}</b><br/>RUC {escape(a.ruc_ganador or '-')}", normal),
                p(a.fecha_buena_pro.strftime("%d/%m/%Y") if a.fecha_buena_pro else "-"),
                p(formato_monto(a.monto, a.moneda)),
                Paragraph(celda_rs, normal),
            ])
            if i % 2 == 0:
                estilos.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f3f5f9")))
        tabla = Table(filas, colWidths=anchos, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde4f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            *estilos,
        ]))
        historia.append(tabla)

    if proximas is not None:
        historia.append(Paragraph(f"Próximas contrataciones ({len(proximas)})", h2))
        if not proximas:
            historia.append(p("No hay contrataciones abiertas de estos productos.", pequeno))
        else:
            fmt = lambda d: d.strftime("%d/%m/%Y %H:%M") if d else "-"
            filas = [[p(t) for t in ("Producto", "Procedimiento", "Entidad", "Descripción", "Estado",
                                     "Publicado", "Cierre de cotización")]]
            for c in proximas:
                filas.append([p(" · ".join(c.categorias)), p(c.nomenclatura), p(c.entidad),
                              p(c.descripcion[:300]), p(c.estado), p(fmt(c.fecha_publicacion)),
                              p(fmt(c.fin_cotizacion))])
            tabla = Table(filas, colWidths=[2.6 * cm, 3.4 * cm, 4.4 * cm, 8.2 * cm, 2.4 * cm, 2.6 * cm, 3.1 * cm],
                          repeatRows=1)
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde4f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]))
            historia.append(tabla)

    historia.append(Spacer(1, 12))
    historia.append(KeepTogether([p(
        "Nota: la verificación de registro sanitario se hace cruzando el RUC o razón social del "
        "ganador con la base de DIGESA cargada. Un ganador puede ofertar un producto cuyo titular "
        "del registro es otra empresa; confirme siempre con la oferta y la consulta oficial de DIGESA.",
        pequeno)]))

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(documento.pagesize[0] - 1.5 * cm, 0.8 * cm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
