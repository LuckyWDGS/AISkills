# Read Blueprint logic and connections through Epic MCP

Use this when asked what an existing Blueprint does, whether its connection
lines can be obtained, or which exact branch/pin should change. This workflow
reads graph topology; it does not run the gameplay or prove every path executes.

## Read-only capture

1. Identify the intended editor/project and asset. Use `builtin_mcp.py status`,
   discover the live toolsets and inspect BlueprintTools, AssetTools and
   EditorAppToolset schemas. Do not start a custom bridge to do these reads.
2. Resolve asset searches to a package path, such as `/Game/Blueprints/BP_Player`.
   Blueprint UObject parameters use the object path
   `/Game/Blueprints/BP_Player.BP_Player`. Prefer a returned ref over constructing
   one. A generated class ending `_C` is not the Blueprint asset.
3. Check `IsPIERunning`. The tested `AssetTools.is_dirty` must run outside PIE
   and takes a **package path**. Do not stop the user's PIE automatically for
   inspection. Preserve an existing dirty state; never save or clear it to make
   a report appear clean.
4. Read parent, member variables, dispatchers and `list_graphs`. For each returned
   graph, `find_nodes` with `title: ""` and no class/entry filter lists the
   supported nodes; batch `get_node_infos` for their actual refs. Entry-only
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

Avoid `find_node_types`, `find_node_categories` and `get_node_type_pins` on the
authored asset during read-only capture: the tested implementation creates and
removes temporary nodes and can dirty the package. Do not compile, arrange,
connect, set defaults, invoke construction/gameplay, or use DSL writes merely to
inspect. An empty localized DSL is not permission to rebuild the graph.

## What the returned data means

`get_node_infos` returns node refs, `type_id` (`Category|Title`), graph positions,
and `input_pins` / `output_pins`. Each pin includes `name`, `value`, `type_id`,
`pin_id` and `connected_pins`. A PinID has this structure:

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
`get_node_infos` supplies logical endpoints and node positions, not the UI's
Bézier control points, wire routing pixels or runtime debugger trace.

Use [animation-state-machines-mcp.md](animation-state-machines-mcp.md) to inspect
pose output, transition booleans, skeleton/slot compatibility and the exact
state-topology gap. Discover dedicated StateTree, BehaviorTree and ControlRig
tools independently. A generic Blueprint graph export is not proof of complete
specialized state/tree topology or write coverage.

## Verified example and maintenance

A UE 5.8.4 first-person character read returned four graphs and 30 nodes, with
125 pins and 35 unique wire segments (13 exec, 22 data). Independently derived
input/output sets matched, all endpoints resolved, and the package stayed clean.
Move and Aim were called from input events; their axis values passed through
data wires and reroutes, while Jump/StopJumping used distinct input phases.
These are fixture-specific counts, not templates to impose on another project.

Keep actual asset paths, raw captures and crash/PIE evidence in the project's
ignored session directory. After an engine upgrade, rerun discovery and a small
read-only fixture check; revisit localized DSL, node enumeration and package-path
semantics. Do not freeze a historical tool count or patch engine files to make
an old client appear compatible. Schema changes should fail visibly and prompt
a narrow exporter update.
