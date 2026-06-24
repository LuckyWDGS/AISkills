# UI From Design Evolution

## Purpose

Keep this skill useful as projects grow. Treat it as a compact, verified knowledge base for design-reference UI work, not as a chat transcript.

## Start Of A UI Module

1. Read the project `AGENTS.md` and any project-local wrapper skill.
2. Search the codebase for existing components, state models, theme tokens, assets, tests, screenshots, and prior design work before inventing new patterns.
3. Read this file and any project-local learning reference named like `*-learnings.md`, `patterns.md`, or `lessons.md`.
4. Identify knowledge gaps: platform behavior, framework APIs, accessibility, performance, visual asset needs, device constraints, or unclear design intent.
5. Build a design coverage matrix when the design has multiple functional areas or unclear states. Identify which module-level references must be generated or requested before implementation.
6. Create a design-to-implementation contract that maps each design area/state to code target, real data/state, interaction, and verification before coding.
7. Use web search only for gaps that current local context cannot answer reliably. Prefer official docs, standards, source repositories, release notes, or vendor docs.

## During Implementation

- Record candidate lessons as you discover them, but only write durable entries after verification or a clear user decision.
- Keep selected, focused, active, loading, checked, favorite, and progress states data-driven.
- If an asset is missing, first search project assets. Generate only the required missing bitmap/vector/design asset, then save and record it according to project conventions.
- If a design area/state is missing or unclear, generate/request a small module-specific reference before coding that area instead of extrapolating from a broad screen.
- Keep implementation tied to the contract. If code starts drifting away from the design, stop and update either the design reference or the implementation plan before continuing.
- Treat traceability as a gate: do not edit visible UI for a design area until its reference, code target, real data/state, interaction, and verification row are connected.
- Treat unclear design coverage as a blocker, not as permission to half-implement. Ask or generate the missing module/state reference, then resume.
- Treat repeated visual mismatch as a structure problem, not a tuning problem. After one focused alignment pass, if broad areas still differ from the reference, stop small patches and rebuild the affected shell/component primitives from a reference-derived scaffold.
- When an external source changes the approach, keep the source link and access date with the lesson.

## End Of A UI Module

Update skill memory when at least one durable lesson exists:

- Project-specific implementation details go into the project-local skill references or project memory.
- Cross-project design-to-UI lessons go into this global skill reference.
- If a project lesson becomes broadly reusable after more than one use, promote the distilled rule here and leave project-specific details local.

Classify before writing:

- Global: reusable design-process, state-fidelity, accessibility, responsive, asset, or verification rule that applies beyond one project.
- Project-local: names a project, component, screen, asset, route, file path, brand style, user preference, exact label, or platform setup unique to the current codebase.
- Promote only the abstract rule. Leave concrete examples, screenshots, generated asset paths, and project decisions in the project-local wrapper.
- Do not put project-only lessons in global references for convenience.

## Entry Template

```markdown
### YYYY-MM-DD - Short Lesson Name

- Scope: global or project-specific.
- Context: feature, screen, platform, design reference, or bug shape.
- Problem: what failed, was unclear, or was repeatedly expensive.
- Pattern: the reusable approach to prefer next time.
- Verification: build/test/screenshot/device/user confirmation used.
- Sources: links and access date when web research informed the lesson.
- Avoid: when this pattern should not be used.
```

## Search Guidance

- Codebase first: `rg`, `rg --files`, existing components, tests, design assets, screenshots, and memory files.
- Web only when needed: current APIs, library behavior, platform guidelines, browser/device quirks, accessibility requirements, asset-format constraints, or design-system docs.
- Prefer primary sources over blogs for technical behavior.
- Summarize sources in your own words; do not paste long external content.
- Record the practical implication, not just the link.

## Seeded Design Lessons

### 2026-05-12 - Semantic Copy Drift Needs A Dedicated Runtime Audit

- Scope: global.
- Context: design-led UI where accepted refreshed references change small but meaningful copy such as top-bar search placeholders, module tabs, button labels, or state titles.
- Problem: screenshots and broad visual diffs can miss or under-prioritize semantic copy drift, especially when the layout still looks correct and the old copy is visually similar.
- Pattern: when accepted designs replace module semantics, add a small runtime semantic audit that clicks or navigates through the affected surfaces and checks title, search placeholder, primary action, selected tab, or other source-of-truth copy against the design contract.
- Verification: in TestUI, a top-bar semantic audit failed before the fix because Initiatives, Calendar, and Settings still rendered `Search tasks...`; after updating runtime state mapping, the same audit passed for all checked modules.
- Avoid: relying only on visual comparison or source grep when a rendered state can differ by route, tab, or drawer.

### 2026-05-12 - Local Browser Audits Must Prove They Loaded The Target App

- Scope: global.
- Context: Playwright/browser checks against local dev servers where several projects may use common ports such as `5173`.
- Problem: an audit can silently test the wrong app if a default localhost port is already occupied by another project. The failure then says more about the environment than the UI under test.
- Pattern: pass an explicit target URL/port into local audits and verify an app-specific identity selector, title, or marker before interacting. Treat wrong-app detection as a verification/tool gap, not a product failure.
- Verification: in TestUI, the first semantic audit hit another app on `127.0.0.1:5173`; rerunning with `TESTUI_URL=http://127.0.0.1:5174/` and an `.app-shell` identity check produced the real pre-fix failure and post-fix pass.
- Avoid: assuming a common dev-server port belongs to the current project.

### 2026-05-12 - Workflow Rules Need Real-Task Validation

- Scope: global.
- Context: reusable design-to-code skills that keep gaining new guardrails after implementation drift, missing design states, weak review tools, or noisy visual checks.
- Problem: a rule can sound correct in the skill file but still fail to change agent behavior unless it is tested against a real project surface or realistic harness task.
- Pattern: when adding or changing a guardrail, run a real-task validation loop. Record the rule tested, scenario, expected enforcement, observed result, pass/fail, and next gap. If the current task cannot exercise the rule, mark it unproven and name the next realistic scenario.
- Verification: future handoffs and design execution files should show which task proved the rule or which scenario remains needed before trusting it.
- Avoid: treating documentation edits or checklist additions as proof that the workflow now works.

### 2026-05-12 - A Usable Skill Must Keep A Capability Gap Backlog

- Scope: global.
- Context: long-running workflow improvement where each task exposes a slightly different weak spot in process, tooling, or verification.
- Problem: teams can keep noticing pain points without ever turning them into concrete next improvements, so the skill sounds strict but stays awkward in real use.
- Pattern: at the end of non-trivial design-led work, record concrete capability gaps, tool gaps, or verification gaps, plus the smallest next fix. Treat that backlog as part of the skill's evolution, not as optional commentary.
- Verification: future sessions should be able to read the backlog and pick one actionable improvement without reconstructing the whole conversation.
- Avoid: writing vague “could be better” notes without naming the missing capability or next increment.

### 2026-05-12 - Screen Fidelity Is Not Flow Integrity

- Scope: global.
- Context: design-led work where individual screens look correct but the user still has to enter, return, cancel, retry, or undo through them.
- Problem: a design set can close page-by-page while navigation and recovery paths remain inconsistent or undefined. That creates UI that looks finished in screenshots but feels broken in use.
- Pattern: run a flow integrity audit for important paths. Record entry, destination, back/return, cancel/close, retry, and undo/remove behavior as part of design coverage instead of assuming page correctness implies path correctness.
- Verification: manually or automatically traverse the flow and confirm that each branch lands in the intended state.
- Avoid: approving a feature family because each page looks correct in isolation.

### 2026-05-12 - Copy Needs One Source Of Truth

- Scope: global.
- Context: design-led work where copy appears in design images, product docs, i18n files, API data, and implementation.
- Problem: titles, labels, empty states, errors, and confirmations can drift because different people treat different sources as authoritative.
- Pattern: create a copy source-of-truth contract for high-visibility copy. Record whether the final text comes from product copy, an i18n resource, an API field, local configuration, or an explicit design-owned override.
- Verification: compare the implemented visible copy against the recorded source rather than only against the design image.
- Avoid: allowing design copy, product copy, and implementation copy to evolve independently.

### 2026-05-12 - Good Design-Led Modules Must Re-Enter On Change

- Scope: global.
- Context: a design-led module already passed review, then later receives a small or medium change request.
- Problem: teams often bypass the original contract on later edits, which slowly reintroduces drift even though the first implementation was strict.
- Pattern: add a change-impact re-entry rule. Later changes that touch layout, states, copy, slots, primitives, interactions, or references must reopen the affected contract rows and rerun the relevant gates before being called complete.
- Verification: the change should leave an updated contract trail rather than only a code diff.
- Avoid: treating a previously approved module as permanently exempt from design review discipline.

### 2026-05-12 - Dense CJK Microtext Needs Its Own Fidelity Gate

- Scope: global.
- Context: generated UI references that are structurally correct but contain small Chinese, Japanese, or Korean labels, tabs, field names, badges, or helper text.
- Problem: image generation can preserve overall layout while distorting small glyphs, writing the wrong words, or producing unreadable microtext. These failures are easy to miss in broad layout review and can make an otherwise good reference unsafe for implementation.
- Pattern: treat dense microtext as its own acceptance surface. Review it separately from layout fidelity, and if it fails, choose the narrowest repair path: regenerate the local region/state, post-edit the text area, or explicitly mark the final implementation to use real rendered text instead of trusting the generated glyphs.
- Verification: zoom review or crop review should confirm the words are readable and semantically correct; if not, the reference stays blocked for that area.
- Avoid: approving a reference because the page shell is good while small labels are wrong, or regenerating an entire strong anchor just to repair two tiny text zones.

### 2026-05-12 - State Precedence Must Be Designed, Not Emergent

- Scope: global.
- Context: design-led UI where loading, error, stale cache, filter-empty, permission, retry, submit, or partial-data states can overlap.
- Problem: static designs usually show one state at a time, but runtime can hit several at once. If precedence is not explicit, the UI ends up following whichever conditional was written first instead of a product decision.
- Pattern: add a state precedence matrix for any surface with overlapping visible states. Record winner states, decorator/coexisting states, and full-replacement states before implementation.
- Verification: simulate overlapping states and confirm the visible result follows the matrix rather than ad hoc code order.
- Avoid: treating `loading`, `error`, `empty`, `permission`, `retrying`, and `stale` as independent checks with no explicit priority.

### 2026-05-12 - Every Design Slot Needs A Real Data Owner

- Scope: global.
- Context: reference-driven UI with badges, subtitles, owners, timestamps, counts, avatars, source labels, or metadata strips.
- Problem: a design can contain many informative slots that look harmless, but runtime data may not stably provide them. Teams then fill the gap with fake text, brittle derivations, or silent omissions that break consistency.
- Pattern: run a data-slot audit before implementation. Map every visible slot to a real field, derived field, or deliberate fallback behavior, including null/missing behavior and overflow rules.
- Verification: test with real payloads that include missing, null, short, and long values to confirm each slot behaves as planned.
- Avoid: copying placeholder or illustrative design content into runtime UI because the slot exists visually.

### 2026-05-12 - Shared Primitive Reuse Needs Compatibility Checks

- Scope: global.
- Context: teams trying to implement a new design by reusing existing shared buttons, inputs, cards, lists, dialogs, or tabs.
- Problem: “reuse the component” sounds efficient, but a primitive that differs in spacing, radii, typography, icon alignment, state layers, or interaction model will create endless local overrides and still not match the reference.
- Pattern: run a primitive compatibility gate before implementation. Decide explicitly whether to inherit, wrap, fork, or rebuild each relevant primitive based on the design's real requirements.
- Verification: confirm the chosen primitive path reduces per-screen overrides and still supports the required states and geometry.
- Avoid: repeated one-off overrides on top of a fundamentally incompatible shared primitive.

### 2026-05-12 - Accepted Design Replacements Need Version Lock

- Scope: global.
- Context: design-led work with anchor screens, derived states, hotspot reviews, screenshot baselines, and iterative regenerated references.
- Problem: a new accepted image can silently replace an old one while contracts, maps, hotspot reviews, or approved baselines still point at the previous version. The implementation then looks traceable on paper but is actually split across two design generations.
- Pattern: give accepted references stable ids or versions. When a new image replaces an old one for the same scope, record the supersede relationship and replacement scope, then sync every downstream artifact that still points at the old version before coding continues.
- Verification: the active contract rows, design map, hotspot/prototype review, and approved baselines should all reference the accepted version for that scope; old versions stay only as rejected/superseded audit artifacts.
- Avoid: mixing old and new references for the same module/state in one implementation pass or assuming filename changes alone are enough to communicate replacement.

### 2026-05-12 - Static Designs Need Focus And Accessibility Contracts

- Scope: global.
- Context: UI work where the static design shows a visual state but not how keyboard, remote, focus, or assistive technology should move through it.
- Problem: click flows can look correct while tab order, visible focus, escape/back behavior, semantics, labels, and announcements are broken or undefined. Static references almost never prove these paths.
- Pattern: for any surface where focus, keyboard, remote, or assistive technology matters, write a focus/accessibility contract before implementation. Cover entry point, order, visible focus treatment, hover-to-focus parity where relevant, actions, trap/release, semantic roles, labels, and critical announcements.
- Verification: run the real focus path and accessible-name/role checks for the implemented surface rather than relying on a screenshot.
- Avoid: assuming accessibility is “already handled” because the layout looks simple or because the mouse path works.

### 2026-05-12 - Async Ownership Prevents Honest UI From Lying

- Scope: global.
- Context: design-led UI with search, filters, retries, saves, source switching, tabs, drawers, or any flow driven by concurrent async work.
- Problem: the visible state can drift away from the intended design/state contract when stale responses overwrite newer user intent, optimistic updates never reconcile, or loading/error panels belong to the wrong request.
- Pattern: write an async/state-ownership contract for dynamic surfaces. Record source of truth, who owns the visible pending state, cancellation or ignore policy for stale responses, optimistic vs confirmed update policy, and retry/reconciliation behavior. Make the UI follow that policy instead of the last promise that happens to resolve.
- Verification: test slow, failed, repeated, and out-of-order responses and confirm the visible state still matches the current user intent and contract row.
- Avoid: letting “latest resolved response wins” emerge accidentally from implementation details.

### 2026-05-12 - Static References Need Behavior And Edge-State Contracts

- Scope: global.
- Context: design-led UI work that starts from static screenshots or generated mockups but includes drawers, menus, tabs, scrolling areas, forms, permissions, localization, or asset-heavy visuals.
- Problem: a static image can show the final look while hiding how the UI moves, scrolls, validates, degrades, localizes, and loads assets. Implementation then guesses those details, which creates drift even when the screenshot looks broadly correct.
- Pattern: before visible implementation, add explicit contracts for motion, scroll/sticky behavior, asset/font/icon requirements, feasibility/performance constraints, form states, role/permission variants, and i18n pressure whenever those details affect the user-visible result.
- Verification: the design execution artifact should show the relevant contract rows and the final check should verify the actual transition, scroll state, asset substitution, form/permission case, or localization pressure case rather than only a still screenshot.
- Avoid: treating missing motion, scroll, form, permission, asset, or localization detail as harmless implementation freedom.

### 2026-05-12 - Risk Tiering Keeps Design Gates Practical

- Scope: global.
- Context: strict design-to-code workflows where too many required checks can slow down small, low-risk changes.
- Problem: if every minor inline control requires the full design-generation and review pipeline, the workflow becomes expensive and teams start bypassing it. If the workflow is too loose, high-risk surfaces drift.
- Pattern: classify each surface as high, medium, or low risk before applying gates. High-risk surfaces get full coverage. Medium-risk surfaces get relevant gates plus written skip reasons. Low-risk inline behavior can proceed with a short reason and a clear upgrade trigger when it reveals a new surface, state, role, motion, or performance concern.
- Verification: the design execution artifact should record risk tier, skipped-gate reasons, and upgrade triggers; later source-click and visual review should promote any underestimated row instead of leaving it hidden.
- Avoid: using risk tiering to skip gates on brand-critical, permission-sensitive, form-heavy, responsive, or novel navigation surfaces.

### 2026-05-12 - Stop Micro-Patching Structural UI Drift

- Scope: global.
- Context: design-led implementation where the rendered UI is repeatedly adjusted with small CSS/layout tweaks but still does not match the reference.
- Problem: when the underlying shell, grid, spacing scale, typography scale, component primitives, or icon language is wrong, small fixes create an endless patch loop. Each local tweak may improve one element while making neighboring areas drift, so the implementation never truly converges on the design.
- Pattern: classify mismatches before fixing. Use `local` for one bounded mismatch that can be patched. Use `systemic` for repeated drift across regions, density, components, or visual language. After one failed systemic alignment pass, stop tweaking and run a fidelity reset: extract the reference's layout scaffold and design tokens, rebuild the affected surface or shared primitives from that scaffold, then reconnect data and interactions.
- Verification: capture a screenshot after the reset and compare broad regions plus critical hotspots against the reference; the reset should reduce whole-family drift, not merely move one mismatched button.
- Avoid: continuing margin/color/font-size patch loops when the first screenshot already proves the implementation model is structurally different from the design.

### 2026-05-12 - Run Design-Led UI Risk Gates In Order

- Scope: global.
- Context: design-led UI projects with generated or supplied references, real interactions, responsive targets, dynamic data, and visual verification.
- Problem: many failures look like visual mismatch at the end, but the root cause happens earlier: unstable reference families, effect images without extracted structure, hard-coded visual states, inline controls misclassified as no-new-UI, missing responsive references, fake or weak data tests, noisy visual diff gates, component-system conflicts, extra live interactions, or review tools that become unreadable.
- Pattern: run a fixed risk ladder before and during implementation. First prove the design family is stable. Then extract a buildable structure. Bind every visual state to app state. Require every `inline` row to carry a reason and an upgrade trigger. Treat each materially different breakpoint as its own design coverage question. Pressure-test with real data and resilience states. Use region/hotspot/approved-baseline visual checks instead of trusting full-page diff alone. Decide whether the reference or existing component system wins. Reconcile source-level handlers after implementation. Keep user review progressive while leaving dense debug maps for agents.
- Verification: the design execution artifact should show the risk-gate result, inline reasons, responsive scope, data-pressure cases, visual-diff policy, component-system decision, and source-click audit result before the UI is called complete.
- Avoid: treating the 10 risks as optional polish items after coding. They are ordered gates; an early failure blocks later implementation.

### 2026-04-28 - Generate Module References For Complex Designs

- Scope: global.
- Context: large product designs with several feature areas, states, dialogs, or device variants.
- Problem: one or two broad mockups rarely specify every function area well enough to implement the whole feature set accurately.
- Pattern: create a design coverage matrix, split the target into small functional modules/states, and generate or request precise references for missing areas before coding them.
- Verification: compare each implemented module/state against its own reference, not only against the broad overview image.
- Avoid: completing a whole feature suite from a vague design mood or a single approximate screen.

### 2026-04-30 - Design Requires Implementation Traceability

- Scope: global.
- Context: UI work where designs are generated or supplied before implementation.
- Problem: design artifacts can become disconnected from code, causing the design and implementation to proceed independently.
- Pattern: after generating or receiving a design, create a design-to-implementation contract mapping each design area/state to code target, real data/state, interaction, and verification. Treat that table as a pre-coding gate, then implement and verify by contract row.
- Verification: final review should show which contract rows were implemented, changed, or deferred.
- Avoid: generating a design image and then coding from memory, mood, or unrelated existing layout.

### 2026-04-30 - Design Is The UI Source, Not A Suggestion

- Scope: global.
- Context: UI implementation based on user-provided or generated design references.
- Problem: the design may exist, but implementation still improvises uncovered or unclear areas without stopping to resolve them.
- Pattern: treat the design as the implementation source for covered modules/states. When a required area is unclear, ask a concise question or generate/request a focused module/state reference before coding that area.
- Verification: uncovered or blocked rows should remain explicit in the contract instead of being silently approximated.
- Avoid: partial implementation that fills gaps from taste, habit, or unrelated existing screens while still claiming to follow the design.

### 2026-05-06 - Example Content Is Not Runtime Content

- Scope: global.
- Context: design references that show occupied lists, example tasks, placeholder cards, or multiple states at once to explain layout possibilities.
- Problem: implementation can copy the visual examples literally, leaving fake or lingering UI content on screen even when the real runtime state is empty.
- Pattern: treat sample cards, placeholder rows, and mixed-state examples as explanatory unless the user explicitly wants seeded runtime content. When real data for that state is empty, render the honest empty state, blank section, or hidden section defined by the product.
- Verification: test the empty runtime state separately from the populated state and confirm the illustrative mock content disappears.
- Avoid: preserving design-time example cards or state snippets when there are no real items to show.

### 2026-05-06 - Missing Design Coverage Should Trigger More Small References

- Scope: global.
- Context: broad UI references that leave several modules, states, or overlays unspecified.
- Problem: implementation quality drops when one overview image is stretched to cover too many uncovered details.
- Pattern: when design coverage is missing, proactively generate a set of small module/state references unless the gap is a genuine product decision that needs user input. Favor precision over breadth.
- Verification: each generated reference should map to a contract row and remove one specific ambiguity from implementation.
- Avoid: waiting passively for the user to notice missing design coverage or relying on one oversized composite mockup to solve many different UI questions.

### 2026-05-06 - Generated Design Should Be Buildable

- Scope: global.
- Context: generated references used to fill missing UI design coverage.
- Problem: a generated image can look attractive but still be too conceptual to implement faithfully.
- Pattern: generate references that are specific enough to split directly into module/state implementation tasks, with clear structure, controls, text zones, state differences, and empty/occupied behavior.
- Verification: if the image cannot be translated into concrete contract rows without extra invention, refine it before coding.
- Avoid: mood boards or high-level concept art standing in for implementation-ready design references.

### 2026-05-06 - Derived References Must Stay Anchored

- Scope: global.
- Context: one primary design reference plus several generated state/module follow-up images.
- Problem: follow-up generated references can drift in shell, spacing, or component language, which makes implementation ambiguous again.
- Pattern: pick one primary reference as the visual anchor, then generate derived references against that anchor. If a derived reference drifts, regenerate it instead of averaging styles in code.
- Verification: compare each derived reference against the anchor before implementation and confirm consistent shell, palette, spacing logic, and component language.
- Avoid: implementing from a mixed set of inconsistent generated references.

### 2026-05-06 - Reference Packs Beat Prompt-Only Follow-Ups

- Scope: global.
- Context: generating several related UI states from one primary screen.
- Problem: follow-up images drift when they are generated from text alone or from a weak set of references.
- Pattern: when the tool supports reference images, build a reference pack in priority order: primary anchor, direct parent state, closest accepted sibling, shared shell crop, changing-module crop, icon/control crop.
- Verification: if sidebar, top bar, icon style, or shell language drift between states, the reference pack was insufficient or mis-prioritized and should be rebuilt before implementation.
- Avoid: spending scarce reference slots on redundant full-page images while omitting the true anchor or parent state.

### 2026-05-07 - Derived State Review Must Include Micro Layout

- Scope: global.
- Context: generated follow-up UI states such as empty, loading, error, drawer, or selected states derived from an accepted anchor screen.
- Problem: a derived image can look correct at the broad layout level while still drifting in canvas size, sidebar details, header spacing, profile block, icon language, column geometry, or non-target data values.
- Pattern: before accepting a derived reference, run a structural consistency review against the anchor. Check exact image dimensions/aspect first, then compare shell, navigation vocabulary, header controls, metrics, gutters, column/card geometry, icon family, profile/user block, and whether only the target module/state changed. Any unrelated visible drift means regenerate before implementation.
- Verification: use at least one objective check such as image dimensions plus a visual row-by-row review recorded in the design execution file.
- Avoid: marking a generated state as passed because it has the same general page composition or because only the central feature area appears plausible.

### 2026-05-08 - Visual Review Must Check State Semantics, Not Just Shell

- Scope: global.
- Context: generated UI references and implemented screens that must stay faithful to an accepted design anchor.
- Problem: a screen can preserve the general shell yet still drift in counts, empty-vs-populated behavior, selected tabs, icon family, action placement, or whether a visible state reflects real runtime data. That kind of drift is easy to miss if review stays at the "looks similar" level.
- Pattern: review in two passes. First verify the anchor-level shell and micro-layout. Then verify state semantics: counts, selected/open/empty/loading/error states, action affordances, and whether content is honest runtime data or only illustrative mock content. Regenerate or fix code if any non-target state changes were invented.
- Verification: compare screenshots or rendered UI against the anchor and confirm visible counts, state toggles, and interaction outcomes match the intended runtime state, not just the overall page composition.
- Avoid: approving a design or implementation because the palette and page skeleton match while the actual state behavior has drifted.

### 2026-05-08 - Audit Every Clickable Point Before Coding

- Scope: global.
- Context: design-led UI work with buttons, tabs, cards, menus, drawers, confirmations, and deep destination screens.
- Problem: broad screenshots often hide missing destination pages, missing micro-states, or controls that look covered but have no concrete target. Implementation then drifts by filling gaps from taste or by leaving invisible dead clicks.
- Pattern: build a clickable-point inventory before coding. For each visible control, classify it as `covered`, `inline`, or `missing`. If missing, generate or request the smallest useful module/state reference before implementing that area. Then implement row-by-row against the design contract and finish with screenshot review focused on micro-layout, icon language, copy, state transitions, and empty/loading/error behavior.
- Verification: the design execution file should show the clickable inventory and contract row mapping, and the final validation should prove that every visible control is either covered by a reference, intentionally inline, or explicitly deferred.
- Avoid: treating a whole page as done because the main frame matches while smaller controls, secondary states, or follow-up screens still have no design coverage.

### 2026-05-08 - Source-Level Click Audit Closes Implementation Drift

- Scope: global.
- Context: design-led UI work where code already exists or new controls are added during implementation.
- Problem: hotspot review over design images can be closed while the implementation still contains extra `@click`, `onClick`, route-link, submit, row-click, or shortcut behavior that the design contract never classified.
- Pattern: after or during implementation, extract the actual interactive handlers from source code and reconcile them against the design execution file. Every live handler should be `covered`, `inline`, or `missing`; missing rows require a focused design reference or explicit deferral before claiming completion.
- Verification: record the source-level click count and the classification result in the project design execution artifact; rerun after adding controls.
- Avoid: relying only on visual hotspot maps when implementation can introduce additional live interactions.

### 2026-05-08 - Evaluation Harnesses Are For Skill Reliability

- Scope: global.
- Context: projects created specifically to test whether design-driven skills make AI follow design references and improve future development.
- Problem: the agent can slip into normal product-delivery mode, adding functionality for its own sake instead of using implementation to expose and repair workflow failures.
- Pattern: when the project is a skill/workflow evaluation harness, treat each design, code edit, screenshot, and mismatch as evidence about the skill. Record whether the guardrail passed, failed, or needs revision. Patch the reusable skill when the failure is general, and keep only project-specific facts in project memory.
- Verification: project memory should state the evaluation goal, and final reports should name the skill behavior tested, not only the app behavior implemented.
- Avoid: measuring success by how feature-rich the demo app became rather than whether future AI sessions will be forced to bind design and implementation.

### 2026-05-08 - Visual Diff Needs Regions, Not Just A Full Page Score

- Scope: global.
- Context: design-led UI verification using screenshots or generated design references.
- Problem: full-canvas design-vs-implementation pixel percentages can be noisy because browser DOM rendering differs from bitmap design images in fonts, antialiasing, shadows, icons, and text wrapping. At the same time, a small control drift can be invisible in a full-page percentage.
- Pattern: keep the canonical viewport fixed, then compare named critical regions or hotspots such as sidebar, top bar, metrics, primary action, drawer, modal, card grid, and empty/error panel. Use full-page diff as a review signal, not as the only pass/fail gate. When testing the guardrail itself, include a tiny synthetic drift probe to prove the region-level thresholds can catch small movement.
- Verification: in the TestUI harness, a full design-vs-live comparison produced a broad review signal while a synthetic 6px primary-action drift triggered the button-region threshold even though its full-canvas ratio was tiny.
- Avoid: claiming pixel-perfect fidelity from a single global diff number, or ignoring a region-level warning because the full-page percentage looks small.

### 2026-05-08 - Hotspot Maps Can Seed Visual Diff Regions

- Scope: global.
- Context: design-led projects that already have a hotspot/prototype review map with clickable coordinates.
- Problem: visual diff tools are weaker when every project hand-writes comparison regions from scratch, but direct design-vs-DOM comparisons on small text-heavy hotspots can generate many review warnings from harmless font and antialiasing differences.
- Pattern: reuse hotspot/prototype coordinates as control-level visual diff regions, especially for buttons, links, menus, and cards. Keep broad structural regions for shell/layout review. Treat hotspot design-vs-DOM diffs as focused inspection prompts, and use screenshot-to-screenshot or synthetic drift probes when the goal is to prove regression sensitivity.
- Verification: in the TestUI harness, `design-review.json` produced 15 hotspot-derived home regions; the New Task hotspot caught a synthetic 6px drift with changed ratio `0.17785`, while many design-vs-live text hotspots also warned and therefore needed human review rather than automatic failure.
- Avoid: applying one threshold to all hotspots, or failing a design implementation solely because every small text hotspot differs from a generated bitmap reference.

### 2026-05-08 - Calibrate Visual Diff With A No-Change Baseline

- Scope: global.
- Context: screenshot or pixel guardrails used after design-led implementation.
- Problem: direct design-vs-DOM comparisons can warn on harmless rendering differences, while a later screenshot regression may need a much stricter threshold to catch true drift.
- Pattern: capture two no-change screenshots at the same viewport and compare them first. Treat this screenshot-to-screenshot result as the runtime noise floor for each region/hotspot. Then compare later screenshots or synthetic probes against that calibrated baseline. A warning is much stronger when it exceeds the no-change baseline by a clear margin.
- Verification: in the TestUI harness, the no-change full-canvas baseline and all hotspot baselines were `0`, while the synthetic New Task 6px drift was `0.17785` in its hotspot. This proved the live page was stable and the design-vs-DOM hotspot warnings came from bitmap/DOM rendering differences, not runtime screenshot noise.
- Avoid: tuning visual-diff thresholds from design-vs-DOM noise alone or assuming a noisy design comparison means the live UI is unstable.

### 2026-05-08 - Prove Guardrails With Real Reversible Drift

- Scope: global.
- Context: skill-evaluation harnesses and high-risk design-led UI workflows where a visual guardrail must be trusted before future work relies on it.
- Problem: synthetic image mutations prove the comparison math, but they do not prove that the guardrail catches actual code or CSS changes in the running app.
- Pattern: after establishing a clean approved screenshot baseline, introduce one tiny reversible code/style drift such as a 4-6px button translation. Run the calibrated visual guardrail and confirm the intended region fails. Save the failure artifact, then immediately remove the drift and rerun the guardrail to confirm the approved baseline is clean again.
- Verification: in TestUI, a temporary `translateX(6px)` on the primary action produced approved-vs-live full-canvas ratio `0.00094`, but the `New Task` hotspot ratio was `0.14214` and failed the calibrated `0.03` threshold. After removing the CSS line, approved-vs-live returned to `0`.
- Avoid: leaving artificial drift in product code, or trusting a visual guardrail that has only been tested on generated/synthetic images.

### 2026-05-08 - CI Should Block On Approved Drift, Not Design Noise

- Scope: global.
- Context: teams turning screenshot-based visual checks into CI-style pass/fail gates.
- Problem: direct design-vs-DOM diffs can remain noisy even when the implementation is stable and approved, so a naive gate either fails too often or gets ignored.
- Pattern: split the visual output into two channels. Blocking findings come only from unstable no-change baseline captures and calibrated approved-baseline drift. Design-vs-DOM findings remain visible as review signals but do not fail CI by themselves.
- Verification: in TestUI, `npm run visual:guardrail:ci` passed while many design-vs-DOM review rows remained, failed only when a real CSS drift moved `home: New Task`, and passed again immediately after the CSS was restored.
- Avoid: making design-vs-reference review noise a hard gate for every run, or hiding that noise entirely.

### 2026-05-08 - Visual Gates Need A Machine-Readable Contract

- Scope: global.
- Context: CI-facing or reusable visual guardrails for design-led UI work.
- Problem: a visual report can explain drift to a human but still leave automation unclear about which region should block, which should only prompt review, and why a threshold exists.
- Pattern: store the gate policy in a small machine-readable contract: canonical viewport, comparison channels, region ids, severity (`block` or `review`), threshold overrides, and rationale. The guardrail should emit a compact gate summary with blocking findings and non-blocking review signals separated.
- Verification: in the TestUI harness, `visual-guardrail.contract.json` promoted the `home: New Task` approved-baseline region to `block`; a temporary `translateX(6px)` drift failed CI with exactly that blocking finding, while design-vs-DOM rows remained review-only. After restoring CSS, the same gate passed.
- Avoid: encoding region severity only in prose, console text, or one-off script branches that cannot be reused across projects.

### 2026-05-08 - Approved Baseline Updates Need A Clean Rerun

- Scope: global.
- Context: screenshot-based visual regression checks that use an approved runtime baseline and an explicit update flag such as `TESTUI_UPDATE_APPROVED_BASELINE=1`.
- Problem: a baseline update can appear to succeed simply because the same run rewrote the baseline, without proving that the next ordinary CI run will stay clean.
- Pattern: validate approved baseline updates in two passes. First run with the update flag after an intentional accepted UI change. Then run the same gate again without the flag and require a clean pass. In harnesses, keep before/after artifacts and restore the canonical baseline if the accepted change was only experimental.
- Verification: in TestUI, increasing the primary action button width to `166px` made CI fail on both `home: New Task` and the adjacent `home: Search input`; updating the approved baseline made CI pass, and a second clean rerun without the update flag also passed.
- Avoid: treating the baseline write step itself as proof that the updated baseline is trustworthy.

### 2026-05-09 - Overlay-State Reviews Must Discount Intentional Scrims

- Scope: global.
- Context: auditing drawer, dialog, popover, or detail-overlay references against their parent design screens.
- Problem: a correct overlay often dims the entire parent page, so a full-shell diff can falsely look like severe sidebar/topbar/metrics drift even when the shell geometry is unchanged.
- Pattern: review overlay states in parent-child pairs, but mask or mentally discount the intentional scrim. Judge the unchanged shell by geometry, alignment, unaffected controls, and whether the new UI only adds the target overlay instead of redesigning the background page.
- Verification: in the TestUI audit, `new-initiative-drawer` and centered confirmation dialogs showed extreme whole-shell diff ratios against their parents until the review accounted for the intentional dimmed backdrop; visually, the shell and parent content remained aligned.
- Avoid: regenerating a correct overlay state only because the full-page comparison counted the scrim as drift.

### 2026-05-11 - Prototype Review Must Be Progressive And Readable

- Scope: global.
- Context: design sets with many generated screens, drawers, menus, dialogs, and clickable hotspots.
- Problem: a dense overlay with boxes on every clickable region becomes slow, visually noisy, and hard for users to operate. It can also falsely imply the flow is closed when a first-level target image exists but the target's own controls have not been reviewed.
- Pattern: keep the dense rectangle overlay as an agent/debug artifact, but make the default user-facing review a progressive flow. Start at the anchor/home screen, show only the current screen's clickable points as colored `*` markers, hide repeated shell navigation behind a toggle, require the current screen/level to be marked reviewed before entering the next level, and classify every marker as open-design, inline/no-new-UI, missing/invalid, or target-exists-but-child-review-pending.
- Verification: in the TestUI harness, replacing the rectangle-heavy review page with a marker-only progressive review made `file://` loading work, showed 14 homepage markers, blocked navigation before Home was marked reviewed, then allowed the same marker to open `My Work` after Home passed.
- Avoid: using one all-at-once hotspot page as proof that a multi-level interaction tree is closed, or covering the design image with many permanent boxes when a simple marker and side-panel detail would be clearer.

### 2026-05-07 - Confirm Platform Before UI Generation

- Scope: global.
- Context: generating design references for apps, websites, dashboards, phone views, tablets, TV, or responsive products.
- Problem: if the platform and breakpoint are not chosen first, generated screens can use mismatched dimensions and density, making later states hard to align and responsive behavior ambiguous.
- Pattern: before generating UI references, confirm or infer the target platform and breakpoint, then record the canvas. Use common defaults only when the product target is unknown: desktop full-screen web `1920x1080`, laptop/common web `1440x900` or `1366x768`, mobile web/H5 `390x844`/`393x852`/`430x932`, tablet `1366x1024` or `1024x1366`, TV/large screen `1920x1080`. If a tool requires dimensions divisible by 16, use the nearest recorded equivalent.
- Verification: the design execution file should show the platform/canvas decision before the first generated image, and every derived state should match the anchor dimensions unless it is an explicit separate breakpoint.
- Avoid: generating a desktop design and treating it as sufficient for mobile/tablet/TV, or mixing canvas sizes inside one screen family.

### 2026-05-07 - Image Tool Fallback Still Requires Structural Review

- Scope: global.
- Context: preferred image tool temporarily fails, times out, or returns upstream errors while generating implementation-ready UI references.
- Problem: switching tools can solve availability but may reintroduce visual drift, size drift, or looser reference adherence.
- Pattern: follow the user's current tool priority, retry transient preferred-tool failures within the tool's retry policy, and only use the secondary tool when allowed. Every fallback-generated image must still pass the same structural consistency review before it becomes an active reference.
- Verification: record which tool failed, why fallback was used, the output dimensions, and the structural review result in the design execution file or asset index.
- Avoid: accepting a fallback image because it exists or looks plausible without checking it against the anchor.

### 2026-05-07 - Map Growing Design Asset Sets

- Scope: global.
- Context: design-led work accumulates several active references, failed attempts, thread-only anchors, and generated state images.
- Problem: a linear asset index becomes hard to scan, and implementation can accidentally use a failed or superseded image.
- Pattern: when a design set grows beyond a few images or includes failed/superseded variants, create a small relationship map. At minimum, distinguish active implementation references, failed/do-not-use references, thread-only anchors, parent-child derivations, and superseded-by links. An HTML map with hover previews and click-through image links is useful when the user needs to inspect the set visually; a JSON map helps regenerate or audit the graph.
- Verification: check that every active node links to an existing local asset and that failed nodes are visually labeled as do-not-use.
- Avoid: relying only on filenames or a long markdown list to communicate which design image drives which UI state.

### 2026-05-07 - Operate The Design Map To Find Missing States

- Scope: global.
- Context: implementation-ready design sets for interactive products where controls can open drawers, menus, details, search results, retries, filters, or navigation screens.
- Problem: static screenshots can look complete while clicks lead to unrepresented UI states, causing implementation to invent missing behavior.
- Pattern: treat the design map as an interaction audit surface. Record visible controls and expected click targets, then operate the map: hover/preview references, click covered targets, and mark controls with no target reference as missing design coverage. Only implement a click if it maps to an accepted reference or a documented inline/no-op behavior.
- Verification: design execution should include an interaction coverage table; the visual map should show covered, partial, and missing click targets.
- Avoid: assuming a visible button is harmless or implementing its destination from intuition when no design state exists.

### 2026-05-07 - Separate Active And Rejected Design Assets

- Scope: global.
- Context: a project has accepted implementation references plus failed, superseded, or rejected generated images.
- Problem: keeping active and failed images in one folder makes it easy to select the wrong reference during implementation or visual comparison.
- Pattern: split design assets by lifecycle when the set contains both active and rejected references. Use clear folders such as `assets/active/` for implementation sources and `assets/rejected/` for do-not-use audit artifacts, then update the asset index, design map, and execution contract paths.
- Verification: run a link/path check after moving files and confirm active references resolve only to the active folder.
- Avoid: relying on filename suffixes such as `failed` or `v1` alone to prevent accidental use.

### 2026-05-07 - Separate Active And Rejected Design Assets

- Scope: global.
- Context: a project has accepted implementation references plus failed, superseded, or rejected generated images.
- Problem: keeping active and failed images in one folder makes it easy to select the wrong reference during implementation or visual comparison.
- Pattern: split design assets by lifecycle when the set contains both active and rejected references. Use clear folders such as `assets/active/` for implementation sources and `assets/rejected/` for do-not-use audit artifacts, then update the asset index, design map, and execution contract paths.
- Verification: run a link/path check after moving files and confirm active references resolve only to the active folder.
- Avoid: relying on filename suffixes such as `failed` or `v1` alone to prevent accidental use.

### 2026-05-07 - Operate The Design Map To Find Missing States

- Scope: global.
- Context: implementation-ready design sets for interactive products where controls can open drawers, menus, details, search results, retries, filters, or navigation screens.
- Problem: static screenshots can look complete while clicks lead to unrepresented UI states, causing implementation to invent missing behavior.
- Pattern: treat the design map as an interaction audit surface. Record visible controls and expected click targets, then operate the map: hover/preview references, click covered targets, and mark controls with no target reference as missing design coverage. Only implement a click if it maps to an accepted reference or a documented inline/no-op behavior.
- Verification: design execution should include an interaction coverage table; the visual map should show covered, partial, and missing click targets.
- Avoid: assuming a visible button is harmless or implementing its destination from intuition when no design state exists.

### 2026-05-07 - Map Growing Design Asset Sets

- Scope: global.
- Context: design-led work accumulates several active references, failed attempts, thread-only anchors, and generated state images.
- Problem: a linear asset index becomes hard to scan, and implementation can accidentally use a failed or superseded image.
- Pattern: when a design set grows beyond a few images or includes failed/superseded variants, create a small relationship map. At minimum, distinguish active implementation references, failed/do-not-use references, thread-only anchors, parent-child derivations, and superseded-by links. An HTML map with hover previews and click-through image links is useful when the user needs to inspect the set visually; a JSON map helps regenerate or audit the graph.
- Verification: check that every active node links to an existing local asset and that failed nodes are visually labeled as do-not-use.
- Avoid: relying only on filenames or a long markdown list to communicate which design image drives which UI state.

### 2026-05-07 - Image Tool Fallback Still Requires Structural Review

- Scope: global.
- Context: preferred image tool temporarily fails, times out, or returns upstream errors while generating implementation-ready UI references.
- Problem: switching tools can solve availability but may reintroduce visual drift, size drift, or looser reference adherence.
- Pattern: follow the user's current tool priority, retry transient preferred-tool failures within the tool's retry policy, and only use the secondary tool when allowed. Every fallback-generated image must still pass the same structural consistency review before it becomes an active reference.
- Verification: record which tool failed, why fallback was used, the output dimensions, and the structural review result in the design execution file or asset index.
- Avoid: accepting a fallback image because it exists or looks plausible without checking it against the anchor.

### 2026-05-07 - Confirm Platform Before UI Generation

- Scope: global.
- Context: generating design references for apps, websites, dashboards, phone views, tablets, TV, or responsive products.
- Problem: if the platform and breakpoint are not chosen first, generated screens can use mismatched dimensions and density, making later states hard to align and responsive behavior ambiguous.
- Pattern: before generating UI references, confirm or infer the target platform and breakpoint, then record the canvas. Use common defaults only when the product target is unknown: desktop full-screen web `1920x1080`, laptop/common web `1440x900` or `1366x768`, mobile web/H5 `390x844`/`393x852`/`430x932`, tablet `1366x1024` or `1024x1366`, TV/large screen `1920x1080`. If a tool requires dimensions divisible by 16, use the nearest recorded equivalent.
- Verification: the design execution file should show the platform/canvas decision before the first generated image, and every derived state should match the anchor dimensions unless it is an explicit separate breakpoint.
- Avoid: generating a desktop design and treating it as sufficient for mobile/tablet/TV, or mixing canvas sizes inside one screen family.

### 2026-05-07 - Derived State Review Must Include Micro Layout

- Scope: global.
- Context: generated follow-up UI states such as empty, loading, error, drawer, or selected states derived from an accepted anchor screen.
- Problem: a derived image can look correct at the broad layout level while still drifting in canvas size, sidebar details, header spacing, profile block, icon language, column geometry, or non-target data values.
- Pattern: before accepting a derived reference, run a structural consistency review against the anchor. Check exact image dimensions/aspect first, then compare shell, navigation vocabulary, header controls, metrics, gutters, column/card geometry, icon family, profile/user block, and whether only the target module/state changed. Any unrelated visible drift means regenerate before implementation.
- Verification: use at least one objective check such as image dimensions plus a visual row-by-row review recorded in the design execution file.
- Avoid: marking a generated state as passed because it has the same general page composition or because only the central feature area appears plausible.

### 2026-06-12 - First-Level Controls Must Close The Loop

- Scope: global.
- Context: design-led dashboards or operational screens with many visible primary and secondary controls.
- Problem: a screen can match the reference visually while prominent buttons, table rows, graph nodes, or inspector actions remain inert, ambiguous, or disconnected from the design map.
- Pattern: before implementation, enumerate every first-level visible control and classify it as `opens-covered-surface`, `inline-state-feedback`, `navigates-covered-route`, or `deferred-explicitly`. After implementation, reconcile this list with actual source click handlers so no shipped handler is unclassified and no visible control is silently dead.
- Verification: run browser interaction QA that clicks each first-level control and confirms a covered destination, inline status, or explicit disabled/deferred state.
- Avoid: treating a visually minor toolbar or inspector action as safe to ignore when it is visible in the accepted reference.

## Hygiene Rules

- Keep `SKILL.md` short; put growing detail in references.
- Replace stale lessons instead of appending contradictory notes.
- Do not store secrets, private credentials, cookies, or sensitive user data.
- Do not store unverified speculation as a rule. Mark uncertainty explicitly when a note is useful but not confirmed.
- If a lesson only applies to one codebase, keep it in that codebase's project-local skill.
- If a global lesson starts depending on MovieCat or any other single project, rewrite it into a project-neutral rule or move it back to that project's local skill.
