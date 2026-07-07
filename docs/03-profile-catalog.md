# 03 — Profile Catalog (grounded in example_profiles/)

The domain, confirmed by your `e1s1` trace and the `example_profiles/` figures, is
**etch / feature cross-section profiles** (trenches, vias, lines) defined either by a
width-vs-height **trace** (CSV, already working) or **parametrically**. All output
must remain symmetric (docs/05) and render via the shared polygon renderer.

## Mode A — Trace (implemented)
A CSV of `Width, Height` -> centered symmetric polygon -> `.bmp`.
Reproduces `e1s1_test.bmp` byte-for-byte. This is the baseline; everything below
generates the same left/right polygon structure so the renderer is shared.

## Mode B — Parametric (to build)
Core feature parameters: structure **pitch**, top **CD**, feature **depth**, and a
**sidewall profile**. On top of that, the modifiers seen in your examples:

| Feature / modifier | Seen in | Parameters |
|--------------------|---------|------------|
| Vertical sidewall | Fig. 4 (Bosch) | SWA = 90 deg |
| Tapered / positive slope | Fig. 4, Fig. 2 | SWA < 90 (top wider than bottom) |
| Re-entrant / negative (undercut) | Fig. 4 | SWA > 90 (bottom wider) |
| Scalloping | Fig. 4 (Bosch DRIE) | scallop pitch + depth along the wall |
| Bowing | Fig. 2 | max bulge width at mid-height |
| Footing | Fig. 5 (Samco) | extra width flare at the base |
| Notching | Fig. 5 (Samco) | width pinch just above the base |
| Microtrench | Fig. 5 | narrow deepening at trench-bottom corners |
| Corner rounding | e1s1, Fig. 2 | top/bottom corner radius |
| Conformal film | (process flows) | film thickness -> polygon offset |

## Implementation note
Most modifiers are polygon operations on the half-profile:
- Tapered / re-entrant walls: linear x-offset vs. height.
- Scalloping: periodic perturbation added to the wall x(height).
- Footing / notching / bowing: localized width deltas over a height band.
- Corner rounding & conformal films: polygon offsetting -- this is where
  shapely.buffer() earns its place (listed as the `geometry` optional dep).

## To confirm with you
- Which of the above are must-haves for v1 vs. later.
- Your naming for each (so GUI controls match your vocabulary).
- Typical default values per parameter.
