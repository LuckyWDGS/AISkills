# Blueprint delivery standards

Rules for gameplay features delivered as Blueprints (a throwable, a contact
surface, a pickup, an ability). They exist because a graph can compile, be fully
wired and pass a runtime check while still being unreadable, debug-looking, hard
to diagnose and unexplained. Apply them to every authored or modified graph;
`scripts/blueprint_lint.py` checks the mechanical parts.

## 1. Design before wiring

Write a short feature brief and show it to the user before creating nodes for
anything beyond a one-node fix. It is the place to think; the graph is the
place to execute.

- **Player-facing result:** what the player sees, hears and feels at each
  state, at production quality. Name the reference if one exists.
- **States and transitions:** e.g. held -> thrown -> bouncing -> fuse -> exploded
  -> destroyed, with the event that moves between them and what each state owns
  (collision, physics, visibility, timers).
- **Systems per concern:** input, ownership, movement/physics, presentation,
  VFX/SFX, cleanup. Pick the engine system on purpose (Chaos rigid body vs.
  ProjectileMovement, spline mesh vs. Niagara ribbon) and say why.
- **Tuning surface:** the few instance-editable variables a designer will tune,
  with units and sensible ranges.
- **Failure and edge cases:** invalid owner, spawn overlap, rapid repeat input,
  destroyed while timers run, network role when multiplayer is in scope.
- **Verification plan:** which runtime state, log lines and numbers prove each
  requirement (see 3 and 5). A plan that can only be checked by looking at a
  screenshot is not finished.

### Presentation is part of the feature

Debug drawing is a development aid, never the delivered presentation:

- `DrawDebug*`, `PredictProjectilePath*` with `DrawDebugType` other than None,
  and on-screen `Print String` do not ship.
- A trajectory preview is a spline (`SplineComponent` + `SplineMeshComponent`
  segments) or a Niagara ribbon/sprite trail fed from the predicted points, with
  a dedicated material (dash/scroll, fade by distance, depth-fade at
  intersections) and a landing marker (decal or mesh with its own material).
  Instanced dots are acceptable only with a purpose-made material and fade.
- Materials go through `unreal-material-artist`, effects through
  `niagara-vfx-artist`; do not ship engine default materials on a visible
  gameplay element.
- Physical objects behave physically: a Chaos rigid body with mass, linear and
  angular damping, CCD for fast objects, a Physical Material for friction and
  restitution, sensible sleep thresholds, and the right collision channels per
  state (held: no collision; thrown: blocks world, ignores the thrower until
  clear). Check bounce, roll and rest in the runtime test, not only the launch.

## 2. Evidence: state and logs first, screenshots only for visual questions

- Gameplay logic is verified by reading runtime state (actor location and
  velocity samples, component properties through ObjectTools, timer state) and
  by log lines, in a bounded PIE/Simulate session. Record numbers: fuse time,
  bounce count, rest position, spawn/destroy counts.
- Take a screenshot only to answer a visual question that state cannot answer
  ("is the trajectory readable against the bright floor?"). Name the question
  before capturing, look at the image, and report the answer. Capturing the
  editor viewport or the graph editor proves nothing about behavior.
- Do not loop on captures when a capture route fails; switch to state/log
  evidence and report the capture gap.

## 3. Logging is part of the implementation

Every authored gameplay Blueprint gets a log path from the start, so problems
are diagnosed from the log instead of guesswork:

- A `bDebugLog` boolean (category `<功能>|调试`, instance editable) and one
  `DebugLog(Message)` function: Branch on `bDebugLog` -> `Print String` with
  **Print to Screen off, Print to Log on**, text prefixed
  `[<BP name>][<module ID>] `. Keep it the only place that prints.
- Log every state transition, every failure branch (cast failed, invalid
  reference, timer cleared early) and the key numbers (launch velocity, fuse
  start/end time, hit actor). Warnings for broken invariants log regardless of
  `bDebugLog`.
- Read them with `LogsToolset.GetLogEntries` during verification: pass
  `category: "LogBlueprintUserMessages"` explicitly (without it the call fails with
  "Log category ... not found") and the Blueprint name as a plain `pattern` (no
  brackets). Quote the relevant lines in the report. A test that switches
  `bDebugLog` on at runtime misses lines written before it did (BeginPlay). `bDebugLog` defaults to false at delivery unless the user wants it on.

## 4. Readable graph layout

A connected graph is not a finished graph, and a lint pass is not proof of a
readable one. Lay out every authored graph so it reads left to right without
tracing wires across the canvas:

- One horizontal execution lane per event or function; execution flows left to
  right. No exec wire runs backward. A loop continues the lane from `Completed`;
  its body, an else branch or another extra exec output is a row dropped just
  below what is already placed.
- The pure (data) nodes feeding an exec node form a small tree in columns
  directly to its left, below the exec wire, each output aimed at the pin it
  feeds. Data wires never run right to left and never pass through other nodes.
- Prefer nearby Getters for newly authored nodes when the variable owner,
  Target, member/local scope and read timing are explicit. Preserve existing
  SET outputs and external/inherited/local Getters when that identity is not
  proven; a long wire is preferable to reading another object or a later value.
- A pure node may be copied near consumers only when its type, every input and
  Target link, defaults and evaluation behavior are preserved. Random, time,
  mutable state, references and containers need particular care. Do not claim
  equivalence merely because the node is pure or the graph compiles.
- **An exec node's output read past the next exec node** (for example a trace
  hit used after a loop) is stored in a local variable right after the producer
  and read with getters where needed. The editor offers no reroute-node action
  through MCP or Python, so long skipping wires cannot be bent around nodes.
- Nodes never overlap. Split a graph that grows past about 30 nodes, or a step
  that repeats, into a named function with a clear input/output contract.
- Delete disabled or abandoned nodes (for example a disabled `Event Tick`)
  before delivery instead of leaving them greyed out.

Review a named graph first. A request to organize it authorizes scoped layout;
otherwise preserve the user's arrangement. Before writes use a candidate or
durable backup. `--all` is reserved for an explicitly requested whole-asset scope:

```powershell
python scripts/blueprint_normalize.py /Game/Path/BP_Feature --graph UpdatePreview --project <Project>
python scripts/blueprint_layout.py /Game/Path/BP_Feature --graph UpdatePreview --project <Project>
# After reviewing the proposed scope; writes require a confirmed idle editor:
python scripts/blueprint_normalize.py /Game/Path/BP_Feature --graph UpdatePreview --write --project <Project>
python scripts/blueprint_layout.py /Game/Path/BP_Feature --graph UpdatePreview --write --reframe --project <Project>
```

`blueprint_normalize.py` copies supported pure-call/operator nodes after checking
pin schemas and input readback; it reports and preserves variable Getters and
SET outputs. A partial failure leaves unsaved work for inspection; it is not a
transactional rewrite. `blueprint_layout.py` places nodes with
size estimates calibrated on UE 5.8 (`blueprint_geometry.py`) and rebuilds each
comment frame around its module and compares node/pin/default/link signatures
before saving. The observed frame membership cache depends on the graph having
been shown and can be lost on duplication. Never open a tab to populate it;
for several frames pass `--frame-map K2Node_Event_0=BP.Feature.Init,...` or report
unresolved membership. Equal native overlap or multiple matching map entries
remain `unmapped`; review the mapping instead of choosing the first module.
The helper creates a replacement, verifies text/style/members, then removes
the old frame. Candidate failures retain the original and remove only the
helper's candidate; an unconfirmed removal reports partial work without saving.
`BlueprintTools.arrange_nodes` alone does not
produce this layout.

## 5. Chinese explanations for functions, variables and modules

- **Functions:** inside every authored function graph, a Chinese comment frame
  around the entry node. The title is short:
  `【函数】UpdateHeldPreview`. The details text says what it does, its
  inputs and outputs, its side effects, and who calls it and when.
- **Event modules:** each event chain in a Chinese module frame with a stable
  module ID: `【松手投掷】【BP.Throw.Release】`. Keep the title on one line
  (about 40 characters); put the explanation in the frame's details text
  (`node_details`). Frames must not overlap or share members.
- **Variables:** Chinese category paths (`抛物线投掷|运行时`,
  `抛物线投掷|设置`, `抛物线投掷|调试`) and Chinese-explained names in the
  module frames that use them.
- **Descriptions:** explain authored functions, member variables and non-obvious
  locals in Chinese, with units, defaults, owners and side effects. Prefer
  official metadata tools when live discovery proves coverage. Without a stock
  hover-metadata write route, the default delivery is the comment frames plus a
  table keyed by asset/graph/module ID and identifier; missing hover text does
  not require C++ or make that delivery incomplete.
- **Optional hover-metadata extension:** only when the user explicitly requests
  the extension workflow, use `assets/plugins/MCPBlueprintMetadata` and:

  ```powershell
  python scripts/install_blueprint_metadata_plugin.py --uproject <Project>.uproject --engine-root <UE root>
  python scripts/blueprint_tooltips.py /Game/Path/BP_Feature --spec <session>/tooltips.json --write --project <Project>
  ```

  Installing adds C++, compiler and restart requirements. Do not install it
  automatically for annotations. Use existing authorization for an extension;
  otherwise finish the official comment/table delivery first. Preserve an
  already installed extension and use it only within the task's scope; verify
  metadata readback when used. Do not restart to obtain hover text.

Comment frames are created and read through Epic's public
`BlueprintGraphEditor` API over Python Remote Execution; see
[Chinese module annotations](blueprint-programming-mcp.md#chinese-module-annotations).

## Saving and backups

Edits made through MCP and editor Python live only in the editor until the asset
is saved; closing or restarting the editor without saving discards them, and a
backup made with `AssetTools.duplicate` is an unsaved asset that disappears too.
The version on disk is the real backup when the asset was clean before your
edits. At handoff, state which assets are unsaved, and before any step that needs
an editor restart (installing a plugin) ask the user to save, or save with their
explicit consent, and confirm afterwards that the reloaded asset still contains
the delivery (`blueprint_lint.py`, `blueprint_tooltips.py`).

## Delivery check

```powershell
python scripts/blueprint_lint.py /Game/Path/BP_Feature --out <session>/lint/BP_Feature --strict
```

The lint reads the graph (inspect_blueprint), comment frames and variable
categories without editing or saving, and reports:

| Rule | Meaning |
| --- | --- |
| `backward_exec`, `exec_lane_jump` | execution wire runs right-to-left / jumps lanes |
| `backward_data_wire` | data wire runs right-to-left; the data node belongs left of its consumer |
| `wire_through_node` | wires pass through other nodes (more than 2 per graph) |
| `long_data_wire`, `getter_fanout` | a value wired across the graph; use a local getter or a local variable |
| `node_overlap`, `wire_crossings`, `large_graph` | nodes stacked, tangled rows, graph due for splitting |
| `debug_draw`, `screen_print`, `no_logging` | debug presentation left in, screen prints, no log path |
| `function_without_description`, `entry_without_frame` | missing Chinese function or module frame |
| `frame_not_chinese`, `frame_without_module_id`, `frame_title_too_long`, `frame_overlap` | frame quality |
| `variable_without_category` | variable left in the default category |

Geometry is estimated by `blueprint_geometry.py` from pins, default-value widgets
and titles (the API has no node sizes), so treat layout counts as pointers to
review. Deliver with zero warnings, or list each remaining warning
with its reason in the handoff.

For behavior changes, select cases from [runtime acceptance](runtime-acceptance.md).
Compile, lint and graph readback do not replace the jump/overlap/physics/animation
lifecycle checks relevant to the feature.
