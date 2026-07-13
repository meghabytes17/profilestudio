# What's changed since the first .exe

Everything below landed after the PyInstaller packaging work. Testers need a **rebuilt .exe**
(`build_exe.bat`, or the `build-exe` GitHub Action) to see any of it.

Tests grew from 27 to **72**, all passing in CI on Python 3.10 and 3.12.

---

## Correctness — the output bitmap

- **No overlapping materials.** Every pixel is now assigned to exactly one material. The
  renderer rasterizes into a label buffer instead of painting layers over each other.
- **Smoothing no longer invents colours.** It used to average pixels at edges, producing
  muddy in-between shades (the grey/yellow blip in the reported `smooth4x.png`). Smoothing is
  now a majority vote, so the .bmp contains **exactly one colour per material** at every
  smoothing level. This is enforced by tests that fail if it ever regresses.
- **No holes/slivers** when a Round and a Taper treatment are combined on the same layer.

## The process stack

- **Fill actually respects its number.** It's an *overfill*: `0` = flush with the surface,
  higher = blanket overburden above it (clamped to the cell). Previously the value was ignored
  and fill always went to the top.
- **Deposit and Fill can use any material in the palette.** You no longer have to add a liner
  or fill material to the stack at 0 nm just to select it. (Etch still lists what's present,
  plus "(any)".)

## Shape treatments

- **Stacking multiple treatments is now discoverable** — the dialog opens with a row visible,
  says so explicitly, and has a prominent "+ Add another treatment" button. The capability
  existed before but people were missing it.

## The preview

- **Static grid.** The plot box keeps a fixed size; only the axis numbers change as you edit.
  It used to resize with the profile and bounce around.
- **Zoom** (wheel or slider) with **Move** and **Measure** as explicit, mutually exclusive
  tools. The cursor changes to a move cursor over the grid when you can pan.
- **Measure**: drag a line across any feature to read its length in nm, accurate at any zoom.
- **Panning is ~26x faster** (311 ms -> 12 ms per drag event). It was re-running the geometry
  engine on every mouse move; it now re-crops a cached render.
- **Live preview**: the Render button is gone — the preview updates as you edit.
- The nm/px resolution is shown, and all renders are clamped so a large profile can't freeze
  the app.

## Display / DPI

- **The window fits any screen at any Windows display scaling.** At 125%/150% the process-step
  fields could end up off-screen; the window now fits the physical screen, the inputs panel
  scrolls, and the preview controls stay visible on short windows.

## Export

- **Polygons export**: write the finished profile as an editable **SVG** (nudge vertices in
  Inkscape/Illustrator) plus a **JSON** of exact per-material nm coordinates.
- Save .bmp still exports the picture at full resolution.

## Branding

- **App icon** for the window, the taskbar and the .exe: a cross-section with a U-shaped
  trench, in SandBox colours, carrying the logo's circuit-probe motif. The wordmark is not
  recreated, per the brand rules.

## Docs

- Three one-page tutorials (mask profile, CSV, process stack) as editable .docx + PDF, kept in
  step with the app — including a "Working in the preview" section for the tools above.
- `PACKAGING.md` covers building the .exe and clearing the Windows icon cache.

---

## Known follow-ups

- The interactive opening-outline editor was built, tried, and **removed** — dragging control
  points proved fiddly. The CSV opening and the polygon export cover the same ground for now.
- A full per-material vertex editor is still open; it carries real topology/overlap risk and
  would need its own design pass.
