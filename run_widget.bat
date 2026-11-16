@echo off
title DroidTest 9 - Desktop HUD Widget
chcp 65001 > nul
cd /d "%~dp0"

start pythonw widget.pyw
exit
