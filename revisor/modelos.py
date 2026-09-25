"""Estructuras de datos del revisor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Adjudicacion:
    """Un ganador (buena pro) de un procedimiento de selección."""

    categoria: str
    nomenclatura: str
    entidad: str
    descripcion: str
    ganador: str
    ruc_ganador: str
    monto: Optional[float] = None
    moneda: str = "PEN"
    fecha_buena_pro: Optional[date] = None
    url: str = ""
    fuente: str = ""


@dataclass
class RegistroSanitario:
    codigo: str
    producto: str = ""
    marca: str = ""
    titular: str = ""
    ruc_titular: str = ""
    fecha_vencimiento: Optional[date] = None
    estado: str = ""

    @property
    def vigente(self) -> Optional[bool]:
        if self.estado:
            est = self.estado.upper()
            if any(p in est for p in ("CANCEL", "VENCID", "SUSPEND", "ANULAD")):
                return False
        if self.fecha_vencimiento:
            return self.fecha_vencimiento >= date.today()
        return None


# Resultado de verificación
CON_REGISTRO = "CON REGISTRO SANITARIO"
SIN_REGISTRO = "SIN REGISTRO SANITARIO"
NO_VERIFICADO = "NO VERIFICADO"


@dataclass
class Verificacion:
    estado: str
    registros: list[RegistroSanitario] = field(default_factory=list)
    relacionados: list[RegistroSanitario] = field(default_factory=list)
    nota: str = ""


@dataclass
class ResultadoGanador:
    adjudicacion: Adjudicacion
    verificacion: Verificacion
