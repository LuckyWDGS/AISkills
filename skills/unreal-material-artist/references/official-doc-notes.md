# Official Doc Notes

Use these notes as source-backed anchors, then verify details against the current engine version and project. Last web check: 2026-05-12.

## Epic Documentation Links

- Main Material Node and Material Inputs: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-the-main-material-node-in-unreal-engine
- Material Expressions Reference: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-expressions-reference?application_version=5.7
- Custom Material Expressions: https://dev.epicgames.com/documentation/en-us/unreal-engine/custom-material-expressions-in-unreal-engine?application_version=5.7
- Material Functions Overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-functions-overview?application_version=5.6
- Creating and Using Material Functions: https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-and-using-material-functions-in-unreal-engine?application_version=5.6
- Using Fresnel in Your Unreal Engine Materials: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-fresnel-in-your-unreal-engine-materials
- Textures in Unreal Engine: https://dev.epicgames.com/documentation/en-us/unreal-engine/textures-in-unreal-engine?application_version=5.6
- Viewport Modes and Shader Complexity: https://dev.epicgames.com/documentation/en-us/unreal-engine/viewport-modes-in-unreal-engine
- Materials landing page: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-materials
- Material Properties: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-properties?application_version=5.6
- Material Inputs: https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine?application_version=5.6
- Material Editor UI, Stats, HLSL Code, and Platform Stats: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-editor-ui?application_version=5.6
- Substrate Materials: https://dev.epicgames.com/documentation/en-us/unreal-engine/substrate-materials-in-unreal-engine?application_version=5.6
- Layered Materials: https://dev.epicgames.com/documentation/en-us/unreal-engine/layered-materials-in-unreal-engine?application_version=5.6
- Creating Layered Materials: https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-layered-materials-in-unreal-engine?application_version=5.6
- Using Material Layers: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-material-layers-in-unreal-engine?application_version=5.6
- Runtime Virtual Texturing: https://dev.epicgames.com/documentation/en-us/unreal-engine/runtime-virtual-texturing-in-unreal-engine?application_version=5.6
- Material Parameter Collections: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-material-parameter-collections-in-unreal-engine?application_version=5.6
- Post Process Materials legacy English page: https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-materials?application_version=4.27
- Post Process Effects: https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-effects-in-unreal-engine?application_version=5.6
- Shading Models: https://dev.epicgames.com/documentation/en-us/unreal-engine/shading-models-in-unreal-engine
- Using Light Functions: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-light-functions-in-unreal-engine
- Light Functions legacy English page: https://dev.epicgames.com/documentation/en-us/unreal-engine/light-functions?application_version=4.27
- Epic Wiki Two-Sided Foliage Material: https://michaeljcole.github.io/wiki.unrealengine.com/Two-Sided_Foliage_Material/
- Epic clear coat tech blog: https://www.unrealengine.com/tech-blog/improved-shading-models-in-unreal-engine-4-25-and-beyond?lang=en-US
- Niagara Mesh Material Override API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/FNiagaraMeshMaterialOverride
- Niagara Renderer MID behavior: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraRendererProperties/NeedsMIDsForMaterials

## Practical Takeaways

- The Main Material Node exposes inputs that change based on Material Domain, Blend Mode, and Shading Model. Do not audit an input in isolation without checking those material properties.
- Epic's Material Properties docs explicitly frame `Material Domain` as the intended use of a material and list specialized shading models such as Clear Coat, Two Sided Foliage, Hair, Cloth, Eye, Single Layer Water, Thin Translucent, and From Material Expression. Treat these as render contracts, not labels.
- Material Inputs documentation confirms that enabled inputs depend on `Blend Mode`, `Shading Model`, and `Material Domain`; if a pin is unavailable or ignored for that contract, graph work wired into it can be wasted.
- Material Expressions define the building blocks of graph authoring; read the graph as a dataflow program from outputs backward.
- Custom Material Expressions allow HLSL, but they can reduce visibility and may prevent some graph-level optimizations. Use them intentionally, not as a default replacement for clear native nodes.
- Material Functions are the right home for reusable material logic that would otherwise drift across many master materials.
- Fresnel is a good simple-case material study because it is visually obvious, cheap when kept node-native, and easy to audit: the rim term should feed a deliberate output such as Emissive or a controlled Lerp, not become an unexplained magic multiplier.
- Layered Materials and Material Layers are powerful for complex per-pixel blends, but Epic's docs warn they can become heavy because layers are evaluated and blended per pixel. Prefer geometry/material-element separation when it is cheaper and artistically sufficient.
- Substrate is documented by Epic as a Beta feature in UE 5.6. It is more expressive than the legacy fixed shading-model set, but should be treated as an expert route that needs platform, version, and cost review before shipping.
- Runtime Virtual Texturing is a material-system contract involving RVT assets, volumes, writers, samplers, and material types. RVT can cache large-area shading, especially landscapes and terrain decals, but the material nodes and RVT asset material type must match.
- Material Parameter Collections are global scalar/vector stores referenced by materials; use them for scene/level/global state, not actor-specific or per-particle variation.
- Post Process Materials should use the Post Process domain and usually output through Emissive Color. Scene data is read with SceneTexture/PostProcessInput routes, and Blendable Location affects precision, timing, and cost.
- Light Functions are materials that filter light intensity. They do not directly change light color, do not work on static lights, and have forward-rendering caveats, so keep them simple and intentional.
- The two-sided foliage tutorial's key contract is `Masked` + `TwoSidedFoliage` + `Two Sided`, with diffuse alpha/opacity, Subsurface Color, Specular, and Roughness exposed for instances.
- Epic's clear coat writeup states that setting the Clear Coat shading model enables Clear Coat and Clear Coat Roughness inputs. In bridge output names, audit these as `CustomData0` and `CustomData1`.
- Texture properties matter to shader correctness and cost: sRGB, compression, mip generation, LOD group, filter mode, virtual texture streaming, and power-of-two assumptions can change how a material looks and performs.
- Shader Complexity view modes are helpful but incomplete. Epic's docs note that Shader Complexity is based on instruction count and does not always reflect texture sample cost equally, so a material with fewer instructions can still be slower if it adds expensive sampling or bandwidth pressure.
- Material Editor Stats, Platform Stats, and generated HLSL views are useful review surfaces. Platform Stats may need external compiler setup for Android, so bridge/tool reports should note when platform stats are unavailable rather than pretending the material was fully benchmarked.
- Niagara renderer materials must match the renderer carrier. Mesh material overrides can use explicit material interfaces or user parameter bindings, and renderer MID behavior means material parameters may be driven from Niagara simulation variables. Audit the renderer contract before judging the material in isolation.

## Verification Habit

When the engine version matters, browse official docs for the active version and inspect the asset through UnrealBridge. Treat web docs as the capability map and live asset readback as ground truth.
