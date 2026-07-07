# 04 — Output `.bmp` Specification

## Format
- Windows BMP (uncompressed). Pillow writes this natively via `Image.save("x.bmp")`.
- Color depth: 24-bit RGB by default. (8-bit palettized is an option if materials map
  to a fixed indexed palette — smaller files, crisp material boundaries.)

## Dimensions & scale
- Image size derived from the physical extent × scale `s` (see doc 02), or fit to a
  user-specified canvas size.
- Document exact rounding/padding so `e1s1.csv` reproducibly yields `e1s1_test.bmp`.

## Material coloring
- A palette maps material -> RGB. Options:
  - Fixed built-in palette (deterministic, good for golden tests).
  - User-assignable per material in the GUI.
- Background color and substrate color defined explicitly.

## Open questions
- Anti-aliasing on/off? (Affects byte-for-byte golden comparisons.)
- Include a scale bar / axis / labels, or pure geometry only?
- Fixed output size vs. size-follows-content?

## Reproducibility / testing
- The pipeline must be deterministic: same input + params -> identical BMP bytes.
- Store `tests/golden/e1s1_test.bmp` and compare on CI (see doc note in tests/).
