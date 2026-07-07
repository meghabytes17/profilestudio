"""The 'bow' knob must bend the sidewall as documented."""
import cv2
import numpy as np

from incoming_profile_utility.parametric import render_line, FEATURE_BGR

FEATURE = np.array(FEATURE_BGR, dtype=np.uint8)  # cv2 stores/reads BGR


def _widths(path):
    im = cv2.imread(str(path))
    mask = np.all(im == FEATURE, axis=2)
    rows = np.where(mask.any(axis=1))[0]
    at = lambda f: int(mask[rows[int(f * (len(rows) - 1))]].sum())
    return at(0.98), at(0.5), at(0.02)  # bottom, mid, top


def _render(params, path):
    render_line(params, path)
    return path


def test_bow_signs(tmp_path):
    base = dict(pitch=90, feature_height=200, bottom_width=32, top_width=32)
    b, m, t = _widths(_render({**base, "bow": 16}, tmp_path / "barrel.bmp"))
    assert m > b and m > t                      # positive bow bulges at mid
    b, m, t = _widths(_render({**base, "bow": -16}, tmp_path / "waist.bmp"))
    assert m < b and m < t                      # negative bow pinches at mid
    b, m, t = _widths(_render({**base, "bow": 0}, tmp_path / "straight.bmp"))
    assert abs(m - (b + t) / 2) <= 2            # zero bow is linear
