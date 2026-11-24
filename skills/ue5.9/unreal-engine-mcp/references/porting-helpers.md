# Porting a helper to UE 5.9

Use this to move a script from `unported` to `5.9` (see
[tool status](shared-conventions.md#engine-version-and-tool-status)). Until it
is ported, a helper is refused on a UE 5.9 editor before it sends a call.

## Why a rename is not a port

UE 5.9 changed toolset owners, tool names (PascalCase), argument names
(camelCase), argument shapes and result fields. Some UE 5.8 owners still
exist, so a half-ported helper can write through one owner and then fail on
another. `ProgrammaticToolset` scripts (`def run()` / `execute_tool`) have no
equivalent entry: UE 5.9 uses `PythonScriptingTools` with top-level
`await call_tool(...)`.

## Steps

1. **List every call.** Read the helper and collect each toolset, tool,
   argument set and result field it uses, including saves and readbacks.
2. **Discover the UE 5.9 contract.** For each call run
   `describe-tool <toolset> <tool>` on the target editor and keep the schema
   in the session directory. Record calls with no native equivalent as gaps.
3. **Rewrite the calls.** Use the discovered names and shapes. Replace a
   `run_tool_script` collector with direct calls or one `execute_python`
   script. Convert object paths (`/Game/M/MI_X.MI_X`) and package paths
   (`/Game/M/MI_X`) explicitly.
4. **Keep the plan-then-run shape for writers.** Collect facts with reads,
   build the plan in a pure function that returns `(steps, problems)`, write
   `<report>-plan.jsonl`, validate with `batch --dry-run`, and execute only
   with `--execute`. One write per step, each with a readback and `expect`.
   Save each package in its own step and read `IsDirty` back.
5. **Switch the contract.** Import `connect` / `call_tool` from
   `ue_mcp.skill_api` directly instead of the skill's legacy `mcp.py` names,
   or drop the `contract="5.8"` argument. This is the line that lifts the
   refusal, so change it last.
6. **Update the offline tests.** Replace the fixtures with results recorded
   from the UE 5.9 editor and cover each problem class in the plan builder.
7. **Verify live in a scratch folder.** Run the plan mode first and confirm
   nothing changed. Run `--execute` only in a folder the user approved. Record
   the build, the cases run and the cases not run.
8. **Relabel.** Change the tool's status to `5.9` in the skill's tool table
   and add the dated entry to the reference's `## 验证记录`.

## Report shape

Keep the helper's existing report fields so downstream tools keep working, and
add `status` (`planned` / `blocked` / `applied` / `failed`), `plan`, `problems`
and `coverage_gaps`. Exit 0 only for `planned` or `applied`. Treat
`left_dirty` as a failure to explain: report the packages and leave them
unsaved.

## CLI conventions

`<tool>.py <spec> [--execute] [--from-plan FILE] [--reuse-existing]
[--project NAME] [--mcp-url URL] [--out FILE] [--markdown]`.
