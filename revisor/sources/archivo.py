"""Importación de archivos descargados manualmente del SEACE / OECE / CONOSCE.

Formatos aceptados:
  * JSON OCDS (release package / record package) del portal de Contrataciones Abiertas.
  * CSV o XLSX con una fila por adjudicación (reportes de buena pro, CONOSCE,
    datos abiertos). Las columnas se detectan por nombre de forma flexible.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ..categorias import clasificar
from ..modelos import Adjudicacion
from ..tablas import a_fecha, a_monto, campo, leer_filas, solo_digitos
from .ocds import adjudicaciones_de_paquete, filtrar

COL_DESCRIPCION = ("descripcion_objeto", "descripcion_del_item", "descripcion", "objeto_contractual",
                   "objeto", "item", "sintesis")
COL_GANADOR = ("nombre_razon_social_ganador", "ganador", "postor_ganador", "razon_social_del_postor",
               "proveedor", "contratista", "razon_social", "postor", "adjudicatario")
COL_RUC = ("ruc_ganador", "ruc_postor", "ruc_proveedor", "ruc_contratista", "ruc_adjudicatario",
           "ruc_codigo_ganador", "ruc")
COL_ENTIDAD = ("entidad_convocante", "nombre_entidad", "entidad", "comprador")
COL_NOMENCLATURA = ("nomenclatura", "codigo_convocatoria", "nro_procedimiento", "proceso", "ocid")
COL_MONTO = ("monto_adjudicado", "monto_contratado", "monto_total", "valor_adjudicado", "monto")
COL_FECHA = ("fecha_buena_pro", "fecha_de_buena_pro", "fecha_otorgamiento", "fecha_adjudicacion",
             "fecha_consentimiento", "fecha")
COL_MONEDA = ("moneda",)
COL_URL = ("url", "enlace", "link")


def importar(ruta: Path | str, desde: date | None = None, hasta: date | None = None,
             contenido: bytes | None = None) -> list[Adjudicacion]:
    ruta = Path(ruta)
    if contenido is None:
        contenido = ruta.read_bytes()
    fuente = f"Archivo: {ruta.name}"
    if ruta.suffix.lower() == ".json":
        paquete = json.loads(contenido.decode("utf-8-sig"))
        return filtrar(adjudicaciones_de_paquete(paquete, desde, hasta, fuente=fuente))

    salida: list[Adjudicacion] = []
    for fila in leer_filas(ruta, contenido):
        descripcion = str(campo(fila, *COL_DESCRIPCION))
        entidad = str(campo(fila, *COL_ENTIDAD))
        categorias = clasificar(f"{descripcion} | {entidad}")
        if not categorias:
            continue
        ganador = str(campo(fila, *COL_GANADOR))
        if not ganador:
            continue  # sin buena pro todavía
        fecha = a_fecha(campo(fila, *COL_FECHA))
        if desde and fecha and fecha < desde:
            continue
        if hasta and fecha and fecha > hasta:
            continue
        for cat in categorias:
            salida.append(Adjudicacion(
                categoria=cat,
                nomenclatura=str(campo(fila, *COL_NOMENCLATURA)),
                entidad=entidad,
                descripcion=descripcion,
                ganador=ganador,
                ruc_ganador=solo_digitos(campo(fila, *COL_RUC))[-11:],
                monto=a_monto(campo(fila, *COL_MONTO)),
                moneda=str(campo(fila, *COL_MONEDA)) or "PEN",
                fecha_buena_pro=fecha,
                url=str(campo(fila, *COL_URL)),
                fuente=fuente,
            ))
    return filtrar(salida)
