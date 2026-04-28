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
- `ASSETS.md`: durable index of user-provided design images, screenshots, PDFs, reference files, generated assets, and external artifacts that future sessions may need. Only include assets that the task actually depends on.
- `DEBUG_SCREENSHOTS.md`: active runtime/test/debug screenshot index. Use it for bug reproduction images, error screenshots, verification captures, and temporary TV/device photos that help debugging code.
- `DECISIONS.md`: short decision log with dates, rationale, and consequences. Keep recent and relevant.
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
- Keep active memory small. Target `HANDOFF.md` under 150 lines and `PROJECT.md` under 250 lines.
- Put volatile exploration details in `archive/` or omit them once the durable result is known.
- Never store API keys, tokens, cookies, private credentials, or sensitive personal data.
- Do not assume conversation attachments will be available in a new session. Preserve important artifacts as project files when possible.
- Keep design/UI references in `ASSETS.md`, not in `DEBUG_SCREENSHOTS.md`. Keep runtime/test/debug captures in `DEBUG_SCREENSHOTS.md`, not in `ASSETS.md`, unless a file truly serves both roles and that dual role is explicitly noted.
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
- If the attachment is available as a local file path outside the project, copy it into a project-local durable location such as `.codex/session/assets/` or a user-approved project asset folder, then record it in the correct index.
- If the attachment cannot be copied or saved from the current interface, write a concise but useful description in the correct index: asset type, what it shows, what the user explicitly wanted done with it, and any uncertainty.
- In `HANDOFF.md`, mention which design assets from `ASSETS.md` and which runtime/debug captures from `DEBUG_SCREENSHOTS.md` are required for the next session.
- Keep both indexes lean. Store references and summaries, not long OCR or full document text unless needed.

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

## Update Pattern

When updating `HANDOFF.md`, include:

- Current objective in one or two sentences.
- Repository state, branch, dirty files that matter, and any unrelated dirty files to avoid.
- What changed, with important absolute paths when useful.
- Required assets from `ASSETS.md` when the next session needs reference images or files.
- Required runtime/debug captures from `DEBUG_SCREENSHOTS.md` when the next session needs reproduction or verification screenshots.
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
