"""Process-op engine + mask shapes."""
import numpy as np
from shapely.geometry import box

from incoming_profile_utility.process import (
    build_base, evaluate, mask_polygon, conformal_deposit, fill, etch, planarize,
    planar_deposit,
)

BASE = dict(pitch=120, feature_height=200, bottom_width=40, top_width=60, mask_height=0)


def _top_width(poly, top):
    band = poly.intersection(box(-999, top - 1.0, 999, top - 0.2))
    return 0.0 if band.is_empty else band.bounds[2] - band.bounds[0]


def test_mask_square_facet_round():
    w, h, y = 40, 50, 100
    top = y + h
    sq = mask_polygon(w, h, y, "square")
    fac = mask_polygon(w, h, y, "facet", facet_angle=45)
    rnd = mask_polygon(w, h, y, "round", radius=12)
    assert abs(sq.area - w * h) < 1e-6
    assert abs(_top_width(sq, top) - w) < 0.5          # square: full width at top
    assert _top_width(fac, top) < w - 5                # facet: narrower at top
    assert fac.area < sq.area and rnd.area < sq.area    # both remove corner material
    # facet angle steeper -> less removed (closer to square)
    steep = mask_polygon(w, h, y, "facet", facet_angle=75)
    assert steep.area > fac.area


def test_conformal_deposit_grows_solid_and_nests():
    base = build_base(BASE)
    a0 = base.solid().area
    st = conformal_deposit(base, "oxide", 8)
    assert st.solid().area > a0                         # solid grew
    assert st.regions[-1][0] == "oxide"


def test_fill_closes_open_region():
    base = build_base(BASE)
    open0 = base.open().area
    st = fill(base, "tungsten", up_to=BASE["feature_height"])
    assert st.open().area < open0 * 0.15                # trench largely filled


def test_isotropic_etch_removes_material():
    base = build_base(BASE)
    st = etch(base, 6, mode="isotropic")
    assert st.solid().area < base.solid().area


def test_planarize_cuts_above_height():
    base = build_base(dict(**{**BASE, "mask_height": 40}))
    st = planarize(base, 200)                            # cut the mask off at feature top
    assert st.solid().bounds[3] <= 200 + 1e-6


def test_planar_deposit_raises_top():
    base = build_base(BASE)
    top0 = base.solid().bounds[3]
    st = planar_deposit(base, "oxide", 15)
    assert st.solid().bounds[3] >= top0 + 14


def test_evaluate_runs_full_stack():
    ops = [dict(op="conformal_deposit", material="oxide", thickness=7),
           dict(op="conformal_deposit", material="nitride", thickness=6),
           dict(op="fill", material="tungsten")]
    st = evaluate(build_base(BASE), ops)
    mats = [m for m, _ in st.regions]
    assert mats[-3:] == ["oxide", "nitride", "tungsten"]


def test_base_types():
    from incoming_profile_utility.process import build_base
    p = dict(pitch=100, feature_height=100, bottom_width=30, top_width=40, mask_height=10)
    assert build_base({**p, "base_type": "blank"}).regions == []          # empty canvas
    sub = build_base({**p, "base_type": "substrate"})
    assert [m for m, _ in sub.regions] == ["silicon"]                     # flat slab only
    line = build_base({**p, "base_type": "line"})
    assert line.solid().area > 0 and "hardmask" in [m for m, _ in line.regions]


def test_superlattice_from_substrate():
    from incoming_profile_utility.process import build_base, evaluate
    base = build_base(dict(base_type="substrate", pitch=100, feature_height=20, mask_height=0))
    ops = [dict(op="planar_deposit", material="sige" if i % 2 else "silicon", thickness=15) for i in range(6)]
    st = evaluate(base, ops)
    assert len(st.regions) == 7                                           # substrate + 6 films
    assert st.solid().bounds[3] > 20                                      # stack grew upward


def test_repeat_block_expands():
    from incoming_profile_utility.process import build_base, evaluate
    base = build_base(dict(base_type="substrate", pitch=100, feature_height=20, mask_height=0))
    ops = [dict(op="repeat", times=8, steps=[
        dict(op="planar_deposit", material="silicon", thickness=15),
        dict(op="planar_deposit", material="sige", thickness=12)])]
    st = evaluate(base, ops)
    assert len(st.regions) == 1 + 8 * 2                 # substrate + 8×(2 films)
    mats = [m for m, _ in st.regions]
    assert mats.count("sige") == 8 and mats.count("silicon") == 9


def test_opening_depth():
    from incoming_profile_utility.process import build_base
    # row 1 = TOP, so silicon (last) is the bottom layer
    layers = [dict(material="nitride", thickness=20),
              dict(material="oxide", thickness=20),
              dict(material="silicon", thickness=40)]   # total 80
    full = build_base(dict(material_layers=layers, pitch=120, space=50))
    sil_full = [g for m, g in full.regions if m == "silicon"][0]
    shallow = build_base(dict(material_layers=layers, pitch=120, space=50, opening_depth=30))
    sil_shallow = [g for m, g in shallow.regions if m == "silicon"][0]
    assert sil_shallow.area > sil_full.area                 # bottom layer no longer notched
    assert abs(sil_shallow.area - 120 * 40) < 1e-6          # full solid band


def test_selective_etch():
    from incoming_profile_utility.process import build_base, evaluate
    base = build_base(dict(material_layers=[
        dict(material="hardmask", thickness=20), dict(material="silicon", thickness=40)],
        pitch=120, space=0, top_vacuum=10))
    a_sil = [g for m, g in base.regions if m == "silicon"][0].area
    a_hm  = [g for m, g in base.regions if m == "hardmask"][0].area
    st = evaluate(base, [dict(op="etch", depth=15, anisotropy=1.0, material="hardmask")])
    reg = dict((m, g.area) for m, g in st.regions)
    assert reg["silicon"] == a_sil            # silicon untouched
    assert reg["hardmask"] < a_hm             # only hardmask etched
