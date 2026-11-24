# UE 5.9 MCP client and transport

How `scripts/builtin_mcp.py` and the `scripts/ue_mcp` package talk to Epic's
MCP server in a UE 5.9 editor. Capability findings per domain are in the
[5.9 audit](ue-5.9-preview-audit.md).

## Contents

- [Server contract](#server-contract)
- [Starting the server](#starting-the-server)
- [Discovery](#discovery)
- [Command line](#command-line)
- [Official Python through MCP](#official-python-through-mcp)
- [Batch: ordered steps and writes](#batch-ordered-steps-and-writes)
- [Schema cache and sessions](#schema-cache-and-sessions)
- [Code layout](#code-layout)
- [Limits and safety](#limits-and-safety)
- [验证记录](#验证记录)

## Server contract

- Endpoint: `http://127.0.0.1:<port>/mcp`, Streamable HTTP POST. A `tools/call`
  response is either one JSON body or an SSE stream; the client reads both.
- Protocol `2025-11-25`. Keep `Mcp-Session-Id` and send
  `notifications/initialized` before other session methods.
- `initialize` returns `com.epicgames.unrealengine/instance` metadata: PID,
  engine version and CL, engine directory and the absolute project file. The
  client also checks the OS process that owns the port on every run.
- Project Settings **MCP Toolset Servers** (`MCPClientToolset`) is the opposite
  direction: it makes UE a client of another server. It is not the endpoint an
  agent connects to.

## Starting the server

- Enable the `ModelContextProtocol` plugin and the official toolset plugins
  for the domain.
- Persistent start: in `Editor / General / ModelContextProtocolSettings` set
  `bAutoStartServer=true`, `ServerUrlPath=/mcp`, `ServerPortNumber` and
  `bEnableToolSearch=true`. Config-driven auto-start skips commandlets.
- One-off authorized launch: `-ModelContextProtocolStartServer
  -ModelContextProtocolPort=<port>`.
- `builtin_mcp.py ensure` checks readiness and explains these routes. It never
  launches or restarts an editor.
- With two editors, keep port 8000 for the stable setup and use 8001 for the
  test editor. One editor owns one port.
- After launch, poll `--timeout 5 status` against a bounded deadline while
  reading the startup log. A successful `initialize` is not readiness: refresh
  `list-toolsets`, confirm the domain is registered, then make a safe state
  read such as `EditorAppToolset.IsPIERunning`.

## Discovery

`tools/list` decides the mode. The client detects it without changing editor
settings.

| `tools/list` shows | Mode | How tools are described |
|---|---|---|
| `list_toolsets`, `describe_toolsets`, `describe_tools`, `call_tool` | Search mode | Batched toolset discovery; `describe_tools` for one tool |
| Qualified tool names | Native mode | Read every page of `tools/list` |

- Search mode can list bare plugin tools next to the four meta-tools. Call
  those by their bare name without `--toolset`; see
  [direct tools](ue-5.9-mcp-canvas-plugins.md).
- Toolset names resolve from a unique class suffix (`MaterialToolset`).
  Mistyped toolset, tool or argument names are rejected locally with a
  suggestion. Required and unknown argument names are checked before dispatch.
- `isError=true` is a failure. A schema that is missing or carries a discovery
  error is never dispatched.
- Tool names are PascalCase and arguments camelCase. Copy them from the live
  schema; never derive one by renaming a UE 5.8 call.
- A missing toolset can mean a disabled plugin or a stale inventory. Refresh
  discovery and check the plugin descriptor before reporting a gap.
- Plugins can register after startup. After a late registration or an
  in-process reload, refresh both `list-tools` and `list-toolsets` with
  `--refresh-schema`, or use `--no-cache --new-session`. A held client calls
  `reinitialize()`. `--no-cache` alone keeps the session's inventory.

## Command line

Global options go before the command: `--url`, `--expect-project`, `--out`,
`--timeout`, `--json`, `--no-cache`, `--refresh-schema`, `--new-session`.

```powershell
python scripts/builtin_mcp.py --no-cache --new-session status
python scripts/builtin_mcp.py --refresh-schema list-toolsets
python scripts/builtin_mcp.py list-tools
python scripts/builtin_mcp.py describe-toolset BlueprintToolset --brief
python scripts/builtin_mcp.py describe-tool BlueprintToolset AddVariable
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorAppToolset
python scripts/builtin_mcp.py call <tool> --toolset <toolset> --args-file <session>/args.json
python scripts/builtin_mcp.py --out <session>/schema.json describe-toolset NiagaraToolset_System
python scripts/builtin_mcp.py inventory --output <session>/inventory.json
```

- `status` prints the listener's process, executable, project, engine version
  and current level. `status` and `ensure` report a failed state read as
  `ready=false` with a nonzero exit code, including a slow-task refusal.
- View large toolsets with `--brief` (one signature line per tool) and keep
  full schemas in files with `--out`.
- Use `--args-file` for non-trivial JSON on PowerShell. Large Unicode payloads
  go through UTF-8 stdin or a file because Windows limits argument length.
- In Git Bash set `MSYS_NO_PATHCONV=1`, or `/Game/...` arguments are rewritten
  to filesystem paths.
- On Windows write large or CJK output with `--out <file>`, or set
  `PYTHONUTF8=1` for a Python process that reads the pipe.
- The server handles calls one at a time; parallel calls gain nothing.
- `run-script` is the UE 5.8 executor and is refused here. Use
  `execute-python`.

## Official Python through MCP

`PythonScriptingTools` exposes `read_me`, `execute_python`, `search_symbols`
and `get_symbol`.

```powershell
python scripts/builtin_mcp.py python-readme
python scripts/builtin_mcp.py call get_symbol --toolset PythonScriptingTools --args-file <session>/symbol.json
python scripts/builtin_mcp.py execute-python <session>/probe.py
```

- Read `python-readme` once per conversation and look each Unreal API up with
  `search_symbols` / `get_symbol` before calling it.
- A script runs on the game thread in a fresh namespace. `unreal`, `asyncio`
  and `call_tool` are available and top-level `await` works. The final
  expression is the return value; `print` goes to LogPython.
- Compose registered tools with `await call_tool(full_name, **arguments)` and
  read their exact return fields.
- Yield with `await asyncio.sleep(0)` between costly chunks. Blocking
  `time.sleep` and synchronous network or process calls are rejected.
- Prefer a domain tool over equivalent Python.

## Batch: ordered steps and writes

`builtin_mcp.py batch <file.jsonl>` runs one step per line in a shared session:

```json
{"label": "set roughness", "toolset": "MaterialInstanceToolset", "tool": "SetScalarParameter", "args": {"instance": {"refPath": "/Game/M/MI_X.MI_X"}, "name": "Roughness", "value": 0.4}, "readback": {"toolset": "MaterialInstanceToolset", "tool": "GetScalarParameter", "args": {"instance": {"refPath": "/Game/M/MI_X.MI_X"}, "name": "Roughness"}}, "expect": 0.4}
{"label": "save", "toolset": "AssetToolset", "tool": "SaveAsset", "args": {"assetPath": "/Game/M/MI_X"}}
```

- Run `--dry-run` first. It checks every tool and every schema-required
  argument against the live schema and stops.
- Steps run in order. The first `error`, `readback_error` or `mismatch` stops
  the batch and later steps are `skipped`; `--continue-on-error` keeps going.
- `expect` compares the readback: equal for scalars (float32 tolerance 1e-6,
  booleans strict), key subset for objects. A `{"refPath": ...}` expectation
  also matches a bare path string.
- Execution is refused during PIE. `--allow-pie` is for PIE-aware reads.
- Every package the steps name is checked before and after. A failed dirty
  precheck refuses the batch. `left_dirty` lists packages left unsaved that
  were clean or absent before, and the CLI exits 1. A failed postcheck keeps
  the completed steps and reports unknown state.
- Put each save in its own final step, naming only the intended package.
- A batch is ordered, not atomic. Steps before a failure stay applied. Read
  the state back before deciding what to do; never replay the file.
- `--out <file>` writes full per-step results and prints the summary.

## Schema cache and sessions

- State lives under `%LOCALAPPDATA%/unreal-engine-mcp` (`$XDG_CACHE_HOME`
  elsewhere) in `schemas/` and `sessions/`. Override the root with
  `UE_MCP_CACHE_DIR`; use a separate root per editor.
- Schemas are cached per editor process, instance, server build and
  inventory. An instance that cannot be identified uses memory only. A tool
  error on a cached schema drops that entry for the next run.
- The session id, inventory and editor identity are saved on exit. A new run
  reuses them only when PID, process start time, executable, project path and
  engine version all match the current listener.
- UE answers a closed session with HTTP 404 without executing the request. The
  client re-initializes, re-reads identity, re-checks the project guard and
  sends that one request again. Nothing else is retried.
- `--new-session` initializes and closes a private session.

## Code layout

`scripts/builtin_mcp.py` and `scripts/python_remote.py` are entry points over
`scripts/ue_mcp`: `protocol` (messages, errors), `client` (HTTP session,
discovery, schema cache, session reuse), `schema` (brief views), `editor`
(which editor serves an endpoint, engine guard), `batch` (ordered steps with
readback), `remote` (Python Remote Execution), `capture` (scene and asset
images), `skill_api` (what sibling skills import through their `mcp.py`
shims) and `cli`.

## Limits and safety

- Epic marks `ModelContextProtocol` Experimental. The server has no auth
  layer. Keep it bound to loopback.
- Starting the server prints the UE EULA Section 6(e) notice: data sent to an
  LLM is Licensed Technology and must not become training input.
- The skill's rules for deletion, overwrite, transactions and verification
  apply on every route.

## 验证记录

- 2026-11-11，UE 5.9.0 Preview / CL 60351404：search mode 的
  `list_toolsets` / `describe_toolsets` / `describe_tools` / `call_tool`、
  native 分页、实例身份元数据、`python-readme`、`execute-python`、
  `batch --dry-run` 与实际批次均已执行。批次完成中文变量提示写入/回读、
  编译和指定保存，最终资产 clean。
- 同日：官方 Python 已验证中文返回、async composition、符号查询、编译后
  函数调用，以及阻塞 `time.sleep` 被拒绝。
- 2026-11-16：客户端复用启动期 inventory 时顶层只见 4 项，`reinitialize()`
  后恢复为 66 个直接工具 + 4 个 meta-tools。
- 未执行：非 loopback 端点、资源（resources）与 prompts。
