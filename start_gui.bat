@echo off
setlocal
cd /d "%~dp0"

python main.py
if errorlevel 1 (
    echo.
    echo Start fehlgeschlagen. Ist Python installiert und im PATH?
    pause
    exit /b 1
)

endlocal
