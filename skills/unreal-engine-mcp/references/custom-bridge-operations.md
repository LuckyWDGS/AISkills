# Custom UnrealBridge fallback operations

Read this only for an operation whose official MCP and public Epic API routes
have been checked and cannot complete the task. This reference describes the
optional custom transport; it is not a prerequisite for official UE automation.
Return to Epic MCP for covered operations. Run the commands from the skill root.
For this user, use background execution and preserve all editor window state.

The custom bridge executes Python directly in a live editor. It auto-discovers via UDP multicast (`239.255.42.99:9876`); the TCP data port is OS-assigned per editor.

## Custom bridge preconditions

If `bridge.py` returns `discovery: no UnrealBridge editors found`, walk these in order — don't troubleshoot Python or firewalls first:

1. **Plugin installed**: check `<UEProject>/Plugins/UnrealBridge/UnrealBridge.uplugin` or the selected engine's plugin location. Install/build it only within an authorized setup for a proven gap; missing custom discovery is not a reason to install it for an official-only task.
2. **Plugin enabled** — check `<UEProject>/<Project>.uproject` `"Plugins"` block for `{"Name":"UnrealBridge", "Enabled":false}` and flip if present.
3. **Editor up and ready** — `bridge.py ping` returns `"ready": true`. `false` means MainFrame still loading; wait 10–60s.

Last resort if multicast is blocked (corp VPN, virtual NIC): `--endpoint=127.0.0.1:<port>` from the editor log line `LogUnrealBridge: Listening on 127.0.0.1:<port>`. Python 3.7+ stdlib only.

## Bridge CLI

```bash
python scripts/bridge.py [options] <command> [args]
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
2. Use a literal multiline input suited to the shell (`exec --stdin`: PowerShell single-quoted here-string, or Bash quoted heredoc). Use `exec-file` for a reusable script or when file-based UTF-8 input is clearer. Keep scripts and results in ignored session output, not the project root.
3. `--json` for parseable output.
4. Exit codes: `0` success · `1` runtime/transport · `2` bad CLI args · `3` AST preflight rejected.
5. **If `exec` hangs**, use a bounded `gamethread-ping` from outside that execution to help distinguish a busy game thread. Do not assume the queue will drain or issue `resume` unless breakpoint control is part of the authorized debugging task. Follow [failure diagnosis](debugging-and-source-navigation.md) before recovery.

Multi-line example:

```bash
python scripts/bridge.py exec --stdin <<'EOF'
from unreal_bridge import Asset
paths, _ = Asset.search_assets_in_all_content(query="Hero", max_results=5)
for p in paths:
    print(p.export_text())
EOF
```

**Windows path gotcha (Bash tool only):** unquoted backslashes get eaten by bash word-splitting — `python G:\Claude\UnrealBridge\.claude\skills\unreal-engine-mcp\scripts\bridge.py exec ...` arrives as `G:ClaudeUnrealBridge.claudeskillsunreal-engine-mcpscriptsbridge.py` and fails with "No such file or directory". Use forward slashes (`G:/Claude/...`) or single-quote the path (`'G:\Claude\...'`). The body inside `<<'EOF' ... EOF` is literal and unaffected — only the arg before the heredoc matters. PowerShell tool is unaffected.

## Custom fallback API — use the wrapper module first within this transport

```python
from unreal_bridge import Asset, Level, Blueprint, Editor, Anim, Material, PoseSearch, Chooser, ...
paths, _ = Asset.search_assets_in_all_content(query="Hero", max_results=20)
```

The audited wrapper has 23 classes (one per `UnrealBridge*Library`) with **kwargs-only signatures** — positional args raise `TypeError` immediately, no UE round-trip. Check the installed snapshot. After custom C++ header changes, regenerate from the matching plugin-source checkout using its manifest generator; do not assume that generator is bundled in this skill.

The live UE 5.8 plugin audit found 1066 function-library `BlueprintCallable` methods but 1064 generated wrapper methods. `SetVariableMetadata` and `SetNodeComment` are missing from that wrapper snapshot. Check the live official metadata schema first; this does not imply an official node-comment setter exists. In tested UE 5.8.4, native comment frames use public Epic Python APIs through background Remote Execution; see [annotation support](blueprint-programming-mcp.md#chinese-module-annotations). Regenerate the custom wrapper only when a justified bridge operation actually requires it.

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

1. **Bridge function names** — `rg -n -F '<exact_function_name>' scripts/bridge_manifest.json` or read the relevant `references/bridge-*-api.md`. Don't translate the C++ name into snake_case in your head and assume.
2. **Bridge USTRUCT return-value fields** — return types like `BridgeGameplayEffectInfo` keep a *minimum* set of fields (not exhaustive); UE 5.x evolves struct shape between versions. Look up the fields in `bridge_manifest.json` `structs` section, OR run a one-off probe `print([a for a in dir(obj) if not a.startswith('_')])` BEFORE writing the consumer code.
3. **UE object attributes** — never `<obj>.<attr>`. Always `get_editor_property` (and respect `protected:` / `EditDefaultsOnly` rejection). Use `Level.list_actor_properties(actor_name=...)` or `Level.list_class_properties(class_path=...)` to list first.
4. **Function signatures** — when unsure: `unreal.UnrealBridgeXxx.fn.__doc__` first line is the signature. Cheaper than a guess + correction round-trip.

**Symptom you're in the bad loop**: your last few exec attempts produced `[WARN]` lines from preflight followed by `AttributeError` tracebacks. Stop and inspect the available names/signatures with one bounded read or manifest search before writing the actual edit.

## Diagnose errors within the chosen transport

For a justified bridge call that returns empty/errors, verify scope, paths, filters and the wrapper contract before replacing it with a broad registry walk. A wrapper defect remains possible; preserve the actual error. The bridge preflight suggestions below apply inside this optional transport. They do not prohibit using public `unreal.*` APIs through Epic Python Remote Execution, which takes priority over a custom plugin for official MCP gaps.

Preflight emits `[WARN]` on known raw-fallback patterns and shows the bridge equivalent inline. To look up before writing: `bridge.py suggest [pattern]`. Patterns currently mapped:

| Raw pattern | Bridge equivalent |
|---|---|
| `ar.get_assets_by_path(...)` | `Asset.list_assets_under_path(folder_path, include_subfolders)` |
| `ar.get_referencers(...)` | `Asset.get_package_referencers(package_name, hard_only)` |
| `ar.get_dependencies(...)` | `Asset.get_package_dependencies(package_name, hard_only)` |
| `unreal.GameplayStatics.get_all_actors_of_class(...)` | `Level.find_actors_by_class(class_path, max_results)` |
| `unreal.GameplayStatics.get_all_actors_with_tag(...)` | `Level.find_actors_by_tag(tag)` |

For a proven bridge fallback with no suitable wrapper, verify the native API and
record the gap before using a narrow `unreal.*` operation within the authorized task.

## Legacy API reference index

Paths in the table are relative to the skill root. The `bridge-*` entries describe custom APIs and must not be mistaken for current official-tool coverage. Preflight checks some custom signatures; it does not validate editor semantics.

| Topic | File | When to read |
|-------|------|------|
| UE 5.8 built-in MCP | `references/builtin-mcp.md` | Transport selection, endpoint/session rules, startup, live ToolsetRegistry inventory, built-in-vs-bridge routing |
| Blueprint programming | `references/blueprint-programming-mcp.md` | Official graph, component/default, compile/log, gameplay and programmatic workflows |
| Blueprint logic and wires | `references/blueprint-graph-inspection.md` | Read-only exporter, pin identity, reciprocal links, reroutes, execution/data flow and interpretation limits |
| Blueprint custom fallback | `references/bridge-blueprint-api.md` | Only for a proven gap: custom variables/functions/components, graph edits, layout and lint |
| Asset queries | `references/bridge-asset-api.md` | Asset lookup, search, references/dependencies, **`SoftObjectPath` stringification** (top-of-file block) |
| UMG / Widget | `references/bridge-umg-api.md` | Widget Blueprint hierarchy/tree |
| Animation and AI programming | `references/animation-state-machines-mcp.md` | Official-first ABP, animation state machine, BlendSpace, Montage/Notify, StateTree, Behavior Tree and Control Rig routes; inspection vs authoring boundaries |
| Animation custom fallback | `references/bridge-anim-api.md` | Only for a proven gap: custom ABP/state/transition/slot/sequence/Montage/BlendSpace operations and semantic invariants |
| DataTable | `references/bridge-datatable-api.md` | Schema, rows, fields, search, CSV |
| Material | `references/bridge-material-api.md` | Material instance parameters |
| Level / Actor | `references/bridge-level-api.md` | Level queries, spawn/destroy/move, property get/set, selection |
| Editor session | `references/bridge-editor-api.md` | Asset open/save, viewport camera, PIE start/stop, console/CVars, BP compile |
| GameplayAbility | `references/bridge-gameplayability-api.md` | GA Blueprint metadata |
| **Generic UPROPERTY read/write (privileged)** | `references/bridge-property-api.md` | When `get_editor_property` rejects with "protected" / `set_editor_property` rejects EditDefaultsOnly sub-fields / you need to read `private:` / bare `UPROPERTY()` / write nested struct values via export-text. `list_u_properties` / `get_u_property_as_export_text(path, "Modifiers[0].Foo.Bar")` / `set_u_property_from_export_text` (with `fire_change_notify` for editor refresh) / `array_append_u_property` (auto-handles FGameplayTagContainer ParentTags) / `array_remove_u_property` / `array_clear_u_property` / `get_asset_cdo_path`. **Privileged** — bypasses UE editor safety net. Use dedicated APIs (`add_gameplay_tag`, `add_ge_modifier_scalable`) when they exist. |
| **GameplayTag references / sources / mutations** | `references/bridge-gameplaytag-api.md` | Read: `find_assets_referencing_tag` (with child-tag expansion), `list_all_registered_tags`, `get_tag_source_info`. Write: `add_gameplay_tag(tag, source_ini='', comment='')`, `rename_gameplay_tag(old, new, rename_children=True)` (auto-inserts redirect, redirect lifetime hardened — survives subsequent mutations + cold restart), `remove_gameplay_tag(tag)`. Source enum: `list_tag_source_inis(filter_type='')`. Redirect ops: `list_gameplay_tag_redirects(source='', old_prefix='')` + `remove_gameplay_tag_redirect(old, new)` for enumerate-then-sweep. Built on the AssetRegistry SearchableName index + IGameplayTagsEditorModule. `bridge-asset-api.md` "SearchableName Index" has the generic read version (PrimaryAssetId, custom named-value structs). |
| **Motion Matching — PoseSearch** | `references/bridge-pose-search-api.md` | Fallback API after checking current official tools/editor APIs. Private `DatabaseAnimationAssets` / `Channels` need dedicated editing semantics; includes `wait-pose-index` CLI. |
| **Motion Matching — Chooser** | `references/bridge-chooser-api.md` | Fallback API after checking current official tools/editor APIs. Private row arrays require consistent updates; covers NestedChooser paths, `matched_row=-1`, compile and refresh. |
| Reactive handlers | `references/bridge-reactive.md` | Register Python on UE events (GameplayEvent / AnimNotify / MovementMode / Attribute / ActorLifecycle / InputAction). |
| Navigation | `references/bridge-navigation-api.md` | NavMesh OBJ export |
| Perf snapshots | `references/bridge-perf-api.md` | Structured FPS / GT / RT / GPU / draw calls / mem / UObject histogram |
| Agent / Gameplay | `references/bridge-gameplay-api.md` | **Mandatory before driving the player pawn** — sticky inputs, camera steering, navmesh path planning. |
| UE Asset / Actor / Material | `references/ue-python-*.md` | Stdlib UE Python helpers (load, list, duplicate, spawn) |

> **Pawn control is non-obvious — read `bridge-gameplay-api.md` first.** Driving the player (sticky `IA_Move`, `apply_look_input`, navigating to a moving target, holding an input over time) has hard constraints a fresh API read won't reveal: `bridge.exec` runs on GameThread so `time.sleep` inside one `exec` freezes the engine and stops the sticky ticker; continuous steering must run from a reactive `register_runtime_timer` callback, not a Python `while` loop; `IA_Move` is camera-relative and the forward-axis convention varies per project. The "Pattern: chase a (possibly moving) target and stop on arrival" section has the working template.

> **During a proven custom-bridge fallback**, lookup by name uses `search_assets_in_all_content(name, max_results)`. On the normal MCP path, use the discovered official AssetTools search. Avoid a full `/Game` registry walk and local filtering. In the custom API, plugin mounts require `BridgeAssetSearchScope.ALL_ASSETS`; `PROJECT` covers `/Game` only. Valid custom scope members are `ALL_ASSETS`, `PROJECT`, and `CUSTOM_PACKAGE_PATH`.

## Layout and lint during a justified fallback

The following layout/lint notes apply only during an already justified custom
bridge fallback; they are not prerequisites for official Blueprint work.

- **Triage available lint results.** Fix issues introduced by the change and explain relevant pre-existing findings; do not add bridge lint as a requirement for official-only or annotation-only work.
- **Name things.** Rename `UnnamedCustomEvent` / `CustomEvent_0` to intent (`OnHealthChanged`).
- **Comment boxes are section titles.** Any graph >10 nodes needs at least one comment box with a meaningful title (`"1. Validate inputs"`, `"2. Apply damage"`) and an appropriate preset color (`Section`, `Validation`, `Danger`, `Network`, `UI`, `Debug`, `Setup`).
- **Pick the right layout strategy.** `auto_layout_graph(... 'pin_aligned' ...)` uses DFS-ordered leaves + downstream-driven Y alignment + live Slate geometry — matches hand-laid BP shape (`.then` rails horizontal, siblings stacked in one column). Requires an opened/ticking graph to read live widgets, so it is unsuitable for this user's normal no-UI workflow. Use a supported model-based layout; consider `'exec_flow'` (Sugiyama-lite, layer-center Y) when layout is in scope and it works without activating UI. Restrict changes to the authored region; do not tidy unrelated branches.
- **Compact by spacing, not by node.** `pin_aligned` treats `h_spacing` as a loose upper bound and internally uses `DataHSpace = max(15, h/3)` and `ExecGap = max(30, h/2)` — so `h_spacing=100` renders tighter than the raw number suggests. Pass smaller values (`40, 32`) for max density.
- **Size predict before spawning.** If placing several nodes in a row by hand, call `predict_node_size` for each kind first so X offsets don't overlap.
- **Post-layout geometry reads.** After `auto_layout_graph` runs, Slate widgets don't refresh `NodePosX/Y` until they tick — so `get_rendered_node_info` returns *pre-layout* pin coords in the same exec. For crossing-detection / wire-length audits right after layout, read `get_node_layout(bp, fn, guid).pos_*` (authoritative from node model) and estimate pin Y as `pos_y + 40 + 22 × dir_index`. Request UI access only if Slate-accurate coordinates are essential and the user has not already authorized it; do not open/focus graphs automatically.
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

## Execution and recovery

Work only on the authorized targets. Use supported transactions and preserve
pre-existing dirty edits; transactions do not guarantee rollback or disk backup.
For write timeouts, follow the [readback rule](developer-workflow.md#make-changes-recoverable-and-unambiguous)
before retrying. Preserve useful tracebacks and diagnose the failing operation.

## Notes

- Python interpreter is **persistent** — variables carry between `exec` calls.
- `print()` returns to bridge; `unreal.log()` only to UE Output Log.
- Structured data: `import json; print(json.dumps(...))` with `--json`.
- If `ping` fails: editor not running, plugin not enabled, or wrong project (preconditions above).
- A read-only call may use a larger bounded timeout after readiness is checked. A timed-out write requires readback before any retry; increasing the timeout does not prevent duplication.
