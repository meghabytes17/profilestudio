# Incoming Profile Utility

A desktop utility for generating **symmetric semiconductor cross-section profiles**
from user input (a CSV of heights/widths, or parametric dimensions such as material
thicknesses and structure pitch) and rendering them to a **`.bmp`** image.

Intended to cover the range of profiles common to semiconductor process flows:
film stacks, line/space gratings, trenches, fins, gate stacks, conformal spacers,
vias/contacts, tapered sidewalls, and multi-material combinations of these.

> **Status:** early scaffold. Architecture and module stubs are in place; core logic
> is still to be implemented. See `docs/` for the working specs.

## Requirements (functional)

- [ ] GUI for user input (file picker + parameter fields + preview)
- [ ] Load a CSV of heights and widths (e.g. `sample_inputs/e1s1.csv`)
- [ ] Parametric input: material thicknesses, structure pitch, etc.
- [ ] Generated profile is **always symmetric** about the vertical axis
- [ ] Output is a `.bmp` file (e.g. `e1s1_test.bmp`)
- [ ] Supports a catalog of common semiconductor profiles

## Project layout

```
incoming-profile-utility/
├── docs/                         # Specs: input format, coordinate system, profile catalog, output spec
├── src/incoming_profile_utility/
│   ├── main.py                   # CLI / app entry point
│   ├── gui.py                    # GUI (tkinter by default; PySide6 optional)
│   ├── io_csv.py                 # CSV loading + validation
│   ├── geometry.py               # Primitives, symmetry, conformal offset, coordinate transforms
│   ├── profiles.py               # Profile catalog / builders (stack, grating, trench, fin, ...)
│   └── renderer.py               # Rasterize geometry -> .bmp (Pillow)
├── sample_inputs/                # Example CSV inputs (add e1s1.csv here)
├── tests/                        # Unit + golden-image tests
└── outputs/                      # Generated .bmp files (gitignored)
```

## Getting started

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# Run the app (once implemented)
python -m incoming_profile_utility.main
```

## Key design decisions (open)

- **GUI framework:** tkinter (stdlib, zero-install) vs. PySide6 (richer preview). Default: tkinter.
- **Geometry engine:** raw Pillow drawing vs. shapely polygons then rasterize.
  Recommended: shapely for geometry (conformal deposition == polygon buffering),
  Pillow only for the final raster pass.
- **Units & scale:** how nm map to pixels — see `docs/02-coordinate-system-and-units.md`.

See `docs/00-requirements.md` for the full requirements breakdown.
