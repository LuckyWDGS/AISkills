---
name: feature-experience
description: Reusable workflow for shaping and implementing connected product features, not just isolated UI. Use when Codex must decide what a feature/module should contain, how it connects to existing behavior and data, whether a design/reference image is needed, how aesthetics relate to functionality, what adjacent flows are affected, how real data parsing/API/storage, performance/caching/resilience should work, or how to evolve project knowledge while building product features.
---

# Feature Experience

## Overview

Use this skill when the user asks for a feature, module, menu item, workflow, or product surface and the right answer requires product thinking, UX structure, aesthetics, state/data design, and code implementation to stay connected.

## Core Principle

A feature is not only a screen. It has intent, entry points, content, states, related actions, real data ownership, performance expectations, cache/resilience behavior, empty/error cases, visual tone, verification, and future lessons.

## Entry Rules

- Use this skill for feature/module requests even when no design image exists.
- If an explicit design reference is provided, also use `$ui-from-design`.
- If a project-local wrapper skill exists, use it for project-specific code paths, domain flows, and lessons.
- If the current project is explicitly a skill/workflow evaluation harness, treat feature work as a test method, not the goal. The main deliverable is improving the reusable workflow so future projects benefit.
- Ask questions only when product intent, data behavior, legal/content constraints, or irreversible architecture choices cannot be inferred safely.
- When no design is provided, create a small product/UX proposal from existing project patterns before asking for a reference image.
- Implement feature modules against real data sources by default. Do not use fake/sample/hard-coded runtime data unless the user explicitly asks for fake test data or a visual-only prototype.
- When the user provides a design/reference, treat it as the implementation source for the covered module/state. Do not let implementation quietly diverge into a separate solution.
- When a valid design/reference exists for a covered module/state, treat it as the primary execution standard for that surface. Do not let existing code habits, nearby screens, or personal design preference override it unless the deviation is required and documented.
- When generating missing references for a feature, prefer implementation-ready module/state designs over conceptual mood boards. The generated image should reduce implementation ambiguity, not just express a visual direction.
- For generated references, UI mockups, image edits, and missing bitmap assets, use `$cm-imagegen` first by default. Use the system built-in `$imagegen` skill/tool only when the user explicitly asks for it, when `$cm-imagegen` is unavailable or fails for a non-safety/non-policy reason, or when the current task truly requires a system-only capability. Do not use either route to bypass a safety/policy refusal.
- Before generating app/site feature references, confirm or infer the target platform and breakpoint: desktop web, mobile web/H5, native phone, tablet, TV/large screen, or multi-breakpoint responsive. If unclear and it affects layout, density, navigation, or image size, ask a concise question before generation; otherwise record the inference.
- For full-screen web features that need generated UI references, set one canonical desktop viewport/canvas before generating the family. Prefer `1920x1080` for new desktop web surfaces when supported, use the real target viewport when known, and keep all derived states at the exact same dimensions as the accepted anchor unless generating an explicit responsive breakpoint.
- For design-led feature work, require a concrete execution file that records coverage, contract rows, missing generated references, and unresolved user decisions before visible implementation proceeds.
- For design-led features, run an interaction coverage pass before implementation. Every visible control, menu entry, card action, retry button, empty-state CTA, drawer action, tab, filter, search, and state toggle should map to a reference-covered state/screen, a deliberately inline/no-op behavior, or a missing design reference to generate/request.
- When implementation already exists or evolves during the task, run a code-level click audit too. Extract actual handlers such as `@click`, `onClick`, router links, form submits, row/card clicks, menu triggers, and keyboard shortcuts, then reconcile them with the feature/design contract as `covered`, `inline`, or `missing`.
- For design-led features with multiple references or failed/generated variants, require asset lifecycle separation before implementation: accepted references belong in an active folder, rejected/superseded/drifted variants belong in a rejected folder, and both statuses must be reflected in the feature/design execution artifact.
- For non-trivial design-led features, require an operable design relationship map before visible implementation. The map should connect feature areas, design references, parent/derived states, superseded variants, and interaction targets so clicking through it reveals missing destination designs before code invents them.
- For design-led features, lock accepted references by version/scope. When a new image replaces an old one, record the supersede relationship and sync the change through contract rows, hotspot review, design map, and any approved baseline before continuing implementation.
- When a feature uses one primary design plus several generated follow-up references, those follow-up references must stay anchored to the primary design. If they drift, regenerate them before coding the affected modules.
- For design-led features, do not accept follow-up references based on broad similarity alone. Review micro-layout invariants against the anchor before implementation: image dimensions/aspect, shell/navigation, header controls, metrics, gutters, card/column geometry, icon family, profile/user block, and whether only the target state changed.
- For design-led features, run `$ui-from-design`'s Risk Gate Ladder and Static Design Gap Gates in order before visible implementation: reference stability, structure extraction, state binding, inline classification, responsive coverage, real-data pressure, visual-diff reliability, component-system conflict, source interaction audit, review-surface usability, design version lock, change-impact re-entry, flow integrity audit, motion/scroll contracts, asset manifest, feasibility/performance gate, primitive compatibility gate, microcopy/glyph fidelity gate, focus/accessibility contract, data-slot audit, copy source-of-truth contract, form state matrix, role/permission matrix, async/state ownership contract, state precedence matrix, i18n pressure, and risk tiering.
- For design-led feature work, classify each surface as `high`, `medium`, or `low` risk before deciding how much process to apply. High-risk feature surfaces need full gate coverage; low-risk inline behavior may proceed only with a written reason and an upgrade trigger.
- When the image tool supports multiple reference inputs, treat reference selection as part of the workflow. Always include the anchor screen first, then the direct parent screen or nearest accepted state before adding looser contextual references.
- When adding or changing a feature workflow rule, validate it on a real feature task, active harness task, or smallest realistic scenario before treating it as proven. Record the rule, scenario, expected enforcement, observed result, pass/fail, and the next missing capability/tool/verification surface.

## Feature Shaping Workflow

1. Clarify the job:
   - who uses it, what they are trying to do, where they start, and what success looks like.
2. Search before inventing:
   - inspect existing screens, routes, components, state models, storage, APIs, commands, tests, assets, and project memory.
3. Map feature relationships:
   - entry points, destination surfaces, related actions, persistence, permissions, empty/loading/error states, undo/remove actions, search/filter/sort, navigation back paths, and cross-device behavior.
4. Map real data behavior:
   - source of truth, real API/parser/storage path, schema, identity, empty data, invalid payloads, migration, cache, and how the feature behaves when real data is missing or malformed.
   - use mocked/fixture data only inside explicit automated tests or user-requested prototypes, and keep it clearly separated from runtime behavior.
   - distinguish visual examples in the design from runtime content requirements; if real data is empty, the feature must fall back to the true empty/blank behavior, not to illustrative mock content.
5. Map quality attributes:
- latency budget, cache source of truth, stale data rules, offline behavior, retry/backoff, pagination, memory/network cost, concurrency limits, cancellation, and what the user sees while external services are slow.
   - for visual or design-led features, include reference versioning, change re-entry, flow integrity, motion, scroll/sticky behavior, font/icon/asset dependencies, primitive compatibility, microcopy/glyph fidelity, focus/accessibility, data-slot mapping, copy source-of-truth, role/permission variants, form states, async/state ownership, state precedence, i18n pressure, and feasibility/performance limits when they affect what the user sees.
6. Decide whether a design/reference is required:
   - require user/design input for brand-critical visuals, novel layouts, ambiguous taste direction, high-visibility navigation, complex empty states, icons/illustrations, or conflicting product choices.
   - proceed with a small proposed design when the project already has a strong visual system and the feature is a clear extension.
   - generate a reference/mockup only when it will unblock aesthetics or layout; label generated concepts as proposals.
   - for multi-area features, decide this per module/state instead of treating one broad design as enough for the whole feature.
   - for responsive or multi-device features, decide which breakpoint references are needed before generating; do not assume a desktop image fully specifies mobile, tablet, TV, or compact layouts.
   - when the missing gap is detailed design coverage rather than a true product decision, proactively generate the missing module/state reference instead of waiting for the user to request it.
   - when a design already exists but still leaves important areas unclear, ask or generate the smallest missing module/state reference before implementing that area.
7. Connect aesthetics to behavior:
   - visual hierarchy should reflect feature priority.
   - selected/focused/current states should reflect real state.
   - empty states should teach the next useful action.
   - clickable surfaces should have known destinations or inline behavior before coding; if a click opens a new UI state without a reference, add it to missing design coverage.
   - for multi-reference features, operate the design map or equivalent audit surface and record which interactions are covered, partial, missing, or intentionally inline.
   - after code exists, compare the actual live clickable inventory against that map so implementation-only controls do not escape design coverage.
   - destructive or irreversible actions need confirmation or recovery.
   - if a design/reference exists, create the design-to-implementation contract before coding; treat it as a gate, not a summary.
   - if the static reference cannot express version replacement, change re-entry, flow integrity, motion, scrolling, asset dependencies, primitive fit, microcopy correctness, focus/accessibility, data-slot mapping, copy ownership, form validation, permissions, async ownership, state precedence, or localization, add those contracts before coding the visible surface.
8. Implement through existing architecture:
   - prefer local patterns for state, data, routing, persistence, components, and tests.
   - keep scope tight, but include the adjacent flows needed for the feature to feel complete.
   - wire runtime UI to real repositories/parsers/APIs/storage, not placeholder arrays or demo-only constants.
   - keep each implementation change tied to a feature/design contract row or a small infrastructure change required by one.
   - when implementation uncovers a missing state, module, or adjacent flow, add it to the contract and generate/request the needed reference before building the visible UI.
9. Verify the connected experience:
   - test the primary path, empty state, removal/cancel path, navigation, persistence, real data parsing/calling, cache hit, slow/failing network behavior, and visual fit.
   - when relevant, test version replacement sync, change re-entry scope, flow integrity, motion timing/direction, scroll/sticky behavior, asset/font/icon substitutions, primitive compatibility decisions, microcopy/glyph fidelity, focus/accessibility, data-slot mapping, copy source-of-truth, form validation states, role/permission variants, async/state ownership behavior, state precedence, and i18n pressure cases as part of the feature, not separate polish.
   - for design-led visual fit, use screenshot comparison when feasible, but region-scope it to meaningful feature surfaces such as shell, navigation, primary action, empty/error panel, drawer, or card grid. Reuse hotspot/prototype coordinates when they exist, and calibrate thresholds with a no-change screenshot-to-screenshot baseline before interpreting drift. Remember that text-heavy design-vs-DOM hotspot comparisons can be noisy. Treat pixel diff as a signal that guides review; do not let a global screenshot percentage replace contract-row verification.
   - when the project is testing workflow reliability, validate the visual guardrail with a tiny reversible code/style drift, save the failure evidence, then restore the code and rerun the guardrail. The point is to prove the workflow catches real regressions, not to keep the artificial change.
   - if the feature workflow uses a blocking visual gate, let it fail only on approved-baseline drift or unstable runtime baseline. Treat design-vs-reference mismatches as review prompts unless the team has explicitly promoted a specific region to a hard gate.
   - for CI-facing visual gates, keep a machine-readable contract that names each comparison channel, region severity, threshold override, and rationale. Emit a compact gate summary so automation can block on real drift while designers/developers still see non-blocking review signals.
   - when an accepted UI change requires updating the approved visual baseline, do not stop after the write step. Run once with the explicit baseline-update flag, then rerun clean without the flag to confirm the new baseline is actually stable.
   - when auditing feature overlay states such as drawers, confirmations, and dialogs against their parent designs, avoid treating intentional page scrims as shell drift. Compare geometry and unchanged parent controls separately from the dimmed backdrop.
   - for implemented UI, rerun the code-level click audit and confirm no live handler is unclassified or missing design coverage.
10. Evolve memory:
   - record durable product, code, UX, design, asset, and verification lessons in the right global or project-local reference.
   - in skill-evaluation projects, report what the implementation attempt proved about the skill: which guardrail worked, which failed, and what reusable rule was changed.
   - when a workflow rule was added or revised, run a real-task validation loop and record whether the rule actually changed task behavior. If the current task cannot exercise it, mark it unproven and name the next realistic task or harness scenario that should.
   - also record capability gaps, tool gaps, and verification gaps that made the task slower or less reliable, but keep them concrete and incremental.
   - when a gap is cross-project, propose the smallest next workflow/tooling improvement instead of only naming the problem.

## Feature Brief Checklist

- Goal: what job does this feature complete?
- Entry: where does the user find it?
- Contents: what belongs inside this surface?
- Actions: what can the user do from here?
- State: loading, empty, error, offline, selected, focused, disabled, permission, and success states.
- Data: real source of truth, API/parser/storage path, identity, persistence, sync, migration, cache, deletion, and undo.
- Performance/reliability: latency budget, cache freshness, stale fallback, refresh trigger, retry/backoff, cancellation, pagination, memory/network cost, and offline behavior.
- Related flows: search, filters, settings, history, favorites, notifications, sharing, playback, checkout, profile, or admin tools as relevant.
- Aesthetics: density, tone, hierarchy, motion, iconography, imagery, and consistency with the project.
- Static design gaps: design version lock, change-impact re-entry rule, flow integrity audit, motion contract, scroll/sticky contract, asset/font/icon manifest, feasibility/performance gate, primitive compatibility gate, microcopy/glyph fidelity gate, focus/accessibility contract, data-slot audit, copy source-of-truth contract, form state matrix, role/permission matrix, async/state ownership contract, state precedence matrix, and i18n pressure.
- Risk tier: high/medium/low, skipped-gate reasons, and upgrade triggers for inline behavior.
- Reference need: user-provided design, generated concept, existing app pattern, or no extra reference.
- Design coverage: which modules/states are covered, missing, partially covered, or safe to inherit from existing patterns.
- Traceability: which design/reference row maps to which code target, real data/state, interaction, and verification.
- Verification: build/test/screenshot/manual path and what proves the feature works.
- Capability gaps: what still had to be guessed, done manually, or validated weakly, and what smallest next improvement would remove that pain.
- Real-task validation: which workflow rule or guardrail was tested, the scenario used, expected enforcement, observed result, pass/fail, and next gap.

## Design-To-Implementation Gate

When a feature uses a design/reference, write a compact contract before editing user-facing code:

```markdown
| Feature area/state | Design/reference | Code target | Real data/state | Interaction | Verification |
| --- | --- | --- | --- | --- | --- |
| Menu favorites entry | sidebar reference | navigation/menu component | current route + favorites count | D-pad focus/OK opens favorites | device navigation check |
| Favorites empty | generated empty-state reference | favorites screen | persisted favorites empty | primary browse/search action | screenshot + empty storage |
```

Rules:

- The design is not accepted for implementation until each visible area/state has a code target, real state/data owner, interaction behavior, and verification method.
- Do not implement a visible design area from memory, mood, or an unrelated existing layout when it lacks a contract row.
- If a code path cannot follow the design because of platform, performance, architecture, or real-data constraints, update the contract and explain the tradeoff before continuing.
- If static design images do not define version replacement, change re-entry, flow integrity, motion, scrolling, assets, primitive fit, microcopy correctness, focus/accessibility, data-slot mapping, copy ownership, form states, permission variants, async ownership, state precedence, or localization behavior, add contract rows or generate/request focused references before implementing those visible states.
- Final verification should walk the contract row by row, including changed, deferred, or blocked rows.
- Do not call a design-led feature complete when contract rows are still unclear, unverified, or missing required design coverage. Raise the missing rows and resolve them first.

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

Bias toward more, smaller, implementation-ready references when that will reduce ambiguity. A handful of narrow module/state designs is usually better than one sweeping but underspecified composite.

## Research And Evolution

- Read `references/feature-evolution.md` when a project should get smarter over time.
- Search the codebase first.
- Use web search only to fill current gaps in APIs, platform behavior, design-system guidance, accessibility, laws, standards, performance guidance, caching semantics, or current third-party service behavior.
- Prefer official or primary sources. Record the URL, access date, and practical implication when the source affects the work.
- Classify every lesson before writing it: global reusable lessons go in this skill's references; project-specific lessons go only in the project-local wrapper or project memory.
- Do not copy project-only paths, labels, data sources, visual decisions, business rules, or one-off fixes into the global skill. If a local lesson is broadly useful, rewrite it as a generalized pattern before promoting it.

## Real Data Rules

- Runtime feature code must use real data sources, parsers, repositories, APIs, storage, and empty/error states by default.
- Do not ship fake lists, fake cards, fake users, fake recommendations, fake status, or hard-coded "demo" records to make a feature appear complete.
- If real data is temporarily unavailable, implement the honest state: loading, empty, stale cached data, offline, retry, unavailable, or permission required.
- Use fake/mock data only when the user explicitly requests it, when building a clearly labeled visual-only prototype, or inside isolated automated tests. Test fixtures must not become runtime product data.
- When a design contains sample content, treat it as illustrative unless it matches a real data source; wire the UI to real data and preserve the design's structure through real fields.

## Final Response Requirements

- State the feature shape: entry, contents, related actions, and key states.
- State which parts needed separate design references and which were covered by existing patterns.
- State risk tiering decisions and any version-lock, flow-integrity, copy-source, change-reentry, motion, scroll, asset, performance, primitive compatibility, microcopy/glyph fidelity, focus/accessibility, data-slot, form, permission, async ownership, state precedence, or i18n contracts that affected the feature.
- State any newly discovered capability/tool/verification gap that should be the next improvement target for the workflow.
- When the task changes workflow rules or evaluates the skill, state the real-task validation result: rule tested, scenario, expected behavior, observed behavior, pass/fail, and next gap.
- State how design/reference rows mapped to implementation targets when design was involved.
- State how active/rejected design assets and any design map/prototype audit were organized when design was involved.
- State performance/cache/resilience decisions for user-facing data.
- State how the feature uses real data and whether any test fixtures/prototypes were used.
- Name files changed and major architecture decisions.
- Say whether a design/reference was used, generated, requested, or intentionally not needed.
- Report verification performed and remaining risks.
- Mention any durable lesson added to skill memory.
