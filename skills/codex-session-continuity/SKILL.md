---
name: codex-session-continuity
description: Maintain lightweight project memory and handoff notes so Codex can continue work across long or slow sessions without carrying a huge transcript. Use automatically for project work when starting a session, ending or pausing a task, preparing a final response after edits, checkpointing progress, preparing a new window or session, reducing context size, summarizing long Codex conversations, creating project memory, or handling Chinese-language requests about session memory, context compression, handoff docs, or continuing in a new Codex window.
---

# Codex Session Continuity

## Overview

Externalize the durable parts of a long Codex conversation into small project files, then resume from those files in a fresh session. Prefer compact, verified project memory over transcript summaries.

## Core Workflow

1. Load rules from this skill file: `C:/Users/QY/.codex/skills/codex-session-continuity/SKILL.md`.
2. Use helper script: `C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py`.
3. Locate the work root from the current task. Store memory in the corresponding project directory, not in global `C:/Users/QY/.codex` and not in a parent workspace/monorepo unless the task explicitly spans that parent. Walk upward from the current directory and prefer the closest existing `.codex/session/HANDOFF.md`; otherwise prefer the closest project marker such as `settings.gradle.kts`, `package.json`, `Cargo.toml`, `pyproject.toml`, or `README.md`. Do not automatically place memory at a parent Git root unless the current directory itself is that root or the user is working across that parent repo.
4. Initialize `.codex/session/` if missing by running:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py init --root auto
```

This also adds `.codex/session/` to the project `.gitignore` and creates or updates a project `AGENTS.md` by default. Use `--no-gitignore` only when the user explicitly wants to version memory files. Use `--no-project-agents` only when the project must not be given local Codex startup instructions.

5. At the start of a new session, read only the active files:

- `.codex/session/HANDOFF.md`
- `.codex/session/PROJECT.md`
- `.codex/session/TASK.md` when the worktree is dedicated to a specific branch/task or when parallel task isolation matters
- `.codex/session/ASSETS.md` only when the task depends on user-provided images, screenshots, PDFs, mockups, documents, or other external references that the user's text makes relevant
- `.codex/session/DEBUG_SCREENSHOTS.md` only when the task depends on runtime screenshots, bug/error captures, visual regression checks, or test-run verification images
- `.codex/session/DECISIONS.md` only when present or referenced

6. Verify the handoff against the repo before editing. Run lightweight checks such as `git status --short`, `rg --files`, or targeted file reads.
7. Before every final response that completes or pauses a project task, update `HANDOFF.md`. This is mandatory for project work, not only a slow-session recovery step.
8. Before a long session gets slow, update the active files early and suggest starting a fresh Codex session with this prompt:

```text
Continue this project. First follow AGENTS.md, read .codex/session/HANDOFF.md and PROJECT.md, then start from Next Steps.
```

## File Roles

- `PROJECT.md`: durable project facts, architecture, commands, constraints, and user preferences. Keep stable and short.
- `HANDOFF.md`: the current task state, what changed, what was verified, blockers, and exact next steps. This is the main resume file.
- `TASK.md`: current worktree task contract. Use it to isolate parallel tasks by branch, worktree, owned code paths, design scope, and validation scope.
- `ASSETS.md`: durable index of user-provided design images, screenshots, PDFs, reference files, generated assets, and external artifacts that future sessions may need. Only include assets that the task actually depends on.
- `DEBUG_SCREENSHOTS.md`: active runtime/test/debug screenshot index. Use it for bug reproduction images, error screenshots, verification captures, and temporary TV/device photos that help debugging code.
- `DECISIONS.md`: short decision log with dates, rationale, and consequences. Keep recent and relevant.
- `design-map.json`: structured relationship graph for non-trivial design-led work. Use it to record active/rejected/reference-only nodes, source image paths, parent/derived edges, superseded links, and interaction coverage.
- `design-map.html`: optional but preferred operable design map for visual inspection. Use it to hover/click references and discover missing interaction destinations before implementation.
- `archive/`: old handoffs. Do not read archive files by default; only load them when active files explicitly point there.

## When To Checkpoint

Always checkpoint at the end of a project task before the final response. Also use observed latency and task complexity, not a fixed token number, to checkpoint earlier when any of these happen:

- Tool calls or responses start feeling slow, even if the model still has context capacity.
- The session contains many large file dumps, logs, screenshots, decompiled output, or generated artifacts.
- The user is about to switch windows, pause work, or asks for a summary/continuation prompt.
- A major milestone is complete and the next step is a distinct phase.
- The task has accumulated enough constraints that losing them would cause rework.
- The user explicitly makes an external artifact part of the task, such as a design image, UI reference, screenshot, PDF, mockup, dataset, or other file that future sessions need.

For practical thresholds, start considering a checkpoint around 150k-200k tokens for latency-sensitive projects. If the model and tooling stay fast, it is acceptable to delay to 300k-400k, but never wait for the automatic compaction limit if the user is already feeling slowdown.

## Writing Rules

- Store facts, decisions, file paths, commands, test results, and next actions. Do not store transcript-style chat.
- Store project memory only under that project's `.codex/session/`. Use global Codex files only for reusable policy, skills, and scripts.
- Put "how to use this memory" in the project's `AGENTS.md` so new Codex sessions know which skill to use and which files to read.
- For parallel work, keep one active task contract per worktree in `TASK.md`. If the task changes, update or replace `TASK.md` before editing code.
- Keep active memory small. Target `HANDOFF.md` under 150 lines and `PROJECT.md` under 250 lines.
- Put volatile exploration details in `archive/` or omit them once the durable result is known.
- Never store API keys, tokens, cookies, private credentials, or sensitive personal data.
- Do not assume conversation attachments will be available in a new session. Preserve important artifacts as project files when possible.
- Keep design/UI references in `ASSETS.md`, not in `DEBUG_SCREENSHOTS.md`. Keep runtime/test/debug captures in `DEBUG_SCREENSHOTS.md`, not in `ASSETS.md`, unless a file truly serves both roles and that dual role is explicitly noted.
- When design/UI work has accepted and rejected/generated variants, separate durable design assets by lifecycle. Prefer `.codex/session/assets/active/` for implementation references and `.codex/session/assets/rejected/` for failed, drifted, superseded, or do-not-use references.
- For non-trivial design-led work, keep a design relationship map in the project session directory. Update `design-map.json` and, when useful for visual inspection, `design-map.html` whenever active/rejected references, derivation links, superseded relationships, or interaction coverage changes.
- Mark uncertainty explicitly. Use "Needs verification" instead of pretending a remembered item is true.
- Treat session files as hints, not ground truth. Re-check code, tests, and current git state before making changes.

## Attachment And Asset Continuity

When the user provides an image, screenshot, design reference, PDF, or other attachment:

- First classify the attachment by user intent from the text, not from the file alone.
- Only treat an image as a design or UI reference when the user's words explicitly indicate that role, for example `design image`, `UI`, `screen design`, `prototype`, `reference image`, `build to this image`, `match this style`, `mockup`, or equivalent wording in Chinese or another language.
- If the user only uploads an image without making it part of the task, do not automatically register it in `ASSETS.md`.
- Distinguish common cases:
  - Design/UI reference: explicit design intent plus image.
  - Bug/error screenshot: text indicates an issue, error, layout bug, or asks for diagnosis.
  - Content/media asset: image is a source file, texture, poster, logo, or material to use directly.
  - Unclassified image: image is present but the user did not state why it matters yet.
- For design/UI references and durable source/reference files, record the item in `ASSETS.md`.
- For test-run screenshots, bug/error captures, runtime verification images, and temporary TV/device photos used for debugging, record the item in `DEBUG_SCREENSHOTS.md`.
- If the attachment is available as a local file path outside the project, copy it into a project-local durable location such as `.codex/session/assets/active/`, `.codex/session/assets/rejected/`, or a user-approved project asset folder, then record it in the correct index.
- If the attachment cannot be copied or saved from the current interface, write a concise but useful description in the correct index: asset type, what it shows, what the user explicitly wanted done with it, and any uncertainty.
- In `HANDOFF.md`, mention which design assets from `ASSETS.md` and which runtime/debug captures from `DEBUG_SCREENSHOTS.md` are required for the next session.
- Keep both indexes lean. Store references and summaries, not long OCR or full document text unless needed.

## Design Reference Iteration

- Every design/UI reference should record:
  - Related task
  - UI scope, such as `home-screen/top-bar`, `player-dialog`, or `search/results`
  - Status, such as `active-reference`, `partial-override`, or `superseded`
  - Supersedes or superseded-by relationship when a newer design replaces an older one
- When a design image is rejected because of layout drift, wrong canvas, inconsistent icon language, bad data/state, or a better generated successor, move or record it as `rejected` / `do-not-implement` and keep active implementation references separate.
- When a design set has multiple active references, generated states, rejected attempts, or thread-only anchors, create/update a relationship map:
  - nodes: id, title, status, scope, image path, implementation scope, do-not-implement flag.
  - edges: anchor/reference-input, derived-state, parent-child, superseded-by.
  - interactions: source reference, control, expected behavior, target reference, coverage status, missing reference id.
  - verification: active nodes link to files that exist, rejected nodes are not used in implementation contracts, and missing interactions are explicit.
- When a new design image arrives, do not assume it replaces the entire older design. Use the user's text to decide whether it:
  - Fully replaces the previous design for the same scope
  - Only overrides one part of the UI
  - Is just an alternative to compare
- If the replacement scope is unclear, keep both entries, narrow the new entry's scope as much as possible, and mark the ambiguity with `Needs verification`.

## Parallel Task Isolation

- Prefer one branch per task and one linked Git worktree per branch. This is the cleanest way to prevent memory, assets, and edits from crossing tasks.
- Use Git worktrees for true parallelism. Git's official `worktree` docs say a repository can support multiple working trees, allowing you to check out more than one branch at a time.
- For a narrow-scope task, optionally use `git sparse-checkout set <dir>...` in that dedicated worktree so only the relevant subset of tracked files is present.
- Create or update `TASK.md` at task start with:
  - Task id and short title
  - Branch name
  - Worktree path
  - Status
  - Goal
  - Owned paths
  - Avoid paths
  - Design scope
  - Related assets and debug captures
  - Validation steps
- Treat `TASK.md` as a change guardrail. If the work requires editing outside owned paths, update the task contract first and explain why.
- If two parallel tasks need the same file, do not let both tasks edit it blindly. Split scope more finely, sequence the work, or merge one task before the other continues.
- Use the automation commands:
- Use the automation commands:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py task-open --root auto --task my-task --goal "Describe the task" --apply
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py task-close --root auto --target-worktree <worktree-root> --branch codex/my-task --base main
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py task-finish --root auto --target-worktree <worktree-root> --branch codex/my-task --base main
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py task-finish --root auto --target-worktree <worktree-root> --merge-from codex/my-task --base main --apply
```

- Branch deletion rule: delete the task branch only after it is merged into the base branch and the task worktree is clean. Prefer dry-run first; add `--apply` only when the checks pass.
- `task-finish` is the preferred high-level closeout path. It updates handoff/task status, runs a cleanup summary, checks merge state, archives the task snapshot, and then calls the equivalent of `task-close --apply` when the safety conditions pass.
- With `--merge-from <branch>`, `task-finish --apply` first merges that branch into the base branch from the current base worktree, then archives and closes the task if the post-merge safety checks pass.
- `task-open` can start from only `--task` and `--goal`. In dry-run it now auto-suggests:
  - branch name
  - worktree path
  - owned paths
  - avoid paths
  - design scope
  - module responsibilities
  - validation steps
- Review those suggestions before `--apply`. Override any of them with explicit `--branch`, `--worktree`, `--scope`, `--avoid`, or `--design-scope` flags when needed.
- On `--apply`, the same summary is written into both the new worktree's `TASK.md` and its seeded `HANDOFF.md`.

## Debug Screenshot Lifecycle

- `DEBUG_SCREENSHOTS.md` should contain only active or still-useful debug captures.
- Keep screenshots that preserve current blockers, reproducible errors, important runtime states, or the latest verification pass for an unfinished issue.
- Delete or remove screenshots from the index after the issue is fixed and the image is no longer useful.
- If a resolved issue still needs a short historical note, summarize it in `HANDOFF.md` or `DECISIONS.md` instead of keeping many old screenshots.
- When `DEBUG_SCREENSHOTS.md` grows noisy, rewrite it to the smallest active set rather than appending indefinitely.
- Use lifecycle labels consistently:
  - `active-bug`: keep until the bug is fixed and a newer verification capture exists.
  - `active-verification`: keep only the newest useful one or two screenshots for that area/state.
  - `fixed-awaiting-cleanup`: the issue is fixed; delete the screenshot by the end of the current related task or the next related session.
  - `stale-delete-soon`: delete as soon as practical.
- Prefer replacing older verification screenshots instead of accumulating many near-duplicates.
- Use `cleanup-report` periodically, especially after finishing a bugfix or a verification-heavy session:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-report --root auto
```

- Use `cleanup-apply` carefully. Default behavior is dry-run; add `--apply` only after reviewing the output:
- Use `cleanup-auto` for the conservative automatic path:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-auto --root auto
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-auto --root auto --apply
```

- Use `cleanup-apply` carefully for more targeted deletion. Default behavior is dry-run; add `--apply` only after reviewing the output:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-apply --root auto
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-apply --root auto --include-fixed --apply
```

- Only use orphan-file deletion flags when you are confident the files are no longer needed:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-apply --root auto --include-orphan-session-assets --min-age-days 7
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py cleanup-apply --root auto --include-orphan-debug-artifacts --min-age-days 7
```

## Update Pattern

When updating `HANDOFF.md`, include:

- Current objective in one or two sentences.
- Repository state, branch, dirty files that matter, and any unrelated dirty files to avoid.
- What changed, with important absolute paths when useful.
- Required assets from `ASSETS.md` when the next session needs reference images or files.
- Required runtime/debug captures from `DEBUG_SCREENSHOTS.md` when the next session needs reproduction or verification screenshots.
- Task scope from `TASK.md` when parallel work isolation matters.
- Commands/tests run and their outcomes.
- Known blockers, assumptions, and risks.
- Ordered next steps that a fresh agent can start immediately.

End-of-task checkpoints should be brief. Replace stale bullets instead of appending a running diary.

When `HANDOFF.md` grows too large or the active objective changes, archive it:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py roll --root .
```

Then write a fresh `HANDOFF.md` for the current objective only.

Use the script status check before final responses when practical:

```bash
python C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py status --root auto
```

If it warns that active files are too large, compress or roll before answering.

## Resume Pattern

In a fresh session:

1. Read active session docs first if they exist.
2. Run `git status --short` and inspect only relevant files.
3. Compare the handoff with the actual repo state.
4. State any mismatch briefly and continue from the listed next step.
5. Refresh `HANDOFF.md` before ending or when the context starts to feel heavy again.
