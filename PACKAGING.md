# Packaging for testers

Two ways to get a standalone **`ProfileStudio.exe`** that testers can run without
installing Python.

## Option A — build the .exe on Windows (one command)

On a Windows machine with Python 3.10+ installed, from the repo root:

```bat
build_exe.bat
```

That creates a virtualenv, installs the app + PyInstaller, and produces a single file:

```
dist\ProfileStudio.exe
```

Send that one file to your testers. (On Linux/macOS, `./build_exe.sh` produces the
equivalent native binary — PyInstaller does **not** cross-compile, so a Windows `.exe`
must be built on Windows.)

## Option B — let CI build it (no local setup)

`.github/workflows/build-exe.yml` builds the Windows `.exe` on a GitHub-hosted Windows
runner. Two triggers:

- **Manual:** on GitHub, open **Actions → build-exe → Run workflow**. When it finishes,
  download the `ProfileStudio-windows` artifact from that run — it contains the
  `.exe`.
- **Release:** `git tag v0.1.0 && git push --tags` builds the `.exe` and attaches it to a
  GitHub Release for that tag, so testers can download it from the Releases page.

This is the easiest way to hand out a build without setting anything up locally.

## Notes for testers

- **First launch is slow.** The single-file build unpacks to a temp folder on start
  (a few seconds); subsequent launches are quicker.
- **SmartScreen / “unknown publisher.”** The exe is unsigned, so Windows may warn on
  first run — click *More info → Run anyway*. Code-signing removes this but needs a
  certificate.
- **User-added materials** (from “+ New material”) are saved to
  `%LOCALAPPDATA%\ProfileStudio\user_materials.json` (migrated automatically from the old `IncomingProfileUtility` folder), so they persist across
  runs and never touch the bundled base palette.
- The exe is large (~150–200 MB) because it bundles NumPy, pandas, OpenCV, and Shapely.

## Customizing

- **Icon:** the SandBox-branded icon (`assets/icon.ico`) is already wired into
  `incoming_profile_utility.spec`.
- **Onedir instead of onefile** (faster startup, but a folder to zip): change the `EXE`
  section per PyInstaller's onedir template, or ask and I'll switch the spec.

## The .exe still shows the old icon

The icon is baked into the .exe **at build time**, so an .exe built before the icon was added
keeps the old one. After pulling, rebuild:

```bat
build_exe.bat
```

If a freshly built .exe *still* shows the old icon in File Explorer, that's the Windows icon
cache, not the build. Confirm the .exe itself is right by checking its Properties, or force a
refresh:

```bat
ie4uinit.exe -show
```

If it persists, clear the cache and restart Explorer:

```bat
taskkill /f /im explorer.exe
del /a /q "%LOCALAPPDATA%\IconCache.db"
del /a /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*"
start explorer.exe
```

Renaming the .exe (or moving it to a different folder) also sidesteps the cached entry.
