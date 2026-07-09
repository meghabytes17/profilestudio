@echo off
REM Build a standalone Windows .exe for the Incoming Profile Utility.
REM Run from the repo root in a Windows command prompt.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[geometry]" pyinstaller
pyinstaller --clean --noconfirm incoming_profile_utility.spec
echo.
echo ============================================================
echo Built: dist\IncomingProfileUtility.exe
echo Send that single file to your testers.
echo ============================================================
