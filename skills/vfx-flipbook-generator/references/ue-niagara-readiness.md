# UE / Niagara Flipbook Readiness

Use this reference when a generated atlas is expected to be usable directly in Unreal materials, Niagara Sprite/SubUV, or both.

The rule is deliberately stricter than "PNG imports into Unreal":

- the atlas texture imports
- the row/column grid divides the atlas dimensions evenly
- frame order and valid frame range are explicit
- alpha or luminance opacity route is clear
- the material contract matches the opacity and blend mode
- Niagara can bind the material and play the intended frames without guessing

## Source-Backed Baseline

Official Unreal references:

- Epic's material `Flipbook` function uses a texture sheet plus `Number of Rows`, `Number of Columns`, `Animation Phase`, and UVs, then plays the cells in order:
  - `https://dev.epicgames.com/documentation/unreal-engine/misc-material-functions-in-unreal-engine?lang=en-US`
- Epic's Niagara Sprite renderer exposes `Sub Image Size` and `Sub UV Blending Enabled`; SubUV blending interpolates from the fractional part of `SubImageIndex`:
  - `https://dev.epicgames.com/documentation/unreal-engine/render-module-reference-for-niagara-effects-in-unreal-engine?lang=en-US`
- Epic's Niagara smoke/SubUV tutorial sets an `8x8` sheet to `Start Frame = 0` and `End Frame = 63`:
  - `https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-smoke-effect-using-sprite-particles-in-niagara-for-unreal-engine?application_version=5.6`
- Epic's Niagara Flipbook Baker guide recommends power-of-two output and warns that sheet rows/columns should divide the texture dimensions evenly to avoid partial pixels, padding, SubUV offset, and jitter:
  - `https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-flipbook-baker-quick-start-guide-in-unreal-engine?application_version=5.6`
- Epic's material blend mode docs describe `Translucent`, `Additive`, and `AlphaComposite` tradeoffs. Additive is common for fire, steam, and holograms because black contributes no visible color, while `AlphaComposite` can preserve readability on bright backgrounds:
  - `https://dev.epicgames.com/documentation/en-us/unreal-engine/material-blend-modes-in-unreal-engine?application_version=5.6`

## Direct UE / Niagara Conditions

For default direct SubUV use, require:

- Atlas format: importable texture source such as PNG, TGA, EXR, or TIFF.
- Atlas dimensions: power-of-two on both axes by default, especially for production runtime assets.
- Production source size: prefer `2048x2048` or `4096x4096` for final atlas sources when platform memory allows, then downscale variants as needed. Treat `1024x1024` as preview, mobile-only, or explicit low-budget delivery.
- Grid divisibility: `atlas_width % columns == 0` and `atlas_height % rows == 0`.
- Exact cell size: record integer `cell_width` and `cell_height`.
- Frame order: row-major, left-to-right, top-to-bottom, unless the manifest says otherwise.
- Frame range: record `StartFrame = 0` and `EndFrame = frame_count - 1`.
- Empty cells: never let Niagara play unused cells unless the blanks are intentional fade or hold frames.
- Opacity route: one of `true-alpha`, `luma`, `additive`, or an explicit custom route.
- Background policy: no checkerboard preview backgrounds in production atlases.
- Edge safety: no important opacity or luma touches cell borders unless the sheet has enough padding or dilation.
- Texture budget: keep within target platform max texture size and expected memory budget.

`10x10 @ 1024x1024`, `10x10 @ 2048x2048`, and `10x10 @ 4096x4096` are not direct production SubUV outputs under this default contract because the grid does not divide the texture dimensions. Treat them as review/sample sheets, or switch to `8x8`, `16x8`, `16x16`, a non-power-of-two divisible atlas with a documented tradeoff, or a custom material/UV route.

## Material Contract

Material-side handoff should say:

- Texture asset name, usually `T_<Effect>_<Grid>_VFX`.
- Material domain: usually `Surface`.
- Shading model: usually `Unlit` for sprite VFX.
- Blend mode:
  - `Additive` for black-background emissive fire, sparks, steam, hologram, and energy where black should disappear.
  - `Translucent` for true alpha smoke, dust, mist, soft cards, and any effect needing opacity control.
  - `AlphaComposite` when additive-style light must remain readable on bright backgrounds.
- RGB source: visible color, emissive color, grayscale luma, or packed channel.
- Opacity source: alpha channel, luminance from RGB, additive black, or custom channel.
- Required Niagara inputs: `ParticleColor` for tint/alpha, optional `DynamicParameter` for emissive/opacity/playback controls.
- Flipbook route:
  - Material `Flipbook` function if the material owns animation phase.
  - TextureSampleParameter/SubUV material route if Niagara owns frame timing.
- Import guidance:
  - visible RGB/emissive textures generally use sRGB
  - masks/luma/data channels generally use linear/no sRGB
  - compression and texture group should match VFX opacity/color use, not PBR surface defaults

## Niagara Contract

Niagara-side handoff should say:

- Renderer: Sprite Renderer for direct SubUV playback.
- Renderer material: the material using the atlas.
- Renderer `Sub Image Size`: `X = columns`, `Y = rows`.
- `SubUV Animation` module:
  - `Start Frame = 0`
  - `End Frame = frame_count - 1`
  - lifetime/playback mode documented
- `Sub UV Blending Enabled`: recommend on for soft smoke/fire interpolation, off or tested for hard-edged random sprites.
- Particle lifetime: enough time to play the intended frame range at the suggested FPS.
- Blank cell handling: End Frame stops before unused cells.
- Random sheet handling: set/randomize `SubImageIndex` instead of running a full continuous animation.
- Bounds and sorting: define fixed bounds and translucent sorting strategy for dense sprite effects.

## Common Flipbook Uses

Continuous flipbooks:

- smoke plume, curl, and fade
- falling dust, powder, mist, and ceiling dust
- flame bodies, torch fire, magic fire, and plasma tongues
- explosions, fireballs, shock puffs, and expanding blast clouds
- water splashes, foam bursts, spray cards, and whitewater support
- blood impact clouds, poison/toxic puffs, and stylized goo bursts
- magical impacts, portal cores, energy wisps, lightning/arc pulses when the shape evolution matters
- holograms, animated decals/cards, UI or mesh material loops when a baked texture animation is cheaper than live logic
- baked Niagara Fluids or other expensive simulations for runtime playback

Randomizable sprite sheets:

- embers, spark flecks, star glints, dust motes, ash, debris chips
- muzzle flash variants and small burst cards
- slash glints or impact spark shapes when each cell is an independent variation
- support particles layered around a continuous hero flipbook

Mixed effects often need both:

- explosion: hero blast flipbook plus random embers/sparks
- roof dust: falling dust flipbook plus random residue motes
- fire: flame-body flipbook plus random ember pop and smoke supports
- portal: continuous core/ring flipbook plus random sparks and shard cards

## Missing-Item Checklist

Before calling an atlas final for Unreal, produce or verify:

- `atlas.png`
- `flipbook-manifest.json`
- `ue-readiness-report.md` from `scripts/ue_flipbook_readiness.py`
- `atlas-catalog.md` / `atlas-catalog.json` from `scripts/flipbook_asset_catalog.py` when a folder contains multiple candidates, preview variants, alpha support outputs, or rejected/raw sources
- row/column grid, frame count, start frame, end frame
- atlas size, raw pre-snap size, exact cell size
- whether the atlas is native high-resolution generation, repacked high-resolution frames, or an upscale derivative
- frame order
- alpha/background policy
- material blend mode recommendation
- Niagara `Sub Image Size`, `SubUV Animation`, and blending recommendation
- playback FPS or intended particle lifetime
- blank-cell policy
- edge/gutter risk
- whether this is `continuous`, `random-sheet`, or `mixed`

## CLI Gate

Run the readiness gate whenever an atlas is intended for UE:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/ue_flipbook_readiness.py D:/path/to/atlas.png --manifest D:/path/to/flipbook-manifest.json --mode both --alpha-policy auto
```

The report statuses mean:

- `ready`: no hard blocker or warning was found by the static checker.
- `conditional`: usable if the documented material/Niagara route accepts the warnings.
- `blocked`: do not call it direct UE/Niagara-ready until the failed checks are repaired or an explicit custom route is documented.

## Candidate Folder Catalog

When several generated outputs exist beside each other, use the catalog tool to make selection and handoff less error-prone:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_asset_catalog.py D:/path/to/atlas-folder --out D:/path/to/atlas-folder/atlas-catalog.md --json-out D:/path/to/atlas-folder/atlas-catalog.json
```

The catalog groups manifest-backed assets, pairs RGB preview atlases with alpha support outputs, imports existing readiness reports, and marks assets as `recommended`, `usable`, `conditional`, `blocked`, or `needs-review`. It also repeats the practical UE defaults that matter most for VFX delivery:

- random sheets should randomize `SubImageIndex` and usually leave `Sub UV Blending` off
- continuous flipbooks should use `SubUV Animation` with explicit start/end frames
- production selection should prefer ready `2048x2048` or `4096x4096` sources over `1024x1024` when memory budget allows
- black luma sheets need Additive or luma-derived opacity
- true-alpha or alpha-support sheets are safer when a Translucent material should remove the black preview background
- ultra-fine constellation/blueprint sheets should be checked at lower mip sizes before shipping on standalone/mobile targets
