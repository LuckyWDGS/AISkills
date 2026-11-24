# Tech Art Material Systems

## Goal

Extend `unreal-material-artist` beyond single-material graph craft into the technical-art layer where materials become a reusable runtime system.

This reference is for decisions like:

- when to use a Master Material versus a Material Function versus a Material Layer
- how to split authored look from runtime controls
- how MPC, MID, Niagara, Blueprint, C++, and actor state should divide responsibility
- how to keep a project's material system scalable instead of becoming a pile of one-off instances

## Table Of Contents

- [System Layers](#system-layers)
- [Division Of Responsibility](#division-of-responsibility)
- [Anti-Patterns](#anti-patterns)
- [Runtime Trace Thinking](#runtime-trace-thinking)
- [Project-Level Design Rule](#project-level-design-rule)

## System Layers

Think in five layers:

1. Asset Layer
   - master materials
   - material functions
   - texture assets
   - MPC assets

2. Instance Layer
   - MI defaults
   - MI inheritance chains
   - platform / quality variants

3. Runtime Parameter Layer
   - MID overrides
   - MPC writes
   - Niagara-driven attributes
   - Blueprint / C++ writes

4. Renderer / Carrier Layer
   - mesh
   - Niagara sprite/ribbon/mesh
   - decal
   - UI
   - post process

5. Validation Layer
   - shader stats
   - import settings
   - runtime parameter trace
   - preview contract scan

## Division Of Responsibility

Use Master Materials for:

- shared feature sets
- stable parameter names
- consistent sampler and switch strategy
- platform fallbacks

Use Material Functions for:

- reusable logic chunks
- math or surface logic shared across multiple masters
- world-aligned / triplanar / blending / packed-mask decode / normal blending / UV utilities

Use Material Instances for:

- content-side tuning
- art variations
- gameplay or effect variants that do not need graph structure changes

Use MPC for:

- global or zone-level values
- weather
- time of day
- world state that many materials read at once

Use MID for:

- per-actor runtime changes
- UI feedback
- one-off gameplay-driven values
- timelines / animation-driven changes

Expect Niagara-owned bindings for:

- per-particle values
- renderer-driven material semantics like sprite color, dynamic material parameter, ribbon width, or SubUV index

## Anti-Patterns

- One master material per asset.
- Large MI chains where nobody knows which layer set a value.
- MPC for per-instance values.
- MID writes to parameters that should be per-particle Niagara inputs.
- Static switch explosion because "it was easy to expose one more option".
- Custom HLSL solving problems that a Material Function should standardize.

## Runtime Trace Thinking

When a look is wrong, trace in this order:

1. What does the master or base material declare?
2. What does the MI override?
3. Is there an MPC involved?
4. Is a MID or Blueprint changing it?
5. If the material expects Niagara-fed values, has Niagara explicitly declared ownership of them?
6. Which carrier actually renders it?

That is why material-side trace and preview-contract checks exist. The hard part is often not "what does the graph do?" but "what inputs does this material expect, and which runtime system is supposed to own them?" The answer to live Niagara ownership itself belongs to `niagara-vfx-artist`.

## Project-Level Design Rule

Every exposed material parameter should answer these questions:

- Who writes it?
- At author time or runtime?
- One asset, one actor, one effect, or whole world?
- Is it stable enough to live in MI defaults, or dynamic enough to require MID / Niagara / MPC?
- What system is allowed to own it?

If those answers are unclear, the material system is already drifting.
