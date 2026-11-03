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

## Workflow

1. **Shot brief first.** Before touching the editor, write the brief from
   [cinematic delivery standards](references/cinematic-delivery-standards.md): purpose, length,
   beats, shot list (camera, framing, lens, move, duration), subjects by actor label, and how the
   sequence is triggered in game. Show it to the user for anything longer than one shot.
2. **Write a shot plan** ([shot plan format](references/shot-plan.md)) and validate it offline:
   `python scripts/sequence_plan_apply.py plan.json`. Fix every error; read every warning.
3. **Build** in the editor: `python scripts/sequence_plan_apply.py plan.json --execute --out <session>`
   (`--replace` to rebuild an existing sequence; it deletes the old asset first).
4. **Lint the result:** `python scripts/sequence_inspect.py /Game/.../LS_Name --out <session>/inspect --strict`
   (camera-cut gaps/overlaps, unbound cuts, unused cameras, empty tracks/sections, missing
   animations, keys outside the range).
5. **Verify with state:** `python scripts/sequence_sample.py /Game/.../LS_Name --apply-report <session>/apply-report.json --out <session>/sample`
   evaluates the sequence at every planned key and checks camera/actor location, pitch/yaw and
   focal length against the plan. Quote the numbers.
6. **Answer visual questions with renders**, never behaviour:
   `python scripts/sequence_render.py /Game/.../LS_Name --frames 30,100 --question "..." --out <session>/render`,
   then look at each image and report the answer (framing, readability, subject in frame).
7. **Hand off:** sequence path, shot table, verification numbers, render answers, open issues,
   and the save state. Nothing is saved unless the user asked (`--save`).

For edits to an existing sequence use the MCP tools directly (inspect first, change only the
named tracks/sections, re-run inspect and sample). Keyframing details, verified tool behaviour
and gaps: [Sequencer MCP toolsets](references/sequencer-mcp-toolsets.md).

## Rules that bite

- Frames in every Sequencer tool are **display-rate frames**; tick resolution is irrelevant.
- `create_camera` / `add_actors` act on the sequence open in Sequencer: `open_sequence` first and
  `close_sequence` when done. `create_camera` also adds camera-cut sections and three camera
  property tracks; reuse them, never add duplicates.
- Channel names: `Location.X/Y/Z`, `Rotation.X` = roll, `.Y` = pitch, `.Z` = yaw; a float
  property section has one channel named `"None"`.
- A section added through MCP has **no length**: make it unbounded or give it a range. Before
  keying a level actor, set every transform channel's default to its current transform, or
  unkeyed rotation/scale snap to 0/1.
- `set_camera_cut_binding` is broken in 5.8.4: bind cuts with editor Python
  (`sequencer_tools.editor.Editor.bind_camera_cuts`).
- The legacy capture renders at 24 fps unless told otherwise and needs pre-roll frames;
  `sequence_render.py` handles both.

## References

| Need | Read |
| --- | --- |
| Tool map, verified behaviour, workarounds, gaps | [Sequencer MCP toolsets](references/sequencer-mcp-toolsets.md) |
| Plan JSON for `sequence_plan_apply.py` | [Shot plan format](references/shot-plan.md) |
| Brief, shot grammar, gameplay trigger, delivery checklist | [Cinematic delivery standards](references/cinematic-delivery-standards.md) |
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
