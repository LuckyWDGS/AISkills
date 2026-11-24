# UE 5.9 editor tools: UI, images and diagnostics

Live checked on UE 5.9.0 Preview CL 60351404 in an isolated project. The
checks below used background MCP calls. They did not open a widget/timeline,
move the user's camera or run PIE. Discover current schemas before reuse;
native ownership changes are not all new capabilities.

## Contents

- [UMG authoring and animation](#umg-authoring-and-animation)
- [Offscreen scene capture and media](#offscreen-scene-capture-and-media)
- [Frame statistics and GPU snapshots](#frame-statistics-and-gpu-snapshots)
- [CSV profiling: callable, but text parsing failed cross-check](#csv-profiling-callable-but-text-parsing-failed-cross-check)
- [Rewind, knowledge and project files](#rewind-knowledge-and-project-files)

## UMG authoring and animation

| Task | Live owner |
|---|---|
| List classes, create Widget Blueprint, edit tree, compile | `WidgetBlueprintEditorSubsystem` |
| Reflect and set widget properties | `ObjectToolset.GetPropertySchema`, `GetProperties`, `SetProperties` |
| Create/list widget animations and bind a widget | `WidgetAnimationToolset` |
| Animation bindings, tracks, sections and numeric keys | `MovieSceneSequenceExtensions`, `MovieSceneBindingExtensions`, `MovieSceneTrackExtensions`, `MovieSceneSectionExtensions` |
| Set the animated property name/path | `MovieScenePropertyTrackExtensions` |
| Tree depth, widget properties, event/delegate connections | `WidgetStaticAnalysisToolset` |

The tested chain created a new Widget Blueprint with a CanvasPanel root and
TextBlock child, wrote Chinese text and display names, and compiled it. Asset
metadata carried a Chinese description and stable module ID. A two-second
WidgetAnimation bound the TextBlock's `RenderOpacity` property to a float
track, with linear keys at display frames 0→0 and 30→1. The tree, text,
binding count, keys and animation duration were read back; the opacity curve
evaluated to 0.5 at frame 15. The final compile
succeeded and only the candidate asset was saved; it then reported clean.

Useful interpretation details:

- Root depth is **0**. One child produces `GetWidgetTreeDepth=1`, consistent
  with `DescribeWidget`'s per-widget depth.
- Display/tick conversion gave a nominal two-second duration of
  `2.0000166893`. Use a tolerance appropriate to the frame/tick rate rather
  than exact floating-point equality.
- `GetWidgetConnectionMap` can include an unconnected built-in delegate such
  as font-loading completion. This alone is not a compile error or proof of
  an application event missing its handler.
- Widget animation data is a MovieScene sequence. Preserve full live
  binding/channel/key descriptors instead of inventing integer IDs.

These checks establish asset authoring, static analysis and compilation.
They do not establish widget layout appearance, runtime playback, input,
MVVM propagation, game HUD integration or DPI behavior. Use runtime/visual
cases for those outcomes.

## Offscreen scene capture and media

`SceneCaptureToolset` can list worlds/viewports/modes, obtain an active
editor view and render a camera snapshot in an explicit world. The tested
`Capture` route used Lit mode at 640×360 and then the shared helper at the
source viewport's dimensions. An explicit pose was changed only in the
capture camera struct. `GetActiveEditorView` before and after returned the
same world and camera; the PNGs were decoded and visually inspected, with no
capture warnings. The helper's tested frame showed the existing arena and
scene effects from the requested pose.

```powershell
python scripts/capture.py --url <MCP URL> --project <absolute .uproject> viewport --pose "x,y,z,pitch,yaw,roll" --out-dir <session>/captures --name shot
python scripts/capture.py --url <MCP URL> --project <absolute .uproject> asset /Game/Materials/M_Name --out-dir <session>/captures
```

`capture.py` selects `SceneCaptureToolset` from live discovery for the modern
viewport route. It copies active camera settings, applies the supplied pose
to that snapshot, and reports camera before/after, `camera_unchanged`, actual
capture metadata and warnings. It does not silently retry a failing modern
capture through the legacy route. The asset-thumbnail route remains
`EditorAppToolset.CaptureAssetImage`; it is different from a world simulation
preview. A 256×256 material thumbnail also passed the live helper route and
was visually inspected. The media handling is shared by both routes.

**Preserve the raw MCP result.** In this 5.9 build the JSON `image` field is a
`urn:toolresult:...` correlation ID. The actual PNG is an `image` content block
in the same tool result, with base64 `data` and `mimeType`. The URN is not a
downloadable URL, resource or filesystem path. Unwrapping the JSON alone
discards the media. `ue_mcp.capture.result_image` handles both the 5.8
embedded bytes and 5.9 content blocks, rejecting missing/ambiguous media.
The saver checks base64 and PNG header/dimensions; inspect/decode the saved
image before claiming visual acceptance.

A scene image does not advance a sequence or prove Niagara/animation motion.
Different frame hashes can result from temporal rendering noise. State the
visual question and inspect the relevant frames.

## Frame statistics and GPU snapshots

The live calls exercised:

- `StatsToolset.GetFrameTimings`: GT/RT/RHI/GPU timing values.
- `StatsToolset.ListStatGroups` and `GetFrameTree`: registered groups and a
  CPU frame tree, with a minimum-duration/depth filter.
- `GpuProfilerToolset.TriggerGPUProfile`: actual Compute/Graphics pass trees.

These were editor diagnostic snapshots under the current workload. They do
not establish packaged-game or PIE performance, consistent frame rate, a
before/after optimization result or platform budgets. Record context and
sample coverage when using them to explain a bottleneck.

## CSV profiling: callable, but text parsing failed cross-check

`PerfToolset.CsvProfilerToolset` exposes `GetCsvInfo`, `ReadStatValues`,
`ReduceStat`, `TopStats` and `ListEvents`. All five accepted a real capture
from a bounded `ConsoleToolset.RunConsoleCommand("csvprofile FRAMES=10")`.
The capture contained ten editor frames and 254 stats, with engine/platform
metadata. Record the output directory baseline before a capture and identify
the new file; do not overwrite or remove unrelated recordings.

**This Preview's native text-CSV numbers did not match the capture file.**
For the same recording, a normal CSV reader found a first `FrameTime` sample
of `23.2072`, while `ReadStatValues` returned ten zeros. Empty raw `EVENTS`
cells became numeric timing strings in `ListEvents`. A repeated native read
reproduced both discrepancies. `ReduceStat` agreed with the native zeros,
which proves only consistency within that parser. It does not validate the
underlying measurements.

Installed source points to the engine CSV reader's `SerializeText` sample
tokenization in `Source/Developer/CSVUtils/Private/CSVProfilerUtils.cpp` as a
candidate explanation for column shifting around empty fields. No engine
patch was made, and this source suspicion is separate from the observed
mismatch. Binary `.csv.bin` parsing was not tested.

For this build, cross-check text-CSV samples against the raw file with a
standards-aware CSV reader before using reductions/rankings/events. The
capture's metadata can select the header row at the end; do not interpret
that header or metadata as frames. Report mismatches and use verified raw
columns for any local analysis. Do not silently accept zero timing results.

Other schema details still matter on a validated reader: windows are
half-open `[frameStart, frameEnd)`, `frameEnd=-1` reaches the end,
`ReadStatValues.count=-1` reads the rest, and absent reduced stats are omitted.
`GetCsvInfo` returns individual names only when `statNameFilter` is set.
`TopStats` ranks raw values with no unit normalization; filter comparable
timing/counter groups rather than mixing byte counts and milliseconds.

## Rewind, knowledge and project files

- `RewindDebuggerToolset.GetSessionInfo` was callable and reported an inactive
  session with zero recording duration. Recorded events, objects/properties
  and trace queries require an actual recording; they remain untested here.
- `KnowledgeBaseTools.ListKnowledgeBases` returned an empty array. A registered
  query/write schema does not mean a knowledge base is configured. Knowledge
  queries and entry writes were not exercised.
- `FileSystemToolset` resolved `/Saved`, created a scoped test directory,
  wrote a new multilingual file, read it in two pages via the returned
  continuation cursor and deleted only that fixture. Concatenating the pages
  exactly reproduced all four lines. Use tool path resolution and returned
  cursors; avoid interpreting virtual roots as operating-system paths.

Keep raw schemas, machine paths, captures and test evidence in ignored session
storage. Readback, compile, image inspection and runtime acceptance are
separate results. None of these 5.9 checks establishes 5.8 editor regression.
