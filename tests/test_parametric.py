"""bow = maximum CD, placed at bow_height (default mid)."""
import cv2
import numpy as np
import pytest

from incoming_profile_utility.parametric import render_line, FEATURE_BGR

FEATURE = np.array(FEATURE_BGR, dtype=np.uint8)  # cv2 reads BGR
NPP = 0.4


def _widths(path):
    im = cv2.imread(str(path))
    return np.all(im == FEATURE, axis=2).sum(axis=1)  # feature width per row


def test_bow_is_max_cd_at_requested_height(tmp_path):
    H, MASK, bow, bh = 200, 35, 52, 100
    p = dict(pitch=90, feature_height=H, bottom_width=26, top_width=26,
             bow=bow, bow_height=bh, mask_height=MASK)
    render_line(p, tmp_path / "b.bmp", NPP)
    w = _widths(tmp_path / "b.bmp")
    max_cd_nm = w.max() * NPP
    assert abs(max_cd_nm - bow) <= 1.0                     # max CD equals bow
    row_at_bh = int(round((H + MASK - bh) / NPP))          # row for bow_height
    assert w[row_at_bh] >= w.max() - 1                     # widest point is at bow_height


def test_bow_height_moves_the_peak(tmp_path):
    def peak_h(bh):
        p = dict(pitch=90, feature_height=200, bottom_width=26, top_width=26,
                 bow=52, bow_height=bh, mask_height=35)
        render_line(p, tmp_path / f"p{bh}.bmp", NPP)
        w = _widths(tmp_path / f"p{bh}.bmp")
        band = np.where(w >= w.max() - 1)[0]
        return (200 + 35) - band.mean() * NPP              # physical height of peak band
    assert peak_h(60) < peak_h(100) < peak_h(150)          # peak migrates upward


def test_bow_below_endpoints_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        render_line(dict(pitch=90, feature_height=200, bottom_width=40,
                         top_width=40, bow=30), tmp_path / "x.bmp", NPP)


def test_taper_is_linear_without_bow_or_mid(tmp_path):
    p = dict(pitch=90, feature_height=200, bottom_width=20, top_width=60, mask_height=0)
    render_line(p, tmp_path / "t.bmp", NPP)
    w = _widths(tmp_path / "t.bmp")
    rows = np.where(w > 0)[0]
    b, m, t = w[rows[-1]], w[rows[len(rows)//2]], w[rows[0]]
    assert abs(m - (b + t) / 2) <= 2
