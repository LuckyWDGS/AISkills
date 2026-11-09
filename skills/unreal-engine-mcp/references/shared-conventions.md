# Shared conventions for the UE skills

`unreal-engine-mcp`, `unreal-sequencer`, `unreal-material-artist`,
`niagara-vfx-artist` and `vfx-flipbook-generator` follow these rules. Each skill adds only its
domain-specific details.

## Requirements

- Python 3.10 or newer. `unreal-engine-mcp` uses only the standard library; the
  Sequencer, material, Niagara and flipbook skills also need Pillow
  (`pip install -r <skill>/requirements.txt`). Flipbook extraction needs FFmpeg
  (installed, or the `imageio-ffmpeg` package). Entry modules stop with a clear
  message on older interpreters.
- `python skills/unreal-engine-mcp/scripts/run_offline_tests.py` runs all five
  offline suites with non-loopback networking blocked; CI runs it on Ubuntu and
  Windows with Python 3.10 and 3.12.
- A UE 5.8+ editor with Epic's `ModelContextProtocol` plugin; Python Remote
  Execution enabled in the target project for MCP-gap operations.

## Editor connection

- Work through background connections only. Do not focus, move, minimize,
  maximize or resize UE windows, send console keystrokes, or drive the editor
  UI unless the user explicitly asks for that UI operation. Never fall back to
  UI automation after a failure.
- Route each operation through Epic's built-in MCP first; for a verified MCP
  gap use stock `unreal.*` APIs over
  [Epic Python Remote Execution](official-python-remote.md) for that one
  operation. Record the engine build, missing operation, inspected live tools,
  chosen public API and readback; return to MCP for the next covered operation.
  See [SKILL.md](../SKILL.md#transport-routing).
- Official API provenance and background operation are separate checks. MCP
  `open_sequence`, `OpenEditorForAsset`, camera/curve editors and legacy capture
  can activate UI. Do not use them as a background workaround. A helper's
  `--allow-editor-ui` flag is for a user-requested UI workflow only; never add
  it automatically after a refusal. Prefer explicit-asset/sequence MCP tools.
- Do not add a custom bridge or C++ plugin to fill an ordinary capability gap.
  Existing project extensions may remain; a new extension is a separate,
  explicitly requested implementation choice, not a prerequisite for delivery.
- Use the [developer workflow](developer-workflow.md) for scoped edits and
  acceptance, and [debugging and source navigation](debugging-and-source-navigation.md)
  to trace bindings, implementations and failure causes.

## Execution boundaries

- Resolve the expected project before writes (`--project`, `--expect-project`
  or `UE_MCP_PROJECT` as supported by the command). Read back the endpoint's
  project, target asset and required schemas. A successful MCP connection alone
  does not identify the intended editor. Use the full `.uproject` path for
  same-named checkouts; a saved session identity is not current process evidence.
- A query-shaped name does not guarantee no side effects. Blueprint node-type
  discovery can create temporary nodes, and MVVM widget binding/model listings
  can create a missing View. Use the domain's verified reads for an audit; see
  the [official capability map](official-capability-map.md).
- Structural edits require a confirmed idle editor; an unknown PIE/Simulate
  state refuses writes. Preserve a user's running session. Runtime verification
  owns and stops only the bounded session it started.
- Inspect first, state the affected graph/module/track, and edit that scope.
  Use a candidate for a destructive rebuild. A duplicate must be saved and
  verified before it counts as a durable backup; transactions are not backups.
- A write timeout has unknown completion. Inspect the affected objects/links
  before deciding whether to repair or retry. Preserve confirmed partial work
  and report it; do not replay a whole batch or hide dirty packages.
- Verify semantics as well as shape. Blueprint variable owner, Target and local
  scope must be proven before replacing a Getter or SET output. Layout-only
  edits must leave node types, defaults and connections unchanged. A lint
  warning alone never authorizes a logic rewrite.

## Evidence and logs

- Verify behavior with state and logs: read runtime values (ObjectTools, audits,
  sampled positions/velocities) and log lines, and report the numbers. Gameplay
  Blueprints carry a log path from the start
  ([Blueprint delivery standards](blueprint-delivery-standards.md#3-logging-is-part-of-the-implementation)).
- Capture a screenshot only to answer a named visual question, look at it, and
  report the answer. Material and VFX look reviews are visual questions; a logic
  change is not. Never capture the graph editor or an unrelated editor view as
  evidence, and do not retry a failing capture route in a loop.
- Debug drawing and on-screen prints are development aids; retain them when
  the user explicitly requests a debug/demo module.
- Keep compile, structural readback, sampled editor evaluation and runtime
  acceptance separate. Empty checks mean collected data, not a pass. Use the
  domain's runtime-acceptance reference only for cases relevant to the change;
  adding a case to a skill does not mean it was run in UE.

### Runtime result record

Record evidence in the project's ignored session directory. One row per case:
`case_id`, `module_id`, asset/graph and map, UE version/CL, network role (or
standalone), trigger, expected result and tolerance, observed values/timestamps,
evidence paths/log window, `pass|fail|not_run|blocked`, and cleanup performed.
Use game time for gameplay timers and state the time dilation; record the
sampling interval and tolerance instead of claiming sub-frame precision.
`blocked` names the unavailable operation; `not_run` means no runtime test was
attempted. Screenshots answer visual questions but do not establish event counts,
timer expiry, state restoration or object destruction.

## Chinese module annotations

- New or modified modules get Chinese comment frames or descriptions, a stable
  searchable module ID, and Chinese notes on non-obvious nodes, timing and
  conditions, using the domain's own metadata: Blueprint comment frames,
  material comment frames plus parameter groups/descriptions, Niagara
  emitter/module display descriptions.
- Preserve existing parameter identifiers, namespaces and bindings; textual
  labels never require runtime Gameplay Tags.
- Read-only audits and local-only work (for example atlas generation) never
  insert annotations into untouched assets.
- Blueprint functions get a Chinese function frame (purpose, inputs, outputs,
  side effects, caller); variables get Chinese category paths. Hover
  descriptions and function categories use official metadata writes when
  discovered. Where unavailable, use comment frames plus a description table
  keyed by asset/graph/module ID as the complete default delivery. The bundled
  MCPBlueprintMetadata plugin is an optional project extension for explicitly
  requested hover metadata; do not install or require it automatically.
- Details and naming: [Chinese module annotations](blueprint-programming-mcp.md#chinese-module-annotations)
  and [Blueprint delivery standards](blueprint-delivery-standards.md#5-chinese-explanations-for-functions-variables-and-modules).
