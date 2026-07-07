"""Application entry point.

Supports (eventually) two modes:
    - GUI:   python -m incoming_profile_utility.main
    - CLI:   python -m incoming_profile_utility.main --csv sample_inputs/e1s1.csv --out outputs/e1s1_test.bmp
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Incoming Profile Utility")
    parser.add_argument("--csv", help="Path to a heights/widths CSV input.")
    parser.add_argument("--out", help="Path to the output .bmp file.")
    parser.add_argument("--no-gui", action="store_true", help="Run headless (CLI only).")
    args = parser.parse_args(argv)

    if args.csv and args.out:
        # TODO: wire up io_csv -> profiles -> geometry (symmetry) -> renderer
        print(f"[stub] would render {args.csv} -> {args.out}")
        return 0

    if args.no_gui:
        parser.error("--no-gui requires --csv and --out")

    # TODO: launch GUI (see gui.py)
    print("[stub] GUI not implemented yet. Try --csv ... --out ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
