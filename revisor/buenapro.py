"""Lectura del "Reporte de otorgamiento de buena pro" del SEACE (PDF dentro del ZIP
"Documentos de Otorgamiento de Buena Pro" de la ficha del procedimiento).

Formato (una sección por ítem):

    Nro. Item :  1        Cantidad Solicitada 67000.0   Valor Referencial : S/ 227,800.00  Resultado Adjudicado
    Descripción del  HENO DE ALFALFA Y/O AVENA - APURIMAC   Unidad de Medida : Kilogramo ...
    Nombre o Razón Social | Integrante del Consorcio | Cantidad Adjudicada | Monto Adjudicado
    10428536890-TICONA MENDEZ NESTOR FAUSTO                  67000.0          227800
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional

_NUM = r"\d[\d,]*(?:\.\d+)?"
# Un par "RUC-NOMBRE" (el nombre termina donde empieza otro RUC o la cantidad).
_PAR = re.compile(r"(\d{11})\s*-\s*(.+?)(?=\s+\d{11}\s*-|\s+" + _NUM + r"\s+" + _NUM + r"(?:\s|$)|$)")
# Fila: [nombre del consorcio] RUC-NOMBRE [RUC-NOMBRE ...] cantidad monto
_FILA = re.compile(
    r"(?:(?P<cons>[A-ZÁÉÍÓÚÑ&][^\d]*?)\s+)?"
    r"(?P<pares>\d{11}\s*-\s*.+?(?:\s+\d{11}\s*-\s*.+?)*)"
    r"\s+(?P<cant>" + _NUM + r")\s+(?P<monto>" + _NUM + r")(?=\s|$)")


@dataclass
class GanadorItem:
    item: str
    descripcion: str
    resultado: str
    ruc: str
    nombre: str
    consorcio: str = ""
    integrantes: list[tuple[str, str]] = field(default_factory=list)
    cantidad: Optional[float] = None
    monto: Optional[float] = None


@dataclass
class ReporteBuenaPro:
    entidad: str = ""
    nomenclatura: str = ""
    descripcion: str = ""
    ganadores: list[GanadorItem] = field(default_factory=list)


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _campo(texto: str, etiqueta: str) -> str:
    m = re.search(etiqueta + r"\s*:?\s*(.+)", texto)
    return m.group(1).strip() if m else ""


def leer_texto(texto: str) -> ReporteBuenaPro:
    rep = ReporteBuenaPro(
        entidad=_campo(texto, r"Entidad convocante"),
        nomenclatura=_campo(texto, r"Nomenclatura"),
    )
    m = re.search(r"Descripci[oó]n del objeto\s*:\s*(.+?)(?=\n\s*Nro\. Item|\Z)", texto, re.S)
    rep.descripcion = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    bloques = re.split(r"(?=Nro\.\s*Item\s*:)", texto)
    for bloque in bloques[1:]:
        item = (re.search(r"Nro\.\s*Item\s*:\s*(\d+)", bloque) or [None, ""])[1]
        desc = re.search(r"Descripci[oó]n del\s+(.+?)(?:\s{2,}|\s+Unidad de Medida|\n)", bloque)
        resultado = (re.search(r"Resultado\s*:?\s*([A-Za-zÁÉÍÓÚáéíóú ]+?)(?:\n|$)", bloque) or [None, ""])[1].strip()
        # Solo la parte después del encabezado de la tabla de postores, en una sola línea
        # (según el PDF, cada fila o cada celda sale en su propia línea).
        cola = re.split(r"Monto\s+Adjudicado", bloque, maxsplit=1)
        filas = re.sub(r"\s+", " ", cola[1] if len(cola) > 1 else "")
        for m in _FILA.finditer(filas):
            pares = [(r, n.strip(" -")) for r, n in _PAR.findall(m.group("pares"))]
            consorcio = (m.group("cons") or "").strip()
            g = GanadorItem(item=item, descripcion=(desc.group(1).strip() if desc else ""),
                            resultado=resultado, ruc=pares[0][0], nombre=pares[0][1],
                            cantidad=_num(m.group("cant")), monto=_num(m.group("monto")))
            if consorcio:
                g.consorcio, g.nombre, g.ruc, g.integrantes = consorcio, consorcio, "", pares
            elif len(pares) > 1:
                g.integrantes = pares[1:]
            rep.ganadores.append(g)
    return rep


def texto_pdf(contenido: bytes) -> str:
    from pypdf import PdfReader
    lector = PdfReader(io.BytesIO(contenido))
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def leer_zip(contenido: bytes) -> ReporteBuenaPro:
    """Busca dentro del ZIP el PDF 'Reporte de otorgamiento de buena pro' y lo lee.
    Si no está, prueba con el resto de PDFs (p. ej. el acta)."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        pdfs = [n for n in z.namelist() if n.lower().endswith(".pdf")]
        pdfs.sort(key=lambda n: (0 if "reporte" in n.lower() else 1, n))
        mejor = ReporteBuenaPro()
        for nombre in pdfs:
            try:
                rep = leer_texto(texto_pdf(z.read(nombre)))
            except Exception:
                continue
            if rep.ganadores:
                return rep
            mejor = mejor if mejor.nomenclatura else rep
        return mejor
