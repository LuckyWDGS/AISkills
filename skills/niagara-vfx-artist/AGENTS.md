# Codex Project Instructions

## Working Directory

- Work in this repository's `skills/niagara-vfx-artist` directory; resolve resources relative to the skill instead of the historical `D:\Skills` checkout.

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
- On UE 5.8+, discover and use Epic MCP tools first, including ProgrammaticToolset for batching. If a capability is missing, inspect official APIs and local UE source, then use a stock `unreal.*` API through Epic Python Remote Execution for that operation. UnrealBridge is retired; do not duplicate an existing official MCP route or use reflection/export-text hacks to bypass editor semantics.

## Local Outputs

- Keep runtime previews, audits, tuning logs, and gap diagnoses under `.codex/session/vfx-delivery/`.
- Do not commit `.codex/session/`, generated previews, local caches, API keys, or one-off experiments unless explicitly promoted.
