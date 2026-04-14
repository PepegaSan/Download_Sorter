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

echo Building standalone EXE...
python -m PyInstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name "Download_Sorter" ^
  --collect-all customtkinter ^
  --hidden-import watchdog.observers.polling ^
  --hidden-import watchdog.observers ^
  main.py

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
