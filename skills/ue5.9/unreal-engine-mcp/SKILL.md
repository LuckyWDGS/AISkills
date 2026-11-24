---
name: unreal-engine-mcp
description: Build and debug Unreal Engine 5.8/5.9 games through Epic MCP. Author Blueprints, characters, Behavior Trees, animation, input, UMG, levels and gameplay. Reconstruct editable modular interiors from reference photos. Connect material, Niagara and Sequencer skills for complete demos. Discover live schemas, compile, save and verify runtime behavior with native tools and official Python.
---

# Unreal Engine MCP

Use Epic's built-in MCP server and this checkout's `scripts/ue_mcp` client.
Read the serving editor's schemas; names, ownership and result types changed
substantially in 5.9. The independent UE 5.8 installation remains a baseline.
Never install a custom bridge or patch the engine to fill an automation gap.

Follow [shared conventions](references/shared-conventions.md): background
connections, Chinese module descriptions and stable module IDs, scoped saves,
and separate structural, compile, editor-evaluation and runtime evidence.
Keep the user's editor, timeline and viewport undisturbed. Use a dedicated,
identity-checked offscreen editor when a render needs camera piloting. Keep OS
keystrokes and UI automation out of MCP fallbacks.

## Connect to the intended editor

Use the five sibling UE skill packages from the same `skills/ue5.9/` folder;
never mix them with `skills/ue5.8/`. The user selects which set Codex links with
`tools/install.ps1 -UEVersion`; do not switch it yourself. Keep local
paths, schema dumps, scripts and continuation notes in ignored `.codex/session/`.

For concurrent editors reserve port 8000 for the stable setup and prefer 8001
for the test editor. Use an explicit absolute project guard and a separate
cache. These variables apply only to the current shell:

```powershell
$env:UNREAL_MCP_URL = 'http://127.0.0.1:8001/mcp'
$env:UE_MCP_PROJECT = '<absolute test .uproject path>'
$env:UE_MCP_CACHE_DIR = '<repo>/.codex/session/ue59-mcp-state'
python scripts/builtin_mcp.py --no-cache --new-session status
python scripts/builtin_mcp.py --refresh-schema list-toolsets
```

`status` reports the listener's current process, executable, project and engine,
plus the server's identity metadata when available. Verify 5.9 and the intended
absolute project path before writing. Same-named project copies require the
full path. A resumed session token never substitutes for a fresh process check.
`--url`, `--expect-project` and `--out` are global CLI options, before the command.

Startup requires `ModelContextProtocol` and the relevant official toolset
plugins. An authorized launch may use `-ModelContextProtocolStartServer
-ModelContextProtocolPort=8001`; `ensure` checks readiness and never launches or
restarts an editor. Poll with a short timeout while reading startup logs, with
a bounded deadline. Initialize alone is insufficient: discover the domain and
make a safe editor-state read. Do not mistake UE's MCP-client settings for the
server endpoint; the server uses Streamable HTTP at `/mcp`.
`status` / `ensure` preserve state-read errors with `ready=false` and a nonzero
exit code, including temporary slow-task refusals.

## Select the live contract

Read [the 5.9 audit](references/ue-5.9-preview-audit.md) for a 5.9 task, or the
[5.8 transport reference](references/builtin-mcp.md) for a 5.8 editor.

| Live discovery | Route |
|---|---|
| `list_toolsets`, `describe_toolsets`, `describe_tools`, `call_tool` | 5.9 search mode; batch toolset discovery or fetch a single tool descriptor |
| `list_toolsets`, `describe_toolset`, `call_tool` | 5.8 search mode |
| Qualified tools directly in `tools/list` | Native discovery, including pagination |

The client supports all three without changing editor settings. Resolved
toolset calls validate required and unknown argument names before dispatch
and treat `isError=true` as failure. Search mode can also expose bare plugin
tools alongside the meta-tools in `tools/list`; they need no invented owner.
Use the [direct-tool route](references/ue-5.9-mcp-canvas-plugins.md) for those
names rather than forcing them through the `--toolset` examples below.
A missing domain may mean a stale inventory or disabled plugin: refresh
discovery and inspect the descriptor/dependencies before calling it an MCP gap.

Before the first operation in a domain:

```powershell
python scripts/builtin_mcp.py describe-toolset BlueprintToolset --brief
python scripts/builtin_mcp.py describe-tool BlueprintToolset AddVariable
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorAppToolset
python scripts/builtin_mcp.py call <exact-tool> --toolset <live-toolset> --args-file <session>/args.json
```

Use the full schema for every tool you call, including struct fields, enums,
reference shapes and output fields. Large toolsets should be viewed with
`--brief`; keep full schemas in local files with global `--out`. The 5.9 client
uses `describe_tools` for individual calls. Do not translate snake_case names
to PascalCase by guesswork: parameters, ownership and behavior changed too.

UE 5.9 can explicitly refuse a call during a slow task with **Not run** and
**This call made no changes**. Retain that result, do independent work, and
retry only after the task ends. A timeout has unknown completion: inspect the
affected state before another write. The client never automatically retries
a tool error or a timed-out write.

Disk schemas are scoped to the current editor process/instance and server
build as well as its inventory. An unidentifiable instance uses memory only.
After startup completes, late plugin registration or an in-process reload,
refresh both `list-tools` and `list-toolsets` with `--refresh-schema` or
`--no-cache --new-session`; a held client can use `reinitialize()`. A reused
session can retain an early inventory even in the same PID. `--no-cache` alone
does not discard that session inventory. The same names and counts do not prove
that argument schemas stayed unchanged.

## Transport routing

1. **Discovered Epic MCP tool.** Use domain tools and `ObjectToolset` reflected
   properties/schema where they cover the operation. Read values back.
2. **Official Python through MCP on 5.9.** Use `PythonScriptingTools` to compose
   tools with `await call_tool(...)`, or reach a public Unreal API for a
   verified domain-tool gap. This is the normal 5.9 scripting route.
3. **Epic Python Remote Execution.** Use only when the required operation is
   uncovered by the target's MCP tools, including its Python executor. On
   5.8, `ProgrammaticToolset` composes registered tools but is not unrestricted
   Python. Read its execution environment before use.

If none covers the operation, report the precise gap and engine build.
Do not silently replay legacy scripts through a new executor.

For 5.9, read `python-readme` once per conversation and look up Unreal APIs
with `search_symbols` / `get_symbol` before calling them:

```powershell
python scripts/builtin_mcp.py python-readme
python scripts/builtin_mcp.py call get_symbol --toolset PythonScriptingTools --args-file <session>/symbol.json
python scripts/builtin_mcp.py execute-python <session>/probe.py
```

Scripts run on the game thread in a fresh namespace. `unreal`, `asyncio` and
`call_tool` are available; top-level `await` works. End with the expression to
return; `print` writes to LogPython. Prefer tools over equivalent Python,
inspect their exact return fields, and yield with `await asyncio.sleep(0)`
between costly chunks. Blocking `time.sleep` and synchronous network/process
calls are rejected. `run-script` retains the different 5.8 `def run()` /
`execute_tool` contract; it is not the 5.9 executor.

Legacy helper scripts that use this contract get a migration error when only
the modern executor is registered. They are never automatically translated or
sent to `execute-python`. This diagnostic does not migrate their domain calls.

Use `batch <steps.jsonl> --dry-run` for ordered writes, then execute the
validated plan. Each step has its own result and optional readback/expectation;
it stops at the first failure. Save intended packages in separate final steps.
It checks PIE and named-package dirty state. A batch is not an atomic rollback.
Failed dirty prechecks refuse execution; failed postchecks preserve completed
steps and report unknown state. Reconcile that state without replaying writes.

## Blueprint and programmer work

Blueprint is the preferred implementation surface for gameplay. For 5.9 start
with [native Blueprint and Graph DSL](references/ue-5.9-blueprint-python.md).
The old Python palette IDs and native Graph DSL references are different.

Read the existing entry, owners, variables, components, graphs and both ends
of each relevant wire. `inspect_blueprint.py` captures topology read-only;
`blueprint_lint.py` checks layout and annotations. Follow their actual version
coverage. Use native variable/function metadata in 5.9; the optional legacy
MCPBlueprintMetadata extension is unnecessary for these tested operations.

For Graph DSL, call `Docs`, then `Read` for the exact asset and scope. Edit the
canonical text with its latest revision; handle `bDslOmitted` and warnings.
Stale revisions reject the edit. Validate semantic completeness before any
whole-entry rewrite. Re-resolve node and pin references after DSL edits or
compilation because nodes may be reconstructed.

For gameplay work follow [delivery standards](references/blueprint-delivery-standards.md):
feature brief, production visuals, a scoped state/error log path, meaningful
functions and tuning variables, Chinese comment frames and metadata, compile,
and relevant runtime cases. Do not add a new language confirmation to an
already authorized Blueprint task. A layout-only change preserves logic.
Annotation-only work does not justify PIE or whole-graph rearrangement.

## Domain routes and evidence

| Work | Read |
|---|---|
| 5.9 complete small game, input/HUD/audio/interaction/lifecycle and package workflow | [Game production](references/game-production.md) |
| 5.9 character AI, Behavior Tree / Blackboard / tasks, animation and runtime observability | [Gameplay AI / animation](references/gameplay-ai-animation.md) |
| 5.9 MVVM HUD, CommonUI menus and UMG/Slate focus or lifetime diagnosis | [UI workflows](references/ue-5.9-ui-workflows.md) |
| 5.9 data-driven gameplay, GAS inspection, sockets/physics, saves/settings/localization and scoped automation | [Game systems](references/ue-5.9-game-systems.md) |
| 5.9 Unreal MCP versus MCP Client, Metadata, Canvas Bridge/Annotations, direct-tool discovery and plugin checks | [MCP / Canvas plugins](references/ue-5.9-mcp-canvas-plugins.md) |
| Canvas model availability, Codex image generation, isolated MRG renders and the actor-camera timing issue | [Generation / render verification](references/ue-5.9-canvas-generation-render.md) |
| Canvas mesh graphs, batched GeometryScript assemblies, material partitions and StaticMesh import | [Canvas mesh generation](references/ue-5.9-canvas-mesh.md) |
| Reference-image hard-surface modeling, editable GLB assemblies, native import and multi-view checks | [Reference-guided static meshes](references/ue-5.9-reference-mesh.md) |
| Rebuild an interior, validate a graybox, compare the saved camera and test lighting in fixed shots | [Photo to playable interior](references/ue-5.9-reference-interiors.md), [camera and cabinet checks](references/ue-5.9-reference-camera-qa.md) |
| Reimport modular scenes while preserving manual edits, or trace a blocked aisle and measure a packaged walkthrough | [Three-way reimport](references/ue-5.9-reimport-reconciliation.md), [packaged movement and profiling](references/ue-5.9-interior-walkthrough.md) |
| 5.9 Canvas, AI animation, Fab/Forge, Lumen/OIT/wind and Web target evidence/dependencies | [Production feature matrix](references/ue-5.9-production-feature-matrix.md) |
| 5.9 registered capability overview, measured improvements and remaining gaps | [5.9 audit](references/ue-5.9-preview-audit.md) |
| What changed from 5.8 skills, callable domains lacking helpers and evidence levels | [Tool coverage](references/ue-5.9-tool-coverage.md) |
| 5.9 Blueprint, native metadata, revision edits and async MCP scripting | [Blueprint / Python](references/ue-5.9-blueprint-python.md) |
| 5.9 StateTree and PCG authoring/evaluation | [StateTree / PCG](references/ue-5.9-statetree-pcg.md) |
| 5.9 Dataflow, CurveAtlas, enums/structs, Deformer Graph and sequence validation | [Data and graphs](references/ue-5.9-dataflow-data-tools.md) |
| 5.9 Geometry, StaticMesh, Texture and TextureGraph contracts | [Geometry / texture tools](references/ue-5.9-geometry-texture-tools.md) |
| 5.9 MetaSound, audio, Media, Control Rig and official MRQ/MRG Python workflows | [Audio / media / render](references/ue-5.9-audio-media-tools.md) |
| 5.9 ABP visibility limits, BehaviorTree/EQS, NavMesh, Input and UI diagnostics | [Animation / AI / UI](references/ue-5.9-animation-ai-tools.md) |
| 5.9 UMG, scene capture, profiling and editor tools | [Editor tools](references/ue-5.9-editor-tools.md) |
| Materials, statistics, diff and MI | Sibling [material skill](../unreal-material-artist/SKILL.md) |
| Niagara stack/renderer/user parameters/compile | Sibling [Niagara skill](../niagara-vfx-artist/SKILL.md) |
| Sequencer and Control Rig, background versus active-timeline limits | Sibling [Sequencer skill](../unreal-sequencer/SKILL.md) |
| Atlas generation/import/handoff | Sibling [flipbook skill](../vfx-flipbook-generator/SKILL.md) |
| Safe scoped implementation, source navigation and failures | [Developer workflow](references/developer-workflow.md), [debugging](references/debugging-and-source-navigation.md) |
| Gameplay/ABP/UI/GAS/PCG runtime cases | [Runtime acceptance](references/runtime-acceptance.md) |
| Legacy graph/programming/animation/domain workflows | [Blueprint](references/blueprint-programming-mcp.md), [graph inspection](references/blueprint-graph-inspection.md), [animation](references/animation-state-machines-mcp.md), [domains](references/official-domain-workflows.md) |

Image capture uses `scripts/capture.py`: 5.9 `SceneCaptureToolset` renders an
explicit pose offscreen; 5.8 uses `EditorAppToolset.CaptureViewport`. Preserve
raw MCP image blocks: a 5.9 `urn:toolresult` correlation string is not a file or
URL. Inspect images before claiming visual acceptance. A thumbnail is not a
simulation preview, and different frame hashes alone do not prove motion.

Keep originals and dirty state intact. Create test/candidate assets in a
scoped folder, save only the intended packages, and never invoke Save All,
clear unrelated dirty flags or overwrite a user's active runtime session.
Separate readback, compilation, editor evaluation, visual checks and runtime
acceptance in the report. UE 5.9 tests do not establish UE 5.8 regression
coverage. Raw evidence and machine paths belong in session output, not skills.
