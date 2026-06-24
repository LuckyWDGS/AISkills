# Feature Experience Evolution

## Purpose

Keep reusable feature-building knowledge compact and useful across projects. Record product, UX, aesthetic, architecture, data, and verification lessons that reduce future rework.

## Start Of A Feature

1. Read the project `AGENTS.md`, active project memory, and project-local wrapper skills.
2. Search existing code and assets before proposing new surfaces.
3. Identify the feature's job, entry points, destination surfaces, related features, and data ownership.
4. Identify the real data source of truth, parser/API/storage path, identity model, and empty/error behavior. Do not start from fake runtime data unless the user explicitly requested it.
5. Decide if a design reference is necessary or if the project has enough patterns to proceed.
6. If design/reference is involved, create a design-to-implementation contract before visible implementation so product intent, aesthetics, code, data, interaction, and verification stay linked.
7. Use web research only for knowledge gaps current local context cannot answer reliably.

## During Work

- Track product questions separately from implementation blockers.
- Prefer decisions that make the feature discoverable, reversible, and connected to adjacent workflows.
- Treat empty/error/offline states as part of the feature, not polish.
- Treat real data integration as part of the feature. Avoid placeholder lists, demo-only constants, and fake runtime state unless explicitly requested.
- Treat performance, caching, slow networks, and third-party failures as part of the feature contract for user-facing data.
- If a UI concept is needed, use existing visual patterns first; generate or request a reference only when it will materially change the result.
- When a design/reference exists, treat the design-to-implementation contract as the implementation gate. Add or revise rows when implementation reveals missing states, data ownership, or platform constraints.
- When a design/reference exists but still leaves a visible area unclear, stop that row and ask or generate the smallest missing module/state reference instead of half-implementing it.
- Record candidate lessons only after verification or explicit user decision.

## End Of A Feature

Write a lesson when the work reveals:

- a reusable feature-shaping pattern.
- a common mistake or mismatch between UI and behavior.
- a useful verification tactic.
- a cache, fallback, timeout, or performance pattern that kept a feature usable.
- a real-data parsing, identity, migration, or source-of-truth pattern that prevented fake or brittle feature behavior.
- a reliable decision rule for when to ask for design/reference input.
- a reliable traceability rule that keeps a design/reference connected to code, data, state, and verification.
- an external source that changed implementation.

Before writing, classify the lesson:

- Global: applies across projects or product types, can be stated without project names, local file paths, private APIs, one-off user taste, or domain-specific labels.
- Project-local: depends on one codebase's architecture, naming, assets, data sources, screens, user decisions, device setup, or release constraints.
- Promote only the generalized rule. Keep the concrete project example in the project-local wrapper skill or project memory.
- Do not duplicate a project-specific lesson into global references just because it was important in that project.

## Entry Template

```markdown
### YYYY-MM-DD - Short Lesson Name

- Scope: global or project-specific.
- Context: feature, module, platform, or workflow.
- Problem: what was unclear, broken, or repeatedly expensive.
- Pattern: the next-time approach.
- Design/reference: whether reference input was needed and why.
- Code/data: source of truth, state, persistence, or architecture note.
- Real data: API/parser/storage path, identity, fixtures/prototype exception if any.
- Performance/cache: latency, cache freshness, stale fallback, retry, or degradation note.
- Verification: build, test, screenshot, device, user confirmation.
- Sources: official/primary links and access date when used.
- Avoid: when not to apply this pattern.
```

## Hygiene

- Do not store chat transcript.
- Do not store secrets or sensitive user data.
- Keep global lessons technology-neutral unless a platform-specific lesson is broadly useful.
- Move project-only details into the project-local wrapper skill.
- If a global note starts naming a single project, screen label, database table, path, or user-specific design preference, move that detail back to the local skill and leave only the abstract rule here.

## Seeded Global Lessons

### 2026-05-12 - Runtime Semantics Need Their Own Feature Audit

- Scope: global.
- Context: feature families with multiple modules whose accepted references differ in search placeholders, titles, primary actions, tabs, filters, or other small semantic UI text.
- Problem: a feature can look visually aligned while still using stale copy from a neighboring module, which makes the product feel incoherent and can hide that implementation did not re-enter the design contract after a reference refresh.
- Pattern: add a runtime semantic audit for affected feature families. Navigate through the surfaces and verify key semantic slots against the feature/design contract, not just against static screenshots.
- Design/reference: the audit should be driven by accepted references or a copy source-of-truth contract.
- Code/data: bind the copy to real module state or i18n/copy config so it changes with the active feature surface.
- Verification: in TestUI, a semantic audit caught `Search tasks...` leaking into Initiatives, Calendar, and Settings, then passed after the runtime `searchPlaceholder` mapping was updated.
- Avoid: treating text drift as harmless because the layout and click targets still work.

### 2026-05-12 - Local Automation Needs Target Identity Checks

- Scope: global.
- Context: feature verification using local browser automation while several apps or dev servers may be running.
- Problem: tests can interact with the wrong localhost app, causing false failures or false confidence.
- Pattern: require explicit URLs or ports for local browser audits and assert an app-specific identity marker before starting feature checks.
- Design/reference: this is especially important for design-led tests because the wrong app can still render a polished UI and confuse visual review.
- Code/data: make the audit fail fast with a clear wrong-target error instead of timing out on missing controls.
- Verification: in TestUI, the first audit hit another app on port `5173`; adding explicit `TESTUI_URL` plus an `.app-shell` identity check made the audit reliable on `5174`.
- Avoid: relying on whichever dev server happens to own the default port.

### 2026-05-12 - Workflow Rules Must Be Proven On Real Tasks

- Scope: global.
- Context: reusable feature workflows that evolve after real project failures, such as design drift, missing interaction coverage, fake data, weak caching, or incomplete verification.
- Problem: adding a rule to a skill can create a false sense of safety if no real task proves that the rule changes planning, implementation, or verification behavior.
- Pattern: pair workflow changes with a real-task validation loop. Use a real feature task, active harness task, or smallest realistic scenario; record expected enforcement, observed result, pass/fail, and the next capability/tool/verification gap.
- Design/reference: design-led features should record this in the same execution artifact as coverage and contract rows so rule validation stays tied to the work.
- Code/data: if no code/data scenario exercises the rule yet, mark it unproven and name the next scenario instead of claiming the skill is solved.
- Verification: the next session should be able to see what was actually tested and what still needs a practical proof.
- Avoid: judging skill quality only by whether the documentation validates or sounds comprehensive.

### 2026-05-12 - Good Workflow Improvement Needs Small Next Fixes

- Scope: global.
- Context: feature and workflow work where the team repeatedly notices missing tooling, weak verification, or manual friction.
- Problem: if each task only records what went wrong, the workflow never becomes practically easier to use; the same pain returns in the next project.
- Pattern: always pair a discovered gap with the smallest reasonable next fix. Keep the gap concrete, classify it as global or project-local, and make it small enough that a later task can actually implement it.
- Design/reference: the same rule applies whether the gap came from design generation, review flow, copy ownership, runtime validation, or tool support.
- Code/data: concrete gaps often point to missing scripts, missing contract sections, missing review surfaces, or missing runtime tests.
- Verification: the next session should be able to pick one backlog item and close it without needing hidden context.
- Avoid: turning the skill into a pile of abstract complaints.

### 2026-05-12 - Features Need Flow Integrity, Not Just Screen Coverage

- Scope: global.
- Context: feature work with entry flows, dialogs, side panels, retry loops, returns, or undo/remove branches.
- Problem: a feature can have complete-looking page references and still fail in actual use because forward and backward paths were never designed as one system.
- Pattern: audit flow integrity explicitly. Track entry, destination, return, cancel/close, retry, and undo/remove branches as part of the feature contract.
- Design/reference: new references may be needed only for missing states in a branch, not necessarily for every step.
- Code/data: route changes, retries, and close behavior should be verified against the same contract as the page visuals.
- Verification: traverse the full path, not only the final destination screen.
- Avoid: equating “all pages exist” with “the feature flow is complete.”

### 2026-05-12 - Copy Ownership Is Part Of Feature Stability

- Scope: global.
- Context: features whose visible copy can come from design images, product documents, i18n resources, API data, or local configuration.
- Problem: copy can drift silently because different implementation surfaces treat different sources as authoritative.
- Pattern: record one copy source of truth for each high-visibility string group and keep implementation tied to it.
- Design/reference: design text is visual guidance unless explicitly declared the final copy source.
- Code/data: if API text is authoritative, treat local labels as wrappers; if i18n is authoritative, keep API and design text from overriding it accidentally.
- Verification: compare implemented strings to the chosen source rather than whichever artifact was edited last.
- Avoid: mixing product copy, design copy, and implementation copy without an explicit owner.

### 2026-05-12 - Later Feature Changes Must Reopen The Contract

- Scope: global.
- Context: a feature already passed design-led review and later gets an additional action, field, state, or copy change.
- Problem: later edits are often treated as “small enough” to bypass the original process, which slowly breaks traceability and consistency.
- Pattern: use a change-impact re-entry rule. Reopen the affected feature/design rows and rerun the relevant gates whenever a later change touches visible behavior.
- Design/reference: if the later change introduces a new visible state or branch, add the missing reference or contract row before coding it.
- Code/data: re-entry is required for copy, slots, primitives, interactions, async behavior, and state precedence changes, not only for large layout changes.
- Verification: the updated contract should show what changed and what was revalidated.
- Avoid: assuming “already reviewed once” means the feature can evolve informally forever.

### 2026-05-12 - Small Generated Labels Can Break A Real Feature

- Scope: global.
- Context: feature work that relies on generated design references with small labels, tabs, field names, or helper text.
- Problem: a feature can look visually aligned while still carrying wrong or unreadable microcopy in the reference image, which then leaks into implementation assumptions or hides a missing copy contract.
- Pattern: audit dense microtext separately. If small generated copy is wrong, repair it locally or mark the implementation to use real rendered text from the actual copy contract.
- Design/reference: treat microcopy drift as a blocking defect for the affected surface, not as harmless noise.
- Code/data: bind final visible labels to real copy and real fields instead of copying flawed generated text.
- Verification: zoom/crop review the affected text zones before promoting the reference.
- Avoid: discarding a strong whole-layout reference when only a tiny text area failed, but also avoid waving the failure through because “it’s just a small label.”

### 2026-05-12 - Feature States Need Precedence, Not Just Coverage

- Scope: global.
- Context: feature work with several valid visual states that can overlap at runtime.
- Problem: the feature may have references for loading, error, empty, retry, stale, or permission states, but still behave inconsistently because nobody decided which one should dominate when several happen together.
- Pattern: write a state precedence matrix alongside the feature/design contract. Decide which state wins, which can decorate loaded content, and which fully replace the surface.
- Design/reference: a separate reference may be needed only when a winner state materially changes layout; otherwise the matrix is the missing contract.
- Code/data: precedence must follow product rules, not conditional order in the component.
- Verification: trigger overlapping states and confirm runtime behavior matches the matrix.
- Avoid: assuming that covering each state independently is enough.

### 2026-05-12 - Visual Slots Are Part Of The Data Contract

- Scope: global.
- Context: features where the design expects several information slots in each card, row, header, or detail panel.
- Problem: the feature can look complete in a mock while relying on fields the real API or repository does not reliably provide.
- Pattern: audit every visible slot and map it to a real field, derived field, or fallback strategy before implementation.
- Design/reference: when a critical slot has no real data owner, either redesign the slot behavior or explicitly mark the fallback.
- Code/data: keep null/missing handling, truncation, and source ownership in the same contract, not scattered through implementation.
- Verification: use real payloads with missing and long values.
- Avoid: inventing stable product data only because the layout has room for it.

### 2026-05-12 - Primitive Compatibility Is A Feature Decision

- Scope: global.
- Context: implementing a feature inside an existing design system or component library.
- Problem: a feature can drift for days because the team chose to reuse an existing primitive that never really matched the target design or interaction model.
- Pattern: make primitive compatibility explicit in the feature contract. For each relevant shared primitive, decide whether to inherit, wrap, fork, or rebuild.
- Design/reference: if the design depends on geometry or states the current primitive cannot express cleanly, compatibility has already failed.
- Code/data: the right primitive decision reduces downstream override debt and keeps later changes more stable.
- Verification: check the final surface and neighboring surfaces for override sprawl or shared-component regressions.
- Avoid: treating component reuse as automatically correct because the names are similar.

### 2026-05-12 - Feature References Need Versioned Ownership

- Scope: global.
- Context: feature work with evolving design references, generated follow-up states, interaction maps, and screenshot baselines.
- Problem: when a new design version is accepted for one feature surface, the surrounding implementation and review artifacts can keep pointing at the old version, so the feature loses one source of truth.
- Pattern: treat accepted design references as versioned feature inputs. Record which version is active, what scope it replaces, and which artifacts must be resynced before continuing implementation: contract rows, hotspot review, design map, and approved baselines.
- Design/reference: old versions remain useful as rejected/superseded audit artifacts, not as parallel implementation sources.
- Code/data: if a feature row still points at an old design version, it is blocked until the row is updated or explicitly deprecated.
- Verification: final review should show that each feature row points at the active design version for its scope.
- Avoid: assuming a new image automatically replaces all related feature artifacts.

### 2026-05-12 - Focus And Accessibility Are Feature Behavior

- Scope: global.
- Context: features opened by keyboard, remote, dialogs, menus, tables, drawers, forms, or dense operational UIs.
- Problem: teams often treat focus and accessibility as a UI polish pass, but they determine whether the feature is actually operable and understandable.
- Pattern: add a focus/accessibility contract when the feature depends on keyboard, remote, or assistive technology behavior. Cover focus entry/order, triggers, close/back behavior, trap/release, roles, labels, and critical announcements as part of the feature contract.
- Design/reference: use a focused derived reference only when visual focus states or accessibility-critical structure are unclear.
- Code/data: keep these rules tied to the real control tree and state transitions, not only to CSS focus styles.
- Verification: test keyboard/remote traversal and accessible names/roles as part of feature QA.
- Avoid: declaring a feature done because the pointer path works.

### 2026-05-12 - Async State Ownership Is Part Of The Feature Contract

- Scope: global.
- Context: features that search, refresh, save, retry, paginate, submit, or switch data sources.
- Problem: the feature can look visually aligned yet still lie to the user when stale responses overwrite current intent, pending states belong to the wrong request, or optimistic UI never reconciles.
- Pattern: record an async/state-ownership contract: source of truth, visible pending owner, stale-response policy, cancellation/ignore behavior, optimistic update rules, and retry/reconciliation path.
- Design/reference: screenshots show destination states, but the contract decides which async event is allowed to move the UI between them.
- Code/data: pair the contract with real repository/API/storage behavior so success/error/loading visuals belong to the correct request lifecycle.
- Verification: test slow, failed, repeated, and out-of-order responses.
- Avoid: allowing async behavior to emerge implicitly from whichever promise resolves last.

### 2026-05-12 - Static Design Gaps Are Feature Requirements

- Scope: global.
- Context: feature work that uses static UI references but includes behavior that a single screenshot cannot express.
- Problem: motion, scroll behavior, fonts/icons, forms, permissions, localization, and visual performance can be treated as UI polish even though they change how the feature works and how trustworthy it feels.
- Pattern: when a feature is design-led, treat static design gaps as part of the feature contract. Add motion/scroll contracts, asset manifests, feasibility/performance checks, form and permission matrices, and i18n pressure cases before coding affected surfaces.
- Design/reference: generate/request focused references only when a written contract is not enough to implement or verify the visible state.
- Code/data: keep these rows tied to real state, role, validation, and data behavior; do not hard-code the screenshot's apparent state.
- Performance/cache: record any visual concession required for the target device or browser before implementation.
- Verification: test the relevant behavior or state matrix as part of feature QA, not only visual screenshot fit.
- Avoid: claiming a design-led feature is complete because the default static state matches while transitions, scrolled states, permissions, validation, or localized text still drift.

### 2026-05-12 - Risk Tier Feature Gates Instead Of Flattening The Process

- Scope: global.
- Context: product teams using strict design/reference workflows across large and small feature changes.
- Problem: a uniform heavy process slows simple changes, while a uniform light process misses high-risk UI and behavior drift.
- Pattern: assign high/medium/low risk per feature surface. High risk gets full design, interaction, state, asset, performance, and verification gates. Medium risk gets relevant gates with skip reasons. Low-risk inline rows can move quickly only when the reason and upgrade trigger are explicit.
- Design/reference: risk tier determines how many references/contracts are needed; it never overrides a clearly missing high-impact design state.
- Code/data: if implementation adds a live handler, new surface, role branch, form state, or data-dependent visual, upgrade the row and fill the missing contract.
- Performance/cache: heavy visual effects or slow data paths raise risk even when the layout is small.
- Verification: final review should report tier changes and any skipped gates that remained safe.
- Avoid: using "low risk" as a label for anything merely small on screen.

### 2026-04-27 - Critical Surfaces Need Stale Fallbacks

- Scope: global.
- Context: home screens, dashboards, menus, and other first-run or high-frequency surfaces that depend on remote APIs.
- Problem: if the UI waits only for a slow or failing external API, the feature can appear empty or broken.
- Pattern: use a stale-while-revalidate flow for important user-facing data: show the last successful cached data immediately, start a bounded background refresh, update the UI and cache only when fresh data succeeds, and surface a small warning only when the refresh fails.
- Design/reference: usually no new design is required; the design decision is an empty/stale/refresh state, not a new layout.
- Code/data: define source of truth, cache key, freshness window, serialization, invalidation, and whether stale data is acceptable per feature.
- Performance/cache: set explicit timeouts and concurrency limits; avoid blocking the primary screen on optional external data.
- Verification: test cold cache, warm cache, slow network, API failure, successful refresh, and app restart persistence.
- Avoid: replacing useful cached data with empty lists after a transient failure.

### 2026-04-28 - Runtime Features Use Real Data By Default

- Scope: global.
- Context: feature modules, product surfaces, and UI connected to application behavior.
- Problem: fake runtime data can make a feature look complete while hiding parsing, identity, empty-state, persistence, API, and error-handling problems.
- Pattern: build product/runtime paths on real data sources, real parsers, real repositories, and real storage by default. Use honest loading/empty/offline/error/stale states when real data is unavailable.
- Design/reference: sample text or cards in a mock are illustrative unless explicitly provided as product data.
- Code/data: keep test fixtures and mocks inside test/prototype boundaries, clearly labeled and not used by production/runtime code.
- Performance/cache: pair real external data with bounded timeouts, cache, stale fallback, and retry behavior when needed.
- Verification: test against real payloads/API responses/storage rows where feasible; if fixtures are used for automated tests, keep them representative and isolated.
- Avoid: hard-coded demo records, fake recommendations, fake status widgets, or placeholder arrays in runtime feature code.

### 2026-04-30 - Design Must Be A Build Contract

- Scope: global.
- Context: feature work where a design, generated reference, mockup, or screenshot informs implementation.
- Problem: design and code can drift into separate tracks: the design shows intent, while implementation follows existing habits or only matches the broad mood.
- Pattern: before visible implementation, write a design-to-implementation contract that maps each feature area/state to reference, code target, real data/state, interaction behavior, and verification. Implement only mapped rows or infrastructure required by mapped rows.
- Design/reference: generated references must state which feature/module/state they unblock; broad references require smaller module/state rows before coding uncovered surfaces.
- Code/data: if real data or architecture makes a row impossible, update the row with the tradeoff rather than silently diverging.
- Performance/cache: include performance, cache, and degraded-state implications when they affect what the user sees.
- Verification: final review should walk contract rows and mark implemented, changed, deferred, or blocked items.
- Avoid: treating a design as inspiration while coding from memory, mood, or unrelated existing UI patterns.

### 2026-04-30 - Unclear Design Requires A Pause, Not A Guess

- Scope: global.
- Context: design-led feature work where the user has provided a reference, but some modules, states, or interactions are still ambiguous.
- Problem: implementation can rush ahead, complete only the obvious pieces, and invent the rest without aligning with the user or a focused design reference.
- Pattern: if a visible module/state is unclear, pause that row, ask a concise clarifying question or generate/request a focused design reference, then continue from the updated contract.
- Design/reference: broad references should be split until the missing decision is local and testable.
- Code/data: do not let real-data wiring become an excuse to skip unresolved design behavior; track both in the same row.
- Verification: blocked or deferred rows should be reported explicitly instead of being hidden by a mostly-finished screen.
- Avoid: half-implementing a design-led feature and treating the unresolved remainder as acceptable drift.

### 2026-05-06 - Empty Runtime Beats Mock Occupancy

- Scope: global.
- Context: feature UIs whose designs show example tasks, cards, records, or multiple state samples to explain the intended look.
- Problem: implementation may preserve the mock occupancy from the design even when the real runtime dataset is empty, which produces misleading UI.
- Pattern: separate layout/state demonstration content from actual runtime requirements. If the source of truth is empty, render the real empty/blank state or suppress the section according to the product rules.
- Design/reference: use the mock content to understand spacing, hierarchy, and possible states, not as a mandate to keep placeholder records on screen.
- Code/data: empty-state behavior must come from the real repository/API/storage result, not from leftover sample arrays or static placeholder composables.
- Verification: test both populated and empty runtime states and confirm the empty state does not visually retain design-time sample items.
- Avoid: copying occupied mock sections literally into runtime UI where no real data exists.

### 2026-05-06 - More Small Design References Reduce Feature Drift

- Scope: global.
- Context: feature work where the user provides some design direction but many module/state details are still missing.
- Problem: if missing coverage is left unresolved, implementation either stalls or starts guessing from one broad mockup.
- Pattern: proactively generate the missing module/state references whenever the blocker is visual detail rather than a true product decision. Prefer multiple narrow, implementation-ready references over one large approximate concept.
- Design/reference: reserve user questions for true product choices, conflicting intent, or taste direction that cannot be inferred safely.
- Code/data: connect each generated reference to a contract row before implementation so the new images reduce ambiguity instead of adding noise.
- Verification: confirm each generated reference directly unlocks one module/state implementation or one blocked contract row.
- Avoid: treating “we already have one big design” as sufficient when the actual implementation still lacks precise per-state guidance.

### 2026-05-06 - Generated References Must Unlock Implementation

- Scope: global.
- Context: feature work that fills missing coverage with generated design references.
- Problem: concept-style generated images can still leave code structure, states, and user-facing details unresolved.
- Pattern: generated references should be implementation-ready artifacts. Each one should clarify one concrete module/state enough to become contract rows and immediate implementation tasks.
- Design/reference: prefer targeted buildable references over expressive but underspecified visual concepts.
- Code/data: if the generated image still requires major invention to map into code and state, regenerate/refine before implementation.
- Verification: a good generated reference should noticeably reduce questions during implementation rather than create new ambiguity.
- Avoid: accepting a beautiful concept image as sufficient when it does not directly support coding.

### 2026-05-06 - One Design Anchor Per Feature Surface

- Scope: global.
- Context: feature work that uses a main design reference plus generated follow-up state/module images.
- Problem: inconsistent follow-up images can reintroduce ambiguity even when each image looks individually usable.
- Pattern: nominate one primary design reference as the anchor for the surface, and require all generated follow-up images to inherit its shell and visual language before implementation.
- Design/reference: regenerate drifting state/module images instead of reconciling their differences ad hoc in code.
- Verification: before coding, check that each follow-up reference still matches the anchor in layout logic, controls, spacing, and tone.
- Avoid: blending several slightly different generated designs during implementation.

### 2026-05-06 - Parent-State References Preserve UI Consistency

- Scope: global.
- Context: generating second-level menus, drawers, overlays, or post-click states from a primary UI screen.
- Problem: using only the homepage or only a text prompt often loses local structure that should persist across the interaction.
- Pattern: use the homepage as the main anchor, but also include the direct parent or upper-level screen as a reference whenever generating a deeper state. If reference slots are limited, anchor and parent should outrank decorative or redundant views.
- Design/reference: keep a small ordered pack of the most informative references rather than a random bundle of screenshots.
- Verification: check whether shared regions such as sidebar, header, shell, and icon language remain stable across the generated states.
- Avoid: generating every deeper state from the homepage alone when a closer accepted parent state exists.

### 2026-05-08 - Review Must Align Visuals, State, And Real Data

- Scope: global.
- Context: feature work that has both a design target and runtime behavior.
- Problem: a feature can pass a superficial visual check while still drifting in counts, empty-state behavior, selected-state logic, icon language, or data truthfulness. That leaves the screen "looking right" but behaving differently from the design or the real source of truth.
- Pattern: review in layers. First check shell and layout against the anchor. Then check state semantics: selected/open/empty/loading/error states, counts, and which elements are real data versus illustrative content. Finally check the runtime flow: clicks, retries, navigation, and whether the screen still works when data changes. Treat any disagreement as a fix or regeneration task, not as acceptable variance.
- Design/reference: when a reference exists, keep every visible state tied to a reference or an explicit inline behavior.
- Code/data: real data should drive the runtime result by default; if the screen shows a count or badge, confirm it comes from actual state, not from a decorative constant unless the project explicitly uses seeded demo data.
- Verification: compare screenshots plus interactive checks, and confirm the visible result still matches the intended runtime state after clicks, retries, and empty/loading/error transitions.
- Avoid: approving a feature because the screen composition matches while the behavior, counts, or source of truth diverge.

### 2026-05-08 - Build A Clickable Inventory Before Implementation

- Scope: global.
- Context: feature modules or product surfaces with many clickable controls and destination states.
- Problem: some controls look covered by a broad page reference but actually lead to missing or underspecified states. That creates either dead clicks or ad hoc implementation guesses.
- Pattern: enumerate every clickable point first, then classify it as `covered`, `inline`, or `missing`. Implement only what is mapped. For missing rows, generate or request the smallest useful reference before coding. After implementation, verify row-by-row that each click lands on a known state or an explicit inline behavior.
- Design/reference: small state-specific references are preferred when the click opens a new module, dialog, or empty/loading/error state.
- Code/data: inline behavior is acceptable only when the product really stays on the same page and the data/state change is explicit.
- Verification: final QA should confirm the click inventory is closed or clearly deferred, not merely that the page looks complete.
- Avoid: turning a visually plausible page into a feature by inventing unreferenced click destinations or ignoring buttons that seem minor.

### 2026-05-08 - Reconcile Actual Code Clicks With Design Coverage

- Scope: global.
- Context: feature work where UI has already been partially implemented or where implementation continues while design coverage is being audited.
- Problem: a design hotspot pass can look closed while the code contains extra live handlers, shortcut paths, row clicks, or inline actions that were never classified.
- Pattern: extract interactive handlers from the source and keep a code-level click inventory next to the design contract. Classify every live handler as `covered`, `inline`, or `missing`; missing handlers must get a focused design reference or be explicitly deferred before completion.
- Design/reference: the design hotspot map proves what should exist; the code inventory proves what actually exists.
- Code/data: treat inline behavior as a real state/action decision, not as a hiding place for unreviewed UI.
- Verification: run the extraction again after implementation changes and confirm no new live click is unclassified.
- Avoid: claiming interaction closure from design screenshots alone when the shipped code can still do more than the design map says.

### 2026-05-08 - Skill Evaluation Projects Are Not Feature Backlogs

- Scope: global.
- Context: a project is created to test and improve reusable skills or workflows, using a demo app as the proving ground.
- Problem: implementation can drift into ordinary feature delivery, which hides whether the skill actually prevented mistakes or just produced a nicer demo.
- Pattern: treat every code change as an experiment against the workflow. Before claiming success, state what the skill was supposed to enforce, what happened, what failed or worked, and whether the reusable skill or project memory changed as a result.
- Design/reference: use generated or supplied designs as test fixtures for the skill's traceability rules, not as a product roadmap to expand indefinitely.
- Code/data: code is still useful, but only insofar as it proves the workflow can constrain implementation and reveal drift.
- Verification: final reports should include skill-level outcomes such as guardrail passed/failed, rule patched, and remaining reliability risk.
- Avoid: judging the work only by implemented features, screenshots, or build success.

### 2026-05-08 - Visual Diff Is A Feature Review Signal

- Scope: global.
- Context: design-led features where aesthetics, state, and implementation must stay bound.
- Problem: a global screenshot diff can miss tiny but important control drift, while exact design-vs-DOM pixel matching can overreact to harmless rendering differences.
- Pattern: define visual-diff checkpoints around feature-critical regions: shell/navigation, primary actions, state panels, drawers/dialogs, cards/lists, and any hotspot users act on. Treat these diffs as prompts for row-by-row review, then verify behavior and state truth separately.
- Design/reference: the design contract should name which reference and region each screenshot comparison supports.
- Code/data: visual diff does not prove data correctness; it must be paired with real state, interaction, and click-audit verification.
- Verification: a minimal TestUI probe caught a synthetic 6px primary-action drift at the region level while demonstrating that full-page design-vs-live diff is too noisy to be the only gate.
- Avoid: using screenshot diff as a replacement for design contracts, real data/state checks, or manual/AI visual inspection.

### 2026-05-08 - Reuse Hotspot Coordinates For Visual Guardrails

- Scope: global.
- Context: feature work with an existing design hotspot/prototype audit and later screenshot verification.
- Problem: feature teams can close interaction coverage but still miss small visual drift, while independent visual diff scripts often duplicate or contradict the hotspot map.
- Pattern: let the hotspot map seed feature-critical visual-diff regions, then keep larger structural regions for layout. Use hotspot-level diff to catch control movement and screenshot-to-screenshot regressions; use design-vs-DOM hotspot warnings as review prompts because text rendering differences are expected.
- Design/reference: each hotspot-derived region should still point back to a design reference, target behavior, or inline classification.
- Code/data: visual regions do not prove behavior; pair them with click inventory and state/data checks.
- Verification: TestUI derived 15 home hotspot regions from `design-review.json`; the New Task hotspot caught a 6px synthetic nudge, proving reuse is practical while also showing threshold calibration is required.
- Avoid: maintaining separate, conflicting click maps and visual-diff region lists.

### 2026-05-08 - Baseline Screenshot Regression Separates Noise From Drift

- Scope: global.
- Context: design-led feature verification where pixel diff is used to protect visual details.
- Problem: generated design images and browser DOM can differ enough to create many review warnings, especially in text-heavy controls, making it hard to know whether a later warning is real regression or expected rendering noise.
- Pattern: take two no-change screenshots of the implemented UI at the canonical viewport and compare them before evaluating drift. Use that baseline as the per-region noise floor, then require later regression warnings to exceed the calibrated baseline. Keep design-vs-DOM diff as a review aid, not the calibration source.
- Design/reference: the baseline belongs to the same reference/contract row and viewport as the UI being checked.
- Code/data: if the baseline is noisy, stabilize timers, animations, random data, loading states, fonts, or viewport setup before trusting visual diff.
- Verification: TestUI produced a no-change baseline of `0` for the full canvas and all home hotspots, then caught a synthetic New Task hotspot drift at `0.17785`.
- Avoid: accepting or rejecting feature fidelity from uncalibrated design-vs-DOM pixel differences.

### 2026-05-08 - Validate Workflow Guardrails With Reversible Code Drift

- Scope: global.
- Context: feature or design workflow evaluation where the goal is to improve future AI reliability.
- Problem: a guardrail can look useful in reports while still failing to catch real implementation drift.
- Pattern: use a small reversible code/style change as a controlled failure test. The guardrail should fail on the intended feature region, the failure artifact should be saved, and the code should be restored with a clean rerun before the task is considered successful.
- Design/reference: tie the drift target to a contract row or hotspot, such as a primary action button or key card.
- Code/data: keep the drift temporary and scoped; do not change runtime data or unrelated behavior.
- Verification: TestUI temporarily shifted the primary action by 6px; calibrated approved-baseline comparison flagged the New Task hotspot at `0.14214`, then returned to `0` after the CSS line was removed.
- Avoid: proving guardrails only with synthetic images while never testing actual app code, or accidentally shipping the artificial drift.

### 2026-05-08 - Split Blocking And Review Visual Signals

- Scope: global.
- Context: feature teams want automated visual protection without constant false positives.
- Problem: some visual comparisons are good for human review but too noisy to decide deployment, especially design-vs-DOM comparisons around text-heavy controls.
- Pattern: keep two layers. `approved-vs-live` and `baseline-repeat` are blocking because they measure real implementation drift and runtime stability. `design-vs-live` stays non-blocking and feeds review queues, screenshots, or PR comments.
- Design/reference: the approved baseline represents the currently accepted shipped or reviewed implementation, not the raw source design bitmap.
- Code/data: regenerate the approved baseline only after an intentional accepted UI change.
- Verification: TestUI CI-mode visual guardrail passed with non-blocking design review rows, failed on temporary real CSS drift, and passed again after restoration.
- Avoid: blocking releases on every design-vs-DOM warning or overwriting the approved baseline during a failing run.

### 2026-05-08 - Visual Gate Policy Belongs In A Contract

- Scope: global.
- Context: feature workflows that want screenshot guardrails to help CI, PR review, or repeated AI implementation checks.
- Problem: without an explicit policy file, visual-diff scripts can mix product-critical drift, noisy design-vs-DOM prompts, and synthetic probes in one report, making it hard to know what automation should block.
- Pattern: define a machine-readable visual gate contract with comparison channels, critical regions, severity, thresholds, and rationale. Then emit a compact summary that separates blocking findings from review signals.
- Design/reference: the contract should reference the same viewport, design/hotspot ids, and approved baseline used by the design-to-implementation contract.
- Code/data: treat the approved screenshot baseline as the accepted implementation source for regression checks; update it only after an intentional UI change has passed design review.
- Verification: TestUI added `visual-guardrail.contract.json` and `visual-guardrail-gate-summary.json`; clean CI passed, a temporary 6px primary-action drift failed with one blocking `home: New Task` finding, and the restored UI passed again.
- Avoid: deciding gate severity from ad hoc console output or hiding review-only visual differences from designers/developers.

### 2026-05-08 - Accepted UI Changes Still Need A Post-Update Gate Pass

- Scope: global.
- Context: feature teams or AI workflows that intentionally approve a UI change and then refresh the approved screenshot baseline.
- Problem: updating the baseline during the same run can hide whether the next normal CI run will stay stable, especially when one visual change also shifts neighboring critical regions.
- Pattern: after an accepted UI change, run the visual gate once with the baseline-update flag, then rerun the normal gate without the flag and require a clean pass. Keep the pre-update failure artifact so the team can see which critical regions moved together.
- Design/reference: compare the failure regions against the design/hotspot contract; an accepted change may legitimately require approving multiple neighboring regions, not only the obvious primary target.
- Code/data: in harnesses, restore the canonical baseline and code after the experiment if the UI change was only used to test workflow reliability.
- Verification: in TestUI, increasing the primary-action button width triggered blocking findings for both `home: New Task` and the adjacent `home: Search input`; after `TESTUI_UPDATE_APPROVED_BASELINE=1`, the same UI passed, and the next clean CI run without the flag also passed.
- Avoid: assuming the changed hotspot list will contain only the intended control or treating the baseline write step as the end of verification.

### 2026-05-09 - Overlay Audits Should Separate Scrim From Shell

- Scope: global.
- Context: feature design reviews for drawers, confirmations, popovers, and detail panels that intentionally dim the parent page.
- Problem: comparing an overlay state directly to its parent can make the whole shell look broken because the scrim darkens sidebar, header, and metrics, even when the only real change is the new overlay surface.
- Pattern: audit overlay states against their parent by separating the intentional dimmed backdrop from the shell itself. Focus on whether geometry, unchanged controls, and parent content stay aligned, then review the overlay as the only target-state addition.
- Design/reference: parent-child pairing still matters, but a correct overlay should not be rejected just because its scrim changes most shared pixels.
- Verification: in the TestUI design audit, `new-initiative-drawer` and centered confirmation dialogs produced extreme shell-diff numbers until the review discounted the scrim; visual inspection confirmed the background page stayed aligned and only the intended overlay changed.
- Avoid: treating any high full-page diff on an overlay reference as proof that the image drifted from its parent.

### 2026-06-12 - Live Event Features Need Density Verification

- Scope: global.
- Context: monitoring, streaming, audit-log, workflow, or realtime dashboards driven by live event feeds.
- Problem: simulated or sparse fixture data can prove layout and APIs but fail to reveal real event density, repeated event names, ordering, overflow, throttling, or inspectability problems.
- Pattern: pair fixture validation with a real or high-density event run before calling the feature complete. Test repeated events, bursty updates, long logs, partial runs, completed runs, and stale/no-event states. Add stable visible identifiers when repeated items must be individually inspected or clicked.
- Design/reference: dense states may need their own design/reference or contract rows if the default screen only shows a clean sample.
- Code/data: preserve source event identity while deriving user-friendly labels, grouping, ordering, and summaries from the real stream.
- Verification: run the UI against live or density-equivalent data and click representative repeated events, log rows, and timeline/graph nodes.
- Avoid: declaring a realtime monitor finished from one static screenshot or a low-volume simulated stream.

### 2026-06-12 - Bilingual Runtime UIs Should Preserve Source Text

- Scope: global.
- Context: operational UIs that translate runtime events, model outputs, logs, summaries, or user-generated content.
- Problem: replacing source text with translated text can improve readability but remove the original debug/audit signal; showing both without a rule can create inconsistent ordering and noisy layouts.
- Pattern: define a bilingual display contract: choose the primary language by UI mode, keep source/original text available as the secondary layer when debugging or auditability matters, and distinguish interface-owned labels from runtime/model-generated content.
- Design/reference: dense bilingual rows need overflow and hierarchy rules so translation does not break layout density.
- Code/data: cache or derive translations separately from immutable source payloads; never mutate raw event/log content for display convenience.
- Verification: test both language modes and confirm primary/secondary order flips consistently while raw/source detail remains inspectable.
- Avoid: translating away diagnostic identifiers, or mixing interface i18n labels with runtime content as if they had the same source of truth.
