# Official Doc Notes

Use these notes as source-backed anchors, then verify details against the current engine version and project. Last web check: 2026-05-11.

## Epic Documentation Links

- Main Material Node and Material Inputs: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-the-main-material-node-in-unreal-engine
- Material Expressions Reference: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-material-expressions-reference?application_version=5.7
- Custom Material Expressions: https://dev.epicgames.com/documentation/en-us/unreal-engine/custom-material-expressions-in-unreal-engine?application_version=5.7
- Viewport Modes and Shader Complexity: https://dev.epicgames.com/documentation/en-us/unreal-engine/viewport-modes-in-unreal-engine
- Materials landing page: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-materials
- Niagara Mesh Material Override API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/FNiagaraMeshMaterialOverride
- Niagara Renderer MID behavior: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/Niagara/UNiagaraRendererProperties/NeedsMIDsForMaterials

## Practical Takeaways

- The Main Material Node exposes inputs that change based on Material Domain, Blend Mode, and Shading Model. Do not audit an input in isolation without checking those material properties.
- Material Expressions define the building blocks of graph authoring; read the graph as a dataflow program from outputs backward.
- Custom Material Expressions allow HLSL, but they can reduce visibility and may prevent some graph-level optimizations. Use them intentionally, not as a default replacement for clear native nodes.
- Shader Complexity view modes are helpful but incomplete. Epic's docs note that Shader Complexity is based on instruction count and does not always reflect texture sample cost equally, so a material with fewer instructions can still be slower if it adds expensive sampling or bandwidth pressure.
- Niagara renderer materials must match the renderer carrier. Mesh material overrides can use explicit material interfaces or user parameter bindings, and renderer MID behavior means material parameters may be driven from Niagara simulation variables. Audit the renderer contract before judging the material in isolation.

## Verification Habit

When the engine version matters, browse official docs for the active version and inspect the asset through UnrealBridge. Treat web docs as the capability map and live asset readback as ground truth.
