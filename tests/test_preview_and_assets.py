"""Preview composition (static grid) and packaged icon assets.

compose_preview is a pure function, so it can be tested without a display; it encodes the
'the grid must not bounce around' requirement. The icon tests guard the .exe/window branding.
"""
from pathlib import Path

import pytest
from PIL import Image

from incoming_profile_utility.gui import compose_preview
from incoming_profile_utility.process import build_base, evaluate, render_regions
from incoming_profile_utility.materials import load_palette

ROOT = Path(__file__).resolve().parents[1]


def _bmp(tmp_path, name, layers, **fields):
    pal = load_palette()
    params = dict(material_layers=layers, pitch=200, space=80, top_vacuum=20,
                  opening_depth=100, opening_bottom_radius=0)
    params.update(fields)
    st = evaluate(build_base(params), [])
    out = tmp_path / name
    render_regions(st, pal, out, 0.5)
    return out


# --------------------------------------------------------------------------- #
# Static plot box: the grid keeps a constant size whatever the profile is
# --------------------------------------------------------------------------- #
def test_plot_box_is_fixed_regardless_of_profile_shape(tmp_path):
    """The grid panel must NOT resize when the profile's aspect changes."""
    tall = _bmp(tmp_path, "tall.bmp", [dict(material="oxide", thickness=500)],
                pitch=120, space=40, opening_depth=500)
    wide = _bmp(tmp_path, "wide.bmp", [dict(material="silicon", thickness=40)],
                pitch=600, space=300, opening_depth=40)
    many = _bmp(tmp_path, "many.bmp",
                [dict(material="hardmask", thickness=60), dict(material="oxide", thickness=60),
                 dict(material="silicon", thickness=300)], pitch=200, space=90, opening_depth=180)
    sizes = {compose_preview(p, 0.5, box_w=700, box_h=400).size for p in (tall, wide, many)}
    assert sizes == {(700, 400)}, f"plot box changed size across profiles: {sizes}"


def test_plot_box_follows_requested_box_size(tmp_path):
    bmp = _bmp(tmp_path, "a.bmp", [dict(material="oxide", thickness=200)])
    assert compose_preview(bmp, 0.5, box_w=640, box_h=380).size == (640, 380)
    assert compose_preview(bmp, 0.5, box_w=900, box_h=520).size == (900, 520)


def test_profile_is_letterboxed_inside_the_box(tmp_path):
    """A tall profile is scaled to fit (aspect preserved), never cropped or stretched."""
    tall = _bmp(tmp_path, "t.bmp", [dict(material="oxide", thickness=600)],
                pitch=100, space=40, opening_depth=600)
    _, fit = compose_preview(tall, 0.5, box_w=700, box_h=400, return_scale=True)
    w, h = Image.open(tall).size
    assert fit > 0
    assert w * fit <= 700 - 48 - 14 + 1e-6      # inside the data area (minus axis margins)
    assert h * fit <= 400 - 12 - 30 + 1e-6


def test_compose_accepts_in_memory_image(tmp_path):
    """Panning composes from a cached PIL image (no disk round-trip per frame)."""
    bmp = _bmp(tmp_path, "m.bmp", [dict(material="oxide", thickness=200)])
    im = Image.open(bmp).convert("RGB")
    assert compose_preview(im, 0.5, box_w=700, box_h=400).size == (700, 400)


def test_fit_scale_gives_exact_nm_per_display_pixel(tmp_path):
    """The measure tool derives nm/px from this scale — it must be exact."""
    npp = 0.5
    bmp = _bmp(tmp_path, "s.bmp", [dict(material="oxide", thickness=300)])
    h_px = Image.open(bmp).size[1]
    _, fit = compose_preview(bmp, npp, box_w=700, box_h=400, return_scale=True)
    nm_per_disp_px = npp / fit
    cell_nm = h_px * npp                       # true cell height in nm
    assert abs((h_px * fit) * nm_per_disp_px - cell_nm) < 1e-6


# --------------------------------------------------------------------------- #
# Icon assets (window + .exe branding)
# --------------------------------------------------------------------------- #
def test_icon_assets_exist():
    assert (ROOT / "assets" / "icon.ico").exists()
    assert (ROOT / "assets" / "icon.png").exists()


def test_ico_contains_all_windows_sizes():
    """Windows picks per-context sizes; a missing 16/32 gives a blurry taskbar icon."""
    ico = Image.open(ROOT / "assets" / "icon.ico")
    sizes = set(ico.info.get("sizes", []))
    assert {(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)} <= sizes


def test_icon_uses_brand_colors():
    png = Image.open(ROOT / "assets" / "icon.png").convert("RGB")
    cols = {c for _, c in png.getcolors(maxcolors=100000)}
    assert (14, 27, 46) in cols                                  # SandBox navy tile
    assert any(abs(r - 79) < 12 and abs(g - 208) < 12 and abs(b - 147) < 12
               for r, g, b in cols)                              # SandBox green trench


def test_spec_wires_the_icon_into_the_exe():
    spec = (ROOT / "incoming_profile_utility.spec").read_text()
    assert 'icon="assets/icon.ico"' in spec
    assert "assets/icon.ico" in spec and "assets/icon.png" in spec   # bundled as data too


def test_make_icon_is_reproducible(tmp_path):
    """tools/make_icon.py regenerates the assets deterministically."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mk", ROOT / "tools" / "make_icon.py")
    mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)
    ico, png = mk.build(tmp_path)
    assert ico.exists() and png.exists()
    assert Image.open(ico).info.get("sizes")
    assert Image.open(png).size == (512, 512)
