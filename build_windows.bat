@echo off
REM ============================================================================
REM  AudioSync Pro — Windows .exe builder
REM
REM  Usage:
REM    build_windows.bat
REM
REM  Output:
REM    dist\AudioSync Pro\AudioSync Pro.exe
REM
REM  Prerequisites:
REM    - Python 3.10+ with pip
REM    - pip install -r requirements.txt
REM    - pip install pyinstaller
REM    - (Optional) icon.ico in project root
REM
REM  To generate icon.ico from icon.png:
REM    pip install Pillow
REM    python -c "from PIL import Image; Image.open('icon.png').save('icon.ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
REM ============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo   AudioSync Pro — Building Windows Application
echo ===================================================
echo.

REM --- Check dependencies ---
echo → Checking dependencies...

python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo ERROR: PyQt6 not installed. Run: pip install PyQt6
    exit /b 1
)

python -c "import numpy" 2>nul
if errorlevel 1 (
    echo ERROR: numpy not installed. Run: pip install numpy
    exit /b 1
)

python -c "import scipy" 2>nul
if errorlevel 1 (
    echo ERROR: scipy not installed. Run: pip install scipy
    exit /b 1
)

python -c "import soundfile" 2>nul
if errorlevel 1 (
    echo ERROR: soundfile not installed. Run: pip install soundfile
    exit /b 1
)

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo ERROR: PyInstaller not installed. Run: pip install pyinstaller
    exit /b 1
)

echo   All dependencies found.

REM --- Check for icon ---
set ICON_FLAG=
if exist "icon.ico" (
    set ICON_FLAG=--icon=icon.ico
    echo   Found icon.ico
) else (
    echo   WARNING: icon.ico not found — building without custom icon.
    echo   To create one from icon.png, run:
    echo     pip install Pillow
    echo     python -c "from PIL import Image; Image.open('icon.png').save('icon.ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
)

REM --- Clean previous builds ---
echo.
echo → Cleaning previous builds...
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul

REM --- Read version ---
for /f "tokens=2 delims='\"" %%a in ('python -c "from version import __version__; print(__version__)"') do set VERSION=%%a
python -c "from version import __version__; print(__version__)" > _ver.tmp
set /p VERSION=<_ver.tmp
del _ver.tmp 2>nul

echo.
echo → Building version %VERSION%...
echo   This may take a few minutes...
echo.

REM --- Build with PyInstaller ---
pyinstaller ^
    --name "AudioSync Pro" ^
    --windowed ^
    --onedir ^
    %ICON_FLAG% ^
    --add-data "core;core" ^
    --add-data "app;app" ^
    --add-data "version.py;." ^
    --hidden-import "scipy.signal" ^
    --hidden-import "scipy.fft" ^
    --hidden-import "scipy.fft._pocketfft" ^
    --hidden-import "numpy" ^
    --hidden-import "soundfile" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --exclude-module "tkinter" ^
    --exclude-module "matplotlib" ^
    --exclude-module "PIL" ^
    --exclude-module "IPython" ^
    --exclude-module "jupyter" ^
    --noconfirm ^
    --clean ^
    main.py

echo.
echo ===================================================

if exist "dist\AudioSync Pro\AudioSync Pro.exe" (
    echo   BUILD SUCCESSFUL
    echo.
    echo   Exe:  dist\AudioSync Pro\AudioSync Pro.exe
    echo.
    echo   To run:
    echo     "dist\AudioSync Pro\AudioSync Pro.exe"
    echo.
    echo   NOTE: Users must have ffmpeg installed and in PATH
    echo   for video file support. Download from:
    echo     https://ffmpeg.org/download.html
) else (
    echo   BUILD FAILED — check output above for errors.
    exit /b 1
)

echo ===================================================
endlocal
