param(
  [switch]$Start
)

$ErrorActionPreference = 'Stop'
$appDir = Join-Path $env:LOCALAPPDATA 'DiamondEducation\PrintAgent'
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Host 'Python 3 topilmadi. Avval https://www.python.org/downloads/windows/ dan Python 3.11+ o''rnating, so''ng shu faylni qayta ishga tushiring.' -ForegroundColor Yellow
  exit 1
}

New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item (Join-Path $sourceDir 'diamond-print-agent.py') (Join-Path $appDir 'diamond-print-agent.py') -Force
Copy-Item (Join-Path $sourceDir 'run-diamond-print-agent-windows.bat') (Join-Path $appDir 'run-diamond-print-agent-windows.bat') -Force

$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Diamond Education Print Agent.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $appDir 'run-diamond-print-agent-windows.bat'
$shortcut.WorkingDirectory = $appDir
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "O'rnatildi: $appDir" -ForegroundColor Green
Write-Host 'Agent Windows bilan avtomatik ishga tushadi. Printer Windows Default Printer qilib belgilang.'
if ($Start) { Start-Process (Join-Path $appDir 'run-diamond-print-agent-windows.bat') }
