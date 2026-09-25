"""Revisión automática diaria (GitHub Actions) → datos para la página web.

    python -m revisor.publicar --salida sitio/datos --dias 365

Consulta el SEACE (prod6), obtiene ganadores y contrataciones abiertas,
verifica el registro sanitario de cada ganador en DIGESA y escribe:
    <salida>/ultimo.json   datos que muestra la página
    <salida>/reporte.pdf   el mismo reporte en PDF
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .modelos import Adjudicacion, RegistroSanitario, ResultadoGanador
from .contactos import BuscadorContactos
from .pdf import generar_pdf
from .registro_sanitario import BaseRegistros
from .revisor import Reporte
from .sources import prod6
from .sources.ocds import filtrar


MUESTRA_REGISTROS = 15


def _iso(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _registro(r: RegistroSanitario) -> dict:
    d = {k: _iso(v) for k, v in asdict(r).items()}
    d["vigente"] = r.vigente
    return d


def _ganador(res: ResultadoGanador) -> dict:
    a, v = res.adjudicacion, res.verificacion
    return {
        "categoria": a.categoria, "nomenclatura": a.nomenclatura, "entidad": a.entidad,
        "descripcion": a.descripcion, "ganador": a.ganador, "ruc": a.ruc_ganador, "monto": a.monto,
        "moneda": a.moneda, "fechaBP": _iso(a.fecha_buena_pro), "url": a.url, "fuente": a.fuente,
        "contacto": a.contacto,
        # Algunas empresas tienen cientos de registros: se envían los relacionados
        # con el producto y una muestra del resto.
        "verif": {"estado": v.estado, "nota": v.nota, "totalRegistros": len(v.registros),
                  "registros": [_registro(r) for r in v.registros[:MUESTRA_REGISTROS]],
                  "relacionados": [_registro(r) for r in v.relacionados]},
    }


def _proxima(c: prod6.Contratacion) -> dict:
    return {
        "categoria": " · ".join(c.categorias), "nomenclatura": c.nomenclatura, "entidad": c.entidad,
        "descripcion": c.descripcion, "monto": None, "moneda": "PEN", "estado": c.estado,
        "fechaPub": _iso(c.fecha_publicacion), "fechaIniCot": _iso(c.inicio_cotizacion),
        "fechaOfertas": _iso(c.fin_cotizacion), "url": c.url, "fuente": "SEACE (contrataciones hasta 8 UIT)",
    }


def ejecutar(salida: Path, dias: int, verificar_digesa: bool = True) -> dict:
    avisos: list[str] = []
    cliente = prod6.ClienteSEACE()
    print(f"Consultando SEACE (últimos {dias} días)…")
    culminadas, abiertas = prod6.recolectar(cliente, dias=dias)
    print(f"  {len(culminadas)} culminadas y {len(abiertas)} abiertas de interés")
    adjs: list[Adjudicacion] = filtrar(prod6.ganadores(cliente, culminadas))
    print(f"  {len(adjs)} ganadores")

    base = BaseRegistros()
    if verificar_digesa:
        from .digesa import ConsultaDIGESA
        consulta = ConsultaDIGESA()
        for ruc in sorted({a.ruc_ganador for a in adjs if a.ruc_ganador}):
            try:
                for reg in consulta.por_ruc(ruc):
                    base.agregar(reg)
                print(f"  DIGESA {ruc}: {len(base.por_ruc.get(ruc, []))} registros")
            except Exception as exc:  # DIGESA caído o formato cambiado
                avisos.append(f"DIGESA no respondió para el RUC {ruc}: {exc}")
        base.archivos.append("Consulta en línea DIGESA (por RUC)")
    print("Buscando datos de contacto (OECE)…")
    buscador = BuscadorContactos()
    for a in adjs:
        if not a.ruc_ganador:
            continue
        regs = base.por_ruc.get(a.ruc_ganador, [])
        direccion = next((r.direccion for r in regs if r.direccion), "")
        try:
            a.contacto = buscador.buscar(a.ruc_ganador, direccion).a_dict()
        except Exception as exc:
            avisos.append(f"No se pudo obtener el contacto del RUC {a.ruc_ganador}: {exc}")
    resultados = []
    for a in adjs:
        v = base.verificar(a)
        resultados.append(ResultadoGanador(a, v))

    hoy = date.today()
    rep = Reporte(desde=hoy - timedelta(days=dias), hasta=hoy, resultados=resultados,
                  fuentes=["SEACE – buscador de contrataciones (prod6.seace.gob.pe)"], avisos=avisos,
                  base_registros=list(base.archivos))
    rep.resultados.sort(key=lambda r: r.adjudicacion.fecha_buena_pro or date.min, reverse=True)
    abiertas.sort(key=lambda c: c.fin_cotizacion or c.fecha_publicacion or datetime.min, reverse=True)

    datos = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "desde": _iso(rep.desde), "hasta": _iso(rep.hasta), "dias": dias,
        "fuentes": rep.fuentes, "avisos": avisos, "baseDigesa": rep.base_registros,
        "ganadores": [_ganador(r) for r in rep.resultados],
        "proximas": [_proxima(c) for c in abiertas],
    }
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "ultimo.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        (salida / "reporte.pdf").write_bytes(generar_pdf(rep, proximas=abiertas))
    except Exception as exc:  # los datos de la página se publican igual
        print(f"  ! No se pudo generar el PDF: {exc}")
    print(f"Listo: {len(datos['ganadores'])} ganadores, {len(datos['proximas'])} próximas → {salida}")
    return datos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", type=Path, default=Path("sitio/datos"))
    ap.add_argument("--dias", type=int, default=365)
    ap.add_argument("--sin-digesa", action="store_true")
    args = ap.parse_args(argv)
    ejecutar(args.salida, args.dias, verificar_digesa=not args.sin_digesa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
