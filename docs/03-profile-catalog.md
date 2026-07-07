# 03 — Profile Catalog

The utility should generate the profiles common to semiconductor process flows.
This catalog will be **finalized against your `example profiles` set**; below is a
starting taxonomy with the parameters each builder needs.

## Building blocks
| Profile | Description | Key parameters |
|---------|-------------|----------------|
| Film stack (blanket) | Planar layers, full-width | per-layer thickness, material |
| Line / space grating | Repeating lines | pitch, CD (line width), space, height |
| Trench (STI) | Recess into substrate | pitch, trench width, depth, sidewall angle |
| Fin (FinFET) | Tall narrow feature | fin width, fin height, pitch, SWA |
| Gate stack | Multi-layer line | gate CD, per-layer thickness (ox/poly/cap) |
| Conformal spacer | Film hugging sidewalls | spacer thickness (== polygon offset) |
| Via / contact hole | Hole (in cross-section: a slot) | CD, depth, taper |
| Mandrel / SADP | Self-aligned double patterning | mandrel CD, spacer, resulting pitch/2 |

## Profile modifiers (apply to any of the above)
- **Sidewall angle (SWA):** vertical (90°), tapered (<90°), or reentrant (>90°).
- **Corner rounding:** radius at top/bottom corners.
- **Undercut / notching:** localized width reduction.
- **Conformality:** ideal (uniform offset) vs. thinned on sidewalls/bottom.

## Geometry note
Several of these reduce to one operation: **polygon offsetting** (shapely `.buffer()`).
- Conformal deposition = positive offset of the underlying polygon.
- Etch/recess = negative offset or boolean subtraction.
Building on this keeps the catalog small and composable.

## To fill in from your examples
- Which of the above appear in your `example profiles`, and any not listed here.
- Naming conventions you already use (so the GUI dropdown matches your vocabulary).
- Default/typical parameter values per profile.
