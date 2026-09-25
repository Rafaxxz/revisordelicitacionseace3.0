"""Exploración (GitHub Actions): respuesta de DIGESA al consultar registros por RUC."""
import re, requests
from html import unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
U = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
P = "ctl00$ContentPlaceHolder1$TabContainer1$TabPanel_ConsultaRUC$"
s = requests.Session(); s.headers["User-Agent"] = UA
html = s.get(U, timeout=60).text
campos = {m.group(1): unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', html)}
print("hidden:", list(campos))
for sel in ("ddlEstado_RUC", "ddlAñoEmision_RUC"):
    blk = re.search(r'name="' + re.escape(P + sel) + r'".*?</select>', html, re.S)
    print(sel, re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', blk.group(0))[:12] if blk else None)
datos = dict(campos)
datos.update({P + "TextBox_ConsultaRUC": "20100055237", P + "Button_ConsultaRUC": "Buscar",
              "ctl00$ContentPlaceHolder1$TabContainer1_ClientState": '{"ActiveTabIndex":1,"TabState":[true,true,true,true,true,true]}'})
for sel in ("ddlEstado_RUC", "ddlAñoEmision_RUC"):
    blk = re.search(r'name="' + re.escape(P + sel) + r'".*?</select>', html, re.S)
    sel_opt = re.search(r'<option selected="selected" value="([^"]*)"', blk.group(0)) if blk else None
    datos[P + sel] = sel_opt.group(1) if sel_opt else ""
r = s.post(U, data=datos, timeout=90)
print("POST", r.status_code, len(r.text))
t = r.text
i = t.find("20100055237")
print("pos ruc:", i)
tablas = re.findall(r'<table[^>]*id="([^"]*(?:Grid|grid|gv)[^"]*)"', t)
print("tablas grid:", tablas)
for tid in tablas:
    blk = re.search(r'<table[^>]*id="' + re.escape(tid) + r'".*?</table>', t, re.S).group(0)
    filas = re.findall(r"<tr.*?</tr>", blk, re.S)
    print(f"\n== {tid}: {len(filas)} filas")
    for f in filas[:6]:
        celdas = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", f, re.S)]
        print(" |", celdas)
m = re.search(r"(Se encontr[^<]{0,120}|No se encontr[^<]{0,120}|registros?[^<]{0,60})", t)
print("msg:", m.group(0) if m else None)
