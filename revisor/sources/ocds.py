"""Conversión de releases OCDS (Contrataciones Abiertas - OECE) a adjudicaciones."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Iterator

from ..categorias import clasificar
from ..modelos import Adjudicacion
from ..tablas import a_fecha, a_monto, solo_digitos


def extraer_releases(paquete: object) -> Iterator[dict]:
    """Acepta un release, una lista, un release package o un record package."""
    if isinstance(paquete, list):
        for p in paquete:
            yield from extraer_releases(p)
        return
    if not isinstance(paquete, dict):
        return
    if "releases" in paquete and isinstance(paquete["releases"], list):
        yield from extraer_releases(paquete["releases"])
    elif "records" in paquete and isinstance(paquete["records"], list):
        for rec in paquete["records"]:
            if isinstance(rec, dict) and isinstance(rec.get("compiledRelease"), dict):
                yield rec["compiledRelease"]
            else:
                yield from extraer_releases(rec)
    elif "results" in paquete and isinstance(paquete["results"], list):
        yield from extraer_releases(paquete["results"])
    elif "ocid" in paquete:
        yield paquete


def _ruc(parte: dict) -> str:
    ident = parte.get("identifier") or {}
    for valor in (ident.get("id"), parte.get("id")):
        digitos = solo_digitos(valor)
        if len(digitos) >= 11:
            return digitos[-11:]
    return solo_digitos(ident.get("id") or parte.get("id"))


def adjudicaciones_de_release(
    release: dict, desde: date | None = None, hasta: date | None = None, fuente: str = "OCDS"
) -> list[Adjudicacion]:
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or {}
    textos = [tender.get("title", ""), tender.get("description", "")]
    textos += [i.get("description", "") for i in tender.get("items") or [] if isinstance(i, dict)]

    salida: list[Adjudicacion] = []
    for award in release.get("awards") or []:
        if not isinstance(award, dict):
            continue
        if (award.get("status") or "active") not in ("active", "pending", ""):
            continue
        fecha = a_fecha(award.get("date") or release.get("date"))
        if desde and (fecha is None or fecha < desde):
            continue
        if hasta and (fecha is None or fecha > hasta):
            continue
        textos_award = textos + [award.get("title", ""), award.get("description", "")]
        textos_award += [i.get("description", "") for i in award.get("items") or [] if isinstance(i, dict)]
        categorias = clasificar(" | ".join(str(t) for t in textos_award if t))
        if not categorias:
            continue
        valor = award.get("value") or {}
        for proveedor in award.get("suppliers") or [{}]:
            for cat in categorias:
                salida.append(
                    Adjudicacion(
                        categoria=cat,
                        nomenclatura=str(tender.get("id") or release.get("ocid", "")),
                        entidad=buyer.get("name", ""),
                        descripcion=str(tender.get("description") or tender.get("title") or award.get("description") or ""),
                        ganador=proveedor.get("name", "") or "(sin nombre)",
                        ruc_ganador=_ruc(proveedor),
                        monto=a_monto(valor.get("amount")),
                        moneda=valor.get("currency") or "PEN",
                        fecha_buena_pro=fecha,
                        url=release.get("url", "") or "",
                        fuente=fuente,
                    )
                )
    return salida


def adjudicaciones_de_paquete(
    paquete: object, desde: date | None = None, hasta: date | None = None, fuente: str = "OCDS"
) -> list[Adjudicacion]:
    salida: list[Adjudicacion] = []
    for rel in extraer_releases(paquete):
        salida.extend(adjudicaciones_de_release(rel, desde, hasta, fuente))
    return salida


def filtrar(adjs: Iterable[Adjudicacion]) -> list[Adjudicacion]:
    """Elimina duplicados (mismo procedimiento, ganador y categoría)."""
    vistos, salida = set(), []
    for a in adjs:
        clave = (a.categoria, a.nomenclatura, a.ruc_ganador or a.ganador, a.monto)
        if clave not in vistos:
            vistos.add(clave)
            salida.append(a)
    return salida
