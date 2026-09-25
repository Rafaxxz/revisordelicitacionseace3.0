from datetime import date

from revisor.digesa import campos_formulario, leer_grilla

HTML = """
<form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc&amp;1" />
<input name="ctl00$X$TextBox_ConsultaRUC" type="text" id="x" />
<input type="submit" name="ctl00$X$Button" value="Buscar" />
<select name="ctl00$X$ddlAñoEmision_RUC"><option value="2026">2026</option><option selected="selected" value="2025">2025</option></select>
<table class="grid" id="ctl00_ContentPlaceHolder1_GridView1">
 <tr><th>REGISTRO</th><th>CERTIFICADO</th><th>EXPEDIENTE</th><th>PRODUCTOS</th><th>FECHA EMISION</th>
     <th>FECHA INICIO VIGENCIA</th><th>FECHA VENCIMIENTO</th><th>EMPRESA</th><th>DIRECCION</th><th></th><th></th></tr>
 <tr><td>A1234567N/NAAVEN</td><td>1-2024</td><td>2-2024-R</td><td>HOJUELA DE AVENA - AVENA PRECOCIDA</td>
     <td>6 de Agosto del 2024</td><td>06/08/2024</td><td>06/08/2029</td><td>AVENAS SAC</td><td>AV. X</td><td>1</td><td>1</td></tr>
 <tr><td colspan="11"><table><tr><td><span>1</span></td><td><a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$GridView1','Page$2')">2</a></td></tr></table></td></tr>
</table></form>
"""


def test_campos_formulario():
    d = dict(campos_formulario(HTML))
    assert d["__VIEWSTATE"] == "abc&1"
    assert d["ctl00$X$TextBox_ConsultaRUC"] == ""
    assert d["ctl00$X$ddlAñoEmision_RUC"] == "2025"
    assert "ctl00$X$Button" not in d


def test_leer_grilla():
    regs, paginas = leer_grilla(HTML)
    assert paginas == [2]
    assert len(regs) == 1
    r = regs[0]
    assert r.codigo == "A1234567N/NAAVEN" and r.titular == "AVENAS SAC"
    assert r.producto.startswith("HOJUELA DE AVENA")
    assert r.fecha_vencimiento == date(2029, 8, 6)
