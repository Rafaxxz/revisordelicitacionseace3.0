"""Verificación de registro sanitario (DIGESA) de los ganadores.

DIGESA publica la relación de registros sanitarios de alimentos
industrializados (portal de datos abiertos / consulta de registros). Descarga
ese archivo (CSV o XLSX) y colócalo en ``data/digesa/`` o súbelo desde la web.
El revisor cruza cada ganador por RUC y, si no hay RUC, por razón social.
"""
from __future__ import annotations

import re
from pathlib import Path

from .categorias import normalizar, producto_relacionado
from .modelos import (CON_REGISTRO, NO_VERIFICADO, SIN_REGISTRO, Adjudicacion,
                      RegistroSanitario, Verificacion)
from .tablas import a_fecha, campo, leer_filas, solo_digitos

URL_CONSULTA_DIGESA = "https://www.digesa.minsa.gob.pe/"

COL_CODIGO = ("registro_sanitario", "nro_registro", "numero_registro", "n_registro", "codigo_registro",
              "registro", "codigo_rs")
COL_PRODUCTO = ("nombre_producto", "producto", "descripcion_producto", "denominacion")
COL_MARCA = ("marca",)
COL_TITULAR = ("titular", "razon_social", "empresa", "fabricante", "solicitante")
COL_RUC = ("ruc_titular", "ruc_empresa", "ruc")
COL_VENCE = ("fecha_vencimiento", "vencimiento", "fecha_vigencia", "vigencia", "fecha_fin")
COL_ESTADO = ("estado", "situacion")

_SUFIJOS = r"\b(s\.?\s?a\.?\s?c\.?|s\.?\s?a\.?\s?a\.?|s\.?\s?a\.?|e\.?\s?i\.?\s?r\.?\s?l\.?|s\.?\s?r\.?\s?l\.?|s\.?\s?c\.?\s?r\.?\s?l\.?|sociedad anonima cerrada|sociedad anonima|empresa individual de responsabilidad limitada)\s*$"


def normalizar_empresa(nombre: str) -> str:
    t = normalizar(nombre).replace(",", " ")
    t = re.sub(_SUFIJOS, "", t).strip()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class BaseRegistros:
    def __init__(self) -> None:
        self.por_ruc: dict[str, list[RegistroSanitario]] = {}
        self.por_nombre: dict[str, list[RegistroSanitario]] = {}
        self.archivos: list[str] = []
        self.total = 0

    @property
    def cargada(self) -> bool:
        return self.total > 0

    def agregar(self, reg: RegistroSanitario) -> None:
        if reg.ruc_titular:
            self.por_ruc.setdefault(reg.ruc_titular, []).append(reg)
        if reg.titular:
            self.por_nombre.setdefault(normalizar_empresa(reg.titular), []).append(reg)
        self.total += 1

    def cargar_archivo(self, ruta: Path | str, contenido: bytes | None = None) -> int:
        ruta = Path(ruta)
        n = 0
        for fila in leer_filas(ruta, contenido):
            codigo = str(campo(fila, *COL_CODIGO))
            if not codigo:
                continue
            ruc = solo_digitos(campo(fila, *COL_RUC))
            self.agregar(RegistroSanitario(
                codigo=codigo,
                producto=str(campo(fila, *COL_PRODUCTO)),
                marca=str(campo(fila, *COL_MARCA)),
                titular=str(campo(fila, *COL_TITULAR)),
                ruc_titular=ruc[-11:] if len(ruc) >= 11 else ruc,
                fecha_vencimiento=a_fecha(campo(fila, *COL_VENCE)),
                estado=str(campo(fila, *COL_ESTADO)),
            ))
            n += 1
        self.archivos.append(ruta.name)
        return n

    def cargar_carpeta(self, carpeta: Path | str) -> int:
        carpeta = Path(carpeta)
        n = 0
        if carpeta.is_dir():
            for ruta in sorted(carpeta.iterdir()):
                if ruta.suffix.lower() in (".csv", ".txt", ".xlsx", ".xlsm"):
                    n += self.cargar_archivo(ruta)
        return n

    def buscar(self, ruc: str, nombre: str) -> list[RegistroSanitario]:
        if ruc and ruc in self.por_ruc:
            return self.por_ruc[ruc]
        clave = normalizar_empresa(nombre)
        return self.por_nombre.get(clave, []) if clave else []

    def verificar(self, adj: Adjudicacion) -> Verificacion:
        if not self.cargada:
            return Verificacion(
                estado=NO_VERIFICADO,
                nota="No se cargó la base de registros sanitarios de DIGESA. "
                     f"Consulta manual: {URL_CONSULTA_DIGESA}",
            )
        registros = self.buscar(adj.ruc_ganador, adj.ganador)
        relacionados = [r for r in registros if producto_relacionado(adj.categoria, r.producto)]
        notas = []
        if normalizar(adj.ganador).startswith("consorcio"):
            notas.append("Ganador es un consorcio: verifique a cada empresa consorciada.")
        if not registros:
            notas.append("No se encontraron registros a nombre del ganador. Puede ser distribuidor "
                         "de un producto cuyo titular es otra empresa (revise la oferta).")
            return Verificacion(estado=SIN_REGISTRO, nota=" ".join(notas))
        if not relacionados:
            notas.append(f"Tiene registros sanitarios, pero ninguno parece de {adj.categoria.lower()}.")
        vencidos = [r for r in relacionados if r.vigente is False]
        if relacionados and len(vencidos) == len(relacionados):
            notas.append("Todos los registros relacionados figuran vencidos o cancelados.")
        return Verificacion(estado=CON_REGISTRO, registros=registros,
                            relacionados=relacionados, nota=" ".join(notas))
