"""Process-op engine: build a profile as an ordered list of operations on 2D regions.

The internal model is a set of labeled 2D polygons (shapely) plus the derived open
(vacuum) region. Each op transforms that state via offset/boolean operations, so
conformal shells, voids/keyholes, overhangs, fills, and etches all fall out of the
geometry rather than being special cases. This is the generalizable model chosen
over width-at-heights (which assumes every boundary is single-valued in height).

Pipeline:  base state  ->  op1 -> op2 -> ...  ->  render_regions()

Coordinates are physical nm, x centered at 0 (symmetry axis), y-up. Rasterization
flips to y-down for the BMP.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import cv2
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from ._curves import half_width_curve  # shared with parametric (see below)


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
@dataclass
class State:
    cell: Polygon
    regions: list = field(default_factory=list)   # ordered (material, geometry), painted bottom->top

    def solid(self):
        geoms = [g for _, g in self.regions if not g.is_empty]
        return unary_union(geoms) if geoms else Polygon()

    def open(self):
        return self.cell.difference(self.solid())

    def add(self, material, geom):
        geom = geom.intersection(self.cell)
        if not geom.is_empty:
            self.regions.append((material, geom))

    def ensure_top(self, y):
        minx, miny, maxx, maxy = self.cell.bounds
        if y > maxy:
            self.cell = box(minx, miny, maxx, y)

    def copy(self):
        return State(self.cell, list(self.regions))


# --------------------------------------------------------------------------- #
# Mask shapes (square / facet / round; facet by angle from horizontal; symmetric)
# --------------------------------------------------------------------------- #
def mask_polygon(width, height, base_y, corner="square", facet_angle=45.0, radius=0.0):
    """Symmetric mask cross-section. corner in {square, facet, round}.

    facet_angle: degrees from horizontal (fab convention); 90 == square.
    radius: corner radius for 'round'.
    Only the two TOP corners are shaped; they are always symmetric.
    """
    x = width / 2.0
    top = base_y + height
    if corner == "facet" and facet_angle < 89.999:
        # tapered sidewalls at facet_angle from horizontal (90 == square).
        inset = height / math.tan(math.radians(facet_angle))
        top_w = width - 2 * inset
        if top_w <= 0:                                # walls meet -> triangular top
            apex_y = min(top, base_y + x * math.tan(math.radians(facet_angle)))
            return Polygon([(-x, base_y), (x, base_y), (0, apex_y)])
        tx = top_w / 2
        return Polygon([(-x, base_y), (x, base_y), (tx, top), (-tx, top)])
    if corner == "round" and radius > 0:
        r = min(radius, x, height)
        pts = [(-x, base_y), (x, base_y), (x, top - r)]
        for a in np.linspace(0, math.pi / 2, 14):    # top-right arc
            pts.append((x - r + r * math.cos(a), top - r + r * math.sin(a)))
        for a in np.linspace(math.pi / 2, math.pi, 14):  # top-left arc
            pts.append((-x + r + r * math.cos(a), top - r + r * math.sin(a)))
        return Polygon(pts)
    return box(-x, base_y, x, top)                    # square


# --------------------------------------------------------------------------- #
# Base state (inverted default: vacuum feature carved into surround material)
# --------------------------------------------------------------------------- #
def build_base(p: dict) -> State:
    H = p["feature_height"]
    bottom, top = p["bottom_width"], p["top_width"]
    pitch = p.get("pitch") or (p["space"] + p.get("linewidth", top))
    mask_h = p.get("mask_height", 0.0)
    total_h = H + mask_h
    cell = box(-pitch / 2, 0, pitch / 2, total_h)

    ys = np.linspace(0, H, 240)
    xs = half_width_curve(ys, H, bottom, top, p.get("bow"), p.get("bow_height"),
                          p.get("mid_width"))
    right = [(x, y) for x, y in zip(xs, ys)]
    left = [(-x, y) for x, y in zip(xs, ys)][::-1]
    feature = Polygon(right + left)                  # the trench (vacuum) within 0..H

    st = State(cell, [])
    surround = p.get("surround_material", "silicon")
    st.add(surround, box(-pitch / 2, 0, pitch / 2, H).difference(feature))

    if mask_h > 0:
        mp = mask_polygon(p.get("mask_width", pitch), mask_h, H,
                          corner=p.get("mask_corner", "square"),
                          facet_angle=p.get("mask_facet_angle", 45.0),
                          radius=p.get("mask_radius", 0.0))
        opening = box(-top / 2, H, top / 2, total_h)  # trench opening continues through mask
        st.add(p.get("mask_material", "hardmask"), mp.difference(opening))
    return st


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
def _extrude_down(geom, depth):
    steps = max(4, int(depth) + 1)
    return unary_union([affinity.translate(geom, yoff=-k)
                        for k in np.linspace(0, depth, steps)])


def conformal_deposit(state: State, material: str, thickness: float) -> State:
    """Uniform film of `thickness` grown on all exposed surfaces into the open region."""
    s = state.solid()
    film = s.buffer(thickness, join_style=2).difference(s).intersection(state.cell)
    st = state.copy(); st.add(material, film); return st


def planar_deposit(state: State, material: str, thickness: float) -> State:
    """Add a flat slab of `thickness` on top of the current highest solid surface."""
    top_y = state.solid().bounds[3] if not state.solid().is_empty else 0.0
    minx, _, maxx, _ = state.cell.bounds
    st = state.copy()
    st.ensure_top(top_y + thickness)                 # give the slab headroom
    st.add(material, box(minx, top_y, maxx, top_y + thickness)); return st


def fill(state: State, material: str, up_to: float | None = None) -> State:
    """Fill the open region (trenches, voids) up to a height (default: feature top)."""
    minx, miny, maxx, maxy = state.cell.bounds
    level = up_to if up_to is not None else maxy
    region = state.open().intersection(box(minx, miny, maxx, level))
    st = state.copy(); st.add(material, region); return st


def etch(state: State, depth: float, mode: str = "isotropic") -> State:
    """Remove material from exposed surfaces. mode: 'isotropic' or 'anisotropic' (vertical)."""
    if mode == "anisotropic":
        removal = _extrude_down(state.open(), depth).intersection(state.solid())
    else:
        removal = state.open().buffer(depth, join_style=2).intersection(state.solid())
    new = [(m, g.difference(removal)) for m, g in state.regions]
    st = State(state.cell, [(m, g) for m, g in new if not g.is_empty]); return st


def planarize(state: State, at_height: float) -> State:
    """Cut everything above `at_height` (CMP)."""
    minx, miny, maxx, _ = state.cell.bounds
    keep = box(minx, miny, maxx, at_height)
    new = [(m, g.intersection(keep)) for m, g in state.regions]
    st = State(state.cell, [(m, g) for m, g in new if not g.is_empty]); return st


OPS = {
    "conformal_deposit": conformal_deposit,
    "planar_deposit": planar_deposit,
    "fill": fill,
    "etch": etch,
    "planarize": planarize,
}


def evaluate(base: State, ops: list[dict]) -> State:
    """Run an ordered op-list. Each op: {'op': name, ...params}."""
    state = base
    for op in ops:
        fn = OPS[op["op"]]
        kwargs = {k: v for k, v in op.items() if k != "op"}
        state = fn(state, **kwargs)
    return state


# --------------------------------------------------------------------------- #
# Rasterization (handles polygons with holes; paints in z-order)
# --------------------------------------------------------------------------- #
def _polys(geom):
    """Yield polygonal parts from any geometry (Polygon/MultiPolygon/GeometryCollection)."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out += _polys(g)
        return out
    return []  # lines / points are not paintable


def _px(ring, cx, total_h, nm_per_px):
    xs, ys = ring.coords.xy
    return np.array([[[(cx + x) / nm_per_px, (total_h - y) / nm_per_px]
                      for x, y in zip(xs, ys)]], dtype=np.int32)


def render_regions(state: State, palette, out_path, nm_per_px: float = 0.4):
    minx, miny, maxx, maxy = state.cell.bounds
    pitch = maxx - minx
    total_h = maxy - miny
    W = int(math.ceil(pitch / nm_per_px)); H = int(math.ceil(total_h / nm_per_px))
    cx = pitch / 2
    img = np.zeros((H, W, 3))
    for material, geom in state.regions:
        color = palette.bgr(material)
        m = np.zeros((H, W), np.uint8)
        for poly in _polys(geom):
            cv2.fillPoly(m, _px(poly.exterior, cx, total_h, nm_per_px), 255)
            for ring in poly.interiors:
                cv2.fillPoly(m, _px(ring, cx, total_h, nm_per_px), 0)  # holes reveal below
        img[m == 255] = color
    cv2.imwrite(str(out_path), img)
    return (W, H)


def render_profile_spec(spec: dict, palette, out_path, nm_per_px: float = 0.4):
    """spec = {'base': {...params incl mask}, 'ops': [ {...}, ... ]}."""
    base = build_base(spec["base"])
    final = evaluate(base, spec.get("ops", []))
    return render_regions(final, palette, out_path, nm_per_px)
