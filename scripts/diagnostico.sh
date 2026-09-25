#!/usr/bin/env bash
# Comprueba desde GitHub Actions el acceso a las fuentes del revisor.
set +e
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
for u in \
  "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml" \
  "https://contratacionesabiertas.oece.gob.pe/" \
  "https://contratacionesabiertas.oece.gob.pe/api/v1/releases?page=1" \
  "https://contratacionesabiertas.osce.gob.pe/" \
  "https://contratacionesabiertas.osce.gob.pe/api/v1/releases?page=1" \
  "https://www.digesa.minsa.gob.pe/" ; do
  echo "=================== $u"
  curl -sSL -A "$UA" -m 40 -o /tmp/r -w "HTTP %{http_code} final=%{url_effective} bytes=%{size_download}\n" "$u"
  head -c 1500 /tmp/r | tr -s '\n' ; echo
done
echo "=================== formulario buscador SEACE"
curl -sSL -A "$UA" -m 40 "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml" -o /tmp/seace.html
grep -oE '<(input|select|button|img)[^>]{0,300}>' /tmp/seace.html | head -150
grep -oiE 'captcha[^"]{0,80}' /tmp/seace.html | sort -u | head
grep -oE 'id="[^"]*(tab|Tab)[^"]*"' /tmp/seace.html | sort -u | head -40
