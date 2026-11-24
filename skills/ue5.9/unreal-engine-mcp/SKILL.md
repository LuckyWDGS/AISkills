---
name: unreal-engine-mcp
description: Drive a running Unreal Engine 5.9 editor through Epic's built-in MCP server to build, inspect and debug games. Use when the task involves Blueprints, Animation Blueprints and state machines, Behavior Trees, StateTree, PCG graphs, Enhanced Input, UMG/MVVM UI, actors, assets, levels, static meshes or packaging; when reading graph logic and pin connections, navigating engine or project source, or diagnosing compile, runtime and crash failures; and as the shared transport for the material, Niagara, Sequencer and flipbook skills.
---

# Unreal Engine MCP (UE 5.9)

> **Scope.** This skill targets UE 5.9 only and was verified on **UE 5.9.0
> Preview, CL 60351404**. A later build can rename tools and arguments, so read
> the live schema before each first call. For a UE 5.8 editor the user links
> `skills/ue5.8/` instead; the client refuses an editor of another engine line.

Use Epic's built-in MCP server through this skill's `scripts/ue_mcp` client.
Follow the [shared conventions](references/shared-conventions.md): background
connections, scoped saves, Chinese module annotations with stable IDs, and the
[evidence levels](references/shared-conventions.md#evidence-levels) used in
every report.

## When to use

- Author or change gameplay: Blueprints, characters, input, UI, AI, levels.
- Explain what an existing graph does, or find the exact pin to change.
- Diagnose a compile error, a runtime failure or a crash, including a trace
  into engine or project source.
- Give the material, Niagara, Sequencer and flipbook skills their editor
  connection. All five skills come from the same `skills/ue5.9/` folder.

## Connect to the intended editor

With two editors, port 8000 belongs to the stable setup and 8001 to the test
editor. Set the endpoint, an absolute project guard and a separate cache for
the current shell:

```powershell
$env:UNREAL_MCP_URL = 'http://127.0.0.1:8001/mcp'
$env:UE_MCP_PROJECT = '<absolute .uproject path>'
$env:UE_MCP_CACHE_DIR = '<repo>/.codex/session/ue59-mcp-state'
python scripts/builtin_mcp.py --no-cache --new-session status
python scripts/builtin_mcp.py --refresh-schema list-toolsets
```

1. `status` reports the listener's process, project, engine version and level.
   Confirm UE 5.9 and the intended absolute project path before any write.
2. `ensure` checks readiness and explains how to start the server. It never
   launches or restarts an editor.
3. After a launch, poll `--timeout 5 status` against a bounded deadline, then
   confirm the domain's toolset is registered and make one safe state read.

Startup options, discovery modes, caching and sessions:
[MCP client](references/mcp-client.md). Keep local paths, schema dumps, scripts
and notes in the ignored `.codex/session/` directory.

## Call a tool

Before the first operation in a domain, read the schema of every tool you will
call, including struct fields, enums, reference shapes and output fields:

```powershell
python scripts/builtin_mcp.py describe-toolset BlueprintToolset --brief
python scripts/builtin_mcp.py describe-tool BlueprintToolset AddVariable
python scripts/builtin_mcp.py call IsPIERunning --toolset EditorAppToolset
python scripts/builtin_mcp.py call <tool> --toolset <toolset> --args-file <session>/args.json
```

Route each operation through the first route that covers it:

1. **Domain tool.** Use the discovered toolset, or `ObjectToolset` reflected
   properties where they cover the operation. Read the value back.
2. **Official Python through MCP.** `PythonScriptingTools` composes tools with
   `await call_tool(...)` and reaches public `unreal.*` APIs for a verified
   domain-tool gap. Run `python-readme` once per conversation and look symbols
   up with `get_symbol` before `execute-python`.
3. **Python Remote Execution**, for an operation neither MCP route covers
   ([reference](references/official-python-remote.md)).

When no route covers the operation, report the operation, the tools checked
and the engine build.

For ordered writes, validate with `batch <steps.jsonl> --dry-run`, then run the
plan. Each step has its own result and optional readback; the batch stops at
the first failure and is not a rollback. Put each save in its own final step.

Two results need care:

- **Not run / This call made no changes** means a slow task refused the call.
  Keep the result and retry after the task ends.
- **A timeout** has unknown completion. Inspect the affected state before
  another write.

## Blueprint and gameplay work

Blueprint is the preferred implementation surface for gameplay. A request for
Blueprint logic is already the language decision: proceed in Blueprint and
recommend C++ only for a demonstrated API limit, a measured performance need
or an existing project convention.

1. **Read first.** Read the entry, owners, variables, components, graphs and
   both ends of each relevant wire. `scripts/inspect_blueprint.py` captures the
   topology read-only ([graph inspection](references/blueprint-graph-inspection.md)).
2. **Author with native tools.** Use native variable and function metadata and
   comment tools. For a scoped rewrite use the Graph DSL: call `Docs`, `Read`
   the exact asset and scope, edit the canonical text with its latest revision,
   and handle `bDslOmitted` and warnings. Re-resolve node and pin references
   after a DSL edit or a compile
   ([Blueprint authoring](references/ue-5.9-blueprint-python.md)).
3. **Deliver to the standard.** Feature brief, production visuals, a state and
   error log path, meaningful functions and tuning variables, Chinese comment
   frames and metadata
   ([delivery standards](references/blueprint-delivery-standards.md)).
4. **Keep the change in scope.** A layout-only change keeps the logic
   signature. An annotation-only change needs text and membership readback,
   without PIE or a whole-graph rearrangement.
5. **Verify.** Compile, read errors and warnings, run the relevant
   [runtime cases](references/runtime-acceptance.md) for changed behavior, and
   finish with `scripts/blueprint_lint.py --strict`.

## Captures

`scripts/capture.py viewport --pose x,y,z,pitch,yaw,roll --out-dir <dir>`
renders the given pose offscreen through `SceneCaptureToolset` and records the
editor view before and after, so the user's camera stays where it was.
`capture.py asset <path>` saves the editor thumbnail. The image is the MCP
image block of the result; a `urn:toolresult` string is a correlation ID, not
a file. Open each image and answer the named visual question.

## Scripts

Status labels are defined in the
[shared conventions](references/shared-conventions.md#engine-version-and-tool-status).

| Script | Status | Use |
|---|---|---|
| `builtin_mcp.py` | `5.9` | Client CLI: status, discovery, call, batch, official Python |
| `capture.py` | `5.9` | Offscreen posed scene capture and asset thumbnails |
| `inspect_blueprint.py` | `5.9` | Read-only Blueprint topology, wires and comment frames |
| `blueprint_lint.py` | `5.9` | Layout, logging and Chinese-annotation lint |
| `reconcile_scene_import.py` | `5.9` | Three-way review of a reimported modular scene |
| `python_remote.py` | `untested` | Epic Python Remote Execution client |
| `fit_reference_camera.py` | `local` | Fit a camera to labelled points in a photo (needs numpy) |
| `blueprint_geometry.py`, `blueprint_comment_geometry.py` | `local` | Node-size and comment-bounds estimates used by the lint |
| `run_offline_tests.py` | `local` | All five offline suites with networking blocked |
| `blueprint_normalize.py`, `blueprint_layout.py` | `unported` | Graph cleanup and layout |
| `pcg_inspect.py` | `unported` | Read-only PCG pins and edges |
| `live_smoke.py`, `record_fixtures.py` | `unported` | Live sampling of the skills' CLIs and fixture recording |

## References

Read only what the task needs.

**Transport and shared rules**

| Need | Read |
|---|---|
| Startup, discovery modes, CLI, batch format, cache and sessions | [MCP client](references/mcp-client.md) |
| Rules shared by the five skills, tool status, evidence levels | [Shared conventions](references/shared-conventions.md) |
| What was verified on this build and the known engine issues | [5.9 audit](references/ue-5.9-preview-audit.md) |
| Coverage per domain and which workflows are still missing | [Tool coverage](references/ue-5.9-tool-coverage.md) |
| Bare-name direct tools, MCP Client, Canvas Bridge and Annotations | [MCP and Canvas plugins](references/ue-5.9-mcp-canvas-plugins.md) |
| Remote Execution for an operation MCP does not cover | [Python Remote Execution](references/official-python-remote.md) |
| Moving an `unported` helper to UE 5.9 | [Porting a helper](references/porting-helpers.md) |

**Gameplay programming**

| Need | Read |
|---|---|
| Blueprint authoring, metadata, Graph DSL, async Python | [Blueprint authoring](references/ue-5.9-blueprint-python.md) |
| What a graph does and how its pins connect | [Graph inspection](references/blueprint-graph-inspection.md) |
| Feature brief, visuals, logging, layout, Chinese explanations, lint | [Delivery standards](references/blueprint-delivery-standards.md) |
| Scoped, recoverable implementation and acceptance | [Developer workflow](references/developer-workflow.md) |
| Compile, runtime and crash diagnosis; source navigation | [Debugging](references/debugging-and-source-navigation.md) |
| Runtime cases for gameplay, animation, UI, GAS, PCG and physics | [Runtime acceptance](references/runtime-acceptance.md) |
| A complete small game: input, HUD, audio, interaction, lifecycle, package | [Game production](references/game-production.md) |

**Animation, AI and UI**

| Need | Read |
|---|---|
| Character AI, Behavior Tree, Blackboard, tasks, animation, observability | [Gameplay AI and animation](references/gameplay-ai-animation.md) |
| Animation Blueprint and state-machine reads, EQS, NavMesh, Input contracts | [Animation and AI tools](references/ue-5.9-animation-ai-tools.md) |
| MVVM HUD, CommonUI menus, UMG and Slate focus or lifetime diagnosis | [UI workflows](references/ue-5.9-ui-workflows.md) |
| UMG authoring, scene capture, profiling, project files | [Editor tools](references/ue-5.9-editor-tools.md) |

**Systems and data**

| Need | Read |
|---|---|
| Data-driven gameplay, GAS, sockets and physics, saves, settings, localization, automation | [Game systems](references/ue-5.9-game-systems.md) |
| StateTree and PCG authoring and evaluation | [StateTree and PCG](references/ue-5.9-statetree-pcg.md) |
| Dataflow, CurveAtlas, enums and structs, Deformer Graph, sequence validation | [Data and graphs](references/ue-5.9-dataflow-data-tools.md) |
| MetaSound, audio, Media, Control Rig, MRQ/MRG Python | [Audio, media and render](references/ue-5.9-audio-media-tools.md) |

**Meshes, scenes and rendering**

| Need | Read |
|---|---|
| Geometry, StaticMesh, Texture and TextureGraph contracts | [Geometry and textures](references/ue-5.9-geometry-texture-tools.md) |
| Canvas mesh graphs, GeometryScript assemblies, StaticMesh import | [Canvas mesh generation](references/ue-5.9-canvas-mesh.md) |
| Hard-surface modeling from a reference image, GLB assemblies | [Reference-guided meshes](references/ue-5.9-reference-mesh.md) |
| An interior rebuilt from photos: graybox, camera match, reimport, walkthrough | [Reference interiors](references/ue-5.9-reference-interiors.md) |
| Canvas model availability, image generation, isolated MRG renders | [Generation and render checks](references/ue-5.9-canvas-generation-render.md) |
| Canvas, AI animation, Fab, Lumen/OIT/wind and Web target dependencies | [Production feature matrix](references/ue-5.9-production-feature-matrix.md) |

**Sibling skills**

| Need | Use |
|---|---|
| Materials, shaders, statistics, diffs, Material Instances | [unreal-material-artist](../unreal-material-artist/SKILL.md) |
| Niagara systems, emitters, renderers, user parameters | [niagara-vfx-artist](../niagara-vfx-artist/SKILL.md) |
| Level Sequences, cameras, cinematics, Control Rig | [unreal-sequencer](../unreal-sequencer/SKILL.md) |
| Flipbook atlas generation and handoff | [vfx-flipbook-generator](../vfx-flipbook-generator/SKILL.md) |
