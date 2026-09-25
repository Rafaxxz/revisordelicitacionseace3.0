"""Exploración (GitHub Actions): consulta DIGESA por RUC con un navegador real (Playwright)."""
import re
from playwright.sync_api import sync_playwright

U = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
PFX = "#ctl00_ContentPlaceHolder1_TabContainer1_TabPanel_ConsultaRUC_"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(U, wait_until="networkidle", timeout=90000)
    tabs = pg.locator(".ajax__tab_tab").all_inner_texts()
    print("pestañas:", tabs)
    pg.locator(".ajax__tab_tab", has_text=re.compile("RUC", re.I)).first.click()
    for anio in ("2026", "2015"):
        pg.fill(PFX + "TextBox_ConsultaRUC", "20100055237")
        pg.select_option(PFX + "ddlEstado_RUC", "%")
        pg.select_option(PFX + "ddlAñoEmision_RUC", anio)
        pg.click(PFX + "Button_ConsultaRUC")
        pg.wait_for_load_state("networkidle", timeout=90000)
        pg.wait_for_timeout(1500)
        panel = pg.locator("#ctl00_ContentPlaceHolder1_TabContainer1_TabPanel_ConsultaRUC")
        tablas = panel.locator("table").all()
        print(f"\n### año {anio}: {len(tablas)} tablas en el panel RUC")
        for t in tablas:
            filas = t.locator("tr").all()
            if len(filas) < 2:
                continue
            tid = t.get_attribute("id")
            print(f"== tabla id={tid} filas={len(filas)}")
            for f in filas[:6]:
                print(" |", [c.strip()[:50] for c in f.locator("th,td").all_inner_texts()])
        txt = pg.inner_text("body")
        m = re.search(r"(\d+)\s+registro", txt)
        print("mensaje:", m.group(0) if m else None, "| ALICORP en página:", "ALICORP" in txt.upper())
        # grid fuera del panel (resultados pueden ir en otro UpdatePanel)
        for tid in pg.eval_on_selector_all("table[id]", "els => els.map(e => e.id + ':' + e.rows.length)"):
            if not tid.endswith(":0") and not tid.endswith(":1"):
                print("   tabla global", tid)
    b.close()
