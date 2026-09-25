#!/usr/bin/env bash
# Explora desde GitHub Actions las páginas de consulta de DIGESA.
set +e
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
curl -sSL -A "$UA" -m 40 https://www.digesa.minsa.gob.pe/ -o /tmp/home.html
echo "== enlaces de la portada relacionados con registros/consultas"
grep -oiE 'href="[^"]+"[^>]*>[^<]{0,80}' /tmp/home.html | grep -iE 'regist|consult|alimen|expedient|dato|vuce' | sort -u | head -80
