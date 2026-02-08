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

# Clean previous builds (keep spec file — it has essential config)
echo ""
echo "→ Cleaning previous builds..."
rm -rf build dist 2>/dev/null || true

# Verify spec file exists
SPEC_FILE="AudioSync Pro.spec"
if [ ! -f "$SPEC_FILE" ]; then
    echo "  ERROR: '$SPEC_FILE' not found. This file contains required"
    echo "         build config (OTIO imports, Info.plist, etc.)."
    exit 1
fi

# Build with PyInstaller using the spec file
echo ""
echo "→ Building application bundle from spec file..."
echo "  This may take a few minutes..."
echo ""

pyinstaller \
    --noconfirm \
    --clean \
    "$SPEC_FILE"

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
