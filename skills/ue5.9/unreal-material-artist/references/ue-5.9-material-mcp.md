# UE 5.9 native material control

Verified on UE 5.9.0 Preview, CL 60351404, on 2026-11-11. These are live MCP
results from isolated candidate assets. They do not establish UE 5.8 runtime
compatibility, target-platform costs or visual approval.

For the second-pass StaticMesh quality/collision getters, Texture pixel
read/export, transient Geometry and untested TextureGraph authoring surface,
read the shared [geometry / texture reference](../../unreal-engine-mcp/references/ue-5.9-geometry-texture-tools.md).

## Discovery and routing

Read the core [5.9 audit](../../unreal-engine-mcp/references/ue-5.9-preview-audit.md)
first. Discover `EditorToolset.MaterialToolset`, `MaterialInstanceToolset`,
`ObjectToolset` and `AssetToolset`. The suffixes are unique in the inspected
inventory. Native methods and arguments use PascalCase and camelCase,
respectively; old Python names such as `MaterialTools.create_material` are a
different contract.

Use native MCP for each covered operation. For dependent batches, read
`PythonScriptingTools.read_me`, look up the exact tool signatures with
`get_symbol`, and use `await call_tool(full_name, **arguments)`. Public Python
APIs in `execute_python` fill an identified native-tool gap. The existing
5.8 recipe/audit executors require separate validation before use on 5.9;
renaming only their toolset cannot translate their arguments or return values.

## Author and verify

The tested route is:

1. `CreateMaterial(folderPath, assetName)` returns a UObject `refPath`.
2. `ListExpressionClasses(materialOrFunction, search)` returns the real class
   references. Pass one to `AddExpression(materialOrFunction, expressionClass, x, y)`.
3. Find editable fields with `ObjectToolset.ListProperties`; use
   `GetPropertySchema` when types, enum values or bounds matter. Set fields
   with `SetProperties(instance, values)`, where `values` is a JSON **string**.
4. Wire `ConnectToOutput(expression, outputName, materialProperty)` or
   `ConnectExpressions`; discover input names with `GetExpressionInputNames`.
   An unnamed function-output input was returned as `"None"` in this build.
5. Read `GetPropertyInput` / `GetExpressionInputs` and the changed values back,
   then `Recompile`. Save the intended asset with `AssetToolset.SaveAsset` and
   check `IsDirty` separately.

An authored scalar parameter used `parameterName`, `defaultValue`, `group` and
`desc`. Chinese group/description text and a `MaterialExpressionComment.text`
round-tripped correctly. Preserve production parameter identifiers when adding
Chinese descriptions and stable module IDs.

`GetPropertySchema(instance, root, maxDepth)` describes types rather than a
specific array element. For example `root="scalarParameterValues"` on a material
instance exposed the element's `parameterInfo` and `parameterValue`, including
the nested association enum. Root cannot contain an array subscript. Discover
property names first: material graph inputs such as roughness are read through
the material tools and are not necessarily reflected properties on `Material`.

Property writes enforce edit conditions and representable types. A scalar
parameter's `enumerationIndex` write was refused while its control type was
Numeric. After selecting EnumerationIndex in an earlier call, a negative value
was refused as outside uint8's range. Both refusals left the original value
unchanged. Read back after any failure; this observation does not make arbitrary
multi-property writes atomic.

## Statistics and diffs are native

`GetStatistics(material)` accepts a Material or MaterialInstance and reports
the current shader platform's compiled statistics:

| Returned field | Use |
|---|---|
| `num_pixel_shader_instructions`, `num_vertex_shader_instructions` | Compiled instruction counts |
| `num_samplers` | Sampler usage |
| `num_pixel_texture_samples`, `num_vertex_texture_samples` | Texture sample counts |
| `num_virtual_texture_samples` | Virtual-texture samples |
| `num_uv_scalars`, `num_interpolator_scalars` | Varying usage |

The test material returned 187 pixel instructions, 147 vertex instructions and
one sampler. These values are evidence that the native route works, not a
budget or GPU timing estimate. Recompile and record the actual platform and
material settings for a production comparison. A completed `Recompile` call,
statistics and a visual/runtime acceptance result are separate evidence.

`DiffMaterial(oldAssetPath, newAssetPath)` and
`DiffFunction(oldAssetPath, newAssetPath)` returned empty strings for identical
duplicates. Changing a scalar default produced a text diff identifying
`defaultValue`, including float precision. Diffs can inspect the loaded asset
state; do not infer that a nonempty diff was saved.

## Live coverage and limits

| Area | Verified evidence |
|---|---|
| Material graph | Create, scalar parameter, Chinese descriptions/comment, output connection readback, recompile and scoped save |
| Material function | Create output/value nodes, connect using discovered input name, recompile, identical/changed diffs |
| Material instance | Create from parent, list parameter, set 0.8 scalar override and read it back within float tolerance |
| Reflection | Nested instance schema, edit-condition/type refusals with unchanged-value readback |
| Persistence | Five material/function/instance candidates saved; each `IsDirty=false` |

No material appearance, runtime MID/MPC behavior, cook, mobile shader platform,
Substrate/layer editing or texture-import regression was exercised by this
acceptance pass. Use the existing domain workflows and their own acceptance
criteria for those operations.

Saving or compiling can start an editor slow task. This build sometimes
responded `Not run ... made no changes` to a subsequent request, including
schema discovery. Wait for that task to finish and retry the explicitly
unexecuted operation. A timeout has unknown completion and requires readback
before any retry.

## Parameter palettes for gameplay assets

A separate 5.9 task authored one default-lit, opaque master and ten palette
instances for a lightweight platform game. The master used vector parameters
`BaseColor` and `EmissiveColor`, scalar parameters `Roughness`, `Metallic` and
`EmissiveStrength`, and a multiply for emission. A Chinese comment and parameter
descriptions documented the purpose while preserving those stable identifiers.

Native `MaterialInstanceToolset.Create(folderPath, assetName, parent)`,
`SetVectorParameter(instance, name, value)` and
`SetScalarParameter(instance, name, value)` built the instances. Readback
confirmed float overrides; scoped saves and `IsDirty=false` confirmed persistence.
The master retained its graph after native `AssetToolset.Move(path, newPath)`;
new instance referencers resolved to its corrected path. These operations are
retained native authoring, not all newly introduced features.

Useful acceptance rules:

- Build a shared master when the palette changes colour/roughness/emission;
  avoid duplicating the full graph for each object. Check linear colours in the
  actual lighting and exposure before approving the palette.
- Inspect the graph and compiled statistics independently. This parameter-only
  graph had no texture-sample expression nodes, yet compiled statistics reported
  one sampler and three pixel texture samples from the compiled engine pass.
  A zero-sampler assertion would misclassify valid output.
- A saved MI override is an asset-authoring result. Runtime MID changes need
  an actual component/material slot and gameplay evidence; matching parameter
  names alone does not prove that the runtime instance is assigned or visible.
- Inspect redirectors/referencers at the exact old path after a move. If that
  path is already absent, no deletion or broad fixup is needed. Never clean a
  whole production folder merely because a candidate was moved.

This palette pass covered structural edits, recompile, readback and clean saves.
In-context visual and gameplay results are separate acceptance records. For
World Cache/AVBOIT, Canvas generation or external Fab assets, first consult the
[production-feature matrix](../../unreal-engine-mcp/references/ue-5.9-production-feature-matrix.md);
ordinary material authoring does not test those services or renderer modes.

## Reimported glTF material instances

In the UE 5.9 kitchen scene, Interchange replaced meshes and returned newly created materials while reusing earlier instances and textures. Four reused instances still had their old `BaseColorFactor`. Their slots pointed to the expected materials, yet the oak and enamel colours were visibly different from the revised source.

1. Read the source glTF material and the intended overrides for this asset. Compare `baseColorFactor` as linear RGBA, including the tint when a base-colour texture is present. Resolve `baseColorTexture.index → textures[index].source → images[source]` and match that image to the imported texture object in the target library. Compare roughness and metallic as separate factors.
2. Read the actual instance parent and its `scalarParameterValues`, `vectorParameterValues` and `textureParameterValues` via `ObjectToolset.GetProperties`. These arrays describe explicit overrides. Where an entry is inherited, query the effective value from the parent/instance parameter contract. This Interchange parent exposed `BaseColorFactor`, `BaseColorTexture`, `RoughnessFactor` and `MetallicFactor`. Look up names on the active parent. For layered instances also preserve parameter association and index.
3. For a source-owned global parameter with an unambiguous name, use `MaterialInstanceToolset.SetScalarParameter` or `SetVectorParameter` to correct a mismatch. For a wrong texture binding, the exposed `SetTextureParameter(instance, name, value)` takes the texture object reference. Check the exact returned path with `GetTextureParameter` before saving. The kitchen's texture bindings already matched. When the project has art-directed overrides, compare the previous import, the current MI and the revised source before changing it. Read each changed parameter back and verify both the mesh's named slot and the placed component's override. Check a close view under the scene's intended exposure before adjusting lighting or roughness again.
4. If the import log flags an unsupported material on a window pane or bottle, inspect the slot's effective blend mode and `StaticMeshToolset.IsNaniteMesh`. For a mesh that needs translucency on this build, a tested path is `SetNaniteEnabled(mesh, bEnabled=false)`. This rebuilds the mesh. Save it, read its state back, and inspect transparency in the next UE render. Keep decisions about opaque geometry separate and measure target-platform cost where relevant.

For module bounds, placement and saved-level checks, see [photo-based interiors](../../unreal-engine-mcp/references/ue-5.9-reference-interiors.md). For three-way review and selected updates to global glTF MI parameters, use [the reimport workflow](../../unreal-engine-mcp/references/ue-5.9-reimport-reconciliation.md).

## Fixed-camera surface comparisons

Use the approved camera and manual exposure. Record its actor path, pose, FOV,
aspect ratio, output dimensions, render pass and the rectangle occupied by the
surface. Photograph the full composition and a grazing close-up. Repeat the
baseline once to measure variation from the renderer. Compare one material or
parameter family at a time, then render the combined choice. On a modular
interior, overriding a named component slot keeps the same mesh, UVs, camera
and lights across both frames.

In the tested 5.9 glTF Substrate parent, enumerate the available switch and
texture parameter names first. Use a child of the imported MI. Import the
metallic/roughness image as linear data (`sRGB=false`, `TC_Masks`).
The green channel encodes roughness and blue encodes metallic. When the map
already contains the target roughness, set `RoughnessFactor=1`. A white
blue channel retains the inherited metallic factor. Pair
`MetallicRoughnessTexture` with `bHasMetallicRoughnessTexture=true`.
For a separate tangent-space normal trial, parent a second MI to that child,
use `TC_Normalmap`, disable sRGB, and pair `NormalTexture` with
`bHasNormalTexture=true`. These exact names belong to this parent. Use the
native MI getters to read back the texture, switch and effective scalar, then
check the binding on the actual component by slot name.

The kitchen comparison used a 1080 × 720 sink shot. In a 275 × 46 pixel region
on the basin, the mean absolute RGB difference between repeated baseline
frames was 0.14 on an 8-bit scale. Strong directional roughness changed that
region by 11.87 and left broad stripes. A finer, lower-amplitude roughness
map changed the same region by 0.78 against its matching geometry baseline.
We retained the fine brush on the metal. The tile and quartz trials included
separate roughness-only and roughness-plus-normal frames. Their close-ups
gave too little visual improvement to justify promoting the additional maps.
Those numbers describe the named captures. Use each shot's own repeat and
surface region to interpret its result.

Static switch edits in a child can leave an engine master marked dirty in
the test editor. Inspect its pre-test dirty state. Save only the candidate
packages. In this isolated run, reloading the previously clean master from
disk cleared that transient change and its file hash was unchanged across
the reload. Inspect the final candidate after reloading.

## Thin-translucent cockpit and masked markings

A 5.9 Preview / CL 60351404 hard-surface asset used three model masters:
opaque PBR, thin translucent glass and masked markings, with thirteen named
material slots. The local modeling/import workflow is documented in
[reference-guided meshes](../../unreal-engine-mcp/references/ue-5.9-reference-mesh.md).

For the tested glass route, discover and set `blendMode=BLEND_Translucent`,
`shadingModel=MSM_ThinTranslucent` and `twoSided=true`, then set the dependent
`translucencyLightingMode=TLM_SurfacePerPixelLighting` in a later call.
Read back after a rejected multi-property write: independent fields may have
changed even when a dependent field was refused. This is not an atomic edit.
Use the exact class returned for `MaterialExpressionThinTranslucentMaterialOutput`;
connect a vector parameter to its discovered `TransmittanceColor` input.
Connect scalar Opacity, Roughness and Specular parameters to their material
outputs. Setting only the ThinTranslucent shading model leaves an incomplete
graph and can produce a temporary compile error during construction.

In this scene, linear transmission colour `(0.82, 0.52, 0.20)`, opacity 0.22
and roughness 0.12 gave amber glass with visible seat and instruments. These are
scene-specific starting values. `refractionMethod=RM_None` was used; this does
not validate refraction. The double-sided glass and interior were checked in
real SceneCapture images, separately from graph/property and MI readback.
The glass was substantially more expensive than the opaque master in native
shader statistics; static desktop rendering does not establish a mobile budget.

For an RGBA colour-and-cutout atlas, use TextureSampleParameter2D RGB to
BaseColor and A to OpacityMask. Set `BLEND_Masked` first, then set the dependent
`opacityMaskClipValue` in a subsequent call. Keep sRGB enabled for colour RGB;
alpha remains the mask. Read back compression/alpha preservation and the actual
RGBA texture, plus the MI texture override. The carrier in this test was a
thin mesh card, not a DeferredDecal. Correct sample wiring does not prove
orientation or surface contact; inspect each carrier's UV and grazing views.

After finishing the graph, recompile the final masters and inspect a bounded
new log interval. Keep historical construction failures separately: scanning
all old log entries can misreport a repaired material as currently failed,
while clearing logs would discard useful evidence. Save the intended masters,
instances, mesh bindings and level, and verify their dirty state independently.

## Unlit world-height backdrop

A second saved material used native `WorldPosition`, `ComponentMask`,
`SmoothStep`, two `VectorParameter` expressions and `LinearInterpolate`.
Select exact class refs: class search for ComponentMask and LinearInterpolate
also returns other expression classes, so the first result is not reliable.
The live mask fields were `r/g/b/a`; SmoothStep fields were `constMin/constMax`.
Its discovered inputs were `Min`, `Max`, `Value`; Lerp used `A`, `B`, `Alpha`.

The graph took absolute world Z, applied SmoothStep(-500, 1800) in centimetres,
blended two linear colours and connected directly to `MP_EmissiveColor`.
`shadingModel=MSM_Unlit`, `twoSided=true`, `blendMode=BLEND_Opaque` all read
back correctly. Chinese parameter groups/descriptions and a comment survived
readback. `GetExpressions` included the comment: six shader expressions plus
one comment, rather than six returned objects. Recompile, graph readback and
the scoped clean save passed; geometry placement and gameplay appearance
remain separate validation. Compiled statistics were 103 pixel instructions,
147 vertex instructions, zero samplers and three pixel texture samples for
this configuration, not a general platform budget.
