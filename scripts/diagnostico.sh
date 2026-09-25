#!/usr/bin/env bash
set +e
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
for u in \
  "https://prod6.seace.gob.pe/v1/s8uit-services/buscadorpublico/contrataciones/buscador?anio=2026&palabra_clave=avena&orden=2&page=1&page_size=5" \
  "https://prod6.seace.gob.pe/buscador-publico/contrataciones" \
  "https://contratacionesabiertas.oece.gob.pe/api/v1/files?page=1&paginateBy=5&format=json" \
  "https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/20100055237" \
  "https://apps.oece.gob.pe/perfilprov-ui/" \
  "https://prodapp2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml" \
  "https://prod4.seace.gob.pe/openegocio/" ; do
  echo "=================== $u"
  curl -sSL -A "$UA" -H "Accept: application/json, text/plain, */*" -H "Referer: https://prod6.seace.gob.pe/" -m 40 -o /tmp/r -w "HTTP %{http_code} bytes=%{size_download}\n" "$u"
  head -c 700 /tmp/r; echo
done
