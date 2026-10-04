@echo off
setlocal
set APPDIR=%LOCALAPPDATA%\DiamondEducation\PrintAgent
if not exist "%APPDIR%\diamond-print-agent.py" (
  echo Diamond Print Agent topilmadi. Avval install-diamond-print-agent-windows.ps1 faylini ishga tushiring.
  pause
  exit /b 1
)
py -3 "%APPDIR%\diamond-print-agent.py"
