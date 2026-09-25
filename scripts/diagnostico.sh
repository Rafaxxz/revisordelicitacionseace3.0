#!/usr/bin/env bash
set +e
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
U="https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx"
curl -sSL -A "$UA" -m 40 -w "\nHTTP %{http_code}\n" "$U" -o /tmp/rs.html
wc -c /tmp/rs.html
grep -oE '<(input|select|option|button|img|form|iframe|script)[^>]{0,250}>' /tmp/rs.html | grep -v '__VIEWSTATE"' | head -120
grep -oiE '(captcha|recaptcha)[^"<]{0,80}' /tmp/rs.html | sort -u | head
sed -e 's/<[^>]*>/ /g' /tmp/rs.html | tr -s ' \n' | head -c 3000
