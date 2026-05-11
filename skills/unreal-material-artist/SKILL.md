---
name: unreal-material-artist
description: Use when Codex needs to design, author, read, review, optimize, or debug Unreal Engine Materials, Material Instances, Material Functions, texture plans, VFX material shaders, Custom HLSL nodes, shader complexity, instruction and sampler budgets, material graph cleanup, or cm-imagegen texture generation for UE assets. Trigger for requests about UE material nodes, blend modes, shading models, texture-vs-procedural tradeoffs, material performance, Niagara renderer materials, mesh/surface/landscape/UI/post-process materials, or audits of existing material assets.
---

# Unreal Material Artist

## Overview

Use this skill for production-facing Unreal Engine material work: turn a visual target into a usable material, read and critique existing graphs, decide when textures beat pure math, generate needed texture assets, write or review HLSL, and validate performance before calling the asset done.

Treat material work as both art direction and engineering. A material is not finished just because it compiles; it must read correctly in context, expose useful controls, avoid dead graph branches, and fit the target platform.

## Core Workflow

1. Capture the material target.
   Identify domain, carrier, target platform, camera distance, blend mode expectations, lighting model, texture availability, runtime controls, and whether the material is for mesh, sprite, ribbon, decal, UI, post process, landscape, or surface shading.

2. Read before writing.
   For existing assets, inspect `MaterialInfo`, graph outputs, expression nodes, parameter lists, Material Instance override chains, compile errors, instruction counts, sampler counts, and stale overrides before editing or tuning.

3. Choose texture versus computation deliberately.
   Use [references/texture-vs-compute.md](references/texture-vs-compute.md) when the material might use procedural noise, masks, flow, distance fields, flipbooks, atlases, or baked lookup textures.

4. Build the material route.
   Prefer clear graph nodes for ordinary math and engine-tracked texture samples. Use Custom HLSL only when it meaningfully improves fidelity, reduces graph complexity, or implements math that nodes cannot express cleanly.

5. Plan and generate textures when needed.
   Read [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md) or [references/texture-prompt-framework.md](references/texture-prompt-framework.md). Use `C:/Users/QY/.codex/skills/cm-imagegen/SKILL.md` for actual image generation, especially masks, sprite textures, atlases, flipbook drafts, style targets, and texture references.

6. Audit and self-review.
   Use structural checks first, then controlled previews or in-level captures. Read [references/material-audit-workflow.md](references/material-audit-workflow.md) for the review loop and CLI tool.

7. Report tradeoffs clearly.
   Explain the live output chain, performance risks, required textures, platform fallback, and any unresolved visual gap.

## Hard Rules

- Do not rely on screenshots of the Material Editor graph as proof. Read the material graph and output connections through tooling when possible.
- Do not leave dead branches, stale MI overrides, or mystery parameters in a production material after the route is confirmed.
- Do not sample textures manually inside Custom HLSL when a normal TextureSample node keeps UE dependency tracking, sampler state, and audit visibility clearer.
- Do not assume lower instruction count means cheaper if the "optimization" adds large textures, many samples, high overdraw, expensive translucency, or poor cache locality.
- Do not generate final textures from text alone when a design/reference image is available. Cache or use the reference and pass it into `cm-imagegen` as an image input.
- Do not treat AI-generated Flow Maps, Normal Maps, packed masks, or precision lookup textures as final without technical validation; generate drafts only, then verify channels and import settings.

## Performance Judgment

When judging cost, consider all of these:

- Shader math: instruction count, expensive functions, loops, branches, Custom HLSL, feature/quality switches.
- Texture cost: sample count, sampler sharing, texture size, format, mips, filtering, bandwidth, cache behavior, virtual texture stacks, and channel packing.
- Blend and visibility: translucent overdraw, depth fade, refraction, masked alpha cost, two-sided shading, pixel coverage, sorting, and particle count.
- Platform: PC can carry richer materials; Android and low-end targets need fewer samples, smaller textures, additive/unlit defaults, and aggressive fallbacks.
- Runtime control: Dynamic Parameters, Material Parameter Collections, Niagara user params, and per-instance overrides should be intentional and named for use, not for node history.

Use `FeatureLevelSwitch`, `QualitySwitch`, material instances, and texture LOD/import settings when the target platform has materially different budgets.

## Tooling

Use the material audit CLI when UnrealBridge is available:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Path/M_Material --project UnrealAI --markdown --instruction-budget 120 --sampler-budget 4
```

The audit writes under:

```text
<project>/.codex/session/material-delivery/
```

It reports graph output chains, dead branches, stale MI overrides, compile findings, instruction count, sampler count, and optional raw graph data.

## Reference Map

- [references/material-audit-workflow.md](references/material-audit-workflow.md)
  Use for review, cleanup, live-graph readback, stale override detection, and acceptance criteria.

- [references/texture-vs-compute.md](references/texture-vs-compute.md)
  Use when deciding whether to bake detail into textures, compute it procedurally, use flipbooks/atlases, or simplify for platform cost.

- [references/material-node-map.md](references/material-node-map.md)
  Use for a compact map of major UE material node families, HLSL guidance, and how to read graph intent.

- [references/material-recipes.md](references/material-recipes.md)
  Use for reusable VFX/surface material setups, common node patterns, and platform-friendly material recipes.

- [references/master-material-architecture.md](references/master-material-architecture.md)
  Use when designing a project-wide master material system, parameter boundaries, instances, and fallback variants.

- [references/texture-strategy-and-ai-prompts.md](references/texture-strategy-and-ai-prompts.md)
  Use when a material needs a single texture, flipbook, sprite atlas, flow map, mask, or generated texture plan.

- [references/texture-prompt-framework.md](references/texture-prompt-framework.md)
  Use when generating texture prompts or deciding whether a texture is appropriate for `cm-imagegen`.

- [references/official-doc-notes.md](references/official-doc-notes.md)
  Use when you need the source-backed principles behind UE material inputs, expression nodes, Custom HLSL, and performance view modes.

## Collaboration With Niagara VFX Artist

Use this skill for the material side of a Niagara effect: material master/instance design, texture needs, shader math, HLSL, graph audit, and material performance. Use `niagara-vfx-artist` for the Niagara side: systems, emitters, renderers, events, simulation, bounds, culling, and integration. When a task spans both, let this skill own the material and texture contract while Niagara owns carrier behavior and runtime effect structure.
