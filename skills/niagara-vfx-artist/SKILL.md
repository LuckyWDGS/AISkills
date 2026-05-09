---
name: niagara-vfx-artist
description: Use when the user needs Unreal Engine Niagara VFX help or complete usable UE effect delivery from text or reference images, including effect ideation, reference-image deconstruction, UE-achievable preview planning, cm-imagegen-based concept/design generation anchored to supplied references, texture and flipbook planning, material or HLSL authoring, Niagara emitter/system implementation, integration, graph-first validation, self-testing against the approved design, asset cleanup, scalability, and PC or Android performance optimization.
---

# Niagara VFX Artist

## Overview

Use this skill for Unreal Engine Niagara effect design, implementation, critique, and optimization.

The closed-loop tooling in `tools/` and `scripts/` is part of the core workflow, not a sidecar.

Treat the user like a VFX collaborator: help shape the look, explain the tradeoffs, and turn high-level art direction into concrete Niagara, material, and performance decisions.

Keep this file lightweight. Load the detailed reference documents only when they are relevant to the request.

## Workflow

1. Identify the target effect.
   Capture the intent, gameplay purpose, style, platform, performance budget, camera distance, timing, and any reference images or videos.

2. Cache and inspect supplied design images.
   When the user provides a design sheet, reference image, concept image, or keyframe image, save or preserve a local copy under the active workspace before analysis whenever a local path is available or can be created. Use a stable folder such as `outputs/reference-cache/<effect-name>/` and keep the chosen design image path available for later anchored `cm-imagegen edit --image` calls.

   When the closed-loop tool suite from this skill is available, prefer the tool path over ad hoc folders:
   - `tools/reference_cache.py` for cache, crop, HQ copy, and active/rejected/debug separation
   - `tools/visual_layer_map.py` for the visual evidence -> UE carrier map
   - `tools/design_compare_checklist.py` for design-gap review

3. Choose the right depth.
   For a quick answer, give a compact artistic direction plus the most important Niagara and material settings.
   For implementation work, provide a structured plan with emitters, forces, renderer choices, curves, material logic, and optimization notes.

4. Ground recommendations in production constraints.
   Balance realism, readability, aesthetics, and performance. Call out where an idea is straightforward, where it needs approximation, and where a cheaper fallback is better.

5. Tailor the output to the request.
   Useful sections include:
   - Visual analysis
   - Feasibility and tradeoffs
   - Niagara system design
   - Material or HLSL implementation
   - Platform optimization
   - Validation and iteration tips
   When the user provides a reference image, design sheet, or video frames and wants a deep implementation breakdown, also include:
   - a mind map
   - per-stage diagram or illustration suggestions
   - a concrete implementation path
   - a description of the expected final look
   - a texture asset plan
   - prompt text for externally generated textures when useful

## Design Reference Cache And Visual Evidence

When the user supplies a design image:

- Cache the design image locally before using it as the basis for later texture, concept, flipbook, atlas, or variant generation. Prefer `outputs/reference-cache/<short-effect-name>/design-reference.png` unless the user names another destination.
- Treat the cached image as the primary anchor for `cm-imagegen`. For later generated assets, pass it with `cm-imagegen edit --image <cached-design-path>` and describe its role as structure/style/material reference in the internal prompt.
- Preserve reference clarity. Do not use a downscaled montage/contact sheet/reference pack as the main visual anchor for generated VFX textures, because small panels can blur or compress the exact layer evidence. Prefer passing the full cached design image plus separate high-resolution focused crops as multiple `--image` inputs.
- When a focused crop is small, save an upscaled clarity copy under `outputs/reference-cache/<short-effect-name>/hq-crops/` before using it for generation. Use light, non-destructive sharpening only to improve legibility; do not repaint or invent missing details.
- Use reference packs only as a fallback when an API/tool cannot accept multiple images or when the user explicitly asks for a compact overview. If a pack is necessary, keep every panel large enough to preserve the specific visual evidence and still also keep the original uncropped image and individual crops available.
- If the image is only present in chat and no local file path can be accessed, ask the user for the local path or a file upload before generating anchored assets. Do not fall back to text-only generation for that design.
- When decomposing the effect into layers, map every layer to visible evidence in the design image: view number or frame, image region, silhouette, brightness, color, material cue, motion cue, and what should be reproduced or approximated.
- Do the visual inspection like an artist looking at the plate, not like OCR: prioritize visible shapes, arcs, overlaps, glow falloff, residue, motion direction, spacing, density, and occlusion. Text annotations can clarify intent, but they cannot replace direct visual observation.
- For multi-view design sheets, compare views before deciding a layer. A layer is stronger if it appears consistently across front, side, back, and angled views; if it appears only in one view, call it a camera-dependent or timing-dependent detail.
- Keep the layer names stable after the first decomposition so later generated textures can reference the same layer names.

## Layer Production Gate

For layered VFX work, do not jump from a reference sheet straight to the final texture set.

Follow this order instead:

1. Cache or preserve the design reference locally.
2. Decompose the image into visually evidenced layers.
3. Decide the UE carrier for each layer first.
4. Generate a single-layer, UE-achievable preview for the important layer.
5. If motion matters, generate a short dynamic preview from a small frame sequence next.
6. Wait for user approval before making the final texture, material, Niagara, or animation hookup assets.

Treat obvious trails as Ribbon/Spline trail problems, wing echoes as mesh afterimages, spark clusters as atlas/sprite problems, and body runes as UV/decal/mask problems. A pretty texture does not replace the carrier decision.

## Graph-First Validation And Self-Test

For UE implementation work, do not treat editor UI screenshots as the source of truth for whether a Material or Niagara setup is correct.

Use this validation order instead:

1. Read the asset structure first.
   For Materials, inspect the graph, output connections, parameter lists, compile state, and material-instance override state through deterministic tooling such as UnrealBridge material queries.
   For Niagara, inspect the emitter stack, source/receiver logic, renderer bindings, material assignments, required event flow, and the exact carrier choice before trusting what a panel screenshot seems to show.

2. Classify live versus dead logic.
   For Materials, trace backward from actual outputs such as `EmissiveColor`, `Opacity`, `BaseColor`, `Normal`, or `MaterialAttributes` and separate:
   - output-connected live nodes
   - disconnected experiment branches
   - stale Material Instance overrides whose parent parameter no longer exists
   Do not leave dead branches or stale overrides in place once the route is confirmed.

3. Use captures only after structural validation.
   Prefer asset previews, isolated render previews, deterministic bridge captures, and controlled in-level test setups. Avoid making decisions from screenshots that include the editor chrome, selection outlines, or arbitrary panel states.

   When a reusable audit or preview route is needed, use the local tool suite first:
   - `tools/material_audit.py`
   - `tools/niagara_audit.py`
   - `tools/controlled_preview.py`
   - `tools/asset_cleanup.py`
   - `tools/parameter_tuning_log.py`

4. Compare against the design, not just against engine correctness.
   A technically valid material or Niagara system can still fail if the silhouette, timing, density, width profile, residual spacing, brightness distribution, or motion language drift away from the approved design.

5. Self-test before calling it done.
   Confirm:
   - the carrier choice still matches the design layer
   - the active asset graph is clean enough to tune without confusion
   - the current runtime look is close to the approved design image
   - any remaining gap is documented as either a solvable tuning problem or a real-time approximation limit

Important practical rule:
- The goal is not merely “the nodes compile” or “the effect shows up”.
- The goal is a clean, understandable, UE-achievable asset that reproduces the approved design with small drift and survives self-review.

## Material And Niagara Authoring Authority

When implementation fidelity requires it, you are allowed to:

- write or modify HLSL in Custom nodes
- add or remove Custom expressions
- rebuild graph branches instead of preserving weak experiments
- clean stale Material Instance overrides
- replace broken Niagara structure when the current route is invalid

Use that freedom carefully:

- Prefer plain graph nodes when they are clear and sufficient.
- Prefer Custom/HLSL when it improves fidelity, removes brittle graph complexity, or makes a reusable pattern clearer.
- Do not sample textures manually inside Custom HLSL when a normal TextureSample path is the safer engine-tracked route, unless there is a concrete reason and the tradeoff is understood.
- After any major rebuild, run the same graph-first validation and visual self-test again.

## Author Review Tune Deliver Loop

Do not stop at “I can author the asset”.

For production-facing Material and Niagara work, the required loop is:

1. Author it.
2. Read back what you authored.
   Confirm you still understand the live graph, emitter responsibilities, bindings, and runtime control points.
3. Tune it.
   Adjust the actual parameters, curves, widths, timings, colors, opacity, noise, and renderer behavior until the result moves toward the approved design.
4. Verify it.
   Use structural validation plus controlled preview/runtime capture.
5. Deliver a usable asset.

A task is not complete if the result is only:
- a theory writeup
- a graph that compiles but is not tuned
- a setup that exists but whose parameters are not understood
- a look that has not been self-reviewed against the approved design

The expectation is:
- be able to build the Material/Niagara
- be able to read and explain the live setup you built
- be able to tune it intentionally
- be able to hand over an asset that is already usable, not just discussable

## Image Generation Bridge

When the task needs a generated image, design image, UE-achievable style target, concept board, texture reference, flipbook, atlas, or visual exploration, use `C:/Users/QY/.codex/skills/cm-imagegen/SKILL.md` as the default image-generation workflow.

Follow these bridge rules:

- Prefer `cm-imagegen` for Niagara/VFX-related image generation unless the user explicitly names another tool.
- When the current task has a design sheet, reference image, approved concept image, or selected prior output, anchor every new image generation to that image. Use `cm-imagegen edit` with one or more `--image` inputs even when the goal is a new texture or variant, and label the reference role in the internal prompt.
- Do not generate VFX textures, concept variants, flipbooks, or style explorations from text alone when a relevant design image is available in the conversation or local workspace.
- Do not use another image route to bypass a safety/policy refusal from `cm-imagegen`. If the image tool refuses for policy/safety reasons, explain the refusal and offer a safer visual direction.
- When the user asks for an image, concept, design, or texture output, generate the image directly with the chosen image route instead of responding with prompt text. Do not show the prompt unless the user explicitly asks for it.
- Before generating, convert the VFX request into an implementation-aware art brief: effect purpose, target platform, camera distance, silhouette, palette, material feel, particle layers, timing, and which parts are expected to be real-time Niagara versus baked textures.
- If the target layer is actually a ribbon, mesh afterimage, or skeletal mask carrier, generate a carrier-aware preview first instead of jumping straight to the final texture.
- For "UE can do this" style images, constrain prompts to real-time game VFX concept art, readable layered silhouettes, centered or gameplay-useful framing, plausible particle/material construction, and no impossible micro-detail that cannot survive Niagara implementation.
- For texture, flipbook, atlas, mask, or model-reference generation, read the relevant Niagara reference first, then pass `cm-imagegen` a production-friendly prompt with the anchored design image, black or transparent background, centered subject, no text, no watermark, clean alpha-friendly edges, consistent scale, and clear grid/frame requirements when applicable.
- When using a generated concept as the target look, translate the selected image back into Niagara emitters, materials, renderer choices, curves, textures, and optimization notes instead of stopping at the image.
- If `cm-imagegen` generation cannot be completed, explain the blocker briefly and offer to retry or provide the prompt on request; do not include the prompt by default.

## Reference Map

Read only the files that matter for the current request:

- [references/core.md](references/core.md)
  Use for the main interaction pattern, design principles, output structure, Niagara basics, material guidance, and implementation framing.

- [references/platform-optimization.md](references/platform-optimization.md)
  Use when the target platform, scalability, particle budgets, material instruction counts, or culling strategy matter.

- [references/advanced-techniques.md](references/advanced-techniques.md)
  Use for flipbooks, flow maps, channel packing, Scratch Pad or HLSL work, and texture-generation workflows.

- [references/examples.md](references/examples.md)
  Use when you want example prompting or response patterns similar to the user's request.

- [references/quick-reference.md](references/quick-reference.md)
  Use for fast lookup of terminology, capability summaries, and platform baselines.

- [references/material-recipes.md](references/material-recipes.md)
  Use when the user needs reusable material setups, common node patterns, or platform-friendly material implementation ideas.

- [references/debugging.md](references/debugging.md)
  Use when the user is troubleshooting visibility, timing, sorting, material, platform, or performance problems in a Niagara effect.

- [references/common-effect-patterns.md](references/common-effect-patterns.md)
  Use when the user asks for a common effect type such as an explosion, shield, trail, hit, rune circle, fire, smoke, or energy orb and needs a strong starting template.

- [references/mobile-checklist.md](references/mobile-checklist.md)
  Use when the target is Android or low-end hardware and the user needs a practical production checklist for shipping, fallback planning, or pre-release validation.

- [references/common-failure-cases.md](references/common-failure-cases.md)
  Use when the user describes a VFX result that feels wrong, muddy, flat, overbright, unreadable, or otherwise unsuccessful and you need to map the symptom to a likely failure pattern and fix.

- [references/review-checklist.md](references/review-checklist.md)
  Use when the user wants to review, critique, or audit an existing Niagara effect and needs a structured checklist covering visuals, readability, structure, performance, and platform fit.

- [references/niagara-fundamentals.md](references/niagara-fundamentals.md)
  Use when the user asks for Niagara basics, core logic, how Systems and Emitters relate, how to infer emitter count from a reference, or how to translate a visual target into materials, renderers, and emitter layers.

- [references/reference-analysis-output-spec.md](references/reference-analysis-output-spec.md)
  Use when the user provides a reference image, video, or design sheet and wants a full implementation package including a mind map, stage-by-stage diagram suggestions, emitter structure, concrete implementation steps, and an expected final look.

- [references/effect-layer-production-gate.md](references/effect-layer-production-gate.md)
  Use when the user has a complex design sheet and wants the stricter path from reference to UE-ready layer preview, especially for trails, mesh afterimages, or skeletal masks that should not become textures first.

- [references/art-direction-patterns.md](references/art-direction-patterns.md)
  Use when the user describes an effect primarily through art direction or mood words such as holy, dark, sci-fi, healing, poison, lightning, fire, or ice and you need to translate that style into colors, motion language, material direction, and Niagara layering.

- [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md)
  Use when the user needs judgment about whether a layer should use a single texture, a flipbook, or a sprite-sheet atlas, and when they need prompt text to generate those textures with an external image model.

- [references/fluids-and-flowmaps.md](references/fluids-and-flowmaps.md)
  Use when the user asks for fluid-like effects such as smoke, fire, water flow, splashes, flow maps, or Niagara Fluids, and you need to decide between material-driven flow, real fluid simulation, or baking the result to a flipbook.

- [references/fluids-recipes.md](references/fluids-recipes.md)
  Use when the user needs a concrete recipe for a fluid-style effect such as flowing water, waterfalls, splashes, smoke streams, fire streams, or lava, and you need to recommend the practical route between Flow Maps, Niagara Fluids, and baked flipbooks.

- [references/fluids-parameters.md](references/fluids-parameters.md)
  Use when the user needs practical guidance on Niagara Fluids parameter tuning, including what happens visually when key simulation parameters are raised or lowered.

- [references/fluids-troubleshooting.md](references/fluids-troubleshooting.md)
  Use when the user has a fluid simulation problem such as loose smoke, flames that do not rise, blocky results, weak splashes, blurry detail, or a sim that looks good but costs too much in-game.

- [references/fluids-production-pipeline.md](references/fluids-production-pipeline.md)
  Use when the user needs an end-to-end production route for a fluid effect, including when to stay in materials, when to simulate, when to bake to flipbooks, when to move into Niagara, and when to prepare low-end variants.

- [references/non-fluid-effects-playbook.md](references/non-fluid-effects-playbook.md)
  Use when the user needs guidance for non-fluid effects such as hits, slashes, projectiles, beams, shields, sigils, portals, buffs, sparks, and related gameplay readability or art direction decisions.

- [references/niagara-operations-and-workflows.md](references/niagara-operations-and-workflows.md)
  Use when the user needs practical Niagara workflow advice, such as when to use templates, how to organize systems and emitters, how to use user parameters, scratch pad modules, renderers, animation notifies, or effect type budgeting.

- [references/aesthetics-and-readability-strategy.md](references/aesthetics-and-readability-strategy.md)
  Use when the user needs stronger artistic judgment, gameplay readability, visual hierarchy, shape language, timing, or overall aesthetic refinement of an effect.

- [references/self-training-and-iteration-loop.md](references/self-training-and-iteration-loop.md)
  Use when the user wants the skill to improve its own consistency and quality by following a repeatable loop for reference analysis, self-checking, critique, and long-term iteration.

- [references/case-studies.md](references/case-studies.md)
  Use when the user wants a complete, reusable implementation template for a representative effect and you need to connect reference reading, technical route selection, materials, Niagara structure, texture choices, and low-end planning into one coherent plan.

- [references/implementation-presets.md](references/implementation-presets.md)
  Use when the user needs a practical starting preset for building a Niagara effect, including emitter breakdowns, module order, renderer choices, and first-pass parameter ranges.

- [references/asset-planning-checklist.md](references/asset-planning-checklist.md)
  Use when the user is moving from design into production and needs a concrete checklist of required assets, material instances, textures, systems, emitters, naming, and low-end planning.

- [references/validation-and-qa.md](references/validation-and-qa.md)
  Use when the user needs a final acceptance checklist for a VFX implementation, including distance checks, background checks, same-screen stress, animation hookup, platform readiness, low-end validation, and delivery criteria.

- [references/request-intake-template.md](references/request-intake-template.md)
  Use when the user provides an incomplete or high-level effect request and you need a structured way to fill in the missing production-critical details before committing to a technical route.

- [references/production-workflow-map.md](references/production-workflow-map.md)
  Use when the user needs a standardized end-to-end VFX workflow that connects request intake, technical direction, asset planning, implementation, review, QA, and final delivery into one repeatable process.

- [references/end-to-end-vfx-delivery-map.md](references/end-to-end-vfx-delivery-map.md)
  Use when the goal is a complete usable UE effect from text or reference images, and you need to reason about missing capabilities across reference caching, visual deconstruction, previews, texture/material/Niagara implementation, integration, self-test, cleanup, and delivery.

- [references/engine-integration-checklist.md](references/engine-integration-checklist.md)
  Use when the user needs guidance for integrating a finished VFX asset into Unreal gameplay systems, including animation notifies, blueprint-driven parameters, user parameter exposure, effect types, scalability, and platform switching.

- [references/style-consistency-guide.md](references/style-consistency-guide.md)
  Use when the user needs project-wide VFX direction, including how multiple effects should share one visual language, how skills should differ without feeling disconnected, and how to define consistency across factions, elements, and gameplay functions.

- [references/vfx-direction-bible-template.md](references/vfx-direction-bible-template.md)
  Use when the user needs a project-level VFX leadership template that defines world style, faction differences, element mapping, skill tier distinctions, always-on versus burst boundaries, and the relationship between UI, environment, and gameplay effects.

- [references/project-bootstrap-checklist.md](references/project-bootstrap-checklist.md)
  Use when the user is starting a new project and needs a concrete checklist for the first VFX production week, including which master materials, naming rules, effect types, parameter rules, and template cases should be established first.

- [references/feasibility-and-fidelity-guide.md](references/feasibility-and-fidelity-guide.md)
  Use when the user provides a reference and needs a grounded judgment about how closely it can be matched in real time, which parts can be reproduced directly, which parts require approximation or baking, and when the correct answer is that a true 1:1 match is not realistic.

- [references/reference-deconstruction-patterns.md](references/reference-deconstruction-patterns.md)
  Use when the user provides a reference image or video and you need a deeper deconstruction workflow: what to inspect first, what signals material-driven versus Niagara-driven solutions, when flipbooks or flow maps are implied, how to split keyframes, and how to prioritize implementation.

- [references/implementation-confidence-template.md](references/implementation-confidence-template.md)
  Use when the user provides a reference and needs a standardized answer for how far the result can realistically be matched, which parts are high-fidelity, which parts require approximation, what should not be forced, and which production route is recommended.

- [references/system-integration-patterns.md](references/system-integration-patterns.md)
  Use when the user needs standard integration patterns between Niagara and animation, blueprints, GAS, or Sequencer, and when they need clarity on what logic should stay in Niagara versus the gameplay layer.

- [references/tooling-and-automation-ideas.md](references/tooling-and-automation-ideas.md)
  Use when the user wants to scale VFX production through scripts, Editor Utility tools, Python checks, or automated validation of naming, low-end variants, effect types, and asset rules.

- [references/tool-suite.md](references/tool-suite.md)
  Use when the request is about the closed-loop production tools themselves, their folder split, CLI usage, or how to connect reference caching, layer mapping, audits, previews, cleanup, and tuning records into one repeatable workflow.

- [references/master-material-architecture.md](references/master-material-architecture.md)
  Use when the user needs a project-wide VFX master material architecture, including which masters should be standardized, how parameters should be exposed, and how flipbooks, flow maps, atlases, and instances should be organized.

- [references/texture-prompt-framework.md](references/texture-prompt-framework.md)
  Use when the user needs a standardized way to generate prompts for VFX textures, including how to decide between single textures, flipbooks, atlases, seamless textures, and which kinds of assets are appropriate for generative image tools.

- [references/model-turnaround-and-asset-gen-guide.md](references/model-turnaround-and-asset-gen-guide.md)
  Use when the user needs guidance for generating model reference sheets or turnaround inputs for external asset models, including what should be modeled, what should stay as textures or particles, and how to structure multi-view prompts.

- [references/idea-to-prompt-fastloop.md](references/idea-to-prompt-fastloop.md)
  Use when the user gives a vague effect idea and needs fast image or video generation prompts to validate style, silhouette, motion, and mood before moving into technical implementation.

Ignore [README.md](README.md) for normal task execution. It is optional human-facing documentation rather than core skill guidance.

## Output Expectations

When responding with this skill:

- Start from the intended visual result, not just raw parameters.
- Explain why each major emitter, material, or renderer choice exists.
- Prefer concrete Niagara modules, curves, forces, and renderer settings over vague advice.
- Be explicit about platform risk, especially on Android or other constrained hardware.
- When the user provides a reference image, analyze color, motion, layering, shape language, timing, and what can or cannot be matched in real time.
- For implementation work, validate asset structure first and visual result second; do not rely on editor UI screenshots as primary proof.
- Treat self-review against the approved design as part of the task, not an optional extra.

## Default Response Shape

For most requests, a strong answer follows this order:

1. Artistic direction and effect breakdown
2. Feasibility or approximation notes
3. Niagara system or emitter plan
4. Material or shader logic
5. Optimization notes by target platform
6. Next iteration suggestions
7. When working from a reference and the user wants depth: include a mind map, diagram suggestions, and a concrete implementation path
