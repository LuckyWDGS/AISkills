# Ribbon Trail Material Seam Debugging

Use this reference when a Niagara Ribbon / trail material shows visible split lines, repeated tile bands, hard width edges, or scene-intersection cuts after the Ribbon geometry and source event chain have already been verified.

## Separate Material Seams From Niagara Folds

Treat it as a material problem only when the silhouette is stable:

- **Material seam**: line follows UV tiling or texture boundaries; shape remains flat and continuous.
- **Niagara fold**: vertical sheets, crossed cards, hard angular planes, or sudden connections between old/new positions. Return to Niagara source/renderer/Actor motion debugging.
- **Scene cut**: edge appears where translucent trail intersects geometry. Use DepthFade/soft-particle logic.

Do not keep adding material softness to hide Ribbon topology problems.

## Carrier Contract

Before editing the graph, confirm the live Niagara renderer:

- Ribbon default UV convention is usually `U = ribbon length`, `V = ribbon width`.
- Keep width masks and edge fades on raw `TexCoord0.V`.
- Put flow, panning, longitudinal tiling, and seam checks on the length axis.
- If the texture art is authored with a different axis, document the art-space remap and keep raw width falloff separate.
- Confirm renderer UV tiling/distribution before graph edits. If Niagara uses distance tiling, material panning and seam blending must respect that live renderer route.
- Treat `TextureCoordinate` as the material-side source of mesh/ribbon UVs. Use explicit component masks/append nodes when separating length and width axes so later audits can see the contract.

## Common Causes

- Packed mask texture is not seamless at `0/1`.
- Texture address mode is `Wrap` while the art expects mirrored continuity.
- Additive/translucent overdraw makes faint tile boundaries brighter.
- Ribbon tiling length is too short, causing frequent repetitions.
- Width alpha has no soft edge, so rectangular carrier boundaries read as seams.
- No DepthFade, so geometry intersections cut the translucent ribbon hard.

## Repair Order

Use the narrowest repair that matches the artifact:

1. **Import/address sanity**
   - Mask/data textures: `sRGB=false`, mask/data compression where appropriate.
   - Try `Mirror` addressing when the texture is non-seamless but mirrorable.
2. **Width soft edge**
   - Build width falloff from raw `TexCoord0.V`.
   - Multiply both opacity/alpha and emissive/glow contribution by the width mask.
   - Expose a width-edge power/softness parameter.
3. **DepthFade**
   - Use DepthFade for translucent/additive scene intersections; it is designed to hide seams where translucent objects intersect opaque ones.
   - Multiply alpha by DepthFade for scene intersections.
   - Expose fade distance; tune per carrier scale and camera distance.
4. **Seam-safe dual sampling**
   - Sample the original mask UV.
   - Sample a half-period shifted UV on the problematic texture axis.
   - Blend with `LinearInterpolate` near `frac(lengthAxis)` boundaries using exposed controls such as:
     - `TailSeamBlendWidth` around `0.05-0.12`.
     - `TailSeamBlendStrength` around `0.8-1.0`.
   - Reuse the same texture/sampler where possible; instruction count rises, sampler count may remain unchanged.
5. **Replace the art**
   - If full-strength dual sampling still leaves a hard split, create/import a genuinely seamless mask texture instead of continuing graph hacks.

When the user explicitly limits the work to material-only, do not change Niagara width, tiling, or renderer settings. State that geometry folds cannot be solved material-only.

## Verification

After material edits:

- Run material audit and compile/shader-map readiness checks.
- Confirm exposed parameters have the project's required descriptions and ranges.
- Confirm the live Niagara renderer or material instance actually uses the edited material route.
- Preview on a Ribbon-like carrier or in the real Niagara system when possible.
- If the visible problem changes from a stable line to folded geometry, return ownership to `niagara-vfx-artist`.

## Official Sources

- Niagara Renderers reference, Ribbon UV tiling distance and age offset behavior: https://dev.epicgames.com/documentation/unreal-engine/render-module-reference-for-niagara-effects-in-unreal-engine
- Coordinates Material Expressions, `TextureCoordinate` UV output: https://dev.epicgames.com/documentation/de-de/unreal-engine/coordinates-material-expressions-in-unreal-engine
- Utility Material Expressions, `DepthFade` and `LinearInterpolate`: https://dev.epicgames.com/documentation/unreal-engine/utility-material-expressions-in-unreal-engine
