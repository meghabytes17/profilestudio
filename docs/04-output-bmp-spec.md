# 04 — Output `.bmp` Specification (finalized)

## Format
- Windows BMP, 24-bit, written by OpenCV `cv2.imwrite` (float canvas falls back
  to 8-bit on write — this is expected and matches the reference).
- Deterministic: identical input + nm/px -> **byte-identical** BMP. Guarded by
  `tests/test_golden.py` against `tests/golden/e1s1_test.bmp`.

## Colors (OpenCV BGR)
- Fill: `(232, 162, 0)` BGR = sky-blue `(0, 162, 232)` RGB.
- Background: black `(0, 0, 0)`.
- (Future) per-material palette for multi-layer profiles.

## Open (for the expansion)
- Anti-aliasing stays **off** to keep golden comparisons exact.
- Multi-material fills, optional scale bar/labels — deferred.
