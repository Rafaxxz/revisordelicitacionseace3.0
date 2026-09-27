"""Lectura del "Reporte de otorgamiento de buena pro" del SEACE (PDF dentro del ZIP
"Documentos de Otorgamiento de Buena Pro" de la ficha del procedimiento).

Formato (una sección por ítem), tal como sale al extraer el texto con diseño:

    Entidad convocante :     MUNICIPALIDAD DISTRITAL DE MANANTAY
    Nomenclatura :           LP-SM-1-2026-MDM-C-1
    Descripción del objeto : ADQUISICION DE INSUMOS ... (sigue en varias líneas)

    Nro. Item :  2        Cantidad Solicitada 58853.0   Valor Referencial : S/ 476,709.30  Resultado  Adjudicado
    Descripción del  ADQUISICION DE HOJUELAS ...        Unidad de Medida : Kilogramo ...
        Nombre o Razón Social          Integrante del Consorcio          Cantidad Adjudicada   Monto Adjudicado
        20609822806-CONSORCIO X        20609822806-EMPRESA A S.A.C.      58853.0               476709.30
                                       20600571916-EMPRESA B S.A.C.

Sin diseño (extract_text normal) el SEACE sale desordenado: los valores de la cabecera
aparecen antes que sus etiquetas. Por eso se lee con extraction_mode="layout" y la
tabla de postores por columnas; se mantiene la lectura en línea como respaldo.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional

_NUM = r"\d[\d,]*(?:\.\d+)?"
_RUC_NOMBRE = re.compile(r"(\d{11})\s*-\s*(.+)")
_PARES = re.compile(r"(\d{11})\s*-\s*(.+?)(?=\s+\d{11}\s*-|$)")
# Un par "RUC-NOMBRE" (el nombre termina donde empieza otro RUC o la cantidad).
_PAR = re.compile(r"(\d{11})\s*-\s*(.+?)(?=\s+\d{11}\s*-|\s+" + _NUM + r"\s+" + _NUM + r"(?:\s|$)|$)")
# Fila: [nombre del consorcio] RUC-NOMBRE [RUC-NOMBRE ...] cantidad monto
_FILA = re.compile(
    r"(?:(?P<cons>[A-ZÁÉÍÓÚÑ&][^\d]*?)\s+)?"
    r"(?P<pares>\d{11}\s*-\s*.+?(?:\s+\d{11}\s*-\s*.+?)*)"
    r"\s+(?P<cant>" + _NUM + r")\s+(?P<monto>" + _NUM + r")(?=\s|$)")
# Líneas del pie de página o encabezados repetidos dentro de la tabla de postores.
_RUIDO = re.compile(r"Usuario\s*:|Fecha de Generaci|Hora de Generaci|P[aá]gina \d+ de|REPORTE DE OTORGAMIENTO|"
                    r"Nombre o Raz|Integrante del Consorcio")


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
    except (TypeError, ValueError, AttributeError):
        return None


def _campo(texto: str, etiqueta: str) -> str:
    m = re.search(etiqueta + r"\s*:?[ \t]*(\S.*)", texto)
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
        desc = _descripcion_item(bloque)
        resultado = (re.search(r"Resultado\s*:?\s*([A-Za-zÁÉÍÓÚáéíóú ]+?)(?:\n|$)", bloque) or [None, ""])[1].strip()
        filas = _filas_por_columnas(bloque)
        if filas is None:
            filas = _filas_en_linea(bloque)
        for nombre, integrantes, cant, monto in filas:
            g = GanadorItem(item=item, descripcion=desc, resultado=resultado, ruc="", nombre="",
                            cantidad=_num(cant), monto=_num(monto))
            _poner_nombre(g, nombre, integrantes)
            rep.ganadores.append(g)
    return rep


def _poner_nombre(g: GanadorItem, nombre: str, integrantes: list[tuple[str, str]]) -> None:
    m = _RUC_NOMBRE.match(nombre)
    g.ruc, g.nombre = (m.group(1), m.group(2).strip(" -")) if m else ("", nombre.strip())
    g.consorcio, g.integrantes = "", integrantes
    if integrantes and (not m or re.match(r"CONSORCIO\b", g.nombre, re.I) or len(integrantes) > 1):
        g.consorcio = g.nombre


def corregir_nombres(rep: ReporteBuenaPro, texto_simple: str) -> None:
    """Cuando la descripción del ítem es larga, en el PDF se monta sobre la tabla de
    postores y, con diseño, el final de la descripción queda pegado al nombre del
    ganador ("… E.I.R.L.MINERALES"). En el texto sin diseño las filas salen limpias y en
    orden: se toma de ahí el nombre de la fila con la misma cantidad y monto."""
    limpias = []
    for tramo in re.split(r"Monto\s+Adjudicado", texto_simple)[1:]:
        tramo = re.split(r"Usuario\s*:|Nro\.\s*Item|Resultado|Descripci[oó]n del|Cantidad Adjudicada", tramo)[0]
        limpias += _filas_en_linea("Monto Adjudicado " + tramo)
    for g in rep.ganadores:
        for i, (nombre, integrantes, cant, monto) in enumerate(limpias):
            if _num(monto) == g.monto and _num(cant) == g.cantidad:
                _poner_nombre(g, nombre, integrantes or g.integrantes)
                del limpias[i]
                break


def _descripcion_item(bloque: str) -> str:
    lineas = bloque.splitlines()
    for i, linea in enumerate(lineas):
        m = re.search(r"Descripci[oó]n del\s+(\S.*?)(?:\s{2,}|\s+Unidad de Medida|$)", linea)
        if not m:
            continue
        partes, col = [m.group(1)], m.start(1)
        # Con diseño la descripción sigue en las líneas de abajo, en la misma columna;
        # la última puede venir pegada a "Nombre o Razón Social".
        for sig in lineas[i + 1:]:
            if "Nombre o Raz" in sig:
                resto = sig.split("Social", 1)[-1]
                if resto[:1].strip():
                    partes.append(re.split(r"\s{2,}", resto.strip())[0])
                break
            if sig[:col].strip() == "" and sig[col:col + 1].strip():
                partes.append(re.split(r"\s{2,}", sig[col:].strip())[0])
            else:
                break
        return " ".join(partes).strip()
    return ""


def _filas_por_columnas(bloque: str) -> Optional[list]:
    """Tabla de postores leída por columnas (texto con diseño). None si el texto no tiene columnas."""
    lineas = bloque.splitlines()
    enc = next((i for i, l in enumerate(lineas) if "Integrante del Consorcio" in l and "Monto Adjudicado" in l), None)
    if enc is None:
        return None
    h = lineas[enc]
    if not re.search(r"\S\s{2,}Integrante del Consorcio\s{2,}Cantidad Adjudicada\s{2,}Monto Adjudicado", h):
        return None  # todo en una línea: no hay columnas
    cols = [0, h.find("Integrante del Consorcio"), h.find("Cantidad Adjudicada"), h.find("Monto Adjudicado")]
    filas: list[list[str]] = []
    for linea in lineas[enc + 1:]:
        if not linea.strip() or _RUIDO.search(linea):
            continue
        celdas = ["", "", "", ""]
        for seg in re.finditer(r"\S+(?: \S+)*", linea):
            c = min(range(4), key=lambda k: abs(cols[k] - seg.start()))
            celdas[c] = (celdas[c] + " " + seg.group()).strip()
        # Empieza una fila nueva si trae un RUC-NOMBRE en la 1.ª columna o montos propios.
        nueva = bool(_RUC_NOMBRE.match(celdas[0])) or bool(celdas[3] and (not filas or filas[-1][3]))
        if nueva or not filas:
            filas.append(celdas)
        else:
            filas[-1] = [(a + " " + b).strip() for a, b in zip(filas[-1], celdas)]
    return [(nombre, [(r, n.strip(" -")) for r, n in _PARES.findall(integ)], cant, monto)
            for nombre, integ, cant, monto in filas if re.fullmatch(_NUM, monto)]


def _filas_en_linea(bloque: str) -> list:
    """Texto sin diseño: cada fila (o celda) en su propia línea."""
    cola = re.split(r"Monto\s+Adjudicado", bloque, maxsplit=1)
    filas = re.sub(r"\s+", " ", cola[1] if len(cola) > 1 else "")
    salida = []
    for m in _FILA.finditer(filas):
        pares = [(r, n.strip(" -")) for r, n in _PAR.findall(m.group("pares"))]
        consorcio = (m.group("cons") or "").strip()
        if consorcio:
            salida.append((consorcio, pares, m.group("cant"), m.group("monto")))
        else:
            salida.append((f"{pares[0][0]}-{pares[0][1]}", pares[1:], m.group("cant"), m.group("monto")))
    return salida


def texto_pdf(contenido: bytes, diseno: bool = True) -> str:
    from pypdf import PdfReader
    lector = PdfReader(io.BytesIO(contenido))
    if diseno:
        try:
            return "\n".join((p.extract_text(extraction_mode="layout") or "") for p in lector.pages)
        except TypeError:  # pypdf sin extraction_mode
            pass
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def leer_pdf(contenido: bytes) -> ReporteBuenaPro:
    rep = leer_texto(texto_pdf(contenido))
    if rep.ganadores:
        corregir_nombres(rep, texto_pdf(contenido, diseno=False))
    return rep


def leer_zip(contenido: bytes) -> ReporteBuenaPro:
    """Busca dentro del ZIP el PDF 'Reporte de otorgamiento de buena pro' y lo lee.
    Si no está, prueba con el resto de PDFs (p. ej. el acta)."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        pdfs = [n for n in z.namelist() if n.lower().endswith(".pdf")]
        pdfs.sort(key=lambda n: (0 if "reporte" in n.lower() else 1, n))
        mejor = ReporteBuenaPro()
        for nombre in pdfs:
            try:
                rep = leer_pdf(z.read(nombre))
            except Exception:
                continue
            if rep.ganadores:
                return rep
            mejor = mejor if mejor.nomenclatura else rep
        return mejor


def leer_archivo(contenido: bytes) -> ReporteBuenaPro:
    """El documento de buena pro suele ser un ZIP, pero puede venir como PDF suelto."""
    if contenido[:4] == b"%PDF":
        return leer_pdf(contenido)
    return leer_zip(contenido)
