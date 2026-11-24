# UE 5.9 render bindings and queue ownership

Use when rendering a sequence whose gameplay camera is assigned through an empty
binding or tag. The native tools and public Python symbols below were discovered
live, and installed source was inspected for binding migration and classic MRQ
setup. The classic MRQ route has not been executed: verify it on the target
before relying on it. It is separate from the
[saved background camera helper](ue-5.9-sequencer.md#native-camera-helper-no-open-timeline-required).

A dedicated 12-frame sequence has been rendered through Canvas
`TriggerSequenceRender` in an isolated offscreen editor
([details](#verified-canvas-sequence-render-12-frames-three-captures)). That
result covers neither the classic MRQ migration recipe nor an existing
gameplay sequence.

## Contents

- [Classic MRQ may reuse a gameplay sequence actor](#classic-mrq-may-reuse-a-gameplay-sequence-actor)
- [Build a dedicated render sequence with a map possessable](#build-a-dedicated-render-sequence-with-a-map-possessable)
- [Own the queue, callbacks and render lifecycle](#own-the-queue-callbacks-and-render-lifecycle)
- [Verified Canvas sequence render: 12 frames, three captures](#verified-canvas-sequence-render-12-frames-three-captures)
- [验证记录](#验证记录)

## Classic MRQ may reuse a gameplay sequence actor

`UMoviePipeline::InitializeLevelSequenceActor` in the installed
`MovieRenderPipelineCore/Private/MoviePipeline.cpp` searches the render world
for `LevelSequenceActor` instances using the target sequence. It calls Stop on
matching players and reuses the last match, or spawns an actor when none exists.
It enforces no loop, no autoplay, pause-at-end and ForceRestoreState, sets the
sequence/time controller and calls Stop again.

Therefore, do not assume MRQ always creates a separate player, nor rely on a
gameplay player's binding override surviving pipeline setup. Stopping an
existing player can also enter its gameplay OnStop cleanup. These are source
findings for classic `UMoviePipeline`; inspect the chosen MRG path separately.

## Build a dedicated render sequence with a map possessable

Keep the gameplay sequence unchanged. For the simple one-camera Transform
sequence produced by the native helper, this route avoids a runtime-only
binding override:

1. Coordinate with the PIE owner before writes. Freshly verify engine/project
   identity, the intended editor map, its persistent camera actor and a new
   destination asset path. Do not bind a PIE clone into an editor asset.
2. Discover `AssetToolset.Duplicate` and call it with `path` and `newPath` for
   the sequence asset. Verify its boolean result, destination existence and
   loaded sequence identity. The discovered tool is `Duplicate`, not
   `DuplicateAsset`.
3. Find the old empty camera binding **inside the duplicate**. Live discovery
   exposed no native wrapper for `add_possessable`, `move_binding_contents` or
   `locate_bound_objects`; use the official Python executor for this route:

   ```python
   new_binding = unreal.MovieSceneSequenceExtensions.add_possessable(
       render_sequence, editor_camera)
   valid = unreal.MovieSceneBindingExtensions.is_valid(new_binding)
   unreal.MovieSceneBindingExtensions.move_binding_contents(old_binding, new_binding)
   objects = unreal.MovieSceneSequenceExtensions.locate_bound_objects(
       render_sequence, new_binding, editor_world)
   ```

   These lines show the API route, not a script to run without intermediate
   checks. Before moving contents, require a nonzero destination GUID, the same
   duplicate sequence, a different source GUID and **no destination tracks**.
   `add_possessable` can return an existing binding. Installed
   `UMovieScene::MoveBindingContents` steals source tracks and calls
   `DestinationBinding->SetTracks(...)`; it replaces destination tracks rather
   than merging them. It also remaps children and can remove colliding child
   bindings. This simplified migration is for the verified no-child fixture;
   inspect component/hierarchical bindings before adapting it to other assets.
4. Enumerate root tracks and CameraCut sections using native
   `MovieSceneSequenceExtensions.GetTracks` and
   `MovieSceneTrackExtensions.GetSections`. Explicitly call
   `MovieSceneSectionExtensions.SetCameraCutBinding` with each intended section
   and the new binding proxy. Moving binding contents does not update root
   camera-cut references or binding tags for you.
5. Discover `MovieSceneBindingTagExtensions.TagBinding` / `UntagBinding` and
   transfer the intended tag. Verify cuts, tracks, keys and tags before removing
   the old empty binding with `MovieSceneBindingExtensions.Remove`.
6. Reacquire binding/channel descriptors after mutation. Confirm
   `locate_bound_objects(render_sequence, new_binding, editor_world)` resolves
   exactly the intended map camera. Read back rate, range, cuts, tags, metadata
   and curve samples, save only the render copy, and check the gameplay asset
   stayed unchanged. New sequences can instead be authored directly around
   `add_possessable`, avoiding migration.
7. Validate resolution again in the render world and inspect actual output.
   An editor-world locator does not establish a PIE/render-world binding or
   the final camera. Confirm the camera's lens/focus as well as its transform.

Look up public symbols through `PythonScriptingTools` before execution. Preserve
returned binding identity fields, including root/parent resolution. A failed or
timed-out mutation must be reconciled by readback before continuing; do not
restart duplication or track migration blindly.

## Own the queue, callbacks and render lifecycle

The reflected subsystem supports both:

```python
subsystem.render_queue_instance_with_executor_instance(temporary_queue, executor)
subsystem.render_queue_instance_with_executor(temporary_queue, executor_type)
```

Create a transient `MoviePipelineQueue` and allocate only its jobs. Snapshot the
user's active queue, jobs, origin and dirty state before and after; do not clear,
copy into or load over that queue to run an independent render. Retain the queue,
executor and finished/error callbacks in a persistent Python module because
each official `execute_python` call has a fresh namespace.

Explicitly configure job map, dedicated render sequence, output directory,
rational rate/range, warm-up, samples, render passes and image/codec policy.
The current reflected GameOverride field is `soft_game_mode_override`;
`game_mode_override` is deprecated since 5.5. The installed default
`MoviePipelineGameMode` enables cinematic mode for the controller, hiding the
player/HUD and preventing movement/turning. It does not suppress every Actor's
BeginPlay. Check automatic Intro/gameplay activity and configure the render job
appropriately rather than changing project defaults as a workaround.

`MoviePipelinePIEExecutor` starts PIE: coordinate with other gameplay tests and
cancel only the owned executor. Require a successful completion callback, no
unresolved error result, and decoded frames matching the requested count, size,
rate and cuts. File growth or `is_rendering=false` alone is insufficient. Follow
[runtime/render acceptance](runtime-acceptance.md) for the observable result.

## Verified Canvas sequence render: 12 frames, three captures

The same 5.9 Preview build rendered a new, disposable sequence with a
placed-camera possessable, Transform animation and CameraCuts, at 24 fps over
`[0,12)`. The original gameplay sequence was not edited or used as this render
fixture. Read the core
[Canvas render reference](../../unreal-engine-mcp/references/ue-5.9-canvas-generation-render.md)
for direct-tool discovery, process isolation and the separate still-camera bug.

After checking the exact live schema, `TriggerSequenceRender` received the
fixture's explicit `SequencePath`, `CameraSource: {"mode":"sequence"}`, custom
320×180 with `matchAspect:false`, all ViewportLookFlags false, and the verified
`UseWorldNormals:"True"` variable. It completed once; no timeline was opened.
This route always uses PIE and has no `ExecutionMode` or per-call frame-range
override. Bound the fixture's playback and cut sections before submitting.

The returned text blocks named capture directories under a unique
`Saved/UnrealCanvasSequenceRender/<run>/` directory. The three expected capture
identities were `DefaultLayer/beauty`, `DefaultLayer/depth` and
`DefaultLayer/normal`. Each had 12 decoded 320×180 PNGs, consecutive frame
numbers 0000–0011, fps=24 and startFrame=0. Use each returned `filePattern`:
the beauty pattern was `frame.Layer1.%04d.png`, not the schema description's
generic example `frame.%04d.png`. Multiple captures can share a directory;
count files matching the capture's pattern, not every PNG in that folder.

All frames had scene content and distinct hashes. Visual inspection of frames
0, 5 and 11 showed coherent camera motion in beauty, depth and normals. A local
H.264 preview encoded from the beauty frames was decoded successfully: 12 frames,
24 fps, 0.5 seconds, 320×180, silent. This is a render-contract test, not final
cinematic-quality approval or audio validation.

PIE ended; camera actor transform/lens, the free viewport camera, actor set,
selection, open assets/timeline, dirty packages and the existing queue matched
their pre-render values. The offscreen viewport's *pixel dimensions* changed
from 387×90 to 383×86, so do not claim the complete UI layout was identical.
The original map and gameplay sequence file hashes stayed unchanged. The
test sequence was removed after output inspection; the render log segment
contained no errors or warnings.

## 验证记录

- 2026-11-11，UE 5.9.0 Preview / CL 60351404：原生工具与公开 Python 符号为
  实时发现；绑定迁移与经典 MRQ 初始化来自安装源码审阅。未迁移绑定、未运行
  executor、未验证渲染帧。
- 2026-11-16，同一构建：独立离屏编辑器中通过 Canvas `TriggerSequenceRender`
  渲染一次性 12 帧 / 24 fps 序列，三个通道各 12 张 320×180 PNG，已解码检查。
- 未执行：经典 MRQ、任意绑定、长序列、音频、Control Rig。


