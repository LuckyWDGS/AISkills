# Generated Texture QA And Image Generation Tactics

## Use This When

- A material needs `cm-imagegen` output, texture references, masks, atlases, flipbooks, rune sheets, noise, or sprite art.
- You need to decide whether AI output is only a draft or can become a runtime texture.
- A generated texture must be checked before UE import.

## Image Generation Strategy

Start from the material contract, not from a pretty prompt.

Define:

- carrier: sprite, ribbon, mesh, decal, UI, surface, post process
- texture role: sprite, mask, flipbook, atlas, ramp, noise, flow, normal, packed channels
- runtime use: alpha, emissive shape, UV distortion, color ramp, random variant, SubUV animation, surface detail
- target platform and budget
- desired import settings
- whether a reference image or approved concept must anchor the generation

If a design/reference image exists, use it as an image reference through `cm-imagegen`. Do not regenerate from text alone unless the user explicitly wants independent exploration.

Before generating, search the reusable material asset library. If an `approved` asset already fits the need closely enough, reuse it instead of generating a new one.

## cm-imagegen Tactics

For stronger generated material assets:

- Generate one texture role at a time. Do not ask for a fire flipbook, smoke mask, sparks, and flow map in one image.
- Use stable canvas requirements: `1024x1024`, `2048x2048`, `4x4 grid`, `8x8 grid`, centered cells.
- Prefer power-of-two output sizes whenever possible: `256`, `512`, `1024`, `2048`. Avoid odd sizes like `1000x1000` for runtime textures unless there is a specific reason.
- For sprite masks, ask for black background or transparent background, centered subject, high contrast, clean alpha-friendly edges.
- For atlases, require consistent scale, centered content per cell, no border, no text, no watermark, no lighting change between cells.
- For flipbooks, require fixed camera, same subject scale, same center point, smooth temporal evolution, no cropping, no sudden frame jumps.
- For seamless textures, explicitly ask for tileable, no directional lighting, no vignette, no unique center landmark.
- Generate 2-4 variants, then pick one and refine from that accepted result instead of averaging multiple unrelated outputs.
- Keep prompts technical and short enough to obey. Put hard constraints near the front.

Bad prompt shape:

```text
beautiful magical fire smoke lightning fantasy texture, high detail, many particles, cinematic
```

Better prompt shape:

```text
4x4 ember sprite atlas, 16 centered ember alpha shapes, consistent scale per cell, high contrast black background, no text, no watermark, for Unreal Niagara additive particles
```

## What AI Should Not Be Trusted To Finalize

Treat these as drafts unless technically validated:

- flow maps with meaningful RG vector direction
- normal maps
- packed masks with exact channel semantics
- signed distance fields
- LUTs or ramps that need exact numeric response
- flipbooks that must conserve volume or loop perfectly

Use AI for concept shape and art direction, then validate or rebuild the technical channels with DCC, scripts, Substance, Houdini, or UE baking.

## Generated Texture QA Checklist

Before importing to UE:

- File dimensions are power of two when mips/streaming matter.
- Atlas and flipbook total canvas should preferably also be power-of-two, not just the per-cell frame size.
- Flipbook or atlas dimensions divide evenly by the grid.
- Each cell has consistent subject scale and center.
- Alpha exists or black-background extraction is intentional.
- RGB edge pixels will not create dark halos.
- Mask, packed, flow, and normal textures will import with sRGB disabled.
- Compression matches role: Masks for data masks, Normalmap for normals, HDR only if truly needed.
- Texture is not larger than the visual value justifies.
- Mips will not destroy tiny linework, rune strokes, or thin lightning branches.
- The generated image has no text, watermark, border, hidden frame labels, or UI artifacts.

Run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py path/to/textures --role atlas --grid 4x4 --markdown
python D:/Skills/skills/unreal-material-artist/tools/channel_packer.py --r D:/Masks/AO.png@L --g D:/Masks/Roughness.png@L --b D:/Masks/Metallic.png@L --a D:/Masks/Opacity.png@L --markdown
python D:/Skills/skills/unreal-material-artist/tools/flipbook_normalizer.py D:/Flipbook/Frames --grid 8x8 --cell-size 256 --markdown
```

Use `channel_packer.py` when separate grayscale masks need to become one runtime RGBA data texture.

Use `flipbook_normalizer.py` when generated frames have center drift, uneven padding, inconsistent crop, or need repacking into a clean atlas before UE import.

If a generated texture survives QA and is likely reusable across tasks, register it into the library with `material_asset_library.py register`. If it fails QA, reject or regenerate it rather than quietly keeping it as future stock.

## UE Import Notes

First-pass rules:

- Color/albedo/emissive art usually uses sRGB on.
- Masks, packed data, flow maps, roughness, metallic, opacity masks, and scalar data usually use sRGB off.
- Normal maps use normal map compression and should not be treated as color art.
- Flipbooks and atlases need correct grid metadata recorded for Niagara or material SubUV usage.
- Power-of-two sizes are the safest default for generated runtime textures because they play better with mip generation, streaming, and cross-platform assumptions.
- Large translucent VFX textures need stricter size control than small opaque surface textures because overdraw multiplies the cost.

## Acceptance Language

A generated texture is accepted only when you can state:

- exact role
- channel meanings
- resolution
- grid if any
- intended import settings
- material parameter or node that will consume it
- known limitations
- whether it is final, draft, or needs technical rebuild

If those cannot be stated, the image is visual inspiration, not a production texture.
