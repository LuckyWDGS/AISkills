"""Trace runtime-facing parameter sources for a material and an optional Niagara system.

Material parameters, the instance chain and the graph come from ``material_audit``
(Epic MCP, live or ``--material-audit``); Niagara user variables and renderer
bindings come from a ``niagara_audit.py`` report (``--niagara-audit``); MPC
parameters are read with ObjectTools. Links are name matches for review, not proof
of a live binding: ``niagara_material_integration_probe.py`` owns that check.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, call_tool


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "runtime_param_trace/2"
COVERAGE_GAPS = [
    "Niagara rapid-iteration parameter values are not exposed by MCP; links use user variables and renderer bindings.",
    "CollectionParameter nodes do not expose their collection asset over MCP; pass --mpc to read a collection.",
]


def load_report(path: str, tool: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("tool") != tool:
        raise SystemExit(f"{path}: expected a {tool} report, got `{payload.get('tool')}`.")
    return payload


def niagara_sources(niagara: dict[str, Any] | None) -> list[dict[str, Any]]:
    """User variables and renderer bindings a material parameter could be driven by."""
    if not niagara:
        return []
    rows = [{"kind": "user_variable", "name": str(item.get("name") or ""), "emitter": "",
             "detail": json.dumps(item.get("defaultValue"), ensure_ascii=False)[:200]}
            for item in niagara.get("user_variables") or []]
    for emitter in niagara.get("emitters") or []:
        for renderer in (emitter.get("parsed") or {}).get("versioned_renderer_objects") or []:
            for key, value in (renderer.get("renderer_data") or {}).items():
                if "Binding" not in key:
                    continue
                bound = ((value or {}).get("parameter") or value or {}).get("name") if isinstance(value, dict) else value
                if bound and bound != "None":
                    rows.append({"kind": "renderer_binding", "name": str(bound), "emitter": emitter.get("name", ""),
                                 "detail": f"{renderer.get('class_name', '')}.{key}"})
    return rows


def infer_mpc_refs(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs = []
    for node in nodes:
        class_name = str(node.get("class_name") or "")
        if "CollectionParameter" not in class_name:
            continue
        key = json.dumps(node.get("key_properties") or {}, ensure_ascii=False)
        path_match = re.search(r"/(?:Game|Engine)/[^;\s,\"]+", key)
        refs.append({"class_name": class_name, "caption": str(node.get("caption") or ""), "key_properties": key,
                     "collection_path_hint": path_match.group(0) if path_match else ""})
    return refs


def infer_runtime_links(report: dict[str, Any]) -> list[dict[str, Any]]:
    material_params = {
        item["name"]: item
        for key in ("scalar_parameters", "vector_parameters", "texture_parameters", "static_switch_parameters")
        for item in report["material_info"].get(key) or []
    }
    sources = report.get("niagara_parameter_sources") or []
    links = []
    for name, param in material_params.items():
        tokens = {token.lower() for token in re.split(r"[^A-Za-z0-9]+", name) if token}
        matched = []
        for row in sources:
            lowered = row["name"].lower()
            if name.lower() in lowered or len([token for token in tokens if token in lowered]) >= 2:
                matched.append(row)
        if matched:
            links.append({"material_param": name, "param_type": param.get("param_type"), "matched_sources": matched})
    return links


def read_mpcs(skill_root: Path, paths: list[str], *, url: str, timeout: float, project: str | None) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        package = path.split(".", 1)[0]
        ref = {"refPath": f"{package}.{package.rsplit('/', 1)[-1]}"}
        try:
            value = call_tool(skill_root, "ObjectTools", "get_properties",
                              {"instance": ref, "properties": ["scalarParameters", "vectorParameters"]},
                              url=url, timeout=timeout, project=project)
            value = value.get("returnValue", value) if isinstance(value, dict) else value
            props = json.loads(value) if isinstance(value, str) else value
        except Exception as exc:  # A missing collection is reported, not fatal.
            rows.append({"path": package, "found": False, "error": str(exc)})
            continue
        rows.append({
            "path": package, "found": True, "name": package.rsplit("/", 1)[-1],
            "scalar_parameters": [{"name": item.get("parameterName"), "default_value": item.get("defaultValue")}
                                  for item in props.get("scalarParameters") or []],
            "vector_parameters": [{"name": item.get("parameterName"), "default_value": item.get("defaultValue")}
                                  for item in props.get("vectorParameters") or []],
        })
    return rows


def build_report(audit: dict[str, Any], niagara: dict[str, Any] | None, mpcs: list[dict[str, Any]]) -> dict[str, Any]:
    info = audit["material_info"]
    layers = audit.get("instance_chain", {}).get("layers") or []
    graph = audit.get("raw_graph") or {"found": False, "nodes": []}
    report = {
        "tool": "runtime_param_trace",
        "schema_version": SCHEMA_VERSION,
        "transport": "epic-mcp (material_audit, niagara_audit, ObjectTools)",
        "material_info": info,
        "chain": {"found": True, "path": info.get("path"), "layers": layers},
        "mi_parameters": None if not info.get("is_material_instance") else {
            "name": info.get("name"), "parent_path": info.get("parent_path"),
            "parameters": layers[0]["override_parameters"] if layers else [],
        },
        "graph": graph,
        "mpcs": mpcs,
        "niagara_system": (niagara or {}).get("system_path", ""),
        "niagara_parameter_sources": niagara_sources(niagara),
        "coverage_gaps": COVERAGE_GAPS,
    }
    report["mpc_refs"] = infer_mpc_refs(graph.get("nodes") or [])
    report["runtime_links"] = infer_runtime_links(report)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    info = report["material_info"]
    lines = [
        f"# Runtime Param Trace: {info['path']}", "",
        f"- Domain: `{info.get('material_domain')}`",
        f"- Blend mode: `{info.get('blend_mode')}`",
        f"- Base material: `{info.get('base_path')}`",
        f"- Niagara system: `{report['niagara_system'] or 'none'}`",
        "", "## Chain", "",
    ]
    for layer in report["chain"]["layers"]:
        tag = "BASE" if layer["is_base_material"] else "MI"
        lines.append(f"- [{tag}] `{layer['path']}` overrides={len(layer['override_parameters'])}")
    lines.extend(["", "## MPC Hints", ""])
    lines += [f"- `{item['class_name']}` `{item['caption']}` path_hint=`{item['collection_path_hint'] or 'none'}`"
              for item in report["mpc_refs"]] or ["- No Material Parameter Collection nodes in the graph."]
    lines.extend(["", "## Niagara Links", ""])
    lines += [f"- `{item['material_param']}` -> " + ", ".join(f"{row['kind']} `{row['name']}`" for row in item["matched_sources"])
              for item in report["runtime_links"]] or ["- No name matches between material parameters and Niagara sources."]
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    if args.material_audit:
        audit = load_report(args.material_audit, "material_audit")
        if "raw_graph" not in audit:
            raise SystemExit(f"{args.material_audit} has no raw_graph; re-run material_audit.py with --include-raw-graph.")
    else:
        from .material_audit import audit as run_audit

        audit = run_audit(ctx.skill_root, args.material_path, url=args.mcp_url, timeout=args.timeout,
                          project=args.project, shader_stats=False, graph_source=args.graph_source)
    niagara = load_report(args.niagara_audit, "niagara_audit") if args.niagara_audit else None
    mpcs = read_mpcs(ctx.skill_root, args.mpc, url=args.mcp_url, timeout=args.timeout, project=args.project) if args.mpc else []
    report = build_report(audit, niagara, mpcs)
    material_path = args.material_path or report["material_info"].get("path", "")
    effect = slugify(args.effect or material_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "runtime-trace", effect, f"{slugify(material_path)}-runtime-param-trace", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trace runtime-facing parameter sources for a material and optional Niagara system.")
    parser.add_argument("material_path", nargs="?", default="", help="Material to read live; optional with --material-audit")
    parser.add_argument("--material-audit", help="material_audit.py --include-raw-graph report instead of a live read")
    parser.add_argument("--niagara-audit", help="niagara_audit.py report of the system that drives the material")
    parser.add_argument("--mpc", action="append", default=[], help="Material Parameter Collection to read (repeatable)")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project", help="Refuse to run unless the MCP endpoint is served by this project.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--graph-source", choices=("mcp", "remote"), default="mcp")
    parser.add_argument("--effect")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.material_path or args.material_audit):
        parser.error("give a material path or --material-audit")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
