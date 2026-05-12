# Material Domain And Rendering Contracts

Use this when a material might be using the wrong `Material Domain`, `Blend Mode`, `Shading Model`, output pins, or render path for its intended carrier.

This is material-side scope only. It can define what a material requires from the caller, but it must not inspect or write live Niagara systems, renderer bindings, or emitter graphs.

## Domain Contracts

| Domain | Use For | Expected Material Route | High-Risk Mistakes |
|---|---|---|---|
| `Surface` | Meshes, characters, props, foliage, water surfaces, most world geometry | PBR or Unlit outputs through the main material node; `BaseColor`, `Roughness`, `Normal`, `Emissive`, `OpacityMask`, `WPO`, and similar pins depend on blend/shading model | Using PostProcess/SceneTexture logic as a surface shortcut; paying for translucent when masked or opaque is enough; heavy WPO/PDO on Nanite/mobile without a fallback |
| `DeferredDecal` | Projected decals, stains, bullet marks, wetness, grime, local overlays | Decal-compatible outputs and opacity route; keep channel writes intentional | Treating a decal like a full surface material; missing opacity/mask control; high overdraw decals stacked over large screen areas |
| `LightFunction` | Animated light intensity masks and projection gobos | Usually simple emissive/intensity mask logic; applied to movable/stationary lights | Expecting it to tint light color directly; expensive animated noise on many lights; forgetting forward-rendering/shadow-channel limitations |
| `Volume` | 3D volume material behavior | Volume-specific attributes, usually very constrained | Reusing surface PBR graphs; too many texture/noise samples in a volume path |
| `PostProcess` | Full-screen or volume-blended screen effects | `EmissiveColor` outputs the final pass color; `SceneTexture` / PostProcessInput route supplies scene data | Wiring PBR outputs; using `SceneColor` when a PostProcessInput is required; running expensive multi-sample effects after every frame without quality gating |
| `UI` | UMG / Slate materials | Unlit-style color and opacity route; simple texture/math; predictable alpha | World-space nodes, scene depth, WPO/PDO, large textures with no mips strategy, unnecessary lighting logic |
| `RuntimeVirtualTexture` | RVT writers/samplers, mostly landscape and terrain blending systems | RVT Output / Sample / Replace expressions plus matching RVT asset material type | Mismatched RVT asset material type; no fallback for unsupported platforms; sampling/writing outside RVT volume assumptions |

## Blend Mode Contracts

| Blend | Use For | Audit Focus |
|---|---|---|
| `Opaque` | Solid surfaces, most PBR assets, Single Layer Water | `Opacity` does not create transparency. Prefer this whenever translucency is not required. |
| `Masked` | Cutouts, foliage, hard alpha cards, holes | Must have a meaningful `OpacityMask`; watch masked overdraw and noisy animated masks. |
| `Translucent` | Glass, soft particles, ghost surfaces, volumetric-looking overlays | Overdraw, sorting, refraction, depth fade, lighting mode, separate translucency, mobile cost. |
| `Additive` | Glows, light sprites, energy overlays | Usually `Unlit`; watch invisible-on-bright-background behavior and overdraw. |
| `Modulate` | Rare multiplicative darkening/tinting | Validate art intent; it is easy to get non-physical or platform-fragile results. |
| `AlphaComposite` | Premultiplied-alpha style translucent compositing | Confirm texture alpha is authored premultiplied or the visual result will be wrong. |
| `AlphaHoldout` | Holdout/cutout compositing | Confirm the target renderer path supports it; usually wants a very explicit matte contract. |

## Output-Pin Review

Review output pins against the selected domain and shading model:

- `PostProcess` should normally output through `EmissiveColor`; PBR pins are suspect.
- `Unlit` needs `EmissiveColor`; lit-only pins such as `Metallic`, `Specular`, `Roughness`, and `Normal` are ignored or wasted.
- `Masked` needs `OpacityMask`; `Opacity` alone does not cut pixels.
- `Translucent` / `Additive` should make alpha, depth, sorting, and overdraw costs explicit.
- `DefaultLit` and other physical surface models should not omit `BaseColor`, `Roughness`, and `Normal` without a reason.
- `WorldPositionOffset` and `PixelDepthOffset` are not just visual features; they are render-contract features with bounds, Nanite, shadow, sorting, and platform implications.
- `Use Material Attributes` moves the contract into a material-attributes chain. Audit `MakeMaterialAttributes`, `BreakMaterialAttributes`, `BlendMaterialAttributes`, and `MaterialAttributeLayers` instead of only checking individual output pins.

## When To Run A Domain Audit

Run `material_domain_audit.py` before deeper graph work when:

- a material is not a regular opaque surface
- a reference image implies glass, water, skin, hair, cloth, UI, decals, post process, light projection, or terrain blending
- a graph compiles but looks wrong in the target carrier
- a performance issue might come from blend mode, overdraw, WPO/PDO, SceneTexture, RVT, or Substrate/layering rather than ordinary math
- a master material is being reused across domains that should probably be separate masters

## Acceptance Notes

A correct material contract should say:

- intended domain, blend mode, shading model, and carrier
- required texture roles and import settings
- required material parameters and who should own them at runtime
- expected output pins or Material Attributes route
- platform budget and fallback path
- preview route that proves the material itself, not a full gameplay integration

