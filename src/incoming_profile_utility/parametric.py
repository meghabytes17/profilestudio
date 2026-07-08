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


from ._curves import half_width_curve as _half_width
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


# ---------------------------------------------------------------------------
# Material/vacuum composition
# ---------------------------------------------------------------------------
def build_profile(p: dict, palette, nm_per_px: float):
    """Compose a profile as material/vacuum regions and return (layers, dims).

    Regions:
      surround_material -- fills the whole unit cell (default: a material)
      feature_material  -- the CD-curve region (default: 'vacuum' -> inverted case,
                           i.e. a trench/hole carved into the surround material)
      mask_material     -- optional block/opening at the top

    Because either region can be a material OR 'vacuum', a CD (including bow = max
    CD at a height) can be defined on solid material or on open space. The default
    is the inverted case: a vacuum feature inside surrounding material.

    Curve params (bottom_width, top_width, bow, bow_height, mid_width, feature_height,
    pitch/space) are as in build_line. Layers are returned in paint order.
    """
    H = p["feature_height"]
    bottom, top = p["bottom_width"], p["top_width"]
    pitch = _resolve_cell(p)
    mask_h = p.get("mask_height", 0.0)
    total_h = H + mask_h

    d = palette.defaults
    surround = p.get("surround_material", d.get("surround_material", "silicon"))
    feature = p.get("feature_material", d.get("feature_material", "vacuum"))
    mask_mat = p.get("mask_material", d.get("mask_material", "hardmask"))
    feature_is_void = (feature == "vacuum")

    ys = np.linspace(0, H, 400)
    xs = _half_width(ys, H, bottom, top,
                     bow=p.get("bow"), bow_height=p.get("bow_height"),
                     mid_width=p.get("mid_width"))

    W_px = math.ceil(pitch / nm_per_px)
    H_px = math.ceil(total_h / nm_per_px)
    cx = pitch / 2

    def px(xp, yp):
        return [(cx + xp) / nm_per_px, (total_h - yp) / nm_per_px]

    layers = []
    # 1) surround fills the whole cell
    layers.append(([px(-pitch / 2, 0), px(pitch / 2, 0),
                    px(pitch / 2, total_h), px(-pitch / 2, total_h)],
                   palette.bgr(surround)))

    if feature_is_void:
        # inverted: mask is a full-width band the trench cuts through
        if mask_h > 0:
            layers.append(([px(-pitch / 2, H), px(pitch / 2, H),
                            px(pitch / 2, total_h), px(-pitch / 2, total_h)],
                           palette.bgr(mask_mat)))
        # trench (vacuum), extended up through the mask so the opening is clear
        right = [px(x, y) for x, y in zip(xs, ys)]
        left = [px(-x, y) for x, y in zip(xs, ys)][::-1]
        if mask_h > 0:
            right = right + [px(top / 2, total_h)]
            left = [px(-top / 2, total_h)] + left
        layers.append((right + left, palette.bgr(feature)))
    else:
        # solid feature sitting in the surround; mask block on top of it
        right = [px(x, y) for x, y in zip(xs, ys)]
        left = [px(-x, y) for x, y in zip(xs, ys)][::-1]
        layers.append((right + left, palette.bgr(feature)))
        if mask_h > 0:
            mw = p.get("mask_width", top) / 2
            layers.append(([px(-mw, H), px(mw, H),
                            px(mw, total_h), px(-mw, total_h)],
                           palette.bgr(mask_mat)))

    return layers, (H_px, W_px)


def render_profile(p: dict, out_path, palette=None, nm_per_px: float = 0.4):
    """Build + rasterize a material/vacuum profile to .bmp. Returns (w, h) px."""
    from .materials import load_palette
    if palette is None:
        palette = load_palette()
    layers, (h, w) = build_profile(p, palette, nm_per_px)
    rnd.render_layers(layers, (h, w), out_path)
    return (w, h)
