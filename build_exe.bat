@echo off
REM Build a standalone Windows .exe for the Incoming Profile Utility.
REM Run from the repo root in a Windows command prompt.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[geometry]" pyinstaller
REM regenerate the version resource + icon from the single version source
python tools\make_version_info.py
python tools\make_icon.py
pyinstaller --clean --noconfirm incoming_profile_utility.spec
echo.
echo ============================================================
echo Built: dist\IncomingProfileUtility.exe
python -c "import sys; sys.path.insert(0,'src'); import incoming_profile_utility as i; print('   '+i.version_string())"
echo Send that single file to your testers.
echo ============================================================
