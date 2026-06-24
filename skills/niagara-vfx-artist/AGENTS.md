# Codex Project Instructions

## Working Directory

- This skill is now worked on directly from `D:\Skills\skills\niagara-vfx-artist`.
- Treat this directory as the active project root for Niagara VFX tool and workflow iteration.
- The parent repository remains `D:\Skills`, but ordinary session memory for this skill should live here, not in the parent root.

## Session Memory

- Use `$codex-session-continuity` for this project.
- First read `.codex/session/HANDOFF.md`.
- Then read `.codex/session/PROJECT.md`.
- Read `.codex/session/ASSETS.md` when reference images, generated VFX assets, or design anchors matter.
- Read `.codex/session/DEBUG_SCREENSHOTS.md` when runtime previews or visual verification captures matter.
- Read `.codex/session/DECISIONS.md` when architecture or workflow decisions matter.
- Keep session memory under `D:\Skills\skills\niagara-vfx-artist\.codex\session\`.

## Niagara VFX Workflow

- Use this skill's `SKILL.md` as the main workflow contract.
- Use `scripts\vfx_delivery\*` as the implementation and validation tool suite.
- Do not rely on editor UI screenshots as proof. Prefer graph-first Niagara audits, controlled preview captures, explicit gap diagnosis, and `unreal-material-artist` for material audits.
- Before tuning a visual mismatch, classify the likely owner layer: reference, texture, material, Niagara, renderer, integration, preview, performance, or unknown.
- Before creating or changing a VFX implementation from a design image, explicitly tell the user which design/reference image will be used as the active implementation anchor and wait for the user's confirmation before proceeding.
- When confirming a design image, also state the implementation scope inside that image, such as `full effect`, `single layer`, `drag trail only`, `wing root only`, or another precise sub-scope. Do not assume a broad sheet and a single-layer crop are interchangeable.
- If the active anchor changes, treat earlier previews, diffs, tuning notes, and diagnoses as historical only until they are revalidated against the new anchor.
- If the intended active anchor exists only in the thread and has not been cached locally, stop before implementation and mark the task blocked by missing durable anchor cache.
- Do not treat a generated texture as a valid implementation asset until it is both imported into UE and verified as referenced by the live material or renderer route being reviewed.
- When Niagara capability is missing, search official Python / Blueprint docs and local UE source first. If the engine exposes an authoritative editor/runtime route but the current bridge does not, extend UnrealBridge instead of forcing fragile reflection or export-text hacks.

## Checkpoint

- Before final responses that complete or pause project work, update `.codex/session/HANDOFF.md`.
- Keep runtime previews, audits, tuning logs, and gap diagnoses under `.codex/session/vfx-delivery/`.
- Do not commit `.codex/session/`, generated previews, local caches, API keys, or one-off experiments unless explicitly promoted.
