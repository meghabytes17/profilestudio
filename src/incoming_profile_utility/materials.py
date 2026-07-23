"""Central material palette for rendered profiles.

A *material* is a named color. `vacuum` is a first-class material (open space).
The palette is the single source of truth that the renderer resolves colors from,
loaded from config/materials.json so materials can be added without code changes.

Colors are stored as RGB (human-friendly) and converted to BGR for OpenCV at draw
time. This palette is independent of the GUI's brand theme.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Directory that holds bundled read-only data (config/…)."""
    if getattr(sys, "frozen", False):                       # PyInstaller build
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]              # repo root (src/pkg -> ../..)


def _user_dir() -> Path:
    """Writable directory for user-added materials."""
    if getattr(sys, "frozen", False):
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        d = Path(root) / "IncomingProfileUtility"
    else:
        d = Path(__file__).resolve().parents[2] / "config"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path.home()
    return d


# config/materials.json = the tracked BASE palette (the app never writes to it).
_DEFAULT_CONFIG = _base_dir() / "config" / "materials.json"
# user-added materials persist here, OUT of version control / next to the app when frozen.
_USER_CONFIG = _user_dir() / "user_materials.json"

# Baked-in fallback so the package works even without the config file.
_FALLBACK = {
    "defaults": {"surround_material": "silicon", "feature_material": "vacuum",
                 "mask_material": "hardmask"},
    "materials": {
        "vacuum": {"rgb": [0, 0, 0], "label": "Vacuum / open space"},
        "silicon": {"rgb": [0, 162, 232], "label": "Silicon"},
        "hardmask": {"rgb": [127, 127, 127], "label": "Hard mask"},
    },
}


class Palette:
    """A loaded material palette: name -> color, plus default region assignments."""

    def __init__(self, data: dict, base_keys=None, base_mats=None):
        self._mats = data["materials"]
        self.defaults = data.get("defaults", {})
        self._base_keys = set(base_keys) if base_keys is not None else set(self._mats.keys())
        # pristine shipped values, so we can tell a recoloured base material from an untouched
        # one (and offer 'reset to default')
        import copy
        self._base_mats = copy.deepcopy(base_mats if base_mats is not None
                                        else {k: v for k, v in self._mats.items() if k in self._base_keys})

    # --- lookups ---
    def names(self) -> list[str]:
        return list(self._mats.keys())

    def label(self, name: str) -> str:
        return self._mats[name].get("label", name)

    def rgb(self, name: str) -> tuple[int, int, int]:
        if name not in self._mats:
            raise KeyError(f"Unknown material '{name}'. Known: {', '.join(self.names())}")
        return tuple(self._mats[name]["rgb"])

    def bgr(self, name: str) -> tuple[int, int, int]:
        r, g, b = self.rgb(name)
        return (b, g, r)  # OpenCV convention

    def hex(self, name: str) -> str:
        r, g, b = self.rgb(name)
        return f"#{r:02X}{g:02X}{b:02X}"

    # --- editing / persistence (used by the GUI's "add material" / "change colour") ---
    def add(self, name: str, rgb, label: str | None = None) -> None:
        self._mats[name] = {"rgb": list(rgb), "label": label or name}

    def set_rgb(self, name: str, rgb) -> None:
        """Recolour an existing material, keeping its label."""
        if name in self._mats:
            self._mats[name]["rgb"] = list(rgb)

    def is_base(self, name: str) -> bool:
        return name in self._base_keys

    def is_modified(self, name: str) -> bool:
        """True if a BASE material has been recoloured away from the shipped palette."""
        base = self._base_mats.get(name)
        return bool(base) and list(base.get("rgb", [])) != list(self._mats.get(name, {}).get("rgb", []))

    def reset_to_base(self, name: str) -> bool:
        """Restore a base material's shipped colour. Returns True if anything changed."""
        base = self._base_mats.get(name)
        if not base or not self.is_modified(name):
            return False
        self._mats[name]["rgb"] = list(base["rgb"])
        return True

    def to_dict(self) -> dict:
        return {"defaults": self.defaults, "materials": self._mats}

    def user_materials(self) -> dict:
        """What must be persisted: materials the user added, PLUS base materials they have
        recoloured (otherwise a recoloured base material would be lost on restart)."""
        return {k: v for k, v in self._mats.items()
                if k not in self._base_keys or self.is_modified(k)}

    def save(self, path: str | Path | None = None) -> None:
        """Persist user-added materials and user recolours, to the untracked user config,
        so the tracked base palette (config/materials.json) is never modified."""
        p = Path(path) if path else _USER_CONFIG
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"materials": self.user_materials()}, indent=2))


def load_palette(path: str | Path | None = None) -> Palette:
    """Load the tracked base palette, then merge any user-added materials (untracked)."""
    p = Path(path) if path else _DEFAULT_CONFIG
    try:
        data = json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = _FALLBACK
    base_keys = set(data["materials"].keys())
    import copy
    base_mats = copy.deepcopy(data["materials"])       # pristine shipped colours
    try:                    # merge user additions AND user recolours (these override the base)
        user = json.loads(_USER_CONFIG.read_text())
        for k, v in user.get("materials", {}).items():
            data["materials"][k] = v
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return Palette(data, base_keys=base_keys, base_mats=base_mats)
