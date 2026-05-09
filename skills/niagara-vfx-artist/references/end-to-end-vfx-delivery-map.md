# End-To-End VFX Delivery Map

## Purpose

Use this reference when the goal is not just advice, but a complete usable UE effect from a text brief or reference image.

The target workflow is:

Input reference or text -> visual deconstruction -> UE-achievable still preview -> motion preview when needed -> approved implementation plan -> texture/material/Niagara/animation hookup -> controlled self-test -> cleanup -> usable delivery.

## Complete Delivery Chain

### 1. Intake And Anchor

Required capability:
- Identify the exact target layer or effect.
- Cache the approved design/reference image locally when available.
- Separate active references from rejected or superseded attempts.
- Record whether the source is authoritative design, style anchor, runtime screenshot, or debug capture.

Common gap:
- Treating a conversation image as if it will always be available later.
- Using a low-resolution montage as an anchor and losing detail.

Needed behavior:
- Always preserve the accepted reference before downstream generation or UE implementation.
- If the authoritative design is not locally available, mark high-fidelity anchored rebuild as blocked instead of improvising from memory.

### 2. Visual Deconstruction

Required capability:
- Decompose visible layers by silhouette, brightness, color, motion cue, residue, spacing, density, and occlusion.
- Decide which parts are material-driven, which are Niagara-driven, and which are baked texture/flipbook driven.
- Map each layer to visible evidence in the reference, not just text labels.

Common gap:
- Naming layers correctly but not proving where they exist visually.
- Missing motion logic such as wing-driven sweep, source attachment, delay, residual fade, or width change.

Needed behavior:
- For each layer, record: visual evidence, UE carrier, expected timing, texture needs, material needs, Niagara needs, and self-test criteria.

### 3. UE-Achievable Preview

Required capability:
- Generate a single-layer still preview that intentionally matches a plausible UE carrier.
- Generate a short motion preview for effects whose quality depends on timing, swing, trail, or residual behavior.

Common gap:
- Making concept art that is beautiful but not a usable implementation target.
- Showing the whole creature or object when the requested layer is a pure effect layer.

Needed behavior:
- Preview the actual carrier idea: ribbon trail, sprite atlas, mesh card, skeletal mask, decal, flow material, or flipbook.
- Keep previews constrained enough that UE can reproduce them.

### 4. Asset Plan

Required capability:
- Decide the minimum texture set, material master/MI, Niagara system/emitter, and optional animation/Blueprint hookup.
- Avoid generating textures before knowing the carrier and shader logic.

Common gap:
- Creating many textures that do not map to the final shader.
- Keeping old wrong-source textures and making the project confusing.

Needed behavior:
- For each texture, state exactly how a shader or renderer will use it.
- Delete or quarantine unused, wrong-route, stale, or superseded assets.

### 5. Material Implementation

Required capability:
- Build a clean material graph or HLSL/custom-node path.
- Read back the graph after authoring.
- Trace live output chains and remove dead branches.
- Keep MI overrides aligned with live parent parameters.
- Tune actual exposed parameters to move toward the approved design.

Common gap:
- Assuming that because nodes exist, they are connected or useful.
- Leaving stale MI overrides after the parent graph changes.
- Stopping at compile success without tuning.

Needed behavior:
- Validate: output connections, compile errors, used/unused expression counts, active parameters, stale overrides, instruction/sampler cost.
- If HLSL improves clarity or fidelity, use it; then validate it as rigorously as a graph node setup.

### 6. Niagara Implementation

Required capability:
- Build emitter structure that matches the carrier route.
- Verify source/receiver/event/data flow, renderer type, material binding, simulation space, bounds, lifetime, width, color, opacity, and spawn timing.
- For trail effects, prove the trail is driven by motion or source points, not faked as an unrelated static card unless that is the approved route.

Common gap:
- Building emitters that exist but do not produce valid source events.
- Mixing mesh/card experiments into a route that was locked to ribbon/trail.
- Judging by a panel screenshot instead of reading the system structure.

Needed behavior:
- Validate emitter roles and data flow before visual tuning.
- Capture in a controlled runtime/preview setup only after structural validation.

### 7. Integration Hookup

Required capability:
- Decide whether the effect attaches to a bone/socket, follows animation notify timing, uses Blueprint/GAS parameters, or runs standalone.
- Expose parameters needed by gameplay or animation: intensity, lifetime, width, color, trigger timing, source transform, left/right side, LOD.

Common gap:
- Creating a good standalone effect that cannot be driven by the actual character motion.

Needed behavior:
- For animation-driven effects, specify how peak frames drive spawn bursts or trail activation.
- Keep source emitters in the coordinate space that preserves residual trails correctly.

### 8. Controlled Visual Self-Test

Required capability:
- Compare against the approved design after implementation.
- Use controlled previews/captures, not editor UI screenshots as primary proof.
- Check still silhouette and motion behavior.

Common gap:
- Proving only that the effect appears, not that it matches the design.

Needed behavior:
- Self-review: silhouette, width, density, brightness, color, residual spacing, motion direction, fade timing, and overdraw.
- Document remaining drift as either tuning work or real-time approximation limit.

### 9. Performance And Scalability

Required capability:
- Check material instructions, texture samplers, particle count, emitter count, overdraw, bounds, culling, LOD, and platform variants.

Common gap:
- High-fidelity PC preview that is too expensive or too broad for gameplay.

Needed behavior:
- Define at least a PC quality target.
- If Android or low-end is in scope, create or plan a fallback route.

### 10. Cleanup And Delivery

Required capability:
- Remove old route assets, stale source PNGs, obsolete screenshots, dead material branches, stale MI overrides, temp actors, and wrong Niagara systems.
- Leave the project with a clear active asset set.

Common gap:
- Delivering a working asset in a dirty folder where old experiments can be mistaken for current implementation.

Needed behavior:
- Keep active assets, rejected assets, debug captures, and project memory separated.
- Before final response, refresh project handoff with changed assets, validation, risks, and next steps.

## Missing Capabilities To Add Over Time

These are the main gaps that would make the workflow more complete and less manual:

- Reference acceptance gate: lock the chosen anchor, quarantine rejected/drifted refs, and record clarity/authority status before generation starts.
- Layer evidence extractor: auto-suggest crops/hotspots and keep each layer tied to visible proof, not only a name.
- Preview approval gate: side-by-side compare reference vs preview with pass/fail/revise state and preset camera/background packs.
- Asset plan generator: derive the minimum texture/material/Niagara asset set, low-end variants, naming, and folder plan before implementation.
- Integration hookup planner: write down socket/notify/Blueprint/GAS/Sequencer ownership, user parameters, trigger timing, and source transform contract.
- Write-side UE helpers: create/duplicate/reset material and Niagara assets, apply EffectType/scalability/folder rules, and safely retire stale routes.
- Visual diff QA: compare captured previews against the approved reference on silhouette, brightness, density, width, spacing, and motion path.
- Delivery packaging: export a final manifest with approved previews, tuning recipe, fallback note, and risk note.
- Learning loop: auto-summarize each shipped effect into a reusable case study and parameter recipe.
- Reference cache tool: save, register, crop, upscale, and classify approved design images automatically.
- Layer map generator: produce a structured layer map from a design image with carrier, timing, texture, material, Niagara, and validation fields.
- Material audit script: report output-connected nodes, dead branches, stale MI overrides, compile errors, instruction/sampler cost, and cleanup candidates in one command.
- Niagara audit script: report emitter count, renderer types, material bindings, event/data dependencies, local/world space, bounds, spawn/lifetime, and likely broken source/receiver chains.
- Preview harness: spawn or preview a system in a controlled scene with fixed background/camera and capture without editor UI.
- Design comparison checklist: score silhouette, color, brightness, density, width, spacing, timing, and motion direction against the approved reference.
- Asset cleanup script: list obsolete/generated/debug assets by lifecycle and safely remove only approved cleanup candidates.
- Parameter tuning log: record which material or Niagara parameters were changed, why, and what visual problem they addressed.

## End State Definition

A usable effect is not just a material, a Niagara system, or a pretty preview.

It is usable only when:
- the target design/reference is known and preserved
- the effect has been decomposed into UE carriers
- previews were approved or the requested implementation target is clear
- material and Niagara assets are structurally valid
- parameters are understood and tuned
- the runtime/captured result is close to the approved design
- old/dirty assets have been cleaned or quarantined
- the next user can find the active assets without guessing
