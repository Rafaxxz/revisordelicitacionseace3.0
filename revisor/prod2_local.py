"""Revisión de licitaciones grandes (SEACE prod2) desde TU PC.

    python -m revisor.prod2_local            # últimos 120 días
    python -m revisor.prod2_local --dias 30

Abre Chrome (visible), busca avena / arroz / vaso de leche en el buscador de
procedimientos, descarga los "Documentos de Otorgamiento de Buena Pro", lee
los ganadores y les busca registro sanitario (DIGESA) y contacto (OECE).
Al final junta estos resultados con los de la revisión automática diaria de
la página web y genera un solo PDF en la carpeta reportes/.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .modelos import Adjudicacion, RegistroSanitario, ResultadoGanador, Verificacion
from .publicar import enriquecer, escribir
from .revisor import Reporte
from .sources import prod2
from .sources.ocds import filtrar
from .sources.prod6 import Contratacion

RAIZ = Path(__file__).resolve().parent.parent
URL_DATOS_WEB = "https://rafaxxz.github.io/revisordelicitacionseace3.0/datos/ultimo.json"


def _f(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def datos_de_la_web(avisos: list[str]) -> tuple[list[ResultadoGanador], list[Contratacion]]:
    """Ganadores de la revisión automática diaria (contrataciones hasta 8 UIT)."""
    try:
        d = requests.get(URL_DATOS_WEB, timeout=30).json()
    except Exception as exc:
        avisos.append(f"No se pudieron traer los datos de la página web: {exc}")
        return [], []

    def reg(r):
        v = _f(r.get("fecha_vencimiento"))
        return RegistroSanitario(codigo=r["codigo"], producto=r.get("producto", ""), titular=r.get("titular", ""),
                                 ruc_titular=r.get("ruc_titular", ""), fecha_vencimiento=v.date() if v else None,
                                 direccion=r.get("direccion", ""))
    res = []
    for g in d.get("ganadores", []):
        fbp = _f(g.get("fechaBP"))
        a = Adjudicacion(categoria=g["categoria"], nomenclatura=g["nomenclatura"], entidad=g["entidad"],
                         descripcion=g["descripcion"], ganador=g["ganador"], ruc_ganador=g["ruc"], monto=g.get("monto"),
                         fecha_buena_pro=fbp.date() if fbp else None, url=g.get("url", ""), fuente=g.get("fuente", ""),
                         contacto=g.get("contacto"))
        v = g["verif"]
        res.append(ResultadoGanador(a, Verificacion(v["estado"], [reg(x) for x in v["registros"]],
                                                    [reg(x) for x in v["relacionados"]], v.get("nota", ""))))
    prox = [Contratacion(id=0, nomenclatura=p["nomenclatura"], entidad=p["entidad"], descripcion=p["descripcion"],
                         objeto="Bien", estado=p.get("estado", ""), categorias=p["categoria"].split(" · "),
                         fecha_publicacion=_f(p.get("fechaPub")), inicio_cotizacion=_f(p.get("fechaIniCot")),
                         fin_cotizacion=_f(p.get("fechaOfertas")), url=p.get("url", ""), fuente=p.get("fuente", ""))
            for p in d.get("proximas", [])]
    return res, prox


def abrir_navegador(p, perfil: Path):
    """Chrome instalado en la PC (mejor para el reCAPTCHA); si no, el Chromium de Playwright."""
    opciones = dict(headless=False, accept_downloads=True, viewport={"width": 1300, "height": 850})
    for canal in ("chrome", "msedge", None):
        try:
            if canal:
                return p.chromium.launch_persistent_context(str(perfil), channel=canal, **opciones)
            return p.chromium.launch_persistent_context(str(perfil), **opciones)
        except Exception:
            continue
    raise RuntimeError("No se pudo abrir Chrome. Ejecuta: python -m playwright install chromium")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=120, help="publicados en los últimos N días (por defecto 120)")
    ap.add_argument("--sin-web", action="store_true", help="no incluir la revisión automática de la página")
    ap.add_argument("--salida", type=Path, default=RAIZ / "reportes")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright

    avisos: list[str] = []
    cache = prod2.Cache(args.salida / "prod2_cache.json")
    with sync_playwright() as p:
        contexto = abrir_navegador(p, args.salida / "perfil_navegador")
        page = contexto.pages[0] if contexto.pages else contexto.new_page()
        robot = prod2.RobotSEACE(page, args.salida / "diagnostico")
        try:
            adjs, pendientes = prod2.recolectar(robot, cache, dias=args.dias)
        finally:
            contexto.close()

    adjs = filtrar(adjs)
    print(f"\n{len(adjs)} ganadores en licitaciones; {len(pendientes)} procesos aún sin buena pro.")
    resultados, base = enriquecer(adjs, avisos)
    fuentes = [f"{prod2.FUENTE} – revisado desde esta PC"]
    if not args.sin_web:
        web_res, web_prox = datos_de_la_web(avisos)
        resultados += web_res
        pendientes += web_prox
        fuentes.append("SEACE – contrataciones hasta 8 UIT (revisión automática de la página)")

    hoy = date.today()
    rep = Reporte(desde=hoy - timedelta(days=args.dias), hasta=hoy, resultados=resultados, fuentes=fuentes,
                  avisos=avisos, base_registros=list(base.archivos) or ["Consulta en línea DIGESA (por RUC)"])
    nombre = f"ganadores_{hoy:%Y%m%d}"
    escribir(args.salida, rep, pendientes, args.dias, nombre_json=f"{nombre}.json", nombre_pdf=f"{nombre}.pdf")
    print(f"\nPDF: {args.salida / (nombre + '.pdf')}")
    print(f"Datos para la página (botón 'Revisar un archivo'): {args.salida / (nombre + '.json')}")
    if (args.salida / "diagnostico").exists() and any((args.salida / "diagnostico").iterdir()):
        print(f"Hubo pasos con problemas: envía la carpeta {args.salida / 'diagnostico'} para ajustar el robot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
