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
- billboards / LOD transitions
- per-instance variation

Key risks:

- heavy masked overdraw
- too much vertex displacement on large foliage counts
- dynamic complexity that does not scale with view distance

## Recommended Runtime Controls

- MPC for wind direction and season/global tint
- per-instance random for hue, dryness, variation
- MI defaults for species-level tuning

## Review Questions

- Is the material paying for detail that the camera never sees?
- Is RVT or baked mask data doing work that the graph should not recompute?
- Are foliage wind and color variation split correctly between author-time and runtime?
- Are masked edges stable in motion and mip transitions?
