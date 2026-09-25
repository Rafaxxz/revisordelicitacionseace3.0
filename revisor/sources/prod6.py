"""SEACE – buscador público de contrataciones (prod6.seace.gob.pe).

API JSON pública del SEACE nuevo, sin captcha:
  GET  /v1/s8uit-services/buscadorpublico/contrataciones/buscador
       ?anio=AAAA&palabra_clave=...&lista_estado_contrato=N&orden=2&page=P&page_size=100
  GET  /v1/s8uit-services/buscadorpublico/contrataciones/listar-completo?id_contrato=ID

Estados (idEstadoContrato): 2 Vigente, 3 En Evaluación, 4 Culminado.
El ganador está en el detalle, por ítem: uitContratoItemProjectionList[] con
codRuc, nomRazonSocial, precioTotal y nomEstadoCotiza == "ADJUDICADO".

El SEACE bloquea algunas IPs extranjeras (prod2, OECE), pero prod6 responde
desde GitHub Actions.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

import requests

from ..categorias import AVENA, VASO_DE_LECHE, clasificar, normalizar
from ..modelos import Adjudicacion

BASE = "https://prod6.seace.gob.pe/v1/s8uit-services/buscadorpublico/contrataciones"
URL_FICHA = "https://prod6.seace.gob.pe/buscador-publico/contrataciones/{id}"
TERMINOS = ["avena", "arroz", "simil", "vaso de leche", "leche", "hojuela", "cereal"]
ESTADOS_ABIERTOS = {2: "Vigente", 3: "En Evaluación"}
CULMINADO = 4

# Productos que no son alimento para personas.
_EXCLUIR = re.compile(r"\b(heno|forraje|pasto|animal(es)?|capibara|caball|ganado|semilla|aves|cuy(es)?|mascota)\b")
# Para "Vaso de Leche" solo interesan los insumos alimenticios del programa.
_ALIMENTO_PVL = re.compile(r"\b(leche|avena|hojuela|cereal|alimento|alimentari|insumo|enriquecid|fortificad|"
                           r"mezcla|quinua|kiwicha|trigo|arroz|harina|producto)s?\b")
_NO_ALIMENTO_PVL = re.compile(r"\b(servicio|alquiler|tinta|menaje|refaccion|mantenimiento|impresion|utiles|"
                              r"camioneta|combustible|asesoria|consultoria|kit|pintura)\b")


@dataclass
class Contratacion:
    id: int
    nomenclatura: str
    entidad: str
    descripcion: str
    objeto: str
    estado: str
    categorias: list[str]
    fecha_publicacion: Optional[datetime] = None
    inicio_cotizacion: Optional[datetime] = None
    fin_cotizacion: Optional[datetime] = None
    url: str = ""
    items: list[dict] = field(default_factory=list)


def _fecha(s: object) -> Optional[datetime]:
    try:
        dt = datetime.strptime(str(s).strip(), "%d/%m/%Y %H:%M:%S")
    except (TypeError, ValueError):
        return None
    # El SEACE a veces trae años corruptos (2052, 4202...).
    return dt if 2000 <= dt.year <= date.today().year + 2 else None


def categorias_de(descripcion: str, objeto: str = "") -> list[str]:
    t = normalizar(descripcion)
    if _EXCLUIR.search(t):
        return []
    cats = clasificar(descripcion)
    if VASO_DE_LECHE in cats:
        es_bien = not objeto or normalizar(objeto) == "bien"
        if not es_bien or _NO_ALIMENTO_PVL.search(t) or not _ALIMENTO_PVL.search(t):
            cats.remove(VASO_DE_LECHE)
    return cats


class ClienteSEACE:
    def __init__(self, sesion: requests.Session | None = None, pausa: float = 0.3) -> None:
        self.s = sesion or requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-PE,es;q=0.9",
            "Referer": "https://prod6.seace.gob.pe/",
        })
        self.pausa = pausa

    def _get(self, ruta: str, params: dict) -> dict:
        ultimo: Exception | None = None
        for intento in range(3):
            try:
                r = self.s.get(f"{BASE}/{ruta}", params=params, timeout=60)
                r.raise_for_status()
                time.sleep(self.pausa)
                return r.json()
            except (requests.RequestException, ValueError) as exc:
                ultimo = exc
                time.sleep(2 * (intento + 1))
        raise RuntimeError(f"SEACE no respondió ({ruta}): {ultimo}")

    def buscar(self, termino: str, estado: int, desde: date | None = None,
               max_paginas: int = 30) -> Iterable[dict]:
        """Resultados más recientes primero; corta al pasar la fecha `desde`."""
        for pagina in range(1, max_paginas + 1):
            datos = self._get("buscador", {
                "anio": date.today().year, "palabra_clave": termino,
                "lista_estado_contrato": estado, "orden": 2, "page": pagina, "page_size": 100,
            })
            filas = datos.get("data") or []
            for f in filas:
                yield f
            total = (datos.get("pageable") or {}).get("totalElements") or 0
            if not filas or pagina * 100 >= total:
                return
            ultima = _fecha(filas[-1].get("fecPublica"))
            if desde and ultima and ultima.date() < desde:
                return

    def detalle(self, id_contrato: int) -> dict:
        return self._get("listar-completo", {"id_contrato": id_contrato})


def _a_contratacion(fila: dict) -> Optional[Contratacion]:
    desc = fila.get("desObjetoContrato") or ""
    cats = categorias_de(desc, fila.get("nomObjetoContrato") or "")
    if not cats:
        return None
    return Contratacion(
        id=fila["idContrato"],
        nomenclatura=fila.get("desContratacion") or "",
        entidad=fila.get("nomEntidad") or "",
        descripcion=re.sub(r"\s+", " ", desc).strip(),
        objeto=fila.get("nomObjetoContrato") or "",
        estado=fila.get("nomEstadoContrato") or "",
        categorias=cats,
        fecha_publicacion=_fecha(fila.get("fecPublica")),
        inicio_cotizacion=_fecha(fila.get("fecIniCotizacion")),
        fin_cotizacion=_fecha(fila.get("fecFinCotizacion")),
        url=URL_FICHA.format(id=fila["idContrato"]),
    )


def recolectar(cliente: ClienteSEACE, dias: int = 30, terminos: list[str] = TERMINOS,
               log=print) -> tuple[list[Contratacion], list[Contratacion]]:
    """Devuelve (culminadas en los últimos `dias`, abiertas: vigentes o en evaluación)."""
    desde = date.today() - timedelta(days=dias)
    culminadas: dict[int, Contratacion] = {}
    abiertas: dict[int, Contratacion] = {}
    for termino in terminos:
        for estado, destino, limite in ((CULMINADO, culminadas, desde), (2, abiertas, None), (3, abiertas, None)):
            n = 0
            for fila in cliente.buscar(termino, estado, desde=limite):
                c = _a_contratacion(fila)
                if not c or c.id in destino:
                    continue
                if limite and c.fecha_publicacion and c.fecha_publicacion.date() < limite:
                    continue
                destino[c.id] = c
                n += 1
            log(f"  SEACE '{termino}' estado {estado}: {n} nuevas")
    return list(culminadas.values()), list(abiertas.values())


def ganadores(cliente: ClienteSEACE, contrataciones: list[Contratacion], log=print) -> list[Adjudicacion]:
    salida: list[Adjudicacion] = []
    for c in contrataciones:
        try:
            det = cliente.detalle(c.id)
        except RuntimeError as exc:
            log(f"  ! {exc}")
            continue
        items = det.get("uitContratoItemProjectionList") or []
        c.items = items
        etapas = det.get("uitContratoEtapaProjectionList") or []
        cierre = max((f for f in (_fecha(e.get("fecFin")) for e in etapas) if f), default=None)
        # Agrupa por proveedor ganador (un proveedor puede ganar varios ítems).
        por_ruc: dict[str, dict] = {}
        for it in items:
            if normalizar(it.get("nomEstadoCotiza") or "") != "adjudicado" or not it.get("codRuc"):
                continue
            g = por_ruc.setdefault(it["codRuc"], {"nombre": it.get("nomRazonSocial") or "", "monto": 0.0, "items": []})
            g["monto"] += float(it.get("precioTotal") or 0)
            g["items"].append(it.get("descripcionItem") or it.get("nomCubso") or "")
        for ruc, g in por_ruc.items():
            for cat in c.categorias:
                salida.append(Adjudicacion(
                    categoria=cat, nomenclatura=c.nomenclatura, entidad=c.entidad,
                    descripcion=c.descripcion + (f" — Ítems: {'; '.join(dict.fromkeys(g['items']))}" if g["items"] else ""),
                    ganador=g["nombre"], ruc_ganador=ruc, monto=round(g["monto"], 2), moneda="PEN",
                    fecha_buena_pro=(cierre or c.fin_cotizacion or c.fecha_publicacion).date()
                    if (cierre or c.fin_cotizacion or c.fecha_publicacion) else None,
                    url=c.url, fuente="SEACE (contrataciones hasta 8 UIT)",
                ))
        if not por_ruc:
            estados = {normalizar(i.get("nomEstadoCotiza") or "") for i in items}
            log(f"  {c.nomenclatura}: sin adjudicado ({', '.join(sorted(e for e in estados if e)) or 'sin ítems'})")
    return salida


__all__ = ["ClienteSEACE", "Contratacion", "recolectar", "ganadores", "categorias_de", "AVENA"]
