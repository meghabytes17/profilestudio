"""High-level profile builders.

Implemented:
    render_trace_csv  -- CSV(width,height) -> symmetric filled profile -> .bmp

Planned parametric builders (docs/03), grounded in the example_profiles/ set:
    - sidewall variants: vertical / tapered (positive) / re-entrant (negative)
    - scalloping (Bosch DRIE periodic sidewall texture)
    - bottom effects: footing, notching, microtrench, rounding
    - bowing (mid-height bulge)
    - conformal film on a feature (polygon offset -- shapely recommended here)
These will emit the same (left,right)-polygon structure so the renderer is shared.
"""
from __future__ import annotations

from pathlib import Path

from . import geometry as geo
from . import renderer as rnd
from .io_csv import load_trace


def render_trace_csv(csv_path: str | Path, out_path: str | Path,
                     nm_per_px: float | None = None) -> tuple[float, tuple[int, int]]:
    """Full pipeline: load trace, scale, build symmetric polygons, render to .bmp.

    Returns (nm_per_px_used, (width_px, height_px)).
    """
    data = load_trace(csv_path)
    if nm_per_px is None:
        nm_per_px = geo.auto_nm_per_pixel(data)
    h, w = geo.image_dims(data, nm_per_px)
    polys = geo.trace_to_polygons(data, h, w, nm_per_px)
    rnd.render_polygons(polys, (h, w), out_path)
    return nm_per_px, (w, h)


# --- parametric builders (TODO) ---
def sidewall_profile(*args, **kwargs):
    raise NotImplementedError("Parametric sidewall builder — see docs/03.")
