# Niagara Ribbon Flame Trail

Use this when the material side of a Niagara ribbon/trail needs a fire, flame, ember, lava, heat, plasma, or energy-flame look with an additive/emissive shader and a packed mask texture.

This is material-side scope only. Niagara owns the live System, Emitter, Renderer, bindings, bounds, culling, and integration proof.

## Table Of Contents

- [Route Contract](#route-contract)
- [Ribbon UV Contract](#ribbon-uv-contract)
- [Packed Mask Convention](#packed-mask-convention)
- [Node Plan](#node-plan)
- [Chinese Artist Parameters](#chinese-artist-parameters)
- [Pre-Evidence Platform Plan](#pre-evidence-platform-plan)
- [MI Handoff Checklist](#mi-handoff-checklist)
- [Validation](#validation)

## Route Contract

Default route:

- `Material Domain`: `Surface`
- `Blend Mode`: `Additive` for glow/fire/energy trails; use `Translucent` only when true alpha compositing or depth relationship matters.
- `Shading Model`: `Unlit`
- `Two Sided`: usually `true` for ribbon readability unless the renderer/carrier proves one-sided is enough. Record the brightness multiplier risk when it is enabled.
- Outputs: drive `EmissiveColor`; wire `Opacity` only when the blend route uses it meaningfully. Do not wire unused lit pins.
- Usage flags: require `Used with Niagara Ribbons`; also set `Beam Trails` if the material is shared with beam/trail renderers.
- Runtime inputs: `ParticleColor.A` for lifetime fade by default; optional `ParticleColor.RGB` for emitter-side tint.

Preferred scaffold command:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_ribbon_additive --effect WingEcho --layer RibbonTrail --folder-path /Game/Materials/VFX --markdown
```

The recipe builds a first-pass packed-mask additive material scaffold with raw U/V split, `Tiling_Length`, optional `Use_Flow_UV_Remap`, Time-driven main/noise panners, B-channel distortion, centered raw-V width falloff, `ParticleColor`, `DynamicParameter.Param1/Param2`, and `EmissiveColor` / `Opacity` outputs. Treat the generated spec as offline graph scaffolding: run live UE pin-name smoke, texture import QA, carrier preview, and Android one-sample fallback review before delivery.

Android / low-tier fallback command:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_ribbon_additive_android --effect WingEcho --layer RibbonTrail --folder-path /Game/Materials/VFX --markdown
```

The fallback recipe keeps the same ribbon UV contract and artist-facing control names where practical, but uses one `Texture_Mask` sample, no secondary noise/distortion sample, and lower brightness defaults. Use it for Android or low-end variants after the full route has established the visual target, or when the task explicitly prioritizes low-tier cost from the start.

`Texture_Mask` defaults to a same-folder `T_FireRibbonMask_VFX` asset reference in the generated builder spec. If the texture is imported elsewhere, edit the spec before `--execute`, then validate the imported texture settings before delivery.

## Ribbon UV Contract

Default Niagara ribbon convention:

- Raw `TexCoord0.U` / X = ribbon length.
- Raw `TexCoord0.V` / Y = ribbon width.
- Longitudinal panning, flame travel, noise scroll, and length tiling use raw `U`.
- Width masks, edge fades, center-core masks, and side breakup use raw `V`.

Art-space texture exception:

- If the texture is authored so its vertical sampling axis is the visible trail flow, explicitly create `Flow_UV = float2(TexCoord0.V, TexCoord0.U)` for texture sampling only.
- Put panning and tiling on `Flow_UV.y`.
- Keep width masks on the original raw `TexCoord0.V`.
- Document this exception in the material comments and handoff. It is not the default ribbon rule.

## Packed Mask Convention

Preferred one-sample flame ribbon mask:

| Channel | Role | Notes |
|---|---|---|
| `R` | core/tongue filament mask | Sharp flame tongues, hot streaks, or same-hue highlight boost. |
| `G` | main flame body / soft band | Broad readable flame band; usually the primary emissive mask. |
| `B` | distortion / breakup / slow noise | Distort `G`/`R`, soften width edge, or drive secondary long-period wobble. |
| `A` | optional opacity/fade/detail | Use only when the asset actually needs a fourth channel. |

Import contract:

- Texture role: mask or packed data.
- `sRGB=false`.
- Mask/data compression such as `TC_Masks` where appropriate.
- Power-of-two dimensions when practical so mips and streaming are available.
- Avoid high-frequency one-pixel filaments for Android; they shimmer and mip poorly.

## Node Plan

Minimum readable route:

1. Read `TexCoord0` and split raw `U/V`.
2. Build width falloff from raw `V`, for example center bright core plus soft side fade.
3. Build sampling UV:
   - default: `Flow_UV = TexCoord0`
   - art-space exception: `Flow_UV = float2(V, U)`
4. Pan main and noise UVs with `Time * Speed_Main` / `Time * Speed_Noise`.
5. Sample the packed mask once for slow B-channel breakup/distortion.
6. Use `B` to offset or perturb the main sample lightly; clamp distortion so the ribbon does not swim across its width.
7. Sample the packed mask again on the distorted main UV for R/G color masks.
8. Combine `G` body + `R` core/filament + optional ember edge.
9. Multiply by `Color_Main`, `Color_Core`, `Intensity`, width falloff, and `ParticleColor.A`.
10. Output to `EmissiveColor` and wire opacity when the Additive route uses it for fade/softness.

Avoid:

- Refraction, scene depth, or expensive depth reads unless the visual target requires heat haze and the platform allows it.
- Multiple high-res samples before the one-sample packed route has been previewed.
- Width panning that makes the flame crawl sideways.
- Unbounded HDR intensity that only looks good on black backgrounds.

## Android One-Sample Fallback

Use `fire_ribbon_additive_android` when Android, low-tier, or heavy overdraw makes the full dual-sample distortion route too expensive.

Fallback graph differences:

- One `Texture_Mask` sample only.
- Keep raw `TexCoord0.U` for length flow and raw `TexCoord0.V` for width falloff.
- Keep optional `Use_Flow_UV_Remap` for art-space textures; it costs graph math, not another sample.
- Omit secondary B-channel noise panner and UV distortion.
- Lower defaults: `Intensity=1.5`, `Core_Boost=1.5`, `OpacityScale=0.85`, `Tiling_Length=2.0`.
- Prefer `256x128` or `512x256` packed mask size before shipping to Android.

Do not call the fallback equivalent to the deep route. It is a platform variant: compare it on the intended carrier/background, then record the visible losses such as less breakup, less internal motion, or flatter flame edges.

## Chinese Artist Parameters

Use English binding names for MI/Niagara/Blueprint compatibility and Chinese descriptions for artist-facing controls.

| Binding | 中文说明 | Default PC | Android fallback | Range | Owner |
|---|---|---:|---:|---|---|
| `Texture_Mask` | 三通道火焰遮罩。R=火舌/亮丝，G=主火带，B=扰动/破碎噪声。 | required | required | texture | artist |
| `Speed_Main` | 主火带沿 Ribbon 长度方向的滚动速度。 | `1.5` | `0.8` | `0-4` | artist |
| `Speed_Noise` | B 通道扰动的慢速滚动速度。 | `0.15` | `0.08` | `0-1` | artist |
| `Tiling_Length` | 沿 Ribbon 长度方向的平铺次数。 | `3.0` | `2.0` | `0.25-8` | artist |
| `Width_Power` | 宽度衰减曲线，越大中心越窄。 | `1.4` | `1.2` | `0.5-4` | artist |
| `Distortion_Intensity` | B 通道对火带的扰动强度。 | `0.06` | `0.02` | `0-0.15` | artist |
| `Core_Boost` | R 通道亮丝对核心高光的增强。 | `3.0` | `1.5` | `0-8` | artist |
| `Intensity` | 整体发光强度。先在灰底和亮底预览，再交付。 | `4.0` | `1.5` | `0-10` | artist |
| `Color_Main` | 主火带颜色。 | orange | orange | color | artist |
| `Color_Core` | 核心高光颜色。 | white-gold | warm yellow | color | artist |
| `OpacityScale` | Niagara 或 MI 控制的整体淡出倍率。 | `1.0` | `0.75` | `0-1` | Niagara/MI |

## Pre-Evidence Platform Plan

Use this before audit evidence exists, then replace it with measured data.

PC first-pass target:

- 1-3 texture samples.
- One packed mask texture at 512-1024 for ordinary trails, 2048 only for hero close-ups.
- Additive/unlit, no refraction by default.
- Keep screen coverage and particle/ribbon count in the contract.

Android first-pass target:

- 0-2 samples, ideally one packed mask.
- 256-512 texture for common gameplay trails unless close-up proof needs more.
- Shorter lifetime, lower opacity/intensity, simpler distortion, fewer overlapping ribbons.
- Prefer `QualitySwitch` / tiered MI values instead of adding static switch combinations.
- Test on black, neutral, bright, and busy backgrounds.

## MI Handoff Checklist

Return this to the VFX lead or artist:

- Master material path.
- Material instance path.
- Packed texture path and import settings.
- Overrides list with defaults and platform fallback values.
- Required Niagara inputs: `ParticleColor.A`, optional tint, optional Dynamic Parameters.
- Ribbon UV assumption and whether `Flow_UV` art-space remap is used.
- Usage flags.
- Preview evidence required: ribbon carrier, background contrast, shader complexity or audit, Android/low tier when in scope.
- Known risks: overdraw, two-sided brightness, mip shimmer, high-frequency masks, bloom/exposure clipping.

## Validation

Minimum material-side validation:

- `material_audit.py`: no compile errors, expected outputs, sampler/instruction counts, no stale MI overrides.
- `material_domain_audit.py`: `Surface + Additive + Unlit`, expected usage flags.
- `texture_asset_report.py` or `texture_import_audit.py`: packed mask role, `sRGB=false`, compression and dimensions.
- `material_preview.py render --carrier ribbon`: ribbon-carrier readability.
- `preview_readability_score.py`: when the preview may be invisible or too bright.
- `platform_scalability_planner.py`: once delivery evidence exists.

Hand real Niagara integration proof to `niagara-vfx-artist`; this skill should not inspect or mutate the live Niagara renderer graph.
