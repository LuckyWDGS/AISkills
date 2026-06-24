# Complex Master Material Playbook

## Use This For

- hero character masters
- environment prop masters
- landscape masters
- decal suites
- wetness / dirt / wear / overlay systems
- advanced UV systems
- runtime variant-heavy materials

## Table Of Contents

- [Design Rules](#design-rules)
- [Recommended Sections](#recommended-sections)
- [Parameter Discipline](#parameter-discipline)
- [Switch Strategy](#switch-strategy)
- [Layout Strategy](#layout-strategy)
- [High-Value Function Library](#high-value-function-library)
- [Cost Control](#cost-control)
- [Default Texture Safety](#default-texture-safety)

## Design Rules

Keep complex masters:

- layered in concept, but not chaotic in graph layout
- modular with Material Functions
- stable in naming
- bounded in switches
- honest about platform limits

## Recommended Sections

Typical complex master blocks:

- Base surface inputs
- Normal pipeline
- Mask decode / packed texture decode
- Overlay / detail layer
- Edge breakup / noise
- Wetness / dirt / wear
- Runtime tint / emissive
- World-aligned or triplanar helpers
- Optional WPO / deformation
- Platform / quality fallbacks

## Parameter Discipline

Expose parameters by intent, not by math history:

- `BaseColorTint`
- `WetnessAmount`
- `OverlayBlendHardness`
- `EdgeBreakupScale`
- `WorldAlignedBlendSharpness`

Avoid:

- `MultiplyA`
- `LerpAlpha2`
- `MaskControl03`

## Switch Strategy

Static switches are powerful, but dangerous.

Use static switches for:

- expensive optional feature blocks
- platform fallbacks
- domain-specific forks that materially change shader cost

Do not use static switches for every tiny art variation. That belongs in dynamic parameters, scalar toggles, or separate masters.

## Layout Strategy

For a large master:

- top row = input / textures
- middle = decode / shape / blend logic
- lower = output assembly
- far side = preview/debug notes and reroutes

Use comments and reroutes, but do not let comments become a substitute for modular functions.

## High-Value Function Library

Every mature material project benefits from a reusable function library for:

- packed channel decode
- normal blend
- detail normal overlay
- triplanar/world aligned
- height blend
- mask remap
- hue/sat/value remap
- cheap Fresnel helpers
- depth fade variants
- UV distortion and panning helpers

If the same graph chunk appears three times, turn it into a function.

## Cost Control

Complex masters should still publish:

- expected sampler budget
- expected instruction budget
- required usages
- recommended import settings
- expected fallback strategy

Complex does not mean unbounded.

## Default Texture Safety

Default textures are part of the shader contract, not harmless placeholders.

- Use color/sRGB defaults only for color, albedo, emissive, or other artist-color inputs.
- Use mask-compatible defaults for mask, packed, ORM, roughness, metallic, opacity, flow, and scalar-data inputs.
- For `SAMPLERTYPE_Masks`, create or reuse a tiny project-local white/black texture with `TC_Masks` and `sRGB=false`.
- Do not use `/Engine/EngineResources/WhiteSquareTexture` as the default for mask/packed sampler slots; it is a color sRGB texture and can trigger sampler-type compile errors.
- Audit the master before artist textures exist. If the empty master fails because of placeholder texture settings, the master is not production-safe yet.
