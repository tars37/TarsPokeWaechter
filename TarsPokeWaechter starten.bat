@echo off
rem Startet den TarsPokeWaechter im Hintergrund (ohne Konsolenfenster) und oeffnet das Dashboard.
cd /d "%~dp0"
start "" pyw "%~dp0tarspokewaechter.py"
