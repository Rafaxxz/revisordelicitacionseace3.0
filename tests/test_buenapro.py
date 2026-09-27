from revisor.buenapro import leer_texto, leer_zip
from tests.generar_reporte_bp import reporte_pdf, zip_bp

TEXTO = """REPORTE DE OTORGAMIENTO DE BUENA PRO
Entidad convocante : PROGRAMA DE DESARROLLO PRODUCTIVO AGRARIO RURAL - AGRO RURAL
Nomenclatura : DIRECTA-DIRECTA-18-2026-MIDAGRI-AGRORUR-1
Descripción del objeto : ADQUISICIÓN DE ALIMENTO SUPLEMENTARIO (HENO DE ALFALFA Y/O AVENA)
Nro. Item : 1 Cantidad Solicitada 67000.0 Valor Referencial : S/ 227,800.00 Resultado Adjudicado
Descripción del HENO DE ALFALFA Y/O AVENA - APURIMAC Unidad de Medida : Kilogramo Cantidad Desierta : 0.0
Nombre o Razón Social Integrante del Consorcio Cantidad Adjudicada Monto Adjudicado
10428536890-TICONA MENDEZ NESTOR FAUSTO 67000.0 227800
Nro. Item : 2 Cantidad Solicitada 38000.0 Valor Referencial : S/ 125,400.00 Resultado Adjudicado
Descripción del HENO DE ALFALFA Y/O AVENA - AREQUIPA Unidad de Medida : Kilogramo Cantidad Desierta : 0.0
Nombre o Razón Social Integrante del Consorcio Cantidad Adjudicada Monto Adjudicado
10404987114-MAMANI JACINTO YUDY KARIN 38000.0 125400
"""


def test_texto_como_la_captura():
    rep = leer_texto(TEXTO)
    assert rep.nomenclatura == "DIRECTA-DIRECTA-18-2026-MIDAGRI-AGRORUR-1"
    assert "AGRO RURAL" in rep.entidad
    assert [(g.item, g.ruc, g.nombre, g.cantidad, g.monto) for g in rep.ganadores] == [
        ("1", "10428536890", "TICONA MENDEZ NESTOR FAUSTO", 67000.0, 227800.0),
        ("2", "10404987114", "MAMANI JACINTO YUDY KARIN", 38000.0, 125400.0)]
    assert rep.ganadores[0].descripcion.startswith("HENO DE ALFALFA Y/O AVENA - APURIMAC")
    assert rep.ganadores[0].resultado == "Adjudicado"


def test_pdf_real_dentro_del_zip():
    pdf = reporte_pdf([("HOJUELA DE AVENA - LIMA", [["20611902329-ALEMARO E.I.R.L.", "", "1000.0", "4500"]]),
                       ("LECHE EVAPORADA", [["CONSORCIO LACTEOS DEL SUR", "20111111111-LACTEOS A SAC", "500.0", "2500.5"]])])
    rep = leer_zip(zip_bp(pdf))
    assert rep.nomenclatura == "DIRECTA-DIRECTA-18-2026-MIDAGRI-AGRORUR-1"
    g1, g2 = rep.ganadores
    assert (g1.ruc, g1.nombre, g1.monto) == ("20611902329", "ALEMARO E.I.R.L.", 4500.0)
    assert g2.consorcio == "CONSORCIO LACTEOS DEL SUR" and g2.integrantes == [("20111111111", "LACTEOS A SAC")]
    assert g2.monto == 2500.5


def test_reporte_real_con_diseno():
    """Texto (con diseño) de un reporte real del SEACE: la cabecera sale ordenada y el
    segundo integrante del consorcio queda debajo de los montos."""
    from pathlib import Path
    texto = (Path(__file__).parent / "datos" / "reporte_bp_LP-SM-1-2026-MDM-C-1.txt").read_text(encoding="utf-8")
    rep = leer_texto(texto)
    assert rep.entidad == "MUNICIPALIDAD DISTRITAL DE MANANTAY"
    assert rep.nomenclatura == "LP-SM-1-2026-MDM-C-1"
    assert rep.descripcion.endswith("LECHE EVAPORADA ENTERA-PERIODO 2026")
    (g,) = rep.ganadores
    assert (g.item, g.resultado, g.ruc, g.nombre) == ("2", "Adjudicado", "20609822806", "CONSORCIO ATUMPAMPA")
    assert (g.cantidad, g.monto) == (58853.0, 476709.30)
    assert g.integrantes == [("20609822806", "INVERSIONES ATUMPAMPA S.A.C."),
                             ("20600571916", "EMPRESA DE COMERCIALIZACION DE ALIMENTOS SHILCAYO S.A.C.")]
    assert g.descripcion.startswith("ADQUISICION DE HOJUELAS DE AVENA, QUINUA PRECOCIDA")
    assert g.descripcion.endswith("CON VITAMINAS Y MINERALES")


def test_nombre_sin_el_final_de_la_descripcion():
    """En este reporte real la descripción del ítem se monta sobre la tabla y, con diseño,
    su final ("MINERALES¿") queda pegado al nombre; el texto sin diseño lo corrige."""
    from pathlib import Path
    from revisor.buenapro import corregir_nombres
    datos = Path(__file__).parent / "datos"
    rep = leer_texto((datos / "reporte_bp_LP-ABR-2-2026-MDT_CS-1_diseno.txt").read_text(encoding="utf-8"))
    assert rep.ganadores[0].nombre.endswith("MINERALES¿")
    corregir_nombres(rep, (datos / "reporte_bp_LP-ABR-2-2026-MDT_CS-1_simple.txt").read_text(encoding="utf-8"))
    (g,) = rep.ganadores
    assert (g.ruc, g.nombre, g.cantidad, g.monto) == ("20480786212", "PROCESADORA INDURLAC E.I.R.L.", 24666.0, 204727.80)
    assert rep.nomenclatura == "LP-ABR-2-2026-MDT/CS-1"
