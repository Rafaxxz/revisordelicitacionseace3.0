@echo off
REM Revisa las licitaciones grandes del SEACE (prod2) desde esta PC y genera el PDF.
REM Se abre una ventana de Chrome: no la cierres. Si aparece un captcha, resuélvelo.
cd /d %~dp0
python -m pip install -r requirements.txt --quiet
python -m playwright install chromium
python -m revisor.prod2_local %*
echo.
echo Listo. El PDF esta en la carpeta "reportes".
start "" "%~dp0reportes"
pause
