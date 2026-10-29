---
name: unreal-engine-mcp
description: Inspect, implement and debug Unreal Engine Blueprints, Animation Blueprints, state machines and their C++ or asset dependencies through Epic's official MCP. Use for UE programming, graph connections, source navigation, runtime/crash diagnosis and editor automation; prefer public Epic APIs before a narrow custom bridge for verified gaps.
---

# Unreal Engine MCP

Use Epic's standard MCP server as the primary interface on UE 5.8+. Treat the custom UnrealBridge Python bridge as an optional fallback, not a co-equal transport.

For this user, keep editor automation in background connections. Do not move,
minimize, maximize, resize or focus UE windows, or use mouse/keyboard input to
send Python through an editor console, unless the user explicitly requests that
UI operation. For a verified MCP gap, prefer Epic's own
[Python Remote Execution](references/official-python-remote.md) through its
supported local endpoint. Do not silently resume UI automation after a failure.

For implementation or repair, read [developer workflow](references/developer-workflow.md).
For code lookup, errors or crashes, read [debugging and source navigation](references/debugging-and-source-navigation.md).
For programmer tasks, start with [Blueprint programming](references/blueprint-programming-mcp.md),
[logic and connection inspection](references/blueprint-graph-inspection.md), or
[animation and state machines](references/animation-state-machines-mcp.md).
`scripts/inspect_blueprint.py` captures existing nodes/pins and verifies both ends
of each wire without authoring, compiling or saving the asset.

## Transport priority

Always prefer Epic's built-in MCP whenever its live schema covers the requested operation. Do not choose the plugin because its wrapper is shorter, its documentation is more familiar, or an older inventory omitted a recently added official tool. Epic updates become available automatically through runtime discovery.

Apply these hard routing rules:

- Read `tools/list` first. If it exposes `list_toolsets` / `describe_toolset` / `call_tool`, use search mode; otherwise use the exact native tool names and schemas. The bundled client handles both modes and pagination. Static inventories are orientation only.
- When official MCP and UnrealBridge overlap, use official MCP.
- Declare a capability gap only after searching the current official toolsets and inspecting the candidate schema.
- A missing toolset can mean its Epic plugin is disabled. Check the installed engine's plugin descriptor and required domain dependencies before calling it a capability gap; enable the needed official plugin within the user's authorized setup scope and refresh discovery.
- Keep any plugin fallback isolated to the missing operation; return to official MCP for later covered operations.
- Before arbitrary bridge Python, check the official `ProgrammaticToolset` for supported batching/orchestration.
- For an MCP gap, consider a documented Epic editor/Python API through an available supported background execution route before introducing a custom plugin. Respect this user's no-UI preference. ProgrammaticToolset orchestrates registered tools; it is not an unrestricted `unreal` Python console.

Use the bundled client from the skill directory:

```powershell
python scripts/builtin_mcp.py status
python scripts/builtin_mcp.py ensure
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py describe-toolset EditorToolset.EditorAppToolset
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorToolset.EditorAppToolset --args '{}'
```

Follow this decision sequence:

1. Run `builtin_mcp.py status` against `http://127.0.0.1:8000/mcp`.
2. Prefer Epic-only startup within the authorized setup: enable `ModelContextProtocol` plus the needed domain toolset plugins, and use `bAutoStartServer=true` or launch flags `-ModelContextProtocolStartServer -ModelContextProtocolPort=8000` for an authorized launch. `ModelContextProtocol.StartServer 8000` is the editor console command, not a reason to drive the console with mouse/keyboard. Preserve an active editor and its unsaved work. `builtin_mcp.py ensure` checks availability and explains these routes. Legacy bootstrap requires explicit `ensure --allow-bridge-bootstrap --bridge-project <target>`; never discover and start an arbitrary editor on a multi-editor host.
3. Run `list-toolsets`, then `describe-toolset <full-toolset-name>` before the first call in a domain. Never guess tool names, arguments, or enum values.
4. Call the underlying tool with the full toolset name and the short tool name from its schema.
5. If MCP cannot perform the operation, check UE's own editor/public Epic APIs next. Use `bridge.py` only for the remaining demonstrated gap or unavailable official execution route; lack of arbitrary Python in ProgrammaticToolset alone does not justify a custom plugin.

Use this fallback order for every individual operation:

1. **Built-in MCP tool** discovered live from UE.
2. **Public Epic editor/Python API** through a supported background connection, when it can perform the missing operation. Use editor UI only when explicitly requested by this user. Do not patch engine files or assume arbitrary Python is available through MCP.
3. **Narrow bridge wrapper around an Epic editor API** when the above routes cannot complete the operation. For Niagara, prefer the plugin's `get/set_official_*_data` and `add_official_module` wrappers because they call Epic's external-edit utilities.
4. **Plugin-specific helper** only for the remaining proven gap. Do not keep the rest of the workflow on the plugin after one fallback.

For common asset work, live UE 5.8 already covers the normal path:

- Texture import: `TextureTools.import_file`, then `ObjectTools.set_properties` and `AssetTools.save_assets`.
- Material graph authoring: `MaterialTools.create_material/add_expression/connect_*/recompile`; use `MaterialInstanceTools` for instance parameters.
- Niagara: create from a system template, add Epic's `/Niagara/DefaultAssets/Templates/Emitters/LocationBasedRibbon.LocationBasedRibbon`, then use `GetRendererSchema`, `SetRendererData`, `SetStackInputData`, compile-state, and stack-issue tools. Find templates by the `RibbonRenderer=1` asset tag rather than name alone.

If live MCP and supported public Epic API routes cannot perform one of these
operations, keep its proven custom-plugin fallback minimal:

- Texture: `Asset.import_texture2d_from_file`.
- Material: `Material.create_material` + `Material.apply_material_graph_ops`; validate with `get_material_graph` and `get_material_compile_errors`.
- Niagara Ribbon: `add_ribbon_renderer_to_emitter`; for renderer edits prefer `get_official_renderer_data_summary` + `set_official_renderer_data`; for stack gaps use `add_official_module` + official stack input data setters.

Do not use arbitrary persistent Python merely to batch operations that the built-in MCP already exposes. Check the built-in `ProgrammaticToolset` first; without a suitable batch surface, use official tools sequentially or a supported Epic editor API route. Fewer round trips alone do not justify a custom plugin.

Do not use the Project Settings **MCP Toolset Servers** entry as the Codex-to-UE endpoint. That list makes UE act as an MCP client. The UE server uses `/mcp` with Streamable HTTP, not the root URL or legacy GET `/sse`.

Read [builtin-mcp.md](references/builtin-mcp.md) for protocol and selection guidance, and [ue-5.8.4-audit.md](references/ue-5.8.4-audit.md) for the release/source audit and maintenance boundaries. The 54-toolset/833-tool count is a historical 5.8.0 project snapshot, not a 5.8.4 limit. Runtime schema always wins.

## Shared material / Niagara routing

The `unreal-material-artist`, `niagara-vfx-artist`, and `vfx-flipbook-generator` skills use this same discovery and transport policy. Standard asset, material graph, MI, texture import/property, Niagara stack/renderer, compile/issue, scene, and capture operations go directly through Epic MCP whenever exposed. `ProgrammaticToolset.get_execution_environment` must be read before its first script; use it to batch registered tools rather than sending arbitrary Python through the custom plugin.

Local image processing, reference locks, visual comparison, manifests, and report packaging can remain local: they are workflow code, not a reason to require an editor plugin. Legacy scripts that instantiate `BridgeClient` or reference `UnrealBridge*Library` still require the custom plugin, even when a field says `use_official_toolsets=true`. Do not call an entire legacy pipeline just to perform an operation already covered by MCP. Record any remaining fallback as one specific operation plus official discovery evidence, engine version, and readback result.

## Field-tested UE 5.8 MCP notes

These notes were verified during a World Partition arena workflow and are
useful when the editor exposes the same UE 5.8 MCP implementation:

- `tools/list` is the reliable live inventory. Some UE 5.8 builds return HTTP
  400 for the older top-level `list_toolsets` / `describe_toolset` calls even
  though the full tool names are present in `tools/list`; prefer the exact
  full names from that inventory when this happens.
- UE 5.8 can return `application/json` for `tools/call` despite advertising
  `text/event-stream`. The bundled `scripts/builtin_mcp.py` accepts both modes;
  if a copied older helper reports an SSE timeout, update it before falling
  back to UnrealBridge or hand-written transport code.
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

Do not require `bridge.py ping` for an Epic-only project. Only when already using
an explicitly selected custom-plugin fallback, check its `ready:true` before
fallback execution and select the intended project on multi-editor hosts.

## Blueprint and programming workflow

Blueprint is the user's preferred implementation surface for gameplay and
programming work. When a task requests Blueprint logic, proceed with official
BlueprintTools, ActorTools, ObjectTools, and the related domain tools; do not
redirect to C++ or request a second implementation-language confirmation.
Recommend C++ for a demonstrated API limitation, measured performance need, or
an existing project convention, while preserving the requested Blueprint interface.

Read [references/blueprint-programming-mcp.md](references/blueprint-programming-mcp.md)
for official graph inspection, component/default edits, batching, compile/log
verification, and the observed Chinese-editor DSL limitation. The legacy
`bridge-blueprint-api.md` is a fallback API reference, not the primary route.

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
focused. Do not invoke the custom plugin merely to satisfy a bridge-only lint or
layout convention. Do not replay a DSL dump until its completeness is verified.

For this user's authored modules, add a **Chinese module comment frame and
searchable textual labels** before delivery. Give the module a stable ID, a
Chinese purpose, and the relevant entry/parameters; add Chinese notes on
non-obvious nodes, timing and conditions. Reuse the module's ID when extending
it. Follow [module annotations](references/blueprint-programming-mcp.md#chinese-module-annotations)
for naming, categories and official-editor routes. This also applies to new or
modified animation, state-machine, material and Niagara modules. Inspection-only
tasks do not authorize inserting annotations into untouched assets.

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
| Read logic and actual pin connections | [Graph inspection](references/blueprint-graph-inspection.md) |
| Animation Blueprint, state machines and AI | [Animation and AI](references/animation-state-machines-mcp.md) |
| Official background Python for an MCP gap | [Epic Python Remote Execution](references/official-python-remote.md) |
| MCP protocol, startup and discovery | [Built-in MCP](references/builtin-mcp.md) |
| Version/source audit and historical boundaries | [UE 5.8.4 audit](references/ue-5.8.4-audit.md) |
| A proven remaining custom-plugin operation | [Custom bridge operations and API index](references/custom-bridge-operations.md) |
