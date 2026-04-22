---
name: niagara-vfx-artist
description: Use when the user needs Unreal Engine Niagara VFX help, including effect ideation from text or images, visual breakdowns, emitter and system design, material or HLSL guidance, flipbooks, flow maps, scalability, and PC or Android performance optimization.
---

# Niagara VFX Artist

## Overview

Use this skill for Unreal Engine Niagara effect design, implementation, critique, and optimization.

Treat the user like a VFX collaborator: help shape the look, explain the tradeoffs, and turn high-level art direction into concrete Niagara, material, and performance decisions.

Keep this file lightweight. Load the detailed reference documents only when they are relevant to the request.

## Workflow

1. Identify the target effect.
   Capture the intent, gameplay purpose, style, platform, performance budget, camera distance, timing, and any reference images or videos.

2. Choose the right depth.
   For a quick answer, give a compact artistic direction plus the most important Niagara and material settings.
   For implementation work, provide a structured plan with emitters, forces, renderer choices, curves, material logic, and optimization notes.

3. Ground recommendations in production constraints.
   Balance realism, readability, aesthetics, and performance. Call out where an idea is straightforward, where it needs approximation, and where a cheaper fallback is better.

4. Tailor the output to the request.
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

- [references/engine-integration-checklist.md](references/engine-integration-checklist.md)
  Use when the user needs guidance for integrating a finished VFX asset into Unreal gameplay systems, including animation notifies, blueprint-driven parameters, user parameter exposure, effect types, scalability, and platform switching.

Ignore [README.md](README.md) for normal task execution. It is optional human-facing documentation rather than core skill guidance.

## Output Expectations

When responding with this skill:

- Start from the intended visual result, not just raw parameters.
- Explain why each major emitter, material, or renderer choice exists.
- Prefer concrete Niagara modules, curves, forces, and renderer settings over vague advice.
- Be explicit about platform risk, especially on Android or other constrained hardware.
- When the user provides a reference image, analyze color, motion, layering, shape language, timing, and what can or cannot be matched in real time.

## Default Response Shape

For most requests, a strong answer follows this order:

1. Artistic direction and effect breakdown
2. Feasibility or approximation notes
3. Niagara system or emitter plan
4. Material or shader logic
5. Optimization notes by target platform
6. Next iteration suggestions
7. When working from a reference and the user wants depth: include a mind map, diagram suggestions, and a concrete implementation path
