# Material Toolset Builder

## Use This When

- You need a higher-level material recipe package instead of hand-writing a low-level MaterialTools graph spec.
- You want a starter route for fire flipbooks, additive fire ribbons, decal stains, two-sided foliage, basic water, energy ribbons, or dissolve-edge materials.
- `graph_diff_refactor.py` has explained a failed regression and you need a narrow, guarded refactor plan before touching the graph.

## Purpose

`material_toolset_builder.py` has three layers:

- `recipe`: offline-first high-level recipe builder. It emits a material route, parameter table, texture requirements, preview plan, audit plan, and executable builder spec.
- `build`: low-level spec executor. It creates a material through UnrealBridge/MaterialTools and wires expressions/outputs. Legacy direct `spec.json` invocation still works.
- `refactor-plan`: graph-diff-aware patch planner. It converts likely causes or explicit operations into one-at-a-time refactor steps, guardrails, and validation commands.

The default posture is safe: `recipe` and `refactor-plan` write evidence and specs without mutating UE assets. Use `recipe --execute` only when UnrealBridge is online and the generated route/spec has been reviewed. Use `graph_refactor_apply.py` after `refactor-plan` when a guarded candidate apply is needed.

## Table Of Contents

- [List Recipes](#list-recipes)
- [Generate A Recipe Package](#generate-a-recipe-package)
- [Execute A Generated Spec](#execute-a-generated-spec)
- [Generate A Refactor Plan From Graph Diff](#generate-a-refactor-plan-from-graph-diff)
- [Refactor Safety Rules](#refactor-safety-rules)
- [Apply A Refactor Plan](#apply-a-refactor-plan)
- [Validation Loop](#validation-loop)

## List Recipes

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py list-recipes
```

Built-in recipes:

- `fire_flipbook`
- `fire_ribbon_additive`
- `fire_ribbon_additive_android`
- `decal_stain`
- `two_sided_foliage`
- `basic_water`
- `energy_ribbon`
- `dissolve_edge`

## Generate A Recipe Package

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_flipbook --effect WingEcho --layer FlameSprite --folder-path /Game/Materials/VFX --markdown
```

For a Niagara Ribbon additive flame trail scaffold:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_ribbon_additive --effect WingEcho --layer RibbonTrail --folder-path /Game/Materials/VFX --markdown
```

For the Android / low-tier one-sample fallback:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe fire_ribbon_additive_android --effect WingEcho --layer RibbonTrail --folder-path /Game/Materials/VFX --markdown
```

Default outputs:

```text
<project>/.codex/session/material-delivery/toolset-recipes/<effect-layer-recipe>/material-toolset-recipe.json
<project>/.codex/session/material-delivery/toolset-recipes/<effect-layer-recipe>/material-builder-spec.json
```

The recipe report includes:

- `route`: Material Domain, Blend Mode, Shading Model, Two Sided, expected outputs, and usage flags.
- `parameters`: recommended scalar/vector controls with defaults and purposes.
- `texture_requirements`: slots, channels, size expectations, sRGB, compression, and required/optional state.
- `builder_spec_path`: the low-level spec that `build` or `recipe --execute` can use.
- `preview_plan`, `audit_plan`, `texture_plan`, and `delivery_plan`.

Use `--inline-build-spec` only when you want the executable spec duplicated inside the recipe report.

## Execute A Generated Spec

Review the generated `material-builder-spec.json` first, then run either:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py build D:/path/material-builder-spec.json --project UnrealAI --endpoint 127.0.0.1:43815 --markdown
```

or:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe energy_ribbon --effect WingEcho --layer RibbonTrail --folder-path /Game/Materials/VFX --execute --project UnrealAI --endpoint 127.0.0.1:43815 --markdown
```

When a builder spec includes `route`, the tool uses the route-aware local material create path so domain, blend, shading model, and two-sided intent are created with the material. For legacy specs without `route`, it preserves the older official `MaterialTools.create` path.

Sprite/ribbon VFX recipes include explicit `ParticleColor` and `DynamicParameter` nodes so preview contract scans can verify the material is prepared for Niagara-driven tint/alpha/control. `DynamicParameter.Param1` and `Param2` are wired into emissive and opacity scale branches with default-zero boost parameters, so the default recipe look stays unchanged while downstream Niagara or MI tuning has live control sockets. Niagara SubUV sprite recipes keep `Two Sided` off because the renderer is normally camera-facing; enable it only for a documented non-camera-facing mesh/card route. VFX texture requirement names end with `_VFX`, such as `T_FireFlipbook_VFX` or `T_FireRibbonMask_VFX`. Usage flags are recorded with audit names such as `NiagaraSprites` and `NiagaraRibbons`. During `--execute`, the builder applies only whitelisted usage flags through `MaterialEditingLibrary.set_base_material_usage`; do not bypass that path with direct `bUsedWith*` property writes.

`fire_ribbon_additive` now builds a first-pass packed-mask additive graph: raw `TexCoord0` U/V split, `Tiling_Length`, optional `Use_Flow_UV_Remap`, Time-driven main/noise Panners, a B-channel distortion sample, a distorted main mask sample, centered raw-V width falloff with Clamp + Power, `ParticleColor`, `DynamicParameter.Param1/Param2`, color/intensity/core/opacity controls, `EmissiveColor`, and `Opacity`. `Texture_Mask` defaults to the same folder's `T_FireRibbonMask_VFX` asset reference in both generated sample nodes; edit that property if the imported mask lives elsewhere. This is still an offline builder-spec scaffold: run live UE pin-name smoke, carrier preview, texture import QA, and an Android one-sample fallback review when those platforms are in scope.

`fire_ribbon_additive_android` is the automatic low-tier fallback recipe. It keeps raw U/V split, `Tiling_Length`, optional `Use_Flow_UV_Remap`, one Time-driven main Panner path, centered raw-V Clamp + Power width falloff, `ParticleColor`, `DynamicParameter.Param1/Param2`, and `EmissiveColor` / `Opacity`, but intentionally uses only one `Texture_Mask` sample and omits the secondary B-channel distortion/noise sample. Its defaults lower `Intensity`, `Core_Boost`, `OpacityScale`, and `Tiling_Length`; treat it as a platform fallback, not a visual-equivalent replacement for the deep route.

## Generate A Refactor Plan From Graph Diff

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py refactor-plan --graph-diff-report D:/reports/graph-diff-refactor.json --markdown
```

Default outputs:

```text
<project>/.codex/session/material-delivery/toolset-refactors/<effect-layer-label>/material-toolset-refactor-plan.json
<project>/.codex/session/material-delivery/toolset-refactors/<effect-layer-label>/material-refactor-patch-spec.json
```

Graph-diff categories map to guarded operations:

- `route` or `domain_contract` -> `restore_route_contract`
- `output_chain`, `alpha`, `coverage`, or `composition` -> `repair_output_chain`
- `brightness`, `texture`, or `budget` -> `normalize_parameters`

You can also request explicit operations:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py refactor-plan --material-path /Game/Materials/M_Foo --operation add-fresnel-layer --operation add-depth-fade --effect Foo --layer Surface --markdown
```

Supported explicit operations:

- `add-fresnel-layer`
- `add-depth-fade`
- `add-detail-normal`
- `restore-route`
- `repair-outputs`
- `normalize-parameters`

## Refactor Safety Rules

- Treat `refactor-plan` output as plan-only. It intentionally does not mutate UE assets.
- Apply one operation at a time through `graph_refactor_apply.py`, then inspect the candidate material, preview, and regression evidence.
- Use GUID-level `material_audit.py --include-raw-graph` before reconnecting output chains.
- For route drift, restore domain/blend/shading/two-sided before tuning color, alpha, or budget.
- For runtime-facing parameters, run `runtime_param_trace.py` before renaming or deleting controls.

## Apply A Refactor Plan

Dry run first:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/path/material-toolset-refactor-plan.json --markdown
```

Then execute against a duplicated candidate:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/path/material-toolset-refactor-plan.json --execute --project UnrealAI --endpoint 127.0.0.1:43815 --carrier sprite --markdown
```

The apply tool leaves the original material untouched, creates backup/candidate duplicates, applies only whitelisted operations, and collects before/after audit, preview, and regression evidence when a baseline exists.

## Validation Loop

After a recipe build or a refactor patch:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Materials/M_Foo --include-raw-graph --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_domain_audit.py /Game/Materials/M_Foo --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_Foo --with-complexity --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --effect Foo --layer Surface --preview-report D:/path/new-preview.json --strict --markdown
```

Then package the result with `delivery_packager.py` and rerun `project_material_health.py` when project-level triage matters.
