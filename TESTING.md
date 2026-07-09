# Testing

The engine (`process.py`, `io_csv.py`, `geometry.py`, `parametric.py`, `materials.py`,
`profiles.py`, `renderer.py`) is pure, deterministic geometry, which makes it ideal for
unit tests. The customtkinter GUI is **not** unit-tested — Tk is painful to drive
headless and almost all the real logic lives in the engine.

## Running the tests

One-time, from the repo root, with your virtualenv active:

```bash
pip install -e ".[dev,geometry]"      # pytest, pytest-cov, ruff, mypy + shapely
```

Then:

```bash
pytest                    # run everything (quiet)
pytest -v                 # verbose: one line per test
pytest tests/test_process.py            # a single file
pytest -k taper                         # tests whose name matches "taper"
pytest --cov=incoming_profile_utility   # with a coverage summary
```

On Windows the same commands work once `.venv\Scripts\activate` is run.

## Layout

```
tests/
  test_smoke.py       package imports + CLI stub run
  test_golden.py      byte-exact CSV->BMP render vs tests/golden/
  test_materials.py   palette lookups + material/vacuum composition
  test_parametric.py  legacy parametric builders (bow / widths)
  test_process.py     process-op engine + mask shapes
  test_regression.py  one test per bug we've fixed (see below)
  golden/             reference images for the golden test
```

## The three kinds of test we rely on

1. **Golden tests** — render a known input and assert the bytes match a stored
   reference (`test_golden.py`). These lock rendering against accidental drift. If you
   intentionally change rendering, regenerate the reference and eyeball the diff.
2. **Property tests** — assert invariants instead of exact pixels: left/right symmetry,
   opening width equals `space`, layers tile with no gap, a taper is monotonic, an
   isotropic etch undercuts laterally. These survive intentional tweaks better than
   goldens.
3. **Regression tests** (`test_regression.py`) — **every bug becomes a permanent test.**
   This is the highest-value habit in the project: when something breaks, first write a
   test that reproduces it, then fix it. The file already covers the opening-width
   doubling, reversed layer order, opening depth, deposit-on-blank, top-surface
   deposition, selective etch, isotropic undercut, the taper angle convention, the
   "side location conflict" from bottom rounding, CSV NaN/negative handling, the CSV
   reference line, and the materials-config write bug.

## Adding a regression test

When you hit a bug, add a test named for the symptom, with a one-line docstring saying
what it locks down:

```python
def test_thing_that_broke():
    """Short description of the bug this prevents from returning."""
    st = build_base(dict(material_layers=[dict(material="silicon", thickness=60)],
                         pitch=120, space=40, top_vacuum=10))
    ...
    assert <the property that should hold>
```

Prefer asserting **geometry** (areas, bounds, region membership) over pixels where you
can — it's clearer and less brittle. Use `build_base(...)` / `evaluate(base, ops)` to
construct a `State`, and `st.regions` (a list of `(material, shapely_polygon)`) to
inspect the result. For pixel-level checks, render with
`render_regions(st, palette, out_path, nm_per_px)` and read the BMP with OpenCV.

## Coverage

```bash
pytest --cov=incoming_profile_utility            # summary in the terminal
pytest --cov=incoming_profile_utility --cov-report=html   # htmlcov/index.html
```

`gui.py` and `main.py` are excluded from coverage (see `pyproject.toml`).

## Linting / typing (optional but declared)

```bash
ruff check src tests      # style / lint
mypy src                  # static types
```

## Continuous integration

`.github/workflows/tests.yml` runs the suite (with coverage) on every push and pull
request, on Python 3.10 and 3.12. Ruff runs in advisory mode for now — once the tree is
clean, remove `continue-on-error` to make lint failures block.
