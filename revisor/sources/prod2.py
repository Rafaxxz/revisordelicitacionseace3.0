"""Robot para el buscador de procedimientos del SEACE (prod2), en TU PC.

prod2.seace.gob.pe bloquea conexiones desde fuera del Perú y usa reCAPTCHA, por
eso no puede correr en GitHub: abre un Chrome visible en tu computadora y sigue
el mismo flujo que harías a mano:

  1. Buscador de Procedimientos de Selección → Descripción del Objeto = término → Buscar
  2. En cada resultado de interés: abrir la ficha (ícono de "Acciones") en otra pestaña
  3. Lista de Documentos → "Documentos de Otorgamiento de Buena Pro" → descargar el ZIP
  4. Leer el "Reporte de otorgamiento de buena pro" → RUC y nombre del ganador

Detalles de la página real (PrimeFaces/JSF, revisados en septiembre de 2026):
  - Todas las pestañas están en el HTML; los campos tienen ids fijos
    (tbBuscador:idFormBuscarProceso:...). El botón "Buscar" visible es
    btnBuscarSelToken: pide un token de reCAPTCHA v3 (invisible) y envía la búsqueda.
  - El ícono de ficha envía el formulario por POST. La URL resultante
    (fichaSeleccion.xhtml?id=...) solo sirve dentro de la misma sesión, así que no
    se puede guardar para otro día. Poniendo target=_blank al formulario la ficha
    se abre en otra pestaña y la lista de resultados queda intacta.
  - La descarga es un enlace con onclick="descargaDocGeneral(uuid, ...)" que redirige
    al servidor de documentos (Alfresco).

Si un paso falla, guarda captura + HTML en reportes/diagnostico/ para ajustar
los selectores.
"""
from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from ..buenapro import ReporteBuenaPro, leer_archivo
from ..categorias import normalizar
from ..modelos import Adjudicacion
from .prod6 import Contratacion, categorias_de

URL = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
TERMINOS = ["avena", "arroz", "simil", "vaso de leche", "leche", "hojuela"]
FUENTE = "SEACE – procedimientos de selección (prod2)"

FORM = "tbBuscador:idFormBuscarProceso"
TAB_PROCESOS = "a[href='#tbBuscador:tab1']"
DOCS = "tbFicha:dtDocumentos"
_BUENA_PRO = re.compile(r"Otorgamiento de (la )?Buena Pro", re.I)


def _id(ident: str) -> str:
    """Selector CSS para un id de JSF (los ':' se escapan)."""
    return "#" + ident.replace(":", "\\:")


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


@dataclass
class DocBuenaPro:
    reporte: ReporteBuenaPro
    fecha: Optional[datetime] = None  # publicación del documento en la ficha


def _fecha(s: str) -> Optional[datetime]:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


class RobotSEACE:
    def __init__(self, page, carpeta_diag: Path, preguntar: Callable[[str], str] = input,
                 log: Callable[..., None] = print, carpeta_zips: Optional[Path] = None,
                 pausa: tuple[float, float] = (1.0, 2.0)) -> None:
        self.page = page
        self.diag = carpeta_diag
        self.zips = carpeta_zips
        self.preguntar = preguntar
        self.log = log
        self.pausa_rango = pausa

    # ---------- utilidades ----------
    def diagnostico(self, paso: str, page=None) -> None:
        page = page or self.page
        self.diag.mkdir(parents=True, exist_ok=True)
        base = self.diag / f"{datetime.now():%H%M%S}_{re.sub(r'[^a-z0-9]+', '_', paso.lower())}"
        try:
            page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
            self.log(f"  (diagnóstico guardado: {base.name}.png/.html)")
        except Exception:
            pass

    def pausa(self) -> None:
        """Pausa de cortesía entre acciones para no cargar el servidor."""
        time.sleep(random.uniform(*self.pausa_rango))

    def _filas(self, page=None):
        return (page or self.page).locator(f"{_id(FORM + ':dtProcesos_data')} > tr")

    def _marcar_filas(self) -> None:
        """Marca las filas actuales para reconocer cuándo el AJAX las reemplaza."""
        self.page.evaluate("""sel => document.querySelectorAll(sel).forEach(tr => tr.dataset.robotViejo = '1')""",
                           f"{_id(FORM + ':dtProcesos_data')} > tr")

    def _esperar_filas_nuevas(self, timeout: int = 60000) -> bool:
        try:
            self.page.wait_for_selector(f"{_id(FORM + ':dtProcesos_data')} > tr:not([data-robot-viejo])",
                                        state="attached", timeout=timeout)
            self.page.wait_for_timeout(500)
            return True
        except Exception:
            return False

    # ---------- búsqueda ----------
    def abrir(self) -> None:
        self.page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        self.page.wait_for_selector(TAB_PROCESOS, timeout=60000)
        self.pausa()
        self.page.click(TAB_PROCESOS)
        self.page.wait_for_selector(_id(FORM + ":descripcionObjeto"), state="visible", timeout=30000)

    def buscar(self, termino: str) -> None:
        campo = self.page.locator(_id(FORM + ":descripcionObjeto"))
        campo.fill(termino)
        anio = self.page.locator(_id(FORM + ":anioConvocatoria_input"))
        if anio.count() and anio.input_value() != str(date.today().year):
            self.log(f"  ! 'Año de la Convocatoria' es {anio.input_value()}, no {date.today().year}")
        self._marcar_filas()
        self.pausa()
        self.page.click(_id(FORM + ":btnBuscarSelToken"))
        for intento in range(3):
            if self._esperar_filas_nuevas(timeout=45000 if intento == 0 else 5000):
                self._ir_a_primera_pagina()
                return
            # Sin respuesta: puede que el reCAPTCHA pida un desafío visible.
            self.diagnostico(f"sin_resultados_{termino}")
            self.preguntar(f"\n>> No llegan resultados para '{termino}'. Si hay un captcha en la ventana, "
                           "resuélvelo y pulsa Buscar; luego presiona Enter aquí… ")
        raise RuntimeError(f"No se pudo buscar '{termino}' (revisa reportes/diagnostico)")

    def _ir_a_primera_pagina(self) -> None:
        """La tabla conserva la página de la búsqueda anterior: volver a la 1."""
        primera = self.page.locator(f"{_id(FORM + ':dtProcesos_paginator_bottom')} .ui-paginator-first")
        if not primera.count() or "ui-state-disabled" in (primera.get_attribute("class") or ""):
            return
        self._marcar_filas()
        self.pausa()
        primera.click()
        if not self._esperar_filas_nuevas():
            self.diagnostico("primera_pagina")

    def total_resultados(self) -> str:
        pie = self.page.locator(f"{_id(FORM + ':dtProcesos_paginator_bottom')} .ui-paginator-current")
        return pie.inner_text().strip() if pie.count() else ""

    def leer_resultados(self, termino: str, pagina: int) -> list[Procedimiento]:
        encabezados = [normalizar(t) for t in
                       self.page.locator(f"{_id(FORM + ':dtProcesos_head')} th").all_inner_texts()]

        def col(nombre: str) -> int:
            return next((i for i, h in enumerate(encabezados) if nombre in h), -1)

        i_ent, i_fec, i_nom = col("entidad"), col("fecha"), col("nomenclatura")
        i_obj, i_des = col("objeto de contratacion"), col("descripcion de objeto")
        if min(i_ent, i_nom, i_des) < 0:
            self.diagnostico("encabezados_resultados")
            raise RuntimeError(f"No reconozco las columnas de resultados: {encabezados}")
        salida = []
        for n, fila in enumerate(self._filas().all()):
            celdas = [c.strip() for c in fila.locator("> td").all_inner_texts()]
            if len(celdas) <= max(i_ent, i_nom, i_des):
                continue  # "No se encontraron Datos"
            p = Procedimiento(
                nomenclatura=celdas[i_nom], entidad=celdas[i_ent], descripcion=re.sub(r"\s+", " ", celdas[i_des]),
                objeto=celdas[i_obj] if i_obj >= 0 else "", fecha_publicacion=_fecha(celdas[i_fec]) if i_fec >= 0 else None,
                fila=n, pagina=pagina, termino=termino)
            p.categorias = categorias_de(p.descripcion, p.objeto)
            salida.append(p)
        return salida

    def siguiente_pagina(self) -> bool:
        boton = self.page.locator(f"{_id(FORM + ':dtProcesos_paginator_bottom')} .ui-paginator-next")
        if not boton.count() or "ui-state-disabled" in (boton.get_attribute("class") or ""):
            return False
        self._marcar_filas()
        self.pausa()
        boton.click()
        if not self._esperar_filas_nuevas():
            self.diagnostico("paginacion_resultados")
            return False
        return True

    # ---------- ficha ----------
    def abrir_ficha(self, p: Procedimiento):
        """Abre la ficha del procedimiento en otra pestaña y la devuelve (hay que cerrarla)."""
        icono = self._filas().nth(p.fila).locator("img[id$='grafichaSel']")
        if not icono.count():
            self.diagnostico(f"icono_ficha_{p.nomenclatura}")
            return None
        # Con target=_blank el POST de JSF abre la ficha en una pestaña nueva y la lista de
        # resultados sigue viva en esta (con "Atrás" se perdería).
        self.page.evaluate("id => { const f = document.getElementById(id); if (f) f.target = '_blank'; }", FORM)
        self.pausa()
        try:
            with self.page.context.expect_page(timeout=30000) as nueva:
                icono.click()
        except Exception:
            self.diagnostico(f"ficha_{p.nomenclatura}")
            return None
        ficha = nueva.value
        ficha.wait_for_load_state("domcontentloaded", timeout=90000)
        return ficha

    def nomenclatura_de_ficha(self, ficha) -> str:
        celda = ficha.locator("xpath=//td[normalize-space(.)='Nomenclatura:']/following-sibling::td[1]").first
        return celda.inner_text().strip() if celda.count() else ""

    def documentos_buena_pro(self, ficha, nomenclatura: str = "") -> Optional[DocBuenaPro]:
        """None si la ficha aún no tiene 'Documentos de Otorgamiento de Buena Pro'."""
        cuerpo = f"{_id(DOCS + '_data')} > tr"
        ficha.wait_for_selector(_id(DOCS + "_data"), state="attached", timeout=60000)
        paginador = _id(DOCS + "_paginator_bottom")
        # Lista paginada de 5 en 5: pedir 15 por página reduce los clics.
        filas_por_pag = ficha.locator(f"{paginador} select.ui-paginator-rpp-options")
        if filas_por_pag.count() and filas_por_pag.locator("option[value='15']").count():
            self._cambiar_pagina_docs(ficha, lambda: filas_por_pag.select_option("15"))
        resultado = None
        for _ in range(20):
            filas = ficha.locator(cuerpo).filter(has_text=_BUENA_PRO)
            if filas.count():
                resultado = self._descargar(ficha, filas.last, nomenclatura) or resultado
            siguiente = ficha.locator(f"{paginador} .ui-paginator-next")
            if not siguiente.count() or "ui-state-disabled" in (siguiente.get_attribute("class") or ""):
                break
            self._cambiar_pagina_docs(ficha, siguiente.click)
        return resultado

    def _cambiar_pagina_docs(self, ficha, accion) -> None:
        ficha.evaluate("sel => document.querySelectorAll(sel).forEach(tr => tr.dataset.robotViejo = '1')",
                       f"{_id(DOCS + '_data')} > tr")
        self.pausa()
        accion()
        ficha.wait_for_selector(f"{_id(DOCS + '_data')} > tr:not([data-robot-viejo])", state="attached", timeout=60000)
        ficha.wait_for_timeout(300)

    def _descargar(self, ficha, fila, nomenclatura: str) -> Optional[DocBuenaPro]:
        celdas = [c.strip() for c in fila.locator("> td").all_inner_texts()]
        fecha = next((f for f in map(_fecha, celdas) if f), None)
        enlace = fila.locator("a[onclick*='descargaDoc']").first
        if not enlace.count():
            self.diagnostico(f"enlace_buena_pro_{nomenclatura}", ficha)
            return None
        self.pausa()
        with ficha.expect_download(timeout=120000) as descarga:
            enlace.click()
        contenido = Path(descarga.value.path()).read_bytes()
        if self.zips:
            self.zips.mkdir(parents=True, exist_ok=True)
            nombre = re.sub(r"[^A-Za-z0-9.-]+", "_", nomenclatura or "sin_nombre")
            ext = Path(descarga.value.suggested_filename).suffix or ".zip"
            (self.zips / f"{nombre}{ext}").write_bytes(contenido)
        return DocBuenaPro(leer_archivo(contenido), fecha)


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


def _rep_a_dict(doc: DocBuenaPro) -> dict:
    rep = doc.reporte
    return {"entidad": rep.entidad, "nomenclatura": rep.nomenclatura, "descripcion": rep.descripcion,
            "fecha_buena_pro": doc.fecha.isoformat() if doc.fecha else None,
            "ganadores": [g.__dict__ for g in rep.ganadores]}


def a_adjudicaciones(p: Procedimiento, rep: dict) -> list[Adjudicacion]:
    fbp = rep.get("fecha_buena_pro")
    fecha = datetime.fromisoformat(fbp).date() if fbp else (p.fecha_publicacion.date() if p.fecha_publicacion else None)
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
                monto=g.get("monto"), moneda="PEN", fecha_buena_pro=fecha,
                # La URL de la ficha solo vale en la sesión del robot: se enlaza al buscador.
                url=URL, fuente=FUENTE))
    return salida


def _pendiente(p: Procedimiento, estado: str) -> Contratacion:
    return Contratacion(id=0, nomenclatura=p.nomenclatura, entidad=p.entidad, descripcion=p.descripcion,
                        objeto=p.objeto, estado=estado, categorias=p.categorias,
                        fecha_publicacion=p.fecha_publicacion, url=URL, fuente=FUENTE)


def revisar_procedimiento(robot: RobotSEACE, p: Procedimiento) -> Optional[DocBuenaPro]:
    ficha = robot.abrir_ficha(p)
    if ficha is None:
        raise RuntimeError("no se pudo abrir la ficha")
    try:
        en_ficha = robot.nomenclatura_de_ficha(ficha)
        if en_ficha and en_ficha != p.nomenclatura:
            robot.diagnostico(f"ficha_distinta_{p.nomenclatura}", ficha)
            raise RuntimeError(f"la ficha abierta es {en_ficha}")
        return robot.documentos_buena_pro(ficha, p.nomenclatura)
    except Exception:
        robot.diagnostico(f"documentos_{p.nomenclatura}", ficha)
        raise
    finally:
        ficha.close()


def recolectar(robot: RobotSEACE, cache: Cache, dias: int = 120, terminos: list[str] = TERMINOS,
               max_paginas: int = 40) -> tuple[list[Adjudicacion], list[Contratacion]]:
    desde = date.today() - timedelta(days=dias)
    adjs: list[Adjudicacion] = []
    pendientes: dict[str, Contratacion] = {}
    vistos: set[str] = set()
    robot.abrir()
    for termino in terminos:
        robot.log(f"Buscando '{termino}'…")
        robot.buscar(termino)
        robot.log(f"  {robot.total_resultados()}")
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
                    adjs += a_adjudicaciones(p, previo)
                    robot.log(f"  {p.nomenclatura}: ganador ya conocido (caché)")
                    continue
                robot.log(f"  {p.nomenclatura}: revisando documentos de buena pro…")
                try:
                    doc = revisar_procedimiento(robot, p)
                except Exception as exc:
                    if "has been closed" in str(exc):
                        raise RuntimeError("Se cerró la ventana de Chrome; vuelve a ejecutar el robot "
                                           "(lo ya descargado está en el caché).") from exc
                    robot.log(f"    ! {exc}")
                    pendientes[p.nomenclatura] = _pendiente(p, "No se pudo revisar la ficha")
                    continue
                if doc and doc.reporte.ganadores:
                    d = _rep_a_dict(doc)
                    cache.put(p.nomenclatura, d)
                    adjs += a_adjudicaciones(p, d)
                    robot.log("    ganador(es): " + ", ".join(f"{g.ruc or '-'} {g.nombre} S/ {g.monto:,.2f}"
                                                            if g.monto is not None else f"{g.ruc} {g.nombre}"
                                                            for g in doc.reporte.ganadores))
                else:
                    if doc:
                        robot.log("    ! hay documento de buena pro pero no se pudo leer el ganador")
                    cache.put(p.nomenclatura, {"ganadores": [], "revisado": date.today().isoformat()})
                    pendientes[p.nomenclatura] = _pendiente(p, "Sin buena pro publicada")
            if viejos and viejos == len(procs):
                break  # resultados ordenados por fecha: ya pasamos el periodo
            if not robot.siguiente_pagina():
                break
            pagina += 1
    return adjs, list(pendientes.values())
