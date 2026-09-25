"""Prueba el robot de prod2 contra una réplica local de las páginas del SEACE
(misma estructura que el buscador real: etiquetas en celdas, tabla de resultados
con 'Acciones' y ficha con 'Lista de Documentos')."""
import functools
import http.server
import os
import shutil
import threading
from pathlib import Path

import pytest

from revisor.sources import prod2
from tests.generar_reporte_bp import reporte_pdf, zip_bp

CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

BUSCADOR = """<html><head><meta charset="utf-8"></head><body>
<ul><li><a href="#">Anuncio de Contratación Futura</a></li><li><a href="#" onclick="document.getElementById('f').style.display='block'">Buscador de Procedimientos de Selección</a></li></ul>
<div id="f" style="display:none"><table>
<tr><td>Nombre o Sigla de Entidad</td><td><input id="ent"></td></tr>
<tr><td>Descripción del Objeto</td><td><input type="hidden" value="x"><input id="desc"></td></tr>
</table><button onclick="buscar()"><span>Buscar</span></button><div id="res"></div></div>
<script>
const filas = [
 ["MUNICIPALIDAD DISTRITAL DE CARABAMBA","24/09/2026 20:32","LP-ABR-3-2026-MDC/CS-1","Bien","CONTRATACIÓN DEL SUMINISTRO DE BIENES HOJUELAS DE KIWICHA, AVENA Y QUINUA CON LECHE ENTERA EN POLVO PARA EL PROGRAMA VASO DE LECHE","f1"],
 ["AGRO RURAL","22/09/2026 23:54","DIRECTA-18-2026","Bien","ADQUISICIÓN DE ALIMENTO SUPLEMENTARIO (HENO DE ALFALFA Y/O AVENA)","f2"],
 ["MUNICIPALIDAD DE UCO","20/09/2026 10:00","AS-SM-2-2026-MDU-1","Bien","ADQUISICION DE HOJUELA DE AVENA PARA EL PROGRAMA DEL VASO DE LECHE","f3"]];
function buscar(){
 const q=document.getElementById('desc').value.toLowerCase();
 let h='<table><thead><tr><th>N°</th><th>Nombre o Sigla de la Entidad</th><th>Fecha y Hora de Publicacion</th><th>Nomenclatura</th><th>Reiniciado Desde</th><th>Objeto de Contratación</th><th>Descripción de Objeto</th><th>Código SNIP</th><th>Acciones</th></tr></thead><tbody>';
 filas.filter(f=>f[4].toLowerCase().includes(q)).forEach((f,i)=>{h+=`<tr><td>${i+1}</td><td>${f[0]}</td><td>${f[1]}</td><td>${f[2]}</td><td></td><td>${f[3]}</td><td>${f[4]}</td><td></td><td><a href="#"><img alt="historial"></a><a href="ficha_${f[5]}.html?id=${f[5]}"><img alt="ficha"></a></td></tr>`});
 document.getElementById('res').innerHTML=h+'</tbody></table>';
}
</script></body></html>"""

FICHA = """<html><head><meta charset="utf-8"></head><body><h3>Lista de Documentos</h3><table>
<tr><th>Nro.</th><th>Etapa</th><th>Documento</th><th>Archivo</th></tr>
<tr><td>1</td><td>Invitación</td><td>Bases Administrativas</td><td><a href="bases.pdf">PDF</a></td></tr>
{extra}
</table></body></html>"""

FILA_BP = '<tr><td>3</td><td>Adjudicación</td><td>Documentos de Otorgamiento de Buena Pro</td><td><a href="bp_{id}.zip" download>ZIP</a></td></tr>'


@pytest.fixture()
def sitio(tmp_path):
    (tmp_path / "buscadorPublico.html").write_text(BUSCADOR, encoding="utf-8")
    (tmp_path / "ficha_f1.html").write_text(FICHA.format(extra=FILA_BP.format(id="f1")), encoding="utf-8")
    (tmp_path / "ficha_f3.html").write_text(FICHA.format(extra=""), encoding="utf-8")  # aún sin buena pro
    (tmp_path / "bp_f1.zip").write_bytes(zip_bp(reporte_pdf([("HOJUELA DE AVENA", [["20611902329-ALEMARO E.I.R.L.", "", "1000.0", "4500"]])])))
    manejador = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()


@pytest.mark.skipif(not Path(CHROME).exists() or shutil.which("true") is None, reason="sin navegador")
def test_robot_en_replica(sitio, monkeypatch):
    base, tmp = sitio
    monkeypatch.setattr(prod2, "URL", base + "/buscadorPublico.html")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME)
        page = nav.new_context(accept_downloads=True).new_page()
        robot = prod2.RobotSEACE(page, tmp / "diag", preguntar=lambda *_: "", log=lambda *_: None)
        adjs, pendientes = prod2.recolectar(robot, prod2.Cache(tmp / "cache.json"), dias=3650, terminos=["avena"])
        nav.close()
    # El heno para animales se descarta; Carabamba tiene ganador; Uco aún no.
    assert {(a.categoria, a.ruc_ganador, a.monto) for a in adjs} == {
        ("Avena", "20611902329", 4500.0), ("Vaso de Leche", "20611902329", 4500.0)}
    assert adjs[0].url.endswith("ficha_f1.html?id=f1")
    assert [c.nomenclatura for c in pendientes] == ["AS-SM-2-2026-MDU-1"]
    cache = prod2.Cache(tmp / "cache.json")
    assert cache.get("LP-ABR-3-2026-MDC/CS-1")["ganadores"][0]["ruc"] == "20611902329"
