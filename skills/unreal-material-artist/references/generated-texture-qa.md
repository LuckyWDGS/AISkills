# Generated Texture QA And Image Generation Tactics

## Use This When

- A material needs `cm-imagegen` output, texture references, masks, atlases, flipbooks, rune sheets, noise, or sprite art.
- You need to decide whether AI output is only a draft or can become a runtime texture.
- A generated texture must be checked before UE import.

## Table Of Contents

- [Image Generation Strategy](#image-generation-strategy)
- [Reference-Driven Generation Gate](#reference-driven-generation-gate)
- [cm-imagegen Tactics](#cm-imagegen-tactics)
- [What AI Should Not Be Trusted To Finalize](#what-ai-should-not-be-trusted-to-finalize)
- [Generated Texture QA Checklist](#generated-texture-qa-checklist)
- [UE Import Notes](#ue-import-notes)
- [Acceptance Language](#acceptance-language)

Related lifecycle step: after generation QA, use [material-asset-library.md](material-asset-library.md) for candidate registration, promotion, or rejection.

## Image Generation Strategy

Start from the material contract and the target look, not from a pretty prompt or a cheap stock substitute.

Define:

- carrier: sprite, ribbon, mesh, decal, UI, surface, post process
- texture role: sprite, mask, flipbook, atlas, ramp, noise, flow, normal, packed channels
- runtime use: alpha, emissive shape, UV distortion, color ramp, random variant, SubUV animation, surface detail
- target platform and budget after the target look is understood
- desired import settings
- whether a reference image or approved concept must anchor the generation

If a design/reference image exists, use it as an image reference through `cm-imagegen`. Do not regenerate from text alone unless the user explicitly wants independent exploration.

Before generating, search the reusable material asset library. If an `approved` asset already fits the need closely enough, reuse it instead of generating a new one. For custom/reference-driven materials, "fits" means it matches the visual reference and the technical role, not just the category name.

When reproducing an online material case, missing textures are a production input gap, not a reason to stop at a constant-color placeholder. Use `cm-imagegen` by default after the library search fails, then record the output as `candidates` or `rejected` instead of promoting it straight to stock.

Do not let texture size or stock availability decide the look before the look is proven. Generate or build the texture that matches the reference first, preferably at a safe power-of-two working size. After preview, downsize, repack, compress, or make LOD/fallback variants only if the important silhouette, edge quality, pattern language, and motion still survive.

## Reference-Driven Generation Gate

For custom materials, the reference image is the art direction contract. Do this before accepting either a library asset or a generated texture:

1. Write a compact reference read: style, palette/value, pattern language, scale, surface type, motion intent, edge/alpha behavior, and carrier.
2. Decide which parts are visual identity and which parts are technical helpers.
3. Search the library for each texture role.
4. Reuse only assets that pass the reference read; mark generic matches as helper-only or reject them.
5. If the library cannot match the visual identity, call `cm-imagegen` with the reference image or a focused crop.
6. QA the generated result against both the reference and the file/UE import rules.
7. Regenerate or refine when the result is structurally usable but visually off-style.

Example: for a custom water material, a stock ripple height can be reused as subtle normal breakup only if it does not dominate the look. If the reference shows painterly cyan foam streaks, stylized cel bands, dark choppy ocean, shallow caustic sand water, or oily alien liquid, generate or build the visible foam/caustic/color/mask assets from that reference instead of using a generic ripple as the final look.

## cm-imagegen Tactics

For stronger generated material assets:

- Generate one texture role at a time. Do not ask for a fire flipbook, smoke mask, sparks, and flow map in one image.
- Use stable canvas requirements: `1024x1024`, `2048x2048`, `4x4 grid`, `8x8 grid`, centered cells.
- Prefer power-of-two output sizes whenever possible: `256`, `512`, `1024`, `2048`. Avoid odd sizes like `1000x1000` for runtime textures unless there is a specific reason.
- For dissolve/noise masks, ask for a grayscale tileable data-like texture, no directional lighting, no vignette, no unique center landmark, and no RGB color variation if the material samples it as a mask.
- For sprite masks, ask for black background or transparent background, centered subject, high contrast, clean alpha-friendly edges.
- For fire masks, decide whether the material consumes alpha or luminance. A black-background fire tongue can work for additive prototypes through the `R` channel, but production sprite cards usually need real alpha or a normalized flipbook/atlas.
- For water ripple/flow/normal sources, treat AI output as draft shape only. Height-style grayscale can seed a prototype, but final normals, flow maps, or vector displacement need DCC/script validation before approval.
- For atlases, require consistent scale, centered content per cell, no border, no text, no watermark, no lighting change between cells.
- For flipbooks, require fixed camera, same subject scale, same center point, smooth temporal evolution, no cropping, no sudden frame jumps.
- For seamless textures, explicitly ask for tileable, no directional lighting, no vignette, no unique center landmark.
- Generate 2-4 variants, then pick one and refine from that accepted result instead of averaging multiple unrelated outputs.
- Keep prompts technical and short enough to obey. Put hard constraints near the front.

For foliage diffuse/alpha cards:

- Use the reference image as `cm-imagegen` input when the user provides a plant, leaf, bush, or desired species.
- Generate a flat card texture, not a beauty render: top-down or orthographic leaf cluster, transparent background or clean alpha, no ground plane, no cast shadow, no text, no watermark.
- Prefer `512x512`, `1024x1024`, or `2048x2048` power-of-two output; use rectangular POT only when the card aspect is intentional.
- Require enough RGB bleed beyond the alpha edge to avoid dark mip halos; reject hard black/white fringe around leaves.
- Treat the card carrier as part of QA: the texture must read correctly on a masked two-sided plane/card or small cluster, not only as a standalone PNG.

Bad prompt shape:

```text
beautiful magical fire smoke lightning fantasy texture, high detail, many particles, cinematic
```

Better prompt shape:

```text
4x4 ember sprite atlas, 16 centered ember alpha shapes, consistent scale per cell, high contrast black background, no text, no watermark, for Unreal Niagara additive particles
```

Foliage prompt shape:

```text
single foliage leaf-card diffuse alpha texture, 1024x1024 power-of-two, top-down flat scanned broadleaf cluster, transparent background with clean cutout alpha, natural green albedo, no cast shadow, no ground, no text, no watermark, for Unreal masked TwoSidedFoliage material
```

## What AI Should Not Be Trusted To Finalize

Treat these as drafts unless technically validated:

- flow maps with meaningful RG vector direction
- normal maps
- water ripple normals derived from generated height without checking scale, seams, and derivative artifacts
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
- Foliage diffuse/alpha textures have real cutout alpha; a fully opaque alpha channel is not enough.
- Leaf-card RGB edges are not polluted by black/white background fringes that will halo in mips.
- RGB edge pixels will not create dark halos.
- BaseColor/Albedo, Emissive color, and visible flipbook or sprite RGB should import with sRGB enabled.
- Mask, packed, flow, and normal textures will import with sRGB disabled.
- Compression matches role: Masks for data masks, Normalmap for normals, HDR only if truly needed.
- Placeholder/default textures must obey the same rule as final textures. A mask/packed/ORM slot cannot safely default to an ordinary color sRGB white texture; use or create a role-correct default such as `TC_Masks` with `sRGB=false`.
- Texture is not larger than the visual value justifies.
- Texture downsizing or compression has not destroyed the visual identity that made the material match the reference.
- Generated black-background masks without alpha are acceptable only when the material explicitly samples luminance/R as the mask; otherwise regenerate or extract a real alpha channel before import.
- For reference-driven work, the texture preserves the reference's style, pattern scale, value range, color logic, and edge language; technically valid but visually generic assets are not final.
- Mips will not destroy tiny linework, rune strokes, or thin lightning branches.
- The generated image has no text, watermark, border, hidden frame labels, or UI artifacts.

Run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py path/to/textures --role atlas --grid 4x4 --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py path/to/leaf-card.png --role foliage --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --scan D:/Textures/WingEcho --packed-convention ORM --emit-import-fix-spec --markdown
python D:/Skills/skills/unreal-material-artist/tools/channel_packer.py --r D:/Masks/AO.png@L --g D:/Masks/Roughness.png@L --b D:/Masks/Metallic.png@L --a D:/Masks/Opacity.png@L --markdown
python D:/Skills/skills/unreal-material-artist/tools/flipbook_normalizer.py D:/Flipbook/Frames --grid 8x8 --cell-size 256 --markdown
```

Use `texture_set_pipeline.py` when generated or received files belong together as a material set. It catches mistakes that single-file checks miss, such as BaseColor/Normal/RMA resolution mismatch, wrong packed-channel convention, missing required slots, opacity separated when it could be packed into alpha, and UE import settings that disagree with the slot role.

Use `channel_packer.py` when separate grayscale masks need to become one runtime RGBA data texture.

Use `flipbook_normalizer.py` when generated frames have center drift, uneven padding, inconsistent crop, or need repacking into a clean atlas before UE import.

If a generated texture survives QA and is likely reusable across tasks, register it into the library with `material_asset_library.py register`. If it fails QA, reject or regenerate it rather than quietly keeping it as future stock.

## UE Import Notes

First-pass rules:

- `sRGB` is role-based, not default-off and not "leave it however it imported." Decide it from the texture's final sampled use in the material.
- Must use sRGB on for visible color textures: `BaseColor` / `Albedo`, `Emissive` color, visible flipbook or sprite `RGB`, and other artist-color inputs the player is meant to see as color.
- Must use sRGB off for data, mask, and vector textures: `Normal`, `Roughness` / `Specular` / `Metallic`, `Opacity` / `Alpha Mask`, packed `ORM` / `RMA` / `MRA`, `Noise`, `FlowMap`, scalar ramps, and channels sampled individually as masks.
- Existing textures should be audited by actual sampler role before changing `sRGB`; do not preserve, enable, or disable it blindly across the project.
- Mask/packed sampler slots need mask-compatible placeholder assets too. Do not wire `/Engine/EngineResources/WhiteSquareTexture` or another color/sRGB texture into a `SAMPLERTYPE_Masks` parameter just because it is "only a default"; create a small project-local white mask texture with `TC_Masks` and `sRGB=false`.
- Normal maps use normal map compression and should not be treated as color art.
- If one asset is trying to serve both visible color and independently sampled mask/data roles, treat that as a mixed-use risk and document or repack it instead of assuming one `sRGB` state is universally correct.
- Flipbooks and atlases need correct grid metadata recorded for Niagara or material SubUV usage.
- Niagara/VFX texture asset names should end with `_VFX` so they remain visually separated from surface/PBR texture sets, for example `T_FireFlipbook_VFX`.
- Power-of-two sizes are the safest default for generated runtime textures because they play better with mip generation, streaming, and cross-platform assumptions.
- Large translucent VFX textures need stricter size control than small opaque surface textures because overdraw multiplies the cost.
- AI-generated water height/ripple textures imported as mask/data should use `TC_Masks` or another non-sRGB data compression route. Do not import them as color art just because they are PNGs.

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
