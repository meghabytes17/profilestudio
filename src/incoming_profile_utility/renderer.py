"""Rasterize polygons to a .bmp using OpenCV (matches the reference pipeline).

Fill color and background are BGR (OpenCV convention). Default (232,162,0) BGR
renders as sky-blue (0,162,232) RGB on a black background. See docs/04.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

FILL_BGR = (232, 162, 0)
BG_BGR = (0, 0, 0)


def render_polygons(polygons, dims: tuple[int, int], out_path: str | Path,
                    fill_bgr=FILL_BGR) -> None:
    """Fill polygons on a canvas of size dims=(h, w) and save as .bmp."""
    h, w = dims
    img = np.zeros((h, w, 3))  # float canvas; cv2 falls back to 8-bit on write
    for poly in polygons:
        cv2.fillPoly(img, np.array([poly], dtype=np.int32), fill_bgr)
    cv2.imwrite(str(out_path), img)


def render_layers(layers, dims: tuple[int, int], out_path) -> None:
    """Fill a list of (polygon_pixels, bgr_color) onto a canvas of size dims=(h, w).

    Layers are painted in order, so later materials overpaint earlier ones.
    """
    h, w = dims
    img = np.zeros((h, w, 3))
    for poly, bgr in layers:
        cv2.fillPoly(img, np.array([poly], dtype=np.int32), bgr)
    cv2.imwrite(str(out_path), img)
