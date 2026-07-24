@echo off
REM ---------------------------------------------------------------------------
REM Regenerate requirements-lock.txt with exact versions AND sha256 hashes.
REM
REM Run this ON WINDOWS, with the same Python you build the .exe with.
REM A lock generated on another OS is WRONG: pip-compile resolves for the current
REM platform, so a Linux-generated lock silently omits PyInstaller's Windows-only
REM dependencies (pefile, pywin32-ctypes) and the build then fails.
REM
REM Re-run this whenever you change dependencies in pyproject.toml.
REM ---------------------------------------------------------------------------
setlocal

echo [1/3] Installing pip-tools...
python -m pip install --upgrade pip pip-tools || goto :err

echo [2/3] Resolving and hashing dependencies (this can take a few minutes)...
REM --allow-unsafe pins setuptools too; without it pip REJECTS the file in hash mode.
REM --extra build brings in PyInstaller so the lock covers the whole build.
pip-compile --generate-hashes --allow-unsafe --extra build --extra geometry ^
            --output-file requirements-lock.txt pyproject.toml || goto :err

echo [3/3] Verifying the lock installs under hash checking...
python -m pip install --require-hashes --dry-run -r requirements-lock.txt || goto :err

echo.
echo ============================================================
echo requirements-lock.txt regenerated and verified.
echo Commit it, then build with build_exe.bat.
echo ============================================================
exit /b 0

:err
echo.
echo *** FAILED - lock not updated. See the error above.
exit /b 1
