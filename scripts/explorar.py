"""Exploración (GitHub Actions): forma real de la API prod6 del SEACE y del formulario DIGESA."""
import json, re, requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Referer": "https://prod6.seace.gob.pe/"}
B = "https://prod6.seace.gob.pe/v1/s8uit-services/buscadorpublico/contrataciones"
s = requests.Session(); s.headers.update(H)

for estado in ("", "2", "3", "4"):
    p = {"anio": 2026, "palabra_clave": "vaso de leche", "orden": 2, "page": 1, "page_size": 3}
    if estado: p["lista_estado_contrato"] = estado
    r = s.get(B + "/buscador", params=p, timeout=60)
    d = r.json()
    print(f"\n### estado={estado!r} HTTP {r.status_code} keys={list(d)} pageable={d.get('pageable')}")
    for x in d.get("data", [])[:3]:
        print(" -", x.get("idContrato"), x.get("nomEstadoContrato"), "|", x.get("desObjetoContrato", "")[:90])

r = s.get(B + "/buscador", params={"anio": 2026, "palabra_clave": "avena", "orden": 2, "page": 1, "page_size": 50, "lista_estado_contrato": 4}, timeout=60)
cul = r.json().get("data", [])
print("\n### culminados avena:", len(cul))
if cul:
    det = s.get(B + "/listar-completo", params={"id_contrato": cul[0]["idContrato"]}, timeout=60).json()
    txt = json.dumps(det, ensure_ascii=False)
    print("### detalle (recortado):", txt[:3500])

print("\n### DIGESA")
U = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
html = requests.get(U, headers={"User-Agent": H["User-Agent"]}, timeout=60).text
for m in re.findall(r'<(?:input|select|a)[^>]*(?:RUC|Ruc|ruc|Buscar|buscar)[^>]*>', html)[:40]:
    print(m[:300])
