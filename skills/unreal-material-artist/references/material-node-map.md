# Material Node And HLSL Map

## Principle

Unreal material nodes are visual authoring blocks that compile into shader code. Read them by intent: coordinates, texture/data fetch, shaping math, lighting/output, runtime control, and platform switching.

For exhaustive per-node behavior, use Epic's Material Expressions Reference. This file is a compact production map for deciding what category a node belongs to and what to inspect.

## Output And Material Inputs

Common outputs:

- `BaseColor`: lit surface color.
- `Metallic`, `Specular`, `Roughness`: PBR response.
- `EmissiveColor`: self-lit output and most VFX glow routes.
- `Opacity`: translucent alpha.
- `OpacityMask`: masked cutout threshold route.
- `Normal`: tangent-space normal unless configured otherwise.
- `WorldPositionOffset`: vertex displacement.
- `PixelDepthOffset`: per-pixel depth offset; expensive/risky with sorting and mobile.
- `Refraction`: translucent distortion; use carefully.
- `MaterialAttributes`: bundled route for layered/material-attribute workflows.

Always check Material Domain, Blend Mode, Shading Model, and usage flags; not every input is meaningful for every material configuration.

## Table Of Contents

- [Node Families](#node-families)
- [VFX Material Types](#vfx-material-types)
- [Read Graph Intent Fast](#read-graph-intent-fast)

## Node Families

Coordinates:

- `TextureCoordinate`, `Panner`, `Rotator`, `WorldPosition`, `ObjectPosition`, `CameraPositionWS`, `ScreenPosition`, `VertexNormalWS`, `Transform`, `ComponentMask`, `AppendVector`.
- Use for UVs, world-space masks, camera distance, object-space projection, panning flows, and screen/post-process coordinates.
- For low-poly cone/cylinder/shell VFX meshes, Fresnel can inherit visible faceting from `VertexNormalWS`. When mesh reauthoring is out of scope, a radial virtual normal can be tested as `LocalPosition -> ComponentMask RG -> Append Z=0 -> Normalize -> Transform Local to World`, but treat it as a look variant and revert if it changes the intended falloff.

Texture and data fetch:

- `TextureSample`, `TextureSampleParameter2D`, `TextureObject`, `TextureObjectParameter`, `SceneTexture`, `VirtualTextureSample`, `RuntimeVirtualTextureSample`, `FontSample`.
- Audit sampler type, sampler source, texture settings, channel use, duplicate samples, dependency visibility, and `MipValueMode`.
- For stretched/panned noise on wrapped mesh carriers, `MipValueMode=Derivative` should use `DDX` / `DDY` nodes fed by clean `TextureCoordinate` when the goal is to keep mip selection independent from tiling/panner math.

Math and shaping:

- `Add`, `Subtract`, `Multiply`, `Divide`, `DotProduct`, `CrossProduct`, `Power`, `Saturate`, `Clamp`, `Min`, `Max`, `Abs`, `Floor`, `Ceil`, `Frac`, `Fmod`, `Lerp`, `SmoothStep`, `Step`, `OneMinus`, `Normalize`, trigonometric nodes.
- Use for cheap shaping when the pattern is simple. Watch repeated high-cost math and Custom nodes that duplicate basic operations.

Masks and falloff:

- `Fresnel`, `DepthFade`, `SphereMask`, radial gradients, distance math, vertex color, object bounds, camera distance.
- Common for shields, rims, soft particles, rings, impact masks, and distance fading.

Color and remap:

- Vector/scalar parameters, curves/ramps via textures, channel masks, desaturation, contrast remap, blackbody-style gradients, color lerps.
- Prefer LUT/ramp textures when a complex art-directed color curve is easier to control as data.

Runtime control:

- `ParticleColor`, `DynamicParameter`, `PerInstanceRandom`, `MaterialParameterCollection`, scalar/vector/static switch parameters, vertex color.
- Name controls by user intent: `EmissiveIntensity`, `OpacityScale`, `FlowSpeed`, `EdgeBreakup`, not `MultiplyA`.

Flow and animation:

- `Panner`, time, sine/cosine, flipbook/SubUV setup, flow map UV offset, atlas cell selection, noise scroll.
- Use flipbooks when shape changes over time; use panners/flow maps when a mostly stable texture needs motion.

Switching and scalability:

- `StaticSwitchParameter`, `FeatureLevelSwitch`, `QualitySwitch`, static bools.
- Use for real platform variants. Avoid casual static switches in many MIs because each unique static combination creates shader permutations.

Custom and HLSL:

- Use Custom nodes for compact algorithms, shader intrinsics, repeated reusable math, or logic that would become unreadable as graph nodes.
- Avoid Custom nodes for trivial add/multiply/lerp/saturate work.
- Keep inputs explicit and named.
- Return the narrowest useful type: `Float1`, `Float2`, `Float3`, or `Float4`.
- Prefer graph `TextureSample` nodes over manual `Texture2DSample` inside Custom HLSL unless there is a concrete dependency or sampling reason.
- Gate SM-specific intrinsics or expensive branches with quality/feature switches when the material ships to weaker platforms.

## VFX Material Types

Additive Unlit:

- Good for sparks, glows, energy cores, muzzle flashes, magic streaks.
- Cheap and readable, but can blow out color and disappear on bright backgrounds.

Translucent Unlit:

- Good for smoke, soft particles, shields, fog, glassy energy, refraction.
- Main risk is overdraw, sorting, refraction, and large screen coverage.

Masked:

- Good for hard cutouts, foliage-like silhouettes, stylized decals, some mesh VFX.
- Avoid noisy animated masks that shimmer.

Opaque or DefaultLit:

- Good for physical surfaces, props, stylized meshes, decals that need lighting response.
- Heavier than unlit VFX, but correct when the object must belong to scene lighting.

Post Process:

- Good for screen-space effects, outlines, color grading, distortion, fullscreen feedback.
- Fullscreen cost is high; audit scene texture samples and resolution.

UI:

- Good for UMG and render-target UI. Keep cost low and avoid scene-dependent assumptions.

## Read Graph Intent Fast

Ask:

- Which output pins are actually connected?
- What controls alpha and emission?
- What texture channels are used?
- Which part gives shape, which part gives color, which part gives motion?
- Which parameters are user-facing?
- Is the graph computing detail that should be a texture?
- Is a texture carrying data that should be cheap math?
- Does the material match the carrier and platform?
