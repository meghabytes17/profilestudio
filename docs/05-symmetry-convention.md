# 05 — Symmetry Convention (finalized)

## Rule
The profile is symmetric about the **vertical center line** of the canvas. This is
achieved by centering every width within `max_width`:

    left_edge  = (max_width - width) / 2
    right_edge =  max_width - (max_width - width) / 2

The renderer fills a left polygon and a right polygon that are mirror images, so
symmetry is exact by construction — no per-pixel drift.

## Input implication
CSV `Width` is the **full** CD (not a half-width). A single centered feature has
its centerline on the mirror axis.

## For parametric builders (docs/03)
Build the right half in physical space, then mirror to the left before rasterizing,
so the same guarantee holds for tapered/re-entrant/scalloped walls.
