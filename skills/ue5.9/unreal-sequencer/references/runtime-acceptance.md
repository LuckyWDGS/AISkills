# Sequencer runtime acceptance

The case definitions below are selectable acceptance procedures. Only explicitly
labeled fixture observations report completed tests. Use the
[shared runtime result record](../../unreal-engine-mcp/references/shared-conventions.md#runtime-result-record).
The current builder/sample/legacy-render helpers require explicit UI opt-in;
do not enable that flag for a background task. Use discovered official background
operations where available and mark unsupported runtime checks `not_run` or
`blocked` with the reason. Inspect structure without opening a timeline.

## UE 5.9 observation routes

These routes were discovered on 5.9.0 Preview / CL 60351404. `ListWorlds` and
`ListViews` were exercised as read-only PIE snapshots; the capture/recording
schemas and Python symbols below were discovered, not executed as part of
that observation pass. Refresh their schemas on the target editor.

Use `SceneCaptureToolset.ListWorlds({})`, select the intended `worldType`,
`mapPath` and `pIEInstance`, and pass its complete `world` reference to
`ListViews({"world": world_ref})`. `bCanCapture` describes prerequisites, not
an already captured image. Inspect `source=PlayerCamera` and its `camera`
location, rotation and FOV. A player view matching an actor camera is merged
with that entry; `sourceActor` can be the camera actor or pawn, rather than
the player controller. Record the actual controller/ViewTarget separately.

The reflected Python read route for the active game world is:

```python
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pc = unreal.GameplayStatics.get_player_controller(world, 0)
pawn = pc.get_controlled_pawn()
view_target = pc.get_view_target()
move_ignored = pc.is_move_input_ignored()
look_ignored = pc.is_look_input_ignored()
pcm = pc.player_camera_manager
camera_location = pcm.get_camera_location()
camera_rotation = pcm.get_camera_rotation()
fov = pcm.get_fov_angle()
world_seconds = unreal.GameplayStatics.get_time_seconds(world)
```

Refuse absent or foreign worlds/controllers rather than substituting editor
objects. `get_controlled_pawn()` is the reflected controller name on this build;
`get_pawn()` was not exposed. For multi-client PIE, identify the world and local
player explicitly. Record full runtime object paths and reacquire them after
each PIE restart. Input flags describe controller state; actual movement and
control behavior need their own observations.

Find the intended runtime `LevelSequenceActor`, then read `sequence_player`:
`is_playing()`, `is_paused()`, `get_current_time()` and
`get_bound_objects(binding_id)`. The returned `QualifiedTime` contains
`time.frame_number.value`, `time.sub_frame` and `rate.numerator/denominator`.
Seconds are `(frame + sub_frame) * denominator / numerator`; do not assume its
rate equals the asset's display rate. Record the runtime owner/player, bound
objects, ViewTarget and restored pawn movement mode together.

For the displayed image, discover and call
`SceneCaptureToolset.CaptureGameViewport({"world": world_ref,
"maxResolution": 1280})`. It captures the actual Game/PIE viewport with UMG,
screen fades and Slate overlays. In PIE, a failed window redraw can fall back
to scene-only output with a warning; that fallback does not establish fade/HUD
behavior. Inspect warnings and decode the returned opaque sRGB8 PNG.
`requestFrameNumber` / `worldTimeSeconds` describe request/readback timing,
not the originating GPU frame or an exact sequence frame. No viewport focus
or camera movement is required. A pose-based offscreen `Capture` cannot prove
a screen fade or HUD behavior.

`PlayerCameraManager.fade_amount` is not reflected on this build: the installed
`FadeAmount` and `bEnableFading` fields lack UPROPERTY. Do not invent a getter
or treat a Fade curve sample as the displayed result. Prepare observation
before triggering a brief Intro; schema discovery or PIE warm-up may outlast
its initial fade. A later clear image cannot prove that earlier fade.

When a continuous record is needed, the discovered native route is:

```json
{"options":{"source":"GameViewport","world":{"refPath":"<PIE world>"},
"maxResolution":1280,"frameRate":30,"maxDurationSeconds":6}}
```

Pass that to `SceneCaptureToolset.StartViewportRecording`, retaining the returned
`recordingId`. Check `ListViewportRecordings` before starting: this build permits
one active recording. Finish only the owned ID with
`StopViewportRecording({"recordingId": id})`; it completes after file finalization.
An automatic stop can report `bActive=false` while `bFinalizing=true`.
Require a finalized result, inspect warnings, decode the MP4 and record
dimensions, duration, frameCount, droppedFrameCount and achievedFrameRate.
The returned `filesystemPath` is local; older recordings may be removed by the
session disk budget. Preserve an accepted recording at its intended output
location. Viewport video is runtime evidence, separate from MRQ output.

Register any required counters before the tested action. Reflected delegates
include `MovieSceneSequencePlayer.on_finished`, `.on_stop` and
`LevelSequencePlayer.on_camera_cut`. Retain callbacks in a persistent Python
module when using separate official `execute_python` calls. A state snapshot
cannot reconstruct previous event counts. Observe the actual gameplay owner
or its test counters for entry/exit reason and cleanup idempotency; do not
evaluate a side-effecting sequence just to sample its camera.

## SEQ.Gameplay.Exit — play, finish, stop, skip and abort

- Record the initiating controller/player, original ViewTarget, input/movement
  state, possessed pawn and every property the sequence owns. Identify the
  sequence player's completion mode and section overrides; Restore State is
  not a substitute for cleanup of gameplay side effects.
- Trigger the actual gameplay entry. Exercise natural finish, explicit Stop,
  Skip/jump-to-end and the feature's abort path separately. Test rapid re-entry
  while already playing, using the agreed restart/ignore rule.
- For these gameplay exits, expect the agreed camera/input/movement state, one
  cleanup dispatch and no lingering cinematic pawn, input lock or duplicate
  player. OnFinished and OnStop have different behavior; verify both relevant
  paths. Restore sequenced properties only while the owned player's playback
  state is usable; make repeated Finish/Stop/Skip cleanup idempotent.
- Test owner destruction, OpenLevel/world teardown, StopPIE and Standalone or
  packaged process exit as separate lifetime cases. Record which actor owns
  the player and which actor tears it down. Restoration needed for continued
  gameplay must occur before that teardown; EndPlay order across actors is
  not a usable guarantee. A clean PIE stop cannot substitute for package exit.
- Record start/finish/stop/abort counts, player status/time, runtime ViewTarget
  and restoration values. For shutdown, record exit status and new log/crash
  evidence instead of requiring a ViewTarget in a destroyed world. Editor cut
  labels are not runtime camera evidence.

### UE 5.9 teardown observation

On 5.9.0 Preview / CL 60351404, the StarHop fixture's initial packaged exit hit
an `IsValid` shared-pointer assertion along
`BP_StarHopPlayer.ReceiveEndPlay → IMovieScenePlayer::RestorePreAnimatedState`.
The installed `ALevelSequenceActor::EndPlay` calls `Stop()` and then `TearDown()`.
A separate actor's EndPlay can therefore see a valid sequence-player UObject
whose internal evaluation state has already been torn down.
`IsValid(UObject)` alone does not establish that Stop/RestoreState is still
safe to invoke.

The fixture fix removed only Stop and RestoreState from the player's
`EventGraph/self.ReceiveEndPlay`. It retains removal of its own sequence
delegates, input mapping context and HUD. Normal Finish/Stop/Skip paths still
restore through the idempotent gameplay routine while the player is usable.
This is an ownership/order fix, not a prohibition on sequence cleanup calls:
an owner that controls teardown must still stop and release its player at
the appropriate point in its own lifecycle.

The edit preserved the other eight Blueprint entries' canonical DSL,
including positions. Compile, scoped save and clean-state readback passed;
13 directed PIE lifecycle assertions passed after the change, including
natural finish, Skip, Stop, restart during Intro, paused restart and StopPIE
both during Intro and after gameplay resumed. The recorded log interval had
no new runtime error. After rebuilding, the Development package naturally
returned 0 during Intro (1 second), after natural completion (12 seconds), and
through the root launcher (5 seconds). These process checks are separate from
PIE OpenLevel/restart and full input playthrough; those packaged gameplay cases
were not exercised. One separate CSV/screenshot instrumented run returned
777003 after normal game-log shutdown; the build's crash-reporting thread
maps that code to its own exception. Preserve this failure and the
[core audit's limits](../../unreal-engine-mcp/references/ue-5.9-preview-audit.md)
instead of claiming every shutdown path passed.

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
  For deferred cameras, read the [5.9 MRQ binding route](ue-5.9-mrq-bindings.md)
  before dispatch; gameplay binding overrides alone do not establish render
  world resolution.
