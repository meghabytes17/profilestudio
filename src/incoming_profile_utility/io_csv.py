"""CSV input loading and validation.

Format (finalized against sample_inputs/e1s1.csv): two numeric columns, `Width`
and `Height` (matched case-insensitively). Each row is the FULL width (CD, in nm)
of the feature at that height (in nm). See docs/01-csv-input-format.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_trace(path: str | Path) -> pd.DataFrame:
    """Load a width/height trace CSV into a validated DataFrame (columns: width, height)."""
    csv = pd.read_csv(path, float_precision="round_trip")
    wcol = [c for c in csv.columns if c.lower() == "width"]
    hcol = [c for c in csv.columns if c.lower() == "height"]
    if not wcol or not hcol:
        raise ValueError("CSV must have columns labeled 'width' and 'height'.")
    df = pd.DataFrame({"width": csv[wcol[0]], "height": csv[hcol[0]]}).apply(
        pd.to_numeric, errors="raise"
    )
    if (df["width"] < 0).any() or (df["height"] < 0).any():
        raise ValueError("Width and height values must be non-negative.")
    return df
