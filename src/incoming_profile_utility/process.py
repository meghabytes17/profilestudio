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
from shapely.geometry import Polygon, box, Point
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
# Base state — selectable starting point for the process stack
#   blank     : empty cell (all vacuum); build everything with ops
#   substrate : a flat slab of surround material; build a film stack on top
#   trench    : inverted default — vacuum trench carved into surround + mask
#   line      : a solid feature (CD curve) standing in vacuum + mask
# --------------------------------------------------------------------------- #
def _trace_opening(trace, total_h, ref=None):
    """Symmetric opening polygon from a width/height trace.

    ref is None -> top-align (trace's top at the stack top). Otherwise ref is the
    y-height (from the stack bottom) where the trace's height=0 is placed, and the
    trace extends up/down from there (its own height values, so negative heights sit
    below the reference).
    """
    pts = sorted(((float(w), float(h)) for w, h in trace), key=lambda t: t[1])
    if not pts:
        return None
    if ref is None:
        off = total_h - max(h for _, h in pts)     # top-align
    else:
        off = float(ref)                           # height=0 -> ref line
    right = [(w / 2.0, h + off) for w, h in pts]
    left = [(-w / 2.0, h + off) for w, h in pts][::-1]
    poly = Polygon(right + left)
    return poly if poly.is_valid else poly.buffer(0)


def _corner_cut(shape_list, cx, top, bottom=None):
    """Union of corner/wall removal shapes for the RIGHT side at opening edge cx.

    Treatments (combinable): round(r), chamfer(s), facet(angle,depth) shape the top
    corner; taper(angle) slopes the ENTIRE layer wall — angle is the sidewall angle from
    the HORIZONTAL base (90 = vertical, smaller = more sloped, opening wider at the top).
    `bottom` is the layer's bottom y (needed for taper).
    """
    cuts = []
    for t in shape_list or []:
        k = t.get("kind")
        if k == "chamfer":
            s = float(t.get("s", 0) or 0)
            if s > 0: cuts.append(Polygon([(cx, top), (cx + s, top), (cx, top - s)]))
        elif k == "facet":
            ang = math.radians(float(t.get("angle", 45) or 45)); d = float(t.get("depth", 0) or 0)
            if d > 0 and 0 < ang < math.pi / 2:
                run = d / math.tan(ang)
                cuts.append(Polygon([(cx, top), (cx + run, top), (cx, top - d)]))
        elif k == "round":
            r = float(t.get("r", 0) or 0)
            if r > 0:
                cuts.append(box(cx, top - r, cx + r, top).difference(Point(cx + r, top - r).buffer(r, quad_segs=32)))
        elif k == "taper":
            ang = float(t.get("angle", 80) or 0)     # sidewall angle from HORIZONTAL base; 90 = vertical
            if bottom is not None and top > bottom and 0 < ang < 90:
                run = (top - bottom) / math.tan(math.radians(ang))
                cuts.append(Polygon([(cx, top), (cx + run, top), (cx, bottom)]))
    if not cuts:
        return None
    u = unary_union(cuts)
    return None if u.is_empty else u


def _rect_opening(space, open_bottom, total, bottom_r=0.0):
    """Rectangular opening; optionally round the two BOTTOM corners (U-shape).
    The radius is capped to fit both the half-width and the opening height, so a
    shallow opening with a big radius can't produce a self-intersecting polygon."""
    x = space / 2.0
    h = total - open_bottom
    if bottom_r <= 0 or h <= 0:
        return box(-x, open_bottom, x, total)
    r = min(bottom_r, x, h)                     # must fit the width AND the opening height
    pts = [(-x, total), (-x, open_bottom + r)]
    import numpy as _np
    for a in _np.linspace(math.pi, 1.5 * math.pi, 20):          # left-bottom arc
        pts.append((-x + r + r * math.cos(a), open_bottom + r + r * math.sin(a)))
    for a in _np.linspace(1.5 * math.pi, 2 * math.pi, 20):      # right-bottom arc
        pts.append((x - r + r * math.cos(a), open_bottom + r + r * math.sin(a)))
    pts.append((x, total))
    poly = Polygon(pts)
    return poly if poly.is_valid else poly.buffer(0)


def _build_material_stack(p: dict) -> State:
    """Vertical stack of material layers with a centered opening.

    Layers are TOP-first (row 1 = top). Height = sum of thicknesses + `top_vacuum`
    (default 20 nm). The opening is a rectangle (`space` wide, cut down by
    `opening_depth`) or, if `opening_trace` is given, that CSV trace shape. Each layer
    may carry a `shape` list of top-inner-corner treatments (combinable, mirrored).
    Empty stack -> blank canvas.
    """
    pitch = p.get("pitch", 100.0)
    space = p.get("space", 0.0) or 0.0
    top_vac = p.get("top_vacuum", 20.0) or 0.0
    layers = [l for l in p.get("material_layers", []) if l.get("thickness", 0) > 0]
    total = sum(l["thickness"] for l in layers)
    trace = p.get("opening_trace")
    open_bottom = 0.0
    if trace:
        opening = _trace_opening(trace, total, p.get("opening_ref"))
    else:
        depth = p.get("opening_depth")
        open_bottom = 0.0 if (depth is None or depth <= 0 or depth >= total) else (total - depth)
        opening = _rect_opening(space, open_bottom, total, p.get("opening_bottom_radius", 0) or 0) if space > 0 else None
    if opening is not None and not opening.is_valid:
        opening = opening.buffer(0)
    cell = box(-pitch / 2, 0, pitch / 2, max(total + top_vac, 1.0))
    st = State(cell, [])
    # the opening wall is straight only from the top down to here; below this it is the
    # rounded bottom (or the opening has ended), so corner cuts must not reach lower or
    # they'd carve disconnected islands out of the mask.
    bottom_r = min((p.get("opening_bottom_radius", 0) or 0), space / 2) if trace is None else 0.0
    wall_bottom = open_bottom + bottom_r
    y = 0.0
    for l in reversed(layers):            # last row -> bottom, first row -> top
        th = l["thickness"]; top = y + th
        band = box(-pitch / 2, y, pitch / 2, top)
        if opening is not None:
            band = band.difference(opening)
        shape = l.get("shape")
        if shape and trace is None and space > 0 and top > open_bottom:
            cut_bottom = max(y, wall_bottom)                       # taper stops at the straight-wall bottom
            if top > cut_bottom:
                rc = _corner_cut(shape, space / 2, top, cut_bottom)
                if rc is not None:
                    rc = rc.intersection(box(-pitch / 2, cut_bottom, pitch / 2, top))  # never below the wall
                    if not rc.is_valid: rc = rc.buffer(0)
                    if not rc.is_empty:
                        lc = affinity.scale(rc, xfact=-1, origin=(0, 0))   # symmetric mirror
                        band = band.difference(rc).difference(lc)
        if not band.is_valid:
            band = band.buffer(0)
        st.add(l["material"], band)
        y += th
    return st


def build_base(p: dict) -> State:
    if p.get("material_layers") is not None:
        return _build_material_stack(p)
    # --- legacy base_type path (kept for programmatic use / tests) ---
    H = p["feature_height"]
    bottom, top = p.get("bottom_width", 0.0), p.get("top_width", 0.0)
    pitch = p.get("pitch") or (p["space"] + p.get("linewidth", top))
    base_type = p.get("base_type", "trench")

    # mask as an ordered stack of layers (bottom -> top). Back-compat: a single
    # mask_material + mask_height becomes a one-layer stack.
    mask_layers = p.get("mask_layers")
    if mask_layers is None:
        mh = p.get("mask_height", 0.0)
        mask_layers = [dict(material=p.get("mask_material", "hardmask"), height=mh)] if mh > 0 else []
    mask_layers = [l for l in mask_layers if l.get("height", 0) > 0]
    total_mask = sum(l["height"] for l in mask_layers)
    total_h = H + total_mask
    cell = box(-pitch / 2, 0, pitch / 2, max(total_h, 1.0))
    st = State(cell, [])
    surround = p.get("surround_material", "silicon")

    if base_type == "blank":
        return st
    if base_type == "substrate":
        st.add(surround, box(-pitch / 2, 0, pitch / 2, H))
        return st

    ys = np.linspace(0, H, 240)
    xs = half_width_curve(ys, H, bottom, top, p.get("bow"), p.get("bow_height"), p.get("mid_width"))
    feature = Polygon([(x, y) for x, y in zip(xs, ys)] + [(-x, y) for x, y in zip(xs, ys)][::-1])

    if base_type == "line":
        st.add(p.get("feature_material", surround), feature)
    else:
        st.add(surround, box(-pitch / 2, 0, pitch / 2, H).difference(feature))

    # mask stack — each layer is a band; only the TOP layer gets the corner shape,
    # and (for a trench) the trench opening is carved through every layer.
    mask_width = p.get("mask_width", pitch)
    corner = p.get("mask_corner", "square"); fa = p.get("mask_facet_angle", 45.0); rad = p.get("mask_radius", 0.0)
    y = H
    for idx, layer in enumerate(mask_layers):
        lh = layer["height"]; is_top = idx == len(mask_layers) - 1
        if is_top and corner != "square":
            mp = mask_polygon(mask_width, lh, y, corner, fa, rad)
        else:
            mp = box(-mask_width / 2, y, mask_width / 2, y + lh)
        if base_type != "line":
            mp = mp.difference(box(-top / 2, y, top / 2, y + lh))   # trench opening
        st.add(layer["material"], mp)
        y += lh
    return st


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
def _extrude_down(geom, depth):
    steps = max(4, int(depth) + 1)
    return unary_union([affinity.translate(geom, yoff=-k)
                        for k in np.linspace(0, depth, steps)])


def conformal_deposit(state: State, material: str, thickness: float) -> State:
    """Uniform film of `thickness` grown on all exposed surfaces into the open region.

    On an empty base the first film is a blanket (planar). The cell is grown upward as
    needed so a film deposited on the TOP surface is shown rather than clipped away.
    """
    s = state.solid()
    if s.is_empty:
        return planar_deposit(state, material, thickness)
    minx, miny, maxx, maxy = state.cell.bounds
    ext = box(minx, miny, maxx, maxy + thickness)                # room for top coating
    film = s.buffer(thickness, join_style=2).difference(s).intersection(ext)
    newtop = max(maxy, film.bounds[3] if not film.is_empty else maxy)
    st = state.copy(); st.cell = box(minx, miny, maxx, newtop)
    st.regions.append((material, film)); return st


def planar_deposit(state: State, material: str, thickness: float) -> State:
    """Add a flat slab of `thickness` on top of the current highest solid surface."""
    top_y = state.solid().bounds[3] if not state.solid().is_empty else 0.0
    minx, _, maxx, _ = state.cell.bounds
    st = state.copy()
    st.ensure_top(top_y + thickness)                 # give the slab headroom
    st.add(material, box(minx, top_y, maxx, top_y + thickness)); return st


def fill(state: State, material: str, overfill: float = 0.0, up_to: float | None = None) -> State:
    """Gap-fill the open region (trenches, voids).

    By default the fill is flush with the surface (the top of the existing solid). A
    positive `overfill` adds that many nm of blanket material above the surface (overburden
    you might later planarize away). `up_to` overrides with an absolute fill height.
    """
    minx, miny, maxx, maxy = state.cell.bounds
    if up_to is not None:
        level = up_to
    else:
        surface = max((g.bounds[3] for _, g in state.regions), default=miny)
        level = min(maxy, surface + max(0.0, overfill))
    region = state.open().intersection(box(minx, miny, maxx, level))
    st = state.copy(); st.add(material, region); return st


def etch(state: State, depth: float, anisotropy: float = 1.0,
         material: str | None = None, mode: str | None = None) -> State:
    """Remove material from exposed surfaces to `depth`.

    anisotropy in [0,1]: 1 = vertical (no undercut), 0 = isotropic. `material` selects
    which material is etched — if given, only that material is removed (the etch stops
    on other materials); None/"(any)" etches everything exposed.
    """
    if mode == "isotropic": anisotropy = 0.0
    elif mode == "anisotropic": anisotropy = 1.0
    a = min(max(float(anisotropy), 0.0), 1.0)
    op = state.open()
    if a <= 1e-6:
        removal = op.buffer(depth, join_style=1)              # isotropic: equal in all directions, rounded
    else:
        removal = _extrude_down(op, depth)                    # vertical component
        lateral = depth * (1.0 - a)
        if lateral > 1e-9:
            removal = removal.buffer(lateral, join_style=1)   # rounded lateral undercut
    removal = removal.intersection(state.solid())
    tgt = None if material in (None, "", "(any)") else material
    new = []
    for m, g in state.regions:
        if tgt is None or m == tgt:
            gg = g.difference(removal)
            if not gg.is_empty: new.append((m, gg))
        else:
            new.append((m, g))
    return State(state.cell, new)


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
    """Run an ordered op-list. Each op: {'op': name, ...params}.

    A {'op':'repeat', 'times':N, 'steps':[...]} group expands to N passes of its
    sub-steps (nesting allowed), which is how superlattices/multilayer stacks are built.
    """
    state = base
    for op in ops:
        if op.get("op") == "repeat":
            for _ in range(max(1, int(op.get("times", 1)))):
                state = evaluate(state, op.get("steps", []))
            continue
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


def _downsample_mode(label, ss):
    """Downsample an integer label image by majority vote (no blending).
    Ties prefer a material over background so thin layers aren't eaten."""
    H, W = label.shape
    Ht, Wt = H // ss, W // ss
    if Ht == 0 or Wt == 0:
        return label
    blocks = (label[:Ht * ss, :Wt * ss]
              .reshape(Ht, ss, Wt, ss).transpose(0, 2, 1, 3).reshape(Ht, Wt, ss * ss))
    shifted = blocks + 1                      # background -1 -> 0
    maxv = int(shifted.max())
    best = np.zeros((Ht, Wt), np.int32)
    out = np.zeros((Ht, Wt), np.int32)
    order = list(range(1, maxv + 1)) + [0]    # materials first, background last (loses ties)
    for v in order:
        cnt = (shifted == v).sum(axis=2).astype(np.int32)
        take = cnt > best
        out[take] = v; best[take] = cnt[take]
    return out - 1


def render_regions(state: State, palette, out_path, nm_per_px: float = 0.4, oversample: int = 1):
    """Rasterize the profile. Every output pixel is assigned to exactly ONE material
    (or background), so materials never overlap and — with oversample>1 — edges are
    smoothed by majority vote WITHOUT introducing any blended/intermediate colors.
    The number of distinct colors equals the number of materials drawn (+ black)."""
    minx, miny, maxx, maxy = state.cell.bounds
    pitch = maxx - minx
    total_h = maxy - miny
    ss = max(1, int(oversample))
    npp = nm_per_px / ss
    W = int(math.ceil(pitch / npp)); H = int(math.ceil(total_h / npp))
    cx = pitch / 2
    label = np.full((H, W), -1, np.int32)     # -1 = background / vacuum
    colors = []
    for idx, (material, geom) in enumerate(state.regions):
        colors.append(palette.bgr(material))
        m = np.zeros((H, W), np.uint8)
        for poly in _polys(geom):
            cv2.fillPoly(m, _px(poly.exterior, cx, total_h, npp), 255)
            for ring in poly.interiors:
                cv2.fillPoly(m, _px(ring, cx, total_h, npp), 0)   # holes reveal below
        label[m == 255] = idx                 # later material wins -> one label per pixel
    if ss > 1:
        label = _downsample_mode(label, ss)
        H, W = label.shape
    img = np.zeros((H, W, 3), np.uint8)
    for idx, color in enumerate(colors):
        img[label == idx] = color             # exact palette colors only
    cv2.imwrite(str(out_path), img)
    return (W, H)


def render_profile_spec(spec: dict, palette, out_path, nm_per_px: float = 0.4):
    """spec = {'base': {...params incl mask}, 'ops': [ {...}, ... ]}."""
    base = build_base(spec["base"])
    final = evaluate(base, spec.get("ops", []))
    return render_regions(final, palette, out_path, nm_per_px)
