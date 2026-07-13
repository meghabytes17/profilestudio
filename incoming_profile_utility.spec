# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Incoming Profile Utility GUI.

Build:  pyinstaller incoming_profile_utility.spec
Output: dist/IncomingProfileUtility.exe  (Windows)  /  dist/IncomingProfileUtility (Linux/macOS)

Produces a single-file, windowed (no console) executable. customtkinter ships JSON
themes + assets that must be collected, and config/materials.json is bundled so the
base palette is available at runtime.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("config/materials.json", "config"), ("assets/icon.png", "assets"), ("assets/icon.ico", "assets")]
datas += collect_data_files("customtkinter")          # themes / assets

hiddenimports = collect_submodules("customtkinter") + [
    "PIL._tkinter_finder", "shapely", "cv2", "pandas", "numpy",
]

a = Analysis(
    ["run_gui.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="IncomingProfileUtility",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # GUI app: no console window
    disable_windowed_traceback=False,
    icon="assets/icon.ico",      # SandBox-branded Profile Studio icon
)
