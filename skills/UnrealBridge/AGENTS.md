# Codex Project Instructions

## Session Memory

- Use `$codex-session-continuity` for this project.
- Read rules from `C:/Users/QY/.codex/skills/codex-session-continuity/SKILL.md`.
- Use helper script `C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py`.
- Project memory lives only in `D:\UnrealBridge\.codex\session\`.

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

## Unreal Material/VFX Delivery Gate

- For reference-driven Unreal material or Niagara work, do not report completion from compile success alone. A delivery needs an evidence pack in the active handoff: reference source, current UE asset paths, compile/readback report, readable preview screenshots, motion evidence when applicable, visual delta notes against the reference, graph/readability evidence, and reviewer result.
- Self-check is required but never sufficient for non-trivial material/VFX delivery. When multi-agent tools are available, an independent read-only review subagent must inspect the evidence pack and return Pass before the work can be called complete. The review subagent must not edit UE assets, code, or session files. If independent review is unavailable or returns Fail, mark the task unverified/blocked and do not present it as delivered.
- Treat these as hard blockers until fixed or explicitly waived by the user: Chinese comments or parameter `Desc` text read back as mojibake/garbage, visible hard card edges or unintended seams, preview/effect clearly not matching the approved reference, messy node layout/line crossings after the user asked for readable graphs, black/empty/invalid preview captures, compile errors, wrong material domain/blend/shading/output wiring, or missing intended Niagara usage flags.
- Chinese graph comments and artist-facing parameter `Desc` values must be verified by exact UE readback or a readable material-editor screenshot. Terminal encoding artifacts are not proof that UE text is correct.
- Graph organization is a visual requirement, not optional cleanup. Use clear functional zones, non-overlapping comment boxes, stable node ordering, reroute nodes or named intermediate nodes where they reduce wire crossings, and enough Chinese comments for another artist to tune the material without guessing.
- For reference matching, compare the UE preview against the actual accepted frame/image/video direction before delivery. The comparison must explicitly cover silhouette, edge softness, value range, focal point, color temperature, streak/noise density, motion direction/speed when applicable, transparency falloff, and any missing layer. If the comparison shows a major mismatch, continue iterating or mark the task blocked.
- For motion VFX, static screenshots are not enough to prove delivery. Provide a short capture, frame sequence, or explicit frame-by-frame/motion readback. If motion cannot be viewed or captured, record that motion verification is missing and keep the task blocked or limited to static material preview only.
