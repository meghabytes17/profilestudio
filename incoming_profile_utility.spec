# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Incoming Profile Utility GUI.

Build:  pyinstaller incoming_profile_utility.spec
Output: dist/ProfileStudio.exe  (Windows)  /  dist/ProfileStudio (Linux/macOS)

Produces a single-file, windowed (no console) executable. customtkinter ships JSON
themes + assets that must be collected, and config/materials.json is bundled so the
base palette is available at runtime.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("config/materials.json", "config"), ("assets/icon.png", "assets"), ("assets/icon.ico", "assets"), ("assets/sandbox-logo.png", "assets")]
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

# Generate the Windows version resource from the single version source at build time, and
# guarantee it is pure ASCII. PyInstaller parses this file as Python source and rejects any
# non-ASCII byte (e.g. an em-dash) with 'invalid or missing encoding declaration'. Doing it
# here means the .exe metadata is correct even if build_exe.bat wasn't run or an older
# generated file is lying around.
import subprocess, sys as _sys
from pathlib import Path as _Path
_vi = _Path("build/version_info.txt")
try:
    subprocess.run([_sys.executable, "tools/make_version_info.py"], check=False)
except Exception:
    pass
if _vi.exists():
    _clean = _vi.read_text(encoding="utf-8", errors="replace").encode("ascii", "replace").decode("ascii")
    _vi.write_text(_clean, encoding="ascii")
    _version_file = str(_vi)
else:
    _version_file = None                      # no resource rather than a broken build

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="ProfileStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # GUI app: no console window
    disable_windowed_traceback=False,
    icon="assets/icon.ico",      # SandBox-branded Profile Studio icon
    version=_version_file,        # .exe Properties -> Details; regenerated + ASCII-sanitised above
)
