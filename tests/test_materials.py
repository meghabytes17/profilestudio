"""Palette + material/vacuum composition."""
import cv2
import numpy as np

from incoming_profile_utility.materials import load_palette
from incoming_profile_utility.parametric import build_profile
from incoming_profile_utility import renderer as rnd


def test_palette_loads_and_resolves():
    pal = load_palette()
    assert "vacuum" in pal.names()
    assert pal.rgb("vacuum") == (0, 0, 0)
    r, g, b = pal.rgb("silicon")
    assert pal.bgr("silicon") == (b, g, r)          # BGR conversion for OpenCV


def _corners(path):
    im = cv2.imread(str(path))                       # BGR
    h, w, _ = im.shape
    center = tuple(int(v) for v in im[h // 2, w // 2])
    edge = tuple(int(v) for v in im[h // 2, 2])
    return center, edge


def test_inverted_is_vacuum_in_material(tmp_path):
    pal = load_palette()
    p = dict(pitch=90, feature_height=200, bottom_width=30,
             top_width=45)  # defaults: vacuum in silicon
    layers, dims = build_profile(p, pal, 0.4)
    out = tmp_path / "inv.bmp"
    rnd.render_layers(layers, dims, out)
    center, edge = _corners(out)
    assert center == (0, 0, 0)                       # trench center is vacuum
    assert edge == pal.bgr("silicon")                # surround is silicon


def test_solid_material_feature(tmp_path):
    pal = load_palette()
    p = dict(pitch=90, feature_height=200, bottom_width=40, top_width=40,
             surround_material="vacuum", feature_material="poly", mask_height=0)
    layers, dims = build_profile(p, pal, 0.4)
    out = tmp_path / "solid.bmp"
    rnd.render_layers(layers, dims, out)
    center, edge = _corners(out)
    assert center == pal.bgr("poly")                 # solid feature center is poly
    assert edge == (0, 0, 0)                         # surround is vacuum
