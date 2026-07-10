"""Regression tests — one per bug fixed during development, so none can silently return.

Each test names the symptom it locks down. These all exercise the *engine* (pure
geometry/logic); the customtkinter GUI is intentionally not unit-tested here.
"""
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from incoming_profile_utility.process import (
    build_base, evaluate, _rect_opening, _corner_cut, _trace_opening,
)
from incoming_profile_utility.materials import load_palette, _DEFAULT_CONFIG
from incoming_profile_utility.io_csv import load_trace

ROOT = Path(__file__).resolve().parents[1]


def _areas(st):
    return {m: g.area for m, g in st.regions}


def _stack(**kw):
    kw.setdefault("pitch", 120)
    kw.setdefault("top_vacuum", 10)
    return build_base(kw)


# --- material-stack base geometry ---------------------------------------------

def test_space_equals_opening_width_no_doubling():
    """'space' maps directly to the opening width (it used to double)."""
    st = _stack(material_layers=[dict(material="silicon", thickness=60)], space=40)
    assert abs(_areas(st)["silicon"] - (120 * 60 - 40 * 60)) < 1e-6


def test_row1_is_top_of_stack():
    """The first layer in the list renders at the TOP (build order was reversed)."""
    st = _stack(material_layers=[dict(material="nitride", thickness=20),
                                 dict(material="silicon", thickness=40)], space=0)
    nitride = [g for m, g in st.regions if m == "nitride"][0]
    silicon = [g for m, g in st.regions if m == "silicon"][0]
    assert nitride.bounds[1] > silicon.bounds[1]     # nitride sits higher


def test_layers_tile_with_no_gap_or_overlap():
    st = _stack(material_layers=[dict(material="silicon", thickness=30),
                                 dict(material="oxide", thickness=30)], space=0)
    assert abs(sum(g.area for _, g in st.regions) - 120 * 60) < 1e-6


def test_opening_depth_leaves_bottom_layer_solid():
    layers = [dict(material="nitride", thickness=20),
              dict(material="oxide", thickness=20),
              dict(material="silicon", thickness=40)]
    st = build_base(dict(material_layers=layers, pitch=120, space=50, opening_depth=30))
    silicon = [g for m, g in st.regions if m == "silicon"][0]
    assert abs(silicon.area - 120 * 40) < 1e-6       # untouched below the opening


def test_top_vacuum_adds_headroom():
    st = build_base(dict(material_layers=[dict(material="silicon", thickness=50)],
                         pitch=100, space=0, top_vacuum=20))
    assert abs(st.cell.bounds[3] - 70) < 1e-6        # 50 + 20


# --- process ops --------------------------------------------------------------

def test_conformal_deposit_on_empty_is_a_blanket():
    """Depositing onto a blank canvas produced nothing; now it blankets."""
    base = build_base(dict(material_layers=[], pitch=120, space=0, top_vacuum=0))
    st = evaluate(base, [dict(op="conformal_deposit", material="oxide", thickness=20)])
    assert "oxide" in _areas(st)


def test_conformal_deposit_grows_cell_for_top_coating():
    """A top-surface film was clipped when there was no headroom; now the cell grows."""
    base = build_base(dict(material_layers=[dict(material="silicon", thickness=40)],
                           pitch=120, space=40, top_vacuum=2))
    top0 = base.cell.bounds[3]
    st = evaluate(base, [dict(op="conformal_deposit", material="oxide", thickness=15)])
    assert st.cell.bounds[3] > top0


def test_selective_etch_leaves_other_materials():
    """Etch used to remove everything; with a material it removes only that one."""
    base = build_base(dict(material_layers=[dict(material="hardmask", thickness=20),
                                            dict(material="silicon", thickness=40)],
                           pitch=120, space=0, top_vacuum=5))
    a0 = _areas(base)
    st = evaluate(base, [dict(op="etch", depth=15, anisotropy=1.0, material="hardmask")])
    a1 = _areas(st)
    assert abs(a1["silicon"] - a0["silicon"]) < 1e-6
    assert a1["hardmask"] < a0["hardmask"]


def test_isotropic_etch_undercuts_laterally():
    """Isotropic etch was a rectangular vertical cut; now it expands in all directions."""
    base = dict(material_layers=[dict(material="silicon", thickness=120)],
                pitch=200, space=40, top_vacuum=5)
    iso = evaluate(build_base(base), [dict(op="etch", depth=25, anisotropy=0.0)])
    ani = evaluate(build_base(base), [dict(op="etch", depth=25, anisotropy=1.0)])
    sil_iso = [g for m, g in iso.regions if m == "silicon"][0]
    sil_ani = [g for m, g in ani.regions if m == "silicon"][0]
    assert sil_iso.area < sil_ani.area               # isotropic removes more (undercut)


# --- per-layer corner shapes --------------------------------------------------

def test_taper_angle_is_from_horizontal():
    """taper angle is the sidewall angle from horizontal: 90 = vertical (no cut)."""
    assert _corner_cut([dict(kind="taper", angle=90)], 20, 100, 0) is None
    cut = _corner_cut([dict(kind="taper", angle=45)], 20, 100, 0)
    assert cut is not None and cut.area > 0


def test_facet_needs_depth_to_do_anything():
    """facet with depth 0 was a silent no-op; assert the contract explicitly."""
    assert _corner_cut([dict(kind="facet", angle=45, depth=0)], 20, 100) is None
    assert _corner_cut([dict(kind="facet", angle=45, depth=20)], 20, 100).area > 0


def test_treatments_combine():
    both = _corner_cut([dict(kind="chamfer", s=10), dict(kind="round", r=15)], 20, 100)
    assert both is not None and both.area > 0


# --- bottom rounding: the "side location conflict" crash ----------------------

@pytest.mark.parametrize("depth,radius", [(30, 40), (20, 60), (15, 50), (200, 47)])
def test_rounded_bottom_is_always_valid(depth, radius):
    """Shallow opening + big radius twisted the polygon (GEOS 'side location conflict')."""
    op = _rect_opening(80, 240 - depth, 240, radius)
    assert op.is_valid


def test_shallow_bottom_round_builds_and_processes():
    p = dict(material_layers=[dict(material="indigo", thickness=240)], pitch=210,
             space=80, top_vacuum=20, opening_depth=30, opening_bottom_radius=40)
    st = evaluate(build_base(p), [dict(op="etch", depth=10, anisotropy=0.0)])  # must not raise
    assert st.regions


# --- CSV loading --------------------------------------------------------------

def test_csv_rejects_ragged_rows(tmp_path):
    """Mismatched column lengths (NaN) crashed the rasterizer; now rejected up front."""
    p = tmp_path / "bad.csv"
    p.write_text("width,height\n0,0\n10,50\n20\n")
    with pytest.raises(ValueError):
        load_trace(p)


def test_csv_negative_width_rejected(tmp_path):
    p = tmp_path / "nw.csv"
    pd.DataFrame({"width": [0, -10, 20], "height": [0, 1, 2]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        load_trace(p)


def test_csv_negative_height_normalized(tmp_path):
    p = tmp_path / "nh.csv"
    pd.DataFrame({"width": [0, 10, 20], "height": [-30, 20, 70]}).to_csv(p, index=False)
    assert abs(float(load_trace(p)["height"].min())) < 1e-9          # shifted to 0
    assert float(load_trace(p, normalize=False)["height"].min()) == -30  # raw kept


def test_csv_opening_reference_line():
    trace = [(30, 0), (30, 40)]
    assert abs(_trace_opening(trace, 100).bounds[3] - 100) < 1e-6      # top-aligned
    assert abs(_trace_opening(trace, 100, ref=0).bounds[1] - 0) < 1e-6  # height=0 at y=0


# --- materials persistence ----------------------------------------------------

def test_adding_material_never_touches_tracked_base(tmp_path, monkeypatch):
    """The app used to rewrite the tracked config, breaking every git pull."""
    import incoming_profile_utility.materials as M
    monkeypatch.setattr(M, "_USER_CONFIG", tmp_path / "user_materials.json")
    before = hashlib.md5(Path(_DEFAULT_CONFIG).read_bytes()).hexdigest()
    pal = load_palette()
    pal.add("zzz_regression", (1, 2, 3))
    pal.save()
    after = hashlib.md5(Path(_DEFAULT_CONFIG).read_bytes()).hexdigest()
    assert before == after                                   # base untouched
    assert (tmp_path / "user_materials.json").exists()       # user delta written


# --- additional coverage for recent features ------------------------------------

def test_partial_anisotropy_between_vertical_and_isotropic():
    """0 < anisotropy < 1 should undercut more than vertical, less than isotropic."""
    base = dict(material_layers=[dict(material="silicon", thickness=120)],
                pitch=200, space=40, top_vacuum=5)
    def remaining(a):
        st = evaluate(build_base(base), [dict(op="etch", depth=25, anisotropy=a)])
        return [g for m, g in st.regions if m == "silicon"][0].area
    assert remaining(1.0) > remaining(0.5) > remaining(0.0)   # more vertical -> less removed


def test_opening_bottom_full_semicircle():
    """radius >= half-width gives a U that narrows to ~0 at the very bottom."""
    from shapely.geometry import box as _box
    space = 80
    op = _rect_opening(space, 0, 200, space)                  # radius capped to half-width
    minx, miny, maxx, maxy = op.bounds
    base_slab = op.intersection(_box(-999, miny, 999, miny + 1))
    assert (base_slab.bounds[2] - base_slab.bounds[0]) < space * 0.5


def test_taper_opens_wider_at_top():
    """A taper on a layer widens its opening toward the top of that layer."""
    from shapely.geometry import box as _box
    layers = [dict(material="silicon", thickness=150, shape=[dict(kind="taper", angle=70)])]
    st = build_base(dict(material_layers=layers, pitch=200, space=50, top_vacuum=5, opening_depth=150))
    sil = [g for m, g in st.regions if m == "silicon"][0]
    def opening_width(y):
        solid = sil.intersection(_box(-100, y - 0.5, 100, y + 0.5)).area   # 1 nm strip
        return 200 - solid
    assert opening_width(140) > opening_width(20)


def test_csv_reference_places_negative_below_line():
    """height=0 lands on the reference line; negative-height points sit below it."""
    trace = [(20, -30), (30, 0), (20, 40)]
    poly = _trace_opening(trace, 200, ref=100)
    assert poly.bounds[1] < 100 < poly.bounds[3]


def test_csv_loads_valid_trace(tmp_path):
    import pandas as pd
    p = tmp_path / "ok.csv"
    pd.DataFrame({"width": [0, 30, 0], "height": [0, 20, 40]}).to_csv(p, index=False)
    df = load_trace(p)
    assert list(df.columns)[:2] == ["width", "height"] and len(df) == 3


def test_user_materials_merge_on_reload(tmp_path, monkeypatch):
    """Saved user materials merge back in on the next load, with correct RGB/BGR."""
    import incoming_profile_utility.materials as M
    monkeypatch.setattr(M, "_USER_CONFIG", tmp_path / "user.json")
    pal = load_palette(); pal.add("mymat", (10, 20, 30)); pal.save()
    pal2 = load_palette()
    assert "mymat" in pal2.names()
    assert pal2.rgb("mymat") == (10, 20, 30)
    assert pal2.bgr("mymat") == (30, 20, 10)


def test_trace_to_parametric_detects_interior_bow():
    import pandas as pd
    from incoming_profile_utility.io_csv import trace_to_parametric
    out = trace_to_parametric(pd.DataFrame({"width": [20, 60, 20], "height": [0, 20, 40]}))
    assert out["feature_height"] == 40
    assert out["bottom_width"] == 20 and out["top_width"] == 20
    assert out.get("bow") == 60 and abs(out["bow_height"] - 20) < 1e-6


def test_trace_to_parametric_monotonic_gives_mid_width():
    import pandas as pd
    from incoming_profile_utility.io_csv import trace_to_parametric
    out = trace_to_parametric(pd.DataFrame({"width": [20, 40, 60], "height": [0, 20, 40]}))
    assert "bow" not in out and "mid_width" in out


def test_round_plus_taper_keeps_mask_connected():
    """round + taper on a mask with a rounded opening bottom must not carve isolated
    islands out of the mask (the 'holes' bug from tester feedback)."""
    layers = [dict(material="hardmask", thickness=200,
                   shape=[dict(kind="round", r=60), dict(kind="taper", angle=75)]),
              dict(material="photoresist", thickness=60)]
    st = build_base(dict(material_layers=layers, pitch=240, space=90, top_vacuum=20,
                         opening_depth=200, opening_bottom_radius=45))
    hm = [g for m, g in st.regions if m == "hardmask"][0]
    parts = len(hm.geoms) if hm.geom_type == "MultiPolygon" else 1
    assert parts <= 2 and hm.is_valid          # left + right bars only, no slivers


def test_smoothing_introduces_no_blended_colors(tmp_path):
    """Oversampled (smoothed) renders must contain ONLY exact palette colors — no
    anti-alias blends — and never more colors than materials + background."""
    import cv2, numpy as np
    from incoming_profile_utility.process import render_regions
    from incoming_profile_utility.materials import load_palette
    pal = load_palette()
    base = build_base(dict(material_layers=[dict(material="oxide", thickness=200,
                          shape=[dict(kind="round", r=50)])], pitch=200, space=90,
                          top_vacuum=40, opening_depth=200, opening_bottom_radius=40))
    st = evaluate(base, [dict(op="conformal_deposit", material="nitride", thickness=30),
                         dict(op="fill", material="tungsten")])
    allowed = {tuple(pal.bgr(m)) for m, _ in st.regions} | {(0, 0, 0)}
    for ss in (1, 2, 4, 8):
        out = tmp_path / f"s{ss}.bmp"
        render_regions(st, pal, out, 0.6, oversample=ss)
        cols = {tuple(px) for px in cv2.imread(str(out)).reshape(-1, 3).tolist()}
        assert cols <= allowed, f"blended colors at {ss}x: {cols - allowed}"


def test_pixels_never_overlap_two_materials(tmp_path):
    """Regions are disjoint and each pixel gets exactly one material color."""
    import cv2
    from incoming_profile_utility.process import render_regions
    from incoming_profile_utility.materials import load_palette
    pal = load_palette()
    base = build_base(dict(material_layers=[dict(material="hardmask", thickness=120),
                                            dict(material="silicon", thickness=180)],
                           pitch=200, space=70, top_vacuum=20, opening_depth=120))
    st = evaluate(base, [dict(op="conformal_deposit", material="nitride", thickness=25)])
    render_regions(st, pal, tmp_path / "o.bmp", 0.5)
    cols = {tuple(px) for px in cv2.imread(str(tmp_path / "o.bmp")).reshape(-1, 3).tolist()}
    allowed = {tuple(pal.bgr(m)) for m, _ in st.regions} | {(0, 0, 0)}
    assert cols <= allowed


def test_fill_overfill_controls_height():
    """Fill is flush with the surface at overfill=0 and adds blanket overburden above it."""
    base = build_base(dict(material_layers=[dict(material="oxide", thickness=250)],
                           pitch=200, space=90, top_vacuum=80, opening_depth=250,
                           opening_bottom_radius=45))
    def w_top(overfill):
        st = evaluate(base, [dict(op="fill", material="tungsten", overfill=overfill)])
        return [g for m, g in st.regions if m == "tungsten"][0].bounds[3]
    assert abs(w_top(0) - 250) < 1e-6          # flush with the oxide surface
    assert abs(w_top(40) - 290) < 1e-6         # 40 nm overburden
    assert w_top(9999) <= 330 + 1e-6           # clamped to the cell top
