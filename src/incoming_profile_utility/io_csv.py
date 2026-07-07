"""CSV input loading and validation.

Finalize against the real e1s1.csv (see docs/01-csv-input-format.md).
"""
from __future__ import annotations

from pathlib import Path


def load_profile_csv(path: str | Path):
    """Load a heights/widths CSV into an in-memory profile description.

    TODO: parse columns, coerce units, validate (docs/01), return a structured object.
    """
    raise NotImplementedError("Define columns/units from e1s1.csv first.")
