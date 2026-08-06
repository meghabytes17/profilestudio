"""SandBox brand theme — colors and the logo mark, shared by every window.

Lives apart from gui.py so small windows (the license screen) can look like the app
without importing the whole editor, engine and image stack.
"""
from __future__ import annotations

NAVY = "#0E1B2E"
NAVY_900 = "#0B1626"
NAVY_800 = "#132540"
NAVY_700 = "#1C2C46"
BLUE = "#283D5D"
BLUE_L = "#6E90C6"
GREEN = "#4FD093"
GREEN_D = "#0E7A49"
GREEN_INK = "#07271A"
ON = "#FFFFFF"
SOFT = "#AEB9C8"
MUT = "#8B99AC"
AMBER = "#E8C46A"
RED = "#E58B8B"          # expiring soon / rejected


def brand_logo(target_h=30):
    """The REAL SandBox mark, placed directly on the dark header.

    Uses the official white (reversed) logo supplied for dark backgrounds — white on
    transparent, ~18:1 against the header. The artwork is never recreated or recolored;
    we just scale it. Falls back to the navy logo on a light plate if the white asset is
    ever missing, so a dark-on-dark invisible mark can't happen.
    """
    from PIL import Image, ImageDraw
    from .materials import _base_dir
    adir = _base_dir() / "assets"
    white = adir / "sandbox-logo-white.png"
    if white.exists():
        try:
            logo = Image.open(white).convert("RGBA")
            lh = target_h
            lw = max(1, int(logo.width * lh / logo.height))
            return logo.resize((lw, lh), Image.LANCZOS)          # straight onto the header
        except Exception:
            pass
    p = adir / "sandbox-logo.png"                                   # fallback: navy on a plate
    if not p.exists():
        return None
    try:
        logo = Image.open(p).convert("RGBA")
    except Exception:
        return None
    plate_h = target_h + 8
    pad_y = 6
    pad_x = 12
    lh = max(1, plate_h - 2 * pad_y)
    lw = max(1, int(logo.width * lh / logo.height))
    logo = logo.resize((lw, lh), Image.LANCZOS)
    plate = Image.new("RGBA", (lw + 2 * pad_x, plate_h), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        [0, 0, plate.width - 1, plate_h - 1], radius=9, fill=(255, 255, 255, 245))
    plate.alpha_composite(logo, (pad_x, pad_y))
    return plate
