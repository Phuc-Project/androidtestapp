@echo off
title Create Desktop Shortcut - DroidTest 9
chcp 65001 > nul
cd /d "%~dp0"

echo ======================================================================
echo       TAO PHIM TAT DROIDTEST 9 & MINI WIDGET RA DESKTOP
echo ======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $shortDir = (cmd /c 'for %%I in (.) do @echo %%~fsI').Trim(); $pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; if (-not $pyw -or !(Test-Path $pyw)) { foreach ($c in @('C:\Program Files\Python314\pythonw.exe', 'C:\Program Files\Python313\pythonw.exe', 'C:\Program Files\Python312\pythonw.exe', 'C:\Program Files\Python311\pythonw.exe', 'C:\Program Files\Python310\pythonw.exe', 'C:\Users\Admin\AppData\Local\Programs\Python\Python314\pythonw.exe')) { if (Test-Path $c) { $pyw = $c; break } } }; if (-not $pyw) { $pyw = 'pythonw.exe' }; $desktops = @([Environment]::GetFolderPath('Desktop'), 'C:\Users\Admin\Desktop', 'C:\Users\Admin\OneDrive\Desktop') | Where-Object { $_ -and (Test-Path $_) -and ($_ -ne $shortDir) } | Select-Object -Unique; foreach ($d in $desktops) { $s = $WshShell.CreateShortcut(\"$d\DroidRouter 9.lnk\"); $s.TargetPath = $pyw; $s.Arguments = '\"' + $shortDir + '\launcher.pyw\"'; $s.WorkingDirectory = $shortDir; $s.IconLocation = $shortDir + '\app_icon.ico, 0'; $s.Description = 'DroidTest 9 - Android VM & Testing Engine'; $s.Save(); $sw = $WshShell.CreateShortcut(\"$d\DroidTest Mini Widget.lnk\"); $sw.TargetPath = $pyw; $sw.Arguments = '\"' + $shortDir + '\widget.pyw\"'; $sw.WorkingDirectory = $shortDir; $sw.IconLocation = $shortDir + '\app_icon.ico, 0'; $sw.Description = 'DroidTest 9 - Floating Desktop Mini Status Widget'; $sw.Save(); Write-Host \"[OK] Da tao shortcut tai: $d\" }"

echo.
echo Hoan tat! Biểu tượng DroidRouter 9 và DroidTest Mini Widget đã sẵn sàng trên màn hình Desktop.
echo.
pause
