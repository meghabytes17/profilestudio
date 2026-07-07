# 00 — Requirements

## Purpose
Generate symmetric semiconductor cross-section profiles from user input and render
them to `.bmp`, for use as "incoming" profiles in process-flow work.

## Functional requirements
| ID  | Requirement | Notes |
|-----|-------------|-------|
| F1  | GUI for user input | File picker, parameter fields, live/preview render, save button |
| F2  | Load CSV of heights + widths | DONE. Format in `01-csv-input-format.md` |
| F3  | Parametric input | Material thickness(es), structure pitch, CD, sidewall angle, etc. |
| F4  | Output `.bmp` | DONE. Format in `04-output-bmp-spec.md` |
| F5  | Profile always symmetric | DONE (trace mode). Convention in `05-...` |
| F6  | Catalog of common profiles | Enumerated in `03-profile-catalog.md` |
| F7  | Round-trip a known case | DONE. Byte-exact golden test passes |

## Non-functional / open questions
- Units: nm? µm? Pixel-per-unit scale factor? (see doc 02)
- Multi-material coloring: fixed palette vs. user-assigned per layer/material?
- Anti-aliasing: BMP is uncompressed raster — do we want AA edges or hard 1-bit-ish edges?
- Preview parity: must the on-screen preview be pixel-identical to the saved BMP?
- Batch mode: process a folder of CSVs headlessly (CLI) in addition to the GUI?

## Inputs received (all three, thank you)
- `profile_sketcher.py` -> ported into src/, kept verbatim in `reference/`
- `e1s1.csv` -> `sample_inputs/`, drives the format spec + golden test
- example profiles -> `example_profiles/`, drove the catalog in `docs/03`
