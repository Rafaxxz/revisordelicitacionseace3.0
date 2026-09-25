from datetime import date

from revisor.contactos import BuscadorContactos
from revisor.digesa import leer_grilla
from revisor.modelos import SIN_REGISTRO, Adjudicacion, ResultadoGanador, Verificacion
from revisor.pdf import generar_pdf
from revisor.revisor import Reporte

FICHA = {"proveedorT01": {"numRuc": "20611902329", "emails": ["ventas@ejemplo.pe", "null"],
                          "telefonos": ["988000111", "988000111"], "esHabilitado": True}}
RESUMEN = {"datosSunat": {"estado": "ACTIVO", "condicion": "HABIDO", "departamento": "LIMA",
                          "provincia": "LIMA", "distrito": "SANTIAGO DE SURCO"},
           "conformacion": {"representantes": [{"razonSocial": "perez rojas ana", "nroDocumento": "12345678"}]}}


class Resp:
    def __init__(self, d):
        self.status_code, self._d = 200, d

    def json(self):
        return self._d


class Sesion:
    headers: dict = {}

    def get(self, url, timeout=0):
        return Resp(RESUMEN if url.endswith("/resumen") else FICHA)


def test_buscar_contacto():
    c = BuscadorContactos(pausa=0, sesion=Sesion()).buscar("20611902329", "AV. LOS PINOS 123")
    assert c.telefonos == ["988000111"]
    assert c.correos == ["ventas@ejemplo.pe"]
    assert c.ubicacion == "LIMA / LIMA / SANTIAGO DE SURCO"
    assert c.estado_sunat == "ACTIVO - HABIDO"
    assert c.representante == "PEREZ ROJAS ANA"
    assert c.direccion == "AV. LOS PINOS 123"
    assert "12345678" not in str(c.a_dict())  # no se guardan DNI


def test_pdf_con_contacto():
    a = Adjudicacion("Avena", "CM-1", "MUNI", "HOJUELA DE AVENA", "ALEMARO EIRL", "20611902329", 10.0,
                     contacto=BuscadorContactos(pausa=0, sesion=Sesion()).buscar("20611902329").a_dict())
    sin = Adjudicacion("Avena", "CM-2", "MUNI", "AVENA", "PERSONA", "10409952319", 5.0,
                       contacto={"telefonos": [], "correos": [], "ubicacion": "CAJAMARCA"})
    rep = Reporte(date.today(), date.today(),
                  [ResultadoGanador(x, Verificacion(SIN_REGISTRO)) for x in (a, sin)])
    assert generar_pdf(rep).startswith(b"%PDF")


def test_digesa_direccion():
    html = ('<table id="ctl00_ContentPlaceHolder1_GridView1"><tr><th>REGISTRO</th><th>CERTIFICADO</th><th>EXPEDIENTE</th>'
            '<th>PRODUCTOS</th><th>FECHA EMISION</th><th>FECHA INICIO VIGENCIA</th><th>FECHA VENCIMIENTO</th>'
            '<th>EMPRESA</th><th>DIRECCION</th></tr><tr><td>A1</td><td>1</td><td>2</td><td>AVENA</td><td>x</td>'
            '<td>01/01/2024</td><td>01/01/2029</td><td>EMP</td><td>AV. X 123</td></tr></table>')
    regs, _ = leer_grilla(html)
    assert regs[0].direccion == "AV. X 123"
