# Sequencer in UE 5.9 Preview

Live checked on 5.9.0 Preview, CL 60351404. This page records background
asset authoring, API discovery and the separately identified runtime checks
in an isolated test project. The camera helper's checks do not open a timeline
or evaluate a game world; the 2026-11-16 Trigger-event pass adds the runtime
evidence below. Render acceptance still requires its own evidence.

The second pass added read-only rig hierarchy, native reference keys, four
Sequence Validator rules, and official Python MRQ queue / MRG topology reads.
Read the shared [audio / media / rig / MRQ reference](../../unreal-engine-mcp/references/ue-5.9-audio-media-tools.md)
and [validator boundaries](../../unreal-engine-mcp/references/ue-5.9-dataflow-data-tools.md)
for those operations. This pass did not validate rig keying or rendering.

## Discover the new owners

The 5.8 `SequencerTools` / keyframing namespaces are not the 5.9 API contract.
Discover these live toolsets and describe each called tool:

| Task | 5.9 owner and useful tools |
|---|---|
| Create an asset, inspect the active timeline | `LevelSequenceEditorBlueprintLibrary.CreateLevelSequence`, `GetCurrentLevelSequence` |
| Rates, ranges, tracks and bindings on an explicit sequence | `MovieSceneSequenceExtensions` |
| Sections on an explicit track | `MovieSceneTrackExtensions` |
| Numeric channel/key identity, key values and curve evaluation | `MovieSceneSectionExtensions` |
| Binding tracks and names | `MovieSceneBindingExtensions` |
| Tagged deferred camera binding | `MovieSceneSequenceExtensions.AddEmptyBinding`, `MovieSceneBindingTagExtensions.TagBinding`, `MovieSceneSequenceExtensions.FindBindingsByTag` |
| Camera-cut binding | `MovieSceneSectionExtensions.SetCameraCutBinding` (authored and read back in the camera pass) |
| Event sections and Director endpoints | `MovieSceneEventTrackExtensions`, `AnimationAssistantToolset.SequencerDirectorToolset`; simple bound Trigger endpoints authored, compiled and exercised below |
| Section time mapping and reusable template binding | `MovieSceneTimeWarpExtensions`, `TemplateSequenceEditorSubsystem`; schema/source review only |
| Active timeline, playback and UI | `LevelSequenceEditorSubsystem`; many methods still require an open Sequencer |
| Control Rig | Discover `ControlRigSequencerEditorLibrary` and `ControlRigTools`; presence does not validate a particular rig operation |

Use the sibling MCP client's plural discovery support. Native names use PascalCase
and arguments use names such as `sequence`, `startFrame`, `trackType` and `inTime`.
Do not mechanically capitalize old arguments or pass an old helper's schema.

## Verified background chain

The following native MCP operations succeeded without an open timeline:

1. `CreateLevelSequence(packagePath, assetName)` created a candidate at a new
   path; collision behavior was not tested. Asset metadata stored a Chinese
   description and stable module ID through `AssetToolset.UpdateMetadataTags`.
2. `SetDisplayRate` and `GetDisplayRate` round-tripped `30000/1001` exactly.
   `SetPlaybackRange(startFrame=0, endFrame=120)` read back an exclusive end of 120.
3. `AddTrack` created a `MovieSceneFadeTrack`, then `AddSection` created a section
   owned by that track. `SetRange` explicitly bounded it to `[0,120)`.
4. `GetNumericChannels` returned the float channel named `None` and its complete
   identity: section reference, channel type, physical index and name.
5. `AddFloatKey` authored linear keys at display frames 0→0 and 60→1.
   `GetKeys` returned two live key identities; `GetFloatKeyValue` read 0 and 1.
   `EvaluateChannelKeys` sampled frames 0 through 60; frame 30 evaluated to 0.5.
6. `GetCurrentLevelSequence` was null before and after. `AssetToolset.SaveAsset`
   saved only the candidate, then `IsDirty` returned false.

Pass returned numeric channel/key descriptors back unchanged. A key handle is a
live opaque identity, not a stable index. Reacquire descriptors after destructive
edits, reloading or restarting. `GetKeys` includes keys outside the section range;
range checks remain necessary. `AddFloatKey.inTime` defaults to display-rate
frames; use the discovered `timeUnit` when tick-resolution frames are intended.

Curve evaluation proves authored curve data. It does not prove runtime fades,
the active game camera, spawned actors or cleanup after Stop/Skip/Abort.

## Native camera helper: no open timeline required

Use `scripts/sequence_native_camera.py` for a **new** camera sequence. It does
not replace existing assets, create a world camera, change lens/focus settings,
open a timeline or evaluate a world. It discovers all required tools before
creation, checks a freshly initialized 5.9 identity and absolute project guard,
and refuses active/unknown PIE or an already open timeline.

Default invocation validates a JSON plan offline:

```powershell
python scripts/sequence_native_camera.py work/intro-plan.json --out work/intro-dry-run.json
```

After setting the intended absolute `UE_MCP_PROJECT`, isolated
`UE_MCP_CACHE_DIR` and `UNREAL_MCP_URL`, add `--execute --save`. The output
includes identity, native calls, created references, save state and partial
errors. A failed/uncertain write is never replayed automatically.
`--state-dir` can select the isolated cache/session directory; when neither
it nor `UE_MCP_CACHE_DIR` is set, the helper uses `.ue-mcp-native-camera`
beside its output report. It refreshes schemas after fresh initialization.

```json
{
  "sequence": "/Game/Demo/Cinematics/LS_Intro",
  "module_id": "Demo.Intro.v1",
  "description_zh": "开场镜头；运行前绑定真实相机，退出恢复玩法状态。",
  "binding_name": "IntroCamera",
  "binding_tag": "Demo.IntroCamera",
  "display_rate": [30, 1],
  "playback": [0, 120],
  "camera_keys": [
    {"frame": 0, "location": [-650, 1800, 650], "look_at": [1000, 0, 250]},
    {"frame": 119, "location": [0, 1100, 340], "look_at": [200, 0, 160]}
  ],
  "fade_keys": [
    {"frame": 0, "value": 1},
    {"frame": 15, "value": 0},
    {"frame": 119, "value": 0}
  ]
}
```

The helper writes complete transform defaults (including Scale and Weight),
six Linear transform curves, a full-range camera cut, optional Fade, binding
tag, Chinese metadata and RestoreState on every section. `look_at` computes
the authored Euler rotation from each pose; it is not a live tracking
constraint. Yaw is unwrapped along the shortest interval between poses.
Ranges are half-open and poses include both the first and last visible frame.

`AddEmptyBinding` is the verified alternative to the failed background
spawnable call. Reject a zero GUID or null/foreign sequence before adding
dependent tracks. The empty possessable intentionally resolves to no actor
until the playback owner binds it. `SetCameraCutBinding` accepts the returned
binding proxy. For readback, discover the cut's camera-binding property via
ObjectToolset, then compare the complete resulting binding identity.

The root ID returned by `GetBindingID` used `sequenceId=0,
resolveParentIndex=0`; `FindBindingsByTag` returned the same nonzero GUID and
sequence ID with `resolveParentIndex=-1`. These are equivalent at the root.
`same_root_binding()` recognizes only this narrow equivalence; it rejects
nested IDs and preserves all returned fields passed to subsequent APIs.

The StarHop Intro and a separate native-camera contract fixture were saved
clean. Each has one tagged binding, 18 transform keys, three Fade keys,
120-frame Transform/CameraCut/Fade sections and RestoreState. Readback checked
all 720 transform and 120 Fade samples against the piecewise Linear plan,
including between-key values. The active timeline stayed null. This is
structure/curve/save coverage, separate from the demo's gameplay acceptance.

## Runtime camera ownership

Live symbol discovery confirmed these public APIs:

```python
player, actor = unreal.LevelSequencePlayer.create_level_sequence_player(
    world_context_object, sequence, playback_settings)
actor.set_binding_by_tag("Demo.IntroCamera", [camera_actor], False)
ids = actor.find_named_bindings("Demo.IntroCamera")
bound_objects = player.get_bound_objects(ids[0])
player.set_completion_mode_override(
    unreal.MovieSceneCompletionModeOverride.FORCE_RESTORE_STATE)
```

Look up their current symbols before use. Create the player in the actual
gameplay world, retain player and actor references, bind the real camera and
verify the bound objects before Play. Configure completion override before
Play. `LevelSequenceActor.set_binding_by_tag` affects that actor's playback
binding overrides; it does not rewrite the sequence asset or another player.

For a Blueprint handler on a function graph, the 5.9 DSL's `|CreateDelegate`
with `:!event FunctionName` wraps the function; `(delegate EventName)` only
references a same-graph custom event. Delegate verbs accept the external
target through the ordinary `:self` pin, for example:

```lisp
(add `MovieSceneSequencePlayer.OnFinished`
  (`|CreateDelegate` :!event `FinishIntro`) :self (`self.IntroPlayer`))
```

This syntax is supported by installed DSL source/documentation; compile and
inspect the actual graph on the target asset before treating the integration
as validated. Removal uses the same dispatcher, player and handler identity.

OnFinished is the natural-completion path; an explicit Stop does not fire it.
Route natural finish, OnStop, Skip and gameplay abort through an idempotent
routine while the owned player's playback state is usable. RestoreState
handles sequenced properties; restore the original ViewTarget, input/movement
state and other gameplay side effects explicitly. `go_to_end_and_stop`
respects the sections' When Finished policy.

Treat owner EndPlay and world/process teardown separately. On this build,
`ALevelSequenceActor::EndPlay` stops and then tears down its player; another
actor's EndPlay must not assume the same player's internal state survives
because `IsValid(UObject)` is true. In StarHop, the player EndPlay now removes
only its own delegates, input mapping and HUD; normal gameplay exits keep
their restoration. The scope-only change compiled/saved and passed 13 PIE
lifecycle assertions. The rebuilt Development package subsequently returned 0
for exit during Intro (1 second), after natural completion (12 seconds) and
through the root launcher (5 seconds). At that stage, packaged full gameplay/
restart was not exercised; the 2026-11-16 follow-up is recorded below.
A separate CSV/screenshot instrumented run returned 777003 after
clean game-log shutdown; keep that Preview limitation in the
[core audit](../../unreal-engine-mcp/references/ue-5.9-preview-audit.md).
Read the [teardown observation](runtime-acceptance.md#ue-59-teardown-observation)
for the crash, ownership boundary and independent shutdown cases. This does
not forbid an owner from stopping/restoring its player before tearing it down.

## Bound Trigger events: title and audio cues

The 2026-11-16 StarHop pass authored and compiled two Director endpoints with
a typed player input, each calling a parameterless gameplay handler, on a
player-bound Trigger track, then exercised natural playback
and an early Enter skip in PIE. These are separate results from the camera
helper's curve checks and the earlier schema-only event review.

### Author a typed binding and endpoint

1. The player binding was created with official Python
   `MovieSceneSequenceExtensions.add_possessable(sequence, temporary_player)`.
   Verify its possessed-object class is the intended generated player class;
   the camera helper's untyped empty binding does not establish this contract.
   Remove only the authoring actor in `finally` and compare the level actor
   set before/after. This pass retained 122 actors with no temporary player.
2. Reacquire the binding through native `GetBindings` and match its possessed
   class before tagging it `StarHop.IntroPlayer`. Do not serialize a reflected
   GUID with `str(binding.binding_id)`: this build produced a Struct debug
   representation, and `TagBinding` rejected it. Reuse the existing nonzero
   native proxy; the failed tag call does not justify creating another binding.
3. Add `MovieSceneEventTrack` to that binding with
   `MovieSceneBindingExtensions.AddTrack`, then
   `MovieSceneEventTrackExtensions.AddEventTriggerSection`. Bound the section
   to the sequence's display-frame range, here `[0,120)` at 30 fps. Discover
   the **event track's** property schema, then set its
   `bFireEventsWhenForwards=true` and `bFireEventsWhenBackwards=false`;
   these direction properties belong to the track, not the section.
4. Call `SequencerDirectorToolset.AddEventKey` with the explicit sequence,
   Trigger section, reflected function name, display-rate frame and
   `bCallInEditor=false`. The successful completion used the intended player
   Blueprint's CDO as the authoring `boundObject`: `OnIntroTitleCue` at frame 6
   and `OnIntroAudioCue` at frame 45. The resulting Director graph has a typed
   player input and calls the handler on that input. A parameter named
   `Default__BP_StarHopPlayer_C` is not a reason to call the CDO at runtime;
   runtime binding supplies the live player.
5. Obtain the Director Blueprint reference through `GetOrCreateDirectorBlueprint`,
   then read that asset with `BlueprintDslToolset.Read`. Verify both
   typed endpoint calls, compile the Director separately with warnings as
   errors, and save the intended sequence. This pass completed those steps;
   successful key creation alone would not establish a working event.

### Bind the live player and gate side effects

On the newly created playback actor, bind both the camera and the current
gameplay player before `Play`. The exercised player route is:

```lisp
(`LevelSequenceActor.SetBindingByTag` sequenceActor "StarHop.IntroPlayer"
  (`|MakeArray` self :!type "Actor Object Reference") false)
```

The tag belongs to the typed possessable in the sequence; the override belongs
to this `LevelSequenceActor`. Recreate it for each new playback owner. Retain
the player/actor references and configure completion and delegates before Play.

Both handlers require `Phase == Intro` and an individual `not Fired` flag.
Set that flag before incrementing its counter or applying the side effect.
The title handler updates HUD text; the audio handler invokes `PlaySound2D`
using the current master volume. Reset flags and counters only when starting
a new intro. Direction flags and `bCallInEditor=false` are authoring settings;
the phase/once guards also protect callbacks arriving after a gameplay exit.

`FinishIntro` first sets its restoration guard, removes its OnFinished/OnStop
delegates, and then stops/restores the still-owned player and restores gameplay.
Removing delegates before Stop prevents re-entry through OnStop. Keep the
earlier EndPlay fix: teardown removes this owner's delegates, input mapping
and widgets without issuing another Stop/RestoreState. An object passing
`IsValid` can already have torn-down MovieScene internals. This cue integration
retained that boundary; it does not make EndPlay a safe second restore path.

### Runtime evidence and limits

| Case | Observed result |
|---|---|
| Natural completion snapshot | Playing phase, title counter 1, audio counter 1, game unpaused |
| Before early skip | Intro phase, title 1, audio 0, movement disabled |
| Real Enter input through `InputToolset.ApplyInput`, then 4.5 seconds of waiting | Playing phase, title 1, audio still 0, game unpaused, Walking movement |
| Repeated FinishIntro and both cue handlers after skip | Snapshot unchanged; no late or duplicate side effects |

Assert the pre-skip phase and counters, rather than assuming a fixed sleep
always lands between keys. Here the Enter test used a 0.45-second initial
wait and observed the required window; the later wait exceeded the four-second
sequence duration. A direct call to FinishIntro alone would not validate the
Enter input route. The three early-skip assertions passed; the natural-play
counter values were collected in a separate post-completion snapshot.

These counters verify handler execution and suppression, not audio audibility
or a rendered title. Reverse playback, looping, editor scrubbing, Repeater
events, payload arguments and MRQ output were not covered by this pass.
The subsequent Windows Development package also passed natural cue-count
checks during complete mapped-input gameplay, menu restart and save/load
travel. A separate one-second intentional exit retained Intro-phase samples,
executed EndPlay and exited with code 0 without a runtime error or ensure.
Keep that narrow teardown case separate from completed gameplay and from the
PIE early-skip evidence; a timer-driven exit is not a tested menu button.
`AddEventKey` still expects a Trigger section, uses reflected UFUNCTION names,
and converts display frames to tick resolution. It supplies no payload values:
target arguments default-construct and produce a warning. For explicit
arguments, dynamic resolvers or conditions, discover the Director/Blueprint
route, author a real body, compile and add a separate runtime test.

## TimeWarp and TemplateSequence: discovered routes

The 2026-11-15 schema/source review found the routes below. They were not
executed in the camera or Trigger-event passes.

- **TimeWarp:** discover the section's supported time-warp contract before
  `SetSectionPlayRate` or `SetCustomTimeWarp`. Sections without a time warp reject
  the operation. A rate of 0 is represented as FixedTime; changing fixed/custom
  mode replaces the previous implementation. Custom curves appear as PlayRate
  or TimeWarp channels: PlayRate values are multipliers, while TimeWarp values
  are tick-resolution frames against unwarped time from the section start.
  Reacquire channel descriptors after switching mode. Read back type, class,
  channels and sampled time mapping, then validate playback separately; a
  numerically valid curve alone does not prove the resulting motion. Installed
  setters do not require an open timeline, but background execution remains
  untested. `GetTimeWarpClasses` can load unloaded Blueprint classes.
- **TemplateSequence:** `TemplateSequenceEditorSubsystem.GetBoundActorClass` /
  `SetBoundActorClass` provide explicit-asset rebinding without requiring an
  open Sequencer in the installed implementation. The setter replaces the root
  spawnable and moves its tracks/child bindings. Components resolve by name;
  missing components on the new class stop binding. CameraAnimationSequence
  accepts camera classes only, and multiple spawnables are rejected as an
  ambiguous root. On a candidate, require a valid nonzero returned binding,
  correct bound class, preserved keys/tracks, resolved components and actual
  playback for acceptance; save only the intended candidate. This route does not establish
  that generic background LevelSequence spawnable creation now works.

## Control Rig: explicit sequence does not imply background operation

The live official `SequencerControlRigSkill` and installed implementation agree:
`FindOrCreateControlRigTrackFromReference` can activate Animation Mode. Its
creation path resolves the bound skeletal mesh through a shared Sequencer
when one exists, initializes/evaluates the rig, and activates ControlRig edit
mode outside a commandlet. Do not call it as a UI-free fallback.

The official contract also requires a focused sequence for `GetLocal*`, for
setters with `bSetKey=true`, and for world-transform setters and space tools.
Selection, mirror, zero, tween and blend operate on Animation Mode/current
selection. Async variants defer work across editor ticks; they do not remove
these focus/selection requirements or make cancellation rollback an applied edit.

Discover rigs with `MakeControlRigReference`, inspect the exact control types,
and distinguish hierarchy reads, typed value writes, key authoring and an
evaluated skeletal pose. Layered tracks and animation import/bake require
Backwards Solve; FK Control Rig supplies it. This pass only read hierarchy
and discovered APIs; no typed key, solve or playback result is claimed.

## MRQ: own the render queue without replacing the user's queue

Live symbol lookup confirmed an API beyond the active-queue examples in the
official Python skill:

```python
subsystem.render_queue_instance_with_executor_instance(temporary_queue, executor)
```

`render_queue_instance_with_executor(queue, executor_type)` is also reflected.
Construct a separate transient `MoviePipelineQueue`, allocate only its own
jobs, and explicitly configure map, sequence, output, frame range, samples,
warm-up and render passes. Snapshot the subsystem's active queue, jobs, origin
and dirty state before and after; do not clear, copy into or reload that queue
merely to start an independent job.

Retain executor/queue/callback references in a persistent Python module: each
`execute_python` call has a fresh namespace. Register finished and error
callbacks before dispatch. Use short later status calls, a unique output
directory, completion/error results and decoded expected-size frames. File
growth, status progress or `is_rendering=false` alone does not establish success.
`MoviePipelinePIEExecutor` launches PIE, so coordinate its lifecycle with any
other editor/gameplay work. Only cancel the executor owned by the current run.

An empty camera binding requires additional MRQ integration. The installed
classic `UMoviePipeline::InitializeLevelSequenceActor` implementation searches
the render world for actors using the target sequence, stops matching players,
and reuses a match or creates an actor. It then enforces playback settings and
stops the selected player again. This can interact with gameplay OnStop cleanup;
do not assume a distinct player or that gameplay overrides survive unchanged.
This source finding is not a claim about every MRG path.

Use a map-resolving possessable in a dedicated render sequence, or verify an
explicit render-player binding route. The
[5.9 render-binding reference](ue-5.9-mrq-bindings.md) gives the exact discovered
native/Python route and migration checks. Queue rendering and binding migration
were not executed in this pass. Do not advertise a production-render helper
based solely on symbol discovery.

## Background spawnable gap remains

On this build, `LevelSequenceEditorSubsystem.AddSpawnableFromClass` with an
explicit sequence and `CineCameraActor` while no timeline was open returned:

```json
{"bindingId":"00000000-0000-0000-0000-000000000000","sequence":null}
```

`MovieSceneSequenceExtensions.GetBindings` then returned an empty array. Treat
this as a failed write, even though MCP did not set `isError`. Do not build tracks
on that proxy, retry by opening UI, or claim that 5.9 fixes the 5.8 limitation.
Inspect a public background API via 5.9 `PythonScriptingTools` for this exact gap
if the task needs it. The existing `background_compat.py` 5.8.4 build allowlist
was not broadened by this test.

## Existing helper scope

The legacy plan builder, inspector, sampler and render helpers retain their
5.8 contracts unless individually ported and exercised. The new native camera
helper is the create-only 5.9 path described above. Shared transport support
does not make every high-level helper compatible. Use current native schemas
and official Python for verified gaps; retain existing UI authorization gates.

No 5.8 editor regression was performed by this 5.9 pass. Save/compile, curve data,
PIE runtime and final rendered image acceptance are separate results.
