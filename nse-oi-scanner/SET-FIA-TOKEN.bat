@echo off
REM Stores the Fyers MCP token as a permanent user environment variable, so the MCP
REM config in .mcp.json can read it without the token ever being written into a file
REM that git tracks. The repository is public - a token pasted into a committed file
REM stays readable long after it is revoked.
setlocal
echo.
echo   ================================================================
echo    FYERS MCP TOKEN
echo   ================================================================
echo.
echo   Ye token Fyers se milega (MCP / FIA section mein).
echo   Yahan paste kar - ye sirf tere Windows user ke environment mein
echo   jayega, kisi file mein nahi, git mein toh bilkul nahi.
echo.
set /p TOK=  FIA_TOKEN:
if "%TOK%"=="" (
    echo.
    echo   Kuch nahi likha - kuch nahi badla.
    echo.
    pause
    exit /b 1
)
setx FIA_TOKEN "%TOK%" >nul
echo.
echo   [OK] FIA_TOKEN set ho gaya.
echo.
echo   ZAROORI: naya terminal kholna padega - setx purane windows mein
echo   asar nahi karta. Uske baad is folder mein Claude Code chala,
echo   .mcp.json apne aap uth jayega.
echo.
pause
