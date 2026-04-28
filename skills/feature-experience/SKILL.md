---
name: feature-experience
description: Reusable workflow for shaping and implementing connected product features, not just isolated UI. Use when Codex must decide what a feature/module should contain, how it connects to existing behavior and data, whether a design/reference image is needed, how aesthetics relate to functionality, what adjacent flows are affected, how performance/caching/resilience should work, or how to evolve project knowledge while building product features.
---

# Feature Experience

## Overview

Use this skill when the user asks for a feature, module, menu item, workflow, or product surface and the right answer requires product thinking, UX structure, aesthetics, state/data design, and code implementation to stay connected.

## Core Principle

A feature is not only a screen. It has intent, entry points, content, states, related actions, data ownership, performance expectations, cache/resilience behavior, empty/error cases, visual tone, verification, and future lessons.

## Entry Rules

- Use this skill for feature/module requests even when no design image exists.
- If an explicit design reference is provided, also use `$ui-from-design`.
- If a project-local wrapper skill exists, use it for project-specific code paths, domain flows, and lessons.
- Ask questions only when product intent, data behavior, legal/content constraints, or irreversible architecture choices cannot be inferred safely.
- When no design is provided, create a small product/UX proposal from existing project patterns before asking for a reference image.

## Feature Shaping Workflow

1. Clarify the job:
   - who uses it, what they are trying to do, where they start, and what success looks like.
2. Search before inventing:
   - inspect existing screens, routes, components, state models, storage, APIs, commands, tests, assets, and project memory.
3. Map feature relationships:
   - entry points, destination surfaces, related actions, persistence, permissions, empty/loading/error states, undo/remove actions, search/filter/sort, navigation back paths, and cross-device behavior.
4. Map quality attributes:
   - latency budget, cache source of truth, stale data rules, offline behavior, retry/backoff, pagination, memory/network cost, concurrency limits, cancellation, and what the user sees while external services are slow.
5. Decide whether a design/reference is required:
   - require user/design input for brand-critical visuals, novel layouts, ambiguous taste direction, high-visibility navigation, complex empty states, icons/illustrations, or conflicting product choices.
   - proceed with a small proposed design when the project already has a strong visual system and the feature is a clear extension.
   - generate a reference/mockup only when it will unblock aesthetics or layout; label generated concepts as proposals.
   - for multi-area features, decide this per module/state instead of treating one broad design as enough for the whole feature.
6. Connect aesthetics to behavior:
   - visual hierarchy should reflect feature priority.
   - selected/focused/current states should reflect real state.
   - empty states should teach the next useful action.
   - destructive or irreversible actions need confirmation or recovery.
7. Implement through existing architecture:
   - prefer local patterns for state, data, routing, persistence, components, and tests.
   - keep scope tight, but include the adjacent flows needed for the feature to feel complete.
8. Verify the connected experience:
   - test the primary path, empty state, removal/cancel path, navigation, persistence, cache hit, slow/failing network behavior, and visual fit.
9. Evolve memory:
   - record durable product, code, UX, design, asset, and verification lessons in the right global or project-local reference.

## Feature Brief Checklist

- Goal: what job does this feature complete?
- Entry: where does the user find it?
- Contents: what belongs inside this surface?
- Actions: what can the user do from here?
- State: loading, empty, error, offline, selected, focused, disabled, permission, and success states.
- Data: source of truth, persistence, sync, migration, cache, deletion, and undo.
- Performance/reliability: latency budget, cache freshness, stale fallback, refresh trigger, retry/backoff, cancellation, pagination, memory/network cost, and offline behavior.
- Related flows: search, filters, settings, history, favorites, notifications, sharing, playback, checkout, profile, or admin tools as relevant.
- Aesthetics: density, tone, hierarchy, motion, iconography, imagery, and consistency with the project.
- Reference need: user-provided design, generated concept, existing app pattern, or no extra reference.
- Design coverage: which modules/states are covered, missing, partially covered, or safe to inherit from existing patterns.
- Verification: build/test/screenshot/manual path and what proves the feature works.

## When To Ask For A Reference

Ask for or generate a design reference when:

- the project lacks a nearby visual pattern.
- the user asks for a specific style, premium feel, complex layout, or brand-sensitive screen.
- the feature introduces a new information architecture or major navigation pattern.
- the empty state, illustration, icon, hero image, or animation carries the meaning.
- multiple reasonable layouts would lead to different product behavior.
- an overview design covers the main screen but not a module, dialog, secondary state, empty/error state, or responsive variant.

Do not block on a reference when:

- the feature is a standard extension of an existing screen.
- the code/data behavior is the real blocker.
- a small proposed layout can be implemented and then compared with user feedback.

When references are needed for a complex feature, generate/request the smallest useful set, such as one image for the menu state, one for the favorites empty state, and one for the focused details dialog. Do not ask for or generate a giant all-in-one mockup unless the user explicitly wants it.

## Research And Evolution

- Read `references/feature-evolution.md` when a project should get smarter over time.
- Search the codebase first.
- Use web search only to fill current gaps in APIs, platform behavior, design-system guidance, accessibility, laws, standards, performance guidance, caching semantics, or current third-party service behavior.
- Prefer official or primary sources. Record the URL, access date, and practical implication when the source affects the work.
- Classify every lesson before writing it: global reusable lessons go in this skill's references; project-specific lessons go only in the project-local wrapper or project memory.
- Do not copy project-only paths, labels, data sources, visual decisions, business rules, or one-off fixes into the global skill. If a local lesson is broadly useful, rewrite it as a generalized pattern before promoting it.

## Final Response Requirements

- State the feature shape: entry, contents, related actions, and key states.
- State which parts needed separate design references and which were covered by existing patterns.
- State performance/cache/resilience decisions for user-facing data.
- Name files changed and major architecture decisions.
- Say whether a design/reference was used, generated, requested, or intentionally not needed.
- Report verification performed and remaining risks.
- Mention any durable lesson added to skill memory.
