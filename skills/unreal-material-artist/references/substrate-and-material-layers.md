# Substrate And Material Layers

Use this when a material is more complex than a single PBR stack: layered paint, armor, dirt, snow, wetness, cloth fuzz, clear coat, skin coatings, terrain blends, hero props, or reusable studio master materials.

This reference is about material authoring and review. Real VFX system wiring remains outside this skill.

## Choose The Layering System

| Approach | Best For | Avoid When |
|---|---|---|
| Simple master material plus Material Instances | Most props, characters, tiling surfaces, straightforward masks | The graph becomes a switch graveyard or repeats large blend blocks |
| Material Functions with `Material Attributes` | Reusable graph chunks, hand-authored layer blends, predictable shipped masters | Artists need to reorder layer stacks per instance without editing the base material |
| Material Layer / Material Layer Blend assets | Artist-editable layer stacks in Material Instances | The project lacks naming/versioning discipline for layer assets |
| Substrate | Physically expressive BSDF layering, thin film, complex matter, advanced clear coat / fuzz / transmission experiments | Simple PBR would do, mobile/low-end is a target, or the project cannot absorb beta-feature and shader-cost risk |
| Runtime Virtual Texture | Landscape and large terrain compositing, decal-like terrain blending, caching expensive landscape shading | Small local material details or assets outside RVT volume assumptions |

## Material Attributes Discipline

`Use Material Attributes` is powerful because it lets whole material descriptions flow through functions and layer blends. It is also where unreadable master materials are born.

Keep the route clean:

- Use `MakeMaterialAttributes` at layer boundaries, not randomly in the middle of unrelated math.
- Use `BreakMaterialAttributes` only when a layer genuinely needs to override specific attributes.
- Keep layer masks named by art meaning: `SnowTopMask`, `WetnessCavityMask`, `PaintWearMask`.
- Put repeated decode/remap/normal-blend logic into functions.
- Record whether a mask is vertex color, texture channel, procedural, RVT, or runtime parameter.
- Do not stack layers that each resample the same base textures unless the visual payoff is worth the cost.

## Material Layers Asset Rules

Material Layer and Material Layer Blend assets are useful when artists need editable stacks in the Material Instance editor.

Review them for:

- stable layer asset names and categories
- unique parameter names inside each layer/blend
- layer-stack order and visibility expectations
- mask source and channel convention
- whether the same layer appears more than once and needs per-layer parameter uniqueness
- whether the base material has a sensible default background layer
- whether static switches in layer assets explode permutations across many instances

## Substrate Rules

Substrate replaces much of the fixed legacy shading-model workflow with a more expressive BSDF-style material framework. Treat it as an expert route, not a default route.

Use Substrate when:

- the reference requires layered matter rather than a simple texture blend
- clear coat, fuzz, thin film, transmission, or complex surface response is central to the look
- the target platform and engine version are known to support the feature safely
- the team accepts the extra audit burden

Be cautious when:

- the material could be normal `DefaultLit`, `ClearCoat`, `Cloth`, `Hair`, or `SingleLayerWater`
- the material is for mobile, UI, cheap VFX, or large-screen terrain
- the project has not enabled or standardized Substrate
- the graph uses Substrate nodes but has no quality fallback or benchmark

## Cost Review

Layered materials usually fail because every layer feels cheap alone, but the stack is not cheap.

Audit:

- texture samples per layer and per final pixel
- repeated normal blending
- height/curvature/cavity masks that could be baked
- static switches that multiply shader permutations
- branchy HLSL inside layer functions
- large full-screen coverage such as landscapes, decals, UI, or post process
- `FeatureLevelSwitch`, `QualitySwitch`, or separate low-cost masters for weaker platforms

## Tool Hooks

- `material_domain_audit.py`: confirm the domain, blend, shading model, output route, and high-level cost risks.
- `material_function_linter.py`: inspect layer functions for missing inputs/outputs, preview defaults, and switch sprawl.
- `shader_permutation_report.py`: find static-switch groups that should be consolidated.
- `texture_asset_report.py` and `texture_import_audit.py`: verify layer masks, normals, packed channels, and RVT-related textures before blaming graph math.

## Delivery Contract

For a complex layered material, report:

- layer list and blend order
- mask source for every layer transition
- texture channel packing convention
- parameter ownership: MI, MID, MPC, vertex color, RVT, or caller-provided
- expected shader cost and sampler count
- fallback strategy for lower feature levels
- preview evidence: neutral shaderball plus at least one target carrier if available

