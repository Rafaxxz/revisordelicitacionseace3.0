"""Orquestación: obtener ganadores, verificar registro sanitario y agrupar."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .categorias import CATEGORIAS
from .modelos import CON_REGISTRO, NO_VERIFICADO, SIN_REGISTRO, Adjudicacion, ResultadoGanador
from .registro_sanitario import BaseRegistros
from .sources import archivo, oece
from .sources.ocds import filtrar


@dataclass
class Reporte:
    desde: date
    hasta: date
    resultados: list[ResultadoGanador] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    base_registros: list[str] = field(default_factory=list)
    generado: datetime = field(default_factory=datetime.now)

    def por_categoria(self) -> dict[str, list[ResultadoGanador]]:
        grupos: dict[str, list[ResultadoGanador]] = {c: [] for c in CATEGORIAS}
        for r in self.resultados:
            grupos.setdefault(r.adjudicacion.categoria, []).append(r)
        for lista in grupos.values():
            lista.sort(key=lambda r: (r.adjudicacion.fecha_buena_pro or date.min), reverse=True)
        return grupos

    def conteo(self) -> dict[str, int]:
        c = {CON_REGISTRO: 0, SIN_REGISTRO: 0, NO_VERIFICADO: 0}
        for r in self.resultados:
            c[r.verificacion.estado] = c.get(r.verificacion.estado, 0) + 1
        return c


def revisar(
    desde: date,
    hasta: date | None = None,
    archivos: list[tuple[str, bytes | None]] | None = None,
    en_linea: bool = True,
    base: BaseRegistros | None = None,
    filtrar_fechas: bool = True,
) -> Reporte:
    """Ejecuta la revisión.

    archivos: lista de (nombre_o_ruta, contenido) de SEACE/OECE; contenido
    None lee la ruta del disco. filtrar_fechas=False toma todo el archivo
    (útil para los datos de demostración)."""
    hasta = hasta or desde
    rep = Reporte(desde=desde, hasta=hasta)
    adjs: list[Adjudicacion] = []

    if en_linea:
        try:
            nuevos = oece.descargar(desde, hasta)
            adjs += nuevos
            rep.fuentes.append(f"OECE Contrataciones Abiertas en línea ({len(nuevos)} ganadores)")
        except oece.ErrorFuente as exc:
            rep.avisos.append(str(exc))

    for nombre, contenido in archivos or []:
        try:
            nuevos = (archivo.importar(nombre, desde, hasta, contenido=contenido) if filtrar_fechas
                      else archivo.importar(nombre, contenido=contenido))
            adjs += nuevos
            rep.fuentes.append(f"{Path(nombre).name} ({len(nuevos)} ganadores)")
        except Exception as exc:  # archivo corrupto o formato desconocido
            rep.avisos.append(f"No se pudo leer {Path(nombre).name}: {exc}")

    base = base or BaseRegistros()
    rep.base_registros = list(base.archivos)
    if not base.cargada:
        rep.avisos.append("Sin base de registros sanitarios DIGESA: los ganadores quedan como NO VERIFICADO.")

    for adj in filtrar(adjs):
        rep.resultados.append(ResultadoGanador(adj, base.verificar(adj)))
    return rep
