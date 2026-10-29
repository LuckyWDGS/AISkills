# Blueprint programming through Epic MCP

Use this for Blueprint/gameplay programming and editor automation. Blueprint is
the user's preferred implementation surface; materials and Niagara are supporting
domains. Respect the requested language and project architecture. A Blueprint
request does not need a second language-choice confirmation.

For implementation/refactoring, use [developer workflow](developer-workflow.md)
for scoped edits, uncertain-write readback and acceptance. For code lookup or a
failure, use [debugging and source navigation](debugging-and-source-navigation.md).

## Discover before implementing

Enable Epic's `ModelContextProtocol` and `EditorToolset` plugins in the intended
project. `EditorToolset` provides Blueprint, actor/components, object properties,
assets, scene, editor/PIE, logs, data assets/tables, and tool orchestration.
Use `builtin_mcp.py list-toolsets`, then describe the needed toolsets. Resolve
unique class suffixes rather than hard-coding historical Python module names.

The 2026-10-28 UE 5.8.4 live check found 53 BlueprintTools tools, 17 ActorTools,
6 ObjectTools, 20 SceneTools, 21 EditorApp tools, 4 Logs tools and 2 Programmatic
tools. These counts describe the tested build, not a required future inventory.

| Programming task | Official route to inspect first |
|---|---|
| Read existing logic | BlueprintTools.list_graphs/get_graph, find_nodes, get_node_infos; inspect pin directions, defaults and connected_pins |
| Variables and defaults | list_variables and variable metadata tools; get_default_object followed by ObjectTools.list_properties/get_properties/set_properties |
| Components and inherited templates | ActorTools.get_components/add_component and ObjectTools; use returned component refs rather than constructing CDO/template paths |
| Functions, events, dispatchers | list_functions/list_events/list_event_dispatchers and the corresponding add/parameter tools |
| Nodes and connections | find_node_types/get_node_type_pins on an authorized candidate graph (see side effects below), create_node, connect_pins, set_pin_value, arrange_nodes |
| Compile and diagnose | compile_blueprint, LogsToolset.GetLogEntries; inspect live input schema for warnings_as_errors |
| Scene and runtime verification | SceneTools and EditorAppToolset.IsPIERunning/StartPIE/StopPIE; re-read schemas before changing runtime state |
| Batch programmatic work | ProgrammaticToolset.get_execution_environment, then execute_tool_script using registered tools |

The initial read audit exercised reads, component discovery and batching against
a project character Blueprint. Treat that inventory as schema/read evidence;
write, compile and runtime claims need operation-specific results. Graph access
does not establish breakpoint, stepping or executed-pin coverage.

## Graph edits

For an existing Blueprint's logic or connection lines, use the read-only
[graph inspection workflow](blueprint-graph-inspection.md) and
`scripts/inspect_blueprint.py`. It exports actual pin endpoints and verifies
links from both directions without compiling, saving or running catalog queries.
Read the linked interpretation guidance before turning the export into a
gameplay explanation or a proposed edit.

Read existing graphs before choosing an edit. For a local change, use typed
nodes/pins and preserve unrelated branches. Discover candidate node types and
their exact pin names; do not infer them from UI labels or old inventories.
Arrange newly authored nodes only when needed, preserving unrelated layout and
the user's window state. Inspect the resulting connections/defaults, compile
logic edits and investigate errors/warnings. For comment-only work, verify frame
membership/text and unchanged logic-node positions/topology; compile if required
by the editing API. Validate changed runtime behavior with a bounded background
PIE or Simulate session when appropriate, preserving existing user sessions.

For DSL work, call `get_graph_dsl_docs` first. Do not treat the advertised
read/edit/write round trip as lossless without comparing its coverage to the
actual graph. Read the current transpiler semantics before replaying a script
over existing logic.

### Chinese module annotations

The user wants each authored module to remain easy to find for both humans and
future agents. Apply this to each new or modified module, including gameplay
Blueprints, animation/state graphs, materials and Niagara as appropriate:

- Wrap the module in a visible **Chinese comment frame**. Use a stable,
  searchable title such as `【初始化】【调试打印】【BP.BeginPlay.PrintSequence】开始运行：每隔0.3秒打印`.
  The Chinese labels and ID are textual search labels, not runtime Gameplay Tags.
  Preserve an existing module ID when extending its implementation.
- Explain the module's purpose, entry, significant parameters and important
  timing/branch conditions in the frame or relevant node comments. Add short
  Chinese comments to non-obvious nodes rather than restating every wire.
  For independent Sequence branches, explain cumulative delay versus waiting
  for the preceding branch, and document intentionally unused pins.
- Give new functions/variables/components clear names and Chinese categories
  and tooltips/descriptions where supported. Keep project/API identifiers stable;
  do not rename existing references just to translate them.
- Use a consistent comment color by role within the project and leave enough
  padding for legible labels and bubble text. Group only this module's nodes;
  do not sweep unrelated branches into the frame or reorganize the entire asset.
- Include the asset/graph and module ID in a project-local module index when
  there are several modules or an index already exists. For a small change,
  the searchable frame and a concise handoff entry are sufficient; do not create
  runtime tags, extra gameplay variables or a global registry solely for indexing.

Prefer discovered official MCP comment/metadata tools when available. In the
tested UE 5.8.4 schema, BlueprintTools has no comment-frame operation and its
UK2Node enumerator omits comment nodes. Epic's public editor Python API does
provide `BlueprintGraphEditor.get_graph_editor(graph).add_comment_to_nodes(...)`,
`list_comment_nodes()` and BlueprintEditorLibrary comment text/color accessors.
For this user, invoke that public API through Epic's
[Python Remote Execution](official-python-remote.md); do not drive the editor
console or change the user's window layout. No custom bridge is needed.
Read the installed/live signatures,
preserve UE transactions, and verify frame membership, text and unchanged pin
topology before saving. An ObjectTools property listing can expose only an
`errorMsg` schema for node classes; do not treat that as supported comment writes
or assume an `isError=false` response guarantees useful property coverage.

In the tested build, an ordinary K2 node's `NodeComment` is not exposed to Python:
`get_editor_property('node_comment')` fails, and no comment methods appear on the
node. Use native group comment frames for node/branch explanations instead of
assuming a bubble setter exists. A comment frame's editable `font_size` and
multiline `node_details` are available through `set_editor_property`; its Details
text also appears in the tooltip. Keep short Chinese titles, a searchable module
ID, and the detailed purpose/entry/timing explanation. Verify all text and frame
membership before saving. This is annotation support, not general node-property
write coverage.

Read-only inspections should report existing annotations and gaps without
adding comments, saving or clearing dirty flags.

### Chinese-editor DSL limitation observed in 5.8.4

In the tested Chinese editor, `read_graph_dsl` returned `""` for a `Move` function
whose `find_nodes` result contained 9 nodes and an EventGraph containing 15 nodes.
Direct and Programmatic calls behaved the same. `get_node_infos` successfully
returned node positions, defaults and connected pins. Its execution pin
`type_id` was localized as `执行`; installed `blueprint_dsl.py` defines
`EXEC_TYPE = 'Exec'` and compares it literally when finding entry nodes. This
explains why that decompiler can miss execution roots in the tested locale.

Use the official node/pin APIs for this case. An empty DSL does not mean an empty
graph and does not justify replacing a graph. Do not patch Epic's files, change
the user's editor language, or introduce a custom C++ bridge just for this
decompiler limitation. Recheck after upgrades.

### Node catalog queries can dirty a Blueprint

In the installed 5.8.4 implementation, `_BlueprintCache.get_macros` builds its
cache by adding and removing engine macro nodes in the supplied graph. A first
`find_node_types` or `find_node_categories` query can therefore mark its package
dirty. `get_node_type_pins` separately creates and removes a node to read pins.
Treat these as mutations when selecting the target, even though they look like
queries. Use an authorized candidate during authoring; use `get_node_infos` on
existing nodes for read-only inspection. Do not clear dirty flags or save the
asset to hide a query side effect.

The live audit observed this after querying an existing ABP's node catalog.
Twenty graph-node listings and five detailed node/pin readbacks still matched
their earlier results; the ABP had an unsaved dirty flag. This does not justify
calling these catalog queries side-effect-free.

## Animation and AI features

Read [animation-state-machines-mcp.md](animation-state-machines-mcp.md) for ABP,
animation state machines, BlendSpaces, Montages/Notifies, StateTree, Behavior
Tree and Control Rig workflows. Generic graph inspection and task Blueprint
logic do not establish specialized tree-topology authoring coverage.

## Programmer checks for a scoped gameplay feature

These are implementation decisions to verify when relevant, not claims of
additional MCP tools. Start from the existing architecture and change the
smallest complete gameplay path.

- **Input and ownership:** inspect the actual Enhanced Input phases and axis
  mapping, mapping-context setup, controller possession, local-player ownership,
  movement settings and camera component. A correct event wire cannot compensate
  for an inactive mapping context or an unpossessed pawn.
- **Functions and events:** give a function an explicit input/output contract;
  use events/delegates for asynchronous responses. Check latent-node restrictions
  in the actual graph type. Follow native/parent/interface calls before replacing
  behavior; use the interface event signature exposed by the current parent.
- **State and references:** identify who owns each value and who updates it.
  Distinguish class defaults, construction-time values, runtime component state
  and animation-instance values. Validate lifetime and object references at the
  point of use; define what happens when an async target disappears.
- **Timers and delegates:** bound repeated work, retain a timer handle when it
  needs cancellation, avoid duplicate bindings, and clean up when the owning
  actor/component ends play. Use UE gameplay timers/events for shipped behavior;
  editor Python callbacks are not the game's runtime implementation.
- **Replication:** when multiplayer is in scope, identify authority and owning
  connection, RPC direction/reliability, replicated-property/RepNotify behavior
  and the client presentation path. A local Blueprint compile or single-player
  PIE does not validate server/client behavior. Test the relevant network roles.
- **UI and reusable components:** preserve existing interfaces, dispatchers,
  component APIs and data assets instead of duplicating state in the widget or
  casting every consumer to one concrete character class. Unbind subscriptions
  when the widget/component lifecycle requires it.
- **Verification:** re-read affected pin links, variable defaults and component
  properties, compile the changed Blueprint/dependents as needed, and inspect the
  specific success, failure and cancellation paths in a bounded runtime check.
  Do not run PIE or compile solely to explain an asset during a read-only task.

## Extend with the appropriate official plugin

An absent domain in live discovery can mean a disabled plugin. Check the
installed descriptor and enable only what the project needs, then restart if
required and refresh the inventory. The tested engine also ships these official
programming-related families:

- `AutomationTestToolset`: test discovery/execution.
- `PluginToolset`, `LiveCodingToolset`: project plugin/build and C++ iteration.
- `AIModuleToolset`, `StateTreeToolset`: AI and StateTree tooling.
- `GameplayTagsToolset`, `GASToolsets`, `GameFeaturesToolset`: gameplay framework tooling.
- `SlateInspectorToolset`, `MVVMToolset`: editor UI inspection and UI binding tooling.
- `DataRegistryToolset`, `PCGToolset`: data and procedural gameplay/editor workflows.

These families were verified in installed source. A follow-up enabled and
discovered AIModuleToolset and StateTreeToolset live; the remaining listed
families were not enabled by this audit. UMG and animation tools can also live inside their owning
official plugins: inspect those descriptors instead of assuming every toolset
has a separate plugin with the same name. Do not enable `AllToolsets` merely to
work around one missing dependency.

For other programmer features, start with the existing Blueprint architecture:
input/actions and actor components, interfaces/dispatchers, data assets/tables,
UMG interaction, gameplay tags/abilities and replicated gameplay. Discover the
relevant official tools per operation and validate the changed behavior; this
task list is not a claim that every specialized editor or debugger API exists.

Check the live schema for breakpoint/debug stepping, semantic lint, specialized
graph layout, private properties and other advanced needs before declaring a
gap. Use a narrowly scoped bridge fallback only when the official operation is
actually unavailable. Keep the rest of the workflow on Epic MCP.
