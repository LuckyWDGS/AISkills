---
name: ui-from-design
description: Reusable workflow for implementing product UI from explicit design references, screenshots, mockups, prototypes, or design images. Use when Codex must match a provided visual design, convert a design into app or web UI, compare implementation screenshots against a design, generate missing visual assets needed for fidelity, split unclear or multi-area designs into precise module-level design targets, or decide which additional local design references must be generated before implementation.
---

# UI From Design

## Overview

Use this skill to turn explicit design references into working UI with visual fidelity and real interactive state. The design is a functional specification, not just a static picture.

## Entry Rules

- Use this skill only when the user's text explicitly identifies an image, screenshot, mockup, prototype, design file, or reference as the UI target.
- If the request is about what a feature should contain, how it connects to related functionality, or whether a design/reference is needed, use `$feature-experience` first and this skill only when a visual design target exists.
- Do not treat an arbitrary uploaded image as a design reference without explicit user intent.
- If a project-local skill or `AGENTS.md` adds stricter rules, follow those rules in addition to this workflow.
- If the design target is missing, inaccessible, too cropped, or ambiguous, ask for the minimum missing information needed to proceed.
- If a design contains multiple functional areas or unclear states, treat it as an overview only. Create a design coverage matrix and generate/request precise module-level references before implementing those areas.
- For long-running projects, use the evolution workflow in `references/evolution.md` so this skill and any project-local wrapper get better over time.

## Workflow

1. Inspect the reference before editing:
   - note viewport, platform, orientation, layout grid, spacing, hierarchy, colors, typography, imagery, icons, density, focus/selection styles, empty/loading/error states, and visible copy.
   - separate real product features from illustrative examples in the mock.
2. Build a design coverage matrix:
   - list each functional area, state, dialog, empty/error/loading view, navigation path, and responsive/device variant.
   - mark each item as covered, partially covered, missing, or blocked by unclear product behavior.
   - do not implement uncovered areas from broad inference when visual fidelity matters.
3. Generate or request missing module references:
   - for unclear or multi-area work, generate focused references for one module/state at a time, such as menu, favorites empty state, details dialog, player overlay, search results, settings form, or error state.
   - prefer small precise images over one large vague screen. The smaller the target, the better the implementation can be checked.
   - label generated references as derived proposals and record what original design or user intent they came from.
   - ask the user only when product intent or taste direction cannot be inferred safely.
4. Translate visual states into app state:
   - selected, focused, hovered, active, checked, disabled, loading, expanded, favorite, progress, and current-item visuals must be driven by state.
   - never hard-code a highlighted item only because it is highlighted in the reference.
5. Identify blockers:
   - missing images, icons, fonts, product copy, interaction rules, navigation rules, focus movement, data source behavior, or target device constraints.
   - ask concise questions only when the answer cannot be safely inferred from the design and project context.
6. Fill asset gaps deliberately:
   - prefer existing project assets and real product/media assets.
   - when a required bitmap asset is missing and no acceptable project asset exists, use the available image-generation skill/tool to generate only the needed asset.
   - save generated assets into an appropriate project asset location and record them in project memory when the project uses an asset index.
7. Implement in the existing stack:
   - follow local framework, component, theme, routing, state-management, and accessibility patterns.
   - keep changes scoped to the requested UI surface and the state required to make it real.
   - preserve responsiveness for the target devices unless the user explicitly asks for a fixed prototype.
8. Verify against the design:
   - run the smallest meaningful build, lint, test, preview, browser, emulator, or screenshot check available.
   - compare the resulting UI against the reference for layout, spacing, visual hierarchy, color, typography, imagery, and state behavior.
   - fix visible mismatches before reporting completion when feasible.
9. Evolve the skill memory:
   - record durable lessons, repeated problems, better patterns, verification tactics, and useful external sources.
   - put cross-project lessons in this skill's references; put project-specific lessons in the project-local skill or project memory.
   - avoid transcript notes, one-off noise, secrets, or unverified guesses.

## Evolution References

- Read `references/evolution.md` when starting a new UI module in a project that should accumulate learning.
- Update that reference only for lessons that help future UI-from-design work across projects.
- If a project has its own wrapper skill, update that project skill's references for local architecture, component, asset, device, build, and verification lessons.
- Classify each design/UI lesson before writing it. Put universal visual-process rules in this global skill; keep project-specific visual language, component names, paths, assets, user taste choices, and screen details in the project-local skill.
- When web research is needed, prefer official or primary sources, record the URL and access date, and store only the distilled project implication.

## Design Extraction Checklist

- Structure: screen shell, navigation, content regions, overlays, dialogs, sidebars, player/tool surfaces.
- Layout: alignment, margins, gutters, card aspect ratios, grid columns, scroll direction, safe areas.
- Visual language: palette, contrast, elevation, borders, radii, glow, blur, shadows, opacity, background treatment.
- Type: hierarchy, size relationships, weight, line height, truncation, wrapping.
- Media: required photos, posters, icons, logos, textures, avatars, thumbnails.
- Interaction: selected, focused, hover, pressed, drag, keyboard/remote navigation, pagination, expansion.
- Data states: empty, loading, error, offline, partial data, no permission, unauthenticated.

## Design Coverage Matrix

Before implementing a large design, write a compact checklist like:

```markdown
| Area/state | Covered by design? | Need generated/requested reference? | Notes |
| --- | --- | --- | --- |
| Home default | yes | no | main reference covers this |
| Favorites empty | no | yes | generate local empty-state reference |
| Details dialog focused episode | partial | yes | needs TV focus state |
| Player overlay paused | no | ask/generate | behavior and controls unclear |
```

Rules:

- Treat big overview images as direction, not proof that all states are specified.
- Generate missing references for the smallest useful unit: one function area, one state, one breakpoint, or one overlay.
- Do not silently invent high-impact screens, dialogs, navigation surfaces, or feature states from a broad visual mood board.
- Keep implementation and verification aligned to the exact reference for that module/state.

## State Fidelity Rules

- Treat every visual state in the reference as a behavior requirement unless the user says it is decorative.
- If the current app lacks the needed state, add the smallest model or prop needed to drive it.
- Use reusable state styles instead of one-off static styling.
- Do not create fake status widgets, memberships, badges, network indicators, weather, analytics, or product data unless the feature exists or the user explicitly asks for a visual-only prototype.
- If a design shows sample content, wire it to real data or documented sample data according to project conventions.

## Handling Unclear Designs

If the design is too broad or unclear, split it into smaller tasks:

- Screen shell and navigation.
- Main content layout and cards.
- Interaction states and transitions.
- Feature-specific modules such as favorites, history, search, settings, details, or player overlays.
- Empty/loading/error/offline states.
- Missing assets and generated asset prompts.
- Responsive behavior for each target device class.
- Verification screenshots or design comparison pass.

When useful, create a derived clarification image or mini mock only after labeling it clearly as an interpretation, not as the original reference. Prefer several precise module references over one vague composite mock.

## Final Response Requirements

- Name the design reference or target area used.
- Summarize any design coverage matrix decisions and generated/requested module references.
- Summarize what was implemented and which states are dynamic.
- Mention generated or missing assets.
- Report the verification/comparison performed.
- Mention any durable lesson added to skill memory.
- State any remaining mismatches or checks that could not be run.
