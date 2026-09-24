@echo off
title Create Desktop Shortcut - DroidRouter 9
chcp 65001 > nul
cd /d "%~dp0"

echo ======================================================================
echo       TẠO PHÍM TẮT DROIDROUTER 9 RA MÀN HÌNH CHÍNH (DESKTOP)
echo ======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $desktops = @([Environment]::GetFolderPath('Desktop'), 'C:\Users\Admin\Desktop', 'C:\Users\Admin\OneDrive\Desktop') | Select-Object -Unique; foreach ($d in $desktops) { if (Test-Path $d) { $s = $WshShell.CreateShortcut(\"$d\DroidRouter 9.lnk\"); $s.TargetPath = 'C:\Program Files\Python314\pythonw.exe'; $s.Arguments = '\"%~dp0launcher.pyw\"'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0app_icon.ico, 0'; $s.Description = 'DroidRouter 9 - Android VM & Proxy Gateway Engine'; $s.Save(); Write-Host \"[OK] Đã tạo biểu tượng tại: $d\DroidRouter 9.lnk\" } }"

echo.
echo Hoàn tất! Biểu tượng DroidRouter 9 đã sẵn sàng trên màn hình Desktop của bạn.
echo Bạn chỉ cần nhấp đúp vào icon đó để mở ứng dụng như một phần mềm Windows thông thường.
echo.
pause
