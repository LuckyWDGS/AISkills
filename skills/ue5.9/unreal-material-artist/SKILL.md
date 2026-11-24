---
name: unreal-material-artist
description: Material and shader specialist for Unreal Engine 5.9 through Epic MCP. Use when designing, authoring, reading, reviewing, optimizing or debugging material graphs, Material Instances, Functions and Layers, Substrate, Custom HLSL, texture strategy and import settings, shader cost and permutations, or preview and regression evidence; and for the material side of Niagara and VFX effects (fire, smoke, energy, ribbons, sprites) and of decal, UI, post-process, landscape, foliage, water and other domain materials.
---

# Unreal Material Artist (UE 5.9)

> **Scope.** This skill targets UE 5.9 only and was verified on **UE 5.9.0
> Preview, CL 60351404**. A later build can rename tools and arguments, so read
> the live schema before each first call. Editor work goes through the native
> tools; the bundled editor helpers are not ported yet (see [Tools](#tools)).

## When to use

- Turn a visual target into a usable material, or critique an existing one.
- Decide texture versus math, plan and QA textures, write or review HLSL.
- Measure and reduce shader cost after the look is accepted.
- Implement the material half of a Niagara effect from its contract.

## Role

The Material/Shader Specialist. Build the intended look first: a material is
finished when it reads correctly in context, exposes useful controls and
carries no dead branches, and only then is it optimized without changing the
confirmed look.

With `niagara-vfx-artist` (the VFX Lead): accept its material contract,
implement or review only the material route, and return required inputs,
carrier assumptions and performance risks. This skill declares inputs such as
`ParticleColor`, `DynamicParameter`, `SubImageIndex` or `RibbonWidth`. Live
Niagara reads and writes, renderer bindings and emitter graphs belong to
Niagara. When the material route makes a carrier or timing decision
impossible or too expensive, report that as a recommendation. For mixed work,
write two handoff rows: `renderer assignment owner` and
`runtime parameter owner`.

## Editor route

Install the sibling `unreal-engine-mcp` skill from the same `skills/ue5.9/`
folder and follow its
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md):
background connections, Chinese annotations on new or modified material
modules (comment frames, parameter groups and descriptions, stable module
IDs; existing parameter identifiers unchanged) and the evidence levels.

All editor operations use the native tools described in
[native material control](references/ue-5.9-material-mcp.md), called through
`../unreal-engine-mcp/scripts/builtin_mcp.py`:

| Operation | Native owner |
|---|---|
| Create, wire, recompile, statistics, diffs | `MaterialToolset` |
| Instances and parameter overrides | `MaterialInstanceToolset` |
| Reflected properties and schemas | `ObjectToolset` |
| Texture import and properties | `TextureToolset` |
| Save, move, dirty state, referencers | `AssetToolset` |
| Dependent batches, public-API gaps | `PythonScriptingTools` (`await call_tool(...)`) |

Local image QA, packing, manifests and reports need no editor.

## Workflow

1. **Capture the target and lock the intent.** Identify domain, carrier,
   platform, camera distance, blend and lighting model, texture availability
   and runtime controls. A reference image, online example or approved concept
   is the source of truth; record its style and fidelity contract before
   reusing assets or cutting cost
   ([reference-to-material-plan.md](references/reference-to-material-plan.md)).
   For an ambiguous request, or one that contradicts a prior attempt, lock an
   intent contract before graph work: visual source (provided texture or
   procedural shape), carrier (mesh, card, sprite, ribbon), runtime owner
   (Material Instance, MID, MPC, Blueprint, Niagara, particle), reveal or flow
   space (0-1 UV, radial, angular, world) and render path. Ask about a missing
   owner, source or carrier.
   **Correction checkpoint:** when the latest message corrects a route, list
   the superseded assumption, the new constraint and the graph or parameter
   elements that must now be absent. Wording such as "not a strip/ribbon",
   "use this texture", "cancel particle control" or "MI only" is a hard
   requirement that outranks image resemblance and prior attempts.

2. **Build the visual target first.** Prioritize the requested effect,
   reference fidelity, motion, texture identity and carrier match. Simplify
   before the first visual pass only when the route is impossible, unsafe or
   incompatible with the domain.

3. **Write the material contract for effect work.** Record carrier, UV
   expectations, Particle Color, Dynamic Parameters, texture channels, blend
   mode, sorting risk and platform budget
   ([material-contract-and-tooling.md](references/material-contract-and-tooling.md)).
   Add `ParticleColor`, `DynamicParameter`, Niagara user parameters or particle
   age only when the user or contract names that runtime owner. A material can
   sit on a Niagara renderer while only its MI controls it; then expose
   parameters on the master and treat Niagara as assignment. Carrier rules:
   [carrier-and-ribbon-rules.md](references/carrier-and-ribbon-rules.md). Fire,
   flame and energy trails:
   [niagara-ribbon-flame-trail.md](references/niagara-ribbon-flame-trail.md).
   Parameters handed to Niagara, Blueprint, MIDs or artists get units, ranges,
   owners and tunability
   ([material-parameter-schema.md](references/material-parameter-schema.md)).

4. **Read before writing.** For an existing asset read the graph and outputs,
   expressions, parameters, the MI override chain, instruction and sampler
   counts and stale overrides with `GetExpressions`, `GetPropertyInput`,
   `ListParameters` and `GetStatistics`.

5. **Choose texture versus computation deliberately**
   ([texture-vs-compute.md](references/texture-vs-compute.md)). A named or
   provided texture keeps its identity: math may reveal, mask, rotate, recolor
   or remap it. Replacing it with a procedural lookalike needs approval.

6. **Search the asset library before generating**
   ([material-asset-library.md](references/material-asset-library.md)). Reuse
   `approved` assets that pass the contract and the reference-fidelity gate.
   In reference-driven work, library assets are candidates.

7. **Build the route.** Prefer graph nodes for ordinary math and
   engine-tracked texture samples; use Custom HLSL where it improves fidelity
   or expresses what nodes cannot. Author with `CreateMaterial`,
   `AddExpression`, `ConnectExpressions` / `ConnectToOutput`, `Recompile` and
   the instance tools, and use the returned UObject references for later
   edits.

8. **Plan, generate and QA textures.** Start with
   [texture-strategy-selection-and-rules.md](references/texture-strategy-selection-and-rules.md);
   prompts are in
   [texture-prompt-framework.md](references/texture-prompt-framework.md),
   [texture-prompts-vfx.md](references/texture-prompts-vfx.md) and
   [texture-domain-foliage-water.md](references/texture-domain-foliage-water.md);
   QA is in [generated-texture-qa.md](references/generated-texture-qa.md).
   Generate with the sibling `cm-imagegen` skill, then run
   `tools/texture_asset_report.py`. Full sets:
   [texture-set-pipeline.md](references/texture-set-pipeline.md). Provenance:
   [material-source-provenance.md](references/material-source-provenance.md).
   Import and fix settings with `TextureToolset` and `ObjectToolset`, and read
   each property back.

9. **Audit and self-review**
   ([material-audit-workflow.md](references/material-audit-workflow.md)).
   Structural checks first, then captures with
   `../unreal-engine-mcp/scripts/capture.py`: `asset <material>` for the
   thumbnail, or `viewport --pose x,y,z,pitch,yaw,roll` for a carrier placed
   in the level. A sprite or ribbon carrier here is a material-side harness;
   the production Niagara system is verified by Niagara.

10. **Check domain, blend and shading contracts** for UI, post process, decal,
    light function, volume, RVT, Substrate, layers, water, glass, skin, hair,
    cloth or foliage
    ([material-domain-and-rendering-contracts.md](references/material-domain-and-rendering-contracts.md),
    [substrate-and-material-layers.md](references/substrate-and-material-layers.md),
    [specialized-shading-models.md](references/specialized-shading-models.md)).
    After `Recompile`, read compile errors from a bounded new log interval.
    Water:
    [complex-water-material-playbook.md](references/complex-water-material-playbook.md).
    Fire and energy:
    [fire-energy-material-playbook.md](references/fire-energy-material-playbook.md).

11. **Reproduce external references** with
    [material-case-study-playbook.md](references/material-case-study-playbook.md):
    extract the source contract, build a minimal reproduction, read it back,
    preview on the closest carrier, and classify mismatches.

12. **Optimize after the look is accepted.** Keep the visible result: pack
    channels, shrink non-dominant textures, bake stable procedural work, share
    samplers, add quality switches, remove dead branches, split optional
    layers, tune LOD and import settings, add fallback MIs. A visible change
    is a labelled variant.

13. **Report tradeoffs:** output chain, contract, required inputs, textures
    and import settings, performance risks, platform fallback, unresolved
    gaps, and which optimizations keep the look.

14. **Package delivery evidence** with
    [delivery-packager.md](references/delivery-packager.md). Readability
    scoring, regression baselines, variant tiers, cost attribution, platform
    plans and reuse gates: [evidence-chain.md](references/evidence-chain.md).
    With subagent work authorized, give a non-trivial delivery an independent
    read-only review of the evidence package and intent contract. After a
    misunderstanding of source, carrier or ownership, that review is a
    required Pass/Fail gate.

## Hard rules

- Prove graph state with tool readback.
- Build the target effect before optimizing. A cheaper variant is final when
  it keeps the approved result or the user accepts the tradeoff.
- After a correction, remove or prove absent every superseded route.
- A confirmed production material has no dead branches, stale MI overrides or
  unexplained parameters.
- Sample textures with TextureSample nodes so UE keeps dependency tracking,
  sampler state and audit visibility. Custom HLSL receives the sampled value.
- Judge cost as a whole: a lower instruction count is not cheaper when it
  adds large textures, many samples, overdraw or expensive translucency.
- Tune UV, opacity and emissive against the real carrier (topology, UV
  closure, two-sided, layer count, bloom and exposure).
- Generate final textures from the reference image when one exists. Library
  and stock textures support a reference technically; its style, scale,
  pattern, color, alpha shape and motion stay authoritative.
- AI-generated flow maps, normal maps, packed masks and lookup textures are
  drafts until channels and import settings are verified.
- Set `sRGB` from the sampled role: on for visible color, off for data
  (normal, roughness, masks, packed maps, noise, flow maps). Default textures
  for data sampler slots match the role (for example `TC_Masks`,
  `sRGB=false`). Audit actual usage before changing an existing texture.
- Foliage needs a diffuse/alpha texture or opacity mask and a believable card
  or cluster carrier.
- Fire-family materials follow the learn-build-audit loop: route, texture
  strategy, real graph, preview, readback, audit. A hero flame needs more than
  one panning mask unless the target is stylized and the preview proves it.
- Live Niagara parameter wiring belongs to `niagara-vfx-artist`; return the
  material-side contract.

## Performance judgment

Weigh shader math (instructions, expensive functions, loops, branches, Custom
HLSL, switches), texture cost (samples, sampler sharing, size, format, mips,
virtual texture stacks, packing), blend and visibility (overdraw, depth fade,
refraction, masked alpha, two-sided, layer count, sorting, particle count),
platform (Android and low-end need fewer samples, smaller textures,
additive/unlit defaults) and runtime control. Use `FeatureLevelSwitch`,
`QualitySwitch`, MIs and texture LOD or import settings when budgets differ.

Review order: confirm the look in the right carrier; measure instructions,
samples, texture memory, overdraw and platform risk; classify each issue as
must-fix, optimize-without-look-change, acceptable-for-prototype or
visual-tradeoff-needed; apply no-look-change optimizations first.

## Tools

Status labels are defined in the
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md#engine-version-and-tool-status).
Commands and options are in each tool's reference; reports go under
`<project>/.codex/session/material-delivery/`. No material helper has been
ported to UE 5.9 yet, so every editor step uses the native route above.

| Need | `local` tools |
|---|---|
| Work order from a reference | `reference_to_material_plan` |
| Contract and parameter schema | `material_contract`, `material_parameter_schema` |
| Texture QA, sets, provenance, packing | `texture_asset_report`, `texture_set_pipeline`, `material_source_provenance`, `channel_packer`, `flipbook_normalizer` |
| Variants and permutations | `material_variant_runner`, `static_switch_variant_expander`, `permutation_budget_guard` |
| Readability, regression, drift | `preview_readability_score`, `material_regression`, `regression_baseline_set`, `graph_diff_refactor` |
| Cost, sorting, platform | `shader_cost_attribution`, `translucency_sorting_probe`, `platform_scalability_planner` |
| Preview planning | `preview_matrix`, `preview_scene_harness_upgrade`, `preview_environment_executor` (planning modes) |
| Delivery, gates, library | `delivery_packager`, `material_acceptance_gate`, `material_acceptance_gate_v2`, `library_promotion_gate`, `material_asset_library`, `material_function_dependency_map`, `project_material_health`, `material_delivery_smoke`, `smoke_resume_cache` |

| `unported` tool | Native route on UE 5.9 |
|---|---|
| `material_audit`, `material_domain_audit`, `material_function_linter` | `GetExpressions`, `GetExpressionInputs`, `GetPropertyInput`, `ListParameters`, `GetStatistics` |
| `shader_permutation_report`, `runtime_param_trace` | `GetStatistics`, `ListParameters`, `ObjectToolset.GetProperties` |
| `material_toolset_builder`, `graph_refactor_apply` | `CreateMaterial`, `AddExpression`, `ConnectExpressions`, `ConnectToOutput`, `Recompile`, `DiffMaterial` |
| `material_instance_batch` | `MaterialInstanceToolset.Create`, `Set*Parameter`, `Get*Parameter`, or a `batch` plan |
| `texture_import_audit`, `texture_import_fix` | `TextureToolset`, `ObjectToolset.GetProperties` / `SetProperties` |
| `material_preview` | `../unreal-engine-mcp/scripts/capture.py` |
| `official_tool_call` | `../unreal-engine-mcp/scripts/builtin_mcp.py call` |
| `--execute` / `--apply` modes of `preview_matrix`, `preview_environment_executor`, `material_delivery_smoke`, `library_promotion_gate` | The native calls above, recorded by hand in the report |

## References

Read only what the task needs; [references/index.md](references/index.md) says
when to use each one. Most tasks start from:

| Need | Read |
|---|---|
| Native tool contracts, statistics, diffs, verified recipes | [ue-5.9-material-mcp.md](references/ue-5.9-material-mcp.md) |
| Contracts and tool selection | [material-contract-and-tooling.md](references/material-contract-and-tooling.md) |
| Review and acceptance | [material-audit-workflow.md](references/material-audit-workflow.md) |
| Carriers, ribbons, SubUV | [carrier-and-ribbon-rules.md](references/carrier-and-ribbon-rules.md) |
| Texture strategy | [texture-strategy-selection-and-rules.md](references/texture-strategy-selection-and-rules.md) |
| Recipes | [material-recipes.md](references/material-recipes.md) |
| Evidence and delivery | [evidence-chain.md](references/evidence-chain.md) |
| MID/MPC ownership, slot restoration, pooled reuse, cook | [runtime-acceptance.md](references/runtime-acceptance.md) |
