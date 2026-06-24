# Official Doc Notes

Use these notes as source-backed anchors, then verify details against the active engine version and live project assets. Last web check: 2026-06-08. Public Epic docs inspected in this pass are Unreal Engine 5.7 unless a URL explicitly says otherwise.

## Epic Documentation Links

- Materials landing page: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-materials
- Material Properties: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-properties
- Material Inputs: https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine
- Material Editor UI, Stats, HLSL Code, and Platform Stats: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-editor-ui
- Material Analyzer: https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-material-analyzer-tool?lang=en-US
- Material Instances: https://dev.epicgames.com/documentation/unreal-engine/instanced-materials-in-unreal-engine?lang=en-US
- Material Parameter Expressions: https://dev.epicgames.com/documentation/en-us/unreal-engine/material-parameter-expressions-in-unreal-engine
- Material Functions: https://dev.epicgames.com/documentation/en-us/unreal-engine/material-functions-in-unreal-engine
- Layering Materials: https://dev.epicgames.com/documentation/en-us/unreal-engine/layering-materials-in-unreal-engine
- Using Material Layers: https://dev.epicgames.com/documentation/unreal-engine/using-material-layers-in-unreal-engine?application_version=5.7
- Substrate Materials Overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-substrate-materials-in-unreal-engine
- Textures in Unreal Engine: https://dev.epicgames.com/documentation/en-us/unreal-engine/textures-in-unreal-engine
- Streaming Virtual Texturing: https://dev.epicgames.com/documentation/unreal-engine/streaming-virtual-texturing-in-unreal-engine?lang=en-US
- Virtual Texturing Settings and Properties: https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-texturing-settings-and-properties-in-unreal-engine
- Texture Import Settings Project Settings: https://dev.epicgames.com/documentation/en-us/unreal-engine/texture-import-settings-in-the-unreal-engine-project-settings
- Performance Guidelines for Mobile Devices: https://dev.epicgames.com/documentation/unreal-engine/performance-guidelines-for-mobile-devices-in-unreal-engine?lang=en-US
- Rendering Features for Mobile Games: https://dev.epicgames.com/documentation/en-us/unreal-engine/rendering-features-for-mobile-games-in-unreal-engine
- Nanite Virtualized Geometry: https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine?lang=en-US
- Nanite Technical Details: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details
- Niagara Ribbon Tutorial: https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-ribbon-effect-in-niagara-for-unreal-engine
- Niagara Render Module Reference: https://dev.epicgames.com/documentation/unreal-engine/render-module-reference-for-niagara-effects-in-unreal-engine?lang=en-US
- Material Editing Blueprint API: https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/MaterialEditing
- `unreal.MaterialEditingLibrary` Python API: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary?application_version=5.7
- Unreal Python editor scripting: https://dev.epicgames.com/documentation/unreal-engine/scripting-the-unreal-editor-using-python?lang=en-US
- Material Parameter Collections: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-material-parameter-collections-in-unreal-engine
- Post Process Effects: https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-effects-in-unreal-engine
- Shading Models: https://dev.epicgames.com/documentation/en-us/unreal-engine/shading-models-in-unreal-engine
- Using Light Functions: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-light-functions-in-unreal-engine
- Epic clear coat tech blog: https://www.unrealengine.com/tech-blog/improved-shading-models-in-unreal-engine-4-25-and-beyond?lang=en-US

## Practical Takeaways

- Material properties are render contracts. `Material Domain`, `Blend Mode`, `Shading Model`, `Two Sided`, usage flags, mobile options, translucency settings, and Nanite override material all affect whether graph pins are meaningful and whether the asset renders on the intended carrier.
- Usage flags compile special material versions for the intended use. For Niagara/VFX work, explicitly check `Used with Niagara Sprites`, `Used with Niagara Ribbons`, `Used with Niagara Mesh Particles`, and `Used with Beam Trails` instead of trusting editor auto-detection.
- Material instances are the standard way to change exposed values without recompiling the parent material. Static switches and static component masks can still create permutation/storage pressure, so keep them sparse and audit instance groups.
- The Material Analyzer is a first-class project audit surface for descendant instances, base property overrides, static switches, static component masks, shader permutation savings, and data-storage savings.
- The Material Editor exposes Stats, Platform Stats, and generated HLSL views. Android Platform Stats require external compiler setup; report missing compiler setup as a validation gap.
- Substrate is no longer just old UE 5.6 beta guidance. In UE 5.7, new projects enable Substrate by default; upgraded existing projects stay non-Substrate unless opted in. Explicit conversion is permanent, and converted Substrate materials render black if Substrate is disabled.
- Substrate GBuffer choice matters. Blendable GBuffer favors speed and consistency; Adaptive GBuffer favors richer material complexity on supported SM6/current-generation platforms and simplifies elsewhere.
- Substrate materials should use the Substrate Stats panel and simplification/closure review. Prefer parameter blending on operators when it preserves the look and reduces cost.
- Material Layers and function-based layered materials are both valid. Use Material Layers for artist-editable instance stacks; use Material Functions/Attributes for graph-level reuse and controlled shipped masters.
- Textures can be visible color, masks, packed data, vectors, flipbooks, or technical lookup data. Set `sRGB`, compression, mips, LOD group, filter, and virtual-texture settings from the sampled role, not from the file extension.
- Power-of-two textures can mip and stream; non-power-of-two textures do not generate mips or stream. Treat generated texture dimensions as a technical gate before UE import.
- Streaming Virtual Texturing requires both per-texture Virtual Texture Streaming and virtual sampler types in materials. VT samples can cost extra lookups/stacks, so audit VT use rather than assuming it is free.
- Record project-level VT settings such as auto virtual-texturing thresholds and import behavior when texture streaming behavior is part of the material contract.
- Nanite material work needs a mesh/material contract. Check blend support, WPO displacement/clamping, UV interpolation assumptions, fallback mesh behavior, and Nanite override material before blaming only shader math.
- Mobile/Android material plans need concrete feature and quality-level gates. Use quality switches, simpler material instances, smaller packed textures, fewer translucent layers, and measured overdraw instead of generic "optimize mobile" advice.
- Official `UMaterialEditingLibrary` and Material Editing Blueprint API are source-backed create/connect/recompile/parameter/usage/statistics surfaces. Python scripting is editor-only, not a cooked runtime route.
- Public primary docs were found for `UMaterialEditingLibrary`, but not for this skill's local `toolset_registry.toolsets.core.material.MaterialTools`, `MaterialInstanceTools`, or `TextureTools` names. Keep those behind runtime availability checks and local smoke-test evidence.
- Niagara renderer materials must match the renderer carrier. The material skill may declare required inputs such as `ParticleColor`, `DynamicParameter`, `SubImageIndex`, or ribbon UV assumptions; live renderer bindings remain Niagara-owned.

## Verification Habit

When the engine version matters, browse official docs for the active version and inspect the asset through UnrealBridge or verified editor tooling. Treat web docs as the capability map, local tool availability as runtime evidence, and live asset readback as ground truth.
