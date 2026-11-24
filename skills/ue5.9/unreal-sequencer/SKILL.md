---
name: unreal-sequencer
description: Build, inspect and verify Unreal Engine 5.9 Level Sequences through Epic MCP. Use when the task involves cinematics, cutscenes, intro or outro sequences, camera moves and camera cuts, actor or transform animation, fades, event tracks, subsequences or Control Rig tracks, or when checking that a sequence plays, skips and hands control back to gameplay correctly. Requires the sibling unreal-engine-mcp skill.
---

# Unreal Sequencer (UE 5.9)

> **Scope.** This skill targets UE 5.9 only and was verified on **UE 5.9.0
> Preview, CL 60351404**. A later build can rename tools and arguments, so read
> the live schema before each first call. Movie Render Queue output has not
> been accepted on this build; see [Known limits](#known-limits).

Use the sibling [core MCP skill](../unreal-engine-mcp/SKILL.md) for the
client, editor and project identity, tool discovery and official Python.
Follow the [shared conventions](../unreal-engine-mcp/references/shared-conventions.md):
background operation, Chinese module descriptions with stable IDs, scoped
saves and the evidence levels. The user's open timeline and viewport stay as
they are.

## When to use

- Create or change a Level Sequence: bindings, tracks, sections, keys.
- Build a camera move, a camera cut or a fade.
- Wire a sequence into gameplay: triggers, events, skip and restore.
- Check an existing sequence for gaps, unbound cuts or stray keys.

## Workflow

1. **Write the shot brief.** Purpose, duration, beats, subject actors, framing,
   lens and move per shot, and the gameplay trigger when there is one. Use the
   [delivery standards](references/cinematic-delivery-standards.md) and the
   [shot plan format](references/shot-plan.md) for larger plans. Validate a
   plan offline with `python scripts/sequence_plan_apply.py plan.json`.
2. **Inspect.** Read the sequence, bindings, tracks, sections, channels, dirty
   state and the active timeline. Work on a new candidate path. In an existing
   asset change only the requested content, and keep a verified backup before
   a destructive rebuild. A sequence that is currently open is left in place.
3. **Author with native tools** on explicit sequence, track, section and
   channel references ([5.9 Sequencer control](references/ue-5.9-sequencer.md)).
   `scripts/sequence_native_camera.py` creates a tagged empty camera binding
   with Transform, CameraCut and Fade tracks and verifies every Linear curve
   sample without an open timeline. Assign a real camera to that binding
   before playback. For a verified native gap use `PythonScriptingTools` after
   reading its instructions and looking the API up.
4. **Read back.** Rates, ranges, binding membership, channel values and
   evaluated curves. Check the binding inventory after every binding write.
5. **Lint the result.** Camera-cut gaps and overlaps, unbound cuts, unused
   cameras, empty tracks and sections, missing animations, keys outside the
   intended range. Reacquire references after a destructive edit.
6. **Verify the requested outcome** at the matching
   [evidence level](../unreal-engine-mcp/references/shared-conventions.md#evidence-levels):
   authored curves, evaluated object state, inspected images or runtime cases.
   Camera ownership, event firing, skeletal playback, fades and
   Finish/Stop/Skip/Abort cleanup are runtime questions; select cases from
   [runtime acceptance](references/runtime-acceptance.md).
7. **Save and report.** Save only the intended packages. Report the sequence
   path, shots, measured checks, visual findings, the actual save state and
   what was not run.

## Contracts that affect correctness

- **Rates and ranges.** Keep rational display rates: `30000/1001` is not
  `29.97`. Check each API's unit (display frame, tick frame or seconds) and
  whether its end bound is exclusive. Bound every new section explicitly; a
  Fade section can default to unbounded.
- **Channels and keys.** Pass returned channel and key descriptors back
  unchanged. A key handle is a live identity, not an index. A float-property
  channel may be named `None`. Transform `Rotation.X/Y/Z` is roll/pitch/yaw.
  Set every channel default to the current transform before keying part of it.
- **Camera cuts.** Keep the complete camera-cut binding ID, including sequence
  ID and parent resolution data. Root-local parent index 0 and root-resolved
  -1 can name the same root binding, so preserve each returned descriptor
  instead of comparing dictionaries.
- **Control Rig.** Creating a Control Rig track can activate Animation Mode,
  and typed keying and world-space operations can need a focused sequence.
  Read the Control Rig section of the reference before using them.
- **Timeouts.** A timeout has unknown completion. Read the affected state
  before another write.

## Known limits

- Background `AddSpawnableFromClass` returns a zero GUID and a null sequence
  on this build without setting `isError`. Treat it as a failed write and use
  a possessable or the tagged empty binding instead.
- Movie Render Queue: use an independently owned queue, preserve the user's
  active queue and coordinate the executor's PIE lifecycle. Read the
  [render-binding route](references/ue-5.9-mrq-bindings.md) before rendering a
  deferred camera binding. A classic MRQ render of a gameplay sequence has not
  been run on this build.
- A posed offscreen capture from the core skill answers a framing question.
  It does not evaluate the sequence.

## Scripts

Status labels are defined in the
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md#engine-version-and-tool-status).

| Script | Status | Use |
|---|---|---|
| `sequence_native_camera.py` | `5.9` | Create-only camera binding with Transform, CameraCut and Fade tracks, verified sample by sample |
| `sequence_plan_apply.py` (no `--execute`) | `local` | Validate a shot plan offline |
| `sequence_plan_apply.py --execute` | `unported` | Plan builder |
| `sequence_inspect.py` | `unported` | Structure and lint report |
| `sequence_sample.py` | `unported` | Timeline evaluation |
| `sequence_render.py` | `unported` | Preview frame capture |

Run `python -m unittest discover -s scripts -p "test_*.py"` after changing a
helper.

## References

| Need | Read |
|---|---|
| Native owners, background authoring chain, camera helper, events, Control Rig, MRQ ownership | [5.9 Sequencer control](references/ue-5.9-sequencer.md) |
| Rendering a deferred camera binding; queue and callback ownership | [Render bindings](references/ue-5.9-mrq-bindings.md) |
| Runtime cases: exit paths, events, binding lifetime, time hierarchy, render output | [Runtime acceptance](references/runtime-acceptance.md) |
| Brief, shot grammar, evidence, gameplay integration, handoff | [Cinematic delivery standards](references/cinematic-delivery-standards.md) |
| Shot plan JSON format | [Shot plan](references/shot-plan.md) |
| Blueprint triggers and event receivers | [Blueprint delivery standards](../unreal-engine-mcp/references/blueprint-delivery-standards.md) |
| Materials or effects inside a shot | [unreal-material-artist](../unreal-material-artist/SKILL.md), [niagara-vfx-artist](../niagara-vfx-artist/SKILL.md) |
