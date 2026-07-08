"""Shared sidewall curvature: half-width vs height (used by parametric + process)."""
from __future__ import annotations

import numpy as np


def half_width_curve(ys, H, bottom, top, bow=None, bow_height=None, mid_width=None):
    """Half-width (distance from centerline) vs height.

    bow given      -> smooth bulge whose MAX CD == bow at bow_height (default H/2),
                      built from two parabolas meeting with zero slope at the apex.
    mid_width given -> parabola through bottom / mid / top (gentle/waisted wall).
    neither        -> straight linear taper.
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
