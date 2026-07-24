# Cutting a release

The version lives in **one place**: `src/incoming_profile_utility/__init__.py`
(`__version__` and `__build_date__`). Everything else reads from it — the title bar, the
header pill, the About tooltip, the .exe file properties, and `pyproject.toml` (checked by a
test).

To release:

1. Bump `__version__` (semver: MAJOR.MINOR.PATCH) and set `__build_date__` to today.
2. Set the same number in `pyproject.toml` -> `[project] version`.
3. Add a dated section to `CHANGES.md`.
4. `pytest` — `test_version_sources_agree` fails if the two version numbers drift.
5. `build_exe.bat` — it regenerates the .exe version resource and icon from `__version__`
   automatically, so `dist\ProfileStudio.exe` -> Properties -> Details shows it.

Testers can always read the running version from the **header pill** (top-right) or the
**title bar**, and the built file's version from right-click -> Properties -> Details. No more
hand-labelling screenshots with a date.

---

# Hash-pinning dependencies (supply-chain hardening)

Do this **on Windows**, with the same Python you build the `.exe` with, before customer
delivery — and again whenever you change dependencies in `pyproject.toml`.

```bat
cd C:\Users\Dagger\source\repos\ipu
tools\make_lock.bat
```

That script does three things: installs `pip-tools`, regenerates `requirements-lock.txt` with
exact versions **and sha256 hashes** for every package (including transitive ones), then
verifies the file installs under hash checking. If any step fails it stops and leaves the
existing lock alone.

Then commit the lock and build as usual:

```bat
git add requirements-lock.txt
git commit -m "Rebuild hash-pinned dependency lock"
build_exe.bat
```

Once the lock contains hashes, **pip enforces them automatically** — any wheel whose hash
doesn't match is refused, so a tampered or substituted package can't get into the `.exe`.

## Two traps worth knowing

1. **Generate it on Windows.** `pip-compile` resolves for the machine it runs on. A lock made
   on Linux/macOS silently omits PyInstaller's Windows-only dependencies (`pefile`,
   `pywin32-ctypes`), and the build then fails with a confusing missing-module error.
2. **`--allow-unsafe` is required** (the script passes it). Without it `setuptools` is left
   unpinned, and pip *rejects the whole file* in hash-checking mode. The flag name is
   historical; pinning setuptools is the safe choice.

## If your build machine has no internet

Vendor the wheels on a connected machine of the **same OS and Python version**:

```bat
pip download -r requirements-lock.txt -d wheelhouse --require-hashes
```

Copy `wheelhouse\` to the build machine, then:

```bat
pip install --no-index --find-links=wheelhouse -r requirements-lock.txt
```
