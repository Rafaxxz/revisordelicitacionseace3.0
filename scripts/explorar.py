"""Exploración (GitHub Actions): consulta DIGESA por RUC enviando el formulario completo."""
import re, requests
from html import unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
U = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
P = "ctl00$ContentPlaceHolder1$TabContainer1$TabPanel_ConsultaRUC$"
s = requests.Session(); s.headers["User-Agent"] = UA
html = s.get(U, timeout=60).text

def formulario(html):
    datos = {}
    for m in re.finditer(r"<input\b[^>]*>", html):
        tag = m.group(0)
        name = re.search(r'name="([^"]+)"', tag)
        if not name: continue
        typ = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1]
        if typ in ("submit", "button", "image"): continue
        if typ in ("checkbox", "radio") and "checked" not in tag: continue
        val = re.search(r'value="([^"]*)"', tag)
        datos[unescape(name.group(1))] = unescape(val.group(1)) if val else ""
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        opts = re.findall(r'<option([^>]*)value="([^"]*)"', m.group(2))
        sel = [v for a, v in opts if "selected" in a] or [v for a, v in opts[:1]]
        datos[unescape(m.group(1))] = unescape(sel[0]) if sel else ""
    return datos

d = formulario(html)
print("campos:", len(d))
for k, v in d.items():
    if "VIEWSTATE" not in k and "EVENTVALIDATION" not in k: print("  ", k, "=", v[:60])
blk = re.search(r'name="' + re.escape(P + "ddlAñoEmision_RUC") + r'".*?</select>', html, re.S)
print("años:", re.findall(r'<option[^>]*value="([^"]*)"', blk.group(0)) if blk else None)

d[P + "TextBox_ConsultaRUC"] = "20100055237"
d[P + "ddlEstado_RUC"] = "%"
d[P + "Button_ConsultaRUC"] = "Buscar"
d["ctl00_ContentPlaceHolder1_TabContainer1_ClientState"] = '{"ActiveTabIndex":1,"TabEnabledState":[true,true,true,true,true,true],"TabWasLoadedOnceState":[true,true,false,false,false,false]}'
r = s.post(U, data=d, headers={"Referer": U, "Origin": "https://consultas-digesa.minsa.gob.pe"}, timeout=90)
t = r.text
print("POST", r.status_code, len(t))
if r.status_code != 200:
    txt = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t)))
    print(txt[:1500])
else:
    for tid in re.findall(r'<table[^>]*id="([^"]+)"', t):
        blk = re.search(r'<table[^>]*id="' + re.escape(tid) + r'".*?</table>', t, re.S).group(0)
        filas = re.findall(r"<tr.*?</tr>", blk, re.S)
        if "RUC" in tid or "Grid" in tid or len(filas) > 2:
            print(f"\n== {tid}: {len(filas)} filas")
            for f in filas[:5]:
                print(" |", [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()[:60] for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", f, re.S)])
    print("contiene ALICORP:", "ALICORP" in t.upper())
