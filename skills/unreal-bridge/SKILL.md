---
name: unreal-bridge
description: Operate a running Unreal Engine editor through Epic's built-in UE 5.8+ MCP as the authoritative primary interface, using the custom UnrealBridge TCP/Python plugin only for live-proven capability gaps or emergency startup fallback. Use when Codex needs to inspect or modify UE assets, levels, Blueprints, Niagara, Sequencer, Control Rig, UMG, PCG, gameplay systems, editor UI/state, tests, logs, performance, or execute Python inside Unreal.
---

# UnrealBridge

Use Epic's standard MCP server as the primary interface on UE 5.8+. Treat the custom UnrealBridge Python bridge as an optional fallback, not a co-equal transport.

## Transport priority

Always prefer Epic's built-in MCP whenever its live schema covers the requested operation. Do not choose the plugin because its wrapper is shorter, its documentation is more familiar, or an older inventory omitted a recently added official tool. Epic updates become available automatically through runtime discovery.

Apply these hard routing rules:

- Treat live `list_toolsets` and `describe_toolset` results as authoritative. Static inventories are orientation only.
- When official MCP and UnrealBridge overlap, use official MCP.
- Declare a capability gap only after searching the current official toolsets and inspecting the candidate schema.
- Keep any plugin fallback isolated to the missing operation; return to official MCP for later covered operations.
- Before arbitrary bridge Python, check the official `ProgrammaticToolset` for supported batching/orchestration.

Use the bundled client from the skill directory:

```powershell
python scripts/builtin_mcp.py status
python scripts/builtin_mcp.py ensure
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py describe-toolset EditorToolset.EditorAppToolset
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorToolset.EditorAppToolset --args '{}'
```

Follow this decision sequence:

1. Run `builtin_mcp.py status` against `http://127.0.0.1:8000/mcp`.
2. Keep official `bAutoStartServer=true` so normal sessions require no plugin bootstrap. If an already-running editor has MCP unavailable, run `builtin_mcp.py ensure`; it uses the custom bridge only as a last-resort bootstrap to execute Epic's `ModelContextProtocol.StartServer 8000`, then returns immediately to official MCP.
3. Run `list-toolsets`, then `describe-toolset <full-toolset-name>` before the first call in a domain. Never guess tool names, arguments, or enum values.
4. Call the underlying tool with the full toolset name and the short tool name from its schema.
5. Fall back to `bridge.py` only when live official discovery proves no suitable operation, official MCP cannot be started, or the task requires Python capability outside the official ProgrammaticToolset sandbox.

Use this three-tier fallback order for every individual operation:

1. **Built-in MCP tool** discovered live from UE.
2. **Narrow bridge wrapper around an Epic editor API** when the built-in server does not expose that operation. For Niagara, prefer the plugin's `get/set_official_*_data` and `add_official_module` wrappers because they call Epic's external-edit utilities.
3. **Plugin-specific helper** only for the remaining proven gap. Do not keep the rest of the workflow on the plugin after one fallback.

For common asset work, live UE 5.8 already covers the normal path:

- Texture import: `TextureTools.import_file`, then `ObjectTools.set_properties` and `AssetTools.save_assets`.
- Material graph authoring: `MaterialTools.create_material/add_expression/connect_*/recompile`; use `MaterialInstanceTools` for instance parameters.
- Niagara: create from a system template, add Epic's `/Niagara/DefaultAssets/Templates/Emitters/LocationBasedRibbon.LocationBasedRibbon`, then use `GetRendererSchema`, `SetRendererData`, `SetStackInputData`, compile-state, and stack-issue tools. Find templates by the `RibbonRenderer=1` asset tag rather than name alone.

If those live tools are absent, keep the plugin fallback minimal:

- Texture: `Asset.import_texture2d_from_file`.
- Material: `Material.create_material` + `Material.apply_material_graph_ops`; validate with `get_material_graph` and `get_material_compile_errors`.
- Niagara Ribbon: `add_ribbon_renderer_to_emitter`; for renderer edits prefer `get_official_renderer_data_summary` + `set_official_renderer_data`; for stack gaps use `add_official_module` + official stack input data setters.

Do not use arbitrary persistent Python merely to batch operations that the built-in MCP already exposes. Check the built-in `ProgrammaticToolset` first; if no official batch surface exists, a narrow plugin batch is preferable to reimplementing editor semantics with raw `unreal.*`.

Do not use the Project Settings **MCP Toolset Servers** entry as the Codex-to-UE endpoint. That list makes UE act as an MCP client. The UE server uses `/mcp` with Streamable HTTP, not the root URL or legacy GET `/sse`.

Read [builtin-mcp.md](references/builtin-mcp.md) for the validated protocol, observed 54-toolset/833-tool inventory, selection guidance, and limitations. Runtime schema always wins over the snapshot.

## Field-tested UE 5.8 MCP notes

These notes were verified during a World Partition arena workflow and are
useful when the editor exposes the same UE 5.8 MCP implementation:

- `tools/list` is the reliable live inventory. Some UE 5.8 builds return HTTP
  400 for the older top-level `list_toolsets` / `describe_toolset` calls even
  though the full tool names are present in `tools/list`; prefer the exact
  full names from that inventory when this happens.
- UE 5.8 can return `application/json` for `tools/call` despite advertising
  `text/event-stream`. The bundled `scripts/builtin_mcp.py` accepts both modes;
  if a copied older helper reports an SSE timeout, update it before falling
  back to UnrealBridge or hand-written transport code.
- In the current Object/Scene tool schemas, fields described as optional may
  still be marked required. Pass explicit empty values (`name: ""`,
  `tag: ""`, `collision_channels: []`, and `null` for object filters) rather
  than omitting them.
- For per-instance skeletal team colors, edit the actor's skeletal mesh
  component with `ObjectTools.set_properties` and a JSON `overrideMaterials`
  array. Do not change the shared `USkeletalMesh` asset; cover every material
  slot and read the property back before playtesting.
- World Partition actors live in external packages. `AssetTools.save_assets`
  may report success while the map package remains dirty; verify the external
  package content (or reopen/re-read through the editor) and use the editor's
  normal **File → Save All** before closing if the level tab still shows `*`.
- For an explicit actor-removal request, audit by label and generated class,
  remove only the resolved actor with `SceneTools.remove_from_scene`, re-scan
  the level, then run a short Simulate-PIE to confirm no spawner recreates it.
- Keep project-specific actor counts, asset paths, and verification results in
  the project's `.codex/session/HANDOFF.md`; this skill should retain only the
  reusable UE/MCP procedure.

## UE 5.8 NPC/AI editing workflow

The DemoAIMCP work established a reusable pattern for multi-team NPC maps and
large crowds. Apply it when an MCP task changes AI, behavior trees, or a World
Partition arena:

- Keep reusable targeting, line-of-sight/navigation caches, behavior-tree
  tasks, and crowd state machines in a runtime plugin. Keep health, weapons,
  damage rules, team presentation, sounds, and corpse handling in the game
  module behind a neutral adapter component. Preserve authored Blueprint paths
  with thin compatibility subclasses/facades instead of duplicating the AI
  implementation.
- Replace per-controller `TActorIterator`/full-world scans with a registry and
  cached target/LOS/navigation results. For high-count simple agents, use a
  lightweight state machine or shared horde controller; enable controller
  ticking only while an agent is moving, reacting, or attacking.
- Budget the visual work independently of decision work: use Animation Budget,
  LOD, `OnlyTickPoseWhenRendered`, lower update rates for distant agents, and
  freeze ragdolls after the short death simulation before disabling collision.
- Make team filtering explicit in the adapter/registry (same-team immunity,
  all other teams valid) and keep a locked target while visible. On temporary
  loss of sight, move to the cached last-known location or a reachable patrol
  point instead of standing still; add progress-based stuck detection with
  bounded retries and a failure backoff.
- For map edits, duplicate the regression level before authoring a larger
  arena, organize new geometry under named folders, keep shared meshes
  immutable, and use component/instance material overrides for team colors.
  After World Partition edits, verify external actor packages and use the
  editor's normal **Save All** if the level tab remains dirty.
- Acceptance loop: build the editor target, statically scan that legacy
  compatibility layers contain no second registry/horde brain, run at least
  20 seconds of Simulate-PIE, and inspect logs for target refresh, movement,
  reload/death cadence, and navigation failures. Record project-specific paths,
  counts, screenshots, and known limitations in `.codex/session/HANDOFF.md`,
  not in this reusable skill.

The custom bridge executes Python directly in a live editor. It auto-discovers via UDP multicast (`239.255.42.99:9876`); the TCP data port is OS-assigned per editor.

## Custom bridge preconditions

If `bridge.py` returns `discovery: no UnrealBridge editors found`, walk these in order — don't troubleshoot Python or firewalls first:

1. **Plugin installed** in `<UEProject>/Plugins/UnrealBridge/` (use `sync_plugin.bat` from this repo; user must edit its `DST=` once). Check: `<UEProject>/Plugins/UnrealBridge/UnrealBridge.uplugin` exists.
2. **Plugin enabled** — check `<UEProject>/<Project>.uproject` `"Plugins"` block for `{"Name":"UnrealBridge", "Enabled":false}` and flip if present.
3. **Editor up and ready** — `bridge.py ping` returns `"ready": true`. `false` means MainFrame still loading; wait 10–60s.

Last resort if multicast is blocked (corp VPN, virtual NIC): `--endpoint=127.0.0.1:<port>` from the editor log line `LogUnrealBridge: Listening on 127.0.0.1:<port>`. Python 3.7+ stdlib only.

## Waiting for the editor to become ready (post-launch / post-relaunch)

After launching/relaunching the editor, poll readiness with **`Monitor`**
(streams progress events, recommended) or **`Bash` with `run_in_background:
true`** (one completion event). Don't write a foreground `for/sleep`
countdown — the harness blocks long leading sleeps and you'll miss readiness.

Paste this verbatim as the `command` for either tool:

```bash
end=$(( $(date +%s) + 300 ))
i=0
until python .claude/skills/unreal-bridge/scripts/bridge.py --json --timeout 3 ping 2>/dev/null | grep -q '"ready": *true'; do
  now=$(date +%s)
  [ "$now" -ge "$end" ] && { echo "[wait] TIMEOUT after 300s"; exit 1; }
  i=$((i + 1))
  [ $((i % 3)) -eq 0 ] && echo "[wait] still booting ($((end - now))s left)"
  sleep 10
done
echo "[wait] READY"
```

Then call one of:

```
Monitor(description="UE editor ready-poll", command=<block above>,
        timeout_ms=360000, persistent=false)

Bash(description="Wait for UE editor ready", command=<block above>,
     run_in_background=true, timeout=360000)
```

**Locks (don't change without reading)**:

- Grep `"ready": *true` — TCP-up ≠ MainFrame-ready. `success:true, ready:false`
  means `exec` calls will be rejected; ping success alone is not enough.
- Ping FIRST then sleep — no leading sleep (harness blocks long ones).
- `i % 3` echo gate — caps notifications at ~10 over 5 min so Monitor doesn't
  trip its event-flood auto-stop.
- `end` deadline must stay **below** the tool `timeout_ms`/`timeout` so you
  get `[wait] TIMEOUT` rather than a silent harness kill.
- Path is relative to repo root; `${CLAUDE_SKILL_DIR}` is **not** reliably set
  in Monitor/Bash subshells — don't substitute it here.
- After the loop returns, do **one foreground** `bridge.py ping` before real
  work — bg success is past tense.
- Multi-editor host: append `--project=<name>` to the ping inside the loop.
- Skip this entirely when invoking `rebuild_relaunch.py` — it polls
  internally and prints `[rebuild] bridge is ready.` on success.

## Bridge CLI

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bridge.py" [options] <command> [args]
```

| Command | Purpose |
|---------|---------|
| `ping` | Check UE connection (TCP-only, doesn't touch GameThread) |
| `exec "<code>"` | Execute single inline statement |
| `exec --stdin <<'EOF' ... EOF` | Multi-line script from stdin (default for >1 line; `-` is shorthand for `--stdin`) |
| `exec-file <path>` | Execute a .py file (use when iterating, debugging, or keeping the script) |
| `preflight <path>` | Lint a script for bridge-call errors WITHOUT sending to UE |
| `suggest [pattern]` | Look up the bridge equivalent for a raw `unreal.*` fallback |
| `gamethread-ping` | Probe GameThread liveness (bypasses exec queue; use when `exec` hangs) |
| `resume` | Unstick a paused BP breakpoint |
| `list-editors` | Print every editor that responded to a discovery probe |
| `wait-compile <material>` / `wait-pose-index <psd>` | Client-side polling helpers |

Optional flags: `--project=<name|path>` (disambiguate when >1 editors run; or env `UNREAL_BRIDGE_PROJECT`), `--endpoint=host:port`, `--token=<secret>`, `--timeout=<s>`, `--json`, `--no-preflight`.

## Custom bridge workflow

1. **Use the built-in MCP decision sequence above first, then ping the custom bridge before fallback.**
2. **Default to `exec --stdin` heredoc, NOT `exec-file`.** A heredoc is the right mode for ~95% of one-shot work — no temp file to name, no cleanup, prompt stays self-contained, no risk of dangling scripts in `$TEMP` / `.tmp` / project root. **Only reach for `exec-file` when you genuinely intend to re-run the same script multiple times** (iterating on a fix, comparing runs). One-shots like "find X, list Y, build a report" → heredoc. If you find yourself writing `with open("/tmp/foo.py", "w")` followed by `bridge.py exec-file /tmp/foo.py`, stop and rewrite as a heredoc.
3. `--json` for parseable output.
4. Exit codes: `0` success · `1` runtime/transport · `2` bad CLI args · `3` AST preflight rejected.
5. **If `exec` hangs**: from a separate terminal try `gamethread-ping` (high latency = GT mid-exec, queue will drain) or `resume` (BP breakpoint).

Multi-line example:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bridge.py" exec --stdin <<'EOF'
from unreal_bridge import Asset
paths, _ = Asset.search_assets_in_all_content(query="Hero", max_results=5)
for p in paths:
    print(p.export_text())
EOF
```

**Windows path gotcha (Bash tool only):** unquoted backslashes get eaten by bash word-splitting — `python G:\Claude\UnrealBridge\.claude\skills\unreal-bridge\scripts\bridge.py exec ...` arrives as `G:ClaudeUnrealBridge.claudeskillsunreal-bridgescriptsbridge.py` and fails with "No such file or directory". Use forward slashes (`G:/Claude/...`) or single-quote the path (`'G:\Claude\...'`). The body inside `<<'EOF' ... EOF` is literal and unaffected — only the arg before the heredoc matters. PowerShell tool is unaffected.

## API surface — use the wrapper module first

```python
from unreal_bridge import Asset, Level, Blueprint, Editor, Anim, Material, PoseSearch, Chooser, ...
paths, _ = Asset.search_assets_in_all_content(query="Hero", max_results=20)
```

The wrapper has 23 classes (one per `UnrealBridge*Library`) with **kwargs-only signatures** — positional args raise `TypeError` immediately, no UE round-trip. This is the structural fix for positional-arg-order hallucinations. Regenerate after C++ header changes via `python tools/gen_manifest.py`.

The live UE 5.8 plugin audit found 1066 function-library `BlueprintCallable` methods but 1064 generated wrapper methods. `SetVariableMetadata` and `SetNodeComment` are missing from the current wrapper, so prefer the built-in Blueprint Toolset for those operations and regenerate the bridge manifest/wrapper before relying on them through Python.

Fallback: raw `unreal.UnrealBridge*Library.foo(...)` works (preflight catches errors), but prefer the wrapper.

## AST preflight (automatic — safety net only)

Every `exec*` call runs an AST preflight in the bridge client BEFORE sending. Reads `scripts/bridge_manifest.json` and rejects locally (exit 3, no UE round-trip) when:

- Function/library name doesn't exist (with did-you-mean)
- Required args missing / unknown kwarg / param given twice
- `unreal.BridgeXxx.YYY` enum member doesn't exist

Type validation is NOT done by preflight. Wrong asset paths / wrong scope still surface at runtime — references prose still matters for those.

**Treat preflight as a backstop, not a planning tool.** If you write code expecting preflight to autocorrect your guesses, you'll produce noisy output and still hit runtime tracebacks for the half it can't catch (USTRUCT field names, Python attribute access, EditDefaultsOnly violations). See "Verify before you call" below.

Bypass with `--no-preflight` (rare). Preview with `bridge.py preflight <path>`.

## Common semantic traps (preflight does NOT catch)

| Symptom | Fix |
|---------|-----|
| Bridge call returns `[]` for an asset you know exists | Wrong scope: `PROJECT` covers `/Game` only; plugin assets need `ALL_ASSETS`. Use `Asset.search_assets_in_all_content(...)`. |
| `get_derived_classes` hangs / huge results | Don't pass `UObject` / `AActor` — narrow to most specific base. |
| Multi-step BP edit feels chatty | Batch with `exec --stdin` heredoc or `exec-file`, not 3 inline `exec` calls. |
| Pawn movement script freezes the editor | `time.sleep` inside `exec` blocks GameThread — see `bridge-gameplay-api.md` "chase a target" pattern (use `register_runtime_timer`). |
| `print('中文' / '한글' / '日本語')` shows `���` or `涓枃` mojibake | Almost always **display-only** — the wire is byte-perfect UTF-8. See "Non-ASCII output (CJK / Greek / emoji)" below. |
| Need "where is this GameplayTag used?" / Find References on a tag | `unreal.UnrealBridgeGameplayTagLibrary.find_assets_referencing_tag(tag, include_children, ...)`. Mutations: `add_gameplay_tag` / `rename_gameplay_tag` (auto-redirect) / `remove_gameplay_tag`; pick the target ini via `list_tag_source_inis(...)`. For `PrimaryAssetId` / other named-value structs use the generic `UnrealBridgeAssetLibrary.find_assets_referencing_searchable_name(struct_type, value, ...)`. See `bridge-gameplaytag-api.md`. |

## Verify before you call — don't lean on preflight

Preflight is a **safety net**, not a planning tool. Writing code from imagined API / field / attribute names and waiting for preflight to tell you the right one produces noisy output (4-8 `[WARN]` per script, often still ending in a runtime traceback) and wastes round-trips. **Verify FIRST, then write the script.** Four axes:

1. **Bridge function names** — `grep scripts/bridge_manifest.json` or read the relevant `references/bridge-*-api.md`. Don't translate the C++ name into snake_case in your head and assume.
2. **Bridge USTRUCT return-value fields** — return types like `BridgeGameplayEffectInfo` keep a *minimum* set of fields (not exhaustive); UE 5.x evolves struct shape between versions. Look up the fields in `bridge_manifest.json` `structs` section, OR run a one-off probe `print([a for a in dir(obj) if not a.startswith('_')])` BEFORE writing the consumer code.
3. **UE object attributes** — never `<obj>.<attr>`. Always `get_editor_property` (and respect `protected:` / `EditDefaultsOnly` rejection). Use `Level.list_actor_properties(actor_name=...)` or `Level.list_class_properties(class_path=...)` to list first.
4. **Function signatures** — when unsure: `unreal.UnrealBridgeXxx.fn.__doc__` first line is the signature. Cheaper than a guess + correction round-trip.

**Symptom you're in the bad loop**: your last few exec attempts produced `[WARN]` lines from preflight followed by `AttributeError` tracebacks. **Stop**, run one heredoc with `dir()` / manifest grep, then write the real script.

## Never silently bail to raw `unreal.*`

If a bridge call returns empty / errors, suspect **your parameters** (wrong scope / path / filter), not the wrapper. Falling back to `unreal.AssetRegistryHelpers` etc. bypasses preflight, audit logging, and often walks 100k–2M registry entries.

Preflight emits `[WARN]` on known raw-fallback patterns and shows the bridge equivalent inline. To look up before writing: `bridge.py suggest [pattern]`. Patterns currently mapped:

| Raw pattern | Bridge equivalent |
|---|---|
| `ar.get_assets_by_path(...)` | `Asset.list_assets_under_path(folder_path, include_subfolders)` |
| `ar.get_referencers(...)` | `Asset.get_package_referencers(package_name, hard_only)` |
| `ar.get_dependencies(...)` | `Asset.get_package_dependencies(package_name, hard_only)` |
| `unreal.GameplayStatics.get_all_actors_of_class(...)` | `Level.find_actors_by_class(class_path, max_results)` |
| `unreal.GameplayStatics.get_all_actors_with_tag(...)` | `Level.find_actors_by_tag(tag)` |

If you genuinely believe no bridge function covers your case, **ask the user before reaching for raw `unreal.*`**.

## Reference index — read these for usage / traps / workflow patterns

Signatures are now mechanically enforced (preflight). References carry semantic traps, scope warnings, and workflow patterns preflight can't catch.

| Topic | File | When to read |
|-------|------|------|
| UE 5.8 built-in MCP | `references/builtin-mcp.md` | Transport selection, endpoint/session rules, startup, live ToolsetRegistry inventory, built-in-vs-bridge routing |
| Blueprint queries + authoring | `references/bridge-blueprint-api.md` | Class hierarchy, variables/functions/components, node search, write ops, auto-layout flow, lint loop |
| Asset queries | `references/bridge-asset-api.md` | Asset lookup, search, references/dependencies, **`SoftObjectPath` stringification** (top-of-file block) |
| UMG / Widget | `references/bridge-umg-api.md` | Widget Blueprint hierarchy/tree |
| Animation | `references/bridge-anim-api.md` | ABP state machines, slots, sequences, montages, blend spaces. **Authoring an ABP? Read the "Authoring an Animation Blueprint (agent workflow)" section first.** |
| DataTable | `references/bridge-datatable-api.md` | Schema, rows, fields, search, CSV |
| Material | `references/bridge-material-api.md` | Material instance parameters |
| Level / Actor | `references/bridge-level-api.md` | Level queries, spawn/destroy/move, property get/set, selection |
| Editor session | `references/bridge-editor-api.md` | Asset open/save, viewport camera, PIE start/stop, console/CVars, BP compile |
| GameplayAbility | `references/bridge-gameplayability-api.md` | GA Blueprint metadata |
| **Generic UPROPERTY read/write (privileged)** | `references/bridge-property-api.md` | When `get_editor_property` rejects with "protected" / `set_editor_property` rejects EditDefaultsOnly sub-fields / you need to read `private:` / bare `UPROPERTY()` / write nested struct values via export-text. `list_u_properties` / `get_u_property_as_export_text(path, "Modifiers[0].Foo.Bar")` / `set_u_property_from_export_text` (with `fire_change_notify` for editor refresh) / `array_append_u_property` (auto-handles FGameplayTagContainer ParentTags) / `array_remove_u_property` / `array_clear_u_property` / `get_asset_cdo_path`. **Privileged** — bypasses UE editor safety net. Use dedicated APIs (`add_gameplay_tag`, `add_ge_modifier_scalable`) when they exist. |
| **GameplayTag references / sources / mutations** | `references/bridge-gameplaytag-api.md` | Read: `find_assets_referencing_tag` (with child-tag expansion), `list_all_registered_tags`, `get_tag_source_info`. Write: `add_gameplay_tag(tag, source_ini='', comment='')`, `rename_gameplay_tag(old, new, rename_children=True)` (auto-inserts redirect, redirect lifetime hardened — survives subsequent mutations + cold restart), `remove_gameplay_tag(tag)`. Source enum: `list_tag_source_inis(filter_type='')`. Redirect ops: `list_gameplay_tag_redirects(source='', old_prefix='')` + `remove_gameplay_tag_redirect(old, new)` for enumerate-then-sweep. Built on the AssetRegistry SearchableName index + IGameplayTagsEditorModule. `bridge-asset-api.md` "SearchableName Index" has the generic read version (PrimaryAssetId, custom named-value structs). |
| **Motion Matching — PoseSearch** | `references/bridge-pose-search-api.md` | **Read before any PSS / PSD read or write** — `DatabaseAnimationAssets` / `Channels` are `private:` and unreachable via `get_editor_property`; this lib is the only path. Includes `wait-pose-index` CLI. |
| **Motion Matching — Chooser** | `references/bridge-chooser-api.md` | **Read before any CHT read or write** — `ResultsStructs` / `DisabledRows` etc. are `private:`; this lib is the only path. Covers NestedChooser `:Name` paths, `matched_row=-1` caveat, and the auto Compile+PostEditChange contract. |
| Reactive handlers | `references/bridge-reactive.md` | Register Python on UE events (GameplayEvent / AnimNotify / MovementMode / Attribute / ActorLifecycle / InputAction). |
| Navigation | `references/bridge-navigation-api.md` | NavMesh OBJ export |
| Perf snapshots | `references/bridge-perf-api.md` | Structured FPS / GT / RT / GPU / draw calls / mem / UObject histogram |
| Agent / Gameplay | `references/bridge-gameplay-api.md` | **Mandatory before driving the player pawn** — sticky inputs, camera steering, navmesh path planning. |
| UE Asset / Actor / Material | `references/ue-python-*.md` | Stdlib UE Python helpers (load, list, duplicate, spawn) |

> **Pawn control is non-obvious — read `bridge-gameplay-api.md` first.** Driving the player (sticky `IA_Move`, `apply_look_input`, navigating to a moving target, holding an input over time) has hard constraints a fresh API read won't reveal: `bridge.exec` runs on GameThread so `time.sleep` inside one `exec` freezes the engine and stops the sticky ticker; continuous steering must run from a reactive `register_runtime_timer` callback, not a Python `while` loop; `IA_Move` is camera-relative and the forward-axis convention varies per project. The "Pattern: chase a (possibly moving) target and stop on arrival" section has the working template.

> **Asset lookup by name defaults to `search_assets_in_all_content(name, max_results)`.** When the user names an asset without a path, do **not** call `unreal.AssetRegistryHelpers.get_assets_by_path('/Game', recursive=True)` and filter — that walks 100k–2M+ entries and times out. The full `search_assets` form needs `BridgeAssetSearchScope.ALL_ASSETS` (not `PROJECT`) when the asset might live in a plugin mount (`/PluginName/...`). `PROJECT` covers `/Game` only; using it for a plugin asset returns `[]` silently. Valid scope members: `ALL_ASSETS`, `PROJECT`, `CUSTOM_PACKAGE_PATH` — there is no `GAME_FOLDER`.

## Blueprint authoring policy (MUST read before BP write ops on either transport)

**非必要不写蓝图 Node 和 Graph.** Agent-authored BPs are visibly weaker than C++ on readability/maintainability/perf. Default response to "用蓝图实现 X":

1. State the tradeoff. Bridge has full graph-write primitives but agent-Graphs are weaker than C++.
2. Offer alternative: a C++ `UFUNCTION(BlueprintCallable)` with thin BP wrapper, or another bridge surface (Material / Anim / UMG / DataTable / Level).
3. **Re-confirm explicitly**: "你仍然希望我用蓝图 Node/Graph 实现，还是改走 C++？"
4. Only proceed on explicit insistence ("就用蓝图写"). Otherwise redirect.

**Exceptions** (skip the dance):
- Pure data writes (`set_blueprint_variable_default` etc.) without new nodes
- Bulk automation explicitly framed as such ("扫 100 个 BP 改默认值")
- Standing authorization in `CLAUDE.md` or current conversation

Hard line: any op spawning/connecting/removing nodes, adding events, or creating functions needs the confirmation dance.

## Blueprint review loop (mandatory after BP authoring)

After authoring/modifying a BP graph (and the user confirmed they want it):

```
1. plan        — list events / functions / local vars in text first
2. build       — add_*_node / connect_graph_pins / add_blueprint_variable …
3. auto_layout — MANDATORY after ANY graph mutation; use 'pin_aligned' (3-exec flow) or 'exec_flow' (bulk).
                 See bridge-blueprint-api.md for the exact open→sleep→layout sequence.
4. lint        — lint_blueprint(...) and resolve every warning/error
5. collapse    — collapse_nodes_to_function on any LongExecChain finding
6. straighten  — straighten_exec_chain on main rails (after 'exec_flow' only)
7. comment     — add_comment_box + set_comment_box_color per section (>10 nodes = mandatory)
8. compile     — compile_blueprints clean
```

- **Lint is non-optional.** Fix every warning/error or comment-box-justify it.
- **Name things.** Rename `UnnamedCustomEvent` / `CustomEvent_0` to intent (`OnHealthChanged`).
- **Comment boxes are section titles.** Any graph >10 nodes needs at least one comment box with a meaningful title (`"1. Validate inputs"`, `"2. Apply damage"`) and an appropriate preset color (`Section`, `Validation`, `Danger`, `Network`, `UI`, `Debug`, `Setup`).
- **Pick the right layout strategy.** `auto_layout_graph(... 'pin_aligned' ...)` uses DFS-ordered leaves + downstream-driven Y alignment + live Slate geometry — matches hand-laid BP shape (`.then` rails horizontal, siblings stacked in one column). Requires the three-exec flow (open graph → sleep → layout) to read live widgets. Use `'exec_flow'` (Sugiyama-lite, layer-center Y) for bulk tidy on large graphs where pixel-accuracy matters less, then follow with `straighten_exec_chain` on the main rail.
- **Compact by spacing, not by node.** `pin_aligned` treats `h_spacing` as a loose upper bound and internally uses `DataHSpace = max(15, h/3)` and `ExecGap = max(30, h/2)` — so `h_spacing=100` renders tighter than the raw number suggests. Pass smaller values (`40, 32`) for max density.
- **Size predict before spawning.** If placing several nodes in a row by hand, call `predict_node_size` for each kind first so X offsets don't overlap.
- **Post-layout geometry reads.** After `auto_layout_graph` runs, Slate widgets don't refresh `NodePosX/Y` until they tick — so `get_rendered_node_info` returns *pre-layout* pin coords in the same exec. For crossing-detection / wire-length audits right after layout, read `get_node_layout(bp, fn, guid).pos_*` (authoritative from node model) and estimate pin Y as `pos_y + 40 + 22 × dir_index`. Only pay the open-graph + sleep cost when you specifically need Slate-accurate coords.
- `auto_insert_reroutes` is intentionally NOT in the loop — empirically it produces many-knot routing that reads worse than the original. Opt in per-graph if a specific case needs it.

## Non-ASCII output (CJK / Greek / emoji)

Bridge is UTF-8 byte-perfect end-to-end since 2026-05-04. **Mojibake = display, not data.** Confirm with hex:

```python
print(got.encode('utf-8').hex(), '==', '测试'.encode('utf-8').hex())
```

If hex matches, it's a Windows cp936/cp1252 console issue — fix the *display*, not the bridge:

| Situation | Fix |
|---|---|
| Piping `bridge.py ... > out.txt` writes cp936 | prefix `PYTHONIOENCODING=utf-8` (bash) / `$env:PYTHONIOENCODING='utf-8'` + `\| Out-File -Encoding utf8` (PS) |
| Reading saved file back | `open(p, encoding='utf-8')` (or `utf-8-sig` for PS BOM) |
| Calling bridge.py from another Python process | set `PYTHONIOENCODING=utf-8` in subprocess env |

Verified: identifiers + literals in script source, exception messages/tracebacks, DataTable FName keys, asset paths with Chinese folders, save→restart→read persistence. Korean/Japanese use the same UTF-8 path — verify with hex if anything looks off.

**Never write temp files to `C:\` root** — use `$env:TEMP\…` or `/tmp/…`.

## Safety Rules

- **NEVER** delete assets / actors / files without explicit confirmation.
- **NEVER** modify or overwrite assets without describing the change first.
- Wrap state-changing ops in `unreal.ScopedEditorTransaction`.
- On failure: show full traceback. Don't silently retry destructive ops.

## Notes

- Python interpreter is **persistent** — variables carry between `exec` calls.
- `print()` returns to bridge; `unreal.log()` only to UE Output Log.
- Structured data: `import json; print(json.dumps(...))` with `--json`.
- If `ping` fails: editor not running, plugin not enabled, or wrong project (preconditions above).
- Timeout: retry with `--timeout 120`.
