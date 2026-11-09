---
name: unreal-sequencer
description: Build, inspect, verify and render Unreal Engine 5.8+ Level Sequences (Sequencer) through Epic's built-in MCP Sequencer toolsets - cinematics, cutscenes, camera shots and moves, camera cuts, look-at framing, focal length/focus/aperture animation, actor transform and skeletal animation tracks, fades, event tracks, subsequences and Control Rig keys. Use when the user wants a cinematic, intro/outro, cutscene, trailer shot, camera fly-through, in-game sequence or wants an existing sequence reviewed or fixed. Needs the sibling skill unreal-engine-mcp (shared MCP client).
---

# Unreal Sequencer

Drive Sequencer in a running UE 5.8+ editor through Epic's official MCP toolsets
(`SequencerTools` 140 tools, `SequencerKeyframingTools`, `SequencerControlRigTools`,
`SequencerOutlinerTools`, conditions, custom bindings, FBX import/export) via the shared client
in `unreal-engine-mcp/scripts/ue_mcp`. Stock editor Python fills the verified gaps. Read
[shared conventions](../unreal-engine-mcp/references/shared-conventions.md) for the editor
session, project guard and evidence rules; they apply here too.

Background operation is the default. Explicit-sequence MCP structure, property and
key tools can work without opening Sequencer. The current plan builder and sampler
depend on an open timeline; legacy rendering can open a capture viewport. These helpers
refuse those operations by default. Use `--allow-editor-ui` only when the user has
explicitly requested that UI workflow, never as an automatic fallback. Local plan
validation and background inspection remain available. Run
`pip install -r requirements.txt` for Pillow-based render evidence checks.

## Workflow

1. **Shot brief first.** Before touching the editor, write the brief from
   [cinematic delivery standards](references/cinematic-delivery-standards.md): purpose, length,
   beats, shot list (camera, framing, lens, move, duration), subjects by actor label, and how the
   sequence is triggered in game. Show it to the user for anything longer than one shot.
2. **Write a shot plan** ([shot plan format](references/shot-plan.md)) and validate it offline:
   `python scripts/sequence_plan_apply.py plan.json`. Fix every error; read every warning.
3. **Build** with explicit-sequence MCP operations for a background task. The bundled builder
   is an opt-in UI route: `python scripts/sequence_plan_apply.py plan.json --execute --allow-editor-ui --project <Project> --out <session>`.
   For a background spawnable, use `Editor.add_spawnable_from_class(sequence, class_path)`:
   it validates the MCP binding and fills only the verified active-timeline gap with Epic's public API.
   The compatibility route is limited to the exact audited engine build; it records Epic's
   deprecation warning and refuses an unreviewed build before a fallback write.
   Prefer a new candidate path. Replacing an existing asset requires `--replace --backup-path
   /Game/.../LS_Backup --save`; it duplicates, saves and verifies the backup before rebuilding.
   A currently open sequence cannot be replaced by this helper.
4. **Lint the result:** `python scripts/sequence_inspect.py /Game/.../LS_Name --project <Project> --out <session>/inspect --strict`
   (camera-cut gaps/overlaps, unbound cuts, unused cameras, empty tracks/sections, missing
   animations, keys outside the range).
5. **Verify with state:** for an explicitly requested UI evaluation,
   `python scripts/sequence_sample.py /Game/.../LS_Name --allow-editor-ui --project <Project> --apply-report <session>/apply-report.json --out <session>/sample`.
   It checks camera/actor location, pitch/yaw/roll, focal length, manual focus and aperture
   where planned. It restores its prior idle root timeline on success or failure, preserving
   a user-selected replacement session. Playing or nested sessions refuse evaluation.
   Empty checks are `collected`, not passed. Quote measured values and coverage gaps.
6. **Answer visual questions with renders**, never behaviour:
   for an explicitly requested capture UI workflow,
   `python scripts/sequence_render.py /Game/.../LS_Name --allow-editor-ui --project <Project> --frames 30,100 --question "..." --out <session>/render`,
   then look at each image and report the answer (framing, readability, subject in frame).
7. **Check gameplay integration** with the relevant [runtime cases](references/runtime-acceptance.md).
   Timeline samples do not prove the game's active camera, event firing, skeletal playback,
   fades or Finish/Stop/Skip/Abort cleanup.
8. **Hand off:** sequence path, shot table, verification numbers, render answers, open issues,
   and the save state. Nothing is saved unless the user asked (`--save`).

For edits to an existing sequence use the MCP tools directly (inspect first, change only the
named tracks/sections, re-run inspect and the permitted evaluation route). Keyframing details, verified tool behaviour
and gaps: [Sequencer MCP toolsets](references/sequencer-mcp-toolsets.md).

## Rules that bite

- The audited general Sequencer/keyframing tools use **display-rate frames**. Verify the unit
  of each Control Rig, subsection, import/export or render API separately. Preserve rational
  rates: `"30000/1001"` is NTSC, while `29.97` means exactly `2997/100`.
- `create_camera` / `add_actors` act on the sequence open in Sequencer: `open_sequence` first and
  restore the previous idle timeline when done; use these only in an explicit UI workflow.
  `create_camera` also adds camera-cut sections and three camera
  property tracks; reuse them, never add duplicates.
- `add_spawnable_from_class` also requires the target timeline open in the audited MCP
  implementation, despite taking a sequence argument. A zero GUID plus `sequence: "None"`
  is failure; a later setter returning true cannot validate it. The background helper checks
  the binding inventory before a public-API fallback and verifies the new binding afterwards.
  Its isolated `background_compat.py` currently permits only
  `5.8.4-58902052+++UE5+Release-5.8`. This controls upgrade risk; it does not remove Epic's
  deprecation. Re-audit MCP and public background alternatives after upgrading, then change
  the guard only with source review and a background smoke test. `Editor.calls` preserves
  warnings, errors, build and compatibility results; retain it in the session report.
- Channel names: `Location.X/Y/Z`, `Rotation.X` = roll, `.Y` = pitch, `.Z` = yaw; a float
  property section has one channel named `"None"`.
- Inspect each new section's actual bounded range; defaults differ by section class (Fade
  can be unbounded). Set the intended range rather than assuming zero length. Before
  keying a level actor, set every transform channel's default to its current transform, or
  unkeyed rotation/scale snap to 0/1.
- `set_camera_cut_binding` has a known pre-write GUID TypeError in the audited 5.8.4 build.
  `Editor.bind_camera_cuts` uses official MCP `get_binding_id` plus
  `ObjectTools.set_properties/get_properties` on `cameraBindingId`, with no Remote Python.
  It preserves and verifies the complete ID (`guid`, `sequenceId`, `resolveParentIndex`);
  a matching GUID alone is insufficient. Unknown errors/timeouts stop further writes.
- The legacy capture renders at 24 fps unless told otherwise and needs pre-roll frames;
  `sequence_render.py` handles both. Success requires its completion callback and decodable
  expected-size PNGs in a unique run directory. A timeout is unknown completion; old files
  and file-count growth cannot establish success. This helper is legacy preview capture,
  not a Movie Render Queue/Graph production pipeline.

## References

| Need | Read |
| --- | --- |
| Tool map, verified behaviour, workarounds, gaps | [Sequencer MCP toolsets](references/sequencer-mcp-toolsets.md) |
| Plan JSON for `sequence_plan_apply.py` | [Shot plan format](references/shot-plan.md) |
| Brief, shot grammar, gameplay trigger, delivery checklist | [Cinematic delivery standards](references/cinematic-delivery-standards.md) |
| Gameplay lifecycle, events, bindings, time domains and render acceptance | [Runtime acceptance](references/runtime-acceptance.md) |
| Blueprint side (Level Sequence Actor, events, logging) | `unreal-engine-mcp` [Blueprint delivery standards](../unreal-engine-mcp/references/blueprint-delivery-standards.md) |
| VFX or materials inside a shot | `niagara-vfx-artist`, `unreal-material-artist` |

## Scripts

| Script | Does |
| --- | --- |
| `sequence_plan_apply.py` | validate a shot plan; with `--execute` build the sequence |
| `sequence_inspect.py` | read-only structure report and lint |
| `sequence_sample.py` | evaluate frames, record state, check against the plan |
| `sequence_render.py` | PNG frames for a named visual question |
| `test_sequencer_tools.py` | offline tests (`python -m unittest discover -s scripts -p "test_*.py"`) |
