# 01 — CSV Input Format

> **DRAFT — to be finalized once `e1s1.csv` is provided.** The real sample will pin
> down column names, units, ordering, and whether a header row is present.

## Working assumption
A CSV describing a stack/profile as a sequence of features, each with a height and width.

Example (illustrative only):
```csv
layer,material,height_nm,width_nm
0,substrate,50,500
1,oxide,20,500
2,poly,80,120
3,nitride_spacer,80,20
```

## Open questions for the real format
- Is it literally two columns (`height,width`) or richer (material, layer index, x-offset)?
- Units — nm, µm, or arbitrary?
- Is `width` a full CD or a half-width (since profiles are symmetric)?
- Does row order imply bottom-to-top stacking, or is there an explicit z/height column?
- Header row present or not?
- How are materials identified (name string, index into a palette, both)?

## Validation rules (to implement)
- Reject non-numeric dimensions.
- Reject negative or zero heights/widths (or define their meaning).
- Warn if widths exceed the structure pitch.
- Confirm the profile can be made symmetric without data loss (see doc 05).
