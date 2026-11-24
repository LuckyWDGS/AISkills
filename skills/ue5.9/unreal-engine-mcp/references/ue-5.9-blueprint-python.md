# UE 5.9: native Blueprint editing and Python over MCP

Verified against 5.9.0 Preview, CL 60351404. Use the live schema on another
build. Tests used a dedicated candidate; they did not modify gameplay assets.
The initial contract audit exercised graph reads, writes, compilation and four
CDO function evaluations, without PIE. Later gameplay evidence is recorded in
[game production](game-production.md) and the dated notes below.

## Native authoring contract

`BlueprintToolsets.BlueprintToolset` owns graph authoring. Copy every name and
argument from the live schema. Examples:

| Operation | 5.9 contract |
|---|---|
| Create an Actor Blueprint | `Create(folderPath, assetName, assetType={refPath: "/Script/Engine.Actor"})` |
| Primitive member variable | `AddVariable(blueprint, name, typeName, options)`; options can contain category/tooltip/read-only/container/local-graph settings |
| Variable metadata | `Set/GetVariableCategory`, `Set/GetVariableTooltip`; native Chinese round-trip verified |
| Function metadata | `AddFunctionGraph(..., flags)` / `Set/GetFunctionFlags`; category, tooltip, access and purity round-tripped |
| Function signature | `AddFunctionParam(graph, paramName, paramType, bInputParam, options)` returns the actual `BlueprintPinID` |
| Graph topology | `GetGraph`, `FindNodes`, `GetNodeInfos`, `GetConnectedSubgraph` |
| Pins | `ConnectPins(outputPin, inputPin)`, `DisconnectPins`, `Set/GetPinValue` |
| Annotation | `AddCommentBox`, `ListCommentBoxes`, `GetCommentBoxText`, `GetNodesInCommentBox`, node notes |
| Diff | `DiffGraphs(oldGraph, newGraph)` returns node matches and typed differences |
| Compile | `CompileBlueprint(blueprint, bWarningsAsErrors)`; errors raise, success returns void |

Blueprint, graph and node inputs are real UObject references, usually
`{"refPath": "..."}`. A 5.9 pin ID uses `node`, **`indexId`**, `direction`.
`GetNodeInfos` returns `typeId`, `inputPins`, `outputPins`, `pinId` and
`connectedPins`. Those differ from the old helper's internal snake_case report
format. Never send an inspection report's normalized ID directly to a write.
Resolve the latest native pins, including direction and owner.

The test connected both data and execution pins of a pure function graph.
Setting the function's pure flag did not wire Entry to Result automatically.
Data readback alone was insufficient: before the exec link, the canonical DSL
contained the signature without a return statement. After connecting it,
`Read` returned `(return InputValue)`.

Write variable and function descriptions with the native metadata tools. Keep
Chinese purpose, inputs/outputs, side effects, caller and a stable module ID in
a comment frame. Do not infer that every native comment-membership query has
complete persisted membership after a reload; report unavailable membership
honestly.

## Native Graph DSL is the preferred scoped rewrite route

Use `BlueprintToolsets.BlueprintDslToolset`. Its `Docs` is authoritative.
Plain Blueprints use this native dialect; the remaining Python
`BlueprintDslTools` handles unsupported subclasses such as Widget/Anim/level
script Blueprints when exposed by the target. Those dialects are different.

1. `Docs()` before the first write/edit.
2. `Read(assetPath, scope)` to get canonical `dsl` and `revision`.
3. `Edit(assetPath, scope, revision, edits)` with exact `oldString` /
   `newString` replacements. Use the same asset and scope as the read.
4. Preserve the returned revision. With `bDslOmitted=true`, the predicted text
   is authoritative; with returned `dsl`, use that canonical text. Inspect
   warnings. Read back, re-resolve nodes/pins, compile and evaluate the change.

The tested edit replaced `(return InputValue)` with
`(return (+ InputValue 2.0))` in one function scope, updating its Chinese
explanation too. Native graph diff found rewired pins and a new arithmetic
node. A deliberately stale revision raised `[revision-mismatch]`; a fresh read
confirmed unchanged DSL after that rejected edit.

Scope can be the entire asset, `GraphName`, or `GraphName/EntryName`. Quote
segments with spaces or `/` using the documented backtick syntax. Entry writes
are upserts, while explicit tombstones delete. Present params/returns/locals
sections specify their exact set; omission preserves those sections. This is
why a guessed whole-document rewrite can remove a signature even when the
intended change is small.

Native DSL uses source member references such as `Actor.K2_GetActorLocation`,
not palette IDs such as `Category|Localized title`. The tested Chinese editor
returned localized node/pin type labels in topology, while native DSL used
stable source references and English pin-type spelling. The old Chinese-editor
Python DSL limitation is not a blanket 5.9 native-DSL limitation.

### Read the actual control flow, not just successful compilation

A packaged input test found an analog-input tail outside the intended position
branch in the canonical graph. It compiled, but sent keyboard and gamepad
movement together before the threshold. A no-value `(return)` also read back as
an empty branch; it did not establish the intended early exit.

For this shape, move the sequential tail into a small function and call it as
the terminal action of an explicit guard. Recheck state after an earlier branch
can change it; independent guarded calls prevent a checkpoint/menu transition
from continuing into the route driver in the same tick. Read the compiled
canonical graph and inspect every condition, continuation and side-effecting
call, then sample runtime input/state. This is a demonstrated authoring pitfall,
not a claim that all multi-statement branches or all return forms are broken.

Never weaken production movement, grant lives or teleport the player to make
an input acceptance test pass. Retain failed traces and distinguish a test
driver correction from a gameplay fix.

## Official async Python replaces the old batching pattern

`PythonScriptingTools.read_me` describes the exact running environment. Read it
once per conversation. `search_symbols` searches registered tools and the
session's Unreal Python API; `get_symbol` documents a toolset, tool, type,
method, property or tool-only struct. Search before approximating an operation
or writing an API call from memory.

`execute_python` takes a **CodeBlock object**, not a plain string:

```json
{"script":{"language":"Python","content":"await asyncio.sleep(0)\nlevel = await call_tool('EditorToolset.LevelToolset.GetCurrentLevel')\n{'level': level, 'sum': sum([2,3,4])}"}}
```

The tested result returned the actual level path, sum 9 and Chinese text.
The client provides `execute_python(script)` and
`builtin_mcp.py execute-python <file.py>` for this contract.

`unreal`, `asyncio` and `call_tool` are preimported. Each execution has a fresh
namespace; its last expression is the return value. `print` only reaches
LogPython. `call_tool` returns the tool's declared JSON-shaped value and raises
on failure. Its strict result dictionary rejects even `.get` for an undeclared
field, so inspect the actual output schema instead of guessing field names.

Use top-level `await`, and yield periodically with `await asyncio.sleep(0)`
during expensive loops. This executor runs on the game thread. Blocking calls
such as `time.sleep` were rejected before execution in the live test; use
async APIs instead. It is an unsandboxed editor interpreter, not a gameplay
implementation or an OS-task worker.

For a verified missing tool operation, look up the public API using symbols,
then call it here. The audit evaluated the compiled function on its CDO using
looked-up `load_object` and `Object.call_method('EchoProbe', args=(value,))`:
inputs `-3, 0, 2.5, 42` returned `-1, 2, 4.5, 44`. This proves sampled compiled
editor execution, not spawning, networking, BeginPlay or PIE behavior.

## 验证记录

- 2026-11-11，UE 5.9.0 Preview / CL 60351404：原生创建、变量/函数中文元数据、参
  数与双向接线、注释、编译；DSL revision/edit、stale 拒绝、graph diff；CDO 输入
  -3/0/2.5/42 得到 -1/2/4.5/44。
- 2026-11-16：独立包输入测试在 canonical graph 中发现位置分支外的模拟输入尾部；
  可编译，但会在阈值前同时发送键盘与手柄移动。
- 未执行：BeginPlay、网络与 PIE 行为。
