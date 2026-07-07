# Incoming Profile Utility

A desktop utility for generating **symmetric semiconductor cross-section profiles**
from user input (a CSV of heights/widths, or parametric dimensions such as material
thicknesses and structure pitch) and rendering them to a **`.bmp`** image.

Intended to cover the range of profiles common to semiconductor process flows:
film stacks, line/space gratings, trenches, fins, gate stacks, conformal spacers,
vias/contacts, tapered sidewalls, and multi-material combinations of these.

> **Status:** foundation working. The CSV -> symmetric polygon -> `.bmp` pipeline is
> implemented and reproduces the reference `e1s1_test.bmp` **byte-for-byte** (see the
> golden test). Parametric profile builders and the GUI refactor are next. Specs in `docs/`.

## Requirements (functional)

- [ ] GUI for user input (file picker + parameter fields + preview)
- [x] Load a CSV of heights and widths (e.g. `sample_inputs/e1s1.csv`)
- [ ] Parametric input: material thicknesses, structure pitch, etc.
- [x] Generated profile is **always symmetric** about the vertical axis
- [x] Output is a `.bmp` file (e.g. `e1s1_test.bmp`)
- [ ] Supports a catalog of common semiconductor profiles

## Project layout

```
incoming-profile-utility/
├── docs/                         # Finalized specs: CSV format, coordinates, catalog, BMP, symmetry
├── reference/                    # Original profile_sketcher.py (kept for provenance)
├── example_profiles/             # Reference figures that define the catalog
├── src/incoming_profile_utility/
│   ├── main.py                   # CLI + GUI entry point
│   ├── gui.py                    # GUI (customtkinter) -- refactor pending
│   ├── io_csv.py                 # CSV (width/height trace) loading + validation
│   ├── geometry.py               # Scale, dims, trace -> symmetric polygons
│   ├── profiles.py               # render_trace_csv() + parametric builders (TODO)
│   └── renderer.py               # Rasterize polygons -> .bmp (OpenCV)
├── sample_inputs/e1s1.csv        # Canonical example input
├── tests/                        # Smoke + golden-image tests
│   └── golden/e1s1_test.bmp      # Byte-exact reference render
└── outputs/                      # Generated .bmp files (gitignored)
```

## Getting started

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# Render the sample profile from the CLI (auto scale):
PYTHONPATH=src python -m incoming_profile_utility.main \
    --csv sample_inputs/e1s1.csv --out outputs/e1s1_test.bmp

# Run tests (includes the byte-exact golden check):
PYTHONPATH=src pytest -q
```

## Key design decisions (open)

- **GUI:** keep **customtkinter** (already built in `reference/`); refactor + add parameter controls.
- **Rendering:** keep **OpenCV** fill/BMP write — it reproduces the reference exactly.
- **Parametric geometry:** add **shapely** for tapered/re-entrant/scalloped walls,
  footing/notching, corner rounding, and conformal films (polygon offsetting).
- **Units & scale:** nm, with an auto `nm/px` heuristic — see `docs/02-...`.

See `docs/00-requirements.md` for the full requirements breakdown.
