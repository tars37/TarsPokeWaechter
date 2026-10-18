@echo off
rem Legt eine Verknuepfung im Autostart-Ordner an: Der TarsPokeWaechter startet dann bei jeder Anmeldung still im Hintergrund.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "$pfad = Join-Path ([Environment]::GetFolderPath('Startup')) 'TarsPokeWaechter.lnk';" ^
  "$l = $w.CreateShortcut($pfad);" ^
  "$l.TargetPath = (Get-Command pyw).Source;" ^
  "$l.Arguments = '\"%~dp0tarspokewaechter.py\" --kein-browser';" ^
  "$l.WorkingDirectory = '%~dp0';" ^
  "$l.IconLocation = '%~dp0web\icon.ico,0';" ^
  "$l.Description = 'TarsPokeWaechter - Pokemon-Restock-Wecker';" ^
  "$l.Save();" ^
  "Write-Host ('Autostart eingerichtet: ' + $pfad)"
pause
