# 02 — Coordinate System & Units

## Physical vs. pixel space
Two distinct spaces, connected by a single **scale factor** `s` (pixels per nm):

- **Physical space:** real dimensions in nm (or µm), y-up (0 at substrate bottom).
- **Pixel space:** image raster, y-**down** (row 0 at top), origin top-left.

`pixel_x = round((x_phys - x_min) * s)`
`pixel_y = round((y_max - y_phys) * s)`   ← note the flip for y-down

Keeping all geometry in physical units until the final raster pass avoids
accumulated rounding error and makes symmetry exact.

## Origin & symmetry axis
- Physical origin at the **center** of the unit cell so the symmetry axis is `x = 0`.
- The renderable window spans `x ∈ [-pitch/2, +pitch/2]` (one unit cell) unless a
  multi-cell view is requested.

## Open questions
- Default units: nm assumed. Confirm.
- Default scale `s`: fixed (e.g. 1 px/nm) or auto-fit to a target image size?
- Do we render exactly one unit cell, N cells, or auto-pad?
- Substrate: drawn to the image bottom edge, or a fixed thickness?
