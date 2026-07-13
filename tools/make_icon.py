"""Profile Studio icon.

Brand: SandBox Semiconductor tokens (navy #0E1B2E, blue #6E90C6, green #4FD093).
Motif: the app's subject - a semiconductor cross-section with a U-shaped trench -
wearing the logo's circuit-probe signature (thin stroke ending in an open circle).
The wordmark is never recreated; only the brand's colours and pin motif are used.

The trench liner is drawn as a FILLED outer-U minus inner-U (not a stroked path), so the
walls meet the rounded bottom seamlessly. Stroking left a visible step at the join because
PIL insets an arc's stroke but centres a line's.

Two size-tuned drawings (standard practice for icons):
  * detailed   -> 256 / 128 / 64 / 48 px
  * simplified -> 32 / 16 px (fine strokes vanish at these sizes)
"""
from PIL import Image, ImageDraw
from pathlib import Path

NAVY   = (14, 27, 46)
INK    = (40, 61, 93)
BLUE_L = (110, 144, 198)
GREEN  = (79, 208, 147)

S = 1024


def _tile(radius=210):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=NAVY)
    return im, d


def _u_fill(d, cx, half, top, bc, color):
    """Filled U: straight walls down to the bottom-arc centre `bc`, then a semicircle of
    radius `half`. One solid shape - no stroke joins to go wrong."""
    d.rectangle([cx - half, top, cx + half, bc], fill=color)
    d.pieslice([cx - half, bc - half, cx + half, bc + half], 0, 180, fill=color)


def _liner(d, cx, half, top, bc, t, color, void=NAVY):
    """Constant-thickness U liner: fill the outer U, then knock out the inner U."""
    _u_fill(d, cx, half + t, top, bc, color)     # outer
    _u_fill(d, cx, half - t, top, bc, void)      # inner (the open trench)


def detailed():
    """Cross-section: light film over substrate, U trench with a green liner, probe pins."""
    im, d = _tile()
    L, Rr = 108, S - 108
    d.rectangle([L, 620, Rr, 872], fill=INK)        # substrate
    d.rectangle([L, 430, Rr, 620], fill=BLUE_L)     # film
    cx, half, top, bc, t = S // 2, 150, 430, 650, 13
    _liner(d, cx, half, top, bc, t, GREEN)
    for x in (cx - half - 168, cx + half + 168):    # probe pins (brand motif)
        d.line([(x, 232 + 34), (x, 430)], fill=GREEN, width=18)
        d.ellipse([x - 34, 232 - 34, x + 34, 232 + 34], outline=GREEN, width=18)
    return im


def simplified():
    """16/32 px: bold trench through a film band. No hairlines - they'd disappear."""
    im, d = _tile(radius=190)
    cx, half, top, bc, t = S // 2, 205, 330, 605, 59
    d.rectangle([96, 470, S - 96, 700], fill=INK)               # film band it cuts through
    _liner(d, cx, half, top, bc, t, GREEN)
    d.line([(96, 900), (S - 96, 900)], fill=BLUE_L, width=54)   # substrate rule
    return im


def build(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    big, small = detailed(), simplified()
    big.resize((512, 512), Image.LANCZOS).save(outdir / "icon.png")   # window/taskbar icon
    frames = [big.resize((s, s), Image.LANCZOS) for s in (256, 128, 64, 48)]
    frames += [small.resize((s, s), Image.LANCZOS) for s in (32, 16)]
    ico = outdir / "icon.ico"
    frames[0].save(ico, format="ICO",
                   sizes=[(f.width, f.height) for f in frames], append_images=frames[1:])
    return ico, outdir / "icon.png"


if __name__ == "__main__":
    ico, png = build(Path(__file__).resolve().parents[1] / "assets")
    print("wrote", ico, "and", png)
