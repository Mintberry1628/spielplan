@echo off
REM ============================================================
REM  Spielplan – lokale Vorschau starten
REM  Doppelklick auf diese Datei: startet einen kleinen Server
REM  und oeffnet die App im Browser. Zum Beenden Fenster schliessen.
REM ============================================================
title Spielplan Vorschau
cd /d "%~dp0docs"
echo.
echo  Spielplan-Vorschau laeuft auf:  http://localhost:8000
echo  Zum Beenden dieses Fenster schliessen.
echo.
start "" "http://localhost:8000/index.html"
python -m http.server 8000
