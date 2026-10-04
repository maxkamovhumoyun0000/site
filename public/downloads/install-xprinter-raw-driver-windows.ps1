<#
Creates a safe raw ESC/POS queue for a directly connected XP-58IIL/XPrinter.
It never changes an existing thermal queue and refuses to guess when more
than one USB printer port is present.
#>
param()

$ErrorActionPreference = 'Stop'
$thermalPattern = 'xp[-_ ]?58|xprinter|thermal|receipt|pos[-_ ]?58|58mm'
$existing = @(Get-Printer | Where-Object { $_.Name -match $thermalPattern -or $_.DriverName -match $thermalPattern })
if ($existing.Count -gt 0) {
  Write-Host "Mavjud termal printer ishlatiladi: $($existing[0].Name)" -ForegroundColor Green
  exit 0
}

$usbPorts = @(Get-PrinterPort | Where-Object { $_.Name -match '^USB\d+$' })
if ($usbPorts.Count -ne 1) {
  Write-Host 'XP-58IIL uchun yagona USB printer port topilmadi. Noto‘g‘ri A4 printer yaratilmasligi uchun queue qo‘shilmadi.' -ForegroundColor Yellow
  exit 0
}

$driverName = 'Generic / Text Only'
if (-not (Get-PrinterDriver -Name $driverName -ErrorAction SilentlyContinue)) {
  Add-PrinterDriver -Name $driverName
}
Add-Printer -Name 'Diamond_XP58IIL' -DriverName $driverName -PortName $usbPorts[0].Name
Write-Host "XP-58IIL raw drayveri tayyor: Diamond_XP58IIL ($($usbPorts[0].Name))" -ForegroundColor Green
