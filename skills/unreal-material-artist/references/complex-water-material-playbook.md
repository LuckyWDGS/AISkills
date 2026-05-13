# Complex Water Material Playbook

Use this when the user asks for custom water, ocean, pool, river, shallow tropical water, stylized anime water, oily liquid, magic water, wet shoreline, caustics, foam, or any material where "water" is the main visual subject.

This file exists because "use Single Layer Water" is not enough. A water material is a stack of shading model, surface motion, color/depth response, normals, foam/caustics masks, carrier geometry, and preview conditions.

## Source-Backed Engine Contract

Official Epic references to keep in mind:

- Single Layer Water uses a transparent-looking water surface while staying on the `Opaque` or `Masked` blend path.
- The Single Layer Water material output defines `Scattering Coefficients`, `Absorption Coefficients`, `PhaseG`, and `Color Scale Behind Water`.
- In Single Layer Water, main-material `Opacity` is not ordinary translucent alpha. It controls the ratio between the water volume BSDF and the surface BRDF, so audit it as a water response control rather than a generic fade.

Useful source anchors:

- Epic Single Layer Water docs: `https://dev.epicgames.com/documentation/zh-cn/unreal-engine/single-layer-water-shading-model-in-unreal-engine`
- Epic Shading Models docs: `https://dev.epicgames.com/documentation/en-us/unreal-engine/shading-models-in-unreal-engine`
- Epic Material Properties docs: `https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-properties`

## First Decision

Pick the water route from the target look, not from performance convenience:

| Target | Preferred Route | Avoid |
|---|---|---|
| Ocean, lake, pool, river surface with physical depth color | `Surface` + `Opaque` or `Masked` + `SingleLayerWater` | Plain translucent glass water unless there is a specific reason |
| Stylized flat/cel/anime water, painterly foam, magic water | `Unlit`, `DefaultLit`, or `SingleLayerWater` depending on lighting need | Replacing the reference's foam/brush language with generic ripple noise |
| Glass tank, bottle liquid, close transparent volume | `Translucent` or `ThinTranslucent`, possibly separate glass and liquid materials | Forcing `SingleLayerWater` when the visual problem is glass/refraction volume |
| Underwater screen tint or drowning/vision effect | `PostProcess` material plus separate water surface | Solving full-screen water feeling only on the surface material |
| Shore wetness, puddles, mud sheen | Surface layered material or decal/RVT support | Building a full water shader when the need is a wetness layer |

## Reference Read

Before building, write a compact read of:

- Water type: ocean, lake, river, pool, shallow shore, swamp, oil, magic, stylized.
- Visual identity: foam shape, caustics shape, color bands, transparency, wave scale, ripple frequency, surface roughness, shoreline breakup, dirt/particles, brush strokes, glow.
- Carrier: large plane, water-body mesh, river spline mesh, puddle decal, contained volume, post-process.
- Motion: still, slow ripple, directional river flow, choppy waves, stylized loop, foam drift, caustics shimmer.
- Required texture roles: normal, height, flow, foam mask, caustics, color ramp, packed data, dirt/particle mask.

If a reference image exists, asset-library results are only candidates. A generic water ripple may support the normal layer, but it cannot replace the visible foam/caustic/color identity unless it actually matches.

## Hero Single Layer Water Route

Material settings:

```text
Material Domain: Surface
Blend Mode: Opaque or Masked
Shading Model: SingleLayerWater
Two Sided: usually false for a top-facing plane; verify special cases
Outputs: BaseColor, Roughness, Specular, Normal, optional WPO, optional Opacity, SingleLayerWaterMaterialOutput
```

Core parameter set:

```text
V_ShallowColor
V_DeepColor
V_FoamColor
V_ScatteringCoefficients
V_AbsorptionCoefficients
V_ColorScaleBehindWater
S_PhaseG
S_SurfaceOpacity
S_Roughness
S_NormalStrength
S_NormalTilingA / S_NormalTilingB
V_NormalSpeedA / V_NormalSpeedB
S_FoamDepthStart / S_FoamDepthEnd
S_FoamIntensity
S_CausticsIntensity
S_WaveAmplitude / S_WaveFrequency / S_WaveSpeed
```

Texture roles:

```text
T_WaterNormalA / T_WaterNormalB
  role: normal
  import: Normalmap, sRGB=false

T_FoamMask
  role: mask or foam shape
  import: TC_Masks, sRGB=false if sampled as data

T_CausticsMask
  role: caustics intensity/shape
  import: TC_Masks, sRGB=false unless it is authored color art

T_FlowMap
  role: RG vector flow
  import: data/flow, sRGB=false
  rule: do not approve AI flow vectors without validation

T_WaterRippleHeight
  role: draft height or ripple mask
  import: TC_Masks, sRGB=false
  rule: may seed a prototype; final normal/flow needs DCC/script validation
```

### Node Route: Normal Motion

```text
TextureCoordinate
  * S_NormalTilingA
  + Time * V_NormalSpeedA
  -> TextureSample(T_WaterNormalA)

TextureCoordinate
  * S_NormalTilingB
  + Time * V_NormalSpeedB
  -> TextureSample(T_WaterNormalB)

T_WaterNormalA + T_WaterNormalB
  -> BlendAngleCorrectedNormals or NormalFromFunction
  -> FlattenNormal / NormalStrength
  -> Normal
```

If the water has strong directional flow:

```text
TextureCoordinate
  + ((T_FlowMap.RG * 2 - 1) * S_FlowStrength)
  + Time * V_FlowSpeed
  -> normal/foam/caustics UVs
```

### Node Route: Depth Color

For Single Layer Water, prefer the engine water model for underwater color response. Use a depth term only when the node path is available and verified for the engine version:

```text
SceneDepthWithoutWater - PixelDepth
  -> subtract S_DepthStart
  -> divide S_DepthRange
  -> Saturate
  -> WaterDepth01

Lerp(V_ShallowColor, V_DeepColor, WaterDepth01)
  -> BaseColor
```

Fallbacks when `SceneDepthWithoutWater` is unavailable or the carrier does not support it:

- Vertex color or mesh-painted depth mask for rivers/pools.
- Landscape/RVT mask for shore zones.
- Manual shallow/deep material instance per area.
- Separate post-process for underwater tint instead of forcing it into the surface.

### Node Route: Single Layer Water Output

```text
V_ScatteringCoefficients
  -> SingleLayerWaterMaterialOutput.ScatteringCoefficients

V_AbsorptionCoefficients
  -> SingleLayerWaterMaterialOutput.AbsorptionCoefficients

S_PhaseG
  -> SingleLayerWaterMaterialOutput.PhaseG

V_ColorScaleBehindWater * optional caustics term
  -> SingleLayerWaterMaterialOutput.ColorScaleBehindWater

S_SurfaceOpacity or depth-shaped opacity control
  -> main material Opacity
```

Audit note: `Opacity` here is a water model control, not a normal translucent fade. Do not tune it with the same expectations as a `Translucent` material.

### Node Route: Foam

Shore foam:

```text
WaterDepth01
  -> OneMinus
  -> SmoothStep(S_FoamDepthStart, S_FoamDepthEnd)
  -> DepthFoamMask

T_FoamMask.R
  <- panned or flow-map UV
  -> multiply DepthFoamMask
  -> multiply S_FoamIntensity
  -> FoamMask

Lerp(BaseWaterColor, V_FoamColor, FoamMask)
  -> BaseColor

FoamMask * optional V_FoamEmission
  -> EmissiveColor for stylized water only
```

Crest foam:

```text
WaveHeightOrNormalDerivedMask
  -> Power(S_CrestSharpness)
  -> multiply T_FoamMask.R
  -> add to FoamMask
```

If no wave-height signal exists, do not fake crest foam from random noise and call it finished. Either add WPO/wave height, generate an authored foam mask, or label it as a prototype.

### Node Route: Caustics

For shallow stylized or pool water:

```text
WorldPosition.XY * S_CausticsTiling
  + Time * V_CausticsSpeedA
  -> T_CausticsMask.R

WorldPosition.XY * S_CausticsTilingB
  + Time * V_CausticsSpeedB
  -> T_CausticsMask.R

Multiply/Add two caustics samples
  -> multiply S_CausticsIntensity
  -> ColorScaleBehindWater or Emissive/BaseColor overlay depending route
```

Do not use a random cloudy noise as "caustics" when the reference has sharp dancing light nets. Generate or author a caustics mask/flipbook that matches the reference.

### Node Route: WPO Waves

Simple material-side WPO for a plane:

```text
WorldPosition.XY
  -> Dot(V_WaveDirectionA)
  -> * S_WaveFrequencyA
  -> + Time * S_WaveSpeedA
  -> Sine
  -> * S_WaveAmplitudeA

Repeat 2-4 wave bands
  -> Add
  -> AppendVector(0, 0, Height)
  -> WorldPositionOffset
```

Use this for modest surface motion. For real oceans, buoyancy, shoreline interaction, or large Gerstner stacks, treat material WPO as only one part of a water system and verify bounds, LOD, shadows, and Nanite/platform support.

## Stylized Water Route

Use this for anime/cel/painterly/magic water where reference style matters more than physical accuracy.

Common settings:

```text
Material Domain: Surface
Blend Mode: Opaque, Masked, Additive, or Translucent depending target
Shading Model: Unlit or DefaultLit; SingleLayerWater only if depth/lighting response is desired
```

Core graph:

```text
Depth or vertex mask
  -> Lerp(V_ShallowStylizedColor, V_DeepStylizedColor)

T_StylizedFoamMask.R
  <- panned world/UV coords
  -> SmoothStep threshold
  -> FoamMask

T_CausticsOrBrushMask.R
  <- panned/rotated world coords
  -> add/multiply into color

Fresnel
  -> edge color / rim foam / outline intensity

Optional WPO sine/ripple
  -> WorldPositionOffset
```

Reference gate:

- If the reference has brushy cyan-white foam, generate or author that foam shape.
- If the reference has cel bands, build stepped color ramps instead of physical absorption.
- If the reference has oily sci-fi liquid, use color-ramp/iridescence/roughness breakup instead of normal lake ripple.
- If the reference has magical glow, route glow deliberately to `EmissiveColor`; do not hide it in a generic base-color tint.

## Translucent Or Thin Glass Water Route

Use this for small contained water, glass tanks, bottles, droplets, or water sheets where actual translucency/refraction is the visual target.

Common settings:

```text
Material Domain: Surface
Blend Mode: Translucent
Shading Model: DefaultLit or ThinTranslucent if tinted glass-like response is needed
```

Core graph:

```text
NormalA/NormalB panners
  -> Normal

DepthFade or SceneDepth delta
  -> color absorption approximation
  -> Lerp(ShallowTint, DeepTint)

Fresnel
  -> Opacity / Specular / tint boost

Refraction input
  <- normal/distortion strength if project route supports it
```

Audit warning:

- This route pays translucent sorting/overdraw cost. Use it because the look needs it, not because "water is transparent."
- For large water bodies, try the Single Layer Water route first.

## Texture Generation Rules For Water

Use `cm-imagegen` for:

- visible foam masks
- stylized brush masks
- caustics masks or draft caustics atlases
- surface dirt/debris masks
- color reference exploration
- draft ripple height maps

Do not treat `cm-imagegen` as final authority for:

- physically meaningful normal maps
- RG flow maps
- vector displacement
- exact LUT/ramp response

If generated output is used:

1. Prefer `512`, `1024`, or `2048` power-of-two.
2. Run `texture_asset_report.py`.
3. Import masks/height/flow as data (`sRGB=false`, mask/data compression).
4. Preview on the water carrier before approving.
5. Register as `candidate` unless tiling, seams, channels, and visual style are verified.

Prompt pattern:

```text
custom water foam mask from reference image, preserve [specific foam style],
1024x1024 power-of-two, seamless tile, grayscale data texture,
no lighting, no perspective, no text, no watermark, for Unreal water material foam mask
```

Bad prompt:

```text
beautiful realistic water texture, detailed waves, blue ocean, cinematic
```

## Preview Gates

A water material is not accepted from a shaderball alone. Preview at least:

- top-down view
- grazing-angle view
- shallow object under water
- deep object under water
- shoreline/intersection if the material has foam
- motion loop for normals/foam/caustics
- one neutral lighting pass and one high-reflection pass
- shader complexity or water-specific audit pass after the look is established

If the reference is stylized, compare:

- foam silhouette
- caustics shape
- color bands
- edge/rim behavior
- motion speed
- scale relative to carrier

## Audit Checklist

Must verify:

- `Material Domain`, `Blend Mode`, and `Shading Model` match the chosen route.
- `SingleLayerWaterMaterialOutput` exists for the Single Layer Water route.
- Normal textures use normal compression and `sRGB=false`.
- Mask/height/flow/packed data use data import settings and role-correct default textures.
- Foam/caustics texture style matches the reference, not merely the category name.
- `Opacity` is interpreted correctly for Single Layer Water.
- WPO bounds, shadows, Nanite/platform support, and collision expectations are documented when WPO is used.
- Generated normal/flow/vector textures are not approved without validation.

## Minimum Deliverable For A Custom Water Request

When asked to make a water material, deliver these artifacts or explicitly mark what is still missing:

- Material or master material with real node graph, not just constants.
- Material instance with named controls.
- Required texture assets or generated candidates with QA reports.
- Preview on a water plane/carrier with at least one depth/shoreline context.
- Audit report with visual-fidelity status and performance risks separated.
- If optimized, note whether each optimization preserves the look or is a visible tradeoff.
