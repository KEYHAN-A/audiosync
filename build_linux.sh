#!/bin/bash
# ============================================================================
#  AudioSync Pro — Linux builder
#
#  Usage:
#    chmod +x build_linux.sh
#    ./build_linux.sh
#
#  Output:
#    dist/AudioSync Pro          (single-file portable executable)
#
#  Prerequisites:
#    - Python 3.10+ with pip
#    - pip install -r requirements.txt
#    - pip install pyinstaller
#    - System packages: libxcb-xinerama0 (for Qt on some distros)
#
#  For AppImage packaging (optional):
#    - Install appimagetool: https://appimage.github.io/appimagetool/
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════"
echo "  AudioSync Pro — Building Linux Application"
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

# Read version
VERSION=$(python3 -c "from version import __version__; print(__version__)")
echo "  Version: $VERSION"

# Clean previous builds
echo ""
echo "→ Cleaning previous builds..."
rm -rf build dist *.spec 2>/dev/null || true

# Check for icon (use PNG on Linux)
ICON_FLAG=""
if [ -f "icon.png" ]; then
    ICON_FLAG="--icon=icon.png"
    echo "  Found icon.png"
fi

# Build with PyInstaller
echo ""
echo "→ Building portable executable..."
echo "  This may take a few minutes..."
echo ""

pyinstaller \
    --name "AudioSync Pro" \
    --onefile \
    $ICON_FLAG \
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

if [ -f "dist/AudioSync Pro" ]; then
    FILE_SIZE=$(du -sh "dist/AudioSync Pro" | cut -f1)
    echo "  BUILD SUCCESSFUL"
    echo ""
    echo "  Binary: dist/AudioSync Pro"
    echo "  Size:   $FILE_SIZE"
    echo ""
    echo "  To run:"
    echo "    ./\"dist/AudioSync Pro\""
    echo ""
    echo "  To install system-wide:"
    echo "    sudo cp \"dist/AudioSync Pro\" /usr/local/bin/audiosync-pro"
    echo "    sudo chmod +x /usr/local/bin/audiosync-pro"
    echo ""

    # Optional: Create AppImage structure
    if command -v appimagetool &> /dev/null; then
        echo "→ appimagetool found — creating AppImage..."
        APPDIR="dist/AudioSync_Pro.AppDir"
        mkdir -p "$APPDIR/usr/bin"
        mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

        cp "dist/AudioSync Pro" "$APPDIR/usr/bin/audiosync-pro"
        chmod +x "$APPDIR/usr/bin/audiosync-pro"

        if [ -f "icon.png" ]; then
            cp icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/audiosync-pro.png"
            cp icon.png "$APPDIR/audiosync-pro.png"
        fi

        cat > "$APPDIR/audiosync-pro.desktop" << 'DESKTOP'
[Desktop Entry]
Name=AudioSync Pro
Exec=audiosync-pro
Icon=audiosync-pro
Type=Application
Categories=AudioVideo;Audio;
Comment=Multi-device audio/video synchronization tool
DESKTOP
        cp "$APPDIR/audiosync-pro.desktop" "$APPDIR/usr/share/applications/audiosync-pro.desktop" 2>/dev/null || true

        cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "${HERE}/usr/bin/audiosync-pro" "$@"
APPRUN
        chmod +x "$APPDIR/AppRun"

        ARCH=$(uname -m)
        appimagetool "$APPDIR" "dist/AudioSync_Pro-${VERSION}-${ARCH}.AppImage"
        echo "  AppImage: dist/AudioSync_Pro-${VERSION}-${ARCH}.AppImage"
    else
        echo "  TIP: Install appimagetool for AppImage packaging:"
        echo "    https://appimage.github.io/appimagetool/"
    fi
else
    echo "  BUILD FAILED — check output above for errors."
    exit 1
fi

echo ""
echo "  NOTE: Users need ffmpeg installed for video file support:"
echo "    sudo apt install ffmpeg"
echo ""
echo "═══════════════════════════════════════════════════"
