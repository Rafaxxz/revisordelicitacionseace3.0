"""Clasificación de procedimientos por producto de interés."""
from __future__ import annotations

import re
import unicodedata

AVENA = "Avena"
ARROZ_SIMIL = "Arroz símil"
ARROZ_FORTIFICADO = "Arroz fortificado"
VASO_DE_LECHE = "Vaso de Leche"

CATEGORIAS = [AVENA, ARROZ_SIMIL, ARROZ_FORTIFICADO, VASO_DE_LECHE]

# Expresiones sobre texto normalizado (minúsculas, sin tildes).
_PATRONES: dict[str, list[str]] = {
    ARROZ_SIMIL: [r"\bsimil(es)?\b.{0,40}\barroz\b", r"\barroz\b.{0,40}\bsimil(es)?\b"],
    ARROZ_FORTIFICADO: [r"\barroz\b.{0,40}\bfortificad[oa]s?\b"],
    VASO_DE_LECHE: [r"\bvaso\s+de\s+leche\b", r"\bp\.?\s?v\.?\s?l\.?\b"],
    AVENA: [r"\bavena\b"],
}

# Palabras que deben aparecer en el nombre del producto de un registro
# sanitario para considerarlo "relacionado" con la categoría.
PALABRAS_PRODUCTO: dict[str, list[str]] = {
    AVENA: ["avena"],
    ARROZ_SIMIL: ["simil", "arroz"],
    ARROZ_FORTIFICADO: ["arroz"],
    VASO_DE_LECHE: ["leche", "avena", "hojuela", "cereal", "enriquecid", "fortificad", "mezcla"],
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


def clasificar(texto: str) -> list[str]:
    """Devuelve las categorías que coinciden con el texto del procedimiento.

    Un mismo procedimiento puede pertenecer a varias (p. ej. "avena para el
    Programa del Vaso de Leche")."""
    t = normalizar(texto)
    encontradas = [
        cat for cat, patrones in _PATRONES.items() if any(re.search(p, t) for p in patrones)
    ]
    # "arroz fortificado símil" es símil, no arroz fortificado a secas.
    if ARROZ_SIMIL in encontradas and ARROZ_FORTIFICADO in encontradas:
        encontradas.remove(ARROZ_FORTIFICADO)
    return [c for c in CATEGORIAS if c in encontradas]


def producto_relacionado(categoria: str, nombre_producto: str) -> bool:
    t = normalizar(nombre_producto)
    palabras = PALABRAS_PRODUCTO.get(categoria, [])
    if categoria == ARROZ_SIMIL:
        return all(p in t for p in palabras)
    return any(p in t for p in palabras)
