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

## Licensing

The app shows a license screen before the main window. Two things must be in place:

1. **`license_usher` (the vendor's compiled checker)** must sit in the repo root when you
   build — `license_usher.abi3.so`, or the `.pyd` on Windows. The spec bundles whatever it
   finds and prints a warning if it finds nothing; a build without it starts and reports
   *"The license component is missing from this installation."*
2. **`license.lic`** goes next to the delivered `ProfileStudio.exe` — **not** inside it. A
   bundled license could never be replaced without a rebuild, and the single-file exe
   unpacks to a temp folder that is wiped on exit.

> **CI builds need a decision.** `.gitignore` currently keeps `license_usher*.so/.pyd` out of
> the repo, so the GitHub Action (which only has the checkout) would build an .exe that
> refuses to start. Either commit the **Windows `.pyd`** — the `.so` in the repo root is
> macOS-only and useless to the Windows build — or add a workflow step that fetches it from
> wherever you keep the vendor library. Until then, build releases with `build_exe.bat` on a
> machine that has the `.pyd`.

On start the app checks `license.lic` beside the exe. If it is missing or rejected, the
screen shows the reason plus this machine's hardware signature (Copy / Save…), which the
tester sends to you; the license file you send back can be installed straight from the same
screen with **Select license file…**. That copies it next to the exe so later starts are
silent. If the exe lives somewhere unwritable (Program Files, a share), the app remembers
where the chosen file is in `%LOCALAPPDATA%\ProfileStudio\license_path.txt` instead.

A valid license shows who it is licensed to and the days remaining, with **Renew license…**
to swap in a new file before the old one runs out. Licenses are machine-bound: one file per
tester's PC.

Running from a source checkout **without** `license_usher` installed skips the check (there
is nothing to protect — they have the source); the console says so. A frozen build never
skips it.

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
