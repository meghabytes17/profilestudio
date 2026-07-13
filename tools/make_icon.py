"""Profile Studio icon.

Brand: SandBox Semiconductor tokens (navy #0E1B2E, blue #6E90C6, green #4FD093).
Motif: the app's subject — a semiconductor cross-section with a U-shaped trench —
wearing the logo's circuit-probe signature (thin stroke ending in an open circle).
The wordmark is never recreated; only the brand's colours and pin motif are used.

Two size-tuned drawings (standard practice for icons):
  * detailed  -> 256 / 128 / 64 / 48 px
  * simplified-> 32 / 16 px (fine strokes vanish at these sizes)
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


def detailed():
    """Cross-section: light film over substrate, U trench, two probe pins."""
    im, d = _tile()
    L, Rr = 108, S - 108
    d.rectangle([L, 620, Rr, 872], fill=INK)        # substrate
    d.rectangle([L, 430, Rr, 620], fill=BLUE_L)     # film
    cx, half, top, bot = S // 2, 150, 430, 800
    # trench void
    d.rectangle([cx - half, top, cx + half, bot - half], fill=NAVY)
    d.pieslice([cx - half, bot - 2 * half, cx + half, bot], 0, 180, fill=NAVY)
    # green trench walls + rounded bottom
    d.line([(cx - half, top), (cx - half, bot - half)], fill=GREEN, width=26)
    d.line([(cx + half, top), (cx + half, bot - half)], fill=GREEN, width=26)
    d.arc([cx - half, bot - 2 * half, cx + half, bot], 0, 180, fill=GREEN, width=26)
    # probe pins (the brand motif)
    for x in (cx - half - 168, cx + half + 168):
        d.line([(x, 232 + 34), (x, 430)], fill=GREEN, width=18)
        d.ellipse([x - 34, 232 - 34, x + 34, 232 + 34], outline=GREEN, width=18)
    return im


def simplified():
    """16/32 px: bold trench through a film band. No hairlines — they'd disappear."""
    im, d = _tile(radius=190)
    cx, half, top, bot, w = S // 2, 205, 330, 812, 118
    d.rectangle([96, 470, S - 96, 700], fill=INK)       # film band it cuts through
    d.line([(cx - half, top), (cx - half, bot - half)], fill=GREEN, width=w)
    d.line([(cx + half, top), (cx + half, bot - half)], fill=GREEN, width=w)
    d.arc([cx - half, bot - 2 * half, cx + half, bot], 0, 180, fill=GREEN, width=w)
    d.line([(96, 900), (S - 96, 900)], fill=BLUE_L, width=54)   # substrate rule
    return im


def build(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    big, small = detailed(), simplified()
    big.resize((512, 512), Image.LANCZOS).save(outdir / "icon.png")       # window/taskbar icon
    frames = []
    for size in (256, 128, 64, 48):
        frames.append(big.resize((size, size), Image.LANCZOS))
    for size in (32, 16):
        frames.append(small.resize((size, size), Image.LANCZOS))
    ico = outdir / "icon.ico"
    frames[0].save(ico, format="ICO",
                   sizes=[(f.width, f.height) for f in frames], append_images=frames[1:])
    return ico, outdir / "icon.png"


if __name__ == "__main__":
    ico, png = build(Path("/home/claude/incoming-profile-utility/assets"))
    print("wrote", ico, "and", png)
