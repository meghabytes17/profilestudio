# 00 — Requirements

## Purpose
Generate symmetric semiconductor cross-section profiles from user input and render
them to `.bmp`, for use as "incoming" profiles in process-flow work.

## Functional requirements
| ID  | Requirement | Notes |
|-----|-------------|-------|
| F1  | GUI for user input | File picker, parameter fields, live/preview render, save button |
| F2  | Load CSV of heights + widths | Format defined in `01-csv-input-format.md` |
| F3  | Parametric input | Material thickness(es), structure pitch, CD, sidewall angle, etc. |
| F4  | Output `.bmp` | Format defined in `04-output-bmp-spec.md` |
| F5  | Profile always symmetric | Convention in `05-symmetry-convention.md` |
| F6  | Catalog of common profiles | Enumerated in `03-profile-catalog.md` |
| F7  | Round-trip a known case | `sample_inputs/e1s1.csv` -> `e1s1_test.bmp` (golden test) |

## Non-functional / open questions
- Units: nm? µm? Pixel-per-unit scale factor? (see doc 02)
- Multi-material coloring: fixed palette vs. user-assigned per layer/material?
- Anti-aliasing: BMP is uncompressed raster — do we want AA edges or hard 1-bit-ish edges?
- Preview parity: must the on-screen preview be pixel-identical to the saved BMP?
- Batch mode: process a folder of CSVs headlessly (CLI) in addition to the GUI?

## Inputs still needed from stakeholder (you)
- `profile_sketcher.py` (initial script) — to reuse conventions/logic, not replace blindly
- `e1s1.csv` — canonical sample input
- The `example profiles` set — to derive the profile catalog and validate output
