@echo off
REM Revisión del día anterior + PDF en la carpeta reportes. Programar con el
REM "Programador de tareas" de Windows para que corra cada mañana.
cd /d %~dp0
python -m revisor --ayer
