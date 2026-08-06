"""Offline license check — headless logic behind the license screen.

The vendor ships `license_usher`, a compiled extension that verifies a signed license
file against this machine. This module wraps it so the GUI never touches the extension
directly and keeps working (with a clear message) when it is missing.

Where the license file lives
    Next to the executable, called ``license.lic``. NOT under ``_MEIPASS``: that is the
    temporary directory PyInstaller unpacks into, so a license placed there would vanish
    on exit and could never be replaced without a rebuild.

    If the folder holding the .exe is read-only (Program Files, a network share), a
    manually chosen license cannot be copied there — we then remember its path in the
    per-user config directory instead, so the choice still survives a restart.
"""
from __future__ import annotations

import importlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

LICENSE_FILENAME = "license.lic"

# Running from a source checkout without the vendor extension installed is a developer
# machine, not a customer install: the source is right there, so gating it buys nothing.
# A frozen build ALWAYS requires the real check — a missing extension fails closed.
ALLOW_UNLICENSED_FROM_SOURCE = True

# The extension is a submodule of recipe_finder in the vendor's CLI, but ships as a
# top-level .so/.pyd next to this app. Accept either.
_MODULE_NAMES = ("recipe_finder.license_usher", "license_usher")

_usher = None
_usher_loaded = False


def usher():
    """The vendor extension, or None if it is not installed. Imported once, lazily."""
    global _usher, _usher_loaded
    if not _usher_loaded:
        _usher_loaded = True
        for name in _MODULE_NAMES:
            try:
                _usher = importlib.import_module(name)
                break
            except ImportError:
                continue
    return _usher


def app_dir() -> Path:
    """Folder the user sees the app in — where license.lic is expected."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]              # repo root (src/pkg -> ../..)


def default_license_path() -> Path:
    return app_dir() / LICENSE_FILENAME


def _pointer_file() -> Path:
    """Remembers a manually chosen license file when we cannot copy it next to the app."""
    from .materials import _user_dir
    return _user_dir() / "license_path.txt"


def remembered_path() -> Path | None:
    try:
        text = _pointer_file().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(text) if text else None


def remember_path(path: Path | None) -> None:
    try:
        if path is None:
            _pointer_file().unlink(missing_ok=True)
        else:
            _pointer_file().write_text(str(path), encoding="utf-8")
    except OSError:
        pass                                                # a lost pointer only costs a re-pick


@dataclass(frozen=True)
class LicenseStatus:
    """Outcome of one license check — everything the screen needs to render itself."""
    ok: bool
    path: Path | None = None
    holder: str = ""
    days_remaining: int | None = None
    linked_to_pc: bool | None = None
    code: str = ""
    detail: str = ""                                        # raw message from the extension
    dev_mode: bool = False                                  # source checkout, no extension

    @property
    def expires_soon(self) -> bool:
        return self.days_remaining is not None and self.days_remaining <= 30

    @property
    def expiry_text(self) -> str:
        if not self.ok:
            return ""
        d = self.days_remaining
        if d is None:
            return "No expiry date — perpetual license."
        if d <= 0:
            return "Expires today."
        return f"Expires in {d} day{'s' if d != 1 else ''}."

    @property
    def reason(self) -> str:
        """One human sentence for why the check failed."""
        if self.ok:
            return ""
        return _REASONS.get(self.code) or self.detail or "The license could not be verified."


_REASONS = {
    "not_found": "No license file was found.",
    "bad_format": "That file is not a valid license file.",
    "bad_signature": "The license file is damaged or has been modified.",
    "expired": "This license has expired.",
    "wrong_machine": "This license was issued for a different computer.",
    "component_missing": "The license component is missing from this installation.",
}


def check(path) -> LicenseStatus:
    """Verify one license file. Never raises."""
    mod = usher()
    if mod is None:
        return LicenseStatus(
            ok=ALLOW_UNLICENSED_FROM_SOURCE and not getattr(sys, "frozen", False),
            path=Path(path) if path else None,
            holder="Development build",
            code="component_missing",
            detail="license_usher is not installed",
            dev_mode=True,
        )
    if not path:
        return LicenseStatus(ok=False, code="not_found", detail="no license file selected")
    path = Path(path)
    try:
        lic = mod.check_license(str(path))
    except mod.LicenseError as error:
        return LicenseStatus(ok=False, path=path, code=getattr(error, "code", "") or "invalid",
                             detail=str(error))
    except Exception as error:                              # extension blew up: still no entry
        return LicenseStatus(ok=False, path=path, code="check_failed", detail=str(error))
    return LicenseStatus(
        ok=True,
        path=path,
        holder=getattr(lic, "holder", "") or "",
        days_remaining=getattr(lic, "days_remaining", None),
        linked_to_pc=getattr(lic, "linked_to_pc", None),
    )


def find_license() -> LicenseStatus:
    """Check the default location, then any remembered manual choice."""
    candidates, seen = [], set()
    for p in (default_license_path(), remembered_path()):
        if p and str(p) not in seen:
            seen.add(str(p))
            candidates.append(p)

    first_failure = None
    for p in candidates:
        status = check(p)
        if status.ok:
            return status
        if first_failure is None or (status.code != "not_found" and first_failure.code == "not_found"):
            first_failure = status                          # prefer a real reason over "not found"
    return first_failure or LicenseStatus(ok=False, code="not_found",
                                          path=default_license_path())


def install(source) -> tuple[Path, bool]:
    """Adopt a validated license file. Returns (path in use, copied next to the app).

    Copying makes the license the new default so the next start is silent. When the app
    folder is not writable we fall back to remembering where the file is.
    """
    source = Path(source).resolve()
    target = default_license_path()
    if source == target:
        remember_path(None)
        return target, True
    try:
        shutil.copyfile(source, target)
    except OSError:
        remember_path(source)
        return source, False
    remember_path(None)                                     # default location wins from now on
    return target, True


def machine_signature() -> str:
    """This machine's hardware signature — the string the vendor turns into a license."""
    mod = usher()
    if mod is None:
        return ""
    try:
        return mod.machine_id_hash_hex() or ""
    except Exception:
        return ""
