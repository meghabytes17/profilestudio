# 06 — v1 Target Profiles

Four reference renders the tool must reproduce in v1 (in `tests/golden/v1/`).
Together they define the real v1 scope: **multi-material** profiles with a
material -> color palette, plus three geometry types beyond the single trace.

## Targets
| File | Size (WxH px) | Materials | Demonstrates |
|------|---------------|-----------|--------------|
| `siren.bmp` | 180 x 4775 | ~1 (+ tiny 2nd) | High-aspect trench, essentially the current trace mode scaled up |
| `unicorn_incoming.bmp` | 207 x 4822 | 3 | Feature + fill + a second material (stacked/nested regions) |
| `FETa_v5.bmp` | 42 x 300 | ~5-6 | Planar multi-layer stack (FET-style gate stack) |
| `incoming_imec.bmp` | 422 x 4725 | ~5 | Multi-film stack with conformal-looking layers lining a feature |

## Observed color palette (fill RGB -> material TBD)
Background is black `(0,0,0)` in all four. Material names to be provided (docs asks below).

**siren**
- `(0,162,232)` sky-blue -- 87%  (same fill as e1s1)
- `(185,122,87)` tan -- 3%

**unicorn_incoming**
- `(0,162,232)` sky-blue -- 43%
- `(163,73,164)` purple -- 27%
- `(255,151,223)` pink -- 21%

**FETa_v5**
- `(235,63,20)` orange-red -- 43%
- `(69,163,186)` teal -- 16%
- `(127,127,127)` gray -- 13%
- `(173,219,36)` green -- 4%
- `(0,162,232)` sky-blue -- 2%
- `(163,73,164)` purple -- 2%

**incoming_imec**
- `(255,181,81)` amber -- 58%
- `(40,61,93)` navy -- 14%
- `(202,214,232)` light blue-gray -- 9%
- `(143,141,141)` gray -- 6%
- `(76,11,194)` violet -- 1%

## Scope delta for v1 (vs. current single-color trace)
1. **Material palette:** renderer must map material -> fill color (extends the
   single hard-coded `(232,162,0)` BGR). Same color recurs across profiles
   (e.g. sky-blue), so a shared named palette makes sense.
2. **Planar layer stacks** (FETa): ordered material bands with per-layer thickness.
3. **Conformal films** (imec): layers that follow a feature's walls == polygon
   offset -> confirms shapely for the geometry engine.
4. **Fills / nested regions** (unicorn): a feature outline plus one or more
   interior materials.
5. Draw order / z-stacking (later material paints over earlier) must be defined.

## OPEN — the input format for multi-material (blocks the build)
The current CSV is a single `Width,Height` trace = one material. Options to specify
these multi-material profiles are enumerated in the chat; decision pending.

## Asks to stakeholder
- A name for each color above (material -> palette).
- How each target was originally produced (hand-authored? from per-layer CSVs?
  from a parametric spec?) -- this tells us the natural input format.
