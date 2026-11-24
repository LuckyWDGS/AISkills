# Flipbook playback acceptance

Local atlas QA is static evidence. These procedures verify the actual UE
material/Niagara playback when that integration is requested; they are not
recorded UE test results. Use the [shared result record](../../unreal-engine-mcp/references/shared-conventions.md#runtime-result-record)
and background official MCP first. Keep temporary diagnostic atlases/materials
in the authorized candidate scope, then remove only those test assets.

## ATLAS.Index.Range — ordering, effective frames and playback

- Record atlas size, integer cell size, columns/rows, actual frame count, frame
  order, intended fps/duration and the exact material/Niagara SubImage mapping.
  Distinguish inclusive end index from normalized animation phase and section
  end-exclusive time. Do not copy one field's endpoint convention into another.
- For 144 frames in 16x16, valid indices are 0..143; 144..255 are unused. Clamp
  or map the runtime index to the valid range. Observe first, middle and last
  effective frames and the next update after completion/loop wrap.
- Expect no playback of unused cells, reversed rows, accidental duplicated tail,
  skipped first frame or out-of-range interpolation. Test SubUV blending both
  at integer frames and between frames when enabled; the last-to-first blend
  must match the agreed loop behavior.
- Use a temporary numbered/color-coded cell atlas when index orientation is
  uncertain. Verify the UE shader/renderer actually samples the intended cells;
  a contact sheet alone cannot prove SubUV orientation.

## ATLAS.Padding.Mips — tile boundaries and minification

- Verify final dimensions divide evenly by the grid. Padding expands and centers
  each cell; adding an outer atlas border shifts the sampling grid. Record both
  source and final cell dimensions. Reject excess frames before packing.
- Check UV tile edges with the actual filter/mip/compression settings at near
  and far distance. Look for neighbor-color bleed, dark fringes, clipped wisps
  and loss of small details. Transparent cell padding alone is not guaranteed
  mip isolation; use appropriate gutters/dilation, UV inset or mip policy only
  as required by the carrier/platform and verify the result.
- Default PoT packers reject 12x12/10x10 grids. An exact grid of that size requires
  an explicitly planned raw NPOT route and target-platform validation; do not
  silently stretch it into a PoT review image and call it ready.

## ATLAS.Alpha.Blend — alpha representation and texture roles

- Identify whether source RGB/alpha is straight, premultiplied, black-luma,
  additive-black or separate RGB/mask textures. Match shader math and BlendMode
  to that representation; inspect over dark, mid and bright backgrounds.
- Expect no checkerboard baked into RGB, double multiplication, black/white
  halo or additive mask interpreted as opacity. A transparent PNG container does
  not establish the correct alpha representation.
- Set sRGB by data role: color channels and linear masks/data need appropriate
  import/sampling. Do not apply a blanket sRGB-off rule to every flipbook.
  Record compression/channel packing, alpha preservation and target texture format.

## ATLAS.Motion.Loop — continuity and lifetime

- Run the effect at its intended playback speed, lifespan, size and camera
  distance. Observe transitions between generated/source phases, interpolation,
  final fade and loop boundary. Record runtime index/age or scoped logs when
  available and visual evidence for stepping, scale drift and shape popping.
- A smoke tail that vanishes into an unused cell is not a verified fade; a loop
  needs an intentional seam. Confirm particle lifetime and index mapping agree,
  then check component cleanup through the Niagara lifecycle cases if relevant.
