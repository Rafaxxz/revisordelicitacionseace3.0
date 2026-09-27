"""Prueba el robot de prod2 contra una réplica local de las páginas del SEACE.

La réplica copia lo que importa del HTML real (tests/datos/prod2_real/): los ids de
PrimeFaces/JSF, las pestañas, el botón "Buscar" con token, la tabla de resultados
paginada que se reemplaza por AJAX, el ícono de ficha que envía el formulario, la
ficha con el Cronograma (que también dice "Otorgamiento de la Buena Pro") y la
Lista de Documentos paginada de 5 en 5 con el enlace descargaDocGeneral(...)."""
import functools
import http.server
import os
import threading
from datetime import date
from pathlib import Path

import pytest

from revisor.sources import prod2
from tests.generar_reporte_bp import reporte_pdf, zip_bp

CHROME = os.environ.get("CHROME_PATH", "")

BUSCADOR = """<html><head><meta charset="utf-8"></head><body>
<ul><li><a href="#tbBuscador:tab7">Anuncio de Contratación Futura</a></li>
<li><a href="#tbBuscador:tab1" onclick="document.getElementById('tab1').style.display='block'">Buscador de Procedimientos de Selección</a></li></ul>
<div id="tab7"><button type="button"><span>Buscar</span></button></div>
<div id="tab1" style="display:none">
<form id="tbBuscador:idFormBuscarProceso" method="get" action="fichaSeleccion.html">
<input type="hidden" name="id" id="idFicha">
<table><tr><td>Descripción del Objeto</td><td><input id="tbBuscador:idFormBuscarProceso:descripcionObjeto" type="text"></td>
<td>Año de la Convocatoria</td><td><select id="tbBuscador:idFormBuscarProceso:anioConvocatoria_input"><option value="">[Seleccione]</option><option value="__ANIO__" selected>__ANIO__</option></select></td></tr></table>
<button id="tbBuscador:idFormBuscarProceso:btnBuscarSelToken" type="button" onclick="setTimeout(buscar, 300)"><span>Buscar</span></button>
<div id="tbBuscador:idFormBuscarProceso:pnlGrdResultadosProcesos"></div>
</form></div>
<script>
const POR_PAG = 2;
const filas = [
 ["MUNICIPALIDAD DE LECHERA","25/09/2026 09:00","AS-SM-9-2026-ML-1","Bien","ADQUISICION DE LECHE EVAPORADA PARA EL PROGRAMA DEL VASO DE LECHE","f6"],
 ["MUNICIPALIDAD DISTRITAL DE CARABAMBA","24/09/2026 20:32","LP-ABR-3-2026-MDC/CS-1","Bien","CONTRATACIÓN DEL SUMINISTRO DE BIENES HOJUELAS DE KIWICHA, AVENA Y QUINUA CON LECHE ENTERA EN POLVO PARA EL PROGRAMA VASO DE LECHE","f1"],
 ["AGRO RURAL","22/09/2026 23:54","DIRECTA-18-2026","Bien","ADQUISICIÓN DE ALIMENTO SUPLEMENTARIO (HENO DE ALFALFA Y/O AVENA)","f2"],
 ["MUNICIPALIDAD DE UCO","20/09/2026 10:00","AS-SM-2-2026-MDU-1","Bien","ADQUISICION DE HOJUELA DE AVENA PARA EL PROGRAMA DEL VASO DE LECHE","f3"],
 ["MUNICIPALIDAD DE MANANTAY","24/08/2026 16:44","LP-SM-1-2026-MDM-C-1","Bien","ADQUISICION DE INSUMOS ALIMENTICIOS PARA EL PROGRAMA DEL VASO DE LECHE: HOJUELA DE AVENA","f4"],
 ["MUNICIPALIDAD ANTIGUA","10/01/2020 09:00","AS-1-2020-MA-1","Bien","ADQUISICION DE AVENA PARA EL VASO DE LECHE","f5"]];
let lista = [], pagina = 0;
function F(s){ return 'tbBuscador:idFormBuscarProceso:' + s; }
function buscar(){
 const q = document.getElementById(F('descripcionObjeto')).value.toLowerCase();
 lista = filas.filter(f => f[4].toLowerCase().includes(q));
 // Como PrimeFaces: la tabla conserva la página de la búsqueda anterior.
 pagina = Math.min(pagina, Math.max(0, Math.ceil(lista.length / POR_PAG) - 1));
 document.getElementById(F('pnlGrdResultadosProcesos')).innerHTML =
  `<div id="${F('dtProcesos')}"><table><thead id="${F('dtProcesos_head')}"><tr><th><span>N°</span></th><th><span>Nombre o Sigla de la Entidad</span></th>` +
  `<th><span>Fecha y Hora de Publicacion</span></th><th><span>Nomenclatura</span></th><th><span>Reiniciado Desde</span></th>` +
  `<th><span>Objeto de Contratación</span></th><th><span>Descripción de Objeto</span></th><th><span>Código SNIP</span></th>` +
  `<th><span>Código Unico de Inversion</span></th><th><span>VR / VE / Cuantía de la contratación</span></th><th><span>Moneda</span></th>` +
  `<th><span>Versión SEACE</span></th><th><span>Acciones</span></th></tr></thead><tbody id="${F('dtProcesos_data')}"></tbody></table>` +
  `<div id="${F('dtProcesos_paginator_bottom')}"><span class="ui-paginator-current"></span>` +
  `<span class="ui-paginator-first ui-state-default" onclick="primera(this)">|&lt;</span>` +
  `<span class="ui-paginator-next ui-state-default" onclick="siguiente(this)">&gt;</span></div></div>`;
 pintar();
}
function pintar(){
 const cuerpo = document.getElementById(F('dtProcesos_data'));
 const trozo = lista.slice(pagina * POR_PAG, (pagina + 1) * POR_PAG);
 cuerpo.innerHTML = trozo.length ? trozo.map((f, i) => `<tr><td>${pagina * POR_PAG + i + 1}</td><td>${f[0]}</td><td>${f[1]}</td><td>${f[2]}</td><td></td><td>${f[3]}</td><td>${f[4]}</td>` +
  `<td><a href="#"><img id="${F('dtProcesos:' + i + ':graCodSnip')}"></a></td><td></td><td>---</td><td>Soles</td><td>3</td>` +
  `<td><a href="#" onclick="return false;"><img id="${F('dtProcesos:' + i + ':grafacciones1')}" alt="historial"></a> ` +
  `<a href="#" onclick="document.getElementById('idFicha').value='${f[5]}';document.getElementById('${F('')}'.slice(0,-1)).submit();return false;">` +
  `<img id="${F('dtProcesos:' + i + ':grafichaSel')}" alt="ficha"></a></td></tr>`).join('')
  : '<tr class="ui-datatable-empty-message"><td colspan="13">No se encontraron Datos</td></tr>';
 const paginas = Math.max(1, Math.ceil(lista.length / POR_PAG));
 const pie = document.getElementById(F('dtProcesos_paginator_bottom'));
 pie.querySelector('.ui-paginator-current').textContent = `[ Mostrando del total ${lista.length} - Página: ${pagina + 1}/${paginas} ]`;
 pie.querySelector('.ui-paginator-first').className = 'ui-paginator-first ui-state-default' + (pagina === 0 ? ' ui-state-disabled' : '');
 pie.querySelector('.ui-paginator-next').className = 'ui-paginator-next ui-state-default' + (pagina + 1 >= paginas ? ' ui-state-disabled' : '');
}
function primera(b){ if (b.className.includes('ui-state-disabled')) return; setTimeout(() => { pagina = 0; pintar(); }, 300); }
function siguiente(b){ if (b.className.includes('ui-state-disabled')) return; setTimeout(() => { pagina++; pintar(); }, 300); }
</script></body></html>"""

FICHA = """<html><head><meta charset="utf-8"></head><body>
<table><tr><td>Nomenclatura:</td><td id="nom"></td></tr></table>
<table><tr><th>Etapa</th><th>Fecha Inicio</th></tr><tr><td>Otorgamiento de la Buena Pro</td><td>02/09/2026</td></tr></table>
<div id="tbFicha:dtDocumentos"><div>Lista de Documentos</div><table><thead id="tbFicha:dtDocumentos_head"><tr><th>Nro.</th><th>Etapa</th>
<th>Documento</th><th>Archivo</th><th>Fecha y Hora de publicación</th><th>Acciones</th></tr></thead>
<tbody id="tbFicha:dtDocumentos_data"></tbody></table>
<div id="tbFicha:dtDocumentos_paginator_bottom"><span class="ui-paginator-next ui-state-default">&gt;</span>
<select class="ui-paginator-rpp-options"><option value="5" selected>5</option><option value="10">10</option><option value="15">15</option></select></div></div>
<script>
const id = new URLSearchParams(location.search).get('id');
const NOM = {f1: "LP-ABR-3-2026-MDC/CS-1", f3: "AS-SM-2-2026-MDU-1", f4: "LP-SM-1-2026-MDM-C-1", f6: "AS-SM-9-2026-ML-1"};
document.getElementById('nom').textContent = NOM[id] || '';
const docs = [["Convocatoria","Bases Administrativas","bases.pdf"], ["Absolución de consultas y observaciones","Pliego","pliego.pdf"],
 ["Integración de las Bases","Bases Integradas","bi.pdf"], ["Presentación de propuestas","Documentos de Presentación de Propuestas","pp.zip"],
 ["Calificación y Evaluación de propuestas","Documentos de Calificación y Evaluación","ce.zip"]];
if (!['f3', 'f6'].includes(id)) docs.push(["Otorgamiento de la Buena Pro","Documentos de Otorgamiento de Buena Pro","bp_" + id + ".zip"]);
let pag = 0, rpp = 5;
function descargaDocGeneral(a, d, c){ window.location = a; }
function pintar(){
 const trozo = docs.slice(pag * rpp, (pag + 1) * rpp);
 document.getElementById('tbFicha:dtDocumentos_data').innerHTML = trozo.map((d, i) =>
  `<tr><td>${pag * rpp + i + 1}</td><td> ${d[0]}</td><td>${d[1]}</td><td><img src="zip.png"><a href="#" onclick="return false;"></a>` +
  `<a href="#" onclick="javascript:descargaDocGeneral('${d[2]}','3','${d[2]}');return false;"><span>(20 KB)</span></a></td>` +
  `<td>02/09/2026 16:31</td><td></td></tr>`).join('');
 document.querySelector('.ui-paginator-next').className = 'ui-paginator-next ui-state-default' + ((pag + 1) * rpp >= docs.length ? ' ui-state-disabled' : '');
}
document.querySelector('.ui-paginator-next').onclick = e => { if (!e.target.className.includes('disabled')) setTimeout(() => { pag++; pintar(); }, 200); };
document.querySelector('.ui-paginator-rpp-options').onchange = e => setTimeout(() => { rpp = +e.target.value; pag = 0; pintar(); }, 200);
pintar();
</script></body></html>"""


@pytest.fixture()
def sitio(tmp_path):
    (tmp_path / "buscadorPublico.html").write_text(BUSCADOR.replace("__ANIO__", str(date.today().year)), encoding="utf-8")
    (tmp_path / "fichaSeleccion.html").write_text(FICHA, encoding="utf-8")
    (tmp_path / "bp_f1.zip").write_bytes(zip_bp(reporte_pdf([("HOJUELA DE AVENA", [["20611902329-ALEMARO E.I.R.L.", "", "1000.0", "4500"]])])))
    (tmp_path / "bp_f4.zip").write_bytes(zip_bp(reporte_pdf([("LECHE EVAPORADA", [
        ["20609822806-CONSORCIO ATUMPAMPA", "20609822806-INVERSIONES ATUMPAMPA S.A.C.", "58853.0", "476709.30"]])])))
    manejador = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    manejador.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()


def _navegador(p):
    try:
        return p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    except Exception as exc:  # sin navegador instalado
        pytest.skip(f"sin navegador: {exc}")


def test_robot_en_replica(sitio, monkeypatch):
    base, tmp = sitio
    monkeypatch.setattr(prod2, "URL", base + "/buscadorPublico.html")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = _navegador(p)
        page = nav.new_context(accept_downloads=True).new_page()
        robot = prod2.RobotSEACE(page, tmp / "diag", preguntar=lambda *_: "", log=lambda *_: None,
                                 carpeta_zips=tmp / "zips", pausa=(0, 0))
        dias = (date.today() - date(2026, 1, 1)).days
        adjs, pendientes = prod2.recolectar(robot, prod2.Cache(tmp / "cache.json"), dias=dias,
                                            terminos=["avena", "vaso de leche"])
        nav.close()
    # El heno para animales se descarta; Carabamba y Manantay (en la 2.ª página) tienen
    # ganador; Uco aún no; el de 2020 queda fuera del periodo. La búsqueda de "vaso de
    # leche" debe volver a la página 1 (donde está el de Lechera, que aún no tiene ganador).
    assert {(a.nomenclatura, a.categoria, a.ruc_ganador, a.monto) for a in adjs} == {
        ("LP-ABR-3-2026-MDC/CS-1", "Avena", "20611902329", 4500.0),
        ("LP-ABR-3-2026-MDC/CS-1", "Vaso de Leche", "20611902329", 4500.0),
        ("LP-SM-1-2026-MDM-C-1", "Avena", "20609822806", 476709.30),
        ("LP-SM-1-2026-MDM-C-1", "Vaso de Leche", "20609822806", 476709.30)}
    manantay = next(a for a in adjs if a.nomenclatura == "LP-SM-1-2026-MDM-C-1")
    assert manantay.ganador.startswith("CONSORCIO ATUMPAMPA (20609822806-INVERSIONES ATUMPAMPA S.A.C.")
    assert str(manantay.fecha_buena_pro) == "2026-09-02"
    assert [c.nomenclatura for c in pendientes] == ["AS-SM-2-2026-MDU-1", "AS-SM-9-2026-ML-1"]
    cache = prod2.Cache(tmp / "cache.json")
    assert cache.get("LP-ABR-3-2026-MDC/CS-1")["ganadores"][0]["ruc"] == "20611902329"
    assert (tmp / "zips" / "LP-ABR-3-2026-MDC_CS-1.zip").exists()
    assert not (tmp / "diag").exists()


def test_cache_evita_volver_a_descargar(sitio, monkeypatch):
    base, tmp = sitio
    monkeypatch.setattr(prod2, "URL", base + "/buscadorPublico.html")
    cache = prod2.Cache(tmp / "cache.json")
    cache.put("LP-ABR-3-2026-MDC/CS-1", {"fecha_buena_pro": "2026-09-02T16:31:00", "ganadores": [
        {"item": "1", "descripcion": "", "resultado": "Adjudicado", "ruc": "20111111111", "nombre": "DE LA CACHE SAC",
         "integrantes": [], "monto": 10.0}]})
    abiertas = []
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = _navegador(p)
        page = nav.new_context(accept_downloads=True).new_page()
        robot = prod2.RobotSEACE(page, tmp / "diag", preguntar=lambda *_: "", log=lambda *_: None, pausa=(0, 0))
        original = robot.abrir_ficha
        monkeypatch.setattr(robot, "abrir_ficha", lambda pr: abiertas.append(pr.nomenclatura) or original(pr))
        adjs, _ = prod2.recolectar(robot, cache, dias=3650, terminos=["kiwicha"])
        nav.close()
    assert abiertas == []
    assert {a.ganador for a in adjs} == {"DE LA CACHE SAC"}
