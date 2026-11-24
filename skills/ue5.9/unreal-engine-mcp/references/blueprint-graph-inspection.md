# Read Blueprint logic and connections through Epic MCP

Use this when asked what an existing Blueprint does, whether its connection
lines can be obtained, or which exact branch/pin should change. This workflow
reads graph topology; it does not run the gameplay or prove every path executes.

## Contents

- [Read-only capture](#read-only-capture)
- [What the returned data means](#what-the-returned-data-means)
- [Turn topology into an accurate explanation](#turn-topology-into-an-accurate-explanation)
- [Animation and specialized graphs](#animation-and-specialized-graphs)
- [Maintenance](#maintenance)
- [验证记录](#验证记录)

## Read-only capture

1. Identify the intended editor/project and asset. Use `builtin_mcp.py status`,
   discover the live toolsets and inspect the `BlueprintToolset`,
   `AssetToolset` and `EditorAppToolset` schemas.
2. Resolve asset searches to a package path, such as `/Game/Blueprints/BP_Player`.
   Blueprint UObject parameters use the object path
   `/Game/Blueprints/BP_Player.BP_Player`. Prefer a returned ref over constructing
   one. A generated class ending `_C` is not the Blueprint asset.
3. Check `IsPIERunning`. `AssetToolset.IsDirty` runs outside PIE and takes a
   **package path**. Do not stop the user's PIE automatically for
   inspection. Preserve an existing dirty state; never save or clear it to make
   a report appear clean.
4. Read parent, member variables, dispatchers and `ListGraphs`. For each returned
   graph, `FindNodes` with `title: ""` and no class/entry filter lists the
   supported nodes; batch `GetNodeInfos` for their actual refs. Entry-only
   filtering misses pure data nodes and is unsuitable for a full wire inventory.
5. Build and validate edges as below. Recheck editor state and dirty status.
   An optional second snapshot detects observed edits during capture. Multiple
   reads are not an atomic editor transaction, even when the two copies match.

Run the bundled stdlib-only exporter from the skill directory:

```powershell
python scripts/inspect_blueprint.py /Game/Blueprints/BP_Player --out <empty-output-dir> --verify-snapshot
```

It uses the official client and a fixed set of read operations. It writes
`calls.json`, `schemas.json`, `snapshot.json`, optional `snapshot-verification.json`,
`connections.json`, `connections.csv` and `report.md` to a new/empty local output
directory. Failed reads keep their partial evidence and return a nonzero exit
code. Topology errors, observed snapshot changes or a changed dirty flag also
return nonzero; a valid partial API view is not a claim of universal coverage.
For other locales, repeat `--exec-type <actual-type-id>` to add execution types.
Defaults are `Exec` and `执行`. Run `--help` for endpoint, timeout and batch size.

Keep the node-type discovery tools (node types, categories, type pins) away
from the authored asset during a read-only capture: they create and remove
temporary nodes and can dirty the package. A capture never compiles, arranges,
connects, sets defaults, invokes construction or gameplay, or writes DSL. A DSL
read that reports `bDslOmitted` is a partial view, not grounds to rebuild the
graph.

## What the returned data means

`GetNodeInfos` returns node refs, a type ID (`Category|Title`), graph positions
and input/output pins. The native fields are camelCase (`typeId`, `inputPins`,
`outputPins`, `pinId`, `connectedPins`, `indexId`). The exporter writes them
as `type_id`, `input_pins`, `output_pins`, `pin_id`, `connected_pins` and
`index_id` in its reports; use those report names for reading only and pass
the native shape back to a tool. Each pin includes `name`, `value`, its type ID,
pin ID and connected pins. A report PinID has this structure:

```json
{
  "node": {"refPath": "/Game/Blueprints/BP_Player.BP_Player:Move.K2Node_CallFunction_1"},
  "direction": "EGPD_Input",
  "index_id": 0
}
```

Use **(node refPath, direction, index_id)** as identity. Titles, pin names,
coordinates and array position are presentation, not unique IDs. Repeated
`Transition`, `Move`, `self`, split-struct or identically named pins are normal.
Do not reinterpret `index_id` as a persistent GUID across reconstruction or
editor sessions; take fresh refs after edits, compile or node replacement.

For every output link `A → B`, verify B is an input pin and that B lists A.
Independently derive directed edges from input links and compare the complete
sets. Deduplicate by the full output/input PinID pair, not by node pair. Keep
parallel data/exec edges, fanout and merges. Report dangling refs, wrong
directions, duplicate pin identities, missing returned nodes and one-sided
links; do not silently discard them or declare the asset broken when concurrent
edits or API omissions could explain the mismatch.

Classify execution/data wires using the actual pin `type_id`, not color or an
English-only label. Preserve endpoint type strings. An exec/data disagreement
at the endpoints needs investigation. Data subtype conversions and wildcard
pins can be valid; do not reject them merely because their strings differ.
Unlinked inputs can use defaults or implicit self, and unused outputs can be
intentional. Their absence of links alone is not a defect.

## Turn topology into an accurate explanation

- **Execution:** start at actual events/function entries, follow output exec
  pins, and name the selected pin for Branch, Sequence, switch and loop nodes.
  Preserve order inside each chain. Distinct events have no global order merely
  because one is drawn to the left. Latent actions, timers, async callbacks and
  delegates require their API/runtime semantics; a wire does not prove immediate
  completion or a single invocation.
- **Data:** trace the producer feeding each important input, including getter,
  pure function, struct component, conversion and default. Explain which value
  controls which operation. Pure nodes have no exec wire; do not omit their
  computation or assert they run only once without checking Blueprint semantics.
- **Reroutes:** keep every Knot node and wire segment in the raw inventory.
  For a readable explanation you may collapse a verified reroute chain into its
  source/destination and mention intermediate Knots. Maintain a visited set for
  cycles and preserve fanout; do not count collapsed paths as literal wires.
- **Functions/macros/interfaces:** a call to `Move` is a node in its caller and
  has a separate implementation graph. Inspect that graph and map call arguments
  to entry pins. The relationship is a semantic call edge, not an inter-graph
  `connected_pins` wire. Check parent/interface dispatch and external owners
  before assuming a same-named graph is the implementation. Expand relevant
  macro/collapsed graphs only as needed; mark unresolved native/external calls.
- **Input:** distinguish Enhanced Input `Started`, `Triggered`, `Completed` and
  `Canceled`, their actual links and X/Y data routing. Similar event names do not
  establish the same mapping, callback timing or input setup. Check controller/
  mapping context and movement configuration separately when they affect behavior.
- **Variables/components:** member listing describes declarations. Defaults,
  local variables, inherited properties/components, CDO settings and runtime
  instance values are different scopes. An absent getter/setter in the inspected
  graphs supports only that observation; it does not establish global non-use
  through children, bindings, reflection, other assets or runtime code.

For a concise user report, describe the asset's role and parent, its entry events,
each meaningful function and data source, and then connection coverage and any
unknowns. Include exact graph/node/pin refs when diagnosing an edit. A small flow
diagram may help; separate data arrows from exec arrows, label semantic calls,
and retain raw edge evidence rather than inventing screenshot geometry.

## Animation and specialized graphs

The tested official node enumerator returns UK2Node subclasses. It reads common
gameplay, pose and transition-rule nodes, but excludes some UEdGraphNode branches,
including animation state/entry/transition nodes and comments. Therefore a
state-machine container can return zero nodes even while its pose and transition
graphs are available. Counts describe **returned nodes and their wires**.
`GetNodeInfos` supplies logical endpoints and node positions, not the UI's
Bézier control points, wire routing pixels or runtime debugger trace.

Use [animation and AI tools](ue-5.9-animation-ai-tools.md) to inspect
pose output, transition booleans, skeleton/slot compatibility and the exact
state-topology gap. Discover dedicated StateTree, BehaviorTree and ControlRig
tools independently. A generic Blueprint graph export is not proof of complete
specialized state/tree topology or write coverage.

## Maintenance

Keep actual asset paths, raw captures and crash/PIE evidence in the project's
ignored session directory. After an engine update, rerun discovery and a small
read-only fixture check, then revisit node enumeration and package-path
semantics. A schema change should fail visibly and prompt a narrow exporter
update.

## 验证记录

- 2026-11-11，UE 5.9.0 Preview / CL 60351404：`inspect_blueprint.py` 走原生
  `BlueprintToolset` 读取拓扑、注释成员和变量分类；重复快照一致，资产 dirty
  状态不变；`blueprint_lint.py` 不经 Remote Execution。
- 同一构建：`AnimationStateMachineGraph` 容器图 `FindNodes` 返回空，状态、
  入口和过渡节点未被枚举；pose 图与 transition-rule 图中的 K2 节点可读。
- 未执行：编辑进行中的并发快照、中英文以外 locale 的 exec 类型。
