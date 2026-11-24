# Fire, Energy, Burning Material Playbook

Use this when the user asks for fire, flame, torch, campfire, magical fire, burning edge, scorch, ember, smoke material, heat haze, lava, magma, plasma, energy flame, or any material where animated emissive heat is the main visual subject.

This file exists because "use Additive + Emissive" is not enough. A usable fire-family material needs a route, carrier, texture plan, node graph, motion plan, preview, and audit.

## Table Of Contents

- [Source-Backed Engine Contract](#source-backed-engine-contract)
- [Learn-Build-Audit Rule](#learn-build-audit-rule)
- [First Decision](#first-decision)
- [Reference Read](#reference-read)
- [Route: Hero Fire Flipbook](#route-hero-fire-flipbook)
- [Route: Single-Mask Panning Fire Detail](#route-single-mask-panning-fire-detail)
- [Route: Burning Dissolve Edge](#route-burning-dissolve-edge)
- [Route: Lava / Magma Surface](#route-lava--magma-surface)
- [Route: Heat Haze / Distortion](#route-heat-haze--distortion)
- [Texture Strategy](#texture-strategy)
- [Preview Gates](#preview-gates)
- [Audit Checklist](#audit-checklist)
- [Minimum Deliverable For A Fire-Family Request](#minimum-deliverable-for-a-fire-family-request)

## Source-Backed Engine Contract

Official Epic references to keep in mind:

- Emissive material values can exceed `1.0` and push the material into HDR/bloom territory.
- Fully emissive materials that do not need scene lighting should usually use the `Unlit` shading model because it is cheaper than lit shading.
- Additive blend adds source color onto the background and is not dynamically lit.
- Translucent/additive materials can become expensive through overdraw; use shader complexity view for particle and transparency-heavy effects.
- Niagara/SubUV sprite workflows use sprite atlases/flipbooks and renderer Sub Image Size or SubUV animation, but the real renderer timing belongs to `niagara-vfx-artist`.

Useful source anchors:

- Epic Material Inputs: `https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine`
- Epic Emissive Material Input: `https://dev.epicgames.com/documentation/en-us/unreal-engine/using-the-emissive-material-input-in-unreal-engine`
- Epic Material Properties and Blend Modes: `https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-properties`
- Epic Transparency Performance: `https://dev.epicgames.com/documentation/en-us/unreal-engine/using-transparency-in-unreal-engine-materials`
- Epic Viewport Shader Complexity: `https://dev.epicgames.com/documentation/en-us/unreal-engine/viewport-modes-in-unreal-engine`
- Epic Niagara smoke SubUV tutorial: `https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-smoke-effect-using-sprite-particles-in-niagara-for-unreal-engine`

## Learn-Build-Audit Rule

If the exact fire-family target is unfamiliar, do not answer from vague memory and do not stop at a concept paragraph.

Use this loop:

1. Search project assets and this skill's references for an existing route.
2. If still uncertain, read official docs or a source tutorial/case study and extract the material contract.
3. Decide whether the material can be built directly from graph nodes, needs generated textures, or needs a Niagara-owned carrier contract.
4. Build the smallest truthful UE material that has the required route, not just constants.
5. Read the graph back and audit it.
6. Preview it on the relevant carrier or a material-side harness.
7. Promote only reusable lessons back into this skill.

If UE automation or required assets are blocked, report the exact blocker and the graph/texture contract that remains to be built. Do not present a plan as a finished material.

## First Decision

Pick the route from the target look:

| Target | Preferred Material Route | Texture Need | Boundary |
|---|---|---|---|
| Hero torch, campfire, realistic flame body | `Surface` + `Additive` or `AlphaComposite` + `Unlit`, one-sided for camera-facing Niagara sprites/SubUV | fire flipbook/SubUV atlas, optional detail mask | Niagara owns spawn rate, frame timing, sorting, bounds |
| Stylized flame card or magic fire patch | `Additive` + `Unlit`, sometimes `Translucent` for softer alpha | flame tongue mask, color ramp, noise/detail mask | Material owns graph and textures; carrier still declared |
| Ember/spark material | `Additive` + `Unlit` | single ember alpha or small random atlas | Niagara owns particle count, velocity, random SubImageIndex |
| Smoke from fire | `Translucent` or `AlphaComposite` + `Unlit` | smoke flipbook or soft alpha mask | Smoke material is separate from flame material |
| Burning/dissolve edge on a mesh | `Masked` or `Opaque` surface, `DefaultLit` or `Unlit` depending target | dissolve/noise/burn mask, edge ramp | Can be pure material/MI animation without Niagara |
| Lava/magma surface | `Opaque` + `DefaultLit` with emissive crack network | crack mask, noise/flow, normal/roughness | Usually surface material, not a particle effect |
| Heat haze | translucent/refraction material or post-process distortion | distortion normal/noise | High cost; preview with background geometry |
| Energy flame/plasma | `Additive` or `AlphaComposite` + `Unlit` | arcs/noise/flipbook/atlas depending motion | Similar audit as fire, different color/ramp language |

## Reference Read

Before building, write a compact read of:

- Flame type: torch, campfire, gas flame, magical flame, stylized anime flame, electric/plasma, lava, burn edge, heat haze.
- Visual identity: white-hot core, yellow/orange/red bands, blue core, smoky edges, black soot, tongues, flicker speed, ember density, crack shapes, lava crust, stylized outline.
- Carrier: sprite, card mesh, ribbon, decal, surface mesh, post process, or material instance animation.
- Carrier topology: flat/open card, closed cone/cylinder/shell, wrapped mesh UV seam, one-sided or two-sided rendering, and expected number of additive layers visible at once.
- Motion: flipbook, panner, threshold animation, vertex/WPO flicker, UV distortion, random atlas cells, or external Niagara timing.
- Required texture roles: fire flipbook, flame tongue mask, ember atlas, smoke flipbook, dissolve mask, crack mask, flow/noise, distortion normal.

If the user provides a reference image, the reference controls the visible flame shape and color bands. A generic library fire mask is only a candidate and must not replace the requested look.

## Route: Hero Fire Flipbook

Material settings:

```text
Material Domain: Surface
Blend Mode: Additive or AlphaComposite
Shading Model: Unlit
Two Sided: false for camera-facing Niagara sprites/SubUV; only enable for a non-camera-facing mesh/card carrier with a documented reason
Outputs: EmissiveColor, Opacity
Expected carrier: sprite/card with SubUV or equivalent flipbook frame selection
```

Core parameters:

```text
T_FireFlipbook_VFX
V_CoreColor
V_OuterColor
S_CoreIntensity
S_OuterIntensity
S_Opacity
S_AlphaContrast
S_BlackEdgeSuppress
S_DistortionStrength
```

Node route:

```text
T_FireFlipbook_VFX.RGB or Color
  -> color ramp or multiply V_CoreColor / V_OuterColor
  -> * S_CoreIntensity / S_OuterIntensity
  -> * ParticleColor.RGB if carrier supplies it
  -> EmissiveColor

T_FireFlipbook_VFX.A or luminance
  -> contrast/remap
  -> * S_Opacity
  -> * ParticleColor.A if carrier supplies it
  -> Opacity
```

Notes:

- If the flipbook is black-background RGB with no alpha, it is a prototype mask unless luminance extraction is intentional and tested.
- If using `AlphaComposite`, verify premultiplied behavior and black-edge cleanliness.
- The material can declare SubUV expectations, but Niagara owns frame timing and renderer bindings.
- VFX texture asset names should end in `_VFX`, for example `T_FireFlipbook_VFX`.

## Route: Single-Mask Panning Fire Detail

Use this for detail flames, magic fire cards, cheap prototypes, or flame overlays.

Material settings:

```text
Blend Mode: Additive
Shading Model: Unlit
Two Sided: false for camera-facing Niagara sprites; enable only for special non-camera-facing card/mesh cases
```

Node route:

```text
TextureCoordinate * S_TilingA
  + Time * V_SpeedA
  -> T_FireMask.R

TextureCoordinate * S_TilingB
  + Time * V_SpeedB
  -> T_NoiseOrFireMask.R

VerticalGradient from UV.y
  -> power/contrast
  -> makes bottom hotter, top softer

(FireMaskA * FireMaskB * VerticalGradient)
  -> contrast with S_EdgeSharpness
  -> FlameMask

FlameMask
  -> Lerp(V_OuterColor, V_CoreColor, core mask)
  -> * S_EmissiveIntensity
  -> EmissiveColor

FlameMask * S_Opacity
  -> Opacity
```

Audit note:

- This can look acceptable for a small layer, but it is not a hero flame body unless the reference is very stylized/static.
- If it looks like one repeated scrolling texture, move to flipbook or add atlas variation.

## Route: Burning Dissolve Edge

Use this for objects burning away, magic incineration, or scorch reveal.

Material settings:

```text
Surface + Masked for cutout burn-away
Surface + Opaque for non-cutout glowing scorch
DefaultLit when the remaining surface must keep PBR response
Unlit when the whole effect is emissive/stylized
```

Node route:

```text
T_BurnNoise.R or VertexColor/paint mask
  -> compare with S_BurnThreshold
  -> OpacityMask

abs(T_BurnNoise.R - S_BurnThreshold)
  -> divide by S_EdgeWidth
  -> OneMinus / Saturate
  -> EdgeBand

EdgeBand * V_EdgeColor * S_EdgeIntensity
  -> EmissiveColor

Optional T_ScorchMask / darkened base color
  -> Lerp(BaseColor, V_ScorchColor, BurnProgress)
```

Audit note:

- Opacity mask data must use `TC_Masks` and `sRGB=false`.
- If the reference has a directional burn front, generic tileable noise is not enough; create a directed mask or combine mask with object/world-space gradient.

## Route: Lava / Magma Surface

Use this for ground cracks, lava pools, molten metal-like fantasy surfaces, and hot rock.

Material settings:

```text
Surface
Blend Mode: Opaque
Shading Model: DefaultLit
Outputs: BaseColor, Roughness, Normal, EmissiveColor
```

Node route:

```text
T_LavaCrackMask.R
  -> contrast/levels
  -> CrackMask

CrackMask
  -> Lerp(V_CoolRockColor, V_HotMagmaColor)
  -> BaseColor

CrackMask * V_MagmaColor * S_EmissiveIntensity
  -> EmissiveColor

Panned noise or flow helper
  -> slight UV offset / emissive flicker

T_RockNormal or generated normal
  -> Normal

Lerp(S_RockRoughness, S_MagmaRoughness, CrackMask)
  -> Roughness
```

Audit note:

- Lava is often a surface material, not a Niagara effect.
- Do not use additive transparency for a solid lava ground just because it glows.

## Route: Heat Haze / Distortion

Use this for hot air distortion above fire, engine heat, or magical shimmer.

Material settings:

```text
Translucent refraction material, or PostProcess material for screen-space route
Unlit where possible
```

Node route:

```text
T_DistortionNoise or normal
  <- panned UV
  -> remap from 0..1 to -1..1
  -> * S_DistortionStrength
  -> Refraction or UV offset route

Soft mask / DepthFade
  -> Opacity
```

Audit note:

- This is usually more expensive and more fragile than emissive fire.
- Preview with background geometry, not a black void.
- Mobile/low-end fallback should be fake emissive shimmer or no distortion.

## Texture Strategy

Search the reusable asset library first, but only reuse an asset if it matches the reference and technical role.

Common roles:

```text
T_FireFlipbook_VFX
  role: flipbook / color+alpha
  typical size: 4x4 or 8x8 cells, 1024/2048/4096 depending budget

T_FireTongueMask_VFX
  role: alpha/mask
  typical size: 512 or 1024 POT

T_EmberAtlas
  role: random atlas
  typical size: 4x4 cells, 512 or 1024 POT

T_SmokeFlipbook
  role: flipbook alpha/color
  typical size: 4x4 or 8x8 cells

T_BurnNoise / T_DissolveMask
  role: mask/data
  import: TC_Masks, sRGB=false

T_LavaCrackMask
  role: mask or color art depending usage
```

Use `cm-imagegen` for:

- fire tongue masks
- ember atlases
- smoke masks or draft smoke flipbooks
- stylized flame shapes from reference
- lava crack masks
- scorch/burn edge masks

Do not treat `cm-imagegen` as final authority for:

- vector flow maps
- physically meaningful normals
- exact SubUV timing
- high-fidelity smoke/fire simulation where real simulation baking is required

Prompt examples:

```text
grayscale flame tongue alpha mask, elongated upward flame shape,
clean silhouette, soft broken edges, high contrast black background,
1024x1024 power-of-two, no lighting, no text, no watermark,
for Unreal additive fire material opacity mask
```

```text
stylized magical blue fire flipbook, sprite sheet, 4x4 grid, 16 frames,
centered flame in each cell, upward licking motion, consistent scale,
white-blue hot core, cyan outer flame, alpha-friendly black background,
no text, no border, no watermark, for Unreal VFX SubUV material
```

Generated texture gate:

1. Prefer power-of-two sizes.
2. Run `texture_asset_report.py`.
3. Import mask/data as `TC_Masks`, `sRGB=false`.
4. If alpha is required, verify real alpha or run an alpha extraction/normalization step.
5. Preview on card/sprite/surface carrier before accepting.
6. Register reusable successes as `candidate` first unless tiling, alpha, channel semantics, and visual style are verified.

## Preview Gates

A fire-family material is not accepted from a shaderball alone. Preview at least:

- on the intended card/sprite/surface carrier
- against black and bright backgrounds
- with bloom/exposure checked enough to avoid a white blob
- shader complexity or overdraw view after the look exists
- parameter sweep for intensity, opacity, speed, threshold, and contrast
- motion check for panners, flipbook/SubUV, or burn threshold animation
- for smoke/heat haze, against scene geometry so softness/distortion is visible
- for lava/burning surface, on a mesh with real UV scale and lighting

## Audit Checklist

Must verify:

- Domain/blend/shading model match the route.
- `EmissiveColor` is the visible route for unlit fire/energy.
- `Opacity` is wired only when the blend mode supports it and the carrier needs it.
- ParticleColor is used when the material contract expects particle tint/alpha.
- Flipbook/SubUV expectations are declared, even if Niagara owns the real timing.
- Mask textures use data import settings when sampled as masks.
- Fire/smoke/lava textures match the reference, not merely the category.
- Additive/translucent overdraw is measured or called out.
- Two-sided additive carriers are compensated for front/back layer multiplication; high emissive values are judged with bloom/exposure enabled, not only by raw parameter values.
- Bloom/exposure are not hiding bad shape language.
- Stale parameters and dead branches are removed after the route is confirmed.

Classify findings:

- Must-fix: compile errors, wrong domain/blend/shading model, missing alpha/mask, wrong import settings, invisible material on intended background.
- Effect-first acceptable for prototype: high emissive, high instruction count, no low-end quality switch, if the look is still being established.
- Optimize-without-look-change: channel packing, lower helper texture size, shared samplers, quality switch, atlas trim, dead branch removal.
- Visual tradeoff: replacing flipbook with panning mask, removing heat distortion, lowering flame frame count, removing smoke layer.

## Minimum Deliverable For A Fire-Family Request

Deliver these artifacts or explicitly mark what is still missing:

- Material or master material with a real graph.
- Material instance with named controls.
- Required texture assets or generated candidates with QA reports.
- Preview on card/sprite/surface/heat-haze carrier as appropriate.
- Audit report separating visual-fidelity status from performance risks.
- A clear boundary note if Niagara must own particle spawn, SubUV timing, renderer sorting, or system integration.
