# UE 5.8 built-in MCP

Use this reference for Epic's built-in MCP discovery and protocol. For a missing
operation, use public Epic editor/Python APIs through
[background Python Remote Execution](official-python-remote.md). There is no
custom-plugin transport.

## Live contract

- Endpoint: `http://127.0.0.1:8000/mcp`
- Transport: Streamable HTTP POST with JSON or SSE responses for `tools/call`
- Negotiated protocol: `2025-11-25` (also accepts older client versions and upgrades them)
- Session: retain `Mcp-Session-Id`; send `notifications/initialized` before other session methods
- Capabilities: tools with `listChanged=true`; resources currently empty; prompts unsupported
- Discovery: read all `tools/list` pages. With `bEnableToolSearch=true`, it exposes `list_toolsets`, `describe_toolset`, and `call_tool`; otherwise it exposes native qualified tool names. The client detects both modes without changing editor settings.
- Console startup syntax: `ModelContextProtocol.StartServer 8000`; stop with `ModelContextProtocol.StopServer`. Do not use mouse/keyboard to send these commands for this user unless explicitly requested; use authorized config/launch routes instead.
- Epic-only launch: enable the `ModelContextProtocol` plugin and required domain toolsets, then use `-ModelContextProtocolStartServer -ModelContextProtocolPort=8000`. The older `-StartModelContextProtocolServer` spelling is deprecated in the installed 5.8.4 source. Config-driven auto-start skips commandlets; the explicit start flag opts them in.
- Preferred persistence: set `bAutoStartServer=true`, `ServerUrlPath=/mcp`, `ServerPortNumber=8000`, and `bEnableToolSearch=true` in `Editor / General / ModelContextProtocolSettings`

The project-settings `MCPClientToolset` list is the opposite direction: it makes UE consume an external MCP server. Do not use its root URL or Legacy SSE entry to connect Codex to UE. The UE server endpoint includes `/mcp` and uses Streamable HTTP.

### UE 5.8 response-mode compatibility

The live server may return either a multi-write `text/event-stream` response or
one `application/json` response for `tools/call`, depending on the UE 5.8
build. The bundled `scripts/builtin_mcp.py` handles both. If the helper waits
for a final SSE event but the server actually returned JSON, update the helper
before declaring the official MCP unavailable. Also note that some builds
expose the underlying tools through `tools/list` but reject the legacy
top-level `list_toolsets` and `describe_toolset` calls; use the exact full tool
names from `tools/list` in that case.

Run the bundled client:

```powershell
python scripts/builtin_mcp.py status
python scripts/builtin_mcp.py ensure
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py describe-toolset EditorToolset.EditorAppToolset
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorToolset.EditorAppToolset --args '{}'
```

`ensure` checks the endpoint and explains Epic-only startup if unavailable. It never starts or relaunches an editor.

Use `--args-file <utf8-json-file>` for complex call arguments on PowerShell. The client resolves unique toolset class suffixes against the live inventory, verifies the tool is present in its schema, handles pagination and either JSON/SSE response mode, and treats MCP `isError=true` as failure. It does not switch transport or retry writes on a tool error.

## Code layout

`scripts/builtin_mcp.py` and `scripts/python_remote.py` are thin entry points
over the `scripts/ue_mcp` package: `protocol` (messages, errors), `client`
(HTTP session, discovery, schema cache, session reuse), `schema` (brief
views), `editor` (which editor serves an endpoint), `batch` (ordered steps with
readback), `remote` (Python Remote Execution), `legacy_bridge` (old
`BridgeClient`), `skill_api` (what sibling skills import through their `mcp.py`
shims) and `cli`. `scripts/live_smoke.py` checks every tool read-only against a
running editor, and `scripts/record_fixtures.py` re-records the material and
Niagara contract-test fixtures (`--check` only reports drift). Python 3.10+.

## Schema cache and call cost

Client state lives under `%LOCALAPPDATA%/unreal-engine-mcp` (`$XDG_CACHE_HOME`
elsewhere; override the root with `UE_MCP_CACHE_DIR`): `schemas/` and `sessions/`.
Search-mode toolset schemas are cached per live inventory. The cache key hashes the live `tools/list`
and toolset list, so enabling or disabling a toolset plugin starts a fresh
cache. A tool missing from a cached schema is re-checked live, and a tool error
on a cached schema deletes that entry (the call itself is never retried). Use
`--refresh-schema` to force a live read or `--no-cache` to bypass it.

Each HTTP request to the UE 5.8.4 server took ~300 ms in testing, even for a
1.7 KB `tools/list`, with background CPU throttling already off. A fresh CLI
`call` needs six (initialize, initialized, `tools/list`, `list_toolsets`, the
call, close): ~2 s. The CLI therefore keeps its session:

- The session id, inventory and serving-editor identity are saved in
  `sessions/` on exit instead of closing the session. The next run sends only
  its own call (~0.3 s measured).
- UE answers an unknown or closed session with HTTP 404 and does not execute the
  request. The client then re-initializes, re-reads the inventory and editor
  identity, re-checks `--expect-project`, and re-sends that one request. Any
  other failure is never retried.
- A session the server still accepts proves the same editor process, so the
  saved inventory and identity remain valid; a session survived 70 s idle in testing.
- If a saved identity contradicts `--expect-project`, the client re-validates
  with a fresh session before refusing.
- `--new-session` initializes and closes a private session (the old behaviour).
  Library callers get a private session unless they pass `session_dir`.

For many reads, one `run-script` is still cheaper than many `call`s. Running calls in
parallel does not help: six concurrent calls took as long as six sequential ones (the
server handles them one at a time), although a long-running script does not block
short calls made meanwhile.

## Batch: ordered steps and writes

`builtin_mcp.py batch <file.jsonl>` runs one step per line in a shared session:

```json
{"label": "set roughness", "toolset": "MaterialInstanceTools", "tool": "set_scalar_parameter", "args": {"instance": {"refPath": "/Game/M/MI_X.MI_X"}, "name": "Roughness", "value": 0.4}, "readback": {"toolset": "MaterialInstanceTools", "tool": "get_scalar_parameter", "args": {"instance": {"refPath": "/Game/M/MI_X.MI_X"}, "name": "Roughness"}}, "expect": 0.4}
{"label": "save", "toolset": "AssetTools", "tool": "save_assets", "args": {"asset_paths": ["/Game/M/MI_X"]}}
```

- Before anything runs, every tool and every schema-required argument is
  checked against the live schema (UE marks some documented-optional fields
  required; pass explicit empty values). `--dry-run` stops after this check.
- Steps run in order; the first `error`, `readback_error` or `mismatch` stops the
  batch and later steps are reported `skipped`. `--continue-on-error` keeps going.
- `expect` compares the readback result: equal for scalars, key subset for objects.
- Nothing is retried, and nothing is atomic: steps before a failure stay applied.
  Read back uncertain writes before deciding what to do next.
- `--out <file>` writes the full per-step results and prints only the summary.
  The exit code is 0 only when every step is `ok`.

## ProgrammaticToolset batching

`builtin_mcp.py run-script <file.py>` sends a script defining `run() -> dict` to
`ProgrammaticToolset.execute_tool_script`; inside it,
`execute_tool(full_tool_name, json_text)` calls any registered tool. From Python,
use `UnrealMcpClient.run_tool_script(script)`. Behaviour observed on UE 5.8.4:

- **Any failing tool call fails the whole script, even inside `try/except`.**
  Only batch calls that must succeed: take names (emitters, expressions) from a
  summary call first, and query only properties that `list_properties` reported.
- Each call still costs ~0.25 s inside the editor; batching saves HTTP round
  trips, not tool time. Skip calls you can infer (for example the expression
  class from its default object name `MaterialExpressionAdd_3`).
- Results are strict dicts: `.get(key, default)` raises. Round-trip each result
  through `json.loads(json.dumps(...))`. Object references then arrive either as
  `{"refPath": ...}` or as a bare path string; accept both.
- Some enum arguments fail inside scripts but work as direct calls (for example
  `MaterialTools.get_property_input` with `MP_CustomData0` or `MP_ShadingModel`).
  Make those calls directly from the client.
- Allowed imports: `json`, `math`, `re`, `time`, `datetime`, `copy`.

`skills/unreal-material-artist/scripts/unreal_material_tools/material_audit.py`
and `skills/niagara-vfx-artist/scripts/vfx_delivery/niagara_audit.py` are worked
examples of a read-only collector built this way.

Niagara `GetSystemCompileState` and `GetStackIssues` wait for any in-flight
compilation and can block past the client timeout; call them separately with a
bounded timeout rather than inside a batch.

## Observed inventory

The 2026-10-28 live UE 5.8.4 audit enabled `ModelContextProtocol`, `EditorToolset`,
`NiagaraToolsets` and `ConfigSettingsToolset` in one Blueprint project. It exposed
25 toolsets / 319 underlying tools in search mode. BlueprintTools contributed 53
and the five Niagara domains 56. These are plugin-dependent project counts.
See [blueprint-programming-mcp.md](blueprint-programming-mcp.md) for the
programming workflow and the observed localized DSL decompiler limitation.

Historical baseline only: the UE 5.8.0 `UnrealAI` editor exposed 54 toolsets and 833 underlying tools on 2026-07-15. This is not the 5.8.4 total, nor proof of a hotfix addition/removal: project plugins change availability. See [ue-5.8.4-audit.md](ue-5.8.4-audit.md) for the current release/source audit. Runtime discovery is authoritative.

| Area | Notable toolsets and coverage |
|---|---|
| Sequencer and Control Rig | 8 toolsets / 319 tools: sequence lifecycle, bindings, tracks, sections, keys, Control Rig, outliner, conditions, custom bindings, import/export |
| Editor assets and scene | 16 toolsets / 226 tools: actors, assets, Blueprint, DataTable/DataAsset/CurveTable, materials/instances, object properties, primitives, scene, skeletal/static meshes, strings, textures, sandboxed orchestration |
| Niagara | 5 toolsets / 56 tools: system/emitter/module/renderer editing, topology, resolved values, dependencies, components, Blueprint wrappers, script discovery |
| PCG | 2 toolsets / 31 tools: PCG graph and spatial operations |
| Editor application and UI | EditorApp (21), Logs (4), SlateInspector (14): selection, viewport, content browser, PIE, screenshots, logs, Playwright-style Slate automation |
| Blueprint | 53 typed tools for lifecycle, variables, components, functions, nodes, pins, graph inspection and mutation |
| Dataflow and UMG | Dataflow (22) and UMG (23) graph/widget creation and editing |
| Physics | PhysicsAsset (17) creation and editing |
| Plugins and build | PluginToolset (17), LiveCoding (1), GameFeatures (7), ConfigSettings (8) |
| Tests and search | AutomationTest (7), SemanticSearch hybrid vector/BM25 (2) |
| Gameplay systems | GameplayTags, GameplayCue, AttributeSet, AbilitySystem inspection, StateTree, BehaviorTree, Conversation, WorldConditions, DataRegistry |
| Skills and assistant | Agent skill list/read/create/update tools plus assistant-state inspection |

Largest individual toolsets observed: Sequencer 140, Sequencer Control Rig 72, Blueprint 53, Niagara System 46, Control Rig 44, PCG 30, UMG 23, Material 22, Keyframing 22, Skeletal Mesh 22.

## Selection rule

Always prefer built-in MCP when a discovered tool covers the operation. It provides live JSON schema, typed `refPath` object references, structured errors, direct ToolsetRegistry integration, and official UE 5.8 domain tools. This is especially valuable for Sequencer, Control Rig, Blueprint, Niagara, Slate UI automation, PCG, UMG, physics assets, automation tests, logs, and Live Coding.

Do not infer absence from this snapshot: Epic can add tools without a skill update.
Re-run live discovery, inspect likely toolsets, and use official MCP whenever
overlap appears. For a missing operation, check public Epic APIs through
[background Python Remote Execution](official-python-remote.md). Areas that
historically lacked MCP coverage include PoseSearch, Chooser, performance
snapshots and nested UPROPERTY access; recheck each operation against current
official tools and editor APIs, including their editing semantics.

Before every underlying call:

1. Run `list-toolsets` if the target toolset is unknown.
2. Run `describe-toolset <toolset> --brief`, then `describe-tool <toolset> <tool>`
   and copy the exact tool name and schema.
3. Call with the full toolset name but the short underlying tool name, for example `IsPIERunning`.
4. Treat the returned MCP text as potentially JSON-encoded; the bundled client decodes one layer automatically.

For AI/NPC or World Partition arena work, keep the existing project architecture
and apply the relevant [developer workflow](developer-workflow.md) patterns.
Choose runtime duration for the behavior under test rather than a fixed minimum.
Use instance-level material overrides where appropriate, verify external-actor
packages, and save the intended packages rather than global Save All.

For official auto-start, use `ConfigSettingsToolset.ConfigSettingsToolset` with container `Editor`, category `General`, section `ModelContextProtocolSettings`. Read the live schema and values first, then set/save the four values listed above. This keeps future sessions independent of manual startup.

## Limits and safety

- Epic marks `ModelContextProtocol` Experimental.
- The current server reports empty `serverInfo`, has no MCP auth layer, exposes no prompts, and exposes no resources in this project.
- Keep it bound to loopback. Do not expose port 8000 to a network.
- Starting the server prints the UE EULA Section 6(e) notice: data sent to an LLM is Licensed Technology, and the provider must not use it as training input.
- Apply the skill's asset deletion, overwrite, transaction, Blueprint authoring, and verification rules regardless of transport.
