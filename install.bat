@echo off
setlocal
cd /d "%~dp0"

echo Abhaengigkeiten werden installiert...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Installation fehlgeschlagen. Ist Python im PATH?
    pause
    exit /b 1
)

echo.
echo Fertig.
pause
endlocal
