"""Genera un PDF con el mismo diseño del 'Reporte de otorgamiento de buena pro' del SEACE (para pruebas)."""
import io, zipfile
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, TableStyle
from reportlab.lib.styles import getSampleStyleSheet


def reporte_pdf(items, consorcio=False) -> bytes:
    buf = io.BytesIO(); st = getSampleStyleSheet()
    h = [Paragraph("REPORTE DE OTORGAMIENTO DE BUENA PRO", st["Title"]),
         Table([["Entidad convocante :", "PROGRAMA DE DESARROLLO PRODUCTIVO AGRARIO RURAL - AGRO RURAL"],
                ["Nomenclatura :", "DIRECTA-DIRECTA-18-2026-MIDAGRI-AGRORUR-1"],
                ["Nro. de convocatoria :", "1"], ["Objeto de contratación :", "Bien"],
                ["Descripción del objeto :", "ADQUISICIÓN DE HOJUELA DE AVENA PARA EL PROGRAMA DEL VASO DE LECHE"]])]
    for n, (desc, filas) in enumerate(items, 1):
        h += [Spacer(1, 10), Table([
            ["Nro. Item :", str(n), "Cantidad Solicitada", "67000.0", "Valor Referencial :", "S/ 227,800.00", "Resultado", "Adjudicado"],
            ["Descripción del", desc, "Unidad de Medida :", "Kilogramo", "Cantidad Desierta :", "0.0", "", ""]])]
        t = Table([["Nombre o Razón Social", "Integrante del Consorcio", "Cantidad Adjudicada", "Monto Adjudicado"]] + filas,
                  colWidths=[200, 150, 90, 90])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.orange), ("GRID", (0, 0), (-1, -1), .5, colors.black),
                               ("FONTSIZE", (0, 0), (-1, -1), 7)]))
        h.append(t)
    SimpleDocTemplate(buf, pagesize=A4).build(h)
    return buf.getvalue()


def zip_bp(pdf: bytes) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("0Acta de otorgamiento de buena pro.pdf", b"%PDF-1.4 vacio")
        z.writestr("1Reporte de otorgamiento de buena pro.pdf", pdf)
    return b.getvalue()
