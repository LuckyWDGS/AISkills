---
name: unreal-material-artist
description: Use when Codex needs a UE Material/Shader Specialist - designing, authoring, reading, reviewing, optimizing or debugging Unreal material graphs, Material Instances/Functions/Layers, Substrate, Custom HLSL, texture strategy and import settings, shader cost and permutations, and preview/regression evidence and acceptance gates through Epic MCP. Also the material side of Niagara/VFX effects (fire, smoke, energy, ribbons, sprites) and decal, UI, post-process, landscape, foliage, water and other domain materials.
---

# Unreal Material Artist

## Editor transport

**Sibling skills:** install `unreal-engine-mcp` in the same `skills/` folder. Every editor-connected tool imports its shared `scripts/ue_mcp` client and stops with a clear error when it is missing; local-only tools run without it. `niagara-vfx-artist` and `cm-imagegen` are workflow partners, not code dependencies.

Follow the [shared UE conventions](../unreal-engine-mcp/references/shared-conventions.md): background editor connections only, MCP first with
Python Remote Execution for a verified gap, and Chinese annotations on new or
modified material modules (comment frames, Chinese parameter groups and
descriptions, stable module IDs; existing parameter identifiers unchanged).

Use Epic's MCP (UE 5.8+) through the sibling `unreal-engine-mcp/scripts/builtin_mcp.py`, discovering the live schema of MaterialTools, MaterialInstanceTools, ObjectTools, TextureTools, AssetTools and ProgrammaticToolset before calling them. Every editor-connected tool here runs on MCP (plus Remote Execution for shader statistics). `preview_matrix.py --execute` captures only the axes MCP can drive and leaves the rest pending manual staging. Local image QA, packing, manifests and reports need no editor. Details: [official-toolsets-vs-local.md](references/official-toolsets-vs-local.md).

## Role

The Material/Shader Specialist: turn a visual target into a usable material, read and critique graphs, decide when textures beat math, generate needed textures, write or review HLSL, and validate performance after the look is proven. Build the intended look first; a material is not finished because it compiles or fits a budget. It must read correctly in context, expose useful controls, carry no dead branches, and then be optimized without breaking the confirmed look.

With `niagara-vfx-artist` (the VFX Lead): accept its material contract, implement or review only the material route, and return required inputs, carrier assumptions and performance risks. This skill may declare inputs such as `ParticleColor`, `DynamicParameter`, `SubImageIndex` or `RibbonWidth`, but live Niagara reads and writes, renderer bindings, emitter graphs and `niagara_material_integration_probe.py` belong to Niagara. Do not override its carrier or timing decisions unless the material route proves them impossible or too expensive; report that as a recommendation. For mixed work, write two handoff rows, `renderer assignment owner` and `runtime parameter owner`.

## Core Workflow

1. **Capture the target and lock the intent.**
   Identify domain, carrier, platform, camera distance, blend and lighting model, texture availability and runtime controls. A reference image, online example or approved concept is the source of truth; record its style/fidelity contract before reusing assets or cutting cost ([reference-to-material-plan.md](references/reference-to-material-plan.md), `tools/reference_to_material_plan.py`).
   When the request is ambiguous or contradicts a prior attempt, lock an intent contract before graph work: visual source (provided texture vs procedural shape), carrier (mesh/card/sprite/ribbon/unknown), runtime owner (Material Instance/MID/MPC/Blueprint/Niagara/particle), reveal or flow space (0-1 UV, radial, angular, world) and render path. Ask about a missing owner/source/carrier instead of inferring it from an image.
   **Correction checkpoint:** when the latest message corrects a route, list the superseded assumption, the new constraint, and the graph or parameter elements that must now be absent. Wording such as "not a strip/ribbon", "use this texture", "do not draw it procedurally", "cancel particle control" or "MI only" is a hard negative requirement that outranks image resemblance and prior attempts.

2. **Build the visual target first.** Prioritize the requested effect, reference fidelity, motion, texture identity and carrier match. Simplify before the first visual pass only when the route is impossible, unsafe or incompatible with the domain.

3. **Write the material contract for effect work.** Record carrier, UV expectations, Particle Color, Dynamic Parameters, texture channels, blend mode, sorting risk and platform budget ([material-contract-and-tooling.md](references/material-contract-and-tooling.md), `tools/material_contract.py`).
   Add `ParticleColor`, `DynamicParameter`, Niagara user parameters or particle age only when the user or contract names that runtime owner. Assignment is not control: a material can sit on a Niagara renderer while only its MI controls it; then expose parameters on the master and treat Niagara as assignment.
   Carrier rules (Niagara ribbon UV `U = length`, `V = width`; ribbon breakup; wrapped meshes; two-sided additive layering; SubUV sprites; `_VFX` texture suffix): [carrier-and-ribbon-rules.md](references/carrier-and-ribbon-rules.md). Fire/flame/energy trails: [niagara-ribbon-flame-trail.md](references/niagara-ribbon-flame-trail.md).
   Parameters handed to Niagara, Blueprint, MIDs or artists get units, ranges, owners and tunability through [material-parameter-schema.md](references/material-parameter-schema.md) / `tools/material_parameter_schema.py`.

4. **Read before writing.** For existing assets read the graph and outputs, expressions, parameters, MI override chain, instruction and sampler counts and stale overrides first: `tools/material_audit.py` (add `--graph-source remote` for a fast read-only graph), `tools/material_domain_audit.py`.

5. **Choose texture versus computation deliberately** ([texture-vs-compute.md](references/texture-vs-compute.md)). A named or provided texture keeps its identity: math may reveal, mask, rotate, recolor or remap it, never replace it with a procedural lookalike without approval.

6. **Search the asset library before generating** ([material-asset-library.md](references/material-asset-library.md), `tools/material_asset_library.py search`). Reuse `approved` assets only when they pass the contract and reference-fidelity gate; in reference-driven work library assets are candidates, not authority.

7. **Build the route.** Prefer graph nodes for ordinary math and engine-tracked texture samples; use Custom HLSL only when it improves fidelity or expresses what nodes cannot. Author through live MCP tools: MaterialTools wraps `UMaterialEditingLibrary`, returned UObject references drive later edits, and ProgrammaticToolset batches reads. Known recipes: `tools/material_toolset_builder.py recipe ... --execute` ([material-toolset-builder.md](references/material-toolset-builder.md)). MI families: `tools/material_instance_batch.py`.

8. **Plan, generate and QA textures.** Start with [texture-strategy-selection-and-rules.md](references/texture-strategy-selection-and-rules.md) (single texture vs flipbook/SubUV vs atlas vs mask); VFX prompts in [texture-prompts-vfx.md](references/texture-prompts-vfx.md); foliage and water in [texture-domain-foliage-water.md](references/texture-domain-foliage-water.md); read [texture-prompt-framework.md](references/texture-prompt-framework.md) and [generated-texture-qa.md](references/generated-texture-qa.md) before generating. Generate with the sibling `cm-imagegen` skill, then `tools/texture_asset_report.py`; register reusable passes in the library and reject failures. Full texture sets: [texture-set-pipeline.md](references/texture-set-pipeline.md); provenance: [material-source-provenance.md](references/material-source-provenance.md). Import settings: `tools/texture_import_audit.py`, `tools/texture_import_fix.py` (plan, then `--apply`).

9. **Audit and self-review** ([material-audit-workflow.md](references/material-audit-workflow.md)). Structural checks first, then captures: `tools/material_preview.py capture <material>` for the material thumbnail, or `--route viewport --pose x,y,z,pitch,yaw,roll --carrier <carrier>` for a carrier placed in the level (the user's camera does not move). A sprite/ribbon preview here is a material-side harness, not the production Niagara system. Performance findings are triage, not permission to lower the look.

10. **Check domain, blend and shading contracts** for UI, post process, decal, light function, volume, RVT, Substrate, layers, water, glass, skin, hair, cloth or foliage: [material-domain-and-rendering-contracts.md](references/material-domain-and-rendering-contracts.md), [substrate-and-material-layers.md](references/substrate-and-material-layers.md), [specialized-shading-models.md](references/specialized-shading-models.md). Compile errors are not exposed by MCP; read them through LogsToolset after a recompile. Water: [complex-water-material-playbook.md](references/complex-water-material-playbook.md). Fire, ember, smoke, heat haze, lava, plasma, energy: [fire-energy-material-playbook.md](references/fire-energy-material-playbook.md).

11. **Reproduce external references** with [material-case-study-playbook.md](references/material-case-study-playbook.md): extract the source contract, build a minimal reproduction, read it back, preview on the closest carrier, and classify mismatches (structural, visual, texture, carrier, engine version).

12. **Optimize after the look is accepted.** Preserve the visible result first: pack channels, shrink non-dominant textures, bake stable procedural work, share samplers, add quality switches, remove dead branches, split optional layers, tune LOD/import settings, add fallback MIs. A visible change is a labelled variant, never a silent replacement.

13. **Report tradeoffs:** output chain, contract, required inputs, textures and import settings, performance risks, platform fallback, unresolved gaps, and which optimizations keep the look.

14. **Package delivery evidence** with [delivery-packager.md](references/delivery-packager.md) / `tools/delivery_packager.py`. Readability scoring, regression baselines, drift diagnosis, variant tiers, cost attribution, platform plans, project triage, reuse gates and the end-to-end smoke chain: [evidence-chain.md](references/evidence-chain.md).
   With subagent work authorized, give non-trivial or process-sensitive deliveries an independent read-only review of the evidence package and intent contract (not the intended answer). After a misunderstanding of source, carrier or ownership, that review is a required Pass/Fail gate: texture source preserved, carrier unchanged, MI-vs-particle ownership respected, no cancelled control path left.

## Hard Rules

- Prove graph state with tool readback, not Material Editor screenshots.
- Build the target effect before optimizing; do not reduce texture resolution, drop layers, swap in generic noise, change blend/shading models or flatten motion to pass an early budget when that changes the look. A cheaper variant is final only if it keeps the approved result or the user accepts the tradeoff.
- After a correction, remove or prove absent every superseded route (procedural replacement of a named texture, ribbon/strip assumptions, cancelled particle controls).
- Leave no dead branches, stale MI overrides or mystery parameters in a confirmed production material.
- Sample textures with TextureSample nodes, not inside Custom HLSL, so UE keeps dependency tracking, sampler state and audit visibility.
- Lower instruction count is not cheaper if it adds large textures, many samples, overdraw, expensive translucency or poor cache locality.
- Tune UV, opacity and emissive against the real carrier (topology, UV closure, two-sided, layer count, bloom/exposure), not the 2D formula; ribbon and carrier specifics are in [carrier-and-ribbon-rules.md](references/carrier-and-ribbon-rules.md).
- Generate final textures from the reference image when one exists (pass it to `cm-imagegen`), not from text alone. Library and stock textures (including generic water/noise/ripple) never override a reference's style, scale, pattern, color, alpha shape or motion; they may only support it technically.
- Treat AI-generated flow maps, normal maps, packed masks and lookup textures as drafts until channels and import settings are verified. Only `approved` library assets are default reuse candidates.
- Set `sRGB` from the sampled role: on for visible color (BaseColor/Albedo, emissive color, flipbook or sprite RGB), off for data (Normal, Roughness/Specular/Metallic, Opacity/masks, packed ORM/RMA/MRA, noise, flow maps, channels sampled as masks). Default textures for data sampler slots must match the role (for example `TC_Masks`, `sRGB=false`). Audit by actual usage before changing an existing texture.
- Foliage needs a diffuse/alpha texture or opacity mask and a believable card/cluster carrier; constant colors on a plane are not a match.
- A case study missing texture art still gets one: search the library, else generate with `cm-imagegen` (power-of-two), self-audit, fix import settings, and store it with category/stage metadata.
- Fire-family materials follow the learn-build-audit loop (route, texture strategy, real graph, preview, readback, audit). `Additive + Unlit + Emissive` alone is not fire, and a single panning mask is not a hero flame unless the target is stylized and the preview proves it.
- Do not read, trace, debug or write live Niagara parameter wiring here; return the material-side contract.
- Distinguish installed Epic source, active MCP discovery and a successful live operation: an installed plugin may not be loaded, and a 5.8.0 inventory says nothing about the 5.8.4 hotfix.

## Performance Judgment

Weigh shader math (instructions, expensive functions, loops, branches, Custom HLSL, switches), texture cost (samples, sampler sharing, size, format, mips, bandwidth, virtual texture stacks, packing), blend and visibility (overdraw, depth fade, refraction, masked alpha, two-sided, layer count, coverage, sorting, particle count, bloom clipping detail), platform (Android and low-end need fewer samples, smaller textures, additive/unlit defaults) and runtime control (Dynamic Parameters, MPCs, Niagara user params and overrides named for use). Use `FeatureLevelSwitch`, `QualitySwitch`, MIs and texture LOD/import settings when budgets differ.

Review order: confirm the look in the right carrier; measure instructions, samples, texture memory, overdraw and platform risk; classify each issue as must-fix, optimize-without-look-change, acceptable-for-prototype or visual-tradeoff-needed; apply no-look-change optimizations first; label any visible tradeoff as a variant.

## Tooling

Commands and options live in each reference. Reports write under `<project>/.codex/session/material-delivery/`.

| Need | Tool |
|---|---|
| Work order from a reference or tutorial | `tools/reference_to_material_plan.py` |
| Niagara-to-material contract; parameter schema | `tools/material_contract.py`, `tools/material_parameter_schema.py` |
| Graph and render-contract audit | `tools/material_audit.py`, `tools/material_domain_audit.py` |
| Recipe builds and refactor plans | `tools/material_toolset_builder.py`, `tools/graph_refactor_apply.py` (`--execute` edits a duplicated candidate) |
| MI families and tiers | `tools/material_instance_batch.py`, `tools/material_variant_runner.py` |
| Textures: file QA, sets, import settings, provenance, packing | `tools/texture_asset_report.py`, `tools/texture_set_pipeline.py`, `tools/texture_import_audit.py`, `tools/texture_import_fix.py`, `tools/material_source_provenance.py`, `tools/channel_packer.py`, `tools/flipbook_normalizer.py` |
| Previews and readability | `tools/material_preview.py capture`, `tools/preview_matrix.py` (`--execute` for MCP-drivable cells), `tools/preview_readability_score.py` |
| Sorting, cost, permutations, runtime sources | `tools/translucency_sorting_probe.py`, `tools/shader_cost_attribution.py`, `tools/shader_permutation_report.py`, `tools/runtime_param_trace.py` |
| Regression, drift, project triage | `tools/material_regression.py`, `tools/regression_baseline_set.py`, `tools/graph_diff_refactor.py`, `tools/project_material_health.py` |
| Delivery, gates, library | `tools/delivery_packager.py`, `tools/material_acceptance_gate.py`, `tools/material_acceptance_gate_v2.py`, `tools/library_promotion_gate.py`, `tools/material_asset_library.py` |

## Reference Map

Read only what the task needs; [references/index.md](references/index.md) says when to use each of them. Most tasks start from [material-contract-and-tooling.md](references/material-contract-and-tooling.md), [material-audit-workflow.md](references/material-audit-workflow.md), [carrier-and-ribbon-rules.md](references/carrier-and-ribbon-rules.md), [texture-strategy-selection-and-rules.md](references/texture-strategy-selection-and-rules.md), [material-recipes.md](references/material-recipes.md) and [evidence-chain.md](references/evidence-chain.md).
