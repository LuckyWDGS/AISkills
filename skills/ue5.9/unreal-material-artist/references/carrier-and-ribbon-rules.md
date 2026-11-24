# Carrier, UV and Ribbon Rules

The canonical carrier rules for material work. `niagara-vfx-artist` points here for
the ribbon UV contract it hands to the material side.

## Table Of Contents

- [Niagara Ribbon UV contract](#niagara-ribbon-uv-contract)
- [Ribbon breakup and silhouette](#ribbon-breakup-and-silhouette)
- [Wrapped mesh carriers](#wrapped-mesh-carriers)
- [Two-sided and additive layering](#two-sided-and-additive-layering)
- [Niagara SubUV sprites](#niagara-subuv-sprites)

## Niagara Ribbon UV contract

Default Niagara ribbon convention:

- Raw `TexCoord0.U` / X = ribbon length; raw `TexCoord0.V` / Y = ribbon width.
- Longitudinal panning, flame travel, noise scroll and length tiling use raw `U`,
  for example `Time * Speed -> Append(X, 0)` and tiling vectors such as `(Tiling_U, 1.0)`.
- Width masks, edge fades, center-core masks and side breakup use raw `V`. `V` offsets
  may add vertical wobble or distortion.
- Do not pan along raw `V` unless live renderer readback proves the carrier maps length
  to `V`, or the material deliberately uses the art-space exception below.

Art-space texture exception:

- If the texture is authored so its vertical sampling axis is the visible trail flow,
  build `Flow_UV = float2(TexCoord0.V, TexCoord0.U)` for texture sampling only.
- Put panning and tiling on `Flow_UV.y`; keep width masks on the original raw `TexCoord0.V`.
- Document the exception in the material comments and handoff. It is not the default.

## Ribbon breakup and silhouette

- Do not multiply a strong independently panned mask into both emissive and opacity:
  the secondary mask then owns a second moving silhouette and reads as two overlaid images.
- Keep silhouette opacity separate from internal emissive breakup. Let the primary mask,
  width fade, particle alpha and tail fade own opacity; let centered secondary noise
  affect emissive/body detail unless the target explicitly needs alpha breakup.
- Center sampled noise before modulating: `CenteredNoise = Noise * 2 - 1`,
  `Modulation = 1 + CenteredNoise * Strength`, then multiply the primary mask by
  `Modulation`. Start `Strength` around `0.1-0.25`; values outside the authored range
  need a new visual review.
- Make secondary moving noise inherit the main distorted ribbon UV before adding a slow
  relative offset. Independent coordinates, distinct tiling and counter-panning are a
  deliberate layer design, reviewed for phase separation, not a default way to add detail.
- When a trail is reported as "two images", first prove the live emitter and renderer
  count and read the renderer shape. `MultiPlaneCount` does not duplicate geometry while
  `Shape=Plane`, and `Two Sided` alone does not prove two surfaces are drawn.
- Approve moving breakup only from at least two time-separated frames on the real
  ribbon carrier (`material_preview.py capture --route viewport --frames 2`), showing a
  coherent silhouette while only internal energy evolves.
- Stable split lines, hard width edges or intersection cuts after the geometry is proven
  stable: [ribbon-trail-seam-debugging.md](ribbon-trail-seam-debugging.md).
- Fire, flame and energy trails: [niagara-ribbon-flame-trail.md](niagara-ribbon-flame-trail.md).

## Wrapped mesh carriers

Cones, cylinders, tubes and mesh light volumes:

- Record UV seam and tiling constraints before tuning noise. If `UV.x` closes at `0/1`,
  horizontal tiling such as `TileU` must be a positive integer unless the graph uses a
  seam-hiding projection; `2.2` renders the seam as a vertical line.
- On low-poly shells, `VertexNormalWS` may be too faceted for Fresnel. A virtual radial
  normal from `LocalPosition.xy` can be tested as an explicit variant; do not make it the
  default or keep it if it changes the intended falloff.
- For strongly tiled, stretched or panned noise, record the mip strategy. When warped
  UVs cause seam shimmer or mip discontinuity, prefer `TextureSample`
  `MipValueMode=Derivative` with `DDX/DDY` from the clean base `TexCoord[0]`, not from the
  multiplied/panned UV.

## Two-sided and additive layering

For `Additive` or `Translucent` materials on two-sided cards, shells, cones, cylinders or
dense particle stacks, record the expected visible layer count. `Two Sided + Additive`
can double or multiply emissive energy: front faces, back faces and overlapping
primitives add before bloom and exposure. Tune emissive and opacity against the real
carrier, not the 2D formula.

## Niagara SubUV sprites

- Default `Two Sided` to off: the sprite renderer is normally camera-facing. Enable it
  only for a documented non-camera-facing mesh/card route.
- Name Niagara/VFX texture assets with a trailing `_VFX` suffix, for example
  `T_FireFlipbook_VFX`.
