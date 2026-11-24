# Landscape And Foliage Material Domain

## Landscape

Landscape materials care about:

- layer blending
- weightmaps and RVT
- distance-based detail
- macro / micro tiling
- world-aligned direction
- performance under huge screen coverage

Key risks:

- too many texture samples per layer
- expensive blends across many painted layers
- poor RVT strategy
- overusing height blends everywhere

## Foliage

Foliage materials care about:

- masked cost
- wind / WPO
- subsurface or two-sided foliage behavior
- diffuse/alpha leaf-card texture quality
- billboards / LOD transitions
- per-instance variation

Key risks:

- heavy masked overdraw
- fake structural matches that use a solid plane instead of a real leaf/bush card
- too much vertex displacement on large foliage counts
- dynamic complexity that does not scale with view distance

## Leaf Card Asset Standard

When a foliage reference depends on real leaf cards, require a diffuse/alpha asset or separate albedo plus opacity mask before accepting visual equivalence.

- Search the reusable library with `--category foliage` first.
- If no approved asset fits, generate with `cm-imagegen`; use the user's plant/reference image when available.
- Prefer power-of-two sizes such as `512x512`, `1024x1024`, or `2048x2048`.
- Require clean cutout alpha, alpha-friendly RGB edge bleed, no baked ground/shadow, and no watermarks/text.
- QA with `texture_asset_report.py --role foliage`, then audit UE import settings after import.
- Preview on a two-sided masked card or small leaf-card cluster; a standalone PNG preview is not enough.

## Recommended Runtime Controls

- MPC for wind direction and season/global tint
- per-instance random for hue, dryness, variation
- MI defaults for species-level tuning

## Review Questions

- Is the material paying for detail that the camera never sees?
- Is RVT or baked mask data doing work that the graph should not recompute?
- Are foliage wind and color variation split correctly between author-time and runtime?
- Are masked edges stable in motion and mip transitions?
