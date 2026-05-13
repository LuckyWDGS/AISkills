---
name: unreal-material-artist
description: Use when Codex needs a Material/Shader Specialist for Unreal Engine material work, including designing, authoring, reading, reviewing, optimizing, or debugging Materials, Material Instances, Material Functions, Material Layers, Material Attributes, Substrate, texture plans, Custom HLSL nodes, shader complexity, instruction and sampler budgets, material graph cleanup, or cm-imagegen texture generation for UE assets. Trigger for requests about UE material nodes, material domains, blend modes, shading models, texture-vs-procedural tradeoffs, material performance, VFX material shaders, Niagara renderer materials, mesh/surface/landscape/foliage/character/environment/UI/post-process/decal/light-function/volume/RVT materials, specialized shading models such as Hair, Cloth, Eye, Clear Coat, Subsurface, Single Layer Water, Thin Translucent, or audits of existing material assets.
---

# Unreal Material Artist

## Overview

Use this skill as the Material/Shader Specialist for production-facing Unreal Engine material work: turn a visual target into a usable material, read and critique existing graphs, decide when textures beat pure math, generate needed texture assets, write or review HLSL, and validate performance before calling the asset done.

Treat material work as both art direction and engineering. A material is not finished just because it compiles; it must read correctly in context, expose useful controls, avoid dead graph branches, and fit the target platform.

Default team model:

- `niagara-vfx-artist` is the VFX Lead for complete effects, layer/carrier direction, emitter behavior, integration, preview, and final effect acceptance.
- `unreal-material-artist` is the material expert for shader graph implementation, texture strategy, HLSL, material performance, and material audit.
- For full Niagara VFX tasks, accept the material contract from Niagara, implement or review only the material route, then return required material inputs, carrier assumptions, and performance risks so Niagara can wire, preview, and tune the whole effect.
- Do not override Niagara carrier or timing decisions unless the material route proves them technically impossible or unnecessarily expensive; report that tradeoff back as a recommendation.
- Do not treat live Niagara system reads, Niagara parameter writes, renderer-binding hookup, emitter graph inspection, rapid-iteration ownership tracing, or real-system semantic plumbing as this skill's core responsibility. Those belong to `niagara-vfx-artist`.

## Core Workflow

1. Capture the material target.
   Identify domain, carrier, target platform, camera distance, blend mode expectations, lighting model, texture availability, runtime controls, and whether the material is for mesh, sprite, ribbon, decal, UI, post process, landscape, or surface shading.

2. Create or request a material contract for effect work.
   For Niagara/VFX layers, record renderer carrier, UV expectations, Particle Color, Dynamic Parameters, texture channels, blend mode, sorting risk, and platform budget before graph work. Use [references/material-contract-and-tooling.md](references/material-contract-and-tooling.md) and `tools/material_contract.py`.

3. Read before writing.
   For existing assets, inspect `MaterialInfo`, graph outputs, expression nodes, parameter lists, Material Instance override chains, compile errors, instruction counts, sampler counts, and stale overrides before editing or tuning.

4. Choose texture versus computation deliberately.
   Use [references/texture-vs-compute.md](references/texture-vs-compute.md) when the material might use procedural noise, masks, flow, distance fields, flipbooks, atlases, or baked lookup textures.

5. Search the reusable asset library before generating.
   Use [references/material-asset-library.md](references/material-asset-library.md) and `tools/material_asset_library.py search`. Reuse `approved` assets first. Only generate a new texture when the library does not already have a suitable reviewed asset.

6. Build the material route.
   Prefer clear graph nodes for ordinary math and engine-tracked texture samples. Use Custom HLSL only when it meaningfully improves fidelity, reduces graph complexity, or implements math that nodes cannot express cleanly.

7. Plan, generate, and QA textures when needed.
   Read [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md), [references/texture-prompt-framework.md](references/texture-prompt-framework.md), and [references/generated-texture-qa.md](references/generated-texture-qa.md). Use `C:/Users/QY/.codex/skills/cm-imagegen/SKILL.md` for actual image generation, then run `tools/texture_asset_report.py` before treating generated files as UE-ready. If a generated asset passes review and looks reusable, register it into the library. If it fails review, reject or regenerate it instead of silently keeping it as future stock.
   For foliage or vegetation cards, missing leaf diffuse/alpha or a believable leaf-card carrier is an asset gap to resolve, not just a visual caveat: search the `foliage` library category first; if no approved asset fits, use `cm-imagegen` from the user's reference image when available, QA with `--role foliage`, import/audit/fix settings, then preview on a masked two-sided card.

8. Audit and self-review.
   Use structural checks first, then controlled previews or in-level captures. Read [references/material-audit-workflow.md](references/material-audit-workflow.md) for the review loop and CLI tool. Use `tools/material_preview.py` for repeatable mesh, shaderball, complexity, parameter sweep, and carrier previews. Treat any sprite/ribbon preview here as a material-side carrier harness, not as ownership of a production Niagara system.

9. Check domain, blend, shading model, and render contract for non-standard materials.
   For UI, post process, decal, light function, volume, RVT, Substrate, layered materials, water, glass, skin, hair, cloth, foliage, or other specialized materials, read [references/material-domain-and-rendering-contracts.md](references/material-domain-and-rendering-contracts.md), [references/substrate-and-material-layers.md](references/substrate-and-material-layers.md), and [references/specialized-shading-models.md](references/specialized-shading-models.md) as needed. Run `tools/material_domain_audit.py` when UnrealBridge is available.

10. Use case studies for external references.
   When matching an online material tutorial or reference, read [references/material-case-study-playbook.md](references/material-case-study-playbook.md). Extract the source contract, build a minimal UE reproduction, audit/read back the asset, preview on the closest carrier, then record whether mismatches are structural, visual, texture, carrier, or engine-version issues.

11. Report tradeoffs clearly.
   Explain the material output chain, material contract, required material inputs, performance risks, required textures, import settings, platform fallback, and any unresolved visual gap.

## Hard Rules

- Do not rely on screenshots of the Material Editor graph as proof. Read the material graph and output connections through tooling when possible.
- Do not leave dead branches, stale MI overrides, or mystery parameters in a production material after the route is confirmed.
- Do not sample textures manually inside Custom HLSL when a normal TextureSample node keeps UE dependency tracking, sampler state, and audit visibility clearer.
- Do not assume lower instruction count means cheaper if the "optimization" adds large textures, many samples, high overdraw, expensive translucency, or poor cache locality.
- Do not generate final textures from text alone when a design/reference image is available. Cache or use the reference and pass it into `cm-imagegen` as an image input.
- Do not accept a foliage material as visually matched when it only has constant colors or a solid plane; leaf/bush materials need a diffuse/alpha texture or separate opacity mask plus a believable card/cluster carrier.
- Do not treat AI-generated Flow Maps, Normal Maps, packed masks, or precision lookup textures as final without technical validation; generate drafts only, then verify channels and import settings.
- Do not use ordinary color/sRGB white textures as defaults for mask, packed, ORM, roughness, metallic, opacity, flow, or scalar-data sampler slots. Their placeholder textures must match the sampler role, such as `TC_Masks` plus `sRGB=false` for Masks data, or the material can compile incorrectly before any artist texture is assigned.
- Do not skip the reusable asset library search when the task needs generic texture building blocks such as noise, masks, distortion, ramps, atlases, or flipbooks.
- Do not treat every generated image as reusable stock. Only `approved` library assets are default reuse candidates.
- Do not read, trace, debug, or write live Niagara emitter/system parameter wiring as part of this skill. Return the material-side contract and let `niagara-vfx-artist` own the real Niagara hookup.

## Performance Judgment

When judging cost, consider all of these:

- Shader math: instruction count, expensive functions, loops, branches, Custom HLSL, feature/quality switches.
- Texture cost: sample count, sampler sharing, texture size, format, mips, filtering, bandwidth, cache behavior, virtual texture stacks, and channel packing.
- Blend and visibility: translucent overdraw, depth fade, refraction, masked alpha cost, two-sided shading, pixel coverage, sorting, and particle count.
- Platform: PC can carry richer materials; Android and low-end targets need fewer samples, smaller textures, additive/unlit defaults, and aggressive fallbacks.
- Runtime control: Dynamic Parameters, Material Parameter Collections, Niagara user params, and per-instance overrides should be intentional and named for use, not for node history.

Use `FeatureLevelSwitch`, `QualitySwitch`, material instances, and texture LOD/import settings when the target platform has materially different budgets.

## Tooling

Create or validate a Niagara-to-material contract:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_contract.py new --effect WingEcho --layer RibbonTrail --renderer ribbon --blend-mode Additive --platform PC --markdown
```

Use the material audit CLI when UnrealBridge is available:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Path/M_Material --project UnrealAI --markdown --instruction-budget 120 --sampler-budget 4
```

Audit material domain, blend mode, shading model, output pins, and render-contract risk:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_domain_audit.py /Game/Path/M_Material --project UnrealAI --markdown
```

Inspect generated or external texture files:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py D:/Textures/WingEcho --role flipbook --grid 8x8 --markdown
```

Audit Unreal texture import settings:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_import_audit.py /Game/Textures/T_WingEchoAtlas.T_WingEchoAtlas --role atlas --grid 4x4 --project UnrealAI --markdown
```

Fix Unreal texture import settings, single or batch:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_import_fix.py /Game/Textures/T_WingEchoMask.T_WingEchoMask --role mask --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_import_fix.py --batch-spec D:/specs/texture-import-fix-batch.json --project UnrealAI --markdown
```

Render material previews or parameter sweeps:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_WingEcho --project UnrealAI --with-complexity --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_WingEcho --carrier sprite --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_WingEcho --carrier ribbon --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_WingEcho --carrier sprite_card --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_WingEcho --carrier ribbon_card --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_WingEcho --carrier decal --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/PP_WingEcho --carrier post_process --project UnrealAI --width 320 --height 180 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py sweep /Game/Materials/MI_WingEcho --param-name Roughness --value 0.1 --value 0.3 --value 0.6 --project UnrealAI --markdown
```

Batch-create and parameterize material instances:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_instance_batch.py D:/specs/wingecho-mi-batch.json --project UnrealAI --preview --markdown
```

Trace material-side parameter sources:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/runtime_param_trace.py /Game/Materials/MI_WingEcho --project UnrealAI --markdown
```

Pack channels or normalize flipbooks:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/channel_packer.py --r D:/Masks/AO.png@L --g D:/Masks/Roughness.png@L --b D:/Masks/Metallic.png@L --a D:/Masks/Opacity.png@L --markdown
python D:/Skills/skills/unreal-material-artist/tools/flipbook_normalizer.py D:/Flipbook/Frames --grid 8x8 --cell-size 256 --markdown
```

Search or register reusable texture assets:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py search --category noise --role surface --power-of-two --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py register D:/Temp/new_noise.png --stage candidates --category noise --role surface --tags seamless,organic --qa-status candidate
```

Reports write under:

```text
<project>/.codex/session/material-delivery/
```

The tools cover graph output chains, dead branches, stale MI overrides, compile findings, instruction count, sampler count, material contracts, material-side parameter traces, reusable asset-library search and promotion, generated texture dimensions, atlas grids, alpha availability, role-specific texture warnings, Unreal import settings, mesh and carrier preview renders, batch MI authoring, channel packing, and flipbook cleanup.

Current preview carrier note:

- `sprite` and `ribbon` previews now default to temporary Niagara-system harnesses, so they are closer to true Niagara sprite/ribbon renderer output than plain cards.
- `sprite_card` and `ribbon_card` keep the older cheap card-based approximation path for quick checks.
- `decal` preview uses a temporary wall plus `DecalActor`.
- `post_process` preview uses a temporary preview volume plus neutral scene geometry.
- Even the Niagara-based preview modes are still lightweight harnesses, not a full gameplay Niagara integration test.
- These previews exist only to review material behavior on likely carriers. Real Niagara system bindings, live parameter sources, and runtime writebacks remain Niagara-owned.

## Reference Map

- [references/material-audit-workflow.md](references/material-audit-workflow.md)
  Use for review, cleanup, live-graph readback, stale override detection, and acceptance criteria.

- [references/material-contract-and-tooling.md](references/material-contract-and-tooling.md)
  Use for Niagara-to-material handoffs, delivery contracts, tool selection, and the material specialist capability roadmap.

- [references/tech-art-material-systems.md](references/tech-art-material-systems.md)
  Use when the task is really about technical-art material systems: master/function layering, runtime ownership, MPC vs MID vs Niagara, and project-wide material architecture.

- [references/material-domain-and-rendering-contracts.md](references/material-domain-and-rendering-contracts.md)
  Use when auditing `Material Domain`, `Blend Mode`, output pins, post process, UI, decal, light-function, volume, RVT, WPO/PDO, or whether a material is in the wrong render path.

- [references/material-case-study-playbook.md](references/material-case-study-playbook.md)
  Use when learning from online material examples, matching a reference material, creating UE reproductions, comparing audit/preview results to the source, and promoting reusable lessons.

- [references/substrate-and-material-layers.md](references/substrate-and-material-layers.md)
  Use for Substrate, Material Layers, Material Attributes, layered master materials, layer masks, BSDF layering, and layer-stack cost review.

- [references/specialized-shading-models.md](references/specialized-shading-models.md)
  Use for Hair, Cloth, Eye, Clear Coat, Subsurface, TwoSidedFoliage, Single Layer Water, Thin Translucent, FromMaterialExpression, or other non-DefaultLit shading decisions.

- [references/complex-master-material-playbook.md](references/complex-master-material-playbook.md)
  Use when designing or reviewing a large multi-feature master material for characters, environments, overlays, wetness, wear, detail systems, or heavy runtime control.

- [references/domain-landscape-foliage.md](references/domain-landscape-foliage.md)
  Use for landscape, foliage, RVT, masked overdraw, wind/WPO, and large-screen-coverage terrain/vegetation material decisions.

- [references/domain-character-environment.md](references/domain-character-environment.md)
  Use for character, armor, cloth, prop, and environment material domain decisions, especially runtime ownership and reuse strategy.

- [references/material-preview-presets.md](references/material-preview-presets.md)
  Use when the task depends on carrier-specific preview intent, especially Niagara sprite/ribbon presets, SubUV preview assumptions, decal preview, or post-process preview behavior.

- [references/material-asset-library.md](references/material-asset-library.md)
  Use when the task may reuse generic texture building blocks, when new generated assets should be categorized and promoted into a library, or when failed generated assets should be kept out of the approved reuse pool.

- [references/texture-vs-compute.md](references/texture-vs-compute.md)
  Use when deciding whether to bake detail into textures, compute it procedurally, use flipbooks/atlases, or simplify for platform cost.

- [references/material-node-map.md](references/material-node-map.md)
  Use for a compact map of major UE material node families, HLSL guidance, and how to read graph intent.

- [references/material-recipes.md](references/material-recipes.md)
  Use for reusable VFX/surface material setups, common node patterns, and platform-friendly material recipes.

- [references/master-material-architecture.md](references/master-material-architecture.md)
  Use when designing a project-wide master material system, parameter boundaries, instances, and fallback variants.

- [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md)
  Use when a material needs a single texture, flipbook, sprite atlas, flow map, mask, or generated texture plan.

- [references/texture-prompt-framework.md](references/texture-prompt-framework.md)
  Use when generating texture prompts or deciding whether a texture is appropriate for `cm-imagegen`.

- [references/generated-texture-qa.md](references/generated-texture-qa.md)
  Use when generating, accepting, rejecting, or importing AI-created textures, masks, atlases, flipbooks, ramps, flow maps, normals, or packed data.

- [references/official-doc-notes.md](references/official-doc-notes.md)
  Use when you need the source-backed principles behind UE material inputs, expression nodes, Custom HLSL, and performance view modes.

## Collaboration With Niagara VFX Artist

Use this skill for the material side of a Niagara effect: material master/instance design, texture needs, shader math, HLSL, graph audit, and material performance. It may declare required inputs such as `ParticleColor`, `DynamicParameter`, `SubImageIndex`, or `RibbonWidth`, but it does not own how a live Niagara system supplies them.

Use `niagara-vfx-artist` for the Niagara side: systems, emitters, renderers, events, simulation, user parameters, renderer bindings, emitter graph hookups, bounds, culling, and integration. When a task spans both, let this skill own the material and texture contract while Niagara owns carrier behavior, runtime effect structure, and every real Niagara read/write decision.
