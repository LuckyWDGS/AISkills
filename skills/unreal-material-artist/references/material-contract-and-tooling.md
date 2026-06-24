# Material Contract And Tooling

## Use This When

- A Niagara effect layer needs a material and the carrier contract must be clear before graph work.
- A material task risks becoming vague: "make it glow", "make it smoky", "use a grid", "make it cheaper".
- The material specialist needs to return concrete material-input requirements, texture requirements, and performance risks to the VFX lead.
- You need to decide which tool or script should support the work.

## Table Of Contents

- [Capability Gaps To Keep Covered](#capability-gaps-to-keep-covered)
- [Material Contract](#material-contract)
- [Texture Asset Report](#texture-asset-report)
- [Texture Set Pipeline](#texture-set-pipeline)
- [Project Material Health](#project-material-health)
- [Material Toolset Builder](#material-toolset-builder)
- [Tooling Roadmap](#tooling-roadmap)
- [Versioned Editor Toolset Absorption](#versioned-editor-toolset-absorption)
- [Recovery To Formalization Flow](#recovery-to-formalization-flow)
- [Material Instance Batch Spec](#material-instance-batch-spec)
- [Output Back To Niagara](#output-back-to-niagara)

## Capability Gaps To Keep Covered

`unreal-material-artist` should not only generate graph ideas. It should cover these production capabilities:

- Intake contract: renderer, UVs, Particle Color, Dynamic Parameters, blend mode, domain, platform, and budget.
- Graph authoring: material outputs, functions, parameters, instances, Custom HLSL, switches, and fallbacks.
- Texture strategy: generated textures, baked textures, procedural math, flipbooks, atlases, packed masks, ramps, flow maps, and import settings.
- Performance review: instruction count, sampler count, texture bandwidth, overdraw, material domain, blend mode, feature level, and screen coverage.
- Asset hygiene: naming, MI override cleanup, dead graph branches, stale parameters, duplicate samples, wrong sRGB, and oversized textures.
- Delivery: a material contract, texture manifest, import settings, parameter table, audit report, known risks, and acceptance checks.

## Material Contract

Before building or reviewing a material for a Niagara layer, write down:

- Effect and layer name.
- Carrier: sprite, ribbon, mesh, decal, surface, UI, post process, landscape, or unknown.
- UV expectations: mesh UV, ribbon UV along length, sprite SubUV, screen UV, world projection, or custom.
- For cone, cylinder, tube, or other wrapped mesh carriers where `UV.x` closes at `0/1`, noise/detail `TileU` must be a positive integer unless a seam-hiding projection is used. Non-integer horizontal tiling such as `2.2` can render the UV seam as a vertical split line; record the constraint in the parameter schema and preview the seam side before delivery.
- For low-poly wrapped light volumes that use Fresnel for soft edges, record whether Fresnel reads real mesh normals or a virtual smooth radial normal. A radial normal such as `normalize(float3(LocalPosition.x, LocalPosition.y, 0))` transformed from Local to World is only a test variant; keep it only after visual approval.
- For stretched or panned noise that samples with heavily modified UVs, record whether mip derivatives should come from the modified UV or a clean base UV. On wrapped VFX meshes, `MipValueMode=Derivative` plus `DDX/DDY(TexCoord0)` can reduce seam shimmer or over-blurred mips caused by tiling/panner math.
- For closed or two-sided mesh volumes, write down whether the player sees one shell, front+back shells, or several overlapping layers. In `Additive`, every visible layer adds emissive energy; compensate with lower opacity/emissive, one-sided routing, culling changes, or a larger softer carrier instead of only chasing color values.
- Niagara SubUV sprite materials should default to `two_sided=false` because the renderer is normally camera-facing; record a reason before enabling Two Sided for a non-camera-facing card/mesh route.
- Niagara/VFX texture asset names should end with `_VFX` so generated flipbooks, masks, ramps, and distortion maps do not blend into ordinary surface texture sets.
- Expected material inputs from Niagara or another caller: `ParticleColor`, `DynamicParameter`, user parameters, custom attributes, SubImageIndex, or vertex color.
- Material route: domain, blend mode, shading model, two-sided flag, expected output pins.
- Texture requirements: role, channels, resolution, grid, sRGB, compression, alpha, and source.
- Budgets: platform, instruction budget, sampler budget, overdraw risk, texture memory limit.
- Acceptance: how it should look, what must be controllable, and what cost must stay under budget.

Use:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_contract.py new --effect WingEcho --layer RibbonTrail --renderer ribbon --blend-mode Additive --platform PC --dynamic-parameters EdgeBreakup,OpacityScale --markdown
```

For reference-driven work, create the broader material work order first:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/reference_to_material_plan.py new --effect WingEcho --layer RibbonTrail --reference D:/Refs/wing_echo.png --cache-reference --target "blue energy ribbon trail with sharp bright core and smoky edge falloff" --profile energy --carrier ribbon --observation "cyan-white core with soft blue broken edge" --must-match "bright core,blue falloff,broken edge alpha" --emit-contract --markdown
```

`reference_to_material_plan.py` emits the route, texture requirements, parameter table, preview commands, audit checklist, and, with `--emit-contract`, a compatible `material_contract.py` seed. Treat plans without observations as scaffolds until a real visual readback is added.

After plan, texture QA, preview, and audit evidence exist, gather them into one delivery package:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/delivery_packager.py build --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/material-preview.json --audit-report D:/path/to/material-audit.json --audit-report D:/path/to/material-domain-audit.json --texture-report D:/path/to/texture-asset-report.json --material-path /Game/Materials/M_WingEcho_RibbonTrail --markdown
```

Use `--strict` when the package should fail until required evidence is complete.

When the material is ready for downstream reuse, run the hard material-side acceptance gate:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

This emits a Niagara-consumable report under `.codex/session/material-delivery/deliveries/<material>/delivery.json` with `delivery_summary.approved_for_reuse=true` only when contract, preview, audit, domain audit, texture-set, regression, budget, usage-flag, and parameter-table evidence all pass.

When the same material may become approved stock, upgrade to the stricter v2 gate:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate_v2.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

Before handoff, upgrade loose parameter rows into an explicit schema:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_parameter_schema.py --package D:/path/to/material-delivery-package.json --audit-report D:/path/to/material-audit.json --runtime-trace-report D:/path/to/runtime-param-trace.json --require-complete --markdown
```

For Additive/Translucent/Ribbon/Decal routes, prove or flag sorting and bounds evidence:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/translucency_sorting_probe.py --package D:/path/to/material-delivery-package.json --material-integration-probe D:/path/to/niagara-material-integration-probe.json --require-proven --markdown
```

After the preview is accepted, lock it as the regression baseline and compare later preview reports against it:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py baseline --package D:/path/to/material-delivery-package.json --label accepted-v001 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/new-material-preview.json --strict --markdown
```

If regression fails, explain the structural cause before refactoring:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_diff_refactor.py diff --before-audit D:/reports/before/material-audit.json --after-audit D:/reports/after/material-audit.json --before-domain-audit D:/reports/before/material-domain-audit.json --after-domain-audit D:/reports/after/material-domain-audit.json --regression-report D:/reports/material-regression-comparison.json --effect WingEcho --layer RibbonTrail --label optimize-pass-01 --markdown
```

Apply a reviewed graph refactor plan to a duplicated candidate material:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --markdown
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --execute --project UnrealAI --endpoint 127.0.0.1:57404 --carrier sprite --markdown
```

Validate an edited contract:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_contract.py validate path/to/material-contract.json --markdown
```

## Texture Asset Report

Use this after `cm-imagegen`, baking, or receiving external texture files:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py D:/textures/WingEcho --role flipbook --grid 8x8 --effect WingEcho --markdown
```

It checks first-pass readiness:

- dimensions and power-of-two status
- alpha availability
- atlas/flipbook grid divisibility
- oversized textures
- role-specific warnings for masks, packed data, flow maps, normals, flipbooks, and atlases

This script is not a replacement for UE import review. It is a fast gate before wasting time wiring a bad generated texture into a material.

## Texture Set Pipeline

Use this when a material has a set of related inputs rather than one isolated texture:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --scan D:/Textures/WingEcho --packed-convention ORM --emit-import-fix-spec --markdown
```

It checks BaseColor, Normal, packed RMA/ORM/MRA, Opacity, and Emissive together, records the packed-channel convention, reports set-level size and naming problems, optionally merges `texture_import_audit.py` evidence, and can emit a `texture_import_fix.py --batch-spec` input.

When source channels arrive separately, pack them through the same report:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --roughness D:/Textures/Roughness.png --metallic D:/Textures/Metallic.png --ao D:/Textures/AO.png --pack-rma-out D:/Textures/T_WingEcho_RMA.png --packed-convention RMA --markdown
```

Preserve texture source provenance before marking a material reusable:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_source_provenance.py --package D:/path/to/material-delivery-package.json --texture-set-report D:/path/to/texture-set-pipeline.json --import-audit-report D:/path/to/texture-import-audit.json --source-manifest D:/path/to/source-manifest.json --require-complete --markdown
```

Use a preview matrix when one preview is too narrow:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_matrix.py --package D:/path/to/material-delivery-package.json --background black,neutral,busy --distance 0,2,5 --angle "0,0;45,10" --time 0.25,1.0 --quality low,high --markdown
```

When screenshot success is not enough, quantify whether the preview actually reads:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_readability_score.py --preview-matrix-report D:/path/to/preview-matrix.json --require-readable --markdown
```

When preview-matrix axes are still only intent, formalize the missing harness capability:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_scene_harness_upgrade.py --preview-matrix-report D:/path/to/preview-matrix.json --variant-report D:/path/to/material-variant-runner.json --markdown
```

Turn the parameter schema into concrete MI tiers:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_variant_runner.py --parameter-schema D:/path/to/material-parameter-schema.json --parent-path /Game/Materials/M_WingEcho_Master --markdown
```

Build a heuristic cost map before optimization:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/shader_cost_attribution.py --audit-report D:/path/to/material-audit.json --markdown
```

Generate platform fallback plans from the existing evidence:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/platform_scalability_planner.py --package D:/path/to/material-delivery-package.json --platform pc,android,low_end --markdown
```

Map function dependencies and hotspots before large cleanup passes:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_function_dependency_map.py --function-linter-report D:/path/to/material-function-linter.json --audit-report D:/path/to/material-audit.json --markdown
```

After v2 approval, decide whether the asset should become approved reusable stock:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/library_promotion_gate.py --asset-id <candidate-id> --report-path D:/path/to/delivery-v2.json --report-path D:/path/to/material-parameter-schema.json --report-path D:/path/to/material-source-provenance.json --report-path D:/path/to/preview-matrix.json --report-path D:/path/to/preview-readability-score.json --require-ready --markdown
```

When the chain should stop being manual and become one smoke run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_delivery_smoke.py --package D:/path/to/material-delivery-package.json --parameter-schema-report D:/path/to/material-parameter-schema.json --source-provenance-report D:/path/to/material-source-provenance.json --translucency-sorting-report D:/path/to/translucency-sorting-probe.json --execute --project UnrealAI --endpoint 127.0.0.1:57404 --markdown
```

## Project Material Health

After material, texture, preview, regression, graph-diff, graph-refactor-apply, and permutation evidence exists, build a project-level heatlist:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --instruction-budget 220 --sampler-budget 12 --texture-max-dimension 2048 --markdown
```

Use `--strict` in automation when failed regressions, high-risk materials/textures/texture sets, or invalid reports should block the pass.

## Material Toolset Builder

Use this when a known route should become a repeatable recipe package or graph-diff evidence should become a guarded patch plan:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_flipbook --effect WingEcho --layer FlameSprite --folder-path /Game/Materials/VFX --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py refactor-plan --graph-diff-report D:/reports/graph-diff-refactor.json --markdown
```

The recipe path emits a route, parameters, texture requirements, preview/audit plan, and executable `material-builder-spec.json`. On `--execute`, route usage flags are applied through a whitelisted `MaterialUsage` enum setter, not direct `bUsedWith*` property writes. Sprite/ribbon recipes route `DynamicParameter.Param1` and `Param2` through default-zero emissive/opacity boost controls so contract evidence is live without changing the default look. The refactor path is plan-only by default and turns graph-diff causes into one-at-a-time operations with guardrails and validation commands.

## Tooling Roadmap

Use `SKILL.md` for the compact public tool map and the individual `references/*.md` files for workflow-specific commands. Keep this file focused on material contract, evidence chain, and handoff shape instead of duplicating every tool description.

High-level routing:

- Intake and reference plans: `reference_to_material_plan.py`, `material_contract.py`.
- Evidence and delivery: `delivery_packager.py`, `material_acceptance_gate.py`, `material_acceptance_gate_v2.py`, `library_promotion_gate.py`.
- Preview and regression: `material_preview.py`, `preview_matrix.py`, `preview_readability_score.py`, `material_regression.py`.
- Texture evidence: `texture_asset_report.py`, `texture_set_pipeline.py`, `texture_import_audit.py`, `texture_import_fix.py`, `material_source_provenance.py`.
- Build/refactor helpers: `material_toolset_builder.py`, `graph_diff_refactor.py`, `graph_refactor_apply.py`.
- Project triage: `project_material_health.py`, `material_function_dependency_map.py`, `shader_cost_attribution.py`, `platform_scalability_planner.py`.

## Versioned Editor Toolset Absorption

Use [official-toolsets-vs-local.md](official-toolsets-vs-local.md) for the source-backed/public API versus local `toolset_registry` policy. Short rule: prefer public/source-backed Unreal APIs or locally confirmed editor toolsets for supported mutations, then immediately validate with local audit/preview/reporting tools.

Use the bridge wrapper directly when you need a confirmed local/editor toolset call with saved evidence:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/official_toolsets_bridge.py asset:duplicate --input D:/payloads/duplicate.json --endpoint 127.0.0.1:8628 --markdown
python D:/Skills/skills/unreal-material-artist/tools/official_toolsets_bridge.py material_instance:set_scalar_parameter --input D:/payloads/set-radius.json --endpoint 127.0.0.1:8628 --markdown
python D:/Skills/skills/unreal-material-artist/tools/official_toolsets_bridge.py material:create --input D:/payloads/create-material.json --endpoint 127.0.0.1:8628 --markdown
```

Do not pretend editor texture tools replace local texture import audit/fix, generated-texture QA, or flipbook/packing helpers unless the active editor route has been smoke-tested.

## Recovery To Formalization Flow

Auto-rebuilt legal materials are no longer only preview-side recovery assets. The intended flow is now:

1. `material_preview.py` or `material_domain_rebuilder.py` detects an invalid render contract.
2. Rebuild into legal `DeferredDecal` or `PostProcess`.
3. Register the rebuilt material into `material_asset_library` as a `candidates` entry.
4. Keep the preview report attached to the candidate record.
5. Use `material_asset_library.py auto-promote` or `promote` after self-review.
6. On approval, emit a delivery-facing report so the rebuilt-material result is visible at the workflow/report layer, not only inside the catalog.

Typical commands:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_SurfaceLike --carrier decal --register-rebuilt-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_SurfaceLike --carrier post_process --register-rebuilt-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --width 320 --height 180 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py auto-promote <asset-id> --self-review approved --report-path D:/path/to/material-preview.json --apply
```

Approval now also writes a delivery report under:

```text
<project>/.codex/session/material-delivery/deliveries/
```

Category and role defaults for rebuilt legal materials:

- `DeferredDecal` -> category `decal`, role `decal-material`
- `PostProcess` -> category `post_process`, role `post-process-material`

## Material Instance Batch Spec

`material_instance_batch.py` uses a JSON spec like:

```json
{
  "parent_path": "/Game/Materials/M_WingEcho_Master",
  "effect": "WingEcho",
  "reuse_existing": true,
  "preview": {
    "enabled": true,
    "mesh": "shaderball",
    "lighting": "hdri",
    "resolution": 512,
    "yaw": 30.0,
    "pitch": 15.0,
    "distance": 0.0
  },
  "instances": [
    {
      "path": "/Game/Materials/MI_WingEcho_A",
      "params": [
        {"name": "Roughness", "type": "Scalar", "value": "0.35"},
        {"name": "TrailColor", "type": "Vector", "value": "(R=1,G=0.6,B=0.2,A=1)"}
      ]
    }
  ]
}
```

Use this when the material specialist must produce multiple variants fast and still hand back previewable assets to the VFX lead.

## Output Back To Niagara

When returning to `niagara-vfx-artist`, summarize:

- material path or proposed asset name
- required renderer-facing material assumptions
- required Dynamic Parameter or Particle Attribute names from the material side
- required texture imports and channel meanings
- known performance cost
- any carrier change recommendation
- audit or texture report path

Do not just say "material is done". Return the material contract that tells Niagara what the material expects. Do not claim that live Niagara bindings were verified here unless `niagara-vfx-artist` separately confirmed them.
