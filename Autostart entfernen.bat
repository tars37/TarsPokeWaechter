@echo off
rem Entfernt die Autostart-Verknuepfung wieder.
powershell -NoProfile -Command ^
  "$pfad = Join-Path ([Environment]::GetFolderPath('Startup')) 'TarsPokeWaechter.lnk';" ^
  "if (Test-Path $pfad) { Remove-Item $pfad; Write-Host 'Autostart entfernt.' } else { Write-Host 'Kein Autostart eingerichtet.' }"
pause
