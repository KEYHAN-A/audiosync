#!/bin/bash
# ============================================================================
#  AudioSync Pro — macOS .app builder
#  
#  Usage:
#    chmod +x build_app.sh
#    ./build_app.sh
#
#  Output:
#    dist/AudioSync Pro.app
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════"
echo "  AudioSync Pro — Building macOS Application"
echo "═══════════════════════════════════════════════════"
echo ""

# Check dependencies
echo "→ Checking dependencies..."
python3 -c "import PyQt6" 2>/dev/null || { echo "ERROR: PyQt6 not installed. Run: pip install PyQt6"; exit 1; }
python3 -c "import numpy" 2>/dev/null || { echo "ERROR: numpy not installed. Run: pip install numpy"; exit 1; }
python3 -c "import scipy" 2>/dev/null || { echo "ERROR: scipy not installed. Run: pip install scipy"; exit 1; }
python3 -c "import soundfile" 2>/dev/null || { echo "ERROR: soundfile not installed. Run: pip install soundfile"; exit 1; }
python3 -c "import PyInstaller" 2>/dev/null || { echo "ERROR: PyInstaller not installed. Run: pip install pyinstaller"; exit 1; }
echo "  All dependencies found."

# Check for icon
if [ ! -f "icon.icns" ]; then
    echo "  WARNING: icon.icns not found — building without custom icon."
    ICON_FLAG=""
else
    ICON_FLAG="--icon=icon.icns"
fi

# Clean previous builds
echo ""
echo "→ Cleaning previous builds..."
rm -rf build dist *.spec 2>/dev/null || true

# Build with PyInstaller
echo ""
echo "→ Building application bundle..."
echo "  This may take a few minutes..."
echo ""

pyinstaller \
    --name "AudioSync Pro" \
    --windowed \
    --onedir \
    $ICON_FLAG \
    --osx-bundle-identifier "com.audiosync.pro" \
    --add-data "core:core" \
    --add-data "app:app" \
    --add-data "version.py:." \
    --hidden-import "scipy.signal" \
    --hidden-import "scipy.fft" \
    --hidden-import "scipy.fft._pocketfft" \
    --hidden-import "numpy" \
    --hidden-import "soundfile" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    --exclude-module "tkinter" \
    --exclude-module "matplotlib" \
    --exclude-module "PIL" \
    --exclude-module "IPython" \
    --exclude-module "jupyter" \
    --noconfirm \
    --clean \
    main.py

echo ""
echo "═══════════════════════════════════════════════════"

if [ -d "dist/AudioSync Pro.app" ]; then
    APP_SIZE=$(du -sh "dist/AudioSync Pro.app" | cut -f1)
    echo "  BUILD SUCCESSFUL"
    echo ""
    echo "  App:  dist/AudioSync Pro.app"
    echo "  Size: $APP_SIZE"
    echo ""
    echo "  To run:"
    echo "    open \"dist/AudioSync Pro.app\""
    echo ""
    echo "  To install:"
    echo "    cp -r \"dist/AudioSync Pro.app\" /Applications/"
    echo ""
else
    echo "  BUILD FAILED — check output above for errors."
    exit 1
fi

echo "═══════════════════════════════════════════════════"
