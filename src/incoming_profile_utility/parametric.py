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


def _half_width(ys, H, bottom, top, bow=None, bow_height=None, mid_width=None):
    """Half-width (distance from centerline) vs height.

    Priority:
      1. bow given  -> smooth bulge whose MAXIMUM CD == bow, located at bow_height
         (default H/2). Two parabolas meet with zero slope at the apex, so the peak
         is exactly at (bow_height, bow) and the walls curve smoothly into it.
      2. mid_width given -> parabola through bottom / mid / top (gentle curve, no peak).
      3. neither -> straight linear taper from bottom to top.
    """
    hb, ht = bottom / 2, top / 2

    if bow is not None:
        if bow < max(bottom, top) - 1e-9:
            raise ValueError(
                "bow is the max CD, so it must be >= bottom_width and top_width. "
                "For a pinched/waisted wall, use mid_width instead."
            )
        hv = bow / 2
        eps = H * 1e-3
        hbow = H / 2 if bow_height is None else float(bow_height)
        hbow = min(max(hbow, eps), H - eps)
        out = np.empty_like(ys, dtype=float)
        lo = ys <= hbow
        out[lo] = hv + (hb - hv) / hbow**2 * (ys[lo] - hbow) ** 2
        out[~lo] = hv + (ht - hv) / (H - hbow) ** 2 * (ys[~lo] - hbow) ** 2
        return np.clip(out, 0, None)

    if mid_width is not None:
        coef = np.polyfit([0.0, H / 2, H], [hb, mid_width / 2, ht], 2)
        return np.clip(np.polyval(coef, ys), 0, None)

    return hb + (ht - hb) * (ys / H)


def build_line(p: dict, nm_per_px: float):
    """Build (layers, dims) for a single symmetric line profile.

    layers: list of (polygon_in_pixels, bgr_color). dims: (height_px, width_px).
    Required: feature_height, bottom_width, top_width, and pitch (or space+linewidth).
    Optional:
      bow          -- the MAXIMUM CD (full width at the widest point of the wall)
      bow_height   -- height at which the bow (max CD) occurs; default H/2
      mid_width    -- CD at mid-height, for a gentle curve with no distinct peak
      mask_height, mask_width, feature_color, mask_color
    """
    H = p["feature_height"]
    bottom, top = p["bottom_width"], p["top_width"]
    pitch = _resolve_cell(p)
    mask_h = p.get("mask_height", 0.0)
    mask_w = p.get("mask_width", top)

    ys = np.linspace(0, H, 400)
    xs = _half_width(ys, H, bottom, top,
                     bow=p.get("bow"), bow_height=p.get("bow_height"),
                     mid_width=p.get("mid_width"))

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
