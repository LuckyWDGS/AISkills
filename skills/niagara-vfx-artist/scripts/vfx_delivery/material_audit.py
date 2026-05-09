from __future__ import annotations

import argparse
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def build_ue_script(material_path: str, instruction_budget: int, sampler_budget: int) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary

        def guid_text(value):
            try:
                return value.to_string()
            except Exception:
                return str(value)

        def serialize_param(param):
            return {{
                "name": param.name,
                "param_type": param.param_type,
                "value": param.value,
            }}

        def serialize_param_default(param):
            return {{
                "name": param.name,
                "param_type": param.param_type,
                "value": param.value,
                "guid": guid_text(param.guid),
            }}

        def serialize_node(node):
            return {{
                "guid": guid_text(node.guid),
                "class_name": node.class_name,
                "caption": node.caption,
                "desc": node.desc,
                "x": node.x,
                "y": node.y,
                "input_names": list(node.input_names),
                "output_names": list(node.output_names),
                "key_properties": node.key_properties,
            }}

        def serialize_connection(connection):
            return {{
                "src_guid": guid_text(connection.src_guid),
                "src_output_name": connection.src_output_name,
                "src_output_index": connection.src_output_index,
                "dst_guid": guid_text(connection.dst_guid),
                "dst_input_name": connection.dst_input_name,
                "dst_input_index": connection.dst_input_index,
                "dst_property_name": connection.dst_property_name,
            }}

        def serialize_finding(finding):
            return {{
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "message": finding.message,
                "expression_guid": guid_text(finding.expression_guid),
                "expression_class": finding.expression_class,
                "detail": finding.detail,
            }}

        info = MAT.get_material_info({material_path!r})
        graph = MAT.get_material_graph({material_path!r})
        analysis = MAT.analyze_material({material_path!r}, {instruction_budget}, {sampler_budget})
        chain = MAT.list_material_instance_chain({material_path!r})
        mi = MAT.get_material_instance_parameters({material_path!r}) if info.is_material_instance else None
        parent_info = MAT.get_material_info(info.parent_path) if info.is_material_instance and info.parent_path else None

        payload = {{
            "material_info": {{
                "found": info.found,
                "name": info.name,
                "path": info.path,
                "is_material_instance": info.is_material_instance,
                "parent_path": info.parent_path,
                "base_path": info.base_path,
                "material_domain": info.material_domain,
                "blend_mode": info.blend_mode,
                "shading_models": list(info.shading_models),
                "two_sided": info.two_sided,
                "use_material_attributes": info.use_material_attributes,
                "usage_flags": list(info.usage_flags),
                "scalar_parameters": [serialize_param_default(item) for item in info.scalar_parameters],
                "vector_parameters": [serialize_param_default(item) for item in info.vector_parameters],
                "texture_parameters": [serialize_param_default(item) for item in info.texture_parameters],
                "static_switch_parameters": [serialize_param_default(item) for item in info.static_switch_parameters],
                "num_expressions": info.num_expressions,
                "num_function_calls": info.num_function_calls,
            }},
            "parent_info": None if parent_info is None else {{
                "path": parent_info.path,
                "scalar_parameters": [serialize_param_default(item) for item in parent_info.scalar_parameters],
                "vector_parameters": [serialize_param_default(item) for item in parent_info.vector_parameters],
                "texture_parameters": [serialize_param_default(item) for item in parent_info.texture_parameters],
                "static_switch_parameters": [serialize_param_default(item) for item in parent_info.static_switch_parameters],
            }},
            "material_instance_parameters": None if mi is None else {{
                "name": mi.name,
                "parent_path": mi.parent_path,
                "parameters": [serialize_param(item) for item in mi.parameters],
            }},
            "instance_chain": {{
                "found": chain.found,
                "path": chain.path,
                "layers": [
                    {{
                        "name": layer.name,
                        "path": layer.path,
                        "is_base_material": layer.is_base_material,
                        "override_parameters": [serialize_param(item) for item in layer.override_parameters],
                    }}
                    for layer in chain.layers
                ],
            }},
            "graph": {{
                "found": graph.found,
                "path": graph.path,
                "is_material_function": graph.is_material_function,
                "nodes": [serialize_node(node) for node in graph.nodes],
                "connections": [serialize_connection(item) for item in graph.connections],
                "output_connections": [serialize_connection(item) for item in graph.output_connections],
            }},
            "analysis": {{
                "found": analysis.found,
                "path": analysis.path,
                "material_domain": analysis.material_domain,
                "shading_models": list(analysis.shading_models),
                "max_instructions": analysis.max_instructions,
                "sampler_count": analysis.sampler_count,
                "expression_count": analysis.expression_count,
                "instruction_budget": analysis.instruction_budget,
                "sampler_budget": analysis.sampler_budget,
                "compile_errors": list(analysis.compile_errors),
                "shader_stats_ready": analysis.shader_stats_ready,
                "findings": [serialize_finding(item) for item in analysis.findings],
            }},
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


def trace_graph(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = {node["guid"]: node for node in graph["nodes"] if node["guid"]}
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for connection in graph["connections"]:
        incoming[connection["dst_guid"]].append(connection)

    def walk_from(guid: str) -> set[str]:
        seen: set[str] = set()
        stack = [guid]
        while stack:
            current = stack.pop()
            if not current or current in seen:
                continue
            seen.add(current)
            for edge in incoming.get(current, []):
                stack.append(edge["src_guid"])
        return seen

    live_nodes: set[str] = set()
    outputs: list[dict[str, Any]] = []
    for output in graph["output_connections"]:
        reachable = walk_from(output["src_guid"])
        live_nodes.update(reachable)
        outputs.append(
            {
                "property": output["dst_property_name"],
                "src_guid": output["src_guid"],
                "reachable_nodes": sorted(reachable),
            }
        )

    ignore = {"Comment", "FunctionInput", "FunctionOutput"}
    dead_nodes = [
        node for guid, node in nodes.items() if guid not in live_nodes and node["class_name"] not in ignore
    ]
    return {
        "live_node_guids": sorted(live_nodes),
        "dead_nodes": dead_nodes,
        "output_chains": outputs,
    }


def stale_overrides(payload: dict[str, Any]) -> list[dict[str, Any]]:
    info = payload["material_info"]
    mi = payload["material_instance_parameters"]
    parent = payload["parent_info"]
    if not info["is_material_instance"] or mi is None or parent is None:
        return []
    valid_names = {
        item["name"]
        for key in ("scalar_parameters", "vector_parameters", "texture_parameters", "static_switch_parameters")
        for item in parent[key]
    }
    return [param for param in mi["parameters"] if param["name"] not in valid_names]


def render_markdown(material_path: str, report: dict[str, Any]) -> str:
    lines = [
        f"# Material Audit: {material_path}",
        "",
        f"- Domain: `{report['material_info']['material_domain']}`",
        f"- Blend mode: `{report['material_info']['blend_mode']}`",
        f"- Instructions: `{report['analysis']['max_instructions']}`",
        f"- Samplers: `{report['analysis']['sampler_count']}`",
        f"- Shader stats ready: `{report['analysis']['shader_stats_ready']}`",
        "",
        "## Findings",
        "",
    ]
    findings = report["analysis"]["findings"]
    if findings:
        for finding in findings:
            lines.append(f"- [{finding['severity']}] `{finding['rule_id']}` {finding['message']}")
    else:
        lines.append("- No analyze_material findings.")
    lines.extend(["", "## Cleanup Candidates", ""])
    if report["graph_summary"]["dead_nodes"]:
        for node in report["graph_summary"]["dead_nodes"]:
            lines.append(f"- Dead node `{node['caption'] or node['class_name']}` ({node['guid']})")
    else:
        lines.append("- No dead material nodes detected.")
    if report["stale_overrides"]:
        for override in report["stale_overrides"]:
            lines.append(f"- Stale MI override `{override['name']}` ({override['param_type']})")
    else:
        lines.append("- No stale MI overrides detected.")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.material_path, args.instruction_budget, args.sampler_budget))
    report = {
        "tool": "material_audit",
        "material_path": args.material_path,
        "material_info": raw["material_info"],
        "analysis": raw["analysis"],
        "instance_chain": raw["instance_chain"],
        "graph_summary": trace_graph(raw["graph"]),
        "stale_overrides": stale_overrides(raw),
        "raw_graph": raw["graph"] if args.include_raw_graph else None,
    }
    base = default_report_path(ctx, "audits/material", slugify(args.material_path), "material-audit", ".json")
    json_out = Path(args.out) if args.out else base
    save_json(json_out, report)
    if args.markdown:
        md_out = json_out.with_suffix(".md")
        write_text(md_out, render_markdown(args.material_path, report))
    print(json_out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit an Unreal material or material instance through unreal-bridge.")
    parser.add_argument("material_path")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--timeout", type=int, default=180)
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
