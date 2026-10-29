# Epic MCP and local material workflow

Checked: 2026-10-28, installed UE 5.8.4 / CL 58902052.

## Control path

Use Epic's ModelContextProtocol server directly. The sibling
`unreal-engine-mcp/scripts/builtin_mcp.py` discovers search mode (three meta tools)
and native mode (individual qualified tools). Read live schemas before calls;
domain plugins must be loaded in the active project.

Installed Epic source:
`Engine/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/`.
MaterialTools delegates graph operations to UMaterialEditingLibrary. These
are Epic tools, not project-local replacements. Module prefixes can change;
never hard-code the old `toolset_registry.toolsets.core.*` namespace.

## Coverage in the installed source

| Need | Official surface | Local responsibility |
|---|---|---|
| Material, function, MPC creation | MaterialTools create_material, create_function, create_parameter_collection | Render contract and naming |
| Expression discovery/create/delete | list_expression_classes, add_expression, delete_expression, get_expressions | Interpret graph intent |
| Graph readback and wiring | Pin names, get_expression_inputs, get_property_input, connect/disconnect tools | Validate expected outputs and visual result |
| Expression/material/texture properties | ObjectTools list/get/set/reset properties | Supported fields and role-correct values |
| Compile/layout/cleanup | MaterialTools recompile, layout_expressions, delete_unused_expressions | Confirm actual compile evidence; no invented statistics |
| MI lifecycle and overrides | MaterialInstanceTools scalar/vector/texture/static-switch, parent, clear, override tools | Parameter ownership and permutation budgets |
| Texture import | TextureTools import_file/get_size; ObjectTools properties; AssetTools save | Alpha/channel/POT checks and source provenance |
| Asset lifecycle/references | AssetTools duplicate/move/save/dirty/dependencies/referencers | Scoped changes and readback |
| Multi-step orchestration | ProgrammaticToolset get_execution_environment/execute_tool_script | Registered tools within the official sandbox |
| Carrier previews | Official scene/editor/capture tools where exposed | Deterministic setup, comparison, acceptance |
| Specialized compile stats/private fields | No equivalence established by source names alone | Check live tools; document a narrow gap if needed |
| Images, atlases, reports, contracts | Local file tools | No editor plugin needed |

Installed source counts: MaterialTools 22, MaterialInstanceTools 13,
ObjectTools 6, TextureTools 2, AssetTools 21, ProgrammaticToolset 2.
These counts are not runtime availability or a hotfix delta.

The 2026-10-28 live 5.8.4 audit matched those counts and successfully read a
project material's expressions and exposed parameters, material property schema
and values, and a texture's dimensions. The material CLI also resolved
`material:get_expressions` and saved `transport: epic-mcp-http` with a successful
result. This confirms the direct transport route, not graph-write, texture-import
or shader-statistics coverage; those writes were not exercised by the audit.

add_expression returns an expression UObject reference. Use it with ObjectTools
and graph connection tools; lack of a custom GUID is not a capability gap.
Query current pins/enums rather than translating old bridge schemas.
Read back after writes and save intended assets.

## CLI and legacy boundaries

`tools/official_toolsets_bridge.py` retains its filename for compatibility,
but defaults to direct MCP HTTP:

```powershell
python tools/official_toolsets_bridge.py material:get_expressions --input args.json --markdown
python tools/official_toolsets_bridge.py texture:import_file --input import-args.json --markdown
```

The JSON file must match the live schema. `--mcp-url` or UNREAL_MCP_URL selects
the editor endpoint. Reports record actual transport and resolved toolset. Tool
errors produce a failed report and nonzero exit code, without retry.

UnrealBridge (custom plugin + TCP) is retired. Older pipelines still construct
`BridgeClient`, which now runs over Epic's Python Remote Execution.
Their editor-connected modes call retired `UnrealBridge*Library` APIs and now
fail fast: `graph_refactor_apply`, `material_asset_library register-material`,
`material_domain_audit`, `material_domain_rebuilder`,
`material_function_linter`, `material_preview`,
`material_toolset_builder build` / `recipe --execute`, `runtime_param_trace`,
`shader_permutation_report`, `texture_import_audit`, and `texture_import_fix`.
Their offline planning/report modes still work. Perform the live step with MCP
tools, save the result JSON, and feed it into the local report code. Each is
pending a port to MCP. `scripts/retired_tools.json` lists each unported tool with the MCP route to use instead;
running one prints that route immediately. `material_audit` (read) and `material_instance_batch` (write) are ported and
are the reference patterns; follow
[porting legacy writers](../../unreal-engine-mcp/references/porting-legacy-writers.md)
for the remaining writers.

For an operation no MCP tool covers, use a stock `unreal.*` API through
`../unreal-engine-mcp/scripts/python_remote.py`. Record the uncovered operation,
engine version, candidate live tools inspected, and readback. Return to MCP for
the next covered step.

## Version evidence

[UE 5.8 release notes](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes)
introduce experimental MCP.
[5.8.4 Hotfix Released](https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775)
(2026-10-20) lists a fix for programmatic material Usage Flags leaving
CachedExpressionData stale, plus material root-pin undo and shader compiler
fixes. It does not announce additional MCP tools. This does not prove the
complete 5.8.0 and 5.8.4 schemas are identical.
