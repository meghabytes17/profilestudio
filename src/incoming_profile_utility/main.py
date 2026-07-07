"""Application entry point.

    GUI:  python -m incoming_profile_utility.main
    CLI:  python -m incoming_profile_utility.main --csv sample_inputs/e1s1.csv \
                                                  --out outputs/e1s1_test.bmp [--nm-per-px 0.25]
"""
from __future__ import annotations

import argparse
import sys

from .profiles import render_trace_csv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Incoming Profile Utility")
    p.add_argument("--csv", help="Path to a width/height trace CSV.")
    p.add_argument("--out", help="Output .bmp path.")
    p.add_argument("--nm-per-px", type=float, default=None,
                   help="Scale (nm per pixel). Omit to auto-compute.")
    p.add_argument("--no-gui", action="store_true", help="Run headless (CLI only).")
    args = p.parse_args(argv)

    if args.csv and args.out:
        npp, (w, h) = render_trace_csv(args.csv, args.out, args.nm_per_px)
        print(f"Rendered {args.out}  ({w}x{h} px, nm/px={npp})")
        return 0

    if args.no_gui:
        p.error("--no-gui requires --csv and --out")

    try:
        from .gui import launch
        launch()
    except NotImplementedError:
        print("[stub] GUI not implemented yet. Use --csv ... --out ... for now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
