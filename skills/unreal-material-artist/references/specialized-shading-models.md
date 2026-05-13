# Specialized Shading Models

Use this when a material is not plain `DefaultLit`, or when a reference image implies skin, foliage transmission, hair, cloth fuzz, eyes, water, glass, clear coat, stylized unlit, or per-pixel shading-model selection.

## Shading Model Map

| Shading Model | Use For | Material-Side Requirements | Common Failure |
|---|---|---|---|
| `Unlit` | UI, VFX, stylized flat shading, post-like mesh overlays | `EmissiveColor` drives the visible result; opacity route depends on blend mode | Wiring PBR outputs and wondering why lighting/normal changes do nothing |
| `DefaultLit` | Most physical surfaces | `BaseColor`, `Roughness`, `Normal`, optional `Metallic`, `Specular`, `AO`, `Emissive` | Missing roughness/normal discipline; using translucency for simple cutouts |
| `Subsurface` | Wax, jade, soft scattering materials | `SubsurfaceColor`, thickness or mask strategy, sane base roughness | Treating it like cheap glow instead of scatter tint |
| `PreintegratedSkin` | Skin-like response in legacy paths | skin masks, normal detail, roughness breakup, color zones | Overusing one flat skin color; no pore/detail normal route |
| `SubsurfaceProfile` | Higher-quality skin and profile-driven SSS | assigned Subsurface Profile asset, `SubsurfaceColor`, mask control | Missing profile asset or using it on non-skin assets without reason |
| `TwoSidedFoliage` | Leaves, grass, thin organic sheets | usually `TwoSided`, `SubsurfaceColor`, masked alpha, wind/WPO budget | Heavy masked overdraw plus expensive WPO on dense foliage |
| `ClearCoat` | car paint, lacquer, varnished materials, coated metals | clear coat amount and clear coat roughness controls, normal strategy for base/coating | Setting the model but never wiring coat intensity |
| `Hair` | groom/card hair shading | tangent/anisotropy-aware texture plan, ID/random variation, stable alpha if cards | Treating hair as generic translucent cards with no strand direction |
| `Cloth` | fabric, velvet, fuzzy textile response | fuzz/sheen color, weave/detail normals, roughness remap | Solving cloth only with base color texture and no grazing response |
| `Eye` | humanoid eye materials | cornea/iris geometry assumptions, normal/refraction/occlusion plan | Applying it to a flat mesh or missing the asset setup the model expects |
| `SingleLayerWater` | water surfaces with opaque-path efficiency | usually `Opaque` blend, water color/absorption, normals, depth/foam support, `SingleLayerWaterMaterialOutput` | Switching to translucent glass logic, omitting the water output, or treating `Opacity` like ordinary translucent alpha |
| `ThinTranslucent` | physically plausible tinted glass | translucent route, tint, roughness, refraction/opacity discipline | Expecting cheap opaque performance from real transparency |
| `FromMaterialExpression` | per-pixel shading model selection | explicit `ShadingModel` output and masks, strong quality/permutation review | Hiding too many unrelated material types in one master |
| `Strata` / Substrate | Substrate-enabled material framework | Substrate graph route and project support | Using beta/advanced nodes without platform or cost review |

## Texture Needs By Family

Use textures when the detail is spatial, art-directed, or reused:

- Skin: base color zones, micro normal, roughness/spec masks, SSS mask.
- Hair: strand alpha, root-tip color, ID/random mask, tangent direction where needed.
- Cloth: weave normal, fuzz/sheen mask, roughness variation, dirt/wear mask.
- Foliage: alpha mask, subsurface/transmission color, normal, wind/variation masks.
- Water/glass: normal waves, foam/depth masks, dirt/scratch masks, packed roughness/opacity.
- Clear coat/paint: flake mask, orange-peel normal, coat roughness, edge wear.

Prefer pure math when the look is simple, low-frequency, globally adjustable, and cheaper than sampling. Prefer baked/packed textures when math becomes noisy, repeated, branchy, or hard to art-direct.

## Review Flow

1. Identify whether the reference truly needs a specialized shading model or whether `DefaultLit` plus a better texture/function stack is enough.
2. Confirm domain and blend mode first; a correct shading model on the wrong domain still fails.
3. Verify required outputs and profiles/assets.
4. Inspect texture roles and import settings.
5. Check whether a cheaper legacy model, Material Layer, or Substrate route is more appropriate.
6. Preview on a carrier that exposes the model: hair cards/groom, foliage planes, eye mesh, water plane, cloth fold, or coated shaderball.
7. Report cost risks, especially two-sided shading, translucency, masked overdraw, multi-layer normals, and Substrate/layer stacks.

For water, also read `complex-water-material-playbook.md`. Single Layer Water requires a concrete node route for normals, absorption/scattering, surface color, optional foam/caustics, and carrier preview; naming the shading model alone is not a water material.

## Boundary Note

If a specialized material is used by Niagara or another runtime system, this skill may define the material inputs it expects. It should not verify live Niagara parameter sources or write into a Niagara emitter/system.
