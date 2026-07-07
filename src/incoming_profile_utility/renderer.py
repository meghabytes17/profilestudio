"""Rasterize geometry to a .bmp using Pillow (see docs/04).

Pipeline must be deterministic so e1s1.csv reproducibly yields e1s1_test.bmp.
"""
from __future__ import annotations

from pathlib import Path


def render_to_bmp(geometry, out_path: str | Path, scale: float, palette: dict | None = None):
    """Draw material polygons onto an RGB canvas and save as .bmp.

    TODO: allocate canvas from physical extent x scale, fill polygons by material
    color (palette), save via Image.save(out_path) — Pillow writes BMP natively.
    """
    raise NotImplementedError
