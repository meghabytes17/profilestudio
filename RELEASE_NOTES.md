# Profile Studio — Release Notes

SandBox Semiconductor · Incoming Profile Utility

Profile Studio builds symmetric semiconductor cross-section profiles and renders them to
24-bit `.bmp`. It runs entirely on the local Windows machine — no server, no network, no
account.

The running version is shown in the **header pill** (top-right), the **title bar**, and the
**status line** at the bottom of the window. The built `.exe` carries it too: right-click →
Properties → Details. Please quote it when reporting an issue.

---

## 1.1.0 — 2026-07-24

**Branding**

- The application and the executable are now **Profile Studio** (`ProfileStudio.exe`; formerly
  `IncomingProfileUtility.exe`). Custom materials saved by earlier versions are migrated
  automatically the first time you run it.
- The real **SandBox Semiconductor logo** now appears in the application header, replacing the
  previous text treatment.
- The version is shown in the header, the title bar and the status line.

**Materials**

- **Change a material's colour at any time** — click its swatch on a layer row or in the
  preview legend. The change applies everywhere that material is used and persists between
  sessions. Shipped materials have a *Reset to default*.
- **Assign colours by hex code** (`#4FD093`, `4fd093`, or short `#4d9`) when creating a
  material or recolouring one, with a live preview swatch. The colour picker is still there.

**Fixes**

- Fields on process-stack and material rows no longer run off the edge of the panel at Windows
  125% / 150% display scaling.
- Corner treatments (round / chamfer / facet) larger than the layer they sit on are clamped to
  that layer, so they ease into the wall instead of leaving a visible step in the opening.
- Zoom now fills the plot area in both directions instead of leaving letterbox bands, so
  zooming no longer feels horizontal-only.

**Security and delivery hardening**

- Preview renders are no longer left behind in the shared temp directory. Each session uses a
  private scratch folder that is deleted on exit, including after a crash.
- Error messages are generic and no longer print absolute filesystem paths on screen; the
  detail is available on hover.
- Dependencies are pinned for reproducible builds, with a one-command hash-pinning process for
  supply-chain integrity (`tools\make_lock.bat`).

See `SECURITY.md` for the full review.

---

## 1.0.0 — 2026-07-17

First packaged release. Feature overview below.

### Building a profile

**Material stack** — define the film stack top-to-bottom; each layer is a material plus a
thickness in nm. Reorder by drag or with the arrow buttons. Pick from the supplied palette
(silicon, oxide, nitride, hardmask, tungsten, SiGe, photoresist and more) or add your own.

**Base feature** — set pitch, opening width ("space"), opening depth, bottom rounding and top
vacuum. The opening is always **symmetric**.

**Opening from CSV** — instead of a rectangular opening, load a measured or simulated profile
as a width/height trace. The trace defines the opening and overrides the width field.

**Per-layer shape treatments** — shape the opening layer by layer. Treatments stack and are
order-independent:

| Treatment | Parameter | Effect |
|---|---|---|
| Round | radius | Fillets the top corner (quarter-circle) |
| Chamfer | size | Straight 45° clip of the top corner |
| Facet | angle + depth | The same straight cut at any angle (a 45° facet *is* a chamfer) |
| Taper | angle | Slopes the whole layer wall (90° = vertical) |

**Process stack** — apply steps in order, each acting on the result above it:

- **Deposit · conformal** — even coating over all surfaces (liners)
- **Deposit · planar** — flat layer over the top
- **Fill** — fills the opening; the value is an *overfill* (0 = flush with the surface, higher
  = blanket overburden)
- **Etch · isotropic / anisotropic** — remove material; anisotropy 1 = fully vertical, 0 =
  fully isotropic (rounds corners, undercuts). Target one material or "(any)"
- **Planarize** — cut everything flat at a height (CMP)
- **Repeat block** — repeat a group of steps for multilayers and superlattices

### Working in the preview

- Updates **live** as you edit; no render button.
- **Zoom** with the wheel or slider; **Move** to pan when zoomed (drag or arrow keys);
  double-click or *Reset* to return to the full view.
- **Measure** — drag a line across any feature to read it in nm, at any zoom. **Snap** to Edge
  or Vertex locks the endpoints onto material boundaries so a slightly-off click still gives
  the true dimension.
- The plot grid keeps a **fixed size** as you edit; only the axis numbers change.
- **Smoothing** (Off / 2× / 4× / 8×) de-jags curved walls.

### Output

- **Save .bmp** — 24-bit bitmap at full resolution. The image contains **exactly one colour per
  material**: smoothing never blends colours and no pixel is ever shared between two materials,
  so the output can be used directly for downstream analysis.
- **Polygons…** — export the profile as editable vector shapes (`.svg`) plus exact per-material
  coordinates in nm (`.json`).
- **Save / Open** project files to store the whole setup; Undo/Redo throughout.

### Environment

- Windows desktop application, distributed as a single `.exe` with no installer and no
  runtime prerequisites.
- Fits any screen at any Windows display scaling; the window is resizable and the preview
  grows with it.
- Custom materials are stored per-user and persist across sessions and upgrades.

---

## Versioning

`MAJOR.MINOR.PATCH` — MAJOR for changes that break existing project files, MINOR for new
features, PATCH for fixes. See `RELEASING.md` for how a release is cut.
