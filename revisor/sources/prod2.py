"""Robot para el buscador de procedimientos del SEACE (prod2), en TU PC.

prod2.seace.gob.pe bloquea conexiones desde fuera del Perú y usa reCAPTCHA, por
eso no puede correr en GitHub: abre un Chrome visible en tu computadora y sigue
el mismo flujo que harías a mano:

  1. Buscador de Procedimientos de Selección → Descripción del Objeto = término → Buscar
  2. En cada resultado de interés: abrir la ficha (ícono de "Acciones")
  3. Lista de Documentos → "Otorgamiento de Buena Pro" → descargar el ZIP
  4. Leer el "Reporte de otorgamiento de buena pro" → RUC y nombre del ganador

Si un paso falla, guarda captura + HTML en reportes/diagnostico/ para ajustar
los selectores.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from ..buenapro import ReporteBuenaPro, leer_zip
from ..categorias import normalizar
from ..modelos import Adjudicacion
from .prod6 import Contratacion, categorias_de

URL = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
TERMINOS = ["avena", "arroz", "simil", "vaso de leche", "leche", "hojuela"]
FUENTE = "SEACE – procedimientos de selección (prod2)"


@dataclass
class Procedimiento:
    nomenclatura: str
    entidad: str
    descripcion: str
    objeto: str
    fecha_publicacion: Optional[datetime]
    fila: int
    pagina: int
    termino: str
    categorias: list[str] = field(default_factory=list)
    ficha_url: str = ""


def _fecha(s: str) -> Optional[datetime]:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


class RobotSEACE:
    def __init__(self, page, carpeta_diag: Path, preguntar: Callable[[str], str] = input,
                 log: Callable[..., None] = print) -> None:
        self.page = page
        self.diag = carpeta_diag
        self.preguntar = preguntar
        self.log = log

    # ---------- utilidades ----------
    def diagnostico(self, paso: str) -> None:
        self.diag.mkdir(parents=True, exist_ok=True)
        base = self.diag / f"{datetime.now():%H%M%S}_{re.sub(r'[^a-z0-9]+', '_', paso.lower())}"
        try:
            self.page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            base.with_suffix(".html").write_text(self.page.content(), encoding="utf-8")
            self.log(f"  (diagnóstico guardado: {base.name}.png/.html)")
        except Exception:
            pass

    def _esperar(self, ms: int = 1200) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        self.page.wait_for_timeout(ms)

    def _input_de_fila(self, etiqueta: str):
        """El <input> que está en la misma fila que el texto de la etiqueta."""
        return self.page.locator(
            f"xpath=//td[contains(normalize-space(.), '{etiqueta}') and not(.//td)]"
            f"/following-sibling::td[1]//input[not(@type='hidden')]").first

    # ---------- búsqueda ----------
    def abrir(self) -> None:
        self.page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        self._esperar()
        pestaña = self.page.get_by_text("Buscador de Procedimientos de Selección", exact=False).first
        if pestaña.count():
            pestaña.click()
            self._esperar()

    def buscar(self, termino: str) -> None:
        campo = self._input_de_fila("Descripción del Objeto")
        campo.fill("")
        campo.fill(termino)
        self.page.get_by_text("Buscar", exact=True).first.click()
        self._esperar(2000)
        for _ in range(3):
            if self._tabla_resultados().count() or self.page.get_by_text("No se encontraron", exact=False).count():
                return
            self.diagnostico(f"sin_resultados_{termino}")
            self.preguntar(f"\n>> No veo resultados para '{termino}'. Si hay un captcha en la ventana, "
                           "resuélvelo y pulsa Buscar; luego presiona Enter aquí… ")
            self._esperar()

    def _tabla_resultados(self):
        return self.page.locator("xpath=//table[.//th[contains(normalize-space(.), 'Nomenclatura')]"
                                 " and .//th[contains(normalize-space(.), 'Descripción de Objeto')]]").last

    def leer_resultados(self, termino: str, pagina: int) -> list[Procedimiento]:
        tabla = self._tabla_resultados()
        if not tabla.count():
            return []
        encabezados = [normalizar(t) for t in tabla.locator("thead th").all_inner_texts()]

        def col(nombre: str) -> int:
            for i, h in enumerate(encabezados):
                if nombre in h:
                    return i
            return -1

        i_ent, i_fec, i_nom = col("entidad"), col("fecha"), col("nomenclatura")
        i_obj, i_des = col("objeto de contratacion"), col("descripcion de objeto")
        salida = []
        for n, fila in enumerate(tabla.locator("tbody > tr").all()):
            celdas = [c.strip() for c in fila.locator("> td").all_inner_texts()]
            if len(celdas) < max(i_ent, i_nom, i_des) + 1:
                continue
            p = Procedimiento(
                nomenclatura=celdas[i_nom], entidad=celdas[i_ent], descripcion=re.sub(r"\s+", " ", celdas[i_des]),
                objeto=celdas[i_obj] if i_obj >= 0 else "", fecha_publicacion=_fecha(celdas[i_fec]) if i_fec >= 0 else None,
                fila=n, pagina=pagina, termino=termino)
            p.categorias = categorias_de(p.descripcion, p.objeto)
            salida.append(p)
        return salida

    def siguiente_pagina(self) -> bool:
        boton = self.page.locator(".ui-paginator-next").last
        if not boton.count() or "ui-state-disabled" in (boton.get_attribute("class") or ""):
            return False
        boton.click()
        self._esperar(1500)
        return True

    def ir_a_pagina(self, pagina: int) -> None:
        for _ in range(pagina - 1):
            if not self.siguiente_pagina():
                break

    def abrir_ficha(self, p: Procedimiento) -> str:
        """Clic en el ícono de ficha (último enlace de 'Acciones') y devuelve la URL de la ficha."""
        fila = self._tabla_resultados().locator("tbody > tr").nth(p.fila)
        enlaces = fila.locator("> td").last.locator("a")
        destino = enlaces.last if enlaces.count() else fila.locator("> td").last.locator("img").last
        antes = self.page.url
        try:
            with self.page.context.expect_page(timeout=4000) as nueva:
                destino.click()
            ficha = nueva.value  # la ficha se abrió en otra pestaña
            ficha.wait_for_load_state("domcontentloaded")
            url = ficha.url
            ficha.close()
            return url
        except Exception:
            pass
        self._esperar(1500)
        if self.page.url != antes:  # la ficha se abrió en la misma pestaña
            url = self.page.url
            self.page.go_back()
            self._esperar()
            return url
        self.diagnostico(f"ficha_{p.nomenclatura}")
        return ""

    # ---------- ficha ----------
    def documentos_buena_pro(self, ficha_url: str) -> Optional[ReporteBuenaPro]:
        """None si la ficha aún no tiene 'Otorgamiento de Buena Pro'."""
        self.page.goto(ficha_url, wait_until="domcontentloaded", timeout=90000)
        self._esperar()
        for _ in range(10):
            fila = self.page.locator("xpath=//tr[td[contains(normalize-space(.), 'Otorgamiento de Buena Pro')]]").first
            if fila.count():
                enlace = fila.locator("a").first
                with self.page.expect_download(timeout=90000) as descarga:
                    enlace.click()
                ruta = descarga.value.path()
                return leer_zip(Path(ruta).read_bytes())
            # Lista de documentos paginada: siguiente página de documentos.
            siguiente = self.page.locator("xpath=//*[contains(., 'Lista de Documentos')]/ancestor::div[1]"
                                          "//*[contains(@class,'ui-paginator-next')]").last
            if not siguiente.count() or "ui-state-disabled" in (siguiente.get_attribute("class") or ""):
                return None
            siguiente.click()
            self._esperar(1000)
        return None


# ---------- caché para no descargar lo mismo cada día ----------
class Cache:
    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        try:
            self.datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.datos = {}

    def get(self, nomenclatura: str) -> Optional[dict]:
        return self.datos.get(nomenclatura)

    def put(self, nomenclatura: str, valor: dict) -> None:
        self.datos[nomenclatura] = valor
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self.datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _rep_a_dict(rep: ReporteBuenaPro) -> dict:
    return {"entidad": rep.entidad, "nomenclatura": rep.nomenclatura, "descripcion": rep.descripcion,
            "ganadores": [g.__dict__ for g in rep.ganadores]}


def a_adjudicaciones(p: Procedimiento, rep: dict) -> list[Adjudicacion]:
    salida = []
    for g in rep.get("ganadores", []):
        if normalizar(g.get("resultado") or "adjudicado") not in ("adjudicado", "consentido", ""):
            continue
        nombre = g["nombre"]
        if g.get("integrantes"):
            nombre += " (" + "; ".join(f"{r}-{n}" for r, n in g["integrantes"]) + ")"
        for cat in p.categorias:
            salida.append(Adjudicacion(
                categoria=cat, nomenclatura=p.nomenclatura, entidad=p.entidad,
                descripcion=p.descripcion + (f" — Ítem {g['item']}: {g['descripcion']}" if g.get("descripcion") else ""),
                ganador=nombre, ruc_ganador=g.get("ruc") or (g["integrantes"][0][0] if g.get("integrantes") else ""),
                monto=g.get("monto"), moneda="PEN",
                fecha_buena_pro=(p.fecha_publicacion.date() if p.fecha_publicacion else None),
                url=p.ficha_url, fuente=FUENTE))
    return salida


def recolectar(robot: RobotSEACE, cache: Cache, dias: int = 120, terminos: list[str] = TERMINOS,
               max_paginas: int = 10) -> tuple[list[Adjudicacion], list[Contratacion]]:
    desde = date.today() - timedelta(days=dias)
    adjs: list[Adjudicacion] = []
    pendientes: dict[str, Contratacion] = {}
    vistos: set[str] = set()
    robot.abrir()
    for termino in terminos:
        robot.log(f"Buscando '{termino}'…")
        robot.buscar(termino)
        pagina = 1
        while pagina <= max_paginas:
            procs = robot.leer_resultados(termino, pagina)
            viejos = 0
            for p in procs:
                if p.fecha_publicacion and p.fecha_publicacion.date() < desde:
                    viejos += 1
                    continue
                if not p.categorias or p.nomenclatura in vistos:
                    continue
                vistos.add(p.nomenclatura)
                previo = cache.get(p.nomenclatura)
                if previo and previo.get("ganadores"):
                    p.ficha_url = previo.get("ficha_url", "")
                    adjs += a_adjudicaciones(p, previo)
                    robot.log(f"  {p.nomenclatura}: ganador ya conocido (caché)")
                    continue
                p.ficha_url = (previo or {}).get("ficha_url") or robot.abrir_ficha(p)
                if not p.ficha_url:
                    continue
                robot.log(f"  {p.nomenclatura}: revisando documentos de buena pro…")
                try:
                    rep = robot.documentos_buena_pro(p.ficha_url)
                except Exception as exc:
                    robot.diagnostico(f"documentos_{p.nomenclatura}")
                    robot.log(f"    ! {exc}")
                    rep = None
                if rep and rep.ganadores:
                    d = _rep_a_dict(rep) | {"ficha_url": p.ficha_url}
                    cache.put(p.nomenclatura, d)
                    adjs += a_adjudicaciones(p, d)
                    robot.log(f"    ganador(es): {', '.join(g.nombre for g in rep.ganadores)}")
                else:
                    cache.put(p.nomenclatura, {"ficha_url": p.ficha_url, "ganadores": []})
                    pendientes[p.nomenclatura] = Contratacion(
                        id=0, nomenclatura=p.nomenclatura, entidad=p.entidad, descripcion=p.descripcion,
                        objeto=p.objeto, estado="Sin buena pro publicada", categorias=p.categorias,
                        fecha_publicacion=p.fecha_publicacion, url=p.ficha_url, fuente=FUENTE)
                # Volver a la lista de resultados en la misma página.
                robot.abrir()
                robot.buscar(termino)
                robot.ir_a_pagina(pagina)
                time.sleep(0.5)
            if viejos and viejos == len(procs):
                break  # resultados ordenados por fecha: ya pasamos el periodo
            if not robot.siguiente_pagina():
                break
            pagina += 1
    return adjs, list(pendientes.values())
