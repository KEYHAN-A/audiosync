# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect ALL opentimelineio submodules so adapters (.otio, .fcpxml, .edl) work
otio_hidden = collect_submodules('opentimelineio')
# Collect OTIO data files (plugin manifests, adapter configs)
otio_datas = collect_data_files('opentimelineio')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'), ('app', 'app'), ('version.py', '.')] + otio_datas,
    hiddenimports=otio_hidden + ['scipy.signal', 'scipy.fft', 'scipy.fft._pocketfft', 'numpy', 'soundfile', 'certifi', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AudioSync Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AudioSync Pro',
)
app = BUNDLE(
    coll,
    name='AudioSync Pro.app',
    icon='icon.icns',
    bundle_identifier='com.audiosync.pro',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '10.15',
        'CFBundleShortVersionString': '2.4.0',
    },
)
