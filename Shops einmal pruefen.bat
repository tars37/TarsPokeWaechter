@echo off
rem Prueft alle aktiven Shops einmal und zeigt das Ergebnis (sendet keine Nachrichten).
cd /d "%~dp0"
py tarspokewaechter.py --einmal
pause
