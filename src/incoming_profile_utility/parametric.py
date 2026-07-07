"""Parametric line-profile builder.

Curvature is described, not traced. The sidewall is a smooth parabola through
three control widths -- your vocabulary maps straight onto it:

    bottom_width / mid_width / top_width  -> control points (full CD at each height)
    bow                                   -> mid deviation from the top-bottom average
                                             (+bow = barrel/bulge, -bow = waist/pinch)
    pitch / space                         -> unit-cell width (linewidth = pitch - space)
    mask_height / mask_width              -> mask block on top (separate material)

A parabola through bottom/mid/top covers taper, bow, waist, and re-entrant walls.
(For S-shaped or scalloped walls we add control points or a periodic term later.)
All widths are centered -> symmetric by construction (docs/05).
"""
from __future__ import annotations

import math

import numpy as np

from . import renderer as rnd

FEATURE_BGR = (232, 162, 0)   # sky-blue (RGB 0,162,232)
MASK_BGR = (127, 127, 127)    # gray


def _resolve_cell(p: dict) -> float:
    """Return pitch, deriving it from space + linewidth if needed."""
    if "pitch" in p:
        return p["pitch"]
    if "space" in p and "linewidth" in p:
        return p["space"] + p["linewidth"]
    raise ValueError("Provide 'pitch', or both 'space' and 'linewidth'.")


def build_line(p: dict, nm_per_px: float):
    """Build (layers, dims) for a single symmetric line profile.

    layers: list of (polygon_in_pixels, bgr_color). dims: (height_px, width_px).
    Required: feature_height, bottom_width, top_width, and pitch (or space+linewidth).
    Optional: mid_width or bow, mask_height, mask_width, feature_color, mask_color.
    """
    H = p["feature_height"]
    bottom, top = p["bottom_width"], p["top_width"]
    bow = p.get("bow", 0.0)
    mid = p.get("mid_width", (top + bottom) / 2 + bow)
    pitch = _resolve_cell(p)
    mask_h = p.get("mask_height", 0.0)
    mask_w = p.get("mask_width", top)

    # parabola through (0, bottom/2), (H/2, mid/2), (H, top/2)
    hs = np.array([0.0, H / 2, H])
    hw = np.array([bottom / 2, mid / 2, top / 2])
    coef = np.polyfit(hs, hw, 2)
    ys = np.linspace(0, H, 300)
    xs = np.clip(np.polyval(coef, ys), 0, None)

    total_h = H + mask_h
    W_px = math.ceil(pitch / nm_per_px)
    H_px = math.ceil(total_h / nm_per_px)
    cx = pitch / 2

    def px(xp: float, yp: float):
        return [(cx + xp) / nm_per_px, (total_h - yp) / nm_per_px]

    right = [px(x, y) for x, y in zip(xs, ys)]
    left = [px(-x, y) for x, y in zip(xs, ys)][::-1]
    layers = [(right + left, p.get("feature_color", FEATURE_BGR))]

    if mask_h > 0:
        mw = mask_w / 2
        layers.append((
            [px(-mw, H), px(mw, H), px(mw, H + mask_h), px(-mw, H + mask_h)],
            p.get("mask_color", MASK_BGR),
        ))
    return layers, (H_px, W_px)


def render_line(p: dict, out_path, nm_per_px: float = 0.4):
    """Build and rasterize a parametric line profile to .bmp. Returns (w, h) px."""
    layers, (h, w) = build_line(p, nm_per_px)
    rnd.render_layers(layers, (h, w), out_path)
    return (w, h)
