# Shared conventions for the UE skills

`unreal-engine-mcp`, `unreal-material-artist`, `niagara-vfx-artist` and
`vfx-flipbook-generator` all follow these rules. Each skill adds only its
domain-specific details.

## Requirements

- Python 3.10 or newer. `unreal-engine-mcp` uses only the standard library; the
  material, Niagara and flipbook skills also need Pillow
  (`pip install -r <skill>/requirements.txt`). Flipbook extraction needs FFmpeg
  (installed, or the `imageio-ffmpeg` package). Entry modules stop with a clear
  message on older interpreters.
- `python skills/unreal-engine-mcp/scripts/run_offline_tests.py` runs all four
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
  operation. See [SKILL.md](../SKILL.md#transport-routing).
- Use the [developer workflow](developer-workflow.md) for scoped edits and
  acceptance, and [debugging and source navigation](debugging-and-source-navigation.md)
  to trace bindings, implementations and failure causes.

## Evidence and logs

- Verify behavior with state and logs: read runtime values (ObjectTools, audits,
  sampled positions/velocities) and log lines, and report the numbers. Gameplay
  Blueprints carry a log path from the start
  ([Blueprint delivery standards](blueprint-delivery-standards.md#3-logging-is-part-of-the-implementation)).
- Capture a screenshot only to answer a named visual question, look at it, and
  report the answer. Material and VFX look reviews are visual questions; a logic
  change is not. Never capture the graph editor or an unrelated editor view as
  evidence, and do not retry a failing capture route in a loop.
- Debug drawing and on-screen prints are development aids, never delivered
  presentation.

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
  side effects, caller); variables get Chinese category paths. Function
  descriptions and variable tooltips have no write route in tested 5.8.4, so the
  handoff includes a description table instead.
- Details and naming: [Chinese module annotations](blueprint-programming-mcp.md#chinese-module-annotations)
  and [Blueprint delivery standards](blueprint-delivery-standards.md#5-chinese-explanations-for-functions-variables-and-modules).
