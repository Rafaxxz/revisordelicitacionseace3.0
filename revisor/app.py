"""Interfaz web: python -m revisor.app  →  http://127.0.0.1:5000"""
from __future__ import annotations

import io
import os
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import Flask, abort, render_template, request, send_file

from .categorias import CATEGORIAS
from .modelos import CON_REGISTRO, NO_VERIFICADO, SIN_REGISTRO
from .pdf import formato_monto, generar_pdf
from .registro_sanitario import URL_CONSULTA_DIGESA, BaseRegistros
from .revisor import Reporte, revisar

RAIZ = Path(__file__).resolve().parent.parent
DIR_SEACE = RAIZ / "data" / "seace"
DIR_DIGESA = RAIZ / "data" / "digesa"
DIR_DEMO = RAIZ / "data" / "demo"
EXT_SEACE = (".csv", ".txt", ".xlsx", ".xlsm", ".json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
_REPORTES: dict[str, Reporte] = {}


def _fecha(valor: str | None, defecto: date) -> date:
    try:
        return datetime.strptime(valor or "", "%Y-%m-%d").date()
    except ValueError:
        return defecto


def _archivos_carpeta(carpeta: Path) -> list[tuple[str, bytes | None]]:
    if not carpeta.is_dir():
        return []
    return [(str(r), None) for r in sorted(carpeta.iterdir()) if r.suffix.lower() in EXT_SEACE]


@app.context_processor
def _utilidades():
    return dict(formato_monto=formato_monto, CON_REGISTRO=CON_REGISTRO,
                SIN_REGISTRO=SIN_REGISTRO, NO_VERIFICADO=NO_VERIFICADO,
                URL_CONSULTA_DIGESA=URL_CONSULTA_DIGESA, CATEGORIAS=CATEGORIAS)


@app.get("/")
def inicio():
    hoy = date.today()
    return render_template("index.html", reporte=None, rid=None, desde=hoy, hasta=hoy,
                           en_linea=True, demo=False)


@app.post("/revisar")
def ejecutar():
    hoy = date.today()
    desde = _fecha(request.form.get("desde"), hoy)
    hasta = max(_fecha(request.form.get("hasta"), desde), desde)
    en_linea = bool(request.form.get("en_linea"))
    demo = bool(request.form.get("demo"))

    base = BaseRegistros()
    if demo:
        base.cargar_carpeta(DIR_DEMO / "digesa")
        archivos = _archivos_carpeta(DIR_DEMO / "seace")
        en_linea = False
    else:
        base.cargar_carpeta(DIR_DIGESA)
        archivos = _archivos_carpeta(DIR_SEACE)
    for f in request.files.getlist("digesa"):
        if f and f.filename:
            base.cargar_archivo(f.filename, f.read())
    for f in request.files.getlist("seace"):
        if f and f.filename:
            archivos.append((f.filename, f.read()))

    rep = revisar(desde, hasta, archivos=archivos, en_linea=en_linea, base=base,
                  filtrar_fechas=not demo)
    rid = uuid.uuid4().hex
    _REPORTES[rid] = rep
    while len(_REPORTES) > 20:
        _REPORTES.pop(next(iter(_REPORTES)))
    return render_template("index.html", reporte=rep, rid=rid, desde=desde, hasta=hasta,
                           en_linea=en_linea, demo=demo)


@app.get("/pdf/<rid>")
def descargar_pdf(rid: str):
    rep = _REPORTES.get(rid)
    if rep is None:
        abort(404, "El reporte expiró; vuelve a ejecutar la revisión.")
    nombre = f"ganadores_{rep.desde:%Y%m%d}"
    if rep.hasta != rep.desde:
        nombre += f"_{rep.hasta:%Y%m%d}"
    return send_file(io.BytesIO(generar_pdf(rep)), mimetype="application/pdf",
                     as_attachment=True, download_name=nombre + ".pdf")


def main() -> None:
    puerto = int(os.environ.get("PORT", "5000"))
    print(f"Revisor de licitaciones en http://127.0.0.1:{puerto}")
    app.run(host="127.0.0.1", port=puerto, debug=False)


if __name__ == "__main__":
    main()
