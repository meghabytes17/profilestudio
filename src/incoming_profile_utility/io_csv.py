"""CSV input loading and validation.

Format (finalized against sample_inputs/e1s1.csv): two numeric columns, `Width`
and `Height` (matched case-insensitively). Each row is the FULL width (CD, in nm)
of the feature at that height (in nm). See docs/01-csv-input-format.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_trace(path: str | Path, normalize: bool = True) -> pd.DataFrame:
    """Load a width/height trace CSV into a validated DataFrame (columns: width, height)."""
    csv = pd.read_csv(path, float_precision="round_trip")
    wcol = [c for c in csv.columns if c.lower() == "width"]
    hcol = [c for c in csv.columns if c.lower() == "height"]
    if not wcol or not hcol:
        raise ValueError("CSV must have columns labeled 'width' and 'height'.")
    df = pd.DataFrame({"width": csv[wcol[0]], "height": csv[hcol[0]]}).apply(
        pd.to_numeric, errors="raise"
    )
    if df.isna().any().any():
        nw = int(df["width"].notna().sum()); nh = int(df["height"].notna().sum())
        raise ValueError(f"CSV has missing values (width entries: {nw}, height entries: {nh}). "
                         "Each row needs exactly one width and one height.")
    if (df["width"] < 0).any():
        raise ValueError("Width must be non-negative — it is the full CD (a size, "
                         "spanning ±width/2 about the centerline), not an x-coordinate.")
    hmin = float(df["height"].min())
    if normalize and hmin < 0:
        df["height"] = df["height"] - hmin   # height is a position; shift so the base = 0
    return df


def trace_to_parametric(df) -> dict:
    """Approximate parametric fields from a width/height trace (for GUI auto-populate).

    Returns keys: feature_height, bottom_width, top_width, and either
    (bow, bow_height) when the widest point is in the interior, else mid_width.
    Pitch/space/mask are not derivable from the trace and are left to the user.
    """
    import numpy as np
    d = df.sort_values("height").reset_index(drop=True)
    h0, h1 = float(d["height"].min()), float(d["height"].max())
    span = h1 - h0
    bottom_raw = float(d["width"].iloc[0])
    top_raw = float(d["width"].iloc[-1])
    out = {
        "feature_height": round(span, 3),
        "bottom_width": round(bottom_raw, 3),
        "top_width": round(top_raw, 3),
    }
    wmax = float(d["width"].max())
    h_at_max = float(d.loc[d["width"].idxmax(), "height"]) - h0
    interior = (0.05 * span) < h_at_max < (0.95 * span)  # widest point not at an end
    if interior and wmax > max(bottom_raw, top_raw) * 1.02:  # a real interior bulge
        out["bow"] = round(wmax, 3)
        out["bow_height"] = round(h_at_max, 3)
    else:
        mid = float(np.interp(h0 + span / 2, d["height"], d["width"]))
        out["mid_width"] = round(mid, 3)
    return out
