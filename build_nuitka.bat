@echo off
setlocal
cd /d "%~dp0"

echo Installing Nuitka...
python -m pip install -q "nuitka>=2.0"
if errorlevel 1 (
    echo pip failed.
    pause
    exit /b 1
)

echo.
echo Nuitka: standalone + onefile (GUI, customtkinter, watchdog)...
echo Hinweis: Ohne --onefile-no-dll kann Windows Defender main.dll sperren
echo           ^(Meldung "Failed to add resources"^). Dann Ausnahme f^ur diesen
echo           Ordner in Defender setzen oder erneut bauen.
echo.

if not exist "nuitka-build\" mkdir "nuitka-build"

python -m nuitka main.py --standalone --onefile --onefile-no-dll --windows-console-mode=disable --enable-plugin=tk-inter --include-package-data=customtkinter --include-package=darkdetect --include-package=watchdog --output-dir=nuitka-build --output-filename=Download_Sorter.exe --assume-yes-for-downloads

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done: nuitka-build\Download_Sorter.exe
pause
endlocal
