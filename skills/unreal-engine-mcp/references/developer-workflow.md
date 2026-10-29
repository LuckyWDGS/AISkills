# Scoped UE development and delivery

Read this for implementation, refactoring or repair across Blueprints, animation,
C++ and their asset dependencies. For explanation-only tasks, use
[graph inspection](blueprint-graph-inspection.md); for a failure, also use
[debugging and source navigation](debugging-and-source-navigation.md).

## Resolve the actual implementation

Translate the request into an observable trigger and result: who invokes it,
which actor/animation instance owns it, when it runs, and which values change.
Use the user's existing requirements as the acceptance criteria; ask only about
ambiguities that materially change the behavior. Preserve Blueprint as the
requested implementation surface.

Resolve the intended running project and engine before writing. Match the
editor process/project, MCP target and engine installation; inspect the
`.uproject` association and installed `Build.version` when version matters.
On a multi-editor host, an open port alone does not identify the right project.
Keep output under the project's ignored session directory, or the authorized
workspace's ignored session directory when the project has none.

Start from the existing entry point and follow the affected path: parent/native
implementation, interfaces, components, callers, consumers and asset defaults.
Use scoped asset queries and actual references. Check relevant referencers before
changing a public function signature, variable type, parameter identifier or asset
path. Registry references may omit dynamic paths and runtime-loaded content;
absence from that search is not proof that no caller exists.

Keep the existing ownership and event model. Do not introduce a second source of
truth in a widget or ABP, replace a Blueprint subsystem with C++, or move it into
a plugin solely to make automation easier. Prefer existing UE events, timers,
components and data assets over new per-frame world scans. Editor Python is
authoring/diagnostic code, not the shipped gameplay implementation.

## Make changes recoverable and unambiguous

Before mutation, record only what is needed to review and recover this change:

- Exact asset/package/graph references; affected node GUIDs, pins, links, defaults
  and relevant properties. Include annotation membership for comment-only work.
- Existing dirty state and relevant source-control changes. Do not revert,
  reload, clear dirty flags or save unrelated user work as housekeeping.
- Expected changes, including nodes/edges to replace and dependencies whose
  interface or generated class may be affected.

Read-only snapshots may span several calls. If topology changes during capture,
repeat the affected read and report the inconsistent snapshot; do not diagnose
broken wires from a mixture of two editor states. If the user changes the target
during authoring, re-read before applying the remaining plan.

Use exact discovered types and returned references. A `refPath` can become stale
after compile/reinstance, reload or editor restart; resolve it again before the
next write. Check existing nodes, module IDs and connections before creating
objects, so rerunning a repair does not duplicate its implementation.

Use UE transactions where the actual editing API supports them. A transaction
does not make several MCP calls atomic, guarantee rollback on an exception, or
back up a saved binary package. For a substantial rewrite, preserve a recoverable
source-control revision or targeted asset backup before saving. Do not create a
backup asset for every small edit.

A write timeout means **unknown completion**, not confirmed failure. Read back
the affected graph/properties and logs before retrying. Classify the operation as
applied, partial, absent or still running. Retry only the missing portion when
safe; do not blindly create another node, bind another delegate or replay a DSL.
Reconcile a partial edit using the recorded plan while preserving concurrent work.

Keep the user's window state unchanged. Do not activate an editor, open/focus a
graph or send console keystrokes merely to execute or arrange code. Use supported
background APIs and read-only model data. If a required operation has only a UI
route, explain the specific gap before requesting that UI action; do not switch
to UI automatically.

## Annotate the authored module

Follow the shared [Chinese annotation convention](blueprint-programming-mcp.md#chinese-module-annotations).
Use a stable module ID in the comment frame and, where useful, in temporary
diagnostic logs. Explain ownership, entry, significant values and timing rather
than narrating every node. Preserve existing parameter names and bindings.

For several modules or an existing project index, keep a compact entry in the
project's established documentation location:

| 模块 ID / 中文名称 | 资产 / 图 / 入口 | 关键参数、依赖 | 验证与已知限制 |
|---|---|---|---|
| `BP.BeginPlay.PrintSequence` / 启动分支打印 | target asset / EventGraph / BeginPlay | Then 0 intentionally unused; cumulative delays | topology + compile; runtime result only if exercised |

This is an example index shape, not a new runtime registry or a mandatory file
for small tasks. Project-specific paths and results belong in that project, not
in the reusable skill. Keep temporary trace flags opt-in or scoped to the test;
avoid unbounded Tick prints and remove diagnostic-only bindings/timers afterward.
Keep logs that the user explicitly requested as part of the feature.

## Validate the changed contract

Choose checks according to the change and existing project policy:

| Change | Relevant evidence |
|---|---|
| Explanation/read-only audit | Existing graph/pin/default reads and their coverage; no compile, save or PIE solely to inspect |
| Comments or layout only | Chinese text, membership and readability; unchanged logic nodes, pins, values and links; compile if the editor operation requires it; no PIE just for comments |
| Gameplay, animation or async behavior | Affected topology/defaults, compile result, logs and a bounded check of the changed trigger/result, including relevant failure/cancellation paths |
| Public contract or shared dependency | Affected callers/children and relevant dependent compile/build checks; network-role or platform checks only when those behaviors are in scope |
| C++ implementation | Correct project/editor target and toolchain, build result and loaded-code state; runtime check for the changed behavior when feasible |

Arrange only newly created or deliberately repositioned nodes. Avoid a whole-graph
layout for a local edit; comment-only work should preserve logic-node positions.
Read back actual values and connections before saving. Compare compiler warnings
to the baseline, follow the project's warning policy, and report pre-existing
warnings separately from newly introduced problems.

Control PIE/Simulate only as required by the current task and without changing
window layout. Detect an existing user session first; do not stop or restart it
for an unrelated check. Configure a supported background test when available,
bound its duration, and end only the session started for this task. If the
required runtime path cannot be exercised without interrupting the user, report
the remaining check instead of claiming it passed.

Save the intended packages only within the authorized edit. A target already
dirty before the task may contain user edits: report that saving it also persists
those edits. World Partition changes can dirty external-actor packages; resolve
and save the relevant packages rather than invoking global Save All. Verify the
save result and dirty state with the correct package-path semantics.

For C++ iteration, distinguish an implementation-body update from reflected
declaration, class-layout, constructor-default or module/build changes. Check the
current UE Live Coding support before relying on a patch. A successful patch is
not proof that existing instances/CDOs received new defaults. If a full build and
restart is needed, preserve work and coordinate the interruption within the task;
do not restart automatically as a generic recovery step.

Deliver the observed behavior, target asset/graph/module ID, what changed, checks
actually performed, and material remaining limits. For a repair, connect the root
cause to the evidence and fix. Include exact source links when verified; do not
describe unexecuted runtime checks as successful.

## When the task involves AI crowds

Apply these patterns only when extending the corresponding project architecture
or addressing measured crowd cost. Reuse a registry and cached target/LOS/nav
queries instead of per-controller full-world scans; bound stuck retries and
failure backoff. Keep team filtering, target retention and last-known-position
behavior explicit. Reduce idle work before adding another ticking controller.

Separate animation/render/ragdoll costs from decision costs. Evaluate animation
budgets, LOD, visibility-based pose ticking and bounded death simulation against
gameplay requirements; off-screen pose updates may still drive required events.
When reusable AI already lives in a runtime plugin, keep game-specific health,
weapons and presentation behind its adapter and preserve existing Blueprint paths
with thin facades. This is not a requirement to create a plugin for ordinary AI.
Validate the actual spawn/target/move/attack/end-play path for the changed feature,
with build and runtime duration chosen for that behavior.
