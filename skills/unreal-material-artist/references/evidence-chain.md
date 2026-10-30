# Evidence Chain

The advanced steps after a material route is built and audited: proving readability,
locking baselines, explaining drift, widening variants, attributing cost, and gating
reuse. Each step names its reference and tool; read only the step the task needs.
Reports write under `<project>/.codex/session/material-delivery/`.

## Table Of Contents

- [Preview and readability](#preview-and-readability)
- [Regression and drift](#regression-and-drift)
- [Variants and permutations](#variants-and-permutations)
- [Cost and platforms](#cost-and-platforms)
- [Project triage](#project-triage)
- [Repeatable graph work](#repeatable-graph-work)
- [Reuse gates](#reuse-gates)
- [End-to-end smoke](#end-to-end-smoke)
- [Preview route and editor notes](#preview-route-and-editor-notes)

## Preview and readability

- A preview that technically succeeds may still be empty or unreadable. Score it with
  [preview-readability-score.md](preview-readability-score.md) /
  `tools/preview_readability_score.py` (visibility, alpha coverage, center energy,
  background contrast, edge readability). Screenshot success alone is not proof for VFX.
- When one preview is too narrow, plan a matrix across background, exposure, distance,
  angle, time, parameter tier, quality, lighting and carrier with
  [preview-matrix.md](preview-matrix.md) / `tools/preview_matrix.py`. It plans one capture
  per cell; stage each context and capture it.
- To turn background, exposure or tier intent into concrete harness steps and variant
  MIs: [preview-scene-harness-upgrade.md](preview-scene-harness-upgrade.md) /
  `tools/preview_scene_harness_upgrade.py`, then
  [preview-environment-executor.md](preview-environment-executor.md) (plans the staged capture).
- Translucent, additive, ribbon and decal routes: check DepthFade/SoftParticle evidence
  and optional sorting/bounds proof with
  [translucency-sorting-probe.md](translucency-sorting-probe.md) /
  `tools/translucency_sorting_probe.py`. Real System/Emitter/Renderer proof stays with
  `niagara-vfx-artist`.

## Regression and drift

- After a preview is accepted, lock the `material_preview.py capture` report as a
  baseline with [material-regression.md](material-regression.md) /
  `tools/material_regression.py`; compare against it after optimization, texture swaps,
  tuning, refactors or rebuilds. Keep the same capture route and pose.
- Many tiers, carriers or environments: manage baselines with
  [regression-baseline-set.md](regression-baseline-set.md) / `tools/regression_baseline_set.py`.
- A failed comparison: diagnose route, output-chain, parameter, node, finding and budget
  changes with [graph-diff-refactor.md](graph-diff-refactor.md) /
  `tools/graph_diff_refactor.py` (before/after `material_audit.py` reports, optional
  `material_domain_audit.py` reports, the regression report) before patching or
  accepting a new baseline.

## Variants and permutations

- With a parameter contract in place, generate `default`, `low`, `high`, `extreme` and
  `gameplay-safe` MI tiers plus `material_instance_batch.py` specs:
  [material-variant-runner.md](material-variant-runner.md) / `tools/material_variant_runner.py`.
- When static switches matter, cover switch space with
  [static-switch-variant-expander.md](static-switch-variant-expander.md) /
  `tools/static_switch_variant_expander.py`, then guard it with
  [permutation-budget-guard.md](permutation-budget-guard.md) /
  `tools/permutation_budget_guard.py` and `tools/shader_permutation_report.py` (realized
  permutations per base material, from effective switch values). For master-material or
  MI-family cleanup, also run Unreal's Material Analyzer when the editor is available.

## Cost and platforms

- Expensive but unclear why: build a heuristic cost map (texture samples, functions,
  Custom HLSL, switches, expensive math, depth/scene reads) with
  [shader-cost-attribution.md](shader-cost-attribution.md) / `tools/shader_cost_attribution.py`.
- PC, Android or low-end guidance: convert audit, texture and route evidence into
  downgrade advice and fallback MI expectations with
  [platform-scalability-planner.md](platform-scalability-planner.md) /
  `tools/platform_scalability_planner.py`. Without evidence, record pre-evidence
  assumptions first and replace them with measurements.

## Project triage

- Many accumulated reports: heatlists of risky materials, texture sets, failed
  regressions, unsafe refactors, parameter collisions, switch pressure and suspicious
  masters with [project-material-health.md](project-material-health.md) /
  `tools/project_material_health.py`.
- Many Material Functions: reuse hotspots, large or switch-heavy functions, duplicate
  names and missing ports with
  [material-function-dependency-map.md](material-function-dependency-map.md) /
  `tools/material_function_dependency_map.py` and `tools/material_function_linter.py`.

## Repeatable graph work

- A known recipe fits: [material-toolset-builder.md](material-toolset-builder.md) /
  `tools/material_toolset_builder.py recipe` plans the route, parameters, textures and
  validation offline; `recipe --execute` (or `build <spec> --execute`) creates the
  material through MCP. It only creates new materials, saves only when every step
  succeeded, leaves a failed build unsaved for inspection, and keeps missing referenced
  textures at their defaults with a warning.
- Refactors: `refactor-plan` turns graph-diff findings into a guarded patch plan;
  [graph-refactor-apply.md](graph-refactor-apply.md) / `tools/graph_refactor_apply.py`
  plans the candidate (its `mcp_route` lists the AssetTools duplicate and MaterialTools
  edits to run as a `builtin_mcp.py batch`). Keep the backup/candidate, whitelisted
  edits, before/after readback and preview/regression evidence.

## Reuse gates

- Final reusable evidence for Niagara, gameplay or another package:
  [material-acceptance-gate.md](material-acceptance-gate.md) /
  `tools/material_acceptance_gate.py` requires contract, preview, audit, domain audit,
  regression, texture-set, budget, usage-flag and parameter-table proof and writes
  `delivery_summary.approved_for_reuse=true` only when the material side is ready.
- Stock-grade reuse adds parameter schema, provenance, preview matrix, readability and
  sorting as hard gates (`tools/material_acceptance_gate_v2.py`, same reference), then
  [library-promotion-gate.md](library-promotion-gate.md) /
  `tools/library_promotion_gate.py` decides library promotion.

## End-to-end smoke

To run the existing evidence as one chain, use
[material-delivery-smoke.md](material-delivery-smoke.md) / `tools/material_delivery_smoke.py`.
`--execute` runs the MCP steps (variant instances through `material_instance_batch`);
preview tiers stay planned until each is staged and captured, so readability and
regression wait on that evidence instead of passing. Pair reruns with
[smoke-resume-cache.md](smoke-resume-cache.md) / `tools/smoke_resume_cache.py`.

## Preview route and editor notes

- `material_preview.py capture` writes a standard `material_preview` report
  (`mode: capture`) read by the acceptance gate, regression, readability score and
  delivery packager. MCP has no shader-complexity view, so `complexity_ok` stays unset
  rather than failing.
- `--route thumbnail` is the editor's material sphere; `--route viewport` captures the
  carrier already in the level, so place the mesh/card/decal/Niagara carrier first with
  SceneTools. The posed capture does not move the user's viewport camera.
- Material previews are material-side evidence only. Real Niagara bindings, live
  parameter sources and runtime writebacks stay with `niagara-vfx-artist` and its
  `niagara_material_integration_probe.py`.
- UE 5.8.4 source ships MaterialTools (22 tools), MaterialInstanceTools (13),
  ObjectTools (6), TextureTools (2) and ProgrammaticToolset (2); the live inventory
  decides availability. Graph readback and wiring use returned UObject references
  (`get_expressions`, `get_expression_inputs`, `get_property_input`, pin-name tools); no
  GUID wrapper is needed.
- Approved library assets also emit a delivery report under
  `<project>/.codex/session/material-delivery/deliveries/`.
