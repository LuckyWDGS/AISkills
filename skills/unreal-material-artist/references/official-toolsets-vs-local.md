# Official And Editor Toolsets Vs Local Workflow

Updated: 2026-06-08

This note compares source-backed Unreal material editing APIs, locally smoke-tested editor toolsets, and the current local `UnrealBridge` + `unreal-material-artist` workflow.

## Summary

- Public UE 5.7 docs back `UMaterialEditingLibrary` and Material Editing Blueprint/Python APIs for many standard material editing operations.
- The `toolset_registry` tool names below were local/editor smoke-tested in this project, but public primary docs were not found for those names in the 2026-06-08 web pass.
- Use local/editor toolset routes only after runtime availability is confirmed in the active editor.
- Local UnrealBridge and skill tooling remain best for transport, auditing, preview, QA, reporting, and production workflow.
- Best control model:
  - `UnrealBridge` remains the transport/orchestration spine
  - source-backed APIs or confirmed local editor toolsets perform standard mutations when available
  - local skill tooling validates, previews, audits, and packages the result

## Table Of Contents

- [Local Toolsets Confirmed Useful](#local-toolsets-confirmed-useful)
- [Smoke-Proven Local Toolset Cases](#smoke-proven-local-toolset-cases)
- [Practical Division Of Labor](#practical-division-of-labor)
- [Current Gap Notes](#current-gap-notes)
- [Recommended Working Rule](#recommended-working-rule)

## Local Toolsets Confirmed Useful

- `toolset_registry.toolsets.core.material.MaterialTools`
- `toolset_registry.toolsets.core.material_instance.MaterialInstanceTools`
- `toolset_registry.toolsets.core.texture.TextureTools`
- `toolset_registry.toolsets.core.asset.AssetTools`
- related expansion candidates:
  - `toolset_registry.toolsets.core.scene.SceneTools`
  - `toolset_registry.toolsets.core.actor.ActorTools`
  - `toolset_registry.toolsets.core.blueprint.BlueprintTools`

## Smoke-Proven Local Toolset Cases

Live-tested on 2026-05-15:

- `AssetTools.create_folder`
- `AssetTools.exists`
- `AssetTools.duplicate`
- `AssetTools.save_assets`
- `MaterialInstanceTools.create`
- `MaterialInstanceTools.list_parameters`
- `MaterialInstanceTools.set_scalar_parameter`
- `MaterialInstanceTools.get_scalar_parameter`
- `MaterialTools.create`
- `MaterialTools.add_expression`
- `MaterialTools.connect_to_output`
- `MaterialTools.recompile`
- `TextureTools.get_size`

Additional material-workflow integrations proven on 2026-05-15:

- `material_instance_batch.py`
  - now supports `use_official_toolsets=true`
  - local toolset route proved for:
    - MI create
    - scalar parameter writes
    - asset save
- `material_preview.py`
  - `sprite_card` preview harness now runs through a toolset-first scene route
  - static-mesh preview actor spawn/removal now prefers `SceneTools`
  - label and transform updates can use `ActorTools`
  - `decal` preview also passed on the toolset-first scene route
- `material_toolset_builder.py`
  - now supports higher-level build chains:
    - create material
    - add expressions
    - write expression properties
    - connect expressions
    - connect to material output
    - recompile
    - save
  - now supports recipe/refactor workflow layers:
    - `recipe` emits route, parameter table, texture requirements, preview/audit plan, and executable builder spec
    - `refactor-plan` turns graph-diff likely causes or explicit operations into guarded one-at-a-time patch plans
    - `build` preserves the low-level spec execution route
  - templates now supported:
    - `constant_scalar`
    - `constant3_color`
    - `scalar_parameter`
    - `vector_parameter`
    - `texture_parameter_2d`
    - `particle_color`
    - `dynamic_parameter`
    - `fresnel`
    - `depth_fade`
    - `add_pair`
    - `multiply_pair`
    - `emissive_color_scalar`
    - `basecolor_roughness_pair`
  - important implementation detail:
    - route-aware recipe specs use the local `create_material` path so domain, blend, shading model, and two-sided intent are created with the material
    - route usage flags such as `NiagaraSprites` and `NiagaraRibbons` are applied through a local whitelist that calls UE's safe `MaterialEditingLibrary.set_base_material_usage`
    - legacy specs without a route still use confirmed `MaterialTools.create` for asset creation
    - expression create/property/connect/output work uses local `UnrealBridgeMaterialLibrary` guid-aware route
    - this hybrid route is intentional because `MaterialTools.add_expression` does not return the stable guid needed for downstream graph operations
- `material_preview.py`
  - `ribbon` preview route also passed after moving Niagara temp asset duplicate/save/delete to confirmed `AssetTools`
- `texture_import_fix.py`
  - apply mode now saves through confirmed `AssetTools.save_assets`
  - smoke passed on `WhiteSquareTexture`
- `material_domain_rebuilder.py`
  - now supports automatic rebuild from ordinary `Surface` materials into legal:
    - `DeferredDecal`
    - `PostProcess`
  - migration path now carries over:
    - basic nodes
    - node property values
    - node-to-node connections
    - compatible output connections
    - compile + save
  - smoke passed on `M_OfficialTemplateSmoke`:
    - rebuilt legal `DeferredDecal` material with `3` expressions and `1` output connection
    - rebuilt legal `PostProcess` material with `3` expressions and `1` output connection
- `material_preview.py`
  - now chains render-contract gate -> automatic domain rebuild -> preview continuation
  - smoke passed for:
    - `Surface -> DeferredDecal -> continue decal preview`
    - `Surface -> PostProcess -> continue post_process preview`
  - rebuilt legal materials can now be optionally formalized into `material_asset_library` candidates instead of remaining preview-only recovery assets
  - the preview-side formalization route now:
    - registers rebuilt `DeferredDecal` as category `decal`
    - registers rebuilt `PostProcess` as category `post_process`
    - attaches the preview report path to the candidate record for later `auto-promote`

Current partial scene-route note:

- `post_process` preview now uses toolset scene spawning for its preview geometry and volume creation path
- but the final preview still depends on the material actually being a valid post-process material
- a failed `post_process` preview at this stage should first be interpreted as a material-domain or render-contract failure, not automatically as a scene-tooling failure
- `decal` and `post_process` now both have render-contract gate behavior
  - `decal`: requires `Material Domain == DeferredDecal`
  - `post_process`: requires `Material Domain == PostProcess`
  - when the domain is wrong, preview now exits early with:
    - `preview_route = blocked-render-contract`
    - a structured gate finding
  - this prevents misdiagnosing a domain mismatch as a scene-tool or preview-harness failure
  - both gates were smoke-tested against a `Surface` material and now correctly report:
    - `decal_render_contract`
    - `post_process_render_contract`
  - those blocked states are no longer dead ends when the workflow allows recovery:
    - the preview tool can now rebuild into a legal domain material and continue

## Practical Division Of Labor

| Area | Source-backed/local toolset | Local Bridge / Skill | Better Primary Path |
|---|---|---|---|
| Create Material | yes | yes | confirmed API/toolset |
| Add Material Expression | yes | yes | confirmed API/toolset |
| Connect Material Output | yes | yes | confirmed API/toolset |
| Recompile Material | yes | yes | confirmed API/toolset |
| Create Material Instance | yes | yes | confirmed API/toolset |
| Set MI scalar/vector/texture/static-switch | yes | yes | confirmed API/toolset |
| List MI parameters | yes | yes | confirmed API/toolset |
| Duplicate/move/save asset | yes | yes | confirmed API/toolset |
| Texture size query | yes | yes | confirmed API/toolset |
| High-level simple material graph build | partial | yes | hybrid |
| Material graph audit | no | yes | local |
| Stale override detection | no | yes | local |
| Material preview harness | no | yes | local |
| Texture import audit/fix | no | yes | local |
| Generated texture QA | no | yes | local |
| Channel packing / flipbook normalization | no | yes | local |
| Delivery / report packaging | no | yes | local |

## Current Gap Notes

- `TextureTools` surface is currently thin in the tested build; it does not replace the local texture import and QA toolchain.
- Confirmed editor material toolsets are strong at direct mutation, but they do not replace:
  - `material_audit.py`
  - `material_preview.py`
  - `texture_import_audit.py`
  - `texture_import_fix.py`
  - `texture_asset_report.py`
  - `runtime_param_trace.py`
- Therefore confirmed editor material toolsets should be treated as mutation primitives, not as full workflow replacements.

## Recommended Working Rule

1. Use public/source-backed APIs or locally confirmed toolset mutations first when a standard operation exists.
2. Use local tooling immediately after for:
   - audit
   - preview
   - import validation
   - reporting
3. For higher-level material graph authoring, use a hybrid route when needed:
   - source-backed or confirmed toolset route for asset creation
   - local guid-aware bridge operations for downstream graph wiring and property writes
4. Keep `UnrealBridge` as the only external control spine so Codex still has one stable way to talk to UE.
5. When a render-contract recovery produces a usable rebuilt material, prefer registering it as a candidate asset immediately so the result can move into the formal library/promote flow instead of staying a hidden preview artifact.
