@echo off
REM Instala dependencias (solo la primera vez) y abre el revisor en el navegador.
cd /d %~dp0
python -m pip install -r requirements.txt --quiet
start "" http://127.0.0.1:5000
python -m revisor web
