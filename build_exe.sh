#!/usr/bin/env bash
# Build a standalone executable (Linux/macOS — for a Windows .exe, run build_exe.bat on Windows).
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[geometry]" pyinstaller
pyinstaller --clean --noconfirm incoming_profile_utility.spec
echo "Built: dist/IncomingProfileUtility"
