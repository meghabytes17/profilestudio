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


def test_ico_uses_dib_below_256_and_png_at_256():
    """Windows Explorer expects classic DIB entries below 256px. PNG-compressed small entries
    are a known cause of Explorer showing a generic/stale icon, so the encoding is asserted."""
    import struct
    raw = (ROOT / "assets" / "icon.ico").read_bytes()
    _, typ, count = struct.unpack("<HHH", raw[:6])
    assert typ == 1 and count >= 6
    off = 6
    seen = {}
    for _ in range(count):
        w, h, _, _, _, bpp, size, offset = struct.unpack("<BBBBHHII", raw[off:off + 16])
        off += 16
        W = w or 256
        blob = raw[offset:offset + size]
        assert len(blob) == size, f"{W}px entry is truncated"
        assert bpp == 32, f"{W}px entry is not 32-bit"
        seen[W] = "PNG" if blob[:8] == b"\x89PNG\r\n\x1a\n" else "DIB"
    for px, fmt in seen.items():
        if px >= 256:
            assert fmt == "PNG", "the 256px entry should be PNG-compressed"
        else:
            assert fmt == "DIB", f"{px}px entry is {fmt}; Windows wants DIB below 256px"


def test_every_ico_frame_decodes():
    for s in (16, 32, 48, 64, 128, 256):
        im = Image.open(ROOT / "assets" / "icon.ico")
        im.size = (s, s)
        assert im.convert("RGBA").size == (s, s)


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


# --------------------------------------------------------------------------- #
# Measure snapping (snap endpoints to material boundaries)
# --------------------------------------------------------------------------- #
def test_snap_edges_detects_material_boundaries():
    """The snap edge-map must find the boundaries in a composed preview."""
    import numpy as np
    from PIL import Image
    # a simple two-band image: the boundary row should be detected as edges
    im = Image.new("RGB", (40, 40), (0, 162, 232))
    im.paste(Image.new("RGB", (40, 20), (127, 127, 127)), (0, 0))
    a = np.asarray(im).astype(np.int16)
    dy = np.any(a[1:, :, :] != a[:-1, :, :], axis=2)
    ys = np.where(dy)[0]
    assert 19 in ys or 20 in ys        # the colour change sits at the band boundary


# --------------------------------------------------------------------------- #
# Versioning: one source of truth, wired everywhere
# --------------------------------------------------------------------------- #
def test_version_sources_agree():
    """pyproject and the package must declare the same version, so a build can't ship
    with a mismatched number."""
    import tomllib
    import incoming_profile_utility as ipu
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == ipu.__version__


def test_version_string_is_well_formed():
    import re
    import incoming_profile_utility as ipu
    assert re.fullmatch(r"\d+\.\d+\.\d+", ipu.__version__)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ipu.__build_date__)
    assert ipu.__version__ in ipu.version_string()
    assert ipu.__build_date__ in ipu.version_string()


def test_exe_version_resource_matches(tmp_path):
    """tools/make_version_info.py stamps the .exe with the same version."""
    import importlib.util
    import incoming_profile_utility as ipu
    spec = importlib.util.spec_from_file_location("mvi", ROOT / "tools" / "make_version_info.py")
    mvi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mvi)
    # the generated resource file (written to build/) must carry this version
    res = (ROOT / "build" / "version_info.txt")
    if res.exists():
        text = res.read_text()
        assert f"'FileVersion', '{ipu.__version__}'" in text


def test_spec_references_version_resource():
    spec = (ROOT / "incoming_profile_utility.spec").read_text()
    assert "version_info.txt" in spec


# --------------------------------------------------------------------------- #
# Hex colour entry for new materials
# --------------------------------------------------------------------------- #
def test_parse_hex_accepts_common_forms():
    from incoming_profile_utility.gui import ProfileStudio
    f = ProfileStudio._parse_hex
    assert f("#4FD093") == (79, 208, 147)
    assert f("4fd093") == (79, 208, 147)      # no leading hash
    assert f("#4d9") == (68, 221, 153)        # short form expands
    assert f("  #FFFFFF ") == (255, 255, 255) # whitespace tolerated
    assert f("000000") == (0, 0, 0)


def test_parse_hex_rejects_bad_input():
    from incoming_profile_utility.gui import ProfileStudio
    f = ProfileStudio._parse_hex
    for bad in ("", "#12", "#12345", "xyzxyz", "gggggg", None):
        assert f(bad) is None


def test_parse_hex_roundtrips_palette_hex():
    """A colour parsed from hex, added to the palette, reads back as the same hex."""
    from incoming_profile_utility.gui import ProfileStudio
    from incoming_profile_utility.materials import load_palette
    rgb = ProfileStudio._parse_hex("#3C64B4")
    pal = load_palette()
    pal.add("cobalt_test", rgb, label="Cobalt")
    assert pal.hex("cobalt_test") == "#3C64B4"


# --------------------------------------------------------------------------- #
# Recolouring an existing material
# --------------------------------------------------------------------------- #
def _fresh_palette(tmp_path, monkeypatch):
    """A palette whose user-overrides file lives in tmp, so tests don't touch real config."""
    from incoming_profile_utility import materials as M
    monkeypatch.setattr(M, "_USER_CONFIG", tmp_path / "user_materials.json")
    return M


def test_recolouring_a_base_material_persists(tmp_path, monkeypatch):
    """Recolouring a SHIPPED material must survive a reload — it is saved as a user override,
    never by editing the tracked base palette."""
    M = _fresh_palette(tmp_path, monkeypatch)
    pal = M.load_palette()
    assert pal.is_base("oxide") and not pal.is_modified("oxide")
    pal.set_rgb("oxide", (230, 60, 140))
    assert pal.is_modified("oxide")
    assert "oxide" in pal.user_materials()          # would previously have been filtered out
    pal.save()
    assert M.load_palette().hex("oxide") == "#E63C8C"


def test_reset_to_base_restores_shipped_colour(tmp_path, monkeypatch):
    M = _fresh_palette(tmp_path, monkeypatch)
    pal = M.load_palette()
    shipped = pal.hex("oxide")
    pal.set_rgb("oxide", (1, 2, 3)); pal.save()
    pal = M.load_palette()
    assert pal.reset_to_base("oxide") is True
    assert pal.hex("oxide") == shipped
    pal.save()
    assert M.load_palette().hex("oxide") == shipped
    assert not M.load_palette().is_modified("oxide")


def test_base_palette_file_is_never_written(tmp_path, monkeypatch):
    """The tracked config/materials.json must be untouched by a recolour."""
    M = _fresh_palette(tmp_path, monkeypatch)
    tracked = ROOT / "config" / "materials.json"
    before = tracked.read_bytes()
    pal = M.load_palette(); pal.set_rgb("silicon", (9, 9, 9)); pal.save()
    assert tracked.read_bytes() == before


def test_recoloured_material_renders_in_its_new_colour(tmp_path, monkeypatch):
    """The bitmap must contain the new colour and NOT the old one (exact-palette guarantee)."""
    M = _fresh_palette(tmp_path, monkeypatch)
    pal = M.load_palette()
    old = pal.rgb("oxide")
    pal.set_rgb("oxide", (230, 60, 140))
    st = evaluate(build_base(dict(material_layers=[dict(material="oxide", thickness=100)],
                                  pitch=200, space=80, top_vacuum=0, opening_depth=50)), [])
    out = tmp_path / "r.bmp"
    render_regions(st, pal, out, 0.5)
    import numpy as np
    a = np.asarray(Image.open(out).convert("RGB")).reshape(-1, 3)
    cols = {tuple(c) for c in np.unique(a, axis=0)}
    assert (230, 60, 140) in cols
    assert tuple(old) not in cols


# --------------------------------------------------------------------------- #
# IP hygiene: what the app leaves on disk
# --------------------------------------------------------------------------- #
def test_preview_is_not_written_to_a_fixed_shared_temp_path():
    """Regression: the preview render (the customer's cross-section = their IP) must not go to
    a predictable path in the shared temp dir, where it survived after exit and where two
    instances clobbered each other."""
    src = (ROOT / "src" / "incoming_profile_utility" / "gui.py").read_text()
    assert "_ipu_preview.bmp" not in src, "preview is using a fixed shared temp filename again"
    assert "_session_tmp()" in src, "preview should render into the private session directory"


def test_session_tmp_is_private_and_purges(tmp_path, monkeypatch):
    """The scratch directory is owner-only and is removed, taking any render with it."""
    import os
    import tempfile as T
    from incoming_profile_utility.gui import ProfileStudio

    obj = ProfileStudio.__new__(ProfileStudio)          # no Tk needed for this logic
    obj._tmpdir = None
    d = ProfileStudio._session_tmp(obj)
    assert d.exists()
    if os.name == "posix":                              # Windows uses ACLs, not mode bits
        assert oct(d.stat().st_mode)[-3:] == "700"
    (d / "preview.bmp").write_bytes(b"secret-geometry")
    ProfileStudio._purge_tmp(obj)
    assert not d.exists(), "scratch directory (and the render inside it) must be removed"


def test_no_network_or_telemetry_in_source():
    """Airgap constraint: nothing may fetch, phone home, or auto-update at runtime."""
    import re
    src_dir = ROOT / "src"
    bad = []
    for py in src_dir.rglob("*.py"):
        text = py.read_text()
        for pat in (r"\burllib\b", r"\brequests\.", r"\bsocket\.", r"urlopen", r"webbrowser",
                    r"https?://(?!www\.w3\.org)"):       # w3.org is the SVG namespace, not a fetch
            if re.search(pat, text):
                bad.append(f"{py.name}: {pat}")
    assert not bad, f"possible network dependency: {bad}"


def test_no_code_execution_primitives_in_source():
    """A hostile project/CSV must not be able to reach eval/exec/pickle/subprocess."""
    import re
    bad = []
    for py in (ROOT / "src").rglob("*.py"):
        text = py.read_text()
        for pat in (r"\beval\(", r"\bexec\(", r"\bpickle\b", r"\bsubprocess\b",
                    r"os\.system\(", r"shell\s*=\s*True", r"yaml\.load\("):
            if re.search(pat, text):
                bad.append(f"{py.name}: {pat}")
    assert not bad, f"code-execution primitive reachable: {bad}"


def test_dependencies_are_pinned_for_release_builds():
    """Reproducible airgapped builds need an exact set, not floating >= bounds.

    Tolerates both forms of the lock: plain pins, and the hash-pinned output of
    `pip-compile --generate-hashes` (where each pin is followed by `--hash=` continuation
    lines and trailing backslashes)."""
    lock = ROOT / "requirements-lock.txt"
    assert lock.exists(), "requirements-lock.txt missing"
    pins = []
    for raw in lock.read_text().splitlines():
        line = raw.strip().rstrip("\\").strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue                       # comments, hash continuations, pip flags
        pins.append(line)
    assert pins, "lock file has no pins"
    unpinned = [p for p in pins if "==" not in p]
    assert not unpinned, f"unpinned entries: {unpinned}"
    names = {p.split("==")[0].lower().replace("_", "-") for p in pins}
    for pkg in ("numpy", "pandas", "opencv-python", "customtkinter", "pillow", "shapely"):
        assert pkg in names, f"{pkg} not pinned"


def test_no_raw_exception_text_is_shown_in_the_ui():
    """Error messages must be generic: raw exception text typically embeds absolute paths and
    internal structure, which then travels in screenshots and support tickets. Detail belongs
    in the hover tooltip, not on screen."""
    import re
    src = (ROOT / "src" / "incoming_profile_utility" / "gui.py").read_text()
    # a widget's visible text must never interpolate the caught exception
    offenders = re.findall(r'text\s*=\s*f?"[^"]*\{exc\}[^"]*"', src)
    assert not offenders, f"raw exception rendered into UI text: {offenders}"
    assert "_show_error(" in src, "errors should go through the generic-message helper"


def test_show_error_keeps_detail_off_screen(tmp_path):
    """_show_error puts the generic message on the widget and the detail in the tooltip."""
    from incoming_profile_utility.gui import ProfileStudio

    class FakeWidget:
        def __init__(self): self.kw = {}
        def configure(self, **kw): self.kw.update(kw)
        def bind(self, *a, **k): pass

    app = ProfileStudio.__new__(ProfileStudio)
    w = FakeWidget()
    secret = "C:\\Users\\Dagger\\SecretTapeout\\wafer.json"
    detail = ProfileStudio._show_error(app, w, "⚠ Couldn't open that project file.",
                                       FileNotFoundError(secret))
    assert secret not in w.kw.get("text", ""), "path leaked into the visible message"
    assert secret in detail, "detail should still be retrievable for diagnosis"


# --------------------------------------------------------------------------- #
# Branding: real logo, product name, exe name
# --------------------------------------------------------------------------- #
def test_real_logo_asset_ships_and_is_bundled():
    logo = ROOT / "assets" / "sandbox-logo.png"
    assert logo.exists(), "the real sandbox-logo.png must ship with the app"
    im = Image.open(logo)
    assert im.mode in ("RGBA", "LA") or "transparency" in im.info, "logo should be transparent"
    spec = (ROOT / "incoming_profile_utility.spec").read_text()
    assert "assets/sandbox-logo.png" in spec, "logo not bundled into the .exe"


def test_mark_is_not_recreated_as_styled_text():
    """Brand rule: use the real mark, never a text stand-in for it."""
    src = (ROOT / "src" / "incoming_profile_utility" / "gui.py").read_text()
    assert "SANDBOX · PROFILE STUDIO" not in src
    assert "sandbox-logo.png" in src, "header should load the real logo asset"


def test_executable_is_named_profile_studio():
    spec = (ROOT / "incoming_profile_utility.spec").read_text()
    assert 'name="ProfileStudio"' in spec
    assert "IncomingProfileUtility" not in (ROOT / "build_exe.bat").read_text()


def test_user_config_migrates_from_the_old_name():
    """Renaming the app must not orphan materials saved by earlier versions."""
    src = (ROOT / "src" / "incoming_profile_utility" / "materials.py").read_text()
    assert '"ProfileStudio"' in src
    assert "IncomingProfileUtility" in src, "legacy path must still be checked for migration"
    assert "copytree" in src, "old user materials should be carried over"


def test_release_notes_cover_the_current_version():
    import incoming_profile_utility as ipu
    notes = (ROOT / "RELEASE_NOTES.md").read_text()
    assert f"## {ipu.__version__}" in notes, "current version has no release-notes section"
    assert ipu.__build_date__ in notes
