# Sequencer MCP toolsets (UE 5.8.4, verified)

Epic's built-in MCP exposes Sequencer through the `animation_toolset` plugin. List or describe
them with `python ../unreal-engine-mcp/scripts/builtin_mcp.py` (or `client.describe_toolset`).

| Toolset | Tools | Use for |
| --- | --- | --- |
| `SequencerTools` | 140 | sequences, bindings, tracks, sections, camera cuts, playback, folders, markers, copy/paste, subsequences |
| `SequencerKeyframingTools` | 22 | channel names, add/remove/get keys (float/int/bool/string), defaults, bake, curve editor |
| `SequencerControlRigTools` | 72 | Control Rig tracks, control transforms per frame, spaces, anim layers, FBX to/from rig, bake to rig |
| `SequencerOutlinerTools` | 18 | outliner tree, mute/solo/lock/pin/expand nodes |
| `SequencerConditionTools` | 9 | track/section/row conditions |
| `SequencerCustomBindingTools` | 8 | spawnable/possessable/custom binding conversion |
| `SequencerImportExportTools` | 6 | FBX import/export, linked anim sequences |

References are passed as `{"refPath": "/Game/Path/LS.LS"}` for objects and
`{"bindingId": "<guid>", "sequence": {...}}` for bindings (`MovieSceneBindingProxy`). Track
classes are passed as class refs, e.g. `{"refPath": "/Script/MovieSceneTracks.MovieScene3DTransformTrack"}`.

## Core recipe (explicit UI workflow only)

The following recipe opens a tab. For the user's default background workflow,
inspect and edit with tools taking explicit sequence/binding/section references.
An explicit sequence argument alone is insufficient: the audited
`add_spawnable_from_class` / `add_spawnable_from_instance` wrappers call
`LevelSequenceEditorSubsystem`, which requires that sequence to be open.
Do not add `--allow-editor-ui` to a helper just because it otherwise refuses.
The UI helper snapshots and restores an idle root timeline, frame, speed and
loop mode; it refuses playing/nested sessions and preserves a user switch.

```text
create_level_sequence(package_path, asset_name)      # deletes an existing asset at that path
set_display_rate(sequence, 30, 1); set_playback_range(sequence, 0, 180)
open_sequence(sequence)                               # needed by create_camera / add_actors
create_camera(spawnable=True) -> binding              # + transform, spawn, camera-cut, 3 property tracks
find_tracks_by_type(binding, MovieScene3DTransformTrack) -> get_sections -> section
add_key_float(section, "Location.X", frame, value, "cubic")
get_child_possessables(camera) -> CameraComponent binding -> get_tracks_on_binding
  (display names CurrentFocalLength, ManualFocusDistance, CurrentAperture) -> add_key_float(section, "None", ...)
add_actors([actor]) -> binding; add_track_to_binding(binding, MovieScene3DTransformTrack) -> add_section
add_track_to_binding(binding, MovieSceneSkeletalAnimationTrack) -> add_section -> set_section_animation -> set_section_range
set_playhead_frame(f); force_evaluate()               # evaluate, then read actors with ActorTools / ObjectTools
restore previous idle root sequence/frame/speed/loop (or close our own new tab)
```

## Verified behaviour

- **Display-rate frames** apply to the audited `set_section_range`, `add_key_float`,
  `get_keys` and `set_playhead_frame`, regardless of the 24000 tick resolution.
  Check other domains' units separately. Keep `numerator/denominator` exact;
  30000/1001 and 29.97 are different rates.
- **`create_camera`** creates a spawnable `CineCameraActor` with a transform track (unbounded
  section), a spawn track, a camera-cut section bound to it, and on its `CameraComponent` child
  binding three float tracks: `CurrentFocalLength`, `ManualFocusDistance`, `CurrentAperture`.
  Key those; a second track for the same property is overridden and has no effect. The camera
  spawns with the editor viewport's transform, so key its location and rotation.
- **Channel names:** transform sections `Location.X/Y/Z`, `Rotation.X/Y/Z`, `Scale.X/Y/Z` with
  `Rotation.X` = roll, `Rotation.Y` = pitch, `Rotation.Z` = yaw. A float property section has one
  channel named `"None"` (not `Value`). `get_channel_names` tells you.
- **`set_property_name_and_path(track, display_name, property_path)`**: `display_name` becomes
  the property *name* the track binds to. Pass the FName (`CurrentFocalLength`); a spaced label
  leaves the track unbound.
- **Section range defaults vary by class.** Inspect `has_section_start_frame` /
  `has_section_end_frame` and bounded endpoints. A Fade section can default to
  an unbounded range; do not report it empty merely because no range was set.
  Set the intended range explicitly when needed. End-exclusive sections do
  not evaluate keys at the end frame; sample `end-1` for the last visible frame.
- **Possessable actor transforms:** a new transform section evaluates unkeyed channels at their
  defaults (rotation 0, scale 1), which rotates and rescales the actor. Set every channel's
  default (`set_default_value`) to the actor's current transform before keying.
- **`set_binding_name`** sets the display name (shown in Sequencer); the binding's object name
  stays `CineCameraActor`, `CineCameraActor2`, ...
- **Binding validity:** UE 5.8.4 CL 58902052 returned a zero GUID and `sequence: "None"`
  for background `add_spawnable_from_class`; `set_binding_name` then returned true even
  for that invalid proxy. `Editor.call` rejects invalid binding inputs. For background
  authoring, use `Editor.add_spawnable_from_class(sequence, class_path)`: MCP first,
  the observed zero-GUID/`sequence: "None"` result, unchanged inventory and inactive target confirmed before the public
  `MovieSceneSequenceExtensions.add_spawnable_from_class` fallback, then binding readback.
  Exceptions/timeouts, another malformed/wrong-sequence proxy, partial additions
  or an unknown editor state do not permit a retry. Readback requires exactly one
  new binding and no removed bindings or duplicate IDs; unexpected inventory
  changes require inspection rather than a clean creation report.
  The public background extension currently emits an Epic deprecation warning in this
  build; its recommended editor-subsystem replacement still requires an open timeline.
  `sequencer_tools/background_compat.py` isolates this call and allows only the audited
  `5.8.4-58902052+++UE5+Release-5.8` build. It checks the live full version and callable
  before loading the fallback target or writing; another build/branch or a missing API
  refuses this route. A working MCP binding still takes precedence on any build.
  `Editor.python` records the build, native warnings/errors and parsed compatibility
  result in `Editor.calls`; a printed marker does not override a failed command result.
  Keep that evidence in reports. Re-check current MCP/custom-binding coverage and public
  APIs after an upgrade, then source-audit and smoke-test any allowlist change.
  No nondeprecated, public, background creation replacement was found in this build.
  Do not suppress the warning or open UI automatically to hide that maintenance limit.
- **Camera inspection:** a spawnable CameraActor may have no separate CameraComponent
  binding. `sequence_inspect.py` reads its template/possessed class through the verified
  metadata gap as well as checking child bindings; names alone are not camera evidence.
  Multiple custom-binding indices or runtime-created cameras need separate runtime checks.
- **Camera-cut binding, official MCP:** verified on `5.8.4-58902052+++UE5+Release-5.8`.
  The specialized `set_camera_cut_binding` still fails before writing, but its editable
  `cameraBindingId` is covered by `ObjectTools`. Get the complete ID using
  `SequencerTools.get_binding_id(sequence, binding)`, set it with
  `ObjectTools.set_properties(instance=section, values=<JSON>)`, and read it with
  `get_properties(instance=section, properties=["cameraBindingId"])`.
  The JSON value is `{"cameraBindingId":{"guid":"...","sequenceId":0,"resolveParentIndex":0}}`;
  take all values from the returned ID rather than hardcoding this local-binding example.
  `Editor.bind_camera_cuts` preflights the sequence inventory and full section paths,
  verifies every field after each write, and skips a binding already equal to the target.
  A failed or ambiguous write stops subsequent cuts; no Python retry is made.
  `sequence_inspect.py` also reads cut IDs through this MCP property route.
  This is an existing official interface discovered by live validation, not evidence of
  a new patch feature or a fix to Epic's specialized setter. When another typed tool
  fails or lacks a getter, inspect that object's official reflected property schema
  before declaring a transport gap; only supported editable properties qualify.
- **`SceneTools.find_actors(name, tag, collision_channels)`** needs all three arguments and
  matches labels by substring; filter on `ActorTools.get_label` for an exact match.
- **`get_section_properties` / `get_section_range`** fail on unbounded sections with "Section
  does not have a start frame"; that is the normal state of camera and property sections.
- `get_bound_objects` returns the spawned or possessed object only while the sequence is open
  and evaluated.

## Gaps and workarounds

| Gap | Workaround |
| --- | --- |
| `add_spawnable_from_class` requires an active target timeline, returns an invalid proxy otherwise | `Editor.add_spawnable_from_class` verifies the no-write result, then permits the isolated deprecated public extension only on the exact audited build, retaining its warning; no automatic `open_sequence` |
| `set_camera_cut_binding` raises the known pre-write "call() takes at most 0 arguments" | Stay on official MCP: `get_binding_id` + `ObjectTools.set_properties/get_properties` for the complete `cameraBindingId`; implemented by `Editor.bind_camera_cuts` |
| No specialized getter reads a camera cut's camera | Official MCP `ObjectTools.get_properties` reads `cameraBindingId`, including binding resolution space (`sequence_inspect.py`) |
| Missing binding internal name/parent/template class, skeletal animation or one-sided range getters in audited schema | `sequence_inspect.py` reads these metadata gaps with stock Python; covered structure/track classes/channel keys stay on MCP and no timeline is opened |
| No general render tool in audited schema | `sequence_render.py` uses deprecated `unreal.SequencerTools.render_movie` only with explicit capture UI opt-in; MRQ/MRG is a separate pipeline requiring current official API/plugin discovery and its own acceptance |
| Legacy capture defaults to 24 fps and starts cold | set `settings.use_custom_frame_rate` / `custom_frame_rate` to the sequence rate; render pre-roll frames before the wanted frame (motion blur and TAA otherwise smear a single cold frame) |
| Render completion callback never fires | retain `OnRenderMovieStopped`; require a successful callback AND fresh, decoded expected-size PNGs under the run's unique token directory. Without a callback, report unknown completion and inspect activity before starting another capture |
| Python key times | `key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)` for display-rate frames |

## Editor-side side effects

`open_sequence` opens the Sequencer tab in the user's editor and evaluating moves possessed
actors; restoration must be checked, especially after events or custom completion
modes. Closing a tab alone does not prove gameplay state restoration.
`create_level_sequence` deletes an existing asset at the path. Use a candidate;
`--replace` requires a distinct saved backup (`--backup-path` plus `--save`) and
refuses the currently open asset. Save only the intended packages under the
task's authorization. Structural reads do not prove evaluated or runtime behavior;
see [runtime acceptance](runtime-acceptance.md).
