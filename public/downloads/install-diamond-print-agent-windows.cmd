@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-diamond-print-agent-windows.ps1" -Start
if errorlevel 1 pause
