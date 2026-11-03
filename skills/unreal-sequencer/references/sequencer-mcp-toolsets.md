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

## Core recipe

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
close_sequence()
```

## Verified behaviour

- **Frames are display-rate frames** in every tool (`set_section_range`, `add_key_float`,
  `get_keys`, `set_playhead_frame`), regardless of the 24000 tick resolution.
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
- **Sections added with `add_section` have no length** (start = end). Make them unbounded with
  `set_section_start_bounded` / `set_section_end_bounded(False)` or set a range; an end-exclusive
  range does not evaluate keys on its end frame.
- **Possessable actor transforms:** a new transform section evaluates unkeyed channels at their
  defaults (rotation 0, scale 1), which rotates and rescales the actor. Set every channel's
  default (`set_default_value`) to the actor's current transform before keying.
- **`set_binding_name`** sets the display name (shown in Sequencer); the binding's object name
  stays `CineCameraActor`, `CineCameraActor2`, ...
- **`SceneTools.find_actors(name, tag, collision_channels)`** needs all three arguments and
  matches labels by substring; filter on `ActorTools.get_label` for an exact match.
- **`get_section_properties` / `get_section_range`** fail on unbounded sections with "Section
  does not have a start frame"; that is the normal state of camera and property sections.
- `get_bound_objects` returns the spawned or possessed object only while the sequence is open
  and evaluated.

## Gaps and workarounds

| Gap | Workaround |
| --- | --- |
| `set_camera_cut_binding` raises "call() takes at most 0 arguments" | editor Python: `section.set_camera_binding_id(unreal.MovieSceneSequenceExtensions.get_binding_id(seq, binding))` (`Editor.bind_camera_cuts`) |
| No tool reads a camera cut's camera | editor Python `section.get_camera_binding_id()` (`sequence_inspect.py`) |
| No render tool | legacy capture `unreal.SequencerTools.render_movie` (deprecated, works without plugins) in `sequence_render.py`; Movie Render Queue needs the `MovieRenderPipeline` plugin enabled (editor restart, ask first) |
| Legacy capture defaults to 24 fps and starts cold | set `settings.use_custom_frame_rate` / `custom_frame_rate` to the sequence rate; render pre-roll frames before the wanted frame (motion blur and TAA otherwise smear a single cold frame) |
| Render completion callback never fires | keep the `OnRenderMovieStopped` delegate referenced after the remote script returns; also detect completion by the expected files |
| Python key times | `key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)` for display-rate frames |

## Editor-side side effects

`open_sequence` opens the Sequencer tab in the user's editor and evaluating moves possessed
actors until the sequence closes; close it when done. `create_level_sequence` deletes an
existing asset at the path. Sequences are unsaved until saved; never save without the user's
request.
