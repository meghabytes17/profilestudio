# 01 — CSV Input Format (finalized against e1s1.csv)

## Format
Two numeric columns, header row required. Column names matched **case-insensitively**:

| Column   | Meaning                                             | Units |
|----------|-----------------------------------------------------|-------|
| `Width`  | **Full** feature width (CD) at that height          | nm    |
| `Height` | Height above the feature bottom                     | nm    |

- Each row is a sample of the profile's full width at a given height — a
  width-vs-height **trace** (a measured or designed sidewall contour).
- `e1s1.csv`: 1000 rows, width 0 -> 25.87 nm, height 0.12 -> 239.68 nm
  (~0.24 nm height step). Width is 0 near the bottom (closed/pointed base),
  rises through a curved region, then holds at max width (vertical upper wall).
- Width is centered at render time, so the trace describes **one full width**,
  not a half-width (see docs/05).

## Validation (implemented in io_csv.load_trace)
- Require `width` and `height` columns; else raise.
- Coerce to numeric (raise on non-numeric).
- Reject negative values.
- (Future) warn if a width exceeds a supplied structure pitch.
