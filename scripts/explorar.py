"""Exploración (GitHub Actions): datos de contacto de proveedores en el OECE."""
import json, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122", "Accept": "application/json"}
for ruc in ("20611902329", "10409952319", "20479379735"):
    for url in (f"https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{ruc}",
                f"https://eap.oece.gob.pe/ficha-proveedor-cns/1.0/ficha/{ruc}/resumen"):
        try:
            r = requests.get(url, headers=H, timeout=40)
            d = r.json()
            txt = json.dumps(d, ensure_ascii=False)
            print(f"\n### {ruc} {url.split('/')[3]} HTTP {r.status_code} len={len(txt)}")
            print(txt[:1800])
        except Exception as e:
            print(ruc, url, "ERROR", e)
