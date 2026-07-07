# 02 — Coordinate System, Units & Scale (finalized)

## Units
Physical dimensions are **nanometers**. A single scale factor `nm_per_px` maps nm -> pixels.

## Auto scale
`auto_nm_per_pixel = round( sqrt(max_width * height_span / 100000), 2 )`
— targets a raster of ~100k px area. For `e1s1.csv` this yields **0.25 nm/px**
(-> 104 x 959 px). The value is user-editable in the GUI.

## Canvas dims
`width_px  = ceil(max_width  / nm_per_px)`
`height_px = ceil(height_span / nm_per_px)`  (height_span = peak-to-peak of Height)

## Axes & symmetry
- Raster is **y-down** (row 0 = top). Physical height is converted via
  `y_px = (max_height - height) / nm_per_px`.
- Each width is centered within `max_width`, so the vertical center line is the
  mirror axis (docs/05). Left edge at `(max_w - w)/2`, right edge at `max_w - (max_w - w)/2`.
