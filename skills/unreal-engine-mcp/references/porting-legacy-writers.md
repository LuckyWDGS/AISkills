# Porting a legacy writer to MCP

Use this when a script that wrote through retired `UnrealBridge*Library` APIs
must work again. Read-only collectors follow the audit pattern in
[builtin-mcp.md](builtin-mcp.md#programmatictoolset-batching); writers follow
this one. Worked example:
`skills/unreal-material-artist/scripts/unreal_material_tools/material_instance_batch.py`.

## Shape

A ported writer only decides *what* to change. The shared
`builtin_mcp.py batch` runner decides *how*: schema validation, ordered
execution, readback, stop on failure, per-step results.

```
spec ──► collect_facts (live, read-only) ──► build_plan (pure) ──► plan.jsonl
                                                   │                    │
                                              problems ──► blocked      ▼
                                                              batch --dry-run (live schema)
                                                                        │
                                              planned ◄── no --execute ─┤
                                                                        ▼
                                                              batch run ──► report rows
```

1. **Collect facts with direct read calls.** Existence, current parents,
   available parameters/properties, anything the plan depends on. Use
   `mcp.connect()` (schema cache, resumed session, `--project` guard).
2. **Build the plan in a pure function** `build_plan(spec, facts) -> (steps, problems)`.
   Turn every condition the legacy script silently skipped or "tried" into a
   problem: missing parent, unknown parameter name or type, existing asset
   without `--reuse-existing`, an existing asset with a different parent.
   A plan with problems never runs.
3. **One write per step, each with a readback and `expect`.** Read the value
   back with the matching getter. Finish each package with its own
   `AssetTools.save_assets` step (that package only) and an
   `AssetTools.is_dirty` readback expecting `false`. Never use global Save All.
4. **Write the plan to `<report>-plan.jsonl`.** Extra keys (`instance`, `kind`,
   …) are ignored by the runner and let the report map results back.
5. **Validate with `run_batch(..., dry_run=True)`**: every tool and every
   schema-required argument must exist in the live schema.
6. **Execute only with `--execute`.** `--from-plan <file>` runs a reviewed or
   hand-edited plan without re-planning.
7. **Treat `left_dirty` as a failure to explain.** The batch lists referenced
   packages it left unsaved (for example a parent material). Do not save them
   to hide it; report them, and reload the package from disk only with the
   user's approval.
8. **Map results into the legacy report shape** so downstream tools keep
   working, and add `status` (`planned` / `blocked` / `applied` / `failed`),
   `plan`, `problems` and `coverage_gaps`. Exit 0 only for `planned`/`applied`.
9. **Side outputs after the batch.** Images and other non-JSON results (for
   example `EditorAppToolset.CaptureAssetImage` previews) are fetched after the
   run, never as batch steps.

## Live API details that matter

- Tool arguments take full object paths (`/Game/M/MI_X.MI_X`); `AssetTools`
  takes package paths (`/Game/M/MI_X`). Convert explicitly in both directions.
- Object references come back as `{"refPath": ...}` or a bare string; `expect`
  accepts either for a `{"refPath": ...}` expectation.
- `ObjectTools.get_properties` returns a JSON string; the runner decodes it.
- Floats are float32 (`0.4` reads back `0.4000000059604645`); numeric `expect`
  uses a 1e-6 tolerance, booleans are strict.
- Nothing is atomic and nothing is retried. Steps before a failure stay
  applied; the report says which. Re-plan from fresh facts before re-running.

## Tests

- Offline: `build_plan` with fact fixtures (happy path, each problem class,
  value normalization) and the report mapping with fabricated batch results.
- Live: run without `--execute` against a sample project and confirm the plan,
  the dry-run validation, and that nothing changed (`exists`, `is_dirty`).
  Run `--execute` only in a scratch folder the user approved.

## Retired-tool registry

Each skill lists its unported tools in `scripts/retired_tools.json` with the MCP
route to use instead and the modes that still work offline. `BridgeClient`
refuses a listed tool before any network call and prints that route; SKILL.md
marks it *(not ported)* or *(live step not ported)*. When a port lands, delete
its entry and its SKILL.md marks: `test_retired_tools.py` fails while the
registry and the modules that still construct `BridgeClient` around
`UnrealBridge*Library` calls disagree.

## CLI conventions

`<tool>.py <spec> [--execute] [--from-plan FILE] [--reuse-existing] [--project NAME]
[--mcp-url URL] [--out FILE] [--markdown]`. Drop `--endpoint`; it addressed the
retired TCP server.
