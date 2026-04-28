# UI From Design Evolution

## Purpose

Keep this skill useful as projects grow. Treat it as a compact, verified knowledge base for design-reference UI work, not as a chat transcript.

## Start Of A UI Module

1. Read the project `AGENTS.md` and any project-local wrapper skill.
2. Search the codebase for existing components, state models, theme tokens, assets, tests, screenshots, and prior design work before inventing new patterns.
3. Read this file and any project-local learning reference named like `*-learnings.md`, `patterns.md`, or `lessons.md`.
4. Identify knowledge gaps: platform behavior, framework APIs, accessibility, performance, visual asset needs, device constraints, or unclear design intent.
5. Build a design coverage matrix when the design has multiple functional areas or unclear states. Identify which module-level references must be generated or requested before implementation.
6. Use web search only for gaps that current local context cannot answer reliably. Prefer official docs, standards, source repositories, release notes, or vendor docs.

## During Implementation

- Record candidate lessons as you discover them, but only write durable entries after verification or a clear user decision.
- Keep selected, focused, active, loading, checked, favorite, and progress states data-driven.
- If an asset is missing, first search project assets. Generate only the required missing bitmap/vector/design asset, then save and record it according to project conventions.
- If a design area/state is missing or unclear, generate/request a small module-specific reference before coding that area instead of extrapolating from a broad screen.
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

### 2026-04-28 - Generate Module References For Complex Designs

- Scope: global.
- Context: large product designs with several feature areas, states, dialogs, or device variants.
- Problem: one or two broad mockups rarely specify every function area well enough to implement the whole feature set accurately.
- Pattern: create a design coverage matrix, split the target into small functional modules/states, and generate or request precise references for missing areas before coding them.
- Verification: compare each implemented module/state against its own reference, not only against the broad overview image.
- Avoid: completing a whole feature suite from a vague design mood or a single approximate screen.

## Hygiene Rules

- Keep `SKILL.md` short; put growing detail in references.
- Replace stale lessons instead of appending contradictory notes.
- Do not store secrets, private credentials, cookies, or sensitive user data.
- Do not store unverified speculation as a rule. Mark uncertainty explicitly when a note is useful but not confirmed.
- If a lesson only applies to one codebase, keep it in that codebase's project-local skill.
- If a global lesson starts depending on MovieCat or any other single project, rewrite it into a project-neutral rule or move it back to that project's local skill.
