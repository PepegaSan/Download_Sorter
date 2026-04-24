@echo off
setlocal
cd /d "%~dp0"

echo Installing PyInstaller (build only)...
python -m pip install -q -r requirements-build.txt
if errorlevel 1 (
    echo pip failed.
    pause
    exit /b 1
)

echo Building standalone EXE (Download_Sorter.spec)...
python -m PyInstaller --noconfirm --clean Download_Sorter.spec

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done: dist\Download_Sorter.exe
echo Config and download_sorter.log are created next to the EXE on first run.
pause
endlocal
