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

Write-Host "Creating desktop shortcuts..."
# shell32.dll icon indices: 13 = chart/graph, 44 = key/login, 23 = monitor/dashboard
New-Shortcut "NSE OI Scanner"    "run_scanner.bat"   "%SystemRoot%\System32\shell32.dll" 13 "Launch NSE F&O OI-Change Scanner"
New-Shortcut "Fyers Login"       "run_login.bat"     "%SystemRoot%\System32\shell32.dll" 44 "Refresh daily Fyers access token"
New-Shortcut "OI Scanner Board"  "run_dashboard.bat" "%SystemRoot%\System32\shell32.dll" 23 "Open OI Scanner dashboard (localhost:8501)"
Write-Host "`nDone. Three icons are on your Desktop."
