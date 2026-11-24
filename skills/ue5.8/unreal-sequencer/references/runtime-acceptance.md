# Sequencer runtime acceptance

These are selectable acceptance procedures, not completed UE tests. Use the
[shared runtime result record](../../unreal-engine-mcp/references/shared-conventions.md#runtime-result-record).
The current builder/sample/legacy-render helpers require explicit UI opt-in;
do not enable that flag for a background task. Use discovered official background
operations where available and mark unsupported runtime checks `not_run` or
`blocked` with the reason. Inspect structure without opening a timeline.

## SEQ.Gameplay.Exit — play, finish, stop, skip and abort

- Record the initiating controller/player, original ViewTarget, input/movement
  state, possessed pawn and every property the sequence owns. Identify the
  sequence player's completion mode and section overrides; Restore State is
  not a substitute for cleanup of gameplay side effects.
- Trigger the actual gameplay entry. Exercise natural finish, explicit Stop,
  Skip/jump-to-end, owner destruction and the feature's abort path separately.
  Test rapid re-entry while already playing, using the agreed restart/ignore rule.
- Expect the agreed camera/input/movement state after each exit, one cleanup
  dispatch and no lingering cinematic pawn, input lock or duplicate player.
  OnFinished and OnStop have different behavior; verify both relevant paths.
- Record start/finish/stop/abort counts, player status/time, runtime ViewTarget
  and restoration values. Editor cut labels are not runtime camera evidence.

## SEQ.Events.Once — director events and scrub behavior

- Give each gameplay event a stable beat/module ID. Play across it normally,
  then test the intended skip, loop and reverse behavior independently.
- Record event timestamps, receiver and counts. Expect the specified count per
  traversal; state-changing rewards/damage/spawns must follow the agreed
  idempotency rule. Bindings must resolve to the intended receiver instance.
- Seeking/evaluating can fire events depending on section/player settings.
  Do not scrub a production sequence with side effects just to collect camera
  samples. Use a controlled candidate or a verified event-suppression route.
  A structural EventTrack or fade channel is not proof of execution.

## SEQ.Bindings.Lifetime — spawnables, possessables and animations

- Spawnables: record spawn sections and counts; observe first visible frame,
  cut boundaries, finish/abort and replay. No stale duplicates should survive
  beyond the intended ownership/completion policy.
- Possessables: confirm actual actor/component references, map availability,
  binding overrides and level-streaming lifetime. Check the original transform,
  animation mode and other controlled properties after exit.
- For skeletal tracks, verify the correct mesh/skeleton, evaluated animation
  time, root motion, blend/Slot interaction and return to gameplay ABP. A valid
  animation asset reference alone does not prove the character played it.

## SEQ.Time.Hierarchy — rational rates and boundary frames

- Record root display rate and tick resolution, each subsection's start offset,
  time scale and local playback range. Preserve rational rates (30000/1001 is
  different from 29.97); convert root time to local time explicitly.
- Sample first, intermediate and last visible frames per shot, each cut boundary
  and relevant transition/animation interval. For end-exclusive ranges use
  `end-1`; a key at `end` may shape interpolation without a live spawnable there.
- Check between keys for cubic overshoot, rotation winding, collision/occlusion
  and subjects leaving frame. Key endpoint matches alone cannot establish these.
  Record roll, focal length, aperture, focus method/distance and actual evaluated
  target bounds/pivot. The plan's look_at/auto-focus are build-time snapshots.

## SEQ.Render.Output — preview versus production output

- Legacy preview capture: retain its completion delegate; require a successful
  callback and the expected count of decoded PNGs of the requested dimensions
  inside a unique run directory. Record token, exact rational rate, range,
  pre-roll, filenames and answered visual question. Old PNGs never count.
- A timeout with no callback means unknown activity. Inspect the existing capture
  before another attempt; do not stop a user's PIE or start overlapping captures.
- Final deliverables through MRQ/MRG need separate discovery of current official
  plugin/API coverage, an explicit queue/job/config, output mapping, warm-up and
  temporal sampling, resolution, color/alpha policy and a completed-job report.
  Validate frame count/rate, cut mapping, image/codec integrity and requested
  quality. `sequence_render.py` does not implement or verify that pipeline.
