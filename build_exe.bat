@echo off
REM Build a standalone Windows .exe for the Incoming Profile Utility.
REM Run from the repo root in a Windows command prompt.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
REM Reproducible build: install the PINNED set, not floating >= versions.
REM Airgapped? see requirements-lock.txt for the vendored-wheelhouse procedure.
pip install -r requirements-lock.txt
if errorlevel 1 (
  echo.
  echo *** Dependency install failed. If it's PyInstaller not matching your Python version,
  echo *** regenerate the lock on THIS machine:  tools\make_lock.bat
  exit /b 1
)
pip install -e .
REM regenerate the version resource + icon from the single version source
python tools\make_version_info.py
python tools\make_icon.py
pyinstaller --clean --noconfirm incoming_profile_utility.spec
echo.
echo ============================================================
echo Built: dist\ProfileStudio.exe
python -c "import sys; sys.path.insert(0,'src'); import incoming_profile_utility as i; print('   '+i.version_string())"
echo Send that single file to your testers.
echo ============================================================
