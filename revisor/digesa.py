"""Consulta en línea de registros sanitarios de alimentos (DIGESA) por RUC.

Página oficial (ASP.NET WebForms):
  https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx

La pestaña "RUC" exige un año de emisión (no tiene opción "todos"), así que se
consulta cada año desde hoy hacia atrás. Un registro sanitario dura 5 años, por
lo que 7 años cubren los vigentes y los vencidos recientes.
La página usa Cloudflare contra navegadores automatizados, pero acepta el
envío normal del formulario (se replican todos los campos como un navegador).
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime
from html import unescape
from typing import Optional

import requests

from .modelos import RegistroSanitario

URL = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
_TAB = "ctl00$ContentPlaceHolder1$TabContainer1$TabPanel_ConsultaRUC$"
_GRID = "ctl00$ContentPlaceHolder1$GridView1"
_GRID_ID = "ctl00_ContentPlaceHolder1_GridView1"


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def campos_formulario(html: str) -> list[list[str]]:
    """Todos los campos que un navegador enviaría (sin botones)."""
    datos: list[list[str]] = []
    for m in re.finditer(r"<input\b[^>]*>", html):
        tag = m.group(0)
        nombre = re.search(r'name="([^"]+)"', tag)
        if not nombre:
            continue
        tipo = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1].lower()
        if tipo in ("submit", "button", "image") or (tipo in ("checkbox", "radio") and "checked" not in tag):
            continue
        valor = re.search(r'value="([^"]*)"', tag)
        datos.append([unescape(nombre.group(1)), unescape(valor.group(1)) if valor else ""])
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        opciones = re.findall(r'<option([^>]*)value="([^"]*)"', m.group(2))
        elegida = [v for a, v in opciones if "selected" in a] or [v for _, v in opciones[:1]]
        datos.append([unescape(m.group(1)), unescape(elegida[0]) if elegida else ""])
    return datos


def _poner(datos: list[list[str]], clave: str, valor: str) -> None:
    for par in datos:
        if par[0] == clave:
            par[1] = valor
            return
    datos.append([clave, valor])


def _fecha(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def leer_grilla(html: str) -> tuple[list[RegistroSanitario], list[int]]:
    """Registros de la tabla de resultados y números de página disponibles."""
    m = re.search(r'<table[^>]*id="' + _GRID_ID + r'".*?</table>\s*(?:</div>)?', html, re.S)
    if not m:
        return [], []
    bloque = m.group(0)
    paginas = sorted({int(n) for n in re.findall(r"Page\$(\d+)", bloque)})
    filas = re.findall(r"<tr\b.*?</tr>", bloque, re.S)
    encabezado: list[str] = []
    registros: list[RegistroSanitario] = []
    for fila in filas:
        celdas_html = re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", fila, re.S)
        celdas = [_texto(c) for c in celdas_html]
        if not encabezado:
            if any("REGISTRO" in c.upper() for c in celdas):
                encabezado = [c.upper() for c in celdas]
            continue
        if "Page$" in fila or len(celdas) < 7:
            continue  # fila del paginador
        col = {k: celdas[i] for i, k in enumerate(encabezado) if i < len(celdas)}
        codigo = col.get("REGISTRO", "")
        if not codigo:
            continue
        registros.append(RegistroSanitario(
            codigo=codigo,
            producto=col.get("PRODUCTOS", ""),
            titular=col.get("EMPRESA", ""),
            fecha_vencimiento=_fecha(col.get("FECHA VENCIMIENTO", "")),
            estado="",
        ))
    return registros, paginas


class ConsultaDIGESA:
    def __init__(self, anios: int = 7, pausa: float = 0.5) -> None:
        self.anios = anios
        self.pausa = pausa
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Referer": URL, "Origin": "https://consultas-digesa.minsa.gob.pe",
        })

    def _post(self, datos: list[list[str]]) -> str:
        for intento in range(3):
            try:
                r = self.s.post(URL, data=datos, timeout=90)
                if r.status_code == 200:
                    time.sleep(self.pausa)
                    return r.text
            except requests.RequestException:
                pass
            time.sleep(3 * (intento + 1))
        raise RuntimeError("DIGESA no respondió a la consulta")

    def por_ruc_anio(self, ruc: str, anio: int) -> list[RegistroSanitario]:
        html = self.s.get(URL, timeout=60).text
        datos = campos_formulario(html)
        _poner(datos, _TAB + "TextBox_ConsultaRUC", ruc)
        _poner(datos, _TAB + "ddlEstado_RUC", "%")
        _poner(datos, _TAB + "ddlAñoEmision_RUC", str(anio))
        _poner(datos, _TAB + "Button_ConsultaRUC", "Buscar")
        html = self._post(datos)
        registros, paginas = leer_grilla(html)
        vistas = {1}
        for pagina in paginas:
            if pagina in vistas:
                continue
            vistas.add(pagina)
            datos = campos_formulario(html)
            _poner(datos, "__EVENTTARGET", _GRID)
            _poner(datos, "__EVENTARGUMENT", f"Page${pagina}")
            html = self._post(datos)
            nuevos, _ = leer_grilla(html)
            registros += nuevos
        for r in registros:
            r.ruc_titular = ruc
        return registros

    def por_ruc(self, ruc: str) -> list[RegistroSanitario]:
        anio = date.today().year
        vistos: dict[str, RegistroSanitario] = {}
        for a in range(anio, anio - self.anios, -1):
            for r in self.por_ruc_anio(ruc, a):
                vistos.setdefault(r.codigo, r)
        return list(vistos.values())
