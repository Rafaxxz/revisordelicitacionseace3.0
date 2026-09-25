"""Exploración (GitHub Actions): variantes de envío del formulario RUC de DIGESA."""
import re, urllib.parse, requests
from html import unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
U = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
T = "ctl00$ContentPlaceHolder1$TabContainer1$TabPanel_ConsultaRUC$"

def formulario(html):
    datos = []
    for m in re.finditer(r"<input\b[^>]*>", html):
        tag = m.group(0); name = re.search(r'name="([^"]+)"', tag)
        if not name: continue
        typ = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1]
        if typ in ("submit", "button", "image") or (typ in ("checkbox", "radio") and "checked" not in tag): continue
        val = re.search(r'value="([^"]*)"', tag)
        datos.append([unescape(name.group(1)), unescape(val.group(1)) if val else ""])
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        opts = re.findall(r'<option([^>]*)value="([^"]*)"', m.group(2))
        sel = [v for a, v in opts if "selected" in a] or [v for a, v in opts[:1]]
        datos.append([unescape(m.group(1)), unescape(sel[0]) if sel else ""])
    return datos

def poner(d, k, v):
    for par in d:
        if par[0] == k: par[1] = v; return
    d.append([k, v])

def texto(t): return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t)))

def resumen(nombre, r):
    t = r.text
    print(f"\n##### {nombre}: HTTP {r.status_code} len={len(t)} ALICORP={'ALICORP' in t.upper()}")
    if r.status_code != 200:
        m = re.search(r"Exception Details:(.{0,300})", texto(t)); print("   ", m.group(1) if m else texto(t)[:300]); return
    for tid in re.findall(r'<table[^>]*id="([^"]+)"', t):
        blk = re.search(r'<table[^>]*id="' + re.escape(tid) + r'".*?</table>', t, re.S).group(0)
        filas = re.findall(r"<tr.*?</tr>", blk, re.S)
        if len(filas) >= 2:
            print(f"   tabla {tid}: {len(filas)} filas")
            for f in filas[:4]:
                print("    |", [texto(c).strip()[:45] for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", f, re.S)])
    i = t.upper().find("ALICORP")
    if i >= 0: print("   contexto:", texto(t[max(0, i - 600):i + 600])[:700])

for variante in ("completo", "async", "latin1"):
    s = requests.Session(); s.headers.update({"User-Agent": UA, "Referer": U, "Origin": "https://consultas-digesa.minsa.gob.pe"})
    d = formulario(s.get(U, timeout=60).text)
    poner(d, T + "TextBox_ConsultaRUC", "20100055237")
    poner(d, T + "ddlAñoEmision_RUC", "2020")
    poner(d, T + "Button_ConsultaRUC", "Buscar")
    h = {}
    if variante == "async":
        poner(d, "ctl00$ContentPlaceHolder1$ScriptManager1",
              "ctl00$ContentPlaceHolder1$TabContainer1$TabPanel_ConsultaRUC$UpdatePanel8|" + T + "Button_ConsultaRUC")
        poner(d, "__ASYNCPOST", "true")
        h = {"X-MicrosoftAjax": "Delta=true", "X-Requested-With": "XMLHttpRequest",
             "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
    if variante == "latin1":
        cuerpo = urllib.parse.urlencode(d, encoding="latin-1")
        r = s.post(U, data=cuerpo, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=90)
    else:
        r = s.post(U, data=d, headers=h, timeout=90)
    resumen(variante, r)
