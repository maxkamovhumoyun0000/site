<#+
Opens the selected XP-58/XPrinter driver's own preferences page.  Custom
thermal forms are vendor-driver specific, so Windows cannot safely overwrite
the driver's DEVMODE from a generic script.  The script picks the thermal
queue and opens the exact dialog where the operator selects 56 mm.
#>
param(
  [string]$PrinterName = ""
)

$ErrorActionPreference = 'Stop'
if (-not $PrinterName) {
  $thermal = Get-Printer | Where-Object { $_.Name -match 'xp[-_ ]?58|xprinter|thermal|receipt|pos[-_ ]?58|58mm' }
  if ($thermal.Count -eq 1) {
    $PrinterName = $thermal[0].Name
  } elseif ($thermal.Count -gt 1) {
    $PrinterName = ($thermal | Select-Object -First 1).Name
  } else {
    Write-Host 'XP-58/XPrinter topilmadi. Printerni ulang yoki printer nomini argument qilib bering.' -ForegroundColor Yellow
    exit 1
  }
}

Write-Host "Driver sozlash ochilmoqda: $PrinterName" -ForegroundColor Green
Write-Host 'Paper Size / Qog''oz o''lchami bo''limidan Custom/Receipt ni tanlang: eni 56 mm, uzunligi Auto/80 mm, Margin 0.' -ForegroundColor Cyan
Write-Host 'Keyin Apply va OK bosing. Lokal agent ishlasa bu sozlama kerak bo''lmaydi, lekin brauzer fallbacki uchun saqlanadi.' -ForegroundColor Cyan
Start-Process rundll32.exe -ArgumentList "printui.dll,PrintUIEntry /e /n `"$PrinterName`""
