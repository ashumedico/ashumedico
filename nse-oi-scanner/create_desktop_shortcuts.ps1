# create_desktop_shortcuts.ps1
# AASHISH TRADING OS - creates ONE desktop folder holding every launcher.
# Run via install.bat (double-click).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$sh   = New-Object -ComObject WScript.Shell

# --- find the REAL Desktop. OneDrive/Known-Folder-Move often redirects it, and
#     writing to the wrong one is why a folder "gets created" but never appears. ---
$candidates = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:USERPROFILE "Desktop")
)
if ($env:OneDrive)         { $candidates += (Join-Path $env:OneDrive "Desktop") }
if ($env:OneDriveCommercial) { $candidates += (Join-Path $env:OneDriveCommercial "Desktop") }
if ($env:OneDriveConsumer) { $candidates += (Join-Path $env:OneDriveConsumer "Desktop") }
# registry is authoritative when Known Folder Move is active
try {
    $reg = (Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name Desktop -ErrorAction Stop).Desktop
    if ($reg) { $candidates = @([Environment]::ExpandEnvironmentVariables($reg)) + $candidates }
} catch { }

$desktop = $null
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { $desktop = $c; break }
}
if (-not $desktop) {
    $desktop = (Join-Path $env:USERPROFILE "Desktop")
    New-Item -ItemType Directory -Path $desktop -Force | Out-Null
}
Write-Host "Desktop detected at: $desktop"

# The one folder that holds the whole trading setup
$folderName = "AASHISH TRADING OS"
$folder     = Join-Path $desktop $folderName

function New-Shortcut($dir, $name, $bat, $iconDll, $iconIdx, $desc) {
    $lnk = $sh.CreateShortcut((Join-Path $dir "$name.lnk"))
    $lnk.TargetPath       = (Join-Path $here $bat)
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation     = "$iconDll,$iconIdx"
    $lnk.Description      = $desc
    $lnk.Save()
    Write-Host "  [OK] $name"
}

# --- clean up every loose icon we have ever dropped on the Desktop ---
$stale = @(
    "NSE OI Scanner","Fyers Login","OI Scanner Board","Trade Signals","Trade Signals + RRG",
    "Signal Desk (1 page)","Auto-Trader (PAPER)","STOP Trading",
    "NSE_Options_Scanner","Fyers_Login",
    "Aashish - RRG Trader","Aashish - Signal Desk","Aashish - Fyers Login",
    "Aashish - Auto-Trader","Aashish - STOP","Aashish - OI Scanner","Aashish - Find Best Setup","6 - OI Scanner","2 - RRG Trader","3 - Signal Desk","4 - Auto-Trader","5 - Find Best Setup","6 - Robustness Test","7 - Journal","8 - OI Scanner"
)
$removed = 0
foreach ($old in $stale) {
    $p = Join-Path $desktop "$old.lnk"
    if (Test-Path $p) { Remove-Item $p -Force; $removed++ }
}
if ($removed -gt 0) { Write-Host "Cleared $removed loose icon(s) from the Desktop." }

# --- create (or refresh) the folder ---
if (-not (Test-Path $folder)) {
    New-Item -ItemType Directory -Path $folder | Out-Null
    Write-Host "Created Desktop folder: $folderName"
} else {
    Get-ChildItem -Path $folder -Filter *.lnk -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "Refreshing folder: $folderName"
}

# --- the launchers, NUMBERED in daily running order ---
# shell32.dll icon indices: 44 key - 137 target - 13 chart - 25 gears - 21 search - 23 monitor - 131 stop
Write-Host "Adding launchers..."
New-Shortcut $folder "1 - Fyers Login"      "run_login.bat"      "%SystemRoot%\System32\shell32.dll" 44  "STEP 1: aaj ka Fyers token"
New-Shortcut $folder "2 - CHECK-IN"         "CHECKIN.bat"        "%SystemRoot%\System32\shell32.dll" 138 "STEP 2: kya hold, kya book, kya naya - bas yahi chahiye"
New-Shortcut $folder "3 - RRG Trader"       "run_rrg_app.bat"    "%SystemRoot%\System32\shell32.dll" 137 "Deep dive: RRG main window + auto-trader (localhost:8501)"
New-Shortcut $folder "4 - Signal Desk"      "run_signals.bat"    "%SystemRoot%\System32\shell32.dll" 13  "One-page desk: OI buildup + 1 CE/1 PE/1 Future + charts + RRG"
New-Shortcut $folder "5 - Auto-Trader"      "run_autotrader.bat" "%SystemRoot%\System32\shell32.dll" 25  "Hands-free auto-trader loop (PAPER unless armed)"
New-Shortcut $folder "6 - Find Best Setup"  "run_sweep.bat"      "%SystemRoot%\System32\shell32.dll" 21  "Backtest RRG setups on your own data and save the winner"
New-Shortcut $folder "7 - Robustness Test"  "run_robustness.bat" "%SystemRoot%\System32\shell32.dll" 166 "Out-of-sample + cost + regime + stability - try to DISPROVE the edge"
New-Shortcut $folder "8 - Journal"          "run_journal.bat"    "%SystemRoot%\System32\shell32.dll" 47  "Grade past signals, learn what works, what to stop"
New-Shortcut $folder "9 - OI Scanner"       "run_scanner.bat"    "%SystemRoot%\System32\shell32.dll" 23  "Console OI-change buildup scanner"
New-Shortcut $folder "SETUP - Telegram Alerts" "TELEGRAM-SETUP.bat" "%SystemRoot%\System32\shell32.dll" 12 "Ek baar: phone pe alert lagao jab T1/stop hit ho"
New-Shortcut $folder "STOP - Kill Switch"   "STOP-TRADING.bat"   "%SystemRoot%\System32\shell32.dll" 131 "PANIC: halt all trading immediately"

# a shortcut straight to the code folder, handy for config.py edits
$lnk = $sh.CreateShortcut((Join-Path $folder "Open code folder.lnk"))
$lnk.TargetPath = $here
$lnk.Description = "The scanner folder (config.py, logs, paper_book.json)"
$lnk.Save()

Write-Host ""
Write-Host "================================================================"
Write-Host "  Done. ONE folder on your Desktop:  $folderName"
Write-Host "  Open it - everything is inside, numbered in running order."
Write-Host "  Roz:  1 - Fyers Login   phir   2 - CHECK-IN   (bas itna hi)"
Write-Host "================================================================"
