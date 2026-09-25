"""Pruebas del cliente SEACE prod6 con respuestas que imitan la forma real de la API."""
from datetime import date, timedelta

from revisor.categorias import ARROZ_FORTIFICADO, AVENA, VASO_DE_LECHE
from revisor.sources import prod6

HOY = date.today().strftime("%d/%m/%Y")


def fila(id_, desc, estado=4, objeto="Bien", fecha=HOY):
    return {"idContrato": id_, "desContratacion": f"CM-{id_}-2026-X", "desObjetoContrato": desc,
            "nomObjetoContrato": objeto, "idEstadoContrato": estado,
            "nomEstadoContrato": {2: "Vigente", 3: "En Evaluación", 4: "Culminado"}[estado],
            "fecPublica": f"{fecha} 10:00:00", "fecIniCotizacion": f"{fecha} 11:00:00",
            "fecFinCotizacion": f"{fecha} 17:00:00", "nomEntidad": "MUNICIPALIDAD X"}


FILAS = {
    4: [fila(1, "ADQUISICION DE HOJUELA DE AVENA PARA EL PROGRAMA DEL VASO DE LECHE"),
        fila(2, "ADQUISICIÓN DE HENO DE CEBADA, AVENA Y RAY GRASS PARA EL EJEMPLAR DE CAPIBARA"),
        fila(3, "SERVICIO DE ALQUILER DE CAMIONETA PARA EL PROGRAMA DE VASO DE LECHE", objeto="Servicio"),
        fila(4, "ADQUISICION DE TINTAS PARA IMPRESORA DEL PROGRAMA VASO DE LECHE"),
        fila(5, "ADQUISICION DE ARROZ FORTIFICADO")],
    3: [fila(6, "ADQUISICION DE LECHE EVAPORADA PARA EL PROGRAMA DEL VASO DE LECHE", estado=3)],
    2: [],
}

DETALLES = {
    1: {"uitContratoEtapaProjectionList": [{"fecFin": f"{HOY} 17:30:00"}],
        "uitContratoItemProjectionList": [
            {"descripcionItem": "HOJUELA DE AVENA", "codRuc": "20111111111", "nomRazonSocial": "AVENAS SAC",
             "precioTotal": 1500, "nomEstadoCotiza": "ADJUDICADO"},
            {"descripcionItem": "AVENA PRECOCIDA", "codRuc": "20111111111", "nomRazonSocial": "AVENAS SAC",
             "precioTotal": 500.5, "nomEstadoCotiza": "ADJUDICADO"}]},
    5: {"uitContratoItemProjectionList": [{"descripcionItem": "ARROZ", "codRuc": None, "nomEstadoCotiza": "DESIERTO"}]},
}


class Falso(prod6.ClienteSEACE):
    def __init__(self):
        super().__init__(pausa=0)

    def _get(self, ruta, params):
        if ruta == "buscador":
            filas = FILAS[params["lista_estado_contrato"]] if params["page"] == 1 else []
            return {"data": filas, "pageable": {"totalElements": len(filas)}}
        return DETALLES.get(params["id_contrato"], {})


def test_categorias_excluye_no_alimentos():
    assert prod6.categorias_de("HENO DE AVENA PARA CAPIBARA") == []
    assert prod6.categorias_de("ALQUILER DE CAMIONETA PARA EL VASO DE LECHE", "Servicio") == []
    assert prod6.categorias_de("TINTAS PARA EL PROGRAMA VASO DE LECHE", "Bien") == []
    assert prod6.categorias_de("HOJUELA DE AVENA PARA EL VASO DE LECHE", "Bien") == [AVENA, VASO_DE_LECHE]


def test_recolectar_y_ganadores():
    cli = Falso()
    culminadas, abiertas = prod6.recolectar(cli, dias=30, terminos=["x"], log=lambda *_: None)
    assert sorted(c.id for c in culminadas) == [1, 5]
    assert [c.id for c in abiertas] == [6]
    adjs = prod6.ganadores(cli, culminadas, log=lambda *_: None)
    assert {(a.categoria, a.ruc_ganador, a.monto) for a in adjs} == {
        (AVENA, "20111111111", 2000.5), (VASO_DE_LECHE, "20111111111", 2000.5)}
    assert adjs[0].fecha_buena_pro == date.today()
    assert "HOJUELA DE AVENA" in adjs[0].descripcion
    assert not any(a.categoria == ARROZ_FORTIFICADO for a in adjs)  # quedó desierto


def test_recolectar_corta_por_fecha():
    viejo = (date.today() - timedelta(days=90)).strftime("%d/%m/%Y")
    FILAS_VIEJAS = {4: [fila(9, "HOJUELA DE AVENA", fecha=viejo)], 3: [], 2: []}

    class Viejo(Falso):
        def _get(self, ruta, params):
            f = FILAS_VIEJAS[params["lista_estado_contrato"]]
            return {"data": f, "pageable": {"totalElements": len(f)}}

    culminadas, _ = prod6.recolectar(Viejo(), dias=30, terminos=["x"], log=lambda *_: None)
    assert culminadas == []


def test_sigue_abierta():
    hoy = date(2026, 9, 25)
    base = prod6._a_contratacion(fila(7, "HOJUELA DE AVENA", estado=2))
    from datetime import datetime as dt
    base.fin_cotizacion = dt(2026, 9, 26, 17)
    assert prod6.sigue_abierta(base, hoy)
    base.fin_cotizacion = dt(2025, 5, 16, 15)
    assert not prod6.sigue_abierta(base, hoy)          # "Vigente" de hace meses
    base.estado = "En Evaluación"
    base.fin_cotizacion = dt(2026, 9, 1)
    assert prod6.sigue_abierta(base, hoy)
    base.fin_cotizacion = dt(2025, 12, 18)
    assert not prod6.sigue_abierta(base, hoy)


def test_excluye_papeleria_pvl():
    assert prod6.categorias_de("MATERIALES, PAPELERIA EN GENERAL PARA LA OFICINA DEL PROGRAMA VASO DE LECHE", "Bien") == []
