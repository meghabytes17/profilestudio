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
   automatically, so `dist\IncomingProfileUtility.exe` -> Properties -> Details shows it.

Testers can always read the running version from the **header pill** (top-right) or the
**title bar**, and the built file's version from right-click -> Properties -> Details. No more
hand-labelling screenshots with a date.
