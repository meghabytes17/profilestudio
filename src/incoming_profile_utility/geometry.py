"""Geometry: coordinate/scale helpers and trace -> symmetric polygon conversion.

All feature widths are centered within the max width, which makes the profile
inherently symmetric about the vertical center line (docs/05). Physical units are
nm; the raster is y-down (docs/02).

NOTE: the trace->polygon math is kept numerically identical to the original
profile_sketcher.py so rendering reproduces the reference BMP byte-for-byte.
The golden test (tests/test_golden.py) guards this.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def auto_nm_per_pixel(data: pd.DataFrame) -> float:
    """Heuristic scale targeting ~100k px area: sqrt(maxW * heightSpan / 1e5)."""
    return round(np.sqrt(max(data["width"]) * np.ptp(data["height"]) / 100_000), 2)


def image_dims(data: pd.DataFrame, nm_per_px: float) -> tuple[int, int]:
    """Return (height_px, width_px) for the raster canvas."""
    w = math.ceil(max(data["width"]) * (1 / nm_per_px))
    h = math.ceil(np.ptp(data["height"]) * (1 / nm_per_px))
    return (h, w)


def trace_to_polygons(data: pd.DataFrame, cal_h: int, cal_w: int, nm_per_px: float):
    """Convert a width/height trace into left + right filled polygons (pixel coords).

    Each width is centered within max_width -> exact left/right symmetry.
    """
    max_h, max_w = max(data["height"]), max(data["width"])
    n = data.sort_values("height")
    top_j = n["width"].lt(max_w).idxmin()
    height_coord = (max_h - n["height"][np.clip(top_j + 1, 0, len(n.index) - 1)]) * (1 / nm_per_px)

    xs, ys = n["width"][::-1], n["height"][::-1]
    left = [[0, height_coord]]
    right = [[cal_w, height_coord]]
    prev = None
    for i, j in zip(xs, ys):
        if prev is None:
            prev = i
        x1 = ((max_w - i) / 2) * (1 / nm_per_px)
        x2 = (max_w - (max_w - i) / 2) * (1 / nm_per_px)
        y = (max_h - j) * (1 / nm_per_px)
        if prev == i == max_w:
            prev = i
            continue
        # 4x duplication preserved from the original (kept for byte-exact parity).
        for _ in range(4):
            left.append([x1, y])
            right.append([x2, y])
        prev = i
    left.append([0, cal_h])
    right.append([cal_w, cal_h])
    return [left, right]
