# Feature Experience Evolution

## Purpose

Keep reusable feature-building knowledge compact and useful across projects. Record product, UX, aesthetic, architecture, data, and verification lessons that reduce future rework.

## Start Of A Feature

1. Read the project `AGENTS.md`, active project memory, and project-local wrapper skills.
2. Search existing code and assets before proposing new surfaces.
3. Identify the feature's job, entry points, destination surfaces, related features, and data ownership.
4. Decide if a design reference is necessary or if the project has enough patterns to proceed.
5. Use web research only for knowledge gaps current local context cannot answer reliably.

## During Work

- Track product questions separately from implementation blockers.
- Prefer decisions that make the feature discoverable, reversible, and connected to adjacent workflows.
- Treat empty/error/offline states as part of the feature, not polish.
- Treat performance, caching, slow networks, and third-party failures as part of the feature contract for user-facing data.
- If a UI concept is needed, use existing visual patterns first; generate or request a reference only when it will materially change the result.
- Record candidate lessons only after verification or explicit user decision.

## End Of A Feature

Write a lesson when the work reveals:

- a reusable feature-shaping pattern.
- a common mistake or mismatch between UI and behavior.
- a useful verification tactic.
- a cache, fallback, timeout, or performance pattern that kept a feature usable.
- a reliable decision rule for when to ask for design/reference input.
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
