param(
  [switch]$Start
)

$ErrorActionPreference = 'Stop'
$appDir = Join-Path $env:LOCALAPPDATA 'DiamondEducation\PrintAgent'
$sourceUrl = if ($env:DIAMOND_PRINT_AGENT_SOURCE) { $env:DIAMOND_PRINT_AGENT_SOURCE.TrimEnd('/') } else { 'https://diamond-education.uz/downloads' }
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Host 'Python 3 topilmadi. Avval https://www.python.org/downloads/windows/ dan Python 3.11+ o''rnating, so''ng shu faylni qayta ishga tushiring.' -ForegroundColor Yellow
  exit 1
}

New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri "$sourceUrl/diamond-print-agent.py" -OutFile (Join-Path $appDir 'diamond-print-agent.py')
Invoke-WebRequest -UseBasicParsing -Uri "$sourceUrl/run-diamond-print-agent-windows.bat" -OutFile (Join-Path $appDir 'run-diamond-print-agent-windows.bat')
Invoke-WebRequest -UseBasicParsing -Uri "$sourceUrl/configure-xprinter-56mm-windows.ps1" -OutFile (Join-Path $appDir 'configure-xprinter-56mm-windows.ps1')
Invoke-WebRequest -UseBasicParsing -Uri "$sourceUrl/install-xprinter-raw-driver-windows.ps1" -OutFile (Join-Path $appDir 'install-xprinter-raw-driver-windows.ps1')

# Creating a Windows printer queue requires elevation. This runs only the
# bundled local script; it never downloads or executes an arbitrary driver.
$driverScript = Join-Path $appDir 'install-xprinter-raw-driver-windows.ps1'
try {
  $driverArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$driverScript`""
  $driverProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList $driverArgs -Verb RunAs -Wait -PassThru
  if ($driverProcess.ExitCode -ne 0) {
    Write-Host 'Printer drayveri avtomatik tayyorlanmadi. Printerni USB orqali ulang va installerni qayta ishga tushiring.' -ForegroundColor Yellow
  }
} catch {
  Write-Host 'Driver oynasi rad etildi. Agent o‘rnatildi, lekin printer drayverini keyinroq administrator sifatida o‘rnating.' -ForegroundColor Yellow
}

$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Diamond Education Print Agent.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $appDir 'run-diamond-print-agent-windows.bat'
$shortcut.WorkingDirectory = $appDir
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "O'rnatildi: $appDir" -ForegroundColor Green
# Old agent processes keep the previous receipt protocol in memory. Stop only
# this application's process before launching the newly installed one.
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'diamond-print-agent\.py' } | ForEach-Object {
  try { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null } catch { }
}
Write-Host 'Agent Windows bilan avtomatik ishga tushadi. XP-58IIL raw drayveri/queue mavjud bo‘lmasa avtomatik tayyorlanadi; default printer shart emas. Test va haqiqiy chek kesilishidan oldin taxminan 18 mm tashqariga chiqariladi.'
Write-Host 'Brauzer fallbacki uchun configure-xprinter-56mm-windows.ps1 ni ishga tushirib, driverda 56 mm ni tanlang.'
Start-Process (Join-Path $appDir 'run-diamond-print-agent-windows.bat')
