# Codex Project Instructions

## Session Memory

- Use `$codex-session-continuity` for this project.
- Read rules from `C:/Users/QY/.codex/skills/codex-session-continuity/SKILL.md`.
- Use helper script `C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py`.
- Project memory lives only in `D:\AISkills\SessionPicture\.codex\session\`.

## Startup

- First read `.codex/session/HANDOFF.md`.
- Then read `.codex/session/PROJECT.md`.
- Read `.codex/session/TASK.md` when present. Treat it as the current worktree's task contract.
- Read `.codex/session/ASSETS.md` only if the task depends on screenshots, design images, PDFs, mockups, or external reference files.
- Read `.codex/session/DEBUG_SCREENSHOTS.md` only if the task depends on runtime screenshots, bug/error captures, or visual verification/debugging images.
- Read `.codex/session/DECISIONS.md` when the handoff references decisions or when architecture/context choices matter.
- Verify memory against current files before editing.

## Checkpoint

- Before every final response that completes or pauses project work, update `.codex/session/HANDOFF.md`.
- Do not treat every uploaded image as a design/UI reference. Only register it as design/UI when the user's text explicitly makes it a design reference.
- If user-provided images or reference files matter, save/copy them under the project when possible and register them in `.codex/session/ASSETS.md` with an asset type and explicit user intent.
- Put runtime/test/debug screenshots in `.codex/session/DEBUG_SCREENSHOTS.md`, not in `.codex/session/ASSETS.md`, and prune stale entries regularly.
- Do not read `.codex/session/archive/` unless explicitly asked or referenced by the active handoff.
