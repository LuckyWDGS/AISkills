"""Audit a Material, Material Instance or Material Function through Epic's built-in MCP.

Graph, parameters, instance chain and usage flags come from one ProgrammaticToolset
script. Output-pin wiring uses direct MaterialTools calls (the script path cannot
pass some EMaterialProperty values). Shader statistics are an MCP gap and use
``MaterialEditingLibrary.get_statistics`` over Epic Python Remote Execution.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, builtin_mcp, python_remote


MATERIAL_PROPERTIES = [
    "MP_BaseColor", "MP_Metallic", "MP_Specular", "MP_Roughness", "MP_Anisotropy", "MP_EmissiveColor",
    "MP_Opacity", "MP_OpacityMask", "MP_Normal", "MP_Tangent", "MP_WorldPositionOffset",
    "MP_SubsurfaceColor", "MP_CustomData0", "MP_CustomData1", "MP_AmbientOcclusion", "MP_Refraction",
    "MP_PixelDepthOffset", "MP_ShadingModel", "MP_FrontMaterial", "MP_SurfaceThickness",
    "MP_Displacement", "MP_MaterialAttributes", "MP_DiffuseColor", "MP_SpecularColor",
] + [f"MP_CustomizedUVs{index}" for index in range(8)]

# Expression classes with no input pins; skipping them saves one editor call each.
NO_INPUT_CLASSES = {
    "Constant", "Constant2Vector", "Constant3Vector", "Constant4Vector", "ScalarParameter",
    "VectorParameter", "StaticBool", "StaticBoolParameter", "TextureCoordinate", "Time",
    "ActorPositionWS", "WorldPosition", "LocalPosition", "CameraPositionWS", "VertexColor",
    "ParticleColor", "VertexNormalWS", "PixelNormalWS", "ObjectPositionWS", "ScreenPosition",
    "ViewSize", "TextureObject", "TextureObjectParameter", "Comment", "NamedRerouteUsage",
    "ParticleSubUV", "DynamicParameter", "CollectionParameter", "PerInstanceRandom",
}
IGNORE_FOR_DEAD = {"Comment", "FunctionInput", "FunctionOutput", "NamedRerouteDeclaration"}
INSTANCE_CLASSES = {"MaterialInstanceConstant", "MaterialInstanceDynamic", "MaterialInstance"}
MATERIAL_INFO_PROPS = ["materialDomain", "blendMode", "shadingModel", "usedShadingModels", "twoSided", "bUseMaterialAttributes"]
COVERAGE_GAPS = [
    "Material compile errors are not exposed by MaterialTools; check MessageLog/LogsToolset after recompile.",
    "NamedRerouteUsage does not expose its declaration; declarations count as live when any usage is live, "
    "so dead nodes behind an unused named reroute may be missed.",
]


def object_path(asset_path: str) -> str:
    """'/Game/M/M_X' -> '/Game/M/M_X.M_X'; full object paths pass through."""
    if re.match(r"^[A-Za-z]:[/\\]", asset_path):
        raise SystemExit(f"{asset_path!r} is a filesystem path; Git Bash rewrote '/Game/...'. Re-run with MSYS_NO_PATHCONV=1.")
    if "." in asset_path.rsplit("/", 1)[-1]:
        return asset_path
    return f"{asset_path}.{asset_path.rsplit('/', 1)[-1]}"


def expression_class(ref_path: str) -> str:
    """Class short name from a default-named expression object, e.g. MaterialExpressionAdd_3 -> Add."""
    name = ref_path.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
    name = re.sub(r"_\d+$", "", name)
    return name[len("MaterialExpression"):] if name.startswith("MaterialExpression") else name


def ref_of(value: Any) -> str:
    """Object references arrive as {"refPath": ...}, a bare path string, or None/"None"."""
    if isinstance(value, dict):
        return value.get("refPath") or ""
    return value if isinstance(value, str) and value != "None" else ""


def node_id(ref_path: str | None) -> str:
    return (ref_path or "").rsplit(":", 1)[-1]


def build_collect_script(asset_path: str) -> str:
    """ProgrammaticToolset script; every call in it must succeed or the whole script fails."""
    return textwrap.dedent(
        """
        import json
        import re

        TARGET = __TARGET__
        INFO_PROPS = __INFO_PROPS__
        NO_INPUT = set(__NO_INPUT__)
        INSTANCES = set(__INSTANCES__)
        M = "editor_toolset.toolsets.material.MaterialTools."
        MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools."
        O = "editor_toolset.toolsets.object.ObjectTools."

        def call(tool, **args):
            # Tool results are strict dicts (no .get default); round-trip to plain JSON types.
            return json.loads(json.dumps(execute_tool(tool, json.dumps(args))["returnValue"]))

        def ref_of(value):
            # Object references arrive as {"refPath": ...} or as a bare path string.
            if isinstance(value, dict):
                return value.get("refPath") or ""
            return value if isinstance(value, str) and value != "None" else ""

        def props(ref, names):
            value = call(O + "get_properties", instance=ref, properties=names)
            return json.loads(value) if isinstance(value, str) else value

        def class_name(ref):
            return ref_of(call(O + "get_class", instance=ref)).rsplit(".", 1)[-1]

        def short_class(ref_path):
            name = re.sub(r"_\\d+$", "", ref_path.rsplit(":", 1)[-1])
            return name[len("MaterialExpression"):] if name.startswith("MaterialExpression") else name

        def overrides(values, key):
            rows = []
            for item in values or []:
                rows.append({"name": item["parameterInfo"]["name"], "param_type": key, "value": item.get("parameterValue"),
                             "expression_guid": item.get("expressionGUId", "")})
            return rows

        def run():
            target = {"refPath": TARGET}
            target_class = class_name(target)
            chain = []
            current, current_class = target, target_class
            while current_class in INSTANCES and len(chain) < 16:
                values = props(current, ["parent", "scalarParameterValues", "vectorParameterValues", "textureParameterValues"])
                chain.append({
                    "path": current["refPath"], "class": current_class,
                    "parent": ref_of(values.get("parent")),
                    "overrides": overrides(values.get("scalarParameterValues"), "Scalar")
                    + overrides(values.get("vectorParameterValues"), "Vector")
                    + overrides(values.get("textureParameterValues"), "Texture"),
                })
                if not chain[-1]["parent"]:
                    break
                current = {"refPath": chain[-1]["parent"]}
                current_class = class_name(current)
            base, base_class = current, current_class

            info = {}
            usage_flags = []
            if base_class == "Material":
                available = json.loads(call(O + "list_properties", instance=base))
                info = props(base, [name for name in INFO_PROPS if name in available])
                usage_names = sorted(name for name in available if name.startswith("bUsedWith"))
                usage_values = props(base, usage_names) if usage_names else {}
                usage_flags = [name[len("bUsedWith"):] for name in usage_names if usage_values.get(name)]

            parameters = {}
            for ref in ([target] + ([base] if base is not target else [])):
                if class_name(ref) != "MaterialFunction":
                    parameters[ref["refPath"]] = call(MI + "list_parameters", material=ref)

            nodes = []
            if base_class in ("Material", "MaterialFunction"):
                for expr_path in [ref_of(item) for item in call(M + "get_expressions", material_or_function=base)]:
                    expr = {"refPath": expr_path}
                    cls = short_class(expr_path)
                    node = {"id": expr_path, "class_name": cls, "inputs": []}
                    if cls not in NO_INPUT:
                        node["inputs"] = [
                            {"input_name": pin["input_name"], "output_name": pin["output_name"],
                             "source": ref_of(pin.get("expression"))}
                            for pin in call(M + "get_expression_inputs", material_or_function=base, expression=expr)
                        ]
                    if "Parameter" in cls and "Collection" not in cls:
                        node.update(props(expr, ["parameterName", "group"]))
                    elif cls == "MaterialFunctionCall":
                        node["function"] = ref_of(props(expr, ["materialFunction"]).get("materialFunction"))
                    nodes.append(node)

            return {
                "target": TARGET, "target_class": target_class,
                "base": base["refPath"], "base_class": base_class,
                "instance_chain": chain, "info": info, "usage_flags": usage_flags,
                "parameters": parameters, "nodes": nodes,
            }
        """
    ).strip().replace("__TARGET__", json.dumps(asset_path)) \
        .replace("__INFO_PROPS__", json.dumps(MATERIAL_INFO_PROPS)) \
        .replace("__NO_INPUT__", json.dumps(sorted(NO_INPUT_CLASSES))) \
        .replace("__INSTANCES__", json.dumps(sorted(INSTANCE_CLASSES)))


def collect_output_connections(module: Any, client: Any, material_path: str) -> list[dict[str, Any]]:
    rows = []
    for prop in MATERIAL_PROPERTIES:
        result = client.call_resolved_tool("MaterialTools", "get_property_input", {
            "material": {"refPath": material_path}, "material_property": prop,
        })
        value = module._decode_text_value(result)
        value = value.get("returnValue", value) if isinstance(value, dict) else value
        source = ref_of((value or {}).get("expression"))
        if source:
            rows.append({"property": prop, "source": source, "output_name": value.get("output_name", "")})
    return rows


STATS_SCRIPT = """
import json, unreal
asset = unreal.load_asset({path!r})
stats = unreal.MaterialEditingLibrary.get_statistics(asset)
fields = ["num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers",
          "num_vertex_texture_samples", "num_pixel_texture_samples", "num_virtual_texture_samples",
          "num_uv_scalars", "num_interpolator_scalars"]
print(json.dumps({{name: getattr(stats, name) for name in fields if hasattr(stats, name)}}))
"""


def collect_shader_stats(skill_root: Path, asset_path: str, project: str | None) -> dict[str, Any]:
    remote = python_remote(skill_root)
    try:
        result = remote.run_python(STATS_SCRIPT.format(path=asset_path), project=project)
    except Exception as exc:  # Remote Execution disabled, no/ambiguous editor, missing engine module.
        return {"ready": False, "transport": "python-remote-execution", "error": str(exc)}
    if not result.get("success"):
        return {"ready": False, "transport": "python-remote-execution",
                "error": remote.stdout_of(result, kinds=("Error",)) or str(result.get("result"))}
    try:
        stats = json.loads(remote.stdout_of(result).strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {"ready": False, "transport": "python-remote-execution", "error": f"unparseable statistics: {exc}"}
    return {"ready": True, "transport": "python-remote-execution", "node": result["node"].get("project_name"), **stats}


def trace_graph(nodes: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {node["id"]: node for node in nodes}
    upstream: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        for pin in node.get("inputs", []):
            if pin.get("source"):
                upstream[node["id"]].add(pin["source"])

    def walk(start: str) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current and current not in seen:
                seen.add(current)
                stack.extend(upstream.get(current, ()))
        return seen

    roots = [(row["property"], row["source"]) for row in outputs]
    roots += [("FunctionOutput", node["id"]) for node in nodes if node["class_name"] == "FunctionOutput"]
    live: set[str] = set()
    chains = []
    for prop, source in roots:
        reachable = walk(source)
        live |= reachable
        chains.append({"property": prop, "src_guid": node_id(source), "reachable_count": len(reachable),
                       "reachable_nodes": sorted(node_id(item) for item in reachable)})
    # Usage -> declaration links are not exposed, so keep every declaration live once any usage is.
    if any(by_id[item]["class_name"] == "NamedRerouteUsage" for item in live if item in by_id):
        for node in nodes:
            if node["class_name"] == "NamedRerouteDeclaration" and node["id"] not in live:
                live |= walk(node["id"])
    dead = [
        {"guid": node_id(node["id"]), "class_name": node["class_name"], "caption": node.get("parameterName", ""),
         "parameter_name": node.get("parameterName", "")}
        for node in nodes if node["id"] not in live and node["class_name"] not in IGNORE_FOR_DEAD
    ]
    return {
        "node_count": len(nodes),
        "live_count": len(live & set(by_id)),
        "live_node_guids": sorted(node_id(item) for item in live if item in by_id),
        "dead_nodes": dead,
        "output_chains": chains,
    }


def stale_overrides(chain: list[dict[str, Any]], parameters: dict[str, list[dict[str, Any]]], base: str) -> list[dict[str, Any]]:
    valid = {item["name"] for item in parameters.get(base, [])}
    if not chain or not valid:
        return []
    # A zero expression GUID marks an engine-managed override such as RefractionDepthBias.
    return [
        {**override, "instance": layer["path"]}
        for layer in chain for override in layer["overrides"]
        if override["name"] not in valid and override.get("expression_guid", "").strip("0-")
    ]


def findings(report: dict[str, Any], instruction_budget: int, sampler_budget: int) -> list[dict[str, Any]]:
    rows = []
    for node in report["graph_summary"]["dead_nodes"]:
        if node["parameter_name"]:
            rows.append({"rule_id": "unused_parameter", "severity": "warning", "expression_guid": node["guid"],
                         "expression_class": node["class_name"],
                         "message": f"Parameter `{node['parameter_name']}` does not reach any output."})
        else:
            rows.append({"rule_id": "dead_expression", "severity": "info", "expression_guid": node["guid"],
                         "expression_class": node["class_name"],
                         "message": f"`{node['class_name']}` does not reach any output."})
    for override in report["stale_overrides"]:
        rows.append({"rule_id": "stale_override", "severity": "warning",
                     "message": f"Override `{override['name']}` on `{override['instance']}` matches no parent parameter."})
    stats = report["analysis"]["shader_stats"]
    if stats.get("ready"):
        if instruction_budget and stats.get("num_pixel_shader_instructions", 0) > instruction_budget:
            rows.append({"rule_id": "instruction_budget", "severity": "error",
                         "message": f"{stats['num_pixel_shader_instructions']} pixel instructions exceed budget {instruction_budget}."})
        if sampler_budget and stats.get("num_samplers", 0) > sampler_budget:
            rows.append({"rule_id": "sampler_budget", "severity": "error",
                         "message": f"{stats['num_samplers']} samplers exceed budget {sampler_budget}."})
    return rows


PARAMETER_GROUPS = {"Scalar": "scalar_parameters", "Vector": "vector_parameters",
                    "Texture": "texture_parameters", "StaticSwitch": "static_switch_parameters"}


def grouped_parameters(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in PARAMETER_GROUPS.values()}
    for row in rows:
        key = PARAMETER_GROUPS.get(row.get("type", ""), "other_parameters")
        groups.setdefault(key, []).append({"name": row["name"], "param_type": row.get("type", ""), "value": None, "guid": ""})
    return groups


def legacy_raw_graph(raw: dict[str, Any], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Raw graph in the shape graph_diff_refactor compares (object names stand in for GUIDs)."""
    nodes, connections = [], []
    for node in raw["nodes"]:
        nodes.append({
            "guid": node_id(node["id"]), "class_name": node["class_name"], "caption": node.get("parameterName", ""),
            "desc": "", "x": None, "y": None,
            "input_names": [pin["input_name"] for pin in node.get("inputs", [])], "output_names": [],
            "key_properties": {key: node[key] for key in ("parameterName", "group", "function") if node.get(key)},
        })
        for index, pin in enumerate(node.get("inputs", [])):
            if pin.get("source"):
                connections.append({
                    "src_guid": node_id(pin["source"]), "src_output_name": pin.get("output_name", ""), "src_output_index": -1,
                    "dst_guid": node_id(node["id"]), "dst_input_name": pin["input_name"], "dst_input_index": index,
                    "dst_property_name": "",
                })
    output_connections = [
        {"src_guid": node_id(row["source"]), "src_output_name": row.get("output_name", ""), "src_output_index": -1,
         "dst_guid": "", "dst_input_name": "", "dst_input_index": -1, "dst_property_name": row["property"]}
        for row in outputs
    ]
    return {"found": True, "path": raw["base"], "is_material_function": raw["base_class"] == "MaterialFunction",
            "nodes": nodes, "connections": connections, "output_connections": output_connections}


def audit(skill_root: Path, asset_path: str, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
          project: str | None = None, shader_stats: bool = True,
          instruction_budget: int = 0, sampler_budget: int = 0) -> dict[str, Any]:
    module = builtin_mcp(skill_root)
    client = module.UnrealMcpClient(url, module.DEFAULT_PROTOCOL, timeout, cache_dir=module.default_cache_dir())
    try:
        client.initialize()
        raw = client.run_tool_script(build_collect_script(object_path(asset_path)))
        outputs = collect_output_connections(module, client, raw["base"]) if raw["base_class"] == "Material" else []
    finally:
        client.close()

    nodes = raw["nodes"]
    if not shader_stats:
        stats = {"ready": False, "error": "skipped (--no-shader-stats)"}
    elif raw["base_class"] != "Material":
        stats = {"ready": False, "error": f"not applicable to {raw['base_class']}"}
    else:
        stats = collect_shader_stats(skill_root, asset_path, project)
    params = raw["parameters"]
    info = raw["info"]
    shading_models = [item.strip() for item in str(info.get("usedShadingModels") or "").split(",") if item.strip()]
    chain = raw["instance_chain"]
    layers = [
        {"name": layer["path"].rsplit(".", 1)[-1], "path": layer["path"], "is_base_material": False,
         "override_parameters": layer["overrides"]}
        for layer in chain
    ]
    layers.append({"name": raw["base"].rsplit(".", 1)[-1], "path": raw["base"], "is_base_material": True, "override_parameters": []})
    report: dict[str, Any] = {
        "tool": "material_audit",
        "material_path": asset_path,
        "transport": {"graph": "epic-mcp ProgrammaticToolset", "outputs": "epic-mcp MaterialTools",
                      "shader_stats": stats.get("transport", "not-run")},
        "material_info": {
            "found": True,
            "name": raw["target"].rsplit(".", 1)[-1],
            "path": raw["target"],
            "class": raw["target_class"],
            "is_material_instance": bool(chain),
            "parent_path": chain[0]["parent"] if chain else "",
            "base_path": raw["base"],
            "base_class": raw["base_class"],
            "material_domain": info.get("materialDomain", ""),
            "blend_mode": info.get("blendMode", ""),
            "shading_model": info.get("shadingModel", ""),
            "shading_models": shading_models,
            "two_sided": info.get("twoSided"),
            "use_material_attributes": info.get("bUseMaterialAttributes"),
            "usage_flags": raw["usage_flags"],
            **grouped_parameters(params.get(raw["target"], [])),
            "num_expressions": len(nodes),
            "num_function_calls": sum(1 for node in nodes if node["class_name"] == "MaterialFunctionCall"),
            "function_dependencies": sorted({node["function"] for node in nodes if node.get("function")}),
        },
        "instance_chain": {"found": True, "path": raw["target"], "layers": layers},
        "graph_summary": trace_graph(nodes, outputs),
        "stale_overrides": stale_overrides(chain, params, raw["base"]),
        "analysis": {
            "found": True,
            "path": raw["target"],
            "material_domain": info.get("materialDomain", ""),
            "shading_models": shading_models,
            "max_instructions": stats.get("num_pixel_shader_instructions", 0) if stats.get("ready") else 0,
            "sampler_count": stats.get("num_samplers", 0) if stats.get("ready") else 0,
            "expression_count": len(nodes),
            "instruction_budget": instruction_budget,
            "sampler_budget": sampler_budget,
            "compile_errors": [],
            "shader_stats_ready": bool(stats.get("ready")),
            "shader_stats": stats,
        },
        "coverage_gaps": COVERAGE_GAPS,
    }
    report["analysis"]["findings"] = findings(report, instruction_budget, sampler_budget)
    report["raw_graph"] = legacy_raw_graph(raw, outputs)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    info = report["material_info"]
    stats = report["analysis"]["shader_stats"]
    graph = report["graph_summary"]
    stat_line = (
        f"pixel `{stats.get('num_pixel_shader_instructions')}` / vertex `{stats.get('num_vertex_shader_instructions')}` instructions, "
        f"`{stats.get('num_samplers')}` samplers" if stats.get("ready") else f"unavailable ({stats.get('error') or 'skipped'})"
    )
    lines = [
        f"# Material Audit: {report['material_path']}",
        "",
        f"- Class: `{info['class']}`" + (f" → base `{info['base_path']}`" if info["is_material_instance"] else ""),
        *([
            f"- Domain / blend / shading: `{info['material_domain']}` / `{info['blend_mode']}` / `{info['shading_model']}`",
            f"- Usage flags: `{', '.join(info['usage_flags']) or 'none'}`",
        ] if info["base_class"] == "Material" else []),
        f"- Expressions: `{info['num_expressions']}` (live `{graph['live_count']}`), function calls `{info['num_function_calls']}`",
        f"- Shader stats: {stat_line}",
        "",
        "## Findings",
        "",
    ]
    rows = report["analysis"]["findings"]
    lines.extend(f"- [{row['severity']}] `{row['rule_id']}` {row['message']}" for row in rows)
    if not rows:
        lines.append("- No findings.")
    lines.extend(["", "## Output chains", ""])
    lines.extend(f"- `{row['property']}` ← `{row['src_guid']}` ({row['reachable_count']} nodes)" for row in graph["output_chains"])
    if not graph["output_chains"]:
        lines.append("- No connected outputs.")
    lines.extend(["", "## Coverage gaps", ""])
    lines.extend(f"- {gap}" for gap in report["coverage_gaps"])
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    report = audit(
        ctx.skill_root, args.material_path, url=args.mcp_url, timeout=args.timeout, project=args.project,
        shader_stats=not args.no_shader_stats,
        instruction_budget=args.instruction_budget, sampler_budget=args.sampler_budget,
    )
    if not args.include_raw_graph:
        report.pop("raw_graph")
    json_out = Path(args.out) if args.out else default_report_path(ctx, "audits/material", slugify(args.material_path), "material-audit", ".json")
    save_json(json_out, report)
    if args.markdown:
        write_text(json_out.with_suffix(".md"), render_markdown(report))
    print(json_out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit an Unreal material, material instance or material function through Epic's built-in MCP.")
    parser.add_argument("material_path")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--project", help="Editor for shader statistics over Python Remote Execution (name or .uproject)")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-shader-stats", action="store_true", help="Skip the Remote Execution statistics step")
    parser.add_argument("--instruction-budget", type=int, default=0)
    parser.add_argument("--sampler-budget", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--include-raw-graph", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
