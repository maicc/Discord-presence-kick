@echo off
title Compilar KickPresence
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0build.ps1" %*
echo.
echo Presiona una tecla para cerrar...
pause >nul
