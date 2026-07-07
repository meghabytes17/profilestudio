"""Geometry primitives, coordinate transforms, symmetry, conformal offsets.

Recommended engine: shapely polygons in physical (nm) space; rasterize only at the end.
See docs/02 (coordinates) and docs/05 (symmetry).
"""
from __future__ import annotations


def mirror_x(polygon):
    """Reflect a polygon across the x = 0 axis. Basis of the symmetry guarantee."""
    raise NotImplementedError


def make_symmetric(right_half):
    """Return the union of right_half and its mirror image (docs/05)."""
    raise NotImplementedError


def conformal_offset(polygon, thickness: float):
    """Uniform outward offset == ideal conformal film deposition (shapely .buffer)."""
    raise NotImplementedError


def phys_to_pixel(x: float, y: float, scale: float, x_min: float, y_max: float):
    """Convert physical (nm, y-up) to pixel (y-down). See docs/02."""
    return round((x - x_min) * scale), round((y_max - y) * scale)
