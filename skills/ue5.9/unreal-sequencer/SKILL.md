---
name: unreal-sequencer
description: Build, inspect and verify Unreal Engine Level Sequences through Epic MCP for cinematics, cutscenes, camera moves, actor animation, fades, events, subsequences and Control Rig. Uses UE 5.9 native background tools and official Python where covered, with conditional UE 5.8 helpers. Requires the sibling unreal-engine-mcp skill.
---

# Unreal Sequencer

Use the sibling [core MCP skill](../unreal-engine-mcp/SKILL.md) for the client,
fresh editor/project identity, tool discovery and official Python execution.
Follow [shared conventions](../unreal-engine-mcp/references/shared-conventions.md),
including Chinese module descriptions, stable module IDs and scoped saves.
Background operation is the default; do not open/focus a timeline or move the
user's viewport as an automation fallback.

## Choose the target engine contract

- **UE 5.9:** read [5.9 Sequencer control](references/ue-5.9-sequencer.md).
  Prefer native tools with explicit sequence/track/section/channel references.
  The create-only `sequence_native_camera.py` helper builds a tagged empty
  camera binding, Transform/CameraCut/Fade tracks and verifies every visible
  Linear curve sample without an open timeline. Its binding must be assigned
  a real camera before playback. Use `PythonScriptingTools` for a verified native gap after
  reading its instructions and looking up the public API. An API's presence
  does not establish background behavior.
- **UE 5.8:** read [the existing tool map](references/sequencer-mcp-toolsets.md)
  and the helper scope below. Its namespaces, object shapes and compatibility
  fallbacks remain conditional on that engine contract.

Do not run a 5.8 high-level builder against 5.9 merely because the shared
transport connects. Describe every called tool and inspect the returned data.

## Build and verify

1. Write the shot brief: purpose, duration, beats, subject actors, framing,
   lens and move per shot, and gameplay trigger when applicable. Use
   [delivery standards](references/cinematic-delivery-standards.md) and the
   [shot plan format](references/shot-plan.md) for larger plans. Offline plan
   validation remains available with `python scripts/sequence_plan_apply.py plan.json`.
2. Inspect the intended sequence, bindings, tracks, sections, channels, dirty
   state and active timeline. Prefer a new candidate path. Modify only the
   requested content in existing assets; retain a verified backup before a
   destructive rebuild. Never replace a currently open sequence.
3. Author through the selected native contract. Read back rates, ranges,
   binding membership, channel values and evaluated curves. A successful
   setter alone does not prove that the target binding or track exists.
4. Check camera-cut gaps/overlaps, unbound cuts, unused cameras, empty
   tracks/sections, missing animations and keys outside the intended range.
   Reacquire references after destructive edits or reconstruction.
5. Verify the requested outcome with the appropriate evidence: authored
   curves, evaluated object state, inspected images, runtime cases or a
   completed render. A 5.9 offscreen scene capture through the core helper
   can answer a framing question, but does not evaluate a sequence by itself.
   Timeline curve data does not prove game camera ownership, event firing,
   skeletal playback, fades or Finish/Stop/Skip/Abort cleanup. Use
   [runtime acceptance](references/runtime-acceptance.md) when those matter.
6. Save only the intended packages when requested or implied by delivery.
   Report the sequence path, shots, measured checks, visual findings, actual
   save state and remaining coverage. Empty checks are `collected`, not passed.

## Contracts that affect correctness

- Preserve rational display rates: `30000/1001` differs from decimal `29.97`.
  Verify each API's display-frame/tick-frame/seconds unit and inclusive versus
  exclusive bounds. Explicitly bound new sections; Fade defaults can be unbounded.
- Pass complete numeric channel and key descriptors back unchanged. Handles
  are live identities, not durable indices. Float-property channels may be
  named `None`. Transform `Rotation.X/Y/Z` convention is roll/pitch/yaw; set
  every channel default to the current transform before partially keying it.
- Background `AddSpawnableFromClass` still returned a zero GUID and null
  sequence in the tested 5.9 build. Verify the binding inventory before
  adding dependent tracks. Do not open UI as an automatic retry. The old
  `background_compat.py` fallback remains limited to its audited 5.8.4 build;
  this test does not authorize widening that guard.
- Preserve the complete camera-cut binding ID, including sequence ID and
  parent resolution data. The 5.9 native camera helper exercised
  `SetCameraCutBinding` and root binding-tag lookup; root-local parent index
  0 and root-resolved -1 can represent the same root binding. Preserve each
  returned descriptor rather than rewriting IDs or comparing dictionaries.
  The 5.8 GUID workaround remains in the old tool map.
- Control Rig track creation can activate Animation Mode; typed keying and
  world-space operations can require a focused sequence. Read the 5.9
  reference before treating an explicit-sequence API as background-safe.
- For MRQ, use an independently owned queue when available, preserve the
  active queue, and coordinate the executor's PIE lifecycle. The classic
  pipeline can reuse or create a sequence actor; do not assume gameplay
  binding overrides survive its setup. Read the
  [5.9 render-binding route](references/ue-5.9-mrq-bindings.md) before rendering
  a deferred camera binding.
- A timeout has unknown completion. Read affected state before retrying a
  write; stop when its outcome cannot be determined.

## Conditional 5.8 helpers

These helpers retain their 5.8 contracts. Their presence is not 5.9 coverage.
Read the [5.8 tool reference](references/sequencer-mcp-toolsets.md) before use.

| Helper | Scope |
|---|---|
| `sequence_inspect.py` | Read-only structure and lint report; validate its tool contract on the target |
| `sequence_plan_apply.py --execute` | Builder depends on an open timeline; `--allow-editor-ui` only for a user-requested UI workflow |
| `sequence_sample.py` | UI evaluation; refuses playing/nested sessions and restores the prior idle root timeline |
| `sequence_render.py` | Legacy preview capture; UI opt-in, explicit frame rate/pre-roll, completion callback and expected-size PNGs required |

The legacy builder's replacement mode requires `--replace --backup-path
/Game/.../LS_Backup --save`; it saves and verifies the backup first. Existing
UI gates must remain. Legacy preview capture is separate from Movie Render
Queue/Graph production acceptance. Use a unique run directory; old files or
file-count growth cannot prove completion. Render-image checks use Pillow
from `requirements.txt`.

For Blueprint triggers and event receivers use the core
[Blueprint standards](../unreal-engine-mcp/references/blueprint-delivery-standards.md).
Use the sibling material or Niagara skill for effects inside a shot. Run
`python -m unittest discover -s scripts -p "test_*.py"` for helper changes;
offline tests and 5.9 editor checks do not establish 5.8 editor regression.
