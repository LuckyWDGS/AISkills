---
name: niagara-vfx-artist
description: Use when the user needs Unreal Engine Niagara VFX help or complete usable Niagara effect delivery from text, reference images, or existing UE assets, including effect ideation, reference-image deconstruction, UE-achievable preview planning, cm-imagegen concept generation, emitter/system design, renderer selection, Niagara module planning, template-based system implementation, source/event wiring, animation/gameplay integration, graph-first Niagara validation, controlled preview capture, scalability, cleanup, and PC or Android Niagara performance optimization. For material graph authoring, texture planning, HLSL, material audits, or shader performance, use unreal-material-artist alongside this skill.
---

# Niagara VFX Artist

## Overview

Use this skill for Unreal Engine Niagara effect design, implementation, critique, integration, and optimization. It owns the Niagara side of the work: systems, emitters, renderers, events, modules, simulation targets, bounds, culling, preview, integration, and final effect delivery.

When the work needs Material graphs, Material Instances, texture plans, Custom HLSL, material performance analysis, or cm-imagegen texture generation, use `unreal-material-artist` for that part. Niagara can request a material contract, but it should not own the material implementation details.

## Workflow

1. Identify the target effect.
   Capture the visual intent, gameplay purpose, camera distance, timing, platform, performance budget, integration point, and whether references are available.

2. Cache and inspect supplied design images.
   When the user provides a design sheet, reference image, concept image, or keyframe image, save or preserve a local copy under the active workspace before analysis whenever possible. Prefer the closed-loop tool suite:
   - `tools/reference_cache.py`
   - `tools/reference_acceptance.py`
   - `tools/layer_evidence.py`
   - `tools/visual_layer_map.py`
   - `tools/design_compare_checklist.py`
   - `tools/preview_approval.py`

3. Decompose the effect into Niagara layers.
   Decide what each layer needs from Niagara: sprite, ribbon, mesh, component renderer, beam/trail behavior, source/receiver events, spawn timing, lifetime, velocity, curves, bounds, attachment, and scalability.

4. Request a material contract when needed.
   If a layer needs a material, define the required carrier contract for `unreal-material-artist`: renderer type, UV expectations, Particle Color/Dynamic Parameter usage, required texture channels, alpha behavior, blend mode expectation, sorting risk, and platform budget.

5. Implement or plan Niagara.
   Prefer template-first Niagara creation and mutation plans over fragile ad hoc graph writing. Use `niagara_asset_assistant.py` for reviewable mutation plans and `niagara_audit.py` for readback.

6. Validate structurally before visual tuning.
   Read the live Niagara system: emitter roles, renderer bindings, event handlers, source/receiver data flow, bounds, sim target, renderer materials, and expected carrier route.

7. Capture and self-review.
   Use controlled previews and captures after structural validation. Compare the effect against the approved design for silhouette, timing, density, width, color, brightness, spacing, and gameplay readability.

## Closed-Loop Tools

The tooling in `tools/` and `scripts/` is part of the core workflow.

Use these when relevant:

- `tools/reference_cache.py` for reference cache, crops, HQ copies, and active/rejected/debug separation.
- `tools/reference_acceptance.py` for approved anchor locking.
- `tools/layer_evidence.py` for hotspot suggestions and layer evidence.
- `tools/visual_layer_map.py` for evidence-to-carrier mapping.
- `tools/asset_plan.py` for first-pass Niagara asset planning and naming.
- `tools/integration_plan.py` for notify/socket/owner/user-parameter hookup planning.
- `tools/niagara_audit.py` for system/emitter/renderer readback.
- `tools/niagara_asset_assistant.py` for template-based Niagara creation or repair plans.
- `tools/controlled_preview.py` for deterministic preview captures.
- `tools/visual_diff_qa.py` and `tools/design_compare_checklist.py` for visual comparison.
- `tools/gap_diagnosis.py` and `tools/parameter_tuning_log.py` for intentional tuning.
- `tools/asset_cleanup.py`, `tools/delivery_package.py`, and `tools/learning_loop.py` for closeout.

For material audits, use:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py <material-path> --project <project-name> --markdown
```

## Niagara Validation Rules

- Do not trust editor UI screenshots as the source of truth for Niagara structure.
- Inspect emitter handles, renderer types, material bindings, event handlers, sim target, bounds, and source/receiver responsibilities before tuning.
- If a renderer material appears missing, first determine whether the renderer slot exists. Empty `RendererProperties` is a missing renderer/emitter construction problem, not merely a material-binding problem.
- In UE 5.7, avoid `NiagaraPythonEmitter.get_modules()` on arbitrary/template emitters as a discovery shortcut. It has caused NiagaraEditor `SharedPointer IsValid()` crashes. Prefer UPROPERTY export audits and known-safe renderer object readback.
- If the silhouette or timing is wrong, diagnose Niagara carrier/renderer/animation before pushing material brightness.
- If the silhouette is right but color, alpha, UV flow, edge softness, or shader detail is wrong, hand the material side to `unreal-material-artist`.

## Image Generation Bridge

Use `cm-imagegen` for concept images, visual direction, style targets, and reference exploration. For generated textures, masks, flipbooks, atlases, or material-specific texture assets, use `unreal-material-artist` to decide and generate the material-facing asset.

When a reference image exists, cache it and use it as an anchor. Do not generate key visual targets from text alone when a relevant local reference is available.

## Reference Map

Read only the files that matter for the current request:

- [references/core.md](references/core.md)
  Use for the main interaction pattern, design principles, Niagara basics, and implementation framing.

- [references/niagara-fundamentals.md](references/niagara-fundamentals.md)
  Use for Systems, Emitters, renderer families, emitter count inference, and translating visual targets into Niagara layers.

- [references/niagara-operations-and-workflows.md](references/niagara-operations-and-workflows.md)
  Use for templates, user parameters, scratch pad usage, renderers, animation notifies, and practical Niagara workflows.

- [references/common-effect-patterns.md](references/common-effect-patterns.md)
  Use for common effects such as explosions, shields, trails, hits, sigils, fire, smoke, projectiles, beams, and portals.

- [references/implementation-presets.md](references/implementation-presets.md)
  Use for practical starting presets, emitter breakdowns, module order, renderer choices, and first-pass ranges.

- [references/reference-analysis-output-spec.md](references/reference-analysis-output-spec.md)
  Use when the user provides a reference image, video, or design sheet and wants a full implementation package.

- [references/effect-layer-production-gate.md](references/effect-layer-production-gate.md)
  Use when a complex design sheet needs a stricter path from reference to UE-ready layer preview.

- [references/reference-deconstruction-patterns.md](references/reference-deconstruction-patterns.md)
  Use for deeper reference/video deconstruction and deciding whether a layer is Niagara-driven, material-driven, mesh-driven, flipbook-driven, or fluid-driven.

- [references/fluids-and-flowmaps.md](references/fluids-and-flowmaps.md)
  Use for fluid-like effects and deciding between Niagara Fluids, flow-map style material support, or baked flipbooks.

- [references/fluids-recipes.md](references/fluids-recipes.md)
  Use for concrete fluid-style effect recipes.

- [references/fluids-parameters.md](references/fluids-parameters.md)
  Use for Niagara Fluids parameter tuning.

- [references/fluids-troubleshooting.md](references/fluids-troubleshooting.md)
  Use when a fluid sim looks loose, blocky, blurry, weak, or too expensive.

- [references/fluids-production-pipeline.md](references/fluids-production-pipeline.md)
  Use for end-to-end fluid production decisions and baking workflows.

- [references/non-fluid-effects-playbook.md](references/non-fluid-effects-playbook.md)
  Use for hits, slashes, projectiles, beams, shields, sigils, portals, buffs, sparks, and related gameplay readability.

- [references/platform-optimization.md](references/platform-optimization.md)
  Use for Niagara scalability, particle budgets, bounds, culling, platform quality levels, and PC/Android tradeoffs. For material-specific cost, use `unreal-material-artist`.

- [references/debugging.md](references/debugging.md)
  Use for troubleshooting visibility, timing, sorting, renderer, integration, platform, and performance problems in Niagara effects.

- [references/review-checklist.md](references/review-checklist.md)
  Use when the user wants to review or critique an existing Niagara effect.

- [references/asset-planning-checklist.md](references/asset-planning-checklist.md)
  Use when moving from design into production naming, systems, emitters, instances, textures, and low-end planning. Delegate material details to `unreal-material-artist`.

- [references/validation-and-qa.md](references/validation-and-qa.md)
  Use for final acceptance checks including distance, background, stress, hookup, platform readiness, and delivery criteria.

- [references/engine-integration-checklist.md](references/engine-integration-checklist.md)
  Use for animation notifies, Blueprints, GAS, Sequencer, user parameters, effect types, scalability, and platform switching.

- [references/tool-suite.md](references/tool-suite.md)
  Use when the request is about the closed-loop production tools and their CLI workflow.

Ignore [README.md](README.md) for normal task execution.

## Output Expectations

When responding with this skill:

- Start from the intended visual result and gameplay readability.
- Explain why each major emitter, renderer, event route, and integration choice exists.
- Prefer concrete Niagara modules, curves, spawn logic, renderer settings, bounds, and scalability settings over vague advice.
- Be explicit about platform risk, especially on Android or low-end hardware.
- For implementation work, validate Niagara structure first and visual result second.
- Treat self-review against the approved design as part of completion.

## Default Response Shape

1. Artistic direction and effect breakdown
2. Feasibility or approximation notes
3. Niagara system, emitter, renderer, and event plan
4. Material contract for `unreal-material-artist`, if needed
5. Integration and scalability notes
6. Validation and self-test plan
