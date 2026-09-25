"""Uso por consola (ideal para programarlo a diario con cron o el Programador de tareas).

    python -m revisor                      # hoy, consulta OECE en línea
    python -m revisor --fecha 2026-09-24   # un día concreto
    python -m revisor --desde 2026-09-01 --hasta 2026-09-24 --sin-linea --archivo reporte.xlsx
    python -m revisor --demo               # datos ficticios de prueba
    python -m revisor web                  # abre la interfaz web
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from .app import DIR_DEMO, DIR_DIGESA, DIR_SEACE, RAIZ, _archivos_carpeta
from .modelos import CON_REGISTRO, NO_VERIFICADO, SIN_REGISTRO
from .pdf import formato_monto, generar_pdf
from .registro_sanitario import BaseRegistros
from .revisor import revisar


def _fecha(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m revisor", description="Revisor diario de licitaciones SEACE")
    ap.add_argument("modo", nargs="?", choices=["revisar", "web"], default="revisar")
    ap.add_argument("--fecha", type=_fecha, help="día de buena pro (AAAA-MM-DD); por defecto hoy")
    ap.add_argument("--ayer", action="store_true", help="revisar el día de ayer")
    ap.add_argument("--desde", type=_fecha)
    ap.add_argument("--hasta", type=_fecha)
    ap.add_argument("--archivo", action="append", default=[], help="archivo SEACE/OECE (repetible)")
    ap.add_argument("--digesa", action="append", default=[], help="base DIGESA CSV/XLSX (repetible)")
    ap.add_argument("--sin-linea", action="store_true", help="no consultar el OECE en línea")
    ap.add_argument("--demo", action="store_true", help="usar datos ficticios de demostración")
    ap.add_argument("--pdf", type=Path, help="ruta del PDF (por defecto reportes/ganadores_FECHA.pdf)")
    args = ap.parse_args(argv)

    if args.modo == "web":
        from .app import main as web
        web()
        return 0

    dia = args.fecha or (date.today() - timedelta(days=1) if args.ayer else date.today())
    desde = args.desde or dia
    hasta = args.hasta or (args.desde and date.today()) or dia

    base = BaseRegistros()
    if args.demo:
        base.cargar_carpeta(DIR_DEMO / "digesa")
        archivos = _archivos_carpeta(DIR_DEMO / "seace")
    else:
        base.cargar_carpeta(DIR_DIGESA)
        archivos = _archivos_carpeta(DIR_SEACE)
    for ruta in args.digesa:
        base.cargar_archivo(ruta)
    archivos += [(ruta, None) for ruta in args.archivo]

    rep = revisar(desde, hasta, archivos=archivos, en_linea=not (args.sin_linea or args.demo), base=base,
                  filtrar_fechas=not args.demo)

    for aviso in rep.avisos:
        print("AVISO:", aviso)
    for cat, resultados in rep.por_categoria().items():
        print(f"\n== {cat} ({len(resultados)}) ==")
        for r in resultados:
            a, v = r.adjudicacion, r.verificacion
            print(f"  - {a.ganador} (RUC {a.ruc_ganador or '-'}) | {a.entidad} | "
                  f"{formato_monto(a.monto, a.moneda)} | {v.estado}")
            for x in (v.relacionados or v.registros)[:3]:
                print(f"      RS {x.codigo}: {x.producto}")
    c = rep.conteo()
    print(f"\nTotal: {len(rep.resultados)} ganadores | con RS {c[CON_REGISTRO]} | "
          f"sin RS {c[SIN_REGISTRO]} | no verificado {c[NO_VERIFICADO]}")

    salida = args.pdf
    if salida is None:
        nombre = f"ganadores_{desde:%Y%m%d}" + (f"_{hasta:%Y%m%d}" if hasta != desde else "")
        salida = RAIZ / "reportes" / f"{nombre}.pdf"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(generar_pdf(rep))
    print(f"PDF generado: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
