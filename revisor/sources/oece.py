"""Descarga en línea desde el portal de Contrataciones Abiertas del OECE (ex OSCE).

El portal publica los datos del SEACE en el estándar OCDS. La URL y los
parámetros se pueden ajustar con variables de entorno por si el OECE cambia
su API:

    OECE_API_URL      (por defecto https://contratacionesabiertas.oece.gob.pe/api/v1/releases)
    OECE_MAX_PAGINAS  (por defecto 50)
"""
from __future__ import annotations

import os
from datetime import date

import requests

from ..modelos import Adjudicacion
from .ocds import adjudicaciones_de_paquete, filtrar

API_URL = os.environ.get(
    "OECE_API_URL", "https://contratacionesabiertas.oece.gob.pe/api/v1/releases"
)
MAX_PAGINAS = int(os.environ.get("OECE_MAX_PAGINAS", "50"))
TERMINOS = ["avena", "arroz fortificado", "simil arroz", "arroz simil", "vaso de leche"]


class ErrorFuente(RuntimeError):
    pass


def _siguiente(datos: object) -> str | None:
    if isinstance(datos, dict):
        links = datos.get("links") or {}
        if isinstance(links, dict) and links.get("next"):
            return links["next"]
        if datos.get("next"):
            return datos["next"]
    return None


def descargar(desde: date, hasta: date, sesion: requests.Session | None = None) -> list[Adjudicacion]:
    sesion = sesion or requests.Session()
    sesion.headers.setdefault("User-Agent", "revisor-licitaciones/1.0")
    salida: list[Adjudicacion] = []
    errores: list[str] = []
    for termino in TERMINOS:
        url: str | None = API_URL
        params: dict | None = {
            "q": termino,
            "date_from": desde.isoformat(),
            "date_to": hasta.isoformat(),
            "page": 1,
        }
        for _ in range(MAX_PAGINAS):
            try:
                resp = sesion.get(url, params=params, timeout=60)
                resp.raise_for_status()
                datos = resp.json()
            except (requests.RequestException, ValueError) as exc:
                errores.append(f"{termino}: {exc}")
                break
            nuevos = adjudicaciones_de_paquete(datos, desde, hasta, fuente="OECE en línea")
            salida.extend(nuevos)
            url = _siguiente(datos)
            if not url:
                break
            params = None  # el enlace "next" ya trae los parámetros
    if errores and not salida:
        raise ErrorFuente(
            "No se pudo consultar el OECE: " + "; ".join(errores[:3])
            + ". Descarga el archivo desde el portal y cárgalo manualmente."
        )
    return filtrar(salida)
