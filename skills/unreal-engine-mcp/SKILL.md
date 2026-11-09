---
name: unreal-engine-mcp
description: Drive a running Unreal Engine 5.8+ editor through Epic's built-in MCP server (127.0.0.1:8000/mcp) and, for verified MCP gaps, Epic's Python Remote Execution. Use to inspect, implement and debug Blueprints, Animation Blueprints, state machines, PCG graphs and scatter tools, actors, assets and levels, and their C++ dependencies; for graph connections, source navigation, runtime/crash diagnosis and editor automation. Also the shared transport for the material, Niagara and flipbook UE skills.
---

# Unreal Engine MCP

Use Epic's built-in MCP server (UE 5.8+) as the editor interface. The scripts need Python 3.10+. For an
operation MCP does not cover, use public `unreal.*` APIs through Epic's
[Python Remote Execution](references/official-python-remote.md). There is no
custom plugin or TCP bridge: UnrealBridge is retired and must not be installed,
started or suggested.

Follow the [shared UE conventions](references/shared-conventions.md): background
editor connections only (no window focus/move/resize, console keystrokes or UI
automation unless the user asks for that UI operation, and never as a fallback),
and Chinese annotations on modules you author or change.

For implementation or repair, read [developer workflow](references/developer-workflow.md).
For code lookup, errors or crashes, read [debugging and source navigation](references/debugging-and-source-navigation.md).
For capability discovery, plugin selection, Enhanced Input, UI/data/GAS/testing
tasks, read the [official capability map](references/official-capability-map.md).
For PCG graph authoring, scatter tools, Blueprint wrappers and evaluated outputs,
read [PCG through official MCP](references/pcg-mcp.md). `scripts/pcg_inspect.py`
reads real pins/edges and graph parameters without executing or generating content.
For UMG/MVVM, GAS, DataRegistry, PhysicsAsset or Dataflow implementation,
read the relevant section of [official domain workflows](references/official-domain-workflows.md).
For programmer tasks, start with [Blueprint programming](references/blueprint-programming-mcp.md),
[logic and connection inspection](references/blueprint-graph-inspection.md), or
[animation and state machines](references/animation-state-machines-mcp.md).
`scripts/inspect_blueprint.py` captures existing nodes/pins and verifies both ends
of each wire without authoring, compiling or saving the asset;
`scripts/blueprint_lint.py` builds on it to check layout, debug leftovers, logging
and Chinese annotations read-only. `scripts/blueprint_normalize.py` and
`scripts/blueprint_layout.py` clean up and lay out authored graphs.

## Transport routing

Every individual operation goes through the first route that covers it:

1. **Built-in MCP tool**, discovered live from the target editor
   (`scripts/builtin_mcp.py`). Includes `ProgrammaticToolset` for batching
   registered tools; it is not an unrestricted Python console.
2. **Public Epic editor/Python API** through background Remote Execution
   (`scripts/python_remote.py`), only after searching the current toolsets and
   inspecting the candidate schema. Return to MCP for the next covered step.

If neither covers the operation, report the gap (operation, toolsets checked,
engine version) instead of patching engine files or writing a plugin. Fewer
round trips alone do not justify leaving MCP. A specifically requested transport
override applies to that operation; a historical opt-in or faster bulk read is
not the default route for future tasks. Covered writes stay on MCP.

Discovery rules:

- Read `tools/list` first. If it exposes `list_toolsets` / `describe_toolset` /
  `call_tool`, the client uses search mode; otherwise native qualified names.
  Static inventories in references are orientation only; runtime schema wins.
- A missing toolset can mean its Epic plugin is disabled. Check the installed
  engine's plugin descriptor and domain dependencies before calling it a gap;
  enable the official plugin within the user's authorized setup scope and refresh.
- Before the first call in a domain, run `describe-toolset <toolset> --brief`
  (one signature line per tool), then `describe-tool <toolset> <tool>` for the
  full schema and enum values of each tool you will call. Do not dump a full
  `describe-toolset` into context: NiagaraToolset_System is ~600 KB, its brief
  view ~7 KB. Never guess tool names, arguments, or enum values.
- If a domain tool fails or lacks a getter, inspect the target's official
  `ObjectTools.list_properties` schema before declaring an MCP gap. Supported
  reflected properties may cover the operation; verify the complete value after
  a write, including struct fields that control resolution or scope.

```powershell
python scripts/builtin_mcp.py status                 # includes the serving editor's project and level
python scripts/builtin_mcp.py ensure
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py describe-toolset MaterialTools --brief
python scripts/builtin_mcp.py describe-tool MaterialTools get_property_input
python scripts/builtin_mcp.py --expect-project <ProjectName> call IsPIERunning --toolset EditorAppToolset --args '{}'
python scripts/builtin_mcp.py call get_current_level --toolset SceneTools --args-file <session>/args.json
python scripts/builtin_mcp.py run-script <session>/reads.py   # ProgrammaticToolset, def run() -> dict
python scripts/builtin_mcp.py batch <session>/steps.jsonl --dry-run   # validate, then run without --dry-run
python scripts/python_remote.py --project <ProjectName> exec --file <session>/probe.py
python scripts/builtin_mcp.py --out <session>/niagara-schema.json describe-tool NiagaraToolset_System GetEmitterData
python scripts/capture.py viewport --pose x,y,z,pitch,yaw,roll --frames 3 --out-dir <session>/captures   # never moves the user's camera
python scripts/capture.py asset /Game/M/M_X --out-dir <session>/captures   # editor thumbnail
python scripts/live_smoke.py --project <ProjectName> --out <session>/smoke.json   # sampled reads; retain evidence and separate collected/skipped from passes
python scripts/live_smoke.py --project <ProjectName> --write   # plus the write paths in /Game/CodexTemp/LiveSmokeWrite, deleted afterwards (~4 min)
python scripts/record_fixtures.py --project <ProjectName> --check   # after an engine upgrade: contract fixtures still match?
```

Toolset names may be given as the unique class suffix (`SceneTools`); the client
resolves it against the live inventory. Use `--args-file` for non-trivial JSON
on PowerShell. The CLI keeps its MCP session between runs, so a repeated `call`
avoids repeated MCP handshakes; each run still verifies the current serving process.
`--new-session` opts out. Mistyped toolset, tool or
argument names are rejected locally with a did-you-mean suggestion; UE itself
silently ignores unknown argument names. In Git Bash set
`MSYS_NO_PATHCONV=1`, or `/Game/...` arguments are rewritten to filesystem paths. Parallel calls are
serialized by the server, so batch with `run-script` instead. On Windows, write
large or CJK output with the global `--out <file>` (UTF-8) instead of piping it, or set `PYTHONUTF8=1`
for any Python that reads the pipe; a GBK console reader garbles UTF-8 text.

Choose the multi-step route by what failure must look like:

- **Many reads** → `run-script`. One editor round trip, but one failing call
  fails the whole script; read the
  [ProgrammaticToolset rules](references/builtin-mcp.md#programmatictoolset-batching) first.
- **Writes or ordered steps** → `batch <file.jsonl>`. One request per step in a
  shared session, each with its own result; validates every tool and required
  argument first, stops at the first failure, and can read back each step with
  an `expect` check; it refuses to run during PIE and reports referenced packages
  left unsaved (`left_dirty`). Run `--dry-run` first and put the save step
  (`AssetTools.save_assets` with the intended packages only) on its own line.
  See [batch](references/builtin-mcp.md#batch-ordered-steps-and-writes).

Startup: enable `ModelContextProtocol` plus the needed domain toolset plugins and
set `bAutoStartServer=true`, or launch with `-ModelContextProtocolStartServer
-ModelContextProtocolPort=8000` for an authorized launch. `ensure` only checks
the endpoint and explains these routes; it never starts or relaunches an editor.
Only one editor can own port 8000. `status` reports the listening process's
`.uproject`, engine version and current level; on a multi-editor host pass
`--expect-project <name-or-absolute.uproject>` (or set `UE_MCP_PROJECT`) so every command refuses an
endpoint served by another project, and pass `--project` to `python_remote.py`.
Use the full project path to distinguish same-named checkouts. A resumed token
never substitutes for a fresh identity check; `--refresh-schema` refreshes both
the inventory and tool schemas after plugin changes.

Common asset work that live UE 5.8 MCP covers:

- Texture import: `TextureTools.import_file`, then `ObjectTools.set_properties` and `AssetTools.save_assets`.
- Material graph authoring: `MaterialTools.create_material/add_expression/connect_*/recompile`; use `MaterialInstanceTools` for instance parameters.
- Niagara: create from a system template, add Epic's `/Niagara/DefaultAssets/Templates/Emitters/LocationBasedRibbon.LocationBasedRibbon`, then use `GetRendererSchema`, `SetRendererData`, `SetStackInputData`, compile-state, and stack-issue tools. Find templates by the `RibbonRenderer=1` asset tag rather than name alone.

Do not use the Project Settings **MCP Toolset Servers** entry as the agent-to-UE endpoint. That list makes UE act as an MCP client. The UE server uses `/mcp` with Streamable HTTP, not the root URL or legacy GET `/sse`.

Read [builtin-mcp.md](references/builtin-mcp.md) for protocol and selection guidance, and [ue-5.8.4-audit.md](references/ue-5.8.4-audit.md) for the release/source audit. Runtime schema always wins over recorded tool counts.

## Shared material / Niagara routing

The `unreal-material-artist`, `niagara-vfx-artist`, `vfx-flipbook-generator` and `unreal-sequencer` skills use this same routing (`unreal-sequencer` covers Level Sequences, cameras and cinematics through the Sequencer toolsets). Standard asset, material graph, MI, texture import/property, Niagara stack/renderer, compile/issue, scene, and capture operations go directly through Epic MCP. Image capture uses `scripts/capture.py` (`EditorAppToolset.CaptureViewport` / `CaptureAssetImage`, `mcp_capture/1` reports). Read `ProgrammaticToolset.get_execution_environment` before its first script.

Local image processing, reference locks, visual comparison, manifests, and report packaging stay local: they are workflow code. Their editor-connected tools all run on Epic MCP; none constructs a plugin client.

## Field-tested UE 5.8 MCP notes

These notes were verified during a World Partition arena workflow and are
useful when the editor exposes the same UE 5.8 MCP implementation:

- `tools/list` is the reliable live inventory. Some UE 5.8 builds return HTTP
  400 for the older top-level `list_toolsets` / `describe_toolset` calls even
  though the full tool names are present in `tools/list`; prefer the exact
  full names from that inventory when this happens.
- UE 5.8 can return `application/json` for `tools/call` despite advertising
  `text/event-stream`. The bundled `scripts/builtin_mcp.py` accepts both modes;
  if a copied older helper reports an SSE timeout, update it before writing
  hand-written transport code.
- In the current Object/Scene tool schemas, fields described as optional may
  still be marked required. Pass explicit empty values (`name: ""`,
  `tag: ""`, `collision_channels: []`, and `null` for object filters) rather
  than omitting them.
- For per-instance skeletal team colors, edit the actor's skeletal mesh
  component with `ObjectTools.set_properties` and a JSON `overrideMaterials`
  array. Do not change the shared `USkeletalMesh` asset; cover every material
  slot and read the property back before playtesting.
- World Partition actors live in external packages. `AssetTools.save_assets`
  may report success while the map package remains dirty. Resolve and verify
  the affected external packages and save only the intended changes through
  supported background APIs; do not invoke global Save All or reload user edits.
- For an explicit actor-removal request, audit by label and generated class,
  remove only the resolved actor with `SceneTools.remove_from_scene`, re-scan
  the level, then check relevant spawners in a bounded background runtime test
  when required by the task; preserve an existing user PIE session.
- Keep project-specific actor counts, asset paths, and verification results in
  the project's `.codex/session/HANDOFF.md`; this skill should retain only the
  reusable UE/MCP procedure.

For AI/crowd and World Partition work, read the conditional patterns in
[developer workflow](references/developer-workflow.md#when-the-task-involves-ai-crowds).
Keep the existing Blueprint/project architecture; a runtime plugin or fixed test
duration is not a prerequisite for an ordinary gameplay task.

## Waiting for the editor to become ready (post-launch / post-relaunch)

Poll `scripts/builtin_mcp.py --timeout 5 status` using the current environment's
background-command or short-wait tools while inspecting startup logs. Use a
bounded deadline and continue communicating while the editor loads. A successful
initialize alone is not editor readiness: refresh `list-toolsets`, verify that
the required domain has registered, then make a safe editor-state read such as
`EditorAppToolset.IsPIERunning` or `SceneTools.get_current_level`.

## Blueprint and programming workflow

Blueprint is the user's preferred implementation surface for gameplay and
programming work. When a task requests Blueprint logic, proceed with official
BlueprintTools, ActorTools, ObjectTools, and the related domain tools; do not
redirect to C++ or request a second implementation-language confirmation.
Recommend C++ for a demonstrated API limitation, measured performance need, or
an existing project convention, while preserving the requested Blueprint interface.

Read [references/blueprint-programming-mcp.md](references/blueprint-programming-mcp.md)
for official graph inspection, component/default edits, batching, compile/log
verification, and the observed Chinese-editor DSL limitation.

For a gameplay feature, follow [Blueprint delivery standards](references/blueprint-delivery-standards.md):

1. Write a feature brief (player-facing result, states, systems, tuning surface,
   edge cases, verification plan) and show it before wiring.
2. Deliver production presentation, never debug drawing: a spline/Niagara
   trajectory with its own material, real Chaos physics with physical materials.
   Route visuals through `unreal-material-artist` / `niagara-vfx-artist`.
3. Build the `bDebugLog` + `DebugLog` log path first and log state transitions
   and failure branches; diagnose from `LogsToolset.GetLogEntries` before guessing.
4. Inspect a named graph with `scripts/blueprint_normalize.py <asset> --graph <name>`
   and `scripts/blueprint_layout.py <asset> --graph <name>` first. Apply only
   justified edits within the authorized scope, with a project guard and backup
   or candidate. Normalize preserves unproven variable owner/Target/local scope;
   shared pure-call copies need input/default readback, compile and behavior
   verification. Layout checks an unchanged logic signature before saving.
5. Explain every function, module and variable group in Chinese: comment
   frames, stable module IDs, supported categories and a parameter/function
   description table. Use official metadata writes where available. The bundled
   MCPBlueprintMetadata plugin and `scripts/blueprint_tooltips.py` are optional
   extensions only for a separately requested hover-metadata workflow.
6. Verify changed behavior with runtime state and log numbers using relevant
   [runtime acceptance cases](references/runtime-acceptance.md); screenshot only
   to answer a named visual question. Record unrun cases explicitly.
7. Finish with `scripts/blueprint_lint.py --strict`.

For Animation Blueprints, animation state machines, BlendSpaces, Montages,
StateTree and Behavior Trees, read
[references/animation-state-machines-mcp.md](references/animation-state-machines-mcp.md).
Treat these as normal programmer tasks. A Sequencer/Control Rig toolset does
not imply complete gameplay animation graph or AI tree authoring coverage.

## Blueprint review after authoring

After authoring/modifying a BP graph within the user's requested task:

On the official path, inspect the existing graphs and pins, make scoped edits,
arrange only authored nodes when needed and supported without UI activation,
read back connections and values, and run `compile_blueprint` for logic edits.
For annotation-only changes, verify text/membership and unchanged topology;
compile if the operation requires it. Do not re-layout the logic graph or start
PIE solely to add comments. Review compiler errors/warnings through
the returned result and LogsToolset; use a bounded PIE/Simulate check when runtime
behavior changed. Use meaningful function/variable names and keep functions
focused. Do not replay a DSL dump until its completeness is verified.

Before delivery, annotate authored Blueprint modules per the
[shared conventions](references/shared-conventions.md#chinese-module-annotations):
a Chinese comment frame with a stable module ID, purpose and entry/parameters,
reusing the ID when extending the module. Naming, categories and editor routes:
[module annotations](references/blueprint-programming-mcp.md#chinese-module-annotations).

## Change and recovery boundaries

Stay within the authorized task and targets. A requested edit includes its
necessary scoped implementation and validation; do not add another confirmation
for an already authorized action. Preserve unrelated assets, user edits and
running/debug sessions. Use supported UE transactions without treating them as
atomic rollback or saved-package backup.

Read back uncertain writes before retrying. Save only the intended packages;
do not clear dirty flags or invoke global Save All to hide side effects. Keep
project-specific snapshots, scripts, logs and handoff records in ignored session
output. Compilation, graph readback and runtime evidence are different checks;
state which were actually completed.

## Read only the relevant references

| Task | Reference |
|---|---|
| Scoped implementation, safe edits and acceptance | [Developer workflow](references/developer-workflow.md) |
| Find code, diagnose logs/runtime/crashes | [Debugging and source navigation](references/debugging-and-source-navigation.md) |
| Blueprint programming and Chinese annotations | [Blueprint programming](references/blueprint-programming-mcp.md) |
| Gameplay feature delivery: design, presentation, logs, layout, Chinese explanations, lint | [Blueprint delivery standards](references/blueprint-delivery-standards.md) |
| Read logic and actual pin connections | [Graph inspection](references/blueprint-graph-inspection.md) |
| Animation Blueprint, state machines and AI | [Animation and AI](references/animation-state-machines-mcp.md) |
| Official background Python for an MCP gap | [Epic Python Remote Execution](references/official-python-remote.md) |
| Writing an MCP executor for a plan (plan → batch) | [Porting legacy writers](references/porting-legacy-writers.md) |
| Runtime cases: gameplay/ABP, UI/MVVM, GAS, registries, PCG and physics | [Runtime acceptance](references/runtime-acceptance.md) |
| Rules shared by all five UE skills | [Shared conventions](references/shared-conventions.md) |
| MCP protocol, startup and discovery | [Built-in MCP](references/builtin-mcp.md) |
| Official domains, useful developer tasks, plugin selection and hidden side effects | [Official capability map](references/official-capability-map.md) |
| PCG graph/parameters, scatter tools, Blueprint wrappers and output diagnosis | [PCG through official MCP](references/pcg-mcp.md) |
| Implement UI/MVVM, GAS, registries, physics, PCG/Dataflow; scoped official tests | [Official domain workflows](references/official-domain-workflows.md) |
| Version/source audit and historical boundaries | [UE 5.8.4 audit](references/ue-5.8.4-audit.md) |
| Stock UE Python snippets for a Remote Execution gap | [Actors](references/ue-python-actors.md), [Assets](references/ue-python-assets.md), [Materials](references/ue-python-materials.md) |
