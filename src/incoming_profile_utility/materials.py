"""Central material palette for rendered profiles.

A *material* is a named color. `vacuum` is a first-class material (open space).
The palette is the single source of truth that the renderer resolves colors from,
loaded from config/materials.json so materials can be added without code changes.

Colors are stored as RGB (human-friendly) and converted to BGR for OpenCV at draw
time. This palette is independent of the GUI's brand theme.
"""
from __future__ import annotations

import json
from pathlib import Path

# config/materials.json lives at the repo root (two levels up from this file's src dir)
_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "materials.json"

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

    def __init__(self, data: dict):
        self._mats = data["materials"]
        self.defaults = data.get("defaults", {})

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

    # --- editing / persistence (used by the GUI's "add material") ---
    def add(self, name: str, rgb, label: str | None = None) -> None:
        self._mats[name] = {"rgb": list(rgb), "label": label or name}

    def to_dict(self) -> dict:
        return {"defaults": self.defaults, "materials": self._mats}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))


def load_palette(path: str | Path | None = None) -> Palette:
    """Load the palette from config/materials.json, falling back to a baked-in set."""
    p = Path(path) if path else _DEFAULT_CONFIG
    try:
        data = json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = _FALLBACK
    return Palette(data)
