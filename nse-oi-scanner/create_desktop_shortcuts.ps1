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
    # Windows forbids \ / : * ? " < > | in a filename. A "/" in a shortcut name is read as
    # a folder separator and throws - which, with ErrorActionPreference=Stop, aborted the
    # whole script and silently dropped every launcher after it, including the kill switch.
    $safe = $name
    foreach ($ch in @('\','/',':','*','?','"','<','>','|')) { $safe = $safe.Replace($ch, '-') }
    try {
        $lnk = $sh.CreateShortcut((Join-Path $dir "$safe.lnk"))
        $lnk.TargetPath       = (Join-Path $here $bat)
        $lnk.WorkingDirectory = $here
        $lnk.IconLocation     = "$iconDll,$iconIdx"
        $lnk.Description      = $desc
        $lnk.Save()
        Write-Host "  [OK] $safe"
    } catch {
        # One bad launcher must never cost the others - especially the kill switch.
        Write-Host "  [!!] $safe  ->  $($_.Exception.Message)"
        $script:failed = $script:failed + 1
    }
}
$script:failed = 0

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

# --- DAILY. Eight icons, because the folder has to be readable at 9:20am. ---
# Everything else still exists and still works - it moved to Tools, one folder in.
# Deleting a working tool to tidy a screen is how you lose it the week you need it.
New-Shortcut $folder "0 - LAUNCHER"        "run_launcher.bat"    (Join-Path $here "tbone.ico") 0 "Ek window - credentials, engine, log"
New-Shortcut $folder "0 - UPDATE"          "UPDATE.bat"          "%SystemRoot%\System32\shell32.dll" 46  "Naya code + icons"
New-Shortcut $folder "1 - START DAY"       "START-DAY.bat"       "%SystemRoot%\System32\shell32.dll" 44  "Login + lot check + paper trader + check-in"
New-Shortcut $folder "2 - CHECK-IN"        "CHECKIN.bat"         "%SystemRoot%\System32\shell32.dll" 138 "Kya hold, kya book, kya naya"
New-Shortcut $folder "3 - DESK (website)"  "run_desk.bat"        "%SystemRoot%\System32\shell32.dll" 13  "Dashboard: signals, charts, opportunities"
New-Shortcut $folder "4 - PAPER LIVE"      "run_paper_session.bat" "%SystemRoot%\System32\shell32.dll" 137 "Poora din - har candle pe trade/exit/trail"
New-Shortcut $folder "5 - ORDER"           "BUY-ORDER.bat"       "%SystemRoot%\System32\shell32.dll" 71  "Browser se order - IP whitelist ki zaroorat nahi"
New-Shortcut $folder "LIVE - arm or disarm" "LIVE-ARM.bat"       "%SystemRoot%\System32\shell32.dll" 48  "Asli order chalu/band"
New-Shortcut $folder "STOP - Kill Switch"  "STOP-TRADING.bat"    "%SystemRoot%\System32\shell32.dll" 131 "PANIC: sab band"

# --- TOOLS. Used sometimes, not daily. ---
$tools = Join-Path $folder "Tools"
if (-not (Test-Path $tools)) { New-Item -ItemType Directory -Path $tools | Out-Null }
Get-ChildItem -Path $tools -Filter *.lnk -ErrorAction SilentlyContinue | Remove-Item -Force
New-Shortcut $tools "Login only"          "run_login.bat"       "%SystemRoot%\System32\shell32.dll" 47  "Sirf token refresh"
New-Shortcut $tools "LIYA (bought)"       "BOUGHT.bat"          "%SystemRoot%\System32\shell32.dll" 165 "Trade book mein daalo"
New-Shortcut $tools "NIKLA (sold)"        "SOLD.bat"            "%SystemRoot%\System32\shell32.dll" 166 "Exit record karo"
New-Shortcut $tools "Paper score"         "run_paper.bat"       "%SystemRoot%\System32\shell32.dll" 71  "Backtest ke against score"
New-Shortcut $tools "Paper auto (setup)"  "SETUP-PAPER.bat"     "%SystemRoot%\System32\shell32.dll" 43  "Ek baar: roz apne aap"
New-Shortcut $tools "Paper auto (stop)"   "STOP-PAPER.bat"      "%SystemRoot%\System32\shell32.dll" 109 "Roz-apne-aap band karo"
New-Shortcut $tools "Find Best Setup"     "run_sweep.bat"       "%SystemRoot%\System32\shell32.dll" 21  "Walk-forward sweep"
New-Shortcut $tools "Suggestions backtest" "run_backtest_cards.bat" "%SystemRoot%\System32\shell32.dll" 172 "Jo cards chhapte hain unka asli P&L"
New-Shortcut $tools "Ablation test"       "run_hypothesis.bat"  "%SystemRoot%\System32\shell32.dll" 24  "Har filter ki asli keemat - isi ne RRG ko kaata"
New-Shortcut $tools "Short book test"    "run_short_test.bat"  "%SystemRoot%\System32\shell32.dll" 168 "LONG vs SHORT vs BOTH - ek hi data pe"
New-Shortcut $tools "Robustness Test"     "run_robustness.bat"  "%SystemRoot%\System32\shell32.dll" 166 "Edge ko DISPROVE karne ki koshish"
New-Shortcut $tools "Journal"             "run_journal.bat"     "%SystemRoot%\System32\shell32.dll" 47  "Purane signals grade karo"
New-Shortcut $tools "Sector feed probe" "run_sectors.bat"     "%SystemRoot%\System32\shell32.dll" 18  "Kaunse index symbols resolve hote hain"
New-Shortcut $tools "Watchlist (Q1)"      "run_watchlist.bat"   "%SystemRoot%\System32\shell32.dll" 70  "Q1 list mein se kaunse F&O mein hain"
New-Shortcut $tools "Lot Audit"           "run_lot_audit.bat"   "%SystemRoot%\System32\shell32.dll" 77  "Har naam ka lot check"
New-Shortcut $tools "Expiry Check"        "run_expiry_check.bat" "%SystemRoot%\System32\shell32.dll" 137 "Kaunsi expiry sasti"
New-Shortcut $tools "Chart list (TradingView)" "run_pine_export.bat" "%SystemRoot%\System32\shell32.dll" 13 "Aaj ke naam -> Pine + watchlist"
New-Shortcut $tools "Pine vs Python"     "run_pine_test.bat"   "%SystemRoot%\System32\shell32.dll" 23 "Chart aur engine ke numbers ek hain ya nahi"
New-Shortcut $tools "Sector map test"    "run_sectors_test.bat" "%SystemRoot%\System32\shell32.dll" 23 "Sector membership sahi nikalta hai ya nahi"
New-Shortcut $tools "Desk render test"    "run_desk_test.bat"   "%SystemRoot%\System32\shell32.dll" 23  "Website sach mein render hoti hai ya nahi"
New-Shortcut $tools "Telegram alerts"     "TELEGRAM-SETUP.bat"  "%SystemRoot%\System32\shell32.dll" 12  "Phone pe alert"
New-Shortcut $tools "Secret update"       "SET-SECRET.bat"      "%SystemRoot%\System32\shell32.dll" 48  "Fyers secret badla toh"
New-Shortcut $tools "MCP token"           "SET-FIA-TOKEN.bat"   "%SystemRoot%\System32\shell32.dll" 48  "Fyers MCP token"
New-Shortcut $tools "First-time setup"    "FIRST-TIME-SETUP.bat" "%SystemRoot%\System32\shell32.dll" 45 "Naye computer pe zero se - clone + keys"
New-Shortcut $tools "Build the .exe"      "BUILD-EXE.bat"        "%SystemRoot%\System32\shell32.dll" 130 "Desktop pe .exe banao (ek baar)"
New-Shortcut $tools "Launcher test"       "run_launcher_test.bat" "%SystemRoot%\System32\shell32.dll" 23 "Window sach mein banti hai ya nahi"

# a shortcut straight to the code folder, handy for config.py edits
$lnk = $sh.CreateShortcut((Join-Path $folder "Open code folder.lnk"))
$lnk.TargetPath = $here
$lnk.Description = "The scanner folder (config.py, logs, paper_book.json)"
$lnk.Save()

Write-Host ""
Write-Host "================================================================"
Write-Host "  Done. ONE folder on your Desktop:  $folderName"
Write-Host "  Open it - everything is inside, numbered in running order."
if ($script:failed -gt 0) { Write-Host "  [!!] $($script:failed) launcher(s) nahi bane - upar dekh." }
Write-Host "  Roz:  1 - START DAY.  Baaki sab Tools folder mein."
Write-Host "================================================================"
