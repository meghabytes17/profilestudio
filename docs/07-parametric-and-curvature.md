# 07 — Parametric Profiles & Curvature

Users shouldn't have to trace SEMs. Instead they **describe** the curvature with a
few numbers and the tool generates a smooth symmetric sidewall.

## Your parameter vocabulary -> geometry
| Your term      | Role in the model |
|----------------|-------------------|
| `linewidth(s)` | feature CD; also `linewidth = pitch - space` |
| `bottom_width` | full width at the base (height 0) -- control point |
| `mid_width`    | full width at mid-height -- control point |
| `top_width`    | full width at the top -- control point |
| `bow`          | the MAXIMUM CD (widest full width on the wall) |
| `bow_height`   | height at which the bow (max CD) occurs; default H/2 |
| `mid_width`    | CD at mid-height, for a gentle curve with no distinct peak |
| `pitch`        | unit-cell width (one line + one space) |
| `space`        | gap width; `pitch = linewidth + space` |
| `mask_height`  | height of the mask block on top (separate material) |

Provide `pitch`, or any two of {`pitch`, `space`, `linewidth`}. Give either
`mid_width` directly or `bow` (then `mid_width = (top+bottom)/2 + bow`).

## The curvature model
The sidewall half-width vs height is built from what you provide:

- **`bow` (max CD) + `bow_height`** -> a smooth bulge whose maximum equals `bow`,
  located at `bow_height`. Two parabolas meet with zero slope at the apex, so the
  peak sits exactly at `(bow_height, bow)` and the walls curve into it. `bow_height`
  is free -- the widest point can be low, mid, or high (see demo). Constraint:
  `bow >= max(bottom_width, top_width)` (it is the maximum). The demo below moves a
  fixed max CD from low to high:

![bow-location demo](curvature_demo.png)

- **`mid_width`** (no bow) -> parabola through bottom / mid / top: a gentle curved
  wall, and the way to express a waist/pinch (mid narrower than the ends).
- **neither** -> straight linear taper. `bottom_width > top_width` gives a
  re-entrant / undercut wall.

Verified in tests: max CD equals `bow`, the widest point lands at `bow_height`, and
the peak migrates as `bow_height` changes.

## Beyond three points (later)
Three control points cover taper, bow, waist, and re-entrant walls -- the common
cases. For S-shaped walls, scalloping (Bosch), or footing/notching, we extend the
same builder with either extra control points or a periodic/localized term added to
`x(height)`. Corner rounding and conformal films come in via polygon offsetting
(shapely). Mask stays a separate rectangular material on top.

## API
`incoming_profile_utility.parametric.render_line(params, out_path, nm_per_px=0.4)`
builds the symmetric polygons and writes a multi-material `.bmp` via the shared
renderer (`render_layers`).
