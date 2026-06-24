---
name: ui-from-design
description: Reusable workflow for implementing product UI from explicit design references, screenshots, mockups, prototypes, or design images. Use when Codex must match a provided visual design, convert a design into app or web UI, compare implementation screenshots against a design, generate missing visual assets needed for fidelity, split unclear or multi-area designs into precise module-level design targets, or decide which additional local design references must be generated before implementation.
---

# UI From Design

## Overview

Use this skill to turn explicit design references into working UI with visual fidelity and real interactive state. The design is the core implementation standard for covered modules/states, not just a static picture or a loose mood reference. Generated references should be implementation-ready rather than conceptual.

## Entry Rules

- Use this skill only when the user's text explicitly identifies an image, screenshot, mockup, prototype, design file, or reference as the UI target.
- If the request is about what a feature should contain, how it connects to related functionality, or whether a design/reference is needed, use `$feature-experience` first and this skill only when a visual design target exists.
- Do not treat an arbitrary uploaded image as a design reference without explicit user intent.
- If a project-local skill or `AGENTS.md` adds stricter rules, follow those rules in addition to this workflow.
- If the project is explicitly a skill/workflow evaluation harness, treat implementation as evidence for improving the skill, not as product delivery. Each code change should prove whether the design-to-code guardrails work and should produce a skill/process update when the guardrails fail.
- If the design target is missing, inaccessible, too cropped, or ambiguous, ask for the minimum missing information needed to proceed.
- If a design contains multiple functional areas or unclear states, treat it as an overview only. Create a design coverage matrix and generate/request precise module-level references before implementing those areas.
- Do not treat a broad design as permission to freestyle the missing half of a feature. Unclear or uncovered areas must be questioned, split, or supplemented before visible implementation.
- Default to filling missing design coverage proactively: generate the missing module/state references unless the blocker is a true product decision that requires the user's choice.
- When generating design references, UI mockups, image edits, or missing bitmap assets, use `$cm-imagegen` first by default. Use the system built-in `$imagegen` skill/tool only when the user explicitly asks for it, when `$cm-imagegen` is unavailable or fails for a non-safety/non-policy reason, or when the current task truly requires a system-only capability. Do not use either route to bypass a safety/policy refusal.
- Before generating an app/site UI design reference, confirm or infer the target platform and breakpoint: desktop web, mobile web/H5, native phone, tablet, TV/large screen, or multi-breakpoint responsive. If the user's request does not make the target clear and the choice affects layout, density, navigation, or size, ask one concise question before generating. If inference is safe, record the chosen platform/breakpoint and why.
- For full-screen web UI references, choose and write down a canonical viewport/canvas before generating a screen family. Prefer `1920x1080` for new desktop web surfaces when supported; use the known production target when one exists. If the active generation path requires dimensions divisible by 16, use the nearest recorded equivalent such as `1920x1088`. After the first accepted anchor, all same-surface states must keep the exact anchor dimensions unless they are intentionally different breakpoints.
- Before visible implementation, create/update a concrete execution file. Use `assets/DESIGN_EXECUTION_TEMPLATE.md` as the preferred template when the project does not already have an equivalent artifact.
- Before coding visible UI, run an interaction coverage pass. Treat every clickable/control surface as a possible route to another design state: primary buttons, tabs, sidebar/menu entries, cards, overflow actions, drawer close/cancel/submit controls, retry buttons, empty-state CTAs, filters, search, and state toggles. Record whether the click is covered by an existing reference, needs a new generated/requested reference, or is intentionally inline/no-op.
- For implemented or partially implemented UI, also run a code-level click audit from the actual source, not only from the design image. Extract framework handlers and interactive elements such as `@click`, `onClick`, router links, form submits, menu triggers, keyboard shortcuts, and row/card click handlers, then reconcile each one against the design coverage table as `covered`, `inline`, or `missing`.
- When a design set has multiple references or any rejected/generated variants, separate assets by lifecycle before coding. Use project-local folders such as `.codex/session/assets/active/` for accepted implementation references and `.codex/session/assets/rejected/` for failed, drifted, superseded, or do-not-use references. Record the same status in `ASSETS.md` and the design execution file.
- When a new accepted reference replaces an old one for the same scope, run a version-lock supersede flow before coding: assign the new reference a version/id, state exactly which prior reference/scope it supersedes, and sync the change through the design execution contract, hotspot/prototype review, design map, and any approved screenshot baseline or review artifact that still points at the old version.
- For non-trivial design sets, create or update an operable relationship map before coding. Prefer `design-map.json` for structured nodes/edges/interactions and `design-map.html` for hover/click inspection. Use `assets/DESIGN_MAP_TEMPLATE.html` and `assets/DESIGN_MAP_DATA_TEMPLATE.json` when the project has no better local tool.
- Operate the design map as part of coverage review: click known targets, inspect hover previews, and mark controls with no accepted target reference as missing design coverage. Do not implement destination UI for an uncovered click from intuition.
- A relationship map is not a full prototype audit. For non-trivial reference images, create or update a hotspot/prototype review surface such as `design-review.json` plus `design-review.html`. Overlay real clickable regions on each design image and mark every region as covered, missing, or inline/no-new-UI.
- The user-facing prototype review should be readable before it is exhaustive. Prefer a progressive flow review that starts from the anchor/home screen, shows only the current screen's clickable points as colored `*` markers, hides repetitive shell/navigation hotspots behind a toggle, and requires the current screen/level to be marked reviewed before navigating into the next level. Keep dense rectangle overlays only as an optional debug view.
- Use marker colors consistently: green `*` opens another accepted design reference, blue `*` is inline/no-new-UI, red `*` is missing or invalid design coverage, and amber `*` means the target exists but lower-level review is not complete.
- Run hotspot review recursively on newly generated destination screens. First-level navigation can be closed while buttons, row menus, card details, dropdowns, and destructive confirmations inside destination screens still lack references.
- Do not mark a level as closed only because every first-level target image exists. A level passes only when every visible control in that level is `covered`, `inline`, or explicitly blocked/missing, and the next level is queued for review. Missing second-level destinations must remain visible as red markers or missing rows until resolved.
- When a valid design reference exists, prefer matching it over your own layout instincts or the convenience of reusing a nearby but visually different existing pattern, unless a documented platform/data constraint forces a deviation.
- Do not keep micro-patching a UI that is structurally unlike the reference. If a rendered screen still has multiple visible mismatches after one focused alignment pass, classify the issue as structural drift, stop local margin/color/button tweaks, and run a fidelity reset: extract the reference's shell, layout grid, spacing scale, type scale, component inventory, and state deltas, then rebuild the affected surface from that scaffold before reconnecting behavior.
- Limit visual alignment loops. A local patch is appropriate for one isolated mismatch; repeated mismatches across sidebar, top bar, cards, tabs, density, or component language mean the implementation model is wrong and must be restructured instead of tuned.
- Once a primary reference is chosen, treat it as the visual anchor for all generated follow-up references. Regenerate any derived module/state image that drifts from the anchor instead of letting implementation blend multiple inconsistent styles.
- Do not accept a generated follow-up reference just because the large layout is recognizable. Compare micro-layout invariants against the anchor: canvas/aspect, sidebar width and labels, header position, gutters, column widths, card radii, icon family, profile/user block, and state-owned data changes. Any visible drift outside the target module/state is a failed reference that must be regenerated before coding.
- When the generation tool supports image references, pass a structured reference pack rather than only a text prompt. Prioritize anchor + parent + sibling + shell crop + changing-module crop + icon/control crop.
- Treat iconography as a first-class consistency target. Check whether button icons, title icons, status icons, sidebar icons, and empty-state icons still belong to the same family before accepting a generated follow-up reference.
- For long-running projects, use the evolution workflow in `references/evolution.md` so this skill and any project-local wrapper get better over time.
- Treat this skill as continuously incomplete on purpose. At the end of each non-trivial design-led task, scan for remaining capability gaps, tool gaps, or verification blind spots that made the work slower, riskier, or more manual than it should be. Record only concrete next gaps, not vague wishes.
- When adding or changing a design workflow guardrail, validate it against a real project task, an active harness task, or the smallest realistic scenario available before claiming it is useful. Record the rule tested, the real task/scenario, the expected enforcement, the observed result, whether it passed, and the next missing capability/tool/verification surface.
- If a guardrail cannot be realistically exercised in the current task, mark it as unproven and name the next task or harness scenario that should test it. Do not treat documentation-only changes as evidence that the skill now works.
- When feasible, add a screenshot/visual-diff guardrail for implemented UI, but treat it as a review trigger rather than a standalone pass/fail. Prefer stable viewport dimensions plus named regions or hotspots such as sidebar, top bar, primary action, cards, and dialogs; derive these regions from an existing hotspot/prototype map when available. Before judging a drift, capture a no-change screenshot-to-screenshot baseline at the same viewport to measure runtime noise, then calibrate hotspot thresholds against that baseline. Whole-page pixel percentages are often too noisy because generated design images and browser-rendered DOM differ in fonts, shadows, antialiasing, and icon rasterization. Small text-heavy hotspots are especially noisy for design-vs-DOM comparisons, so use them mainly as focused review prompts or screenshot-to-screenshot regression probes.
- In a skill-evaluation harness or other high-risk visual workflow, prove the visual guardrail with a temporary real code/style micro-drift, preserve the failing artifact, restore the code immediately, and rerun the guardrail to prove it goes clean. Do not leave artificial drift in the product code.
- When turning a visual guardrail into a blocking check, make only runtime-baseline instability and approved-baseline drift fail the gate. Keep design-vs-DOM differences as non-blocking review signals unless the project explicitly decides otherwise.
- For reusable or CI-facing visual gates, write the blocking/review policy as a machine-readable contract instead of burying it in prose. The contract should name the viewport, comparison channels, per-region severity, threshold overrides, and reasons; the guardrail should emit a compact gate summary with blocking findings separated from review signals.
- When an intentional UI change is accepted and the approved screenshot baseline is updated, rerun the same gate once without the baseline-update flag to prove the new baseline is stable. In workflow harnesses, preserve pre-update and post-update artifacts, and restore the canonical baseline afterward when the change was only an experiment.

## Risk Gate Ladder

Run these gates in order for non-trivial design-led UI work. Earlier failures block later implementation; do not skip to coding because a later gate looks easy.

1. Design-series stability: the active reference set must share one anchor and consistent typography, spacing, icon language, sidebar/top-bar geometry, radii, shadows, and component density. If a sibling or derived state drifts, reject or regenerate it before coding.
2. Structure extraction: do not treat a design as only an effect image. Before visible coding, write the reference-derived structure: shell, regions, grid tracks, fixed vs fluid dimensions, spacing tokens, typography scale, component primitives, and responsive assumptions. If the structure cannot be extracted, generate/request a structural or module-specific reference first.
3. State binding: every selected, focused, hovered, active, expanded, checked, loading, empty, error, progress, and disabled visual must be driven by real app state. A visual state copied from the reference but hard-coded in runtime code is a failure.
4. Inline classification: every `inline` control must have a written reason explaining why no new UI reference is needed. If implementation later reveals a drawer, dialog, picker, confirmation, route, result panel, or other new surface, immediately reclassify it as `missing` and generate/request the smallest reference before implementing it.
5. Responsive coverage: one desktop reference does not automatically cover mobile, tablet, TV, or narrow web. Record the target breakpoint(s), and generate/request separate references when layout, navigation, density, or interaction materially changes.
6. Real data pressure: verify with real parsed/API/repository data by default, including long text, empty lists, many items, slow or failed responses, partial data, and cached/offline states when applicable. Use fake data only when the user explicitly requests a prototype or test fixture.
7. Visual-diff reliability: use full-page diff as a review signal only. Use critical regions, hotspots, and approved runtime baselines for real drift; calibrate with a no-change baseline before making a visual check blocking.
8. Design language vs component system: decide whether the design reference or the existing component system wins for the current surface. If the design wins and the existing primitives cannot match it, rebuild or wrap the component primitives instead of forcing the design through incompatible widgets.
9. Source interaction audit: after implementation, extract live click/submit/router/shortcut handlers from source and reconcile every one as `covered`, `inline`, or `missing`. Extra live controls not in the design contract are drift.
10. Review-surface usability: as design sets grow, keep the user-facing review progressive and marker-based. Keep dense overlays/debug maps for agents, not as the default user review path.

## Static Design Gap Gates

Static references show destination states better than they show behavior, assets, edge cases, or engineering limits. Before visible implementation, assign a risk tier and fill every relevant gap contract in the design execution artifact.

- Risk tiering: classify each surface as `high`, `medium`, or `low`. Use `high` for brand-critical screens, new navigation, drawers/dialogs, forms, permission variants, responsive rewrites, heavy visuals, or anything with real user risk. High-risk rows require all relevant gates. Medium-risk rows require relevant gates plus written skip reasons. Low-risk inline rows may proceed with a short reason, but must be promoted if implementation reveals a new surface, state, role, form, motion, or performance issue.
- Design version lock / supersede flow: every accepted reference should have a stable id or version plus replacement scope. When a new image replaces an old one, record `supersedes`, affected modules/states, and which downstream artifacts must be updated: contract rows, hotspot review, design map, implementation notes, and approved baselines. Do not mix old and new references for the same scope in one implementation pass.
- Change-impact re-entry rule: once a design-led module is implemented, later changes that touch its layout, visible states, copy, data slots, primitives, interactions, or target references must re-enter the existing contract instead of being treated as free-form incremental edits. Reopen the affected rows, mark what changed, and rerun the relevant gates before closing the change.
- Motion contract: for drawers, menus, tabs, accordions, loading skeletons, hover/focus/pressed states, route transitions, and overlays, record trigger, start/end state, duration, easing, direction, delay, interrupt/cancel behavior, reduced-motion behavior, and verification. If the static reference does not define the transition and the motion affects meaning or usability, generate/request a small storyboard or write a contract before coding.
- Scroll contract: record scroll containers, fixed/sticky headers or sidebars, sticky table columns, overflow clipping, nested scroll, scroll restoration, infinite/paged loading, keyboard/remote focus movement, and scrolled-state visuals. Generate/request a scrolled-state reference when sticky or overflow behavior changes what the user sees.
- Flow integrity audit: do not review only isolated screens. For every covered path, record the entry, destination, return path, cancel/close path, retry path, and any undo/remove/confirm branch. A screen family is not closed until its important forward and backward transitions are coherent and covered.
- Asset/font/icon manifest: list required fonts, fallbacks, icon family/source, stroke/fill rules, shadows/elevation, blur/backdrop effects, logos, photos, illustrations, and generated bitmap assets before implementation. If the project lacks a matching asset, import/generate/substitute deliberately and record the visual tradeoff.
- Feasibility/performance gate: check expensive blur, translucent layers, large shadows, gradients, nested scroll areas, heavy media, animated backgrounds, canvas/WebGL, and high-frequency animations against the target device/browser. If the exact design is too costly, record the smallest visual concession and why before coding it.
- Primitive compatibility gate: before reusing an existing button/input/card/list/dialog primitive, compare it against the design's geometry, spacing, radii, type scale, icon alignment, state layers, and interaction model. Decide explicitly whether to inherit, wrap, fork, or rebuild. Do not force an incompatible shared primitive through repeated local overrides.
- Microcopy / glyph fidelity gate: treat small labels, tab names, field labels, helper text, badge text, Chinese/Japanese/Korean microtext, and other dense UI copy as a separate acceptance surface. If the image generator distorts glyphs, writes the wrong words, or produces unreadable small text, do not accept the image as implementation-ready until that region is regenerated, post-edited, or replaced by real runtime text in code.
- Focus / accessibility contract: record focus order, visible focus treatment, hover-to-focus parity where relevant, keyboard/remote triggers, escape/back/enter/space behavior, focus trap/release, semantic roles, labels, accessible names, and screen-reader-critical announcements. If the visual design does not clarify this, inherit from an existing accessible pattern or write the contract before coding.
- Data-slot audit: every visible slot in the design such as title, subtitle, tag, status badge, count, owner, timestamp, source label, avatar, thumbnail, or metadata row must map to a real field, derived field, or deliberate fallback. If the data source cannot stably provide the slot, record the degradation or request/design a different slot behavior before implementation.
- Copy source-of-truth contract: for high-visibility UI copy such as titles, button labels, empty-state text, field names, helper text, menu items, confirmations, and errors, record the final source of truth: design reference, product copy doc, i18n resource, API field, or local config. Do not let design copy, product copy, and implementation copy drift independently.
- Form state matrix: for every form or input surface, cover default, focus, hover when applicable, validation error, disabled, required/optional, submitting, success, permission/no-access, and server failure. Missing high-impact states require a generated/requested reference or an inherited component rule with a written reason.
- Role/permission matrix: list which controls and states appear for admin, member/user, guest, unauthenticated, read-only, and no-permission cases as relevant. Decide hidden vs disabled vs upgrade/login prompt explicitly; do not silently hide or invent controls because one reference shows only one role.
- Async race / state ownership contract: for dynamic UI, record source of truth, which request or action owns the visible state, cancellation/ignore policy for stale responses, optimistic vs confirmed updates, retry behavior, concurrency limits, and which result wins when responses return out of order. Loading, success, and error visuals must follow that policy instead of whichever promise resolves last.
- State precedence matrix: when more than one visible state can apply at the same time such as permission denied, fatal error, retrying, stale cache, filtering, submitting, empty after filter, or loading more, record which state wins, what can coexist, and which state decorates rather than replaces the base UI.
- I18n pressure: test or plan for CJK/Latin differences, long English/German-like labels, unbroken tokens, RTL direction when supported, and localized numbers, dates, currencies, and pluralization. Generate/request separate breakpoint or RTL references when layout direction or text expansion materially changes the UI.
- Text/glyph drift repair rule: when a generated image is structurally correct but a small text region is wrong, prefer the narrowest repair path first: regenerate only the affected region/state, post-edit the local text area, or record that the final implementation must use real rendered text instead of trusting the generated glyphs. Do not throw away a good layout anchor just because two tiny labels drifted.

## Workflow

1. Inspect the reference before editing:
   - note viewport, platform, orientation, layout grid, spacing, hierarchy, colors, typography, imagery, icons, density, focus/selection styles, empty/loading/error states, and visible copy.
   - if the design still needs to be generated, choose the platform/breakpoint first and record the canvas decision before prompting.
   - separate real product features from illustrative examples in the mock.
   - treat the design reference as the source for the covered UI behavior and visual decisions, unless the user explicitly says a visible element is decorative or only conceptual.
   - identify whether repeated cards, fake counts, placeholder labels, mixed state panels, or sample tasks are demonstrating possible states rather than specifying runtime data that should remain on screen.
   - assign the risk tier, run the Risk Gate Ladder top-down, run the relevant Static Design Gap Gates, and record any blocker in the design execution artifact.
2. Build a design coverage matrix:
   - list each functional area, state, dialog, empty/error/loading view, navigation path, and responsive/device variant.
   - list each visible interaction and its target state/screen. If clicking something should reveal another UI and that UI is not represented, mark it as missing design coverage.
   - when code already exists, cross-check the visual interaction list against the implementation's actual click handlers so invisible or easy-to-miss live controls are not skipped.
   - mark each item as covered, partially covered, missing, or blocked by unclear product behavior.
   - for each `inline` row, write the reason it does not require a new reference and the trigger that would promote it to `missing`.
   - distinguish first-level screen coverage from per-screen hotspot coverage. A target screen existing does not prove every visible button inside that screen is covered.
   - for multi-screen sets, build a progressive review queue: anchor/home first, then first-level destinations, then drawers/menus/dialogs/details, then deeper confirmations or inline-expanded states.
   - do not implement uncovered areas from broad inference when visual fidelity matters.
   - write this matrix into the active design execution file rather than keeping it only in scratch reasoning.
   - when several references exist, ensure every row points to an active reference path, not a rejected or superseded file.
   - if a new accepted image replaces an old one, record the supersede relationship and the exact rows/artifacts that must be updated before implementation continues.
3. Generate or request missing module references:
   - for unclear or multi-area work, generate focused references for one module/state at a time, such as menu, favorites empty state, details dialog, player overlay, search results, settings form, or error state.
   - prefer small precise images over one large vague screen. The smaller the target, the better the implementation can be checked.
   - when the missing gap is visual/layout/state coverage rather than a product decision, generate first instead of waiting for the user to notice the gap.
   - generate references that can be implemented directly: they should make the module shell, alignment, hierarchy, visible controls, text slots, state differences, and expected occupancy/empty behavior clear enough to map into code without extra guesswork.
   - describe the primary reference's shell, spacing logic, controls, palette, and component language in the generation prompt so follow-up references stay visually compatible with the anchor.
   - if the tool allows only a small number of reference images, spend those slots on the most structurally informative images: primary anchor first, then direct parent state, then the nearest accepted sibling, then focused crops of the shared shell and the changing module.
   - label generated references as derived proposals and record what original design or user intent they came from.
   - move failed or drifted generated images into the rejected asset folder once a better candidate replaces them.
   - ask the user only when product intent or taste direction cannot be inferred safely.
4. Create a design-to-implementation contract:
   - map every design area/state to the code component/file that will implement it, the real data/state that drives it, the interaction behavior, and the verification method.
   - do not treat the design as a standalone artifact. Each generated/requested design reference must have an implementation target and acceptance criteria.
   - do not start coding a module until its design reference, functional behavior, data/state mapping, and verification expectation are connected.
   - include design version lock, change-impact re-entry, flow integrity, motion, scroll/sticky behavior, asset/font/icon dependencies, performance concessions, primitive compatibility, microcopy/glyph fidelity, focus/accessibility, data-slot mapping, copy source of truth, form states, role/permission variants, async/state ownership, state precedence, and i18n pressure rows when they affect visible behavior.
   - treat the contract as an implementation gate: no visible UI row, no visible UI code, unless the row is necessary infrastructure for a mapped area.
   - write the contract into the design execution file so implementation can be audited against it later.
   - keep the design map synchronized with accepted/rejected references, derivation edges, superseded links, and missing interaction targets.
   - keep the hotspot/prototype review synchronized with each reference image's visible controls and missing second-level targets.
   - keep a readable flow-review surface for users and a dense debug overlay for agents when both are useful. The readable view should avoid covering the design with many boxes; mark clickable points with `*`, show details in side panels, and lazy-load only the current image when possible.
5. Translate visual states into app state:
   - selected, focused, hovered, active, checked, disabled, loading, expanded, favorite, progress, and current-item visuals must be driven by state.
   - never hard-code a highlighted item only because it is highlighted in the reference.
6. Identify blockers:
   - missing images, icons, fonts, product copy, copy source decisions, text/glyph fidelity decisions, interaction rules, motion rules, scroll/sticky rules, navigation rules, return/cancel path rules, focus movement, accessibility semantics, primitive compatibility decisions, data-slot mapping, form states, permission/role states, async ownership rules, state precedence rules, i18n behavior, data source behavior, or target device constraints.
   - ask concise questions only when the answer cannot be safely inferred from the design and project context.
   - when the missing information affects a visible module/state, stop that row and resolve it through a question or a focused derived reference instead of partially implementing it.
7. Fill asset gaps deliberately:
   - prefer existing project assets and real product/media assets.
   - when a required bitmap asset is missing and no acceptable project asset exists, generate only the needed asset. Use `$cm-imagegen` first by default; use the system built-in `$imagegen` route only for explicit user requests, `$cm-imagegen` failure/unavailability, or a true system-only need.
   - save generated assets into an appropriate project asset location and record them in project memory when the project uses an asset index.
8. Implement in the existing stack:
   - follow local framework, component, theme, routing, state-management, and accessibility patterns.
   - keep changes scoped to the requested UI surface and the state required to make it real.
   - preserve responsiveness for the target devices unless the user explicitly asks for a fixed prototype.
   - trace every UI code change back to a design coverage row or design-to-implementation contract row.
   - build the design skeleton before polishing details: page shell, major regions, grid tracks, spacing tokens, typography scale, card/button/input primitives, icon family, and state styles should exist as shared structure before filling content.
   - implement version-lock decisions, re-entry decisions, flow integrity, motion, scroll/sticky behavior, primitive choices, microcopy/glyph decisions, focus/accessibility behavior, data-slot mapping, copy-source decisions, form state, role/permission, async/state ownership, state precedence, i18n, and asset choices from the contract, not from intuition.
   - if the first screenshot review shows broad mismatch, do not chase one-off CSS patches. Replace the affected structure or component primitive so all related areas move toward the design together.
   - use real project data paths by default. Do not add fake runtime content, placeholder metrics, or invented records unless the user explicitly asked for fake/prototype data.
9. Verify against the design:
   - run the smallest meaningful build, lint, test, preview, browser, emulator, or screenshot check available.
   - compare the resulting UI against the reference for layout, spacing, visual hierarchy, color, typography, imagery, and state behavior.
   - run a real-data pressure pass for UI surfaces that render dynamic data: long labels, empty collections, many records, slow loading, failed requests, partial data, and cache/offline fallback when those states are possible.
    - verify version lock when references changed: contract rows, hotspot review, design map, and approved baselines should all point at the accepted version.
   - verify change-impact re-entry when modifying an already-covered module: affected rows should be reopened, updated, and revalidated rather than silently patched.
   - verify flow integrity when relevant: covered entry, destination, cancel/close, return, retry, and undo/remove paths should all land in an expected state.
    - verify motion and scroll behavior when relevant: transition direction/duration, reduced-motion fallback, sticky/fixed regions, overflow clipping, scroll restoration, and focus movement.
    - verify asset/font/icon fidelity from the manifest and call out every deliberate substitution.
    - verify primitive compatibility decisions when relevant: shared primitives should either match the design system need or be intentionally wrapped/forked, not patched ad hoc per screen.
    - verify microcopy/glyph fidelity when relevant: small labels, field names, tabs, badges, and dense CJK text should be readable and semantically correct; if the image tool failed there, record the repair path instead of pretending the image is implementation-ready.
    - verify focus/accessibility behavior when relevant: visible focus, keyboard/remote triggers, escape/back, semantic roles, and screen-reader-critical text.
    - verify data-slot mapping and fallback behavior with real data samples, especially for null, missing, or unexpectedly long values.
   - verify copy source-of-truth when relevant: visible copy should trace to one authoritative source, and any deliberate deviation should be recorded.
    - verify form state, role/permission, async ownership, state precedence, and i18n pressure matrices for covered high-risk surfaces.
   - when visual diff tooling is available, compare at the canonical viewport and named critical regions. Prefer reusing hotspot/prototype coordinates for clickable controls, but calibrate them differently from broad layout regions. First run a no-change screenshot-to-screenshot baseline when possible; if the baseline is stable, later hotspot warnings are stronger evidence of real drift. Use direct design-vs-implementation diff to focus inspection, not to replace judgment, and use control-level or hotspot-level screenshot-to-screenshot probes to catch small drift that a full-canvas percentage would hide.
   - if the task is explicitly validating the workflow itself, deliberately introduce a tiny reversible CSS/layout drift in a safe local edit, verify that the guardrail fails on the intended region, then remove the drift and verify the guardrail returns to clean.
   - if the visual guardrail is used in CI or as a blocking gate, separate blocking vs non-blocking outputs explicitly. Blocking should come from calibrated approved-baseline drift or unstable no-change baseline; design-vs-reference noise should stay visible but non-blocking.
   - if a region should be promoted to hard failure, record that decision in a small contract/config file with the region id, comparison channel, threshold, severity, and rationale, then emit a machine-readable summary suitable for CI or PR review.
   - if the approved baseline is intentionally updated, verify the update flow in two passes: one run with the explicit update flag to write the baseline, then one clean rerun without the flag to prove the new baseline is stable and not only self-passing because it was rewritten in the same step.
   - when comparing an overlay state such as a drawer, dialog, or menu-on-scrim against its parent design, do not treat full-shell dimming as automatic drift. Mask or discount intentional scrims and focus the review on shell geometry, unaffected controls, and whether only the target interaction state changed.
   - verify each contract row, not only the overall screenshot mood.
   - diagnose mismatch class before fixing: `local` means one bounded element is off and may be patched; `systemic` means repeated spacing, density, shell, typography, component, or icon drift and requires a fidelity reset. Record the class in the design execution artifact.
   - after one failed systemic alignment pass, pause implementation and rebuild from the reference-derived scaffold instead of continuing small tweaks. Do not report completion while the work is still in a patch loop.
   - when comparing derived design references to their anchor, verify both macro-layout and micro-layout. A state reference is not accepted if it changes unrelated shell details, navigation vocabulary, profile area, icon language, totals, gutters, or card geometry.
   - verify design-map links and interaction coverage before claiming the design set is implementation-ready.
   - verify hotspot coverage on the actual reference images before claiming an interactive design set is closed.
   - operate the progressive flow review level by level. Start at the anchor/home screen, mark it reviewed only after its visible points are covered/inline/missing, then continue to level 1 and deeper states. If a target opens but its child controls are unreviewed, report it as next-level work rather than silently passing the whole flow.
   - after implementation, verify the actual source-level clickable inventory against the design contract. A UI is not closed if the code contains live clicks that are neither covered by a reference nor explicitly inline/deferred.
   - fix visible mismatches before reporting completion when feasible.
10. Evolve the skill memory:
   - record durable lessons, repeated problems, better patterns, verification tactics, and useful external sources.
   - put cross-project lessons in this skill's references; put project-specific lessons in the project-local skill or project memory.
   - when working inside a skill-evaluation harness, explicitly classify every observed drift as a skill failure, project-specific exception, or implementation bug before deciding whether to patch global skills.
   - when a new or revised workflow rule is part of the task, run a real-task validation loop: choose the closest real task or smallest realistic harness scenario, state what the rule should prevent or force, observe whether it actually changes the work, and record the result.
   - if the validation fails or only partially works, patch the skill, template, tool, or project wrapper in the same turn when feasible, then record the remaining gap instead of declaring the rule complete.
   - before ending a skill-evaluation pass, ask three concrete questions: what capability is still missing, what tool or automation would reduce recurring manual work, and what smallest next patch would make the workflow more usable in a real project.
   - if a gap is cross-project and actionable, add it to the capability-gap section of the design execution artifact or project memory with a recommended next increment.
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
- Version lineage: active reference id, replaced reference id, replacement scope, and synced downstream artifacts.
- Change re-entry: which later modifications reopened prior rows, why, and what had to be revalidated.
- Interaction: selected, focused, hover, pressed, drag, keyboard/remote navigation, pagination, expansion.
- Flow integrity: forward path, return path, cancel/close path, retry path, undo/remove path, terminal states.
- Motion: transition trigger, duration, easing, direction, interruption, loading shimmer, reduced-motion fallback.
- Scroll: scroll container, sticky/fixed regions, overflow clipping, restoration, nested scroll, scrolled-state visuals.
- Assets: font files or fallbacks, icon source/family, image provenance, shadow/blur feasibility, generated assets.
- Primitive fit: existing shared component match, required wrapper/fork, state-layer differences, icon/text alignment fit.
- Microcopy fidelity: small labels, dense text zones, CJK glyph integrity, text-correction path, real-rendered fallback.
- Accessibility: focus order, visible focus, keyboard/remote actions, semantic roles, labels, announcements, trap/release behavior.
- Data slots: real fields, derived fields, null handling, truncation, hidden-when-missing behavior, fallback copy.
- Copy source: design text, product copy doc, i18n key, API field, local config, or explicit override owner.
- Async ownership: source of truth, loading owner, stale response policy, optimistic updates, cancellation, retry, reconciliation.
- State precedence: coexisting states, winner state, decorator states, replacement states, priority order.
- Forms and permissions: validation, disabled/submitting/success/no-access states, role-based visibility.
- I18n: long labels, wrapping/truncation, RTL, localized dates/numbers/currencies.
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

## Design-To-Implementation Contract

After the coverage matrix, create a compact traceability table before coding:

```markdown
| Design area/state | Design reference | Code target | Real data/state | Interaction | Verification |
| --- | --- | --- | --- | --- | --- |
| Favorites empty | generated favorites-empty ref | FavoritesScreen | favorites flow empty | browse/search action focused | screenshot + empty DB |
| Focused card | home design | MovieCard | Compose focus state | D-pad focus/OK | TV emulator focus check |
```

Rules:

- Write the contract before editing user-facing UI code, and keep it updated when discoveries change the scope.
- A design reference without a code target is only a concept, not implementation guidance.
- A code change without a design row is drift unless it is infrastructure needed by a mapped row.
- Every generated design must say what feature/module/state it is meant to implement.
- Every implemented module must be checked against its own mapped reference.
- If the implementation cannot follow a design row because of real data, platform, performance, or architecture constraints, update the contract and explain the tradeoff before continuing.
- Final verification must walk the contract row by row and mark each row implemented, changed, deferred, or blocked.
- Do not mark a design-led module as complete while contract rows are still missing required reference, behavior, or verification. Surface the blocked rows explicitly.

## State Fidelity Rules

- Treat every visual state in the reference as a behavior requirement unless the user says it is decorative.
- If the current app lacks the needed state, add the smallest model or prop needed to drive it.
- Use reusable state styles instead of one-off static styling.
- Do not create fake status widgets, memberships, badges, network indicators, weather, analytics, or product data unless the feature exists or the user explicitly asks for a visual-only prototype.
- If a design shows sample content, wire the UI to real data fields and real app state by default. Use documented sample data only for explicit prototypes or isolated tests, not runtime feature implementation.
- If a design shows occupied cards or task rows only to illustrate layout/state possibilities, do not keep those cards when the real runtime list is empty. Render the honest empty state, blank area, or no-section variant required by the product instead.

## Handling Unclear Designs

If the design is too broad or unclear, split it into smaller tasks:

- Screen shell and navigation.
- Main content layout and cards.
- Interaction states and transitions.
- Motion and scroll/sticky behavior that static images do not define.
- Focus/accessibility behavior that static images do not define.
- Data-slot mapping from design placeholders to real data fields.
- Microcopy and glyph integrity for dense labels and CJK text.
- Copy source of truth for visible labels and messages.
- Feature-specific modules such as favorites, history, search, settings, details, or player overlays.
- Empty/loading/error/offline states.
- Async request/state ownership and stale-response behavior.
- State precedence where loading/error/empty/filter/cache/permission states can overlap.
- Flow integrity across entry, destination, close/back, and retry/undo branches.
- Forms, validation, permissions, and role variants.
- Primitive compatibility decisions for reused shared components.
- Design version replacements and which artifacts must be resynced.
- Change-impact re-entry when revisiting an already-implemented module.
- Font/icon/asset manifest and substitutions.
- I18n pressure for long text, RTL, and localized values.
- Text drift repair strategy for generated references with structurally-correct layouts but broken small copy.
- Capability/tool gaps discovered while doing this task: missing review surface, missing automation, missing parser, missing generator control, missing validation path.
- Missing assets and generated asset prompts.
- Responsive behavior for each target device class.
- Verification screenshots or design comparison pass.

When useful, create a derived clarification image or mini mock only after labeling it clearly as an interpretation, not as the original reference. Prefer several precise module references over one vague composite mock.

If the user already provided a design and the implementation is still unclear, prefer asking or generating a precise missing module/state reference over guessing. The goal is to make the final UI come from the design set, not from ad hoc implementation imagination.

If several areas are missing, generate them as a small set of targeted references rather than trying to stretch one vague overview image across the whole feature. More precise references usually make implementation faster and more faithful.

Implementation-ready references are preferred over concept images. If a generated image cannot be split into concrete module/state work, it is not detailed enough yet and should be refined before implementation.

If multiple generated references are needed, compare them back to the primary reference before implementation. Inconsistency is a regeneration problem, not an implementation freedom.

When the underlying image API supports multi-turn editing or image-reference editing, prefer deriving the next state from the accepted anchor or nearest accepted parent state rather than generating from scratch. This usually improves sidebar, top-bar, icon, and shell consistency.

The design execution file is mandatory for non-trivial design-led work. If it is missing, create it first; if it is stale, update it before further implementation.

## Final Response Requirements

- Name the design reference or target area used.
- Summarize any design coverage matrix decisions and generated/requested module references.
- Summarize risk tiering decisions and any motion, scroll, asset, performance, form, permission, or i18n contracts that affected implementation.
- Summarize any design-version replacement, focus/accessibility, or async/state ownership contracts that affected implementation.
- Summarize any primitive compatibility, data-slot mapping, or state precedence decisions that materially changed the implementation path.
- Summarize any microcopy/glyph fidelity issue and how it was repaired or deferred to real rendered text.
- Summarize any flow integrity, copy source-of-truth, or change-impact re-entry decision that materially affected completion or later maintenance.
- Summarize the design-to-implementation contract and call out any rows that changed during implementation.
- Summarize what was implemented and which states are dynamic.
- Mention generated or missing assets.
- Mention active/rejected asset organization and whether a design map was created or updated.
- Mention whether hotspot/prototype review was created or updated, and call out missing second-level references.
- Report the verification/comparison performed.
- Mention any durable lesson added to skill memory.
- Mention any newly discovered capability gap, tool gap, or validation gap that should be the next improvement target for the skill.
- For workflow/skill-evaluation work, report the real-task validation loop: rule tested, scenario used, expected behavior, observed behavior, pass/fail, and the next gap.
- State any remaining mismatches or checks that could not be run.
