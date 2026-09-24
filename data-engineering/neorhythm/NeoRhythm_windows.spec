# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  NeoRhythm – Windows build spec (PyInstaller)
#  Usage (on a Windows machine):
#      pip install pyinstaller pygame pyttsx3
#      pyinstaller NeoRhythm_windows.spec
#  The finished app will be in:  dist\NeoRhythm\NeoRhythm.exe
#  Place the stimuli\ folder NEXT TO NeoRhythm.exe, i.e.:
#      dist\NeoRhythm\stimuli\classical\
#      dist\NeoRhythm\stimuli\lullabies\
#      dist\NeoRhythm\stimuli\whitenoise\
# ============================================================
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

tmp_ret = collect_all('pygame')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('pyttsx3')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# pyttsx3 on Windows uses the built-in SAPI5 engine; the following
# hidden imports ensure the COM/win32 bridge is bundled correctly.
hiddenimports += [
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'win32com.client',
    'win32com.server',
]

a = Analysis(
    ['neorhythm2.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeoRhythm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=False hides the terminal window (GUI-only app)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    # icon='NeoRhythm.ico',  # uncomment and provide a .ico file to set an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeoRhythm',
)
# NOTE: no BUNDLE() block here – that is macOS-only.
