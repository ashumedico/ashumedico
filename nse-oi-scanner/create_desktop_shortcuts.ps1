# create_desktop_shortcuts.ps1
# Creates 3 desktop icons for the NSE OI Scanner. Run via install.bat (double-click).
$ErrorActionPreference = "Stop"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$desktop = [Environment]::GetFolderPath("Desktop")
$sh      = New-Object -ComObject WScript.Shell

function New-Shortcut($name, $bat, $iconDll, $iconIdx, $desc) {
    $lnk = $sh.CreateShortcut((Join-Path $desktop "$name.lnk"))
    $lnk.TargetPath       = (Join-Path $here $bat)
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation     = "$iconDll,$iconIdx"
    $lnk.Description       = $desc
    $lnk.Save()
    Write-Host "  [OK] $name.lnk"
}

Write-Host "Refreshing desktop shortcuts (replacing any old ones)..."
# Remove stale icons from earlier versions so the desktop is clean
foreach ($old in @("NSE OI Scanner","Fyers Login","OI Scanner Board","Trade Signals","NSE_Options_Scanner","Fyers_Login")) {
    $p = Join-Path $desktop "$old.lnk"
    if (Test-Path $p) { Remove-Item $p -Force }
}

# shell32.dll icon indices: 13 = chart/graph, 44 = key/login, 23 = monitor, 137 = target/signals
New-Shortcut "NSE OI Scanner"      "run_scanner.bat"   "%SystemRoot%\System32\shell32.dll" 13  "Launch NSE F&O OI-Change Scanner"
New-Shortcut "Fyers Login"         "run_login.bat"     "%SystemRoot%\System32\shell32.dll" 44  "Refresh daily Fyers access token"
New-Shortcut "OI Scanner Board"    "run_dashboard.bat" "%SystemRoot%\System32\shell32.dll" 23  "Open OI Scanner dashboard (localhost:8501)"
New-Shortcut "Trade Signals + RRG" "run_signals.bat"   "%SystemRoot%\System32\shell32.dll" 137 "1 CE + 1 PE + 1 Future, 3 annotated charts + RRG rotation"
Write-Host "`nDone. Four fresh icons are on your Desktop."
