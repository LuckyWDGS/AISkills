# Shared conventions for the UE 5.9 skills

`unreal-engine-mcp`, `unreal-sequencer`, `unreal-material-artist`,
`niagara-vfx-artist` and `vfx-flipbook-generator` follow these rules. Each
skill adds only its domain-specific details.

## Contents

- [Engine version and tool status](#engine-version-and-tool-status)
- [Requirements](#requirements)
- [Editor connection](#editor-connection)
- [Execution boundaries](#execution-boundaries)
- [Evidence levels](#evidence-levels)
- [Chinese module annotations](#chinese-module-annotations)
- [Documentation conventions](#documentation-conventions)

## Engine version and tool status

This bundle (`skills/ue5.9/`) targets **UE 5.9 only**. Everything recorded in it
was verified on **UE 5.9.0 Preview, CL 60351404**. A later build can rename
tools, arguments and result fields, so the live schema always wins over a name
written here. When `builtin_mcp.py status` reports another build, re-run
discovery for each tool before its first call and record the new build in the
relevant verification record.

The shared client refuses an editor of another engine line before it sends a
request. For a UE 5.8 editor the user links `skills/ue5.8/` with
`tools/install.ps1 -UEVersion 5.8`; never switch the linked bundle yourself and
never mix files from the two bundles.

Every script and tool in these skills carries one status. Each skill lists its
tools with this label.

| Status | Meaning |
|---|---|
| `local` | Runs without an editor: planning, image QA, packing, manifests, reports. |
| `5.9` | Editor-connected and verified on the build above through UE 5.9 tools. |
| `untested` | Editor-connected through an engine-neutral route, but not yet run on the build above. Verify it on a scratch target before relying on it. |
| `unported` | Still written against UE 5.8 tool names. The client refuses it before any call. Do the same work with the native tools in the skill's `ue-5.9-*.md` reference. |

An `unported` helper is moved to `5.9` by following
[porting a helper](porting-helpers.md). Its offline tests and plan/report
modes keep working in the meantime.

## Requirements

- Python 3.10 or newer. `unreal-engine-mcp` uses only the standard library; the
  Sequencer, material, Niagara and flipbook skills also need Pillow
  (`pip install -r <skill>/requirements.txt`). Flipbook extraction needs FFmpeg
  (installed, or the `imageio-ffmpeg` package). Entry modules stop with a clear
  message on older interpreters.
- `python skills/ue5.9/unreal-engine-mcp/scripts/run_offline_tests.py` runs all
  five offline suites with non-loopback networking blocked. CI runs it on
  Ubuntu and Windows with Python 3.10 and 3.12.
- A UE 5.9 editor with Epic's `ModelContextProtocol` plugin and the official
  toolset plugins for the domain. `PythonScriptingTools` runs public Python
  through MCP.

## Editor connection

- Work through background connections. Leave UE windows, focus, the viewport
  camera and the open timeline as the user has them. UI operations (window
  moves, console keystrokes, opening an asset editor) happen only when the
  user asks for that operation; a failed call is never retried through the UI.
- Route each operation through the first route that covers it:
  1. a discovered Epic domain tool;
  2. `PythonScriptingTools` over MCP, to compose tools with
     `await call_tool(...)` or to reach a public `unreal.*` API for a verified
     domain-tool gap, after reading `read_me` and looking the symbols up;
  3. [Epic Python Remote Execution](official-python-remote.md), only when the
     MCP routes above do not cover the operation.
  Record the build, the inspected tools, the public API used and the readback.
  Return to the domain tool for the next covered operation.
- Some official calls activate UI even though they are official:
  `OpenEditorForAsset`, opening a sequence, camera and curve editors. Prefer
  the explicit-asset variants. A helper's `--allow-editor-ui` flag serves a
  user-requested UI workflow only.
- Gaps are reported with the operation, the tools checked and the build. A new
  bridge, C++ plugin or engine patch is a separate, explicitly requested piece
  of work. Existing project extensions may stay.
- Use the [developer workflow](developer-workflow.md) for scoped edits and
  acceptance, and [debugging and source navigation](debugging-and-source-navigation.md)
  to trace bindings, implementations and failure causes.

## Execution boundaries

- Resolve the expected project before writes (`--project`, `--expect-project`
  or `UE_MCP_PROJECT`). Use the full `.uproject` path for same-named checkouts.
  Identity comes from a fresh process check on every run.
- Some query-shaped tools have side effects. Blueprint node-type discovery can
  create temporary nodes, and MVVM binding or model listings can create a
  missing View. Use the reads named in the domain reference for an audit.
- Structural edits need a confirmed idle editor; an unknown PIE/Simulate state
  refuses writes. A user's running session is preserved. Runtime verification
  owns and stops only the bounded session it started.
- Inspect first, state the affected graph, module or track, and edit that
  scope. Use a candidate for a destructive rebuild. A duplicate counts as a
  backup once it is saved and verified; a transaction is an undo step only.
- UE 5.9 can refuse a call during a slow task with **Not run** and
  **This call made no changes**. Keep that result, do independent work and
  retry after the task ends.
- A timeout has unknown completion. Inspect the affected objects before
  deciding whether to repair or retry. Keep confirmed partial work and report
  it. The client never retries a tool error or a timed-out write.
- Save only the intended packages. Leave unrelated dirty flags and the user's
  other assets alone; global Save All is out of scope.
- Verify semantics as well as shape. Prove a Blueprint variable's owner,
  Target and local scope before replacing a Getter or a SET output. A
  layout-only edit leaves node types, defaults and connections unchanged. A
  lint warning alone does not authorize a logic rewrite.

## Evidence levels

Report each claim at the level that was actually reached, and name the levels
that were not run. A higher level never follows from a lower one.

| Level | What it shows | What still needs its own check |
|---|---|---|
| 1. Registered | The editor lists the tool and its schema. | That the call works on this asset. |
| 2. Called | The tool returned a result or an explicit error. | That the value was stored. |
| 3. Read back | A separate read returned the written structure or value. | Compilation and behavior. |
| 4. Compiled | The asset compiled; errors and warnings were read. | That it evaluates as intended. |
| 5. Evaluated in editor | Sampled curves, statistics, graph output or dirty state. | Appearance and gameplay. |
| 6. Seen | An image was captured and inspected for a named visual question. | Motion, event counts, timing. |
| 7. Runtime | A PIE or packaged case ran with expected and observed values. | Other platforms and cases. |

Rules that apply at every level:

- An empty check is `collected`, not `pass`.
- A capture answers a named visual question. Inspect the image and report the
  answer. Material and VFX looks are visual questions; a logic change is
  verified with state and logs. Graph-editor screenshots are not evidence.
- A thumbnail is a static render. Differing frame hashes alone do not show
  motion, because temporal AA changes them too.
- Installed source, an enabled plugin and a registered schema are three
  separate facts. So are a saved asset, a clean dirty flag and a cooked build.
- Results from this build say nothing about UE 5.8 or another platform.
- Debug drawing and on-screen prints are development aids. Keep them only when
  the user asks for a debug or demo module.

### Runtime result record

Record evidence in the project's ignored session directory, one row per case:
`case_id`, `module_id`, asset/graph and map, UE version/CL, network role (or
standalone), trigger, expected result and tolerance, observed values and
timestamps, evidence paths or log window, `pass|fail|not_run|blocked`, and the
cleanup performed. Use game time for gameplay timers and state the time
dilation. Record the sampling interval and tolerance. `blocked` names the
unavailable operation; `not_run` means no runtime test was attempted. Select
cases from the skill's `runtime-acceptance.md`.

## Chinese module annotations

- New or modified modules get a Chinese comment frame or description, a
  stable searchable module ID, and Chinese notes on non-obvious nodes, timing
  and conditions. Use the domain's own metadata: Blueprint comment frames,
  material comment frames plus parameter groups and descriptions, Niagara
  emitter and module display descriptions.
- Frame titles follow `【类别】【用途】【Module.ID】一句说明`, for example
  `【初始化】【调试打印】【BP.BeginPlay.PrintSequence】开始运行：每隔0.3秒打印`.
  Keep the title on one line (about 40 characters) and put purpose, entry,
  parameters and timing in the frame's details text.
- The labels and ID are text for searching. They are not Gameplay Tags and
  need no runtime variables or registry. Reuse the existing ID when extending
  a module.
- Frames enclose only their own module's nodes, never overlap and never share
  members. Use one comment colour per role within a project.
- Blueprint functions get a Chinese function frame around the entry (purpose,
  inputs, outputs, side effects, caller). Variables get Chinese category
  paths. Function and variable descriptions use the native metadata writes in
  [Blueprint authoring](ue-5.9-blueprint-python.md).
- Existing parameter identifiers, namespaces and bindings stay unchanged.
- Read-only audits and local-only work (for example atlas generation) leave
  untouched assets without new annotations.
- With several modules, add the asset/graph and module ID to the project's
  module index when one exists.

Details:
[Blueprint delivery standards](blueprint-delivery-standards.md#5-chinese-explanations-for-functions-variables-and-modules).

## Documentation conventions

These rules keep the five skills consistent. `tools/ue_docs_lint.py` checks the
mechanical ones.

- **Language.** `SKILL.md`, tool documentation and rules are written in
  English. Verification records are written in Chinese under a final
  `## 验证记录` heading. Text authored inside UE assets follows the annotation
  rule above.
- **Rules and records are separate.** A reference states rules and known
  limits first, in the present tense, with no reference to a particular
  session (`this run`, `本次`). Dated observations, measured numbers and the
  list of what was not run go under `## 验证记录`, each entry naming the date
  and build.
- **Contents.** A reference longer than 150 lines starts with a `## Contents`
  list.
- **Line width.** Prose wraps at 80 columns (CJK characters count as two).
  Tables, code blocks, headings and link targets are exempt.
- **Descriptions.** A skill's `description` says what the skill does and then
  when to use it ("Use when ..."), names the trigger words a user would type,
  and does not name an assistant.
- **Affirmative first.** Say what to do. State a prohibition once, in the
  section that owns it; evidence caveats live in
  [Evidence levels](#evidence-levels).
- **One home per fact.** `SKILL.md` routes to references and does not repeat
  them. Tool commands live in the skill's tool reference.
