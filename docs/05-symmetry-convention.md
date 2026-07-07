# 05 — Symmetry Convention

The generated profile must **always be symmetric**. This defines how.

## Rule
- Mirror plane is the vertical axis `x = 0` (center of the unit cell).
- Build the right half in physical space, then mirror to the left:
  `left = mirror_x(right)`. This guarantees exact symmetry (no per-pixel drift).

## Consequences for input
- If a CSV/parameter gives a **full width** (CD), the half-width is `CD / 2`.
- If input is already two-sided but slightly asymmetric (measurement noise), decide a
  policy: (a) average the two sides, (b) take one side as authoritative, or (c) reject.
  **Default: take right side (or the max) as authoritative and mirror.** Confirm.

## Consequences for rendering
- Render one half at full resolution, mirror the pixel buffer, concatenate — OR
  render the full symmetric polygon set directly. Prefer geometry-level mirroring so
  the raster pass sees a single symmetric polygon (cleaner edges at the axis).

## Open questions
- Is left-right the only symmetry, or is vertical stacking symmetry ever needed?
- For odd features straddling the axis (a single centered line), confirm the axis
  passes through the feature center, not its edge.
