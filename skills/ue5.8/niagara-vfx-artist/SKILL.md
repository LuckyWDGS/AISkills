---
name: niagara-vfx-artist
description: VFX lead for Unreal Engine 5.8 Niagara effects through Epic MCP. Use when the user needs Niagara help or a complete usable effect from text, reference images or existing assets - effect direction, reference deconstruction, layers and carriers, systems, emitters, renderers and modules, events and gameplay integration, structural validation, preview capture, scalability, cleanup, and PC or Android performance. Material graphs, textures, HLSL and shader cost go to unreal-material-artist alongside this skill.
---

# Niagara VFX Artist (UE 5.8)

> **Scope.** This skill targets UE 5.8 only (verified on UE 5.8.4). Read the
> live schema before each first call. For a UE 5.9 editor the user links
> `skills/ue5.9/` instead; the client refuses an editor of another engine line.

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
from the same `skills/ue5.8/` folder and follow the
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md):
background connections, Chinese emitter and module descriptions with stable
IDs on new or modified modules (existing parameter namespaces and bindings
unchanged) and separate structural, compile, visual and runtime evidence.

Editor operations go through Epic MCP: this skill's tools, or
`../unreal-engine-mcp/scripts/builtin_mcp.py` for a single call. Discover the
`NiagaraToolset_System`, `Assets`, `Component`, `Blueprint` and `Info`
toolsets and their schemas live, and read `ProgrammaticToolset`'s execution
environment before batching. Toolset coverage:
[niagara-mcp-toolsets.md](references/niagara-mcp-toolsets.md).

`GetSystemCompileState` and `GetStackIssues` wait for an in-flight compile.
Call them separately with a bounded timeout. When a first-load compile keeps
diagnostics waiting, check compile readiness through a background asset load
and report that boundary; the Niagara editor stays closed. For an operation
no MCP tool covers, use a stock `unreal.*` API through
`../unreal-engine-mcp/scripts/python_remote.py`.

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

6. **Build.** Start from a template and write a reviewable mutation plan with
   `niagara_asset_assistant.py` (`plan-template`, `repair-plan`, `new-plan`).
   `apply --plan <plan>` dry-runs offline; `apply --plan <plan> --execute`
   runs every operation through the official tools with a readback per write
   and saves only when all succeed. A stack edit respects the input's live
   visibility, editability, type and static-switch dependencies.

7. **Validate structure before tuning the look.** Read emitter roles,
   renderer bindings, event handlers, source and receiver data flow, user
   parameters, namespaces, bounds, sim target and renderer materials. Record
   one primary `role` per emitter plus its composite `roles` and
   `capabilities`: a ribbon receiver can also be an Attribute Reader receiver.

8. **Capture and self-review.** Place the system in the level (find its actor
   with `SceneTools.find_actors`) and capture it with
   `../unreal-engine-mcp/scripts/capture.py viewport --pose
   x,y,z,pitch,yaw,roll --frames 3 --interval 0.5 --out-dir
   .codex/session/vfx-delivery/captures/<effect>`. A posed capture renders
   from that pose, so the user's camera stays put. `capture.py asset <system
   path>` gives a thumbnail only. Feed the PNGs to `visual_diff_qa`,
   `preview_approval` or `effect_preview_approval` with `--preview-path`, and
   judge silhouette, timing, density, width, color, brightness, spacing and
   gameplay readability against the approved design. When the frames show a
   single simulation state, report that boundary.

9. **Treat new assets as provisional until read back.**
   - A generated texture counts once it is imported and the live material or
     renderer in the reviewed route references it.
   - A new or repaired system counts once `niagara_audit.py` (add
     `--diagnostics` and a bounded `--diagnostics-timeout` for compile state
     and stack issues) matches the plan,
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
  `niagara_material_integration_probe.py`; data-interface bindings it cannot
  read are listed in its `coverage_gaps`.
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
- Promote assets after the delivery index is ready.
  `delivery_finalize.py --dry-run-promote` lists the mappings and
  `--promote-assets` runs them as an asset batch with existence readbacks,
  refusing an existing target.

## Image generation

Use `cm-imagegen` for concept images, visual direction and style targets. For
textures, masks, flipbooks and atlases, `unreal-material-artist` decides and
generates the material-facing asset. Cache an existing reference image and use
it as the anchor for generation.

## Tools

Commands, flags and outputs: [tool-suite.md](references/tool-suite.md).
`local` tools run without an editor; `5.8` tools read or write through Epic
MCP on a UE 5.8 editor.

| Stage | `local` tools |
|---|---|
| Reference and anchor | `reference_cache`, `reference_acceptance`, `layer_evidence`, `visual_layer_map` |
| Planning | `asset_plan`, `integration_plan`, `control_preset`, `control_binding_generator`, `effect_control_schema`, `control_provenance_check`, `niagara_asset_assistant` (plan modes) |
| Preview and QA | `visual_diff_qa`, `design_compare_checklist`, `motion_qa`, `preview_approval`, `effect_preview_approval` |
| Tuning | `gap_diagnosis`, `parameter_tuning_log` |
| Closeout | `delivery_package`, `delivery_dashboard`, `delivery_finalize` (`--dry-run-promote`), `learning_loop`, `flipbook_builder` |

| Stage | `5.8` tools |
|---|---|
| Build and repair | `niagara_asset_assistant apply --execute` |
| Readback | `niagara_audit`, `niagara_material_integration_probe`, `live_asset_verify`, `--live` modes of `effect_control_schema` and `control_provenance_check` |
| Capture | `../unreal-engine-mcp/scripts/capture.py` |
| Closeout | `delivery_finalize --promote-assets`, `delivery_chain_smoke`, `ue_smoke`, `asset_cleanup` |

## References

Read only what the task needs. [references/index.md](references/index.md)
lists every reference with when to use it.

| Need | Start with |
|---|---|
| Toolset coverage and helper boundaries | [niagara-mcp-toolsets.md](references/niagara-mcp-toolsets.md) |
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
