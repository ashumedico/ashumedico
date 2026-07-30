# create_desktop_shortcuts.ps1
# AASHISH TRADING OS — desktop icons. Run via install.bat (double-click).
$ErrorActionPreference = "Stop"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$desktop = [Environment]::GetFolderPath("Desktop")
$sh      = New-Object -ComObject WScript.Shell

function New-Shortcut($name, $bat, $iconDll, $iconIdx, $desc) {
    $lnk = $sh.CreateShortcut((Join-Path $desktop "$name.lnk"))
    $lnk.TargetPath       = (Join-Path $here $bat)
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation     = "$iconDll,$iconIdx"
    $lnk.Description      = $desc
    $lnk.Save()
    Write-Host "  [OK] $name"
}

# --- clear every old icon name we have ever shipped, so the desktop stays clean ---
$stale = @(
    "NSE OI Scanner","Fyers Login","OI Scanner Board","Trade Signals","Trade Signals + RRG",
    "Signal Desk (1 page)","Auto-Trader (PAPER)","STOP Trading",
    "NSE_Options_Scanner","Fyers_Login",
    "Aashish - RRG Trader","Aashish - Signal Desk","Aashish - Fyers Login",
    "Aashish - Auto-Trader","Aashish - STOP","Aashish - OI Scanner","Aashish - Find Best Setup"
)
foreach ($old in $stale) {
    $p = Join-Path $desktop "$old.lnk"
    if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host "Creating AASHISH TRADING OS icons..."
# shell32.dll icon indices: 137 target · 13 chart · 44 key · 23 monitor · 25 gears · 131 stop · 21 search
New-Shortcut "Aashish - RRG Trader"      "run_rrg_app.bat"    "%SystemRoot%\System32\shell32.dll" 137 "Aashish Trading OS - RRG cockpit + auto-trader (localhost:8501)"
New-Shortcut "Aashish - Fyers Login"     "run_login.bat"      "%SystemRoot%\System32\shell32.dll" 44  "Get today's Fyers token (run first each morning)"
New-Shortcut "Aashish - Signal Desk"     "run_signals.bat"    "%SystemRoot%\System32\shell32.dll" 13  "One-page desk: OI buildup + 1 CE/1 PE/1 Future + charts + RRG"
New-Shortcut "Aashish - Auto-Trader"     "run_autotrader.bat" "%SystemRoot%\System32\shell32.dll" 25  "Hands-free auto-trader loop (PAPER unless armed)"
New-Shortcut "Aashish - Find Best Setup" "run_sweep.bat"      "%SystemRoot%\System32\shell32.dll" 21  "Backtest RRG setups on your own data and save the winner"
New-Shortcut "Aashish - OI Scanner"      "run_scanner.bat"    "%SystemRoot%\System32\shell32.dll" 23  "Console OI-change buildup scanner"
New-Shortcut "Aashish - STOP"            "STOP-TRADING.bat"   "%SystemRoot%\System32\shell32.dll" 131 "PANIC kill switch - halt all trading immediately"

Write-Host "`nDone. 7 icons on your Desktop, all named 'Aashish - ...'."
Write-Host "Daily order:  Fyers Login  ->  RRG Trader"
