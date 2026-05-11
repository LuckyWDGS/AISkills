# Texture Versus Compute

## Use This When

- A material could be built from pure nodes/HLSL or from texture data.
- A VFX layer needs noise, masks, flow, flipbooks, atlases, distance falloff, or high-frequency detail.
- A material feels expensive and you need to decide whether to bake, simplify, or keep procedural control.

## Decision Rule

Use textures when the visual information is detailed, organic, reusable, high frequency, or expensive to regenerate per pixel.

Use computation when the visual information is simple, low frequency, strongly parameterized, resolution independent, or cheaper than fetching texture memory.

Do not compare “one texture” against “one math node.” Compare the whole route: samples, texture size, overdraw, cache behavior, mip quality, instruction count, platform, and how much screen area the material covers.

## Textures Are Usually Better For

- Organic noise with recognizable shape detail.
- Smoke, fire, splashes, clouds, sparks, ember shapes, leaf breakup, decals, runes, silhouettes, dirt, wear, cracks, and painterly masks.
- Flipbooks and SubUV animation where motion shape matters more than live simulation.
- Random atlas variants for sparks, lightning, shards, impact marks, and non-continuous shape variation.
- Flow maps, lookup ramps, baked gradients, signed distance masks, and packed data that would be expensive or awkward to derive per pixel.
- Reused detail across many particles or meshes, especially when one sampled mask replaces several procedural branches.

## Computation Is Usually Better For

- Simple gradients, linear fades, UV math, panners, radial rings, Fresnel, depth fade, camera distance, vertex color, world position masks, and scalar remaps.
- Parameterized shapes that must scale cleanly without texture resolution limits.
- Small math chains that avoid a texture fetch and do not create high instruction count.
- Procedural controls that designers must tune per instance.
- Platform variants where memory bandwidth is tighter than ALU.

## Warning Signs That A Texture Is Needed

- The procedural graph is recreating noise, feathering, cracks, cloud edges, flames, or organic masks with many layers of math.
- The graph uses several Custom nodes or repeated noise branches to approximate one stable art-directed pattern.
- The material is visually muddy because the procedural detail has no authored silhouette.
- A layer needs frame-to-frame shape evolution such as fire, smoke, splash, or explosion body.

## Warning Signs That Pure Texture Is Wrong

- A large translucent plane samples several 2K textures for a tiny on-screen effect.
- The material needs simple distance, ring, or Fresnel math but uses a large mask because it was easy to generate.
- Texture scale, mip bleeding, compression, or UV seams are more visible than the effect.
- The texture is generated AI output with imprecise channels, dirty alpha, inconsistent frame scale, or fake normal/flow data.

## Performance Review

Evaluate:

- `TextureSample` count and sampler state.
- Texture resolution, format, compression, sRGB, mips, and channel packing.
- Shader instruction count and expensive math.
- Translucent overdraw and screen coverage.
- Material domain and blend mode.
- Particle count or mesh count using the material.
- Platform and quality level.

Typical VFX starting budgets:

- PC simple VFX material: 80-160 instructions, 1-4 samples.
- PC hero VFX material: 160-300 instructions, 4-8 samples if screen coverage is controlled.
- Android simple VFX material: under 30-50 instructions, 0-2 samples.
- Android richer VFX material: 50-80 instructions, 1-3 samples only with controlled overdraw.

Treat these as first-pass guardrails, not universal truth. A full-screen translucent material at 60 instructions can be worse than a tiny spark material at 180.

## Baked Versus Live

Bake to texture or flipbook when:

- The pattern is expensive and repeatable.
- The motion is fluid-like or shape-changing.
- The look depends on artist-authored silhouette.
- A cheaper runtime route can play the baked data convincingly.

Keep live computation when:

- The shape must react to runtime parameters.
- The math is cheap and readable.
- The material must work across many scales and UV layouts.
- Baked texture memory would exceed the value of the saved math.
