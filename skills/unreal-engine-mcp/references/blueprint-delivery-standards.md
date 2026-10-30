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

A connected graph is not a finished graph. Lay out every authored graph so it
reads left to right without tracing wires across the canvas:

- One horizontal execution lane per event or function; execution flows left to
  right. No exec wire runs backward; a loop body sits to the right of its loop
  node, below the lane.
- Pure data nodes sit to the left of and slightly below the pin they feed.
  **Use one getter per consumer** instead of wiring one variable getter across
  the graph; getters are free.
- Lanes are separated by at least two node heights; nodes never overlap; use
  reroute (knot) nodes when a wire must bend around something.
- Split a graph that grows past about 30 nodes, or a step that repeats, into a
  named function with a clear input/output contract.
- Arrange authored nodes with `BlueprintTools.arrange_nodes` /
  `set_node_position`, then correct by hand. Never re-layout untouched nodes.
- Delete disabled or abandoned nodes (for example a disabled `Event Tick`)
  before delivery instead of leaving them greyed out.

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
- **Function descriptions and variable tooltips** (the Details-panel
  "Description" / "Tooltip") have no write route in tested UE 5.8.4: MCP
  BlueprintTools, ObjectTools (`metaData` / `newVariables` unreadable) and the
  editor Python API (`new_variables` and function-entry metadata not exposed)
  were all checked. Put the text in the frames above and include a
  function/variable description table in the handoff so the user can paste it
  into Details if they want tooltips. Recheck after engine upgrades; do not
  write a C++ plugin for it.

Comment frames are created and read through Epic's public
`BlueprintGraphEditor` API over Python Remote Execution; see
[Chinese module annotations](blueprint-programming-mcp.md#chinese-module-annotations).

## Delivery check

```powershell
python scripts/blueprint_lint.py /Game/Path/BP_Feature --out <session>/lint/BP_Feature --strict
```

The lint reads the graph (inspect_blueprint), comment frames and variable
categories without editing or saving, and reports:

| Rule | Meaning |
| --- | --- |
| `backward_exec`, `exec_lane_jump` | execution wire runs right-to-left / jumps lanes |
| `long_data_wire`, `getter_fanout` | a value wired across the graph; use a local getter or reroute |
| `node_overlap`, `wire_crossings`, `large_graph` | nodes stacked, tangled rows, graph due for splitting |
| `debug_draw`, `screen_print`, `no_logging` | debug presentation left in, screen prints, no log path |
| `function_without_description`, `entry_without_frame` | missing Chinese function or module frame |
| `frame_not_chinese`, `frame_without_module_id`, `frame_title_too_long`, `frame_overlap` | frame quality |
| `variable_without_category` | variable left in the default category |

Geometry is estimated from positions and pin counts, so treat layout counts as
pointers to review. Deliver with zero warnings, or list each remaining warning
with its reason in the handoff.
