"""Datos de contacto de proveedores desde fuentes oficiales del OECE.

1. Ficha del proveedor (RNP):  https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{RUC}
   → teléfonos y correos que el proveedor declaró en el Registro Nacional de Proveedores.
2. Ficha resumen:              https://eap.oece.gob.pe/ficha-proveedor-cns/1.0/ficha/{RUC}/resumen
   → estado y condición SUNAT, ubicación (departamento/provincia/distrito) y
     representante legal.
3. Respaldo: la dirección que figura en los registros sanitarios de DIGESA.

No se guardan números de DNI de socios ni representantes.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import requests

URL_FICHA = "https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{ruc}"
URL_RESUMEN = "https://eap.oece.gob.pe/ficha-proveedor-cns/1.0/ficha/{ruc}/resumen"
URL_FICHA_WEB = "https://apps.oece.gob.pe/perfilprov-ui/ficha/{ruc}"


@dataclass
class Contacto:
    ruc: str
    telefonos: list[str] = field(default_factory=list)
    correos: list[str] = field(default_factory=list)
    ubicacion: str = ""
    direccion: str = ""
    estado_sunat: str = ""
    representante: str = ""
    habilitado_rnp: bool | None = None
    ficha_url: str = ""
    fuentes: list[str] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not (self.telefonos or self.correos)

    def a_dict(self) -> dict:
        return asdict(self)


def _limpios(valores) -> list[str]:
    salida: list[str] = []
    for v in valores or []:
        v = str(v or "").strip()
        if v and v.lower() not in ("null", "none", "-") and v not in salida:
            salida.append(v)
    return salida


def _texto(v) -> str:
    v = str(v or "").strip()
    return "" if v.lower() in ("null", "none") else v


class BuscadorContactos:
    def __init__(self, pausa: float = 0.3, sesion: requests.Session | None = None) -> None:
        self.s = sesion or requests.Session()
        self.s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122",
                               "Accept": "application/json"})
        self.pausa = pausa
        self._cache: dict[str, Contacto] = {}

    def _json(self, url: str) -> dict:
        for intento in range(3):
            try:
                r = self.s.get(url, timeout=40)
                if r.status_code == 200:
                    time.sleep(self.pausa)
                    return r.json()
            except (requests.RequestException, ValueError):
                pass
            time.sleep(2 * (intento + 1))
        return {}

    def buscar(self, ruc: str, direccion_respaldo: str = "") -> Contacto:
        if ruc in self._cache:
            return self._cache[ruc]
        c = Contacto(ruc=ruc, ficha_url=URL_FICHA_WEB.format(ruc=ruc))

        prov = (self._json(URL_FICHA.format(ruc=ruc)).get("proveedorT01") or {})
        if prov:
            c.telefonos = _limpios(prov.get("telefonos"))
            c.correos = _limpios(prov.get("emails"))
            c.habilitado_rnp = prov.get("esHabilitado")
            c.fuentes.append("Ficha RNP (OECE)")

        res = self._json(URL_RESUMEN.format(ruc=ruc))
        sunat = res.get("datosSunat") or {}
        if sunat:
            c.ubicacion = " / ".join(x for x in (_texto(sunat.get("departamento")), _texto(sunat.get("provincia")),
                                                 _texto(sunat.get("distrito"))) if x)
            c.estado_sunat = " - ".join(x for x in (_texto(sunat.get("estado")), _texto(sunat.get("condicion"))) if x)
            c.fuentes.append("SUNAT vía OECE")
        reps = ((res.get("conformacion") or {}).get("representantes") or [])
        nombres = _limpios(r.get("razonSocial") for r in reps)
        if nombres:
            c.representante = ", ".join(n.upper() for n in nombres[:2])

        if direccion_respaldo:
            c.direccion = direccion_respaldo
            c.fuentes.append("Registro sanitario DIGESA")
        self._cache[ruc] = c
        return c
