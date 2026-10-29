---
name: unreal-material-artist
description: Use when Codex needs a UE Material/Shader Specialist for material graph design, authoring, reading, review, optimization, debugging, texture strategy, import audits/fixes, Custom HLSL, Material Instances, Material Functions, Material Layers, Material Attributes, Substrate, shader complexity, sampler/instruction budgets, preview/regression baselines, delivery packages, acceptance gates, or official/editor material-tool bridge work. Trigger for Unreal material domains, blend modes, shading models, VFX/Niagara renderer materials, fire/flame/ember/smoke/heat-haze/lava/energy materials, landscape/foliage/character/environment/UI/post-process/decal/light-function/volume/RVT materials, specialized shading models, texture-vs-procedural tradeoffs, material function linting, shader permutation reports, and material asset audits.
---

# Unreal Material Artist

## Editor transport

Follow the [shared UE conventions](../unreal-engine-mcp/references/shared-conventions.md): background editor connections only, MCP first with
Python Remote Execution for a verified gap, and Chinese annotations on new or
modified material modules (comment frames, Chinese parameter groups and
descriptions, stable module IDs; existing parameter identifiers unchanged).

On UE 5.8+, use Epic's MCP directly through the sibling `unreal-engine-mcp/scripts/builtin_mcp.py`. Discover the active schema before calling MaterialTools, MaterialInstanceTools, ObjectTools, TextureTools, AssetTools, or ProgrammaticToolset. They are Epic engine plugins in 5.8.4; old `toolset_registry.toolsets.core.*` module names are historical and must not be hard-coded.

`tools/official_toolsets_bridge.py` calls MCP over HTTP and resolves aliases such as `material:get_expressions` from live discovery. UnrealBridge (custom plugin + TCP) is retired; there is no plugin transport.

Material graph creation, node reference readback, wiring, MI parameters, texture import, and exposed UObject properties use official MCP tools. Local file QA, manifests, image packing, and reports remain local. `tools/material_audit.py` reads through MCP (plus Remote Execution for shader statistics). The editor-connected modes of the older domain-audit, recipe-builder, MI-batch, import-fix, and preview scripts call retired `UnrealBridge*Library` APIs and fail fast until ported; their offline modes still work. Do the live step with MCP and feed its JSON into the local report code. See [references/official-toolsets-vs-local.md](references/official-toolsets-vs-local.md) for the list.

## Overview

Use this skill as the Material/Shader Specialist for production-facing Unreal Engine material work: turn a visual target into a usable material, read and critique existing graphs, decide when textures beat pure math, generate needed texture assets, write or review HLSL, and validate performance after the target look is proven.

Treat material work as both art direction and engineering. Default to effect fidelity first: build the intended look before optimizing it. A material is not finished just because it compiles or fits a budget; it must read correctly in context, expose useful controls, avoid dead graph branches, then be optimized as much as possible without breaking the confirmed look.

Default team model:

- `niagara-vfx-artist` is the VFX Lead for complete effects, layer/carrier direction, emitter behavior, integration, preview, and final effect acceptance.
- `unreal-material-artist` is the material expert for shader graph implementation, texture strategy, HLSL, material performance, and material audit.
- For full Niagara VFX tasks, accept the material contract from Niagara, implement or review only the material route, then return required material inputs, carrier assumptions, and performance risks so Niagara can wire, preview, and tune the whole effect.
- Do not override Niagara carrier or timing decisions unless the material route proves them technically impossible or unnecessarily expensive; report that tradeoff back as a recommendation.
- Do not treat live Niagara system reads, Niagara parameter writes, renderer-binding hookup, emitter graph inspection, rapid-iteration ownership tracing, or real-system semantic plumbing as this skill's core responsibility. Those belong to `niagara-vfx-artist`.

## Core Workflow

1. Capture the material target.
   Identify domain, carrier, target platform, camera distance, blend mode expectations, lighting model, texture availability, runtime controls, and whether the material is for mesh, sprite, ribbon, decal, UI, post process, landscape, or surface shading. If the user provides a reference image, online example, approved concept, or asks for a custom material, treat that visual target as the source of truth and record the style/fidelity contract before choosing reusable assets or performance shortcuts. For reference-driven work, use [references/reference-to-material-plan.md](references/reference-to-material-plan.md) and `tools/reference_to_material_plan.py` to create the first structured work order.
   Before authoring, lock a short intent contract whenever the request could be read in more than one way or contradicts a prior attempt. Explicitly record: visual source (`provided texture` vs `procedural shape`), carrier (`mesh/card/sprite/ribbon/unknown`), runtime owner (`Material Instance/MID/MPC/Blueprint/Niagara/particle`), reveal or flow space (`0-1 UV`, radial, angular, world space), and render path. If the user says variants of "not a strip/ribbon material", "cancel particle control", "only adjust in the Material Instance", "use this texture", or "do not draw the circle procedurally", those statements override visual similarity in screenshots and must be restated before graph work. Ask concise clarifying questions for any missing owner/source/carrier detail instead of inferring it from the image.
   If the latest user message corrects a prior route, run a correction checkpoint before any graph change: list the superseded assumption, the new explicit constraint, and the graph or parameter elements that must be absent. Treat phrases such as "not a strip", "not ribbon", "use this texture", "do not procedurally draw it", "cancel particle control", and "MI only" as hard negative requirements, not style hints.

2. Build the visual target first.
   Make the first usable material version prioritize the requested effect, reference fidelity, motion/readability, texture identity, and carrier match. Do not downgrade a custom look just because an early budget estimate looks high. Only simplify before the first visual pass when the requested route is technically impossible, unsafe, or clearly incompatible with the material domain.

3. Create or request a material contract for effect work.
   For Niagara/VFX layers, record renderer carrier, UV expectations, Particle Color, Dynamic Parameters, texture channels, blend mode, sorting risk, and platform budget before graph work. Use [references/material-contract-and-tooling.md](references/material-contract-and-tooling.md) and `tools/material_contract.py`.
   Do not add `ParticleColor`, `DynamicParameter`, Niagara user parameters, or particle age/progress inputs just because the material might be used by a particle renderer. Add those only when the user or effect contract names that runtime owner. When the requested owner is a Material Instance, expose scalar/vector/texture parameters on the master material, create or update the MI, and treat Niagara/particle work as assignment/integration only.
   Distinguish assignment from control. A material may be assigned to a Niagara or particle renderer while still being controlled only by a Material Instance. If runtime owner is `Material Instance`, Niagara usage flags and renderer assignment are allowed, but `ParticleColor`, `DynamicParameter`, particle age, Niagara user parameters, and renderer-bound progress inputs are forbidden unless the user explicitly reopens particle ownership.
   For Niagara Ribbon / trail materials, treat the renderer's default UV convention as `U = ribbon length` and `V = ribbon width`. Put trail flow, panning, noise scroll, and longitudinal tiling on raw `TexCoord0.U` / X by default, for example `Time * Speed -> Append(X, 0)` and tiling vectors such as `(Tiling_U, 1.0)`. Use raw `TexCoord0.V` / Y for width falloff and optional vertical wobble/distortion offsets. Do not pan along raw `TexCoord0.V` unless live renderer readback proves that the current carrier maps length to V, or the material deliberately contains a documented art-space UV remap. When the trail texture art is authored with its vertical sampling axis as the visible flow direction, explicitly build `Flow_UV = float2(TexCoord0.V, TexCoord0.U)` for texture sampling only, keep Time/Pan/Tiling on the sampling V axis, and keep all width masks on the original raw `TexCoord0.V`.
   For additive fire/flame/energy ribbon trails, read [references/niagara-ribbon-flame-trail.md](references/niagara-ribbon-flame-trail.md) before inventing channel semantics, artist parameters, Android fallbacks, or MI handoff rows.
   When a Ribbon/trail material shows stable split lines, hard width edges, or intersection cuts after Niagara geometry is proven stable, use [references/ribbon-trail-seam-debugging.md](references/ribbon-trail-seam-debugging.md) before adding ad hoc graph fixes.
   For wrapped mesh carriers such as cones, cylinders, tubes, or mesh light volumes, record UV seam and tiling constraints before tuning noise. If `UV.x` closes at `0/1`, horizontal noise/detail tiling such as `TileU` should be a positive integer unless the graph uses a seam-hiding projection route.
   For low-poly cone/cylinder/shell light-volume carriers, do not assume `VertexNormalWS` is smooth enough for Fresnel. A virtual radial normal from `LocalPosition.xy` can be tested as an explicit variant, but do not make it the default or keep it if it changes the intended falloff.
   For strongly tiled, stretched, or panned noise on wrapped meshes, record the mip/derivative strategy. When warped UVs create seam shimmer or mip discontinuity, prefer `TextureSample` `MipValueMode=Derivative` with `DDX/DDY` generated from clean base `TexCoord[0]`, not from the multiplied/panned UV.
   For `Additive` or `Translucent` materials on two-sided cards, shells, cones, cylinders, or dense particle stacks, record the expected visible layer count. `Two Sided + Additive` can visually double or multiply emissive energy because front faces, back faces, and overlapping primitives add together before bloom/exposure.
   For Niagara SubUV sprite materials, default `Two Sided` to off because the renderer is normally camera-facing; enable it only for a documented non-camera-facing mesh/card route. Name Niagara/VFX texture assets with a trailing `_VFX` suffix, for example `T_FireFlipbook_VFX`.
   When parameters will be handed to Niagara, Blueprint, MID variants, or artists, use [references/material-parameter-schema.md](references/material-parameter-schema.md) and `tools/material_parameter_schema.py` to turn names/defaults into an explicit contract with units, ranges, runtime owners, write owners, tunability, and regression participation.

4. Read before writing.
   For existing assets, inspect `MaterialInfo`, graph outputs, expression nodes, parameter lists, Material Instance override chains, compile errors, instruction counts, sampler counts, and stale overrides before editing or tuning.

5. Choose texture versus computation deliberately.
   Use [references/texture-vs-compute.md](references/texture-vs-compute.md) when the material might use procedural noise, masks, flow, distance fields, flipbooks, atlases, or baked lookup textures.
   When the user names or provides a texture asset as the visual source, preserve that texture identity. Procedural math may reveal, mask, rotate, recolor, feather, or remap the texture, but must not replace the named texture with a procedurally drawn lookalike unless the user approves that substitution.

6. Search the reusable asset library before generating.
   Use [references/material-asset-library.md](references/material-asset-library.md) and `tools/material_asset_library.py search`. Reuse `approved` assets first only when they pass the material contract and reference-fidelity gate. In reference-driven or custom work, library assets are candidates, not authority: reject generic/simple matches that would change the intended style, scale, pattern language, color, motion, alpha shape, or material identity. Only generate a new texture when the library does not already have a suitable reviewed asset.

7. Build the material route.
   Prefer clear graph nodes for ordinary math and engine-tracked texture samples. Use Custom HLSL only when it meaningfully improves fidelity, reduces graph complexity, or implements math that nodes cannot express cleanly.

7.1. Verify versioned editor/tooling APIs before write-side mutations.
   Discover and call Epic's live MCP tools first. MaterialTools delegates standard graph operations to `UMaterialEditingLibrary`, so a custom wrapper is unnecessary when those tools cover the operation. Use returned UObject references for downstream edits; lack of a bridge-style GUID is not a capability gap. Check ProgrammaticToolset for batching. Use [references/official-toolsets-vs-local.md](references/official-toolsets-vs-local.md) and `tools/official_toolsets_bridge.py` for direct calls and saved evidence.

8. Plan, generate, and QA textures when needed.
   Start with [references/texture-strategy-selection-and-rules.md](references/texture-strategy-selection-and-rules.md) when choosing single texture vs Flipbook/SubUV vs atlas vs generated mask. Use [references/texture-prompts-vfx.md](references/texture-prompts-vfx.md) only when fire, ember, smoke, lightning, or related VFX prompt templates are needed, and use [references/texture-domain-foliage-water.md](references/texture-domain-foliage-water.md) for leaf-card or water-reference texture policy. [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md) is only the router. Also read [references/texture-prompt-framework.md](references/texture-prompt-framework.md) and [references/generated-texture-qa.md](references/generated-texture-qa.md) before generation. Use the installed sibling `cm-imagegen` skill for actual image generation, then run `tools/texture_asset_report.py` before treating generated files as UE-ready. If a generated asset passes review and looks reusable, register it into the library. If it fails review, reject or regenerate it instead of silently keeping it as future stock.
   When the material uses a full texture set, use [references/texture-set-pipeline.md](references/texture-set-pipeline.md) and `tools/texture_set_pipeline.py` to check BaseColor, Normal, RMA/ORM/MRA, Opacity, and Emissive together, emit import-fix batch specs, and pack Roughness/Metallic/AO when needed.
   When texture source, prompt, original file, import settings, repair history, packed-channel sources, or reuse rights matter, use [references/material-source-provenance.md](references/material-source-provenance.md) and `tools/material_source_provenance.py` before calling the texture set reusable.
   For foliage or vegetation cards, missing leaf diffuse/alpha or a believable leaf-card carrier is an asset gap to resolve, not just a visual caveat: search the `foliage` library category first; if no approved asset fits, use `cm-imagegen` from the user's reference image when available, QA with `--role foliage`, import/audit/fix settings, then preview on a masked two-sided card.

9. Audit and self-review.
   Use official structural checks first, then controlled previews or in-level captures through official scene/editor tools where exposed. Read [references/material-audit-workflow.md](references/material-audit-workflow.md) for the evidence model. Treat performance findings as evidence and triage, not automatic permission to lower the look. `tools/material_preview.py` remains a legacy bridge executor for specific uncovered preview needs; do not make it a prerequisite for normal material work. Treat any sprite/ribbon preview here as a material-side carrier harness, not as ownership of a production Niagara system.
   For master-material or MI-family cleanup, also use Unreal's Material Analyzer when the editor is available, and use `tools/shader_permutation_report.py` or `tools/permutation_budget_guard.py` when static switches/static masks are the risk.
   When one preview is too narrow, use [references/preview-matrix.md](references/preview-matrix.md) and `tools/preview_matrix.py` to plan or execute a matrix across background intent, exposure intent, distance, angle, time, parameter tier, quality, lighting, and carrier.
   For Additive/Translucent/Ribbon/Decal routes, use [references/translucency-sorting-probe.md](references/translucency-sorting-probe.md) and `tools/translucency_sorting_probe.py` to check material-side DepthFade/SoftParticle evidence plus optional Niagara sorting/bounds proof. Keep real Niagara System/Emitter/Renderer proof in `niagara-vfx-artist`.

10. Check domain, blend, shading model, and render contract for non-standard materials.
   For UI, post process, decal, light function, volume, RVT, Substrate, layered materials, water, glass, skin, hair, cloth, foliage, or other specialized materials, read [references/material-domain-and-rendering-contracts.md](references/material-domain-and-rendering-contracts.md), [references/substrate-and-material-layers.md](references/substrate-and-material-layers.md), and [references/specialized-shading-models.md](references/specialized-shading-models.md) as needed. Read supported domain properties through official ObjectTools; reserve the legacy `tools/material_domain_audit.py` executor for a demonstrated audit gap.
   For custom or complex water, also read [references/complex-water-material-playbook.md](references/complex-water-material-playbook.md) before authoring. A water material needs a concrete route, node plan, texture roles, carrier preview, and water-specific audit; do not stop at naming the shading model.
   For fire, flame, burning, ember, smoke, heat-haze, lava, magma, plasma, or energy-flame materials, read [references/fire-energy-material-playbook.md](references/fire-energy-material-playbook.md) before authoring. A fire-family material needs a concrete route, carrier, texture plan, node graph, motion plan, preview, and audit; do not stop at `Additive + Unlit + Emissive`.

11. Use case studies for external references.
   When matching an online material tutorial or reference, read [references/material-case-study-playbook.md](references/material-case-study-playbook.md). Extract the source contract, build a minimal UE reproduction, audit/read back the asset, preview on the closest carrier, then record whether mismatches are structural, visual, texture, carrier, or engine-version issues. If the source needs a texture that is missing and no approved library asset fits, `cm-imagegen` is the default generation route; generated assets must be QA'd, imported with role-correct settings, and registered as candidate or rejected library assets before future reuse.

12. Optimize after the effect is accepted.
   Once the look is correct enough to judge, reduce cost by preserving the same visible result first: pack channels, lower non-dominant texture sizes, bake stable procedural work, share samplers, add quality switches, remove dead branches, split expensive optional layers, tune LOD/import settings, or create fallback material instances. If an optimization visibly changes the effect, report it as a variant or tradeoff instead of silently replacing the approved look.

13. Report tradeoffs clearly.
   Explain the material output chain, material contract, required material inputs, performance risks, required textures, import settings, platform fallback, any unresolved visual gap, and which optimizations preserve the look versus change it.

14. Package delivery evidence.
   When a material route is ready to hand off or pause, use [references/delivery-packager.md](references/delivery-packager.md) and `tools/delivery_packager.py` to gather the plan, contract, texture reports, preview reports, audits, risks, and next actions into one delivery package. A package can be incomplete during iteration, but final delivery should not be treated as handoff-ready while required evidence is missing.
   When subagents are available and the user has authorized subagent work, use an independent read-only reviewer for non-trivial delivery or process-sensitive revisions. Give the reviewer the evidence package and the user-facing intent contract, not the intended answer. The reviewer should check for mismatched owner/carrier/source assumptions, missing preview/readback proof, hard edges/seams, garbled artist-facing text, and whether the output still follows the user's latest wording.
   When subagent work is authorized and the task is process-sensitive because a prior attempt misunderstood source, carrier, or parameter ownership, make the read-only review a required gate. The reviewer must explicitly Pass/Fail whether the texture source is preserved, carrier was not silently changed, MI-vs-particle ownership is respected, and no cancelled control path remains.

15. Score preview readability before final approval.
   When a preview technically succeeds but might still be visually empty or unreadable, use [references/preview-readability-score.md](references/preview-readability-score.md) and `tools/preview_readability_score.py` to quantify visibility, alpha coverage, center energy, background contrast, and edge readability. Treat screenshot success alone as insufficient proof for VFX materials.

16. Lock accepted previews and guard against drift.
   After a preview is visually accepted, use [references/material-regression.md](references/material-regression.md) and `tools/material_regression.py` to lock the accepted `material_preview.py` result as a baseline. After optimization, texture swaps, parameter tuning, graph refactors, or rebuilds, compare the new preview against that baseline before calling the change safe.
   When one baseline is no longer enough because tiers, carriers, or preview environments have multiplied, use [references/regression-baseline-set.md](references/regression-baseline-set.md) and `tools/regression_baseline_set.py` to manage and resolve the right accepted baseline for each context.

17. Explain failed regressions before refactoring.
   When a regression comparison fails, use [references/graph-diff-refactor.md](references/graph-diff-refactor.md) and `tools/graph_diff_refactor.py` with before/after `material_audit.py` reports, optional `material_domain_audit.py` reports, and the regression report. Diagnose route, output-chain, parameter, node, finding, and budget changes before patching or accepting a new baseline.

18. Turn parameter schemas into executable MI tiers.
   When the parameter contract exists and the next step is wider preview or gameplay-safe tuning, use [references/material-variant-runner.md](references/material-variant-runner.md) and `tools/material_variant_runner.py` to generate `default`, `low`, `high`, `extreme`, and `gameplay-safe` material-instance tiers, plus `material_instance_batch.py` specs and preview-matrix command scaffolds.
   When static switches also matter, follow with [references/static-switch-variant-expander.md](references/static-switch-variant-expander.md) and `tools/static_switch_variant_expander.py` so the chain covers permutation space instead of only dynamic parameters. Then use [references/permutation-budget-guard.md](references/permutation-budget-guard.md), `tools/permutation_budget_guard.py`, and `tools/shader_permutation_report.py` before that switch space becomes a shader-permutation liability.

19. Upgrade preview intent axes into a real harness plan.
   When `preview_matrix.py` still treats background, exposure, or parameter tiers as intent-only, use [references/preview-scene-harness-upgrade.md](references/preview-scene-harness-upgrade.md) and `tools/preview_scene_harness_upgrade.py` to map those axes to concrete harness capabilities, variant MIs, and executable commands.
   When the next step is to actually run those environment axes, use [references/preview-environment-executor.md](references/preview-environment-executor.md) and `tools/preview_environment_executor.py`.

20. Attribute shader cost before blind optimization.
   When a material is expensive but the source of cost is unclear, use [references/shader-cost-attribution.md](references/shader-cost-attribution.md) and `tools/shader_cost_attribution.py` to build a heuristic cost map across texture samples, functions, custom HLSL, switches, expensive math, and depth/scene reads.

21. Plan platform fallbacks once evidence exists.
   When delivery needs PC, Android, or low-end guidance, use [references/platform-scalability-planner.md](references/platform-scalability-planner.md) and `tools/platform_scalability_planner.py` to convert audit, texture, and route evidence into platform-specific downgrade advice and fallback MI expectations. If no evidence exists yet, record pre-evidence platform assumptions first, then replace them with measured data.

22. Run project-level health triage after evidence exists.
   When multiple material, texture, regression, graph-diff, graph-refactor-apply, or permutation reports have accumulated, use [references/project-material-health.md](references/project-material-health.md) and `tools/project_material_health.py` to build heatlists for risky materials, texture sets, failed regressions, unsafe refactor candidates, parameter collisions, static-switch pressure, and suspicious master-material candidates.

23. Map material-function dependencies before large-scale cleanup.
   When the project has many Material Functions or master-material dependencies, use [references/material-function-dependency-map.md](references/material-function-dependency-map.md), `tools/material_function_dependency_map.py`, and `tools/material_function_linter.py` to identify function reuse hotspots, large/switch-heavy functions, duplicate names, missing inputs/outputs, preview-default issues, and likely cleanup targets.

24. Use recipe builder or refactor planner for repeatable graph work.
   When a known recipe fits, use [references/material-toolset-builder.md](references/material-toolset-builder.md) and `tools/material_toolset_builder.py recipe` to generate the route, parameters, textures, and validation plan offline. Execute covered steps with official MCP, preserving the recipe's render contract and usage flags. The builder's `build` / `recipe --execute` paths remain legacy bridge executors and are reserved for demonstrated gaps. Use `refactor-plan` to turn graph-diff findings into a guarded patch plan before mutation.

25. Apply graph refactors only through a reviewable candidate flow.
   Use [references/graph-refactor-apply.md](references/graph-refactor-apply.md) and `tools/graph_refactor_apply.py` for a dry-run candidate plan. Execute covered duplicate/edit/save steps through official MCP. Its legacy `--execute` path is a fallback; retain the backup/candidate, whitelisted edits, before/after readback, and applicable preview/regression evidence regardless of transport.

26. Approve material reuse through a hard acceptance gate.
   When a material is intended to become final reusable evidence for Niagara, gameplay, or another downstream package, use [references/material-acceptance-gate.md](references/material-acceptance-gate.md) and `tools/material_acceptance_gate.py`. This gate reads the delivery package and linked evidence, requires contract, preview, audit, domain audit, regression, texture-set, budget, usage-flag, and parameter-table proof, then writes a Niagara-consumable report with `delivery_summary.approved_for_reuse=true` only when the material side is actually ready.

27. Escalate to stricter reuse approval when the asset may enter stock/library reuse.
   When the material should become a strongly reusable stock asset, use [references/material-acceptance-gate-v2.md](references/material-acceptance-gate-v2.md) and `tools/material_acceptance_gate_v2.py` so parameter schema, source provenance, preview matrix, readability, and translucent sorting evidence become hard gates instead of only supporting reports. Then use [references/library-promotion-gate.md](references/library-promotion-gate.md) and `tools/library_promotion_gate.py` to decide whether the candidate should become approved library stock.

28. Close the loop with one material-side smoke chain.
   When the question is no longer "what evidence do we still need?" but "can the current evidence actually run end to end as one chain?", use [references/material-delivery-smoke.md](references/material-delivery-smoke.md) and `tools/material_delivery_smoke.py` for planning. Its live orchestration includes legacy bridge executors; use `--execute` only for an evidenced gap within the authorized task. Otherwise run covered operations through official MCP and retain the equivalent evidence without inventing passes for incompatible legacy report gates. When repeated reruns would otherwise waste time, pair it with [references/smoke-resume-cache.md](references/smoke-resume-cache.md) and `tools/smoke_resume_cache.py`.

## Hard Rules

- Do not rely on screenshots of the Material Editor graph as proof. Read the material graph and output connections through tooling when possible.
- Do not let performance be the default first priority for custom, reference-driven, or look-development material work. Build the target effect first, then optimize from that baseline.
- Do not silently reduce texture resolution, remove layers, replace art-directed masks with generic noise, switch blend/shading models, or flatten motion just to pass an early budget if that changes the requested look.
- Do not convert a material into a ribbon/strip, particle-driven, or procedural-shape route when the user's wording says otherwise, even if the reference image visually resembles that family. User-stated source and control ownership outrank image resemblance and prior attempts.
- Do not carry forward old graph assumptions after a user correction. Remove or prove absent any superseded route, especially procedural replacement of a named texture, ribbon/strip assumptions, and particle-driven controls that the user cancelled.
- Do not present a cheaper variant as the final material unless it preserves the approved visual result or the user explicitly accepts the visual tradeoff.
- Do not leave dead branches, stale MI overrides, or mystery parameters in a production material after the route is confirmed.
- Do not sample textures manually inside Custom HLSL when a normal TextureSample node keeps UE dependency tracking, sampler state, and audit visibility clearer.
- Do not assume lower instruction count means cheaper if the "optimization" adds large textures, many samples, high overdraw, expensive translucency, or poor cache locality.
- Do not generate final textures from text alone when a design/reference image is available. Cache or use the reference and pass it into `cm-imagegen` as an image input.
- Do not let reusable assets override a custom/reference-driven material target. An approved library texture is still wrong if it is only a generic category match and does not match the reference's style, scale, pattern language, color/roughness read, edge/alpha shape, motion intent, carrier, and technical role.
- Do not tune UV, opacity, or emissive parameters from the 2D material formula alone. Check the carrier mesh topology, UV closure, two-sided flag, overlapping layer count, and bloom/exposure path; these can dominate the final look even when the graph math is correct.
- Do not author Niagara Ribbon / trail material motion on raw `TexCoord0.V` as the default. Niagara Ribbon commonly uses `U` for length and `V` for width, so panning/noise scroll/longitudinal tiling must go through raw `TexCoord0.U` / X unless renderer readback documents an exception or the material deliberately uses an art-space sampling remap. For that remap, use `Flow_UV = float2(TexCoord0.V, TexCoord0.U)` for texture sampling, pan/tile on `Flow_UV.y`, and keep width masks or edge fades on the original raw `TexCoord0.V`.
- Do not multiply a strong independently panned mask into both Ribbon emissive and opacity. That makes the secondary mask own a second moving silhouette and commonly reads as two overlaid images.
- For subtle internal Ribbon breakup, center sampled noise before modulation: `CenteredNoise = Noise * 2 - 1`, `Modulation = 1 + CenteredNoise * Strength`, then multiply the primary mask by `Modulation`. Start `Strength` around `0.1-0.25`; values outside the artist-authored range require a new visual review.
- Keep Ribbon silhouette opacity separate from internal emissive breakup by default. Let the primary mask, width fade, particle alpha, and tail fade own opacity; let centered secondary noise affect emissive/body detail unless the visual target explicitly needs alpha breakup.
- Make secondary moving noise inherit the main distorted Ribbon UV before adding a slow relative offset. Independent coordinates, distinct tiling, and counter-panning should be treated as a deliberate layer design and reviewed for phase separation, not as a default way to add detail.
- When a trail is reported as two images, first prove the live emitter and renderer count and read the renderer shape. Do not infer duplicate geometry from `MultiPlaneCount` while `Shape=Plane`, and do not treat `Two Sided` alone as proof that two surfaces are being drawn.
- Do not approve moving Ribbon breakup from graph structure or compilation alone. Capture at least two time-separated frames on the real Niagara Ribbon carrier and confirm the silhouette stays coherent while only internal energy detail evolves.
- Do not accept a foliage material as visually matched when it only has constant colors or a solid plane; leaf/bush materials need a diffuse/alpha texture or separate opacity mask plus a believable card/cluster carrier.
- Do not treat AI-generated Flow Maps, Normal Maps, packed masks, or precision lookup textures as final without technical validation; generate drafts only, then verify channels and import settings.
- Do not treat `sRGB` as a blanket default, and do not assume it should stay off. Set `sRGB` from the texture's final sampled role: enable it for visible color textures such as `BaseColor` / `Albedo`, `Emissive` color, and flipbook or sprite `RGB` that is meant to be seen as color; disable it for data, mask, and vector textures such as `Normal`, `Roughness` / `Specular` / `Metallic`, `Opacity` / `Alpha Mask`, packed `ORM` / `RMA` / `MRA`, `Noise`, `FlowMap`, and channels sampled individually as masks. Audit existing textures by actual material usage before changing them.
- Do not use ordinary color/sRGB white textures as defaults for mask, packed, ORM, roughness, metallic, opacity, flow, or scalar-data sampler slots. Their placeholder textures must match the sampler role, such as `TC_Masks` plus `sRGB=false` for Masks data, or the material can compile incorrectly before any artist texture is assigned.
- Do not skip the reusable asset library search when the task needs generic texture building blocks such as noise, masks, distortion, ramps, atlases, or flipbooks.
- Do not treat every generated image as reusable stock. Only `approved` library assets are default reuse candidates.
- Do not promote or reuse a simple stock water/noise/ripple texture as the visual identity of a custom water material unless it visually matches the reference. Generic ripple, noise, foam, or flow data may support the shader as a technical helper, but the reference controls the final water style.
- Do not let an online case study silently degrade because it lacks texture art. Search the library first; if missing, use `cm-imagegen`, prefer power-of-two output, self-audit the generated image, import/fix UE settings, and store the asset with category/stage metadata.
- Do not answer "I can make fire" from vague memory. For fire/flame/burning/ember/smoke/heat-haze/lava/energy materials, use the learn-build-audit loop: route selection, texture strategy, real graph, preview, readback, and audit. If missing knowledge blocks the route, research official/source material first, then build and review.
- Do not present `Additive + Unlit + Emissive` as a finished fire material by itself. Fire needs shape language, color bands, alpha/mask or flipbook logic, motion, carrier context, and overdraw review.
- Do not use a single panning fire mask as a hero flame unless the target is explicitly stylized/static and the preview proves it. Hero fire usually needs flipbook/SubUV or a richer carrier contract.
- Do not read, trace, debug, or write live Niagara emitter/system parameter wiring as part of this skill. Return the material-side contract and let `niagara-vfx-artist` own the real Niagara hookup.
- Distinguish installed Epic source, active MCP discovery, and a successful live operation. A plugin being installed does not prove it is loaded, and a 5.8.0 inventory does not establish what changed in the 5.8.4 hotfix.

## Performance Judgment

When judging cost, consider all of these:

- Shader math: instruction count, expensive functions, loops, branches, Custom HLSL, feature/quality switches.
- Texture cost: sample count, sampler sharing, texture size, format, mips, filtering, bandwidth, cache behavior, virtual texture stacks, and channel packing.
- Blend and visibility: translucent overdraw, depth fade, refraction, masked alpha cost, two-sided shading, visible layer count, pixel coverage, sorting, particle count, and whether bloom/exposure is clipping away the intended texture/noise detail.
- Platform: PC can carry richer materials; Android and low-end targets need fewer samples, smaller textures, additive/unlit defaults, and aggressive fallbacks.
- Runtime control: Dynamic Parameters, Material Parameter Collections, Niagara user params, and per-instance overrides should be intentional and named for use, not for node history.

Use `FeatureLevelSwitch`, `QualitySwitch`, material instances, and texture LOD/import settings when the target platform has materially different budgets.

Performance review order:

1. Confirm the material reaches the intended visual target in the right carrier/context.
2. Measure instructions, samples, texture memory, overdraw, shader complexity, and platform risk.
3. Classify each issue as must-fix, optimize-without-look-change, acceptable-for-prototype, or visual-tradeoff-needed.
4. Apply no-look-change optimizations first.
5. Ask for or clearly label tradeoff variants when performance requires visible simplification.

## Tooling

Detailed command examples live in the reference files. Use this as the compact entry map. Local planning/report/image tools remain usable, but the editor-connected audit, preview, MI-batch, import-fix and legacy executors listed below are conditional fallback tools, not the default control path. Gather covered live evidence through MCP first.

| Need | Tool |
|---|---|
| Turn a reference or tutorial into a material work order | `tools/reference_to_material_plan.py` |
| Write or validate a Niagara-to-material contract | `tools/material_contract.py` |
| Build recipe packages or guarded graph plans | `tools/material_toolset_builder.py` |
| Apply a reviewed refactor to a duplicated candidate | `tools/graph_refactor_apply.py` |
| Gather delivery evidence | `tools/delivery_packager.py` |
| Approve delivery or stock reuse | `tools/material_acceptance_gate.py`, `tools/material_acceptance_gate_v2.py`, `tools/library_promotion_gate.py` |
| Lock or compare accepted previews | `tools/material_regression.py`, `tools/regression_baseline_set.py` |
| Explain visual or graph drift | `tools/graph_diff_refactor.py` |
| Build project heatlists | `tools/project_material_health.py` |

| Need | Tool |
|---|---|
| Parameter schema / MI handoff | `tools/material_parameter_schema.py`, `tools/material_instance_batch.py` |
| Graph and render-contract audit | `tools/material_audit.py`, `tools/material_domain_audit.py` |
| Translucency/additive/ribbon sorting evidence | `tools/translucency_sorting_probe.py` |
| Texture file, set, import, and provenance checks | `tools/texture_asset_report.py`, `tools/texture_set_pipeline.py`, `tools/texture_import_audit.py`, `tools/texture_import_fix.py`, `tools/material_source_provenance.py` |
| Carrier previews and matrices | `tools/material_preview.py`, `tools/preview_matrix.py`, `tools/preview_readability_score.py` |
| Runtime parameter source tracing | `tools/runtime_param_trace.py` |
| Channel packing and flipbook cleanup | `tools/channel_packer.py`, `tools/flipbook_normalizer.py` |
| Reusable asset search, registration, and promotion | `tools/material_asset_library.py` |

Approved material assets now also emit a higher-level delivery report under `<project>/.codex/session/material-delivery/deliveries/`, so rebuilt-material approval is visible in the workflow output and not only as a catalog state change.

Reports write under:

```text
<project>/.codex/session/material-delivery/
```

The tools cover reference-to-material planning, delivery packaging, hard material acceptance reports, parameter schemas, preview matrices, translucency sorting probes, texture source provenance, material preview regression, delivery smoke orchestration, regression-cause graph diffing, project-level material health heatlists, recipe builder specs, guarded graph refactor plans, full texture-set QA and RMA packing, graph output chains, dead branches, stale MI overrides, compile findings, instruction count, sampler count, material contracts, material-side parameter traces, reusable asset-library search and promotion, generated texture dimensions, atlas grids, alpha availability, role-specific texture warnings, Unreal import settings, mesh and carrier preview renders, batch MI authoring, channel packing, and flipbook cleanup.

Current preview carrier note:

- `sprite` and `ribbon` previews now default to temporary Niagara-system harnesses, so they are closer to true Niagara sprite/ribbon renderer output than plain cards.
- `sprite_card` and `ribbon_card` keep the older cheap card-based approximation path for quick checks.
- `decal` preview uses a temporary wall plus `DecalActor`.
- `post_process` preview uses a temporary preview volume plus neutral scene geometry.
- Even the Niagara-based preview modes are still lightweight harnesses, not a full gameplay Niagara integration test.
- These previews exist only to review material behavior on likely carriers. Real Niagara system bindings, live parameter sources, and runtime writebacks remain Niagara-owned; hand `material_contract`, `delivery_packager`, and preview evidence to `niagara-vfx-artist`. Its `niagara_material_integration_probe.py` validates the real System/Emitter/Renderer route.

Editor/toolset note:

- Epic's UE 5.8.4 source ships MaterialTools (22 tools), MaterialInstanceTools (13), ObjectTools (6), TextureTools (2), and ProgrammaticToolset (2). These source counts describe the installed build; use the active server inventory for availability.
- Standard graph readback and wiring can use returned UObject references: `get_expressions`, `get_expression_inputs`, `get_property_input`, `get_expression_input_names`, and `get_expression_output_names`. A custom GUID wrapper is not required for the normal graph route.
- Import with `TextureTools.import_file`; apply supported texture/expression properties with `ObjectTools.set_properties`; save with `AssetTools.save_assets` and read back. Discover required fields and enums first.
- `tools/official_toolsets_bridge.py` calls Epic MCP directly and saves transport plus resolved-toolset evidence.
- Keep local image QA, packing, visual comparisons, contracts, and delivery reports. Check specialized compiler/statistics, private-property, and controlled-preview needs against the live tools first; for a remaining gap use a stock `unreal.*` API through `../unreal-engine-mcp/scripts/python_remote.py`.

## Reference Map

Read only what the task needs. [references/index.md](references/index.md) says when to use each one.

- **Plan and contract:** [reference-to-material-plan](references/reference-to-material-plan.md), [material-contract-and-tooling](references/material-contract-and-tooling.md), [material-parameter-schema](references/material-parameter-schema.md), [material-domain-and-rendering-contracts](references/material-domain-and-rendering-contracts.md), [master-material-architecture](references/master-material-architecture.md), [tech-art-material-systems](references/tech-art-material-systems.md), [platform-scalability-planner](references/platform-scalability-planner.md), [permutation-budget-guard](references/permutation-budget-guard.md), [static-switch-variant-expander](references/static-switch-variant-expander.md), [material-variant-runner](references/material-variant-runner.md)
- **Recipes, domains and shading:** [material-recipes](references/material-recipes.md), [material-recipes-trails-shockwaves-dissolve-water-fire](references/material-recipes-trails-shockwaves-dissolve-water-fire.md), [material-recipes-vfx-shield-explosion-smoke](references/material-recipes-vfx-shield-explosion-smoke.md), [material-recipes-naming-and-mobile](references/material-recipes-naming-and-mobile.md), [fire-energy-material-playbook](references/fire-energy-material-playbook.md), [complex-master-material-playbook](references/complex-master-material-playbook.md), [complex-water-material-playbook](references/complex-water-material-playbook.md), [material-case-study-playbook](references/material-case-study-playbook.md), [niagara-ribbon-flame-trail](references/niagara-ribbon-flame-trail.md), [domain-character-environment](references/domain-character-environment.md), [domain-landscape-foliage](references/domain-landscape-foliage.md), [specialized-shading-models](references/specialized-shading-models.md), [substrate-and-material-layers](references/substrate-and-material-layers.md), [material-node-map](references/material-node-map.md), [material-function-dependency-map](references/material-function-dependency-map.md)
- **Textures and assets:** [texture-strategy-and-ai-prompts](references/texture-strategy-and-ai-prompts.md), [texture-strategy-selection-and-rules](references/texture-strategy-selection-and-rules.md), [texture-vs-compute](references/texture-vs-compute.md), [texture-prompt-framework](references/texture-prompt-framework.md), [texture-prompts-vfx](references/texture-prompts-vfx.md), [texture-domain-foliage-water](references/texture-domain-foliage-water.md), [texture-set-pipeline](references/texture-set-pipeline.md), [generated-texture-qa](references/generated-texture-qa.md), [material-source-provenance](references/material-source-provenance.md), [material-asset-library](references/material-asset-library.md), [library-promotion-gate](references/library-promotion-gate.md)
- **Preview, regression and cost:** [preview-matrix](references/preview-matrix.md), [preview-readability-score](references/preview-readability-score.md), [preview-scene-harness-upgrade](references/preview-scene-harness-upgrade.md), [preview-environment-executor](references/preview-environment-executor.md), [material-preview-presets](references/material-preview-presets.md), [translucency-sorting-probe](references/translucency-sorting-probe.md), [ribbon-trail-seam-debugging](references/ribbon-trail-seam-debugging.md), [material-regression](references/material-regression.md), [regression-baseline-set](references/regression-baseline-set.md), [shader-cost-attribution](references/shader-cost-attribution.md)
- **Audit, refactor and editor tools:** [material-audit-workflow](references/material-audit-workflow.md), [graph-diff-refactor](references/graph-diff-refactor.md), [graph-refactor-apply](references/graph-refactor-apply.md), [project-material-health](references/project-material-health.md), [material-toolset-builder](references/material-toolset-builder.md), [official-toolsets-vs-local](references/official-toolsets-vs-local.md), [official-doc-notes](references/official-doc-notes.md)
- **Delivery and gates:** [delivery-packager](references/delivery-packager.md), [material-acceptance-gate](references/material-acceptance-gate.md), [material-acceptance-gate-v2](references/material-acceptance-gate-v2.md), [material-delivery-smoke](references/material-delivery-smoke.md), [smoke-resume-cache](references/smoke-resume-cache.md)

## Collaboration With Niagara VFX Artist

Use this skill for the material side of a Niagara effect: material master/instance design, texture needs, shader math, HLSL, graph audit, and material performance. It may declare required inputs such as `ParticleColor`, `DynamicParameter`, `SubImageIndex`, or `RibbonWidth`, but it does not own how a live Niagara system supplies them.

Use `niagara-vfx-artist` for the Niagara side: systems, emitters, renderers, events, simulation, user parameters, renderer bindings, emitter graph hookups, bounds, culling, and integration. When a task spans both, let this skill own the material and texture contract while Niagara owns carrier behavior, runtime effect structure, every real Niagara read/write decision, and `niagara_material_integration_probe.py` validation.

For mixed material/Niagara contexts, write two separate handoff rows: `renderer assignment owner` and `runtime parameter owner`. If assignment owner is Niagara but runtime parameter owner is Material Instance, the material specialist must not add Niagara or particle parameter inputs; Niagara receives only the material/MI assignment contract.
