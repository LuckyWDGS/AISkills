---
name: niagara-vfx-artist
description: VFX lead for Unreal Engine 5.9 Niagara effects through Epic MCP. Use when the user needs Niagara help or a complete usable effect from text, reference images or existing assets - effect direction, reference deconstruction, layers and carriers, systems, emitters, renderers and modules, events and gameplay integration, structural validation, preview capture, scalability, cleanup, and PC or Android performance. Material graphs, textures, HLSL and shader cost go to unreal-material-artist alongside this skill.
---

# Niagara VFX Artist (UE 5.9)

> **Scope.** This skill targets UE 5.9 only and was verified on **UE 5.9.0
> Preview, CL 60351404**. A later build can rename tools and arguments, so read
> the live schema before each first call. Editor work goes through the native
> Niagara tools; the bundled editor helpers are not ported yet (see
> [Tools](#tools)).

## When to use

- Design a Niagara effect from a brief, a reference image or an existing asset.
- Build or repair systems, emitters, renderers, modules and user parameters.
- Hook an effect into gameplay and check activation, completion and cleanup.
- Review an effect for readability, structure and platform cost.

## Roles

- `niagara-vfx-artist` is the VFX Lead and owns the whole effect: visual
  intent, gameplay readability, reference decomposition, layers, carriers,
  systems, emitters, renderers, events, bounds, preview, integration and final
  delivery.
- `unreal-material-artist` is the Material/Shader Specialist. Niagara decides
  what each layer needs from a material (for example `Additive Unlit`,
  `ParticleColor`, `DynamicParameter`, a soft-edge mask, flipbook support, a
  sampler budget) and hands over a contract. Material builds or audits that
  route; Niagara then binds, previews, tunes and validates.
- Ownership runs one way: Niagara directs material work, and Niagara system
  reads, writes and hookup decisions stay here.

## Editor route

Install the sibling `unreal-engine-mcp` and `vfx-flipbook-generator` skills
from the same `skills/ue5.9/` folder and follow the
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md):
background connections, Chinese emitter and module descriptions with stable
IDs on new or modified modules (existing parameter namespaces and bindings
unchanged) and the evidence levels.

All editor operations use the native tools in
[native Niagara control](references/ue-5.9-niagara-mcp.md), called through
`../unreal-engine-mcp/scripts/builtin_mcp.py`:

| Operation | Native owner and tools |
|---|---|
| Create from a template, add or remove emitters | `NiagaraToolset_System`: `CreateNiagaraSystem`, `AddEmitter`, `RemoveEmitter` |
| Structure reads | `GetSystemSummary`, `GetEmitterTopology`, `GetScriptStackTopology`, `GetEmitterData`, `GetRendererData` |
| Renderer, stack and module edits | `SetRendererData`, `SetStackInputData`, `SetModuleEnabled`, `SetSystemData` |
| User parameters | `AddUserVariables`, `GetUserVariables` |
| Compile and diagnostics | `GetSystemCompileState`, `GetStackIssues` |
| Script descriptions | `NiagaraToolset_Assets.SetNiagaraScriptDescription`, `GetNiagaraScriptDigest` |
| Find, duplicate, save, reload | `AssetToolset` |
| Dependent batches, public-API gaps | `PythonScriptingTools` (`await call_tool(...)`) |

`GetSystemCompileState` and `GetStackIssues` wait for an in-flight compile.
Call them separately with a bounded timeout. When a first-load compile keeps
diagnostics waiting, check compile readiness through a background asset load
and report that boundary; the Niagara editor stays closed.

## Workflow

1. **Identify the target effect.** Visual intent, gameplay purpose, camera
   distance, timing, platform, performance budget, integration point and the
   available references.

2. **Cache and inspect supplied images.** Save a local copy of every design
   sheet, reference or keyframe under the workspace before analysis, using
   `reference_cache`, `reference_acceptance`, `layer_evidence`,
   `visual_layer_map`, `design_compare_checklist` and `preview_approval`.
   State which image is the active implementation anchor and its scope
   (`full effect`, `single layer`, `drag trail only`, ...). Proceed when one
   image is supplied and the request names the scope. Ask when several images
   could be the anchor, the scope is ambiguous or the anchor replaces an
   approved one.

3. **Respect anchor authority.** When the anchor changes, earlier previews,
   diffs, tuning notes and diagnoses are historical until revalidated. An
   anchor that exists only in the conversation blocks implementation until it
   is cached locally. A composite sheet and a single-layer crop are different
   anchors.

4. **Decompose the effect into layers.** For each layer decide renderer
   (sprite, ribbon, mesh, component), beam or trail behavior, source and
   receiver events, spawn timing, lifetime, velocity, curves, bounds,
   attachment and scalability.

5. **Request a material contract when a layer needs one.** Give
   `unreal-material-artist` the renderer type, UV expectations, Particle Color
   and Dynamic Parameter usage, texture channels, alpha behavior, blend mode,
   sorting risk and platform budget. For ribbons and trails hand over the ribbon
   UV contract (`U = length`, `V = width`; motion on `U`, width falloff on `V`)
   from
   [carrier-and-ribbon-rules.md](../unreal-material-artist/references/carrier-and-ribbon-rules.md#niagara-ribbon-uv-contract).
   Read back and document any custom UV override.

6. **Build.** Start from a template and write a reviewable mutation plan
   (`niagara_asset_assistant plan-template`, `repair-plan`, `new-plan`; these
   planning modes are local). Apply it with the native tools, reading back
   after each write. A stack edit respects the input's live visibility,
   editability, type and static-switch dependencies; re-query topology after
   changing a static switch.

7. **Validate structure before tuning the look.** Read emitter roles,
   renderer bindings, event handlers, source and receiver data flow, user
   parameters, namespaces, bounds, sim target and renderer materials. Record
   one primary `role` per emitter plus its composite `roles` and
   `capabilities`: a ribbon receiver can also be an Attribute Reader receiver.

8. **Capture and self-review.** Place the system in the level and capture it
   with `../unreal-engine-mcp/scripts/capture.py viewport --pose
   x,y,z,pitch,yaw,roll --frames 3 --interval 0.5 --out-dir
   .codex/session/vfx-delivery/captures/<effect>`. The capture renders that
   pose offscreen through `SceneCaptureToolset`, so the user's camera stays
   put. `capture.py asset <system path>` gives a thumbnail only. Feed the PNGs
   to `visual_diff_qa`, `preview_approval` or `effect_preview_approval` with
   `--preview-path`, and judge silhouette, timing, density, width, color,
   brightness, spacing and gameplay readability against the approved design.
   When the frames show a single simulation state, report that boundary.

9. **Treat new assets as provisional until read back.**
   - A generated texture counts once it is imported and the live material or
     renderer in the reviewed route references it.
   - A new or repaired system counts once its summary, topology, renderer and
     stack data, `GetSystemCompileState` and `GetStackIssues` match the plan,
     its receiver and source roles, renderer family, material bindings and
     data flow are confirmed, and no test asset sits in a production folder.
   - A system named `Ribbon` or `Trail` whose live receiver is still
     sprite-only or has no material is an incomplete test route.

10. **Integrate and accept.** For gameplay hookup or lifetime changes select
    cases from [runtime acceptance](references/runtime-acceptance.md):
    activation, completion, pooling and reset, owner destruction, moving
    bounds, age and seek behavior.

## Validation rules

**Structure**

- Structure is proven by tool reads of emitter handles, renderer types,
  material bindings, event handlers, sim target and bounds.
- Classify the owner of a visual mismatch before tuning: reference, texture,
  material, Niagara, renderer, integration, preview or performance.
- Niagara owns the parameter truth. When a material expects `ParticleColor`,
  `DynamicParameter`, `SubImageIndex`, `RibbonWidth` or custom attributes,
  verify who writes them, where they are bound and that the live system feeds
  the expected values. Prove the system, emitter and renderer binding with
  `GetRendererData` and the stack reads; list data-interface bindings the
  reads cannot show as coverage gaps.
- An emitter can hold several roles. A `Followers` emitter with a Ribbon
  renderer, a bound ribbon material, `NiagaraDataInterfaceParticleRead` and
  `SpawnParticlesFromOtherEmitter` is both `trail-receiver` and
  `attribute-reader-receiver`.
- A missing renderer material starts with the renderer slot: empty
  `RendererProperties` means the renderer or emitter was never constructed.
- Edit through the official tools. When no official route exists, report the
  gap; reflection and export-text writes stay out.

**Look**

- Wrong silhouette or timing: diagnose carrier, renderer and animation before
  raising material brightness.
- Right silhouette but wrong color, alpha, UV flow, edge softness or shader
  detail: hand the material side to `unreal-material-artist`.
- Flipbook and SubUV atlases are power-of-two on both axes. Rebuild or resize
  a non-conforming atlas (for example `2160x4090` to `2048x4096`) and keep the
  raw dimensions in the manifest.

**Delivery**

- Keep previews, audits, tuning logs and diagnoses under
  `.codex/session/vfx-delivery/`.
- Final delivery uses `delivery_package.py --require-ready`, or
  `delivery_package.py check --index <delivery-index.json> --require-ready`.
  Add `--require-visual-qa` for design-fidelity delivery; without it `ready`
  covers structure and asset routes only.
- With `--final-material`, the package consumes the approved material
  delivery report from the sibling `material-delivery` session tree.
- Use structural contract flags or `--effect-type-contract` for
  non-negotiable structure such as Ribbon renderers, material binding,
  Attribute Reader data flow, FixedBounds and no test emitters.
- An approved preview counts for the current anchor revision and the current
  system and material route. Older approvals are historical.
- Promote assets after the delivery index is ready, with `AssetToolset`
  duplicate or move and save, verifying references and refusing an existing
  target. `delivery_finalize.py --dry-run-promote` lists the mappings.

## Image generation

Use `cm-imagegen` for concept images, visual direction and style targets. For
textures, masks, flipbooks and atlases, `unreal-material-artist` decides and
generates the material-facing asset. Cache an existing reference image and use
it as the anchor for generation.

## Tools

Status labels are defined in the
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md#engine-version-and-tool-status).
Commands, flags and outputs: [tool-suite.md](references/tool-suite.md). No
Niagara helper has been ported to UE 5.9 yet, so every editor step uses the
native route above.

| Stage | `local` tools |
|---|---|
| Reference and anchor | `reference_cache`, `reference_acceptance`, `layer_evidence`, `visual_layer_map` |
| Planning | `asset_plan`, `integration_plan`, `control_preset`, `control_binding_generator`, `effect_control_schema` and `control_provenance_check` (without `--live`), `niagara_asset_assistant` (plan modes) |
| Preview and QA | `visual_diff_qa`, `design_compare_checklist`, `motion_qa`, `preview_approval`, `effect_preview_approval` |
| Tuning | `gap_diagnosis`, `parameter_tuning_log` |
| Closeout | `delivery_package`, `delivery_dashboard`, `delivery_finalize` (`--dry-run-promote`), `learning_loop`, `flipbook_builder` |

| `unported` tool | Native route on UE 5.9 |
|---|---|
| `niagara_audit`, `live_asset_verify`, `ue_smoke` | `GetSystemSummary`, `GetEmitterTopology`, `GetEmitterData`, `GetRendererData`, `GetSystemCompileState`, `GetStackIssues` |
| `niagara_material_integration_probe`, `--live` modes of `effect_control_schema` and `control_provenance_check` | `GetRendererData`, `GetStackInputData`, `GetUserVariables` |
| `niagara_asset_assistant apply --execute` | The native writes, one per plan operation, each read back |
| `asset_cleanup`, `delivery_finalize --promote-assets`, `delivery_chain_smoke` | `AssetToolset` duplicate, move, save and referencer reads |

Capture uses the core skill's `capture.py` (`5.9`).

## References

Read only what the task needs. [references/index.md](references/index.md)
lists every reference with when to use it.

| Need | Start with |
|---|---|
| Native tool contracts and verified recipes | [ue-5.9-niagara-mcp.md](references/ue-5.9-niagara-mcp.md) |
| Intake and art direction | [core.md](references/core.md), [request-intake-template.md](references/request-intake-template.md) |
| Building Niagara | [niagara-fundamentals.md](references/niagara-fundamentals.md), [common-effect-patterns.md](references/common-effect-patterns.md) |
| Fluids | [fluids-and-flowmaps.md](references/fluids-and-flowmaps.md) |
| Production and delivery | [production-workflow-map.md](references/production-workflow-map.md), [validation-and-qa.md](references/validation-and-qa.md) |
| Debugging and performance | [debugging.md](references/debugging.md), [platform-optimization.md](references/platform-optimization.md) |
| Tool commands | [tool-suite.md](references/tool-suite.md) |
| Runtime cases | [runtime-acceptance.md](references/runtime-acceptance.md) |

## Response shape

Start from the intended visual result and gameplay readability, and explain
why each major emitter, renderer, event route and integration choice exists.
Prefer concrete modules, curves, spawn logic, renderer settings, bounds and
scalability settings. State platform risk, especially on Android.

1. Artistic direction and effect breakdown
2. Feasibility or approximation notes
3. Niagara system, emitter, renderer and event plan
4. Material contract for `unreal-material-artist`, when needed
5. Integration and scalability notes
6. Validation and self-test plan
