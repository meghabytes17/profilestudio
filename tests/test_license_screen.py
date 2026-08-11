"""License screen sizing.

The screen has to fit displays we never see: 1366x768 laptops, and Windows desktop
scaling at 125–150% (which is where small screens usually run). Only the geometry maths
is tested — building the window needs a display, which CI does not have.
"""
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter", reason="GUI toolkit not importable here")

from incoming_profile_utility.license_gui import (BTN_PAD, MIN_H, MIN_W, PREF_W,  # noqa: E402
                                                  SCREEN_MARGIN_H, fit_size, fit_top)

# Real pixels the widgets ask for at 100%; roughly what the panel-open state measures.
CONTENT_W, CONTENT_H = 583, 601


def scaled(px, f):
    """What the widgets measure once Windows scaling inflates every font and padding."""
    return int(px * f)


@pytest.mark.parametrize("f", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("screen", [(1366, 768), (1024, 600), (1920, 1080), (2560, 1440)])
def test_window_always_fits_on_the_screen(screen, f):
    sw, sh = screen
    w, h, _ = fit_size(scaled(CONTENT_W, f), scaled(CONTENT_H, f), sw, sh, f)
    assert w * f <= sw, "window is wider than the screen"
    assert h * f <= sh - 40, "window is taller than the screen (no room for the title bar)"


def test_measurements_are_not_scaled_twice():
    """The regression: geometry() scales again, so passing raw pixels squares the factor."""
    w, h, _ = fit_size(scaled(CONTENT_W, 1.5), scaled(CONTENT_H, 1.5), 1920, 1080, 1.5)
    assert h == pytest.approx(CONTENT_H + 2 * BTN_PAD, abs=3)
    assert h < CONTENT_H * 1.5, "height was inflated by the scaling factor instead of divided"


def test_content_that_fits_is_shown_whole():
    w, h, scrolls = fit_size(CONTENT_W, CONTENT_H, 1920, 1080, 1.0)
    assert not scrolls
    assert h >= CONTENT_H, "a window with room to spare should not clip its content"
    assert w == PREF_W


def test_content_too_tall_for_the_screen_scrolls_instead_of_being_cut_off():
    _, h, scrolls = fit_size(scaled(CONTENT_W, 1.5), scaled(CONTENT_H, 1.5), 1366, 768, 1.5)
    assert scrolls, "content taller than the screen must scroll — the buttons sit below it"
    assert h <= 768 / 1.5 - SCREEN_MARGIN_H + 1


def test_never_shrinks_below_a_usable_size():
    """A screen too small for the minimum still gets a usable window, not a sliver."""
    w, h, _ = fit_size(CONTENT_W, CONTENT_H, 480, 320, 1.0)
    assert (w, h) == (MIN_W, MIN_H)


def test_small_content_keeps_the_design_width():
    w, h, _ = fit_size(100, 100, 1920, 1080, 1.0)
    assert w == PREF_W, "narrow content should not produce a cramped window"
    assert h == MIN_H


def test_wide_content_widens_the_window_up_to_the_screen():
    w, _, _ = fit_size(900, CONTENT_H, 1920, 1080, 1.0)
    assert w == 900, "the window should grow to fit content wider than the design width"
    w, _, _ = fit_size(4000, CONTENT_H, 1366, 768, 1.0)
    assert w <= 1366, "…but never past the screen"


def test_a_window_that_grows_slides_up_instead_of_off_the_screen():
    """Opening the renew panel on a short screen used to push the buttons out of reach."""
    y = 160                                  # where a 288px window was centred on 768px
    assert fit_top(y, 288, 768) == y, "a window that fits should not be moved"
    moved = fit_top(y, 625, 768)             # the panel opens: 625px tall
    assert moved + 625 <= 768
    assert moved >= 0


def test_a_window_taller_than_the_screen_starts_at_the_top():
    assert fit_top(100, 2000, 768) == 0


def test_scroll_region_binding_is_additive():
    """CTkScrollableFrame maintains its scroll region from its own <Configure> binding.

    A plain bind() replaces it, which leaves the body unscrollable exactly when the screen
    is too small — silently, since everything still looks right on a big monitor.
    """
    src = (Path(__file__).resolve().parents[1] / "src" / "incoming_profile_utility"
           / "license_gui.py").read_text(encoding="utf-8")
    assert 'bind("<Configure>", self._rewrap, add="+")' in src
