"""Golden test: the CSV->BMP pipeline must reproduce the reference render exactly."""
from pathlib import Path

import cv2
import numpy as np

from incoming_profile_utility.profiles import render_trace_csv

ROOT = Path(__file__).resolve().parents[1]


def test_e1s1_matches_reference(tmp_path):
    out = tmp_path / "e1s1.bmp"
    render_trace_csv(ROOT / "sample_inputs" / "e1s1.csv", out)  # auto nm/px
    mine = cv2.imread(str(out))
    ref = cv2.imread(str(ROOT / "tests" / "golden" / "e1s1_test.bmp"))
    assert mine is not None and ref is not None
    assert mine.shape == ref.shape
    assert np.array_equal(mine, ref), "render drifted from the golden reference"
