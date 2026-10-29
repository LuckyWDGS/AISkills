# Niagara through Epic MCP

Checked: 2026-10-28, installed UE 5.8.4 / CL 58902052.

## Primary route

Use Epic's ModelContextProtocol server directly and inspect live Niagara
toolsets. Official source is under
`Engine/Plugins/Experimental/Toolsets/NiagaraToolsets/Source/NiagaraToolsets/Private/`.
The earlier recommendation to keep UnrealBridge as the control spine and port
Epic functions into custom C++ wrappers is superseded.

Use the sibling `unreal-engine-mcp/scripts/builtin_mcp.py` for discovery and calls.
Read ProgrammaticToolset's execution environment before batching registered
tools. Its sandbox is orchestration, not arbitrary unreal Python.

## Installed official coverage

| Operation | Official tools / model |
|---|---|
| Discovery | Assets script search/digests, discovery info, Info enum inspection |
| System creation | CreateNiagaraSystem from a template |
| Structure | GetSystemSummary, GetEmitterSummary, emitter/script/module/input topology |
| Schemas | System, emitter, renderer, data interface, module, dynamic input, stack input |
| System/emitter/renderer data | Corresponding Get/Set data tools |
| Emitters | AddEmitter, RemoveEmitter |
| Renderers | AddRenderer, RemoveRenderer, renderer schema/data including Ribbon |
| Modules | AddModule, RemoveModule, SetModuleEnabled |
| Set Parameters | Add module, add/remove parameter entry |
| Stack values | GetStackInputData, SetStackInputData, module/script/emitter input values |
| User variables | System add/remove/read; component Get/Set and SetSystem |
| Dependencies | GetSystemDependencies |
| Diagnostics | Async GetSystemCompileState, GetStackIssues, ApplyStackIssueFix |
| Blueprint wrappers | Construct from System or Component |

Discover current references, fields, enums, defaults, and required fields.
GetSystemSummary is the installed source name; old GetSystemInfo examples are
historical. Re-query topology after structural edits; do not synthesize stack
identifiers or overwrite raw EmitterHandles.

Ribbon convenience is not a capability gap: inspect AddRenderer plus renderer
schema/data and Epic templates first. Rapid-iteration helpers also overlap
semantically with stack value editing; inspect the current stack schema before
declaring a custom setter necessary.

## Validation and legacy boundaries

The 5.8.4 live audit found all five Niagara toolsets (56 tools). System summary,
emitter topology, Ribbon renderer schema, compile state and stack issues were
successfully read through official HTTP, with no custom plugin. No Niagara
asset writes were exercised.

On first load of a previously unopened Epic template, GetSystemCompileState and
GetStackIssues waited on pending compilation; a longer client request received
the engine's own 120-second compile-wait timeout. Opening that asset through
`EditorAppToolset.OpenEditorForAsset` let compilation finish. Both diagnostics
then succeeded: UpToDate, no errors/warnings; the package remained clean. For
this symptom, check compilation and open the intended asset with official tools
before declaring an MCP gap. A timeout is not proof that the HTTP parser failed.
Do not blindly retry a state-changing operation after a timeout.

Prefer official structural readback, compile state, and stack issues before
visual tuning. Local reports still own composite roles, renderer/material
contracts, accepted anchors, image QA, comparisons, and delivery. They can
consume official evidence without making UnrealBridge mandatory.

UnrealBridge (custom plugin + TCP) is retired. The editor-connected modes of
`niagara_asset_assistant` apply, `niagara_param_sweep`, `runtime_control_probe`, `live_asset_verify`, `controlled_preview`, `effect_control_schema` live reads, `asset_cleanup` execute, `ue_write_helpers`, and `flipbook_ue_pipeline` call `UnrealBridge*Library` APIs and fail fast until ported to MCP.
Their offline plan/report modes still work.

`niagara_audit.py` is ported: one ProgrammaticToolset script reads the system
summary/data/dependencies and each emitter's data, topology and renderer data,
then maps them onto the report shape `delivery_package` and the integration probe
already consume. Mesh renderers without override materials report the mesh's
material slots (`material_source: mesh-slots`). Data-interface values such as a
ParticleRead `EmitterBinding` are `StackInputData_Unsupported`, so attribute-reader
roles come from module names and `data_interface_bindings` stays empty; the
report lists this under `coverage_gaps`. `niagara_material_integration_probe`
reads renderer bindings from the audit's renderer data instead of the plugin.

Port the remaining writers (for example `niagara_asset_assistant` apply) with
[porting legacy writers](../../unreal-engine-mcp/references/porting-legacy-writers.md):
live facts, a pure plan, then `builtin_mcp.py batch` with readbacks.

Possible fallback candidates include specialized particle event-handler
construction, private-property diagnostics, live control/provenance probes,
and exact legacy preview features. These are candidates, not permanent gaps:
inspect live tools and official APIs first. Record one missing operation,
candidate schemas, engine version, and error/readback evidence; return to MCP
for subsequent covered steps.

A historical ToolsetRegistry hang does not prove the current HTTP tool is
broken. Diagnose response mode, readiness, compile state, and target references.
After an ambiguous write timeout, inspect state before retrying or switching
transport to prevent duplicate emitters/modules.

## Release evidence

[UE 5.8 release notes](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes)
introduce experimental MCP.
[5.8.4 Hotfix Released](https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775)
lists an audio sampling DI shutdown assertion fix under Niagara, and no
announced additional MCP tools. Source coverage and live counts must not be
described as additions made specifically by 5.8.4 without an older-build
schema comparison.
