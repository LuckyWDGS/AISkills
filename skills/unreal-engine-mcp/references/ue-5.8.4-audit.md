# UE 5.8.4 MCP maintenance audit

Checked 2026-10-28 (America/Los_Angeles).

## Version and release evidence

The installed engine's `Engine/Build/Build.version` reports UE 5.8.4,
CL 58902052, compatible CL 55116800, branch `++UE5+Release-5.8`.
Use Build.version rather than directory names as version evidence.

- [UE 5.8 release notes](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes)
  introduce the experimental Unreal MCP server and mention an animation
  assistant toolset. These are 5.8 release features, not demonstrated 5.8.4 additions.
- [5.8.4 Hotfix Released](https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775)
  was published 2026-10-20. Its published changes do not announce additional
  MCP tools. They do include material Usage Flags cache refresh, root-pin undo,
  shader compiler fixes, and a Niagara audio sampling DI shutdown assertion fix.
- No 5.8.5 hotfix announcement was returned by the official forum search in
  this audit. This is a dated search result, not a permanent latest-version claim.

A live tool count alone cannot identify hotfix changes. Compare two snapshots
from the same project, enabled plugins, and discovery mode before claiming
tools were added/removed in a particular patch. The old 54/833 count is a
project-specific 5.8.0 baseline with no complete schema diff established here.

## Installed Epic source

The relevant plugins ship with the engine:

- `Experimental/ModelContextProtocol`: HTTP MCP server, search/native modes,
  protocol/session support. It is disabled by default in the plugin descriptor.
- `Experimental/ToolsetRegistry`: typed engine tool discovery and execution.
- `Experimental/Toolsets/EditorToolset`: MaterialTools (22), MI tools (13),
  ObjectTools (6), TextureTools (2), AssetTools (21), ProgrammaticToolset (2),
  plus scene, Blueprint, and other editor domains.
- `Experimental/Toolsets/NiagaraToolsets`: System, Assets, Component,
  Blueprint, and Info domains; schemas, summaries, topology, data/stack editing,
  emitters/modules/renderers, user variables, compile/issue diagnostics.
- Additional official plugin families include Sequencer/Control Rig,
  PCG, UMG, physics, Slate inspection, logs, settings, automation tests,
  Gameplay Tags/GAS/StateTree/AI, data registries, and plugin/build tooling.

Source presence does not prove a plugin is enabled or a tool is loaded.
Discover the active project before calls. Do not enable the entire AllToolsets
aggregator merely to hide one missing domain dependency.

## Live validation

The same-day live audit enabled Epic's ModelContextProtocol, EditorToolset,
NiagaraToolsets and ConfigSettingsToolset in a Blueprint project. The editor
restarted normally and auto-started `http://127.0.0.1:8000/mcp`; official settings
readback confirmed `/mcp`, port 8000, auto-start and search mode. No UnrealBridge
plugin was installed or used. Inventory: **25 toolsets / 319 tools**, including
BlueprintTools 53 and the five Niagara domains 56. These are project counts.

Successful read-only checks included Blueprint parent/member/functions/graphs,
CDO and components, actual nodes/pins/connections, official sandboxed batching,
scene and logs, material nodes/parameters/properties, texture dimensions, Niagara
summary/topology/renderer schema/compile state/stack issues, and settings readback.
The audited Blueprint, material and template packages remained clean. This audit
does not prove asset writes, Blueprint compilation or debugger stepping. The
follow-up also exercised official PIE/Simulate start/stop; that is a smoke test,
not validation of newly authored gameplay.

Two maintenance findings change the workflow:

1. In the Chinese editor, Blueprint DSL readback returned empty strings for
   nonempty graphs (9-node function and 15-node event graph). Structured node/pin
   reads worked. The installed decompiler compares `Exec` against localized pin
   type IDs such as `执行`. Use official node/pin tools and verify DSL completeness
   before replaying it; no engine patch or bridge is needed for that route.
2. Niagara diagnostics initially waited on an unopened template's compilation,
   including the engine's 120-second compile-wait timeout. Opening the intended
   asset with official OpenEditorForAsset allowed compilation to finish; compile
   and issues reads then succeeded (UpToDate, no errors/warnings; 6 info notices).

The user's primary workflow is Blueprint/gameplay programming. See
[blueprint-programming-mcp.md](blueprint-programming-mcp.md). The former blanket
policy to discourage Blueprint and ask again before graph edits is superseded;
follow the user's requested implementation surface and validate scoped changes.

### Animation and AI programming extension

The follow-up live audit read 18 graphs from an existing AnimBlueprint,
including two state machines, state pose graphs and transition rules, plus
two graphs from a copy-pose ABP. Official node/pin reads covered pose chains,
BlendSpace inputs and boolean transition rules. ObjectTools read BlendSpace
axes/samples/skeleton and Montage slot tracks/segments/blend values.

The state-machine containers returned empty `find_nodes` lists. Installed
`BlueprintGraphEditor.cpp::ListAllNodes` enumerates UK2Node; animation
state/transition/entry nodes derive from UEdGraphNode instead. This is a real
inspection boundary, not an empty state machine. The node catalog includes
an animation state-machine node, but full topology authoring was not tested.

The catalog query also exposed a mutation hidden behind a query-shaped API:
`_BlueprintCache.get_macros` temporarily adds/removes macros in the supplied
graph. It marked the inspected ABP dirty. Twenty graph-node listings and five
detailed node/pin reads still matched the earlier results. The asset was not
saved. `get_node_type_pins` also creates/removes a temporary node by design.
Future read-only audits should avoid these catalog/pin-type queries on authored
assets; use existing-node reads or a separately authorized candidate.

Installed AnimationAssistantToolset source defines eight toolsets for Control
Rig and Sequencer (319 decorated tools), not a dedicated gameplay ABP,
BlendSpace or Montage asset-authoring toolset. StateTreeToolset defines nine
inspection tools; AIModuleToolset defines seven BehaviorTree inspection tools.
No dedicated state/tree topology authoring operations were found in those
packages. The follow-up enabled all three plugins and verified the live inventory:
eight animation toolsets / 319 tools plus StateTreeTools / 9 and BehaviorTreeTools
/ 7, growing the project total to **35 toolsets / 654 tools**. This corrects an
earlier arithmetic total of 419 animation tools; no tool was removed by a patch.

ControlRigTools successfully read two graphs, their nodes, hierarchy/bones and
member variables from an existing foot-IK rig and controls from a first-person
rig. Package-path dirty checks outside PIE were false afterward. Enabled-content
searches found no LevelSequence, StateTree or BehaviorTree fixture; those asset
operations remain untested despite successful tool registration/schema reads.

A reviewed script run through the official editor Python console also verified
`unreal.AnimationLibrary` (the ScriptName of UAnimationBlueprintLibrary), read
Montage Notify tracks/events, and found no dirty content/map packages. Native
AnimBlueprint/Montage/BlendSpace factories and Notify/NotifyState/sync-marker/
curve editing method signatures were available. Writes were not executed. This
is an Epic editor API fallback route, not an additional MCP capability or a
custom bridge dependency.

### Crash investigation and diagnostic restart

The previous editor crashed after about 61 minutes in an RHI/D3D12 shader-resource
path, with a VSM page-marking breadcrumb. The last MCP event preceded it by about
44 minutes; the evidence does not establish MCP as the cause. A follow-up kept
DX12 and temporarily disabled VSM via a launch-only INI override, verified by
SearchCVars. The project renderer INI was not changed. The baseline and subsequent
animation/AI-plugin launch completed render and PIE smoke checks without an
observed repeat during the bounded audit. A short observation cannot establish a
permanent fix or isolate VSM as the root cause. Keep machine-specific crash dumps,
timings and launch details in session evidence, not in the reusable skill.

See [animation-state-machines-mcp.md](animation-state-machines-mcp.md) for
task-specific routes and acceptance checks. Prefer a supported UE editor/UI or
public Epic API route for a missing MCP operation before a custom adapter.

## Maintenance boundary

1. Epic MCP owns covered UE reads/writes, compile/issue queries, asset/scene
   operations, and registered-tool orchestration.
2. Local skills own artistic decisions, contracts, reference/image processing,
   comparisons, reports, and delivery evidence. These do not require custom C++.
3. UnrealBridge is an optional adapter for specific proven gaps. Record the
   operation, live tools checked, version, and successful readback. Recheck the
   gap after engine upgrades; do not port new official tools into custom wrappers.

Legacy `BridgeClient` pipelines remain present for compatibility. Their
ToolsetRegistry calls or `use_official_toolsets=true` flags do not make their
transport Epic-only. The material `official_toolsets_bridge.py` CLI now uses
direct HTTP by default, with explicit, reasoned legacy fallback only.

## Refresh procedure

Run the bundled client against the target editor:

```powershell
python scripts/builtin_mcp.py status
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py inventory --output <session-path>/ue-mcp-inventory.json
python scripts/builtin_mcp.py describe-toolset MaterialTools
python scripts/builtin_mcp.py describe-toolset ProgrammaticToolset
```

Keep full inventories and live evidence in the workspace session directory.
Use this reference for reusable conclusions, not machine-specific asset paths.
