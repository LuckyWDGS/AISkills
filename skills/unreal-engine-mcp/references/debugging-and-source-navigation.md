# UE failure diagnosis and source navigation

Use this when finding where behavior is implemented or diagnosing compilation,
runtime, animation, transport or crash problems. Start with the actual symptom and
reproduction context; a screenshot, disconnected MCP session or last log line
alone does not establish the cause.

## Identify the failing layer

| Observation | Evidence to collect before choosing a recovery |
|---|---|
| MCP cannot connect or times out | Exact endpoint/project, process state, MCP/server logs, request result; distinguish stale session, disabled toolset and a tool blocked on editor work |
| Editor still exists but does not answer | Current build/shader/asset work and debugger/breakpoint state; use a discovered safe state read with a short timeout, not a new write as a liveness probe |
| Blueprint/C++ compile fails | Complete relevant compiler diagnostic, asset or target, first causal error and referenced node/symbol; later generated errors may be consequences |
| Runtime behavior is wrong | Map/world, owning actor/instance, trigger, inputs, authority/local role, timestamped logs and the actual execution path if observable |
| Process exits/crash dialog appears | Matching process exit and current crash context/log/call stack; distinguish fatal crash, assertion/ensure, normal shutdown and stale crash files |
| Material/FX appears wrong | Actual component/renderer/material/texture/parameter binding and compile readiness before attributing the result to shader math |

Do not call an editor crashed merely because port 8000 is closed. Conversely,
a responsive TCP listener does not prove the game thread or requested tool is
ready. Avoid repeatedly launching requests into a busy or stopped game thread.
Resume a breakpoint or change PIE state only when required by the authorized
debugging task; do not unpause unrelated user debugging to make automation pass.

## Locate Blueprint logic and its native implementation

1. Resolve the precise asset, parent class, graph and owning instance/CDO.
   Follow [graph inspection](blueprint-graph-inspection.md) for stable node GUIDs,
   exact graph references and reciprocal pin endpoints. Start with the reported
   module ID or event, then inspect its immediate execution and data dependencies.
2. For function/interface/event nodes, resolve the actual owner and member
   identity from available node metadata and class/function information. Follow
   parent calls, interface implementers, macro/function libraries and dispatchers.
   If metadata omits the target, state that gap rather than infer the owner from
   the displayed title. Asset references identify dependencies, not executed calls.
3. Search the relevant project `Source`, project `Plugins` and `Config` paths
   first with `rg`/`rg --files`, then the selected engine's owning module/plugin.
   Use exact symbols and asset paths to narrow the search. Inspect `.Build.cs`,
   `.Target.cs` and `.uplugin` when module/dependency ownership matters; generated
   `Intermediate` files are evidence of a build, not the source to fix.
4. Map names carefully: a Chinese node title, `DisplayName`, Python `ScriptName`,
   C++ member and generated `_Implementation`/`Execute_...` entry can differ.
   Inspect the declaration/UFUNCTION metadata and definition before naming a file
   or calling an API. Follow BlueprintNativeEvent/BlueprintImplementableEvent and
   interface dispatch to the actual override when relevant.
5. Trace the code that produced the value or error, not only the receiving node.
   For an MCP failure, resolve the discovered tool's registered implementation
   and its input schema before blaming Blueprint logic. Use installed source or
   documented runtime signatures; do not patch Epic code to bypass a tool gap.

Blueprint `.uasset`/`.umap` packages are binary. Use official asset/graph APIs for
their contents, not a text search pretending to read their logic. Content search,
Find References or AssetRegistry results can miss soft/dynamically constructed
paths, reflection/delegate bindings and disabled plugin content. State the search
scope and distinguish direct evidence from possible runtime callers.

Match source to the running engine version, plugin revision and loaded build.
Live Coding patches and stale binaries can make the disk source differ from the
running code. An installed engine may lack the relevant source or debug symbols;
report the confirmed module/symbol and missing evidence instead of fabricating
a source line. Link `file:line` only after reading that exact file and line.

## Follow the data and lifecycle

Choose the relevant checks; do not run every row for every bug.

| Symptom | High-value checks |
|---|---|
| Input/event never fires | Enhanced Input phase and mapping context; possession/local player; component activation; actual event binding; parent behavior and input consumption |
| `Accessed None`, invalid cast or stale reference | First failing pin and object lifetime; spawn/initialization order; world and class; async completion after destroy/unpossess; CDO versus runtime instance. Add validity handling only when the missing object is an expected case |
| Delayed, repeated or missing action | Delay/Sequence branch semantics, re-entry and retrigger behavior, timer ownership/handle, duplicate delegate binding, latent cancellation and EndPlay cleanup |
| Wrong value despite correct defaults | The real runtime writer, construction script, inherited/component overrides, spawn parameters, config/data assets, replication/RepNotify and animation update order |
| ABP transition/pose does not happen | Actual mesh/AnimClass/skeleton and instance; final Output Pose and StateResult; directed transition rule and current inputs; sync groups, slot/group, montage interruption and blend timing |
| AI state/task stalls | Task lifecycle start/finish/abort; Blackboard/property-binding types; decorator/transition evaluation; possession, navmesh reachability and perception input |
| Server/client disagree | Authority and owning connection, RPC route, replicated state/RepNotify, relevant net mode and actual client presentation path |
| Material/Niagara parameter has no effect | Live renderer/component assignment, parent/MI overrides, exact parameter identifier/namespace and data binding; system compile/stack issues, bounds and culling |
| Performance regresses | Reproduction scene and build/platform, game/render/GPU owner, trace or timing evidence; check repeated scans, new Tick work, allocations and FX/animation cost before changing architecture |

For animation multithreading, preserve the project's property-access/thread-safe
update model. Do not add arbitrary UObject/actor calls to worker-thread evaluation
as a quick diagnostic. Empty generic state-node enumeration is a known coverage
limit; follow [animation inspection](animation-state-machines-mcp.md), not an
assumption that the machine has no states.

## Preserve crash evidence before recovery

Inspect the selected project's `Saved/Logs` and `Saved/Crashes` when present,
plus the matching CrashReportClient output if needed. Correlate modification
times, process/project identity and the crash identifier from the context file.
Keep the relevant log slice, `CrashContext.runtime-xml`, assertion/fatal text and
available call stack/minidump path under ignored session output. Do not dump
entire unrelated logs or personal data into the handoff.

Read the **first causal diagnostic and the crash stack together**. Last-written
log lines may be unrelated or missing buffered output. An ensure can be nonfatal;
a transport timeout can occur while compilation is healthy. Identify whether the
stack names an Epic module, project/plugin code or automation entry point, and
record the confidence and any missing symbols. A stack frame is an investigation
lead, not proof that its module introduced the fault.

Once a specific API invocation has caused a crash, do not repeat it on the
original asset to confirm the same result. Inspect its implementation/contract
and choose a safe public alternative or a disposable reproduction within scope.
Preserve unsaved work when possible. Do not delete `Saved`, `Intermediate`, DDC,
logs or crash reports, disable unrelated plugins, kill/relaunch the editor or
rebuild the entire engine as a generic first response. Recovery should target
the evidenced layer and stay within the user's requested restart/setup scope.

## Test one explanation and close the loop

Keep a short evidence chain: observed failure → candidate cause → supporting
node/value/source/log → discriminating check → result → scoped fix. Prefer a
read-only observation or minimal reproduction over a broad speculative rewrite.
If a check fails to support the explanation, update it before making more changes.
For an uncertain write, apply the [timeout/readback rule](developer-workflow.md#make-changes-recoverable-and-unambiguous).

Temporary diagnostics should identify the module ID, owner instance, relevant
values and role/time when needed. Use supported official logs or instrumentation;
do not claim breakpoint stepping, trace capture, animation-state inspection or
executed-pin coverage merely because graph reads are available. If the live tool
does not provide execution evidence, label static conclusions as static and
record the runtime observation that remains necessary.

Fix the cause without masking it by disconnecting behavior, suppressing errors,
clearing dirty flags, changing the editor locale or adding an unconditional delay.
An expected optional reference can need a validity branch; an initialization bug
usually needs the correct ownership/order/event contract. Compile/build and
exercise the original failing trigger as appropriate to the change, then follow
the [delivery workflow](developer-workflow.md#validate-the-changed-contract).
Report confirmed cause versus remaining hypothesis, exact changed locations,
evidence, validation and any remaining reproduction limit.
