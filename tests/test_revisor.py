from datetime import date
from pathlib import Path

from revisor.categorias import (ARROZ_FORTIFICADO, ARROZ_SIMIL, AVENA, VASO_DE_LECHE, clasificar)
from revisor.modelos import CON_REGISTRO, NO_VERIFICADO, SIN_REGISTRO, Adjudicacion
from revisor.pdf import generar_pdf
from revisor.registro_sanitario import BaseRegistros, normalizar_empresa
from revisor.revisor import revisar
from revisor.sources import archivo
from revisor.sources.ocds import adjudicaciones_de_paquete
from revisor.tablas import a_monto

DEMO = Path(__file__).resolve().parent.parent / "data" / "demo"


def test_clasificar():
    assert clasificar("Adquisición de hojuela de AVENA precocida") == [AVENA]
    assert clasificar("Alimento símil arroz fortificado") == [ARROZ_SIMIL]
    assert clasificar("ARROZ FORTIFICADO con hierro") == [ARROZ_FORTIFICADO]
    assert clasificar("Leche evaporada para el Programa del Vaso de Leche") == [VASO_DE_LECHE]
    assert clasificar("Avena para el PVL 2026") == [AVENA, VASO_DE_LECHE]
    assert clasificar("Arroz pilado superior") == []
    assert clasificar("Compra de útiles de oficina") == []


def test_montos():
    assert a_monto("185.430,00") == 185430.0
    assert a_monto("185,430.00") == 185430.0
    assert a_monto("S/ 1 200,5") == 1200.5
    assert a_monto("") is None


def test_normalizar_empresa():
    assert normalizar_empresa("Alimentos del Sur S.A.C.") == normalizar_empresa("ALIMENTOS DEL SUR SAC")
    assert normalizar_empresa("Demo E.I.R.L.") == "demo"


def test_importar_csv_filtra_fecha_y_categoria():
    adjs = archivo.importar(DEMO / "seace" / "demo_buena_pro.csv", date(2026, 9, 24), date(2026, 9, 24))
    assert {a.ruc_ganador for a in adjs} == {"20000000011", "20000000022"}
    avena = next(a for a in adjs if a.categoria == AVENA)
    assert avena.monto == 185430.0 and avena.ganador.startswith("AGROINDUSTRIAS")


def test_ocds():
    paquete = {"records": [{"compiledRelease": {
        "ocid": "x", "buyer": {"name": "MUNI"},
        "tender": {"id": "AS-1", "title": "Arroz fortificado"},
        "awards": [
            {"status": "active", "date": "2026-09-25T10:00:00-05:00", "value": {"amount": 10},
             "suppliers": [{"name": "A SAC", "identifier": {"id": "20111111111"}}]},
            {"status": "cancelled", "date": "2026-09-25", "suppliers": [{"name": "B"}]},
        ]}}]}
    adjs = adjudicaciones_de_paquete(paquete, date(2026, 9, 25), date(2026, 9, 25))
    assert len(adjs) == 1 and adjs[0].ruc_ganador == "20111111111" and adjs[0].categoria == ARROZ_FORTIFICADO
    assert adjudicaciones_de_paquete(paquete, date(2026, 9, 26), date(2026, 9, 26)) == []


def test_verificacion():
    base = BaseRegistros()
    assert base.verificar(Adjudicacion(AVENA, "", "", "", "X", "1")).estado == NO_VERIFICADO
    base.cargar_carpeta(DEMO / "digesa")
    con = base.verificar(Adjudicacion(AVENA, "", "", "", "AGROINDUSTRIAS DEMO ANDINA SAC", ""))
    assert con.estado == CON_REGISTRO
    assert [r.producto for r in con.relacionados] == ["HOJUELA DE AVENA PRECOCIDA"]
    sin = base.verificar(Adjudicacion(ARROZ_SIMIL, "", "", "", "Otra", "20999999999"))
    assert sin.estado == SIN_REGISTRO
    vencido = base.verificar(Adjudicacion(ARROZ_FORTIFICADO, "", "", "", "", "20000000033"))
    assert "vencidos" in vencido.nota


def test_revision_completa_y_pdf():
    base = BaseRegistros()
    base.cargar_carpeta(DEMO / "digesa")
    archivos = [(str(p), None) for p in sorted((DEMO / "seace").iterdir())]
    rep = revisar(date(2026, 9, 24), date(2026, 9, 25), archivos=archivos, en_linea=False, base=base)
    grupos = rep.por_categoria()
    assert len(grupos[AVENA]) == 2 and len(grupos[VASO_DE_LECHE]) == 3
    pdf = generar_pdf(rep)
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


def test_web():
    from revisor.app import app
    cliente = app.test_client()
    assert cliente.get("/").status_code == 200
    r = cliente.post("/revisar", data={"desde": "2026-09-25", "demo": "1"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "<details" in html and "HOJUELA DE AVENA PRECOCIDA" in html
    rid = html.split("/pdf/")[1].split('"')[0]
    pdf = cliente.get(f"/pdf/{rid}")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
