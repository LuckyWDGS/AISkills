from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_ue_script(material_path: str, system_path: str | None, mpc_paths: list[str]) -> str:
    payload = json.dumps({"material_path": material_path, "system_path": system_path or "", "mpc_paths": mpc_paths}, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import re
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        N = getattr(unreal, "UnrealBridgeNiagaraLibrary", None)
        payload = json.loads({payload!r})
        material_path = payload["material_path"]
        system_path = payload["system_path"]
        mpc_paths = payload["mpc_paths"]

        def guid_text(value):
            try:
                return value.to_string()
            except Exception:
                return str(value)

        def serialize_param_default(param):
            return {{
                "name": param.name,
                "param_type": param.param_type,
                "value": param.value,
                "guid": guid_text(param.guid),
            }}

        def serialize_param(param):
            return {{
                "name": param.name,
                "param_type": param.param_type,
                "value": param.value,
            }}

        def serialize_node(node):
            return {{
                "guid": guid_text(node.guid),
                "class_name": node.class_name,
                "caption": node.caption,
                "desc": node.desc,
                "key_properties": node.key_properties,
                "input_names": list(node.input_names),
                "output_names": list(node.output_names),
            }}

        material_info = MAT.get_material_info(material_path)
        chain = MAT.list_material_instance_chain(material_path)
        graph = MAT.get_material_graph(material_path)
        mi = MAT.get_material_instance_parameters(material_path) if material_info.is_material_instance else None

        mpcs = []
        for mpc_path in mpc_paths:
            info = MAT.get_material_parameter_collection(mpc_path)
            mpcs.append({{
                "path": info.path,
                "found": info.found,
                "name": info.name,
                "scalar_parameters": [{{"name": p.name, "default_value": p.default_value, "id": guid_text(p.id)}} for p in info.scalar_parameters],
                "vector_parameters": [{{"name": p.name, "default_value": str(p.default_value), "id": guid_text(p.id)}} for p in info.vector_parameters],
            }})

        graph_nodes = [serialize_node(node) for node in graph.nodes]

        rapid_params = []
        if system_path and N is not None:
            try:
                for p in N.list_rapid_iteration_parameters(system_path):
                    rapid_params.append({{
                        "parameter_name": str(p.parameter_name),
                        "value_text": str(p.value_text),
                        "type_name": str(p.type_name),
                        "script_usage": str(p.script_usage),
                        "emitter_name": str(p.emitter_name),
                        "emitter_path": str(p.emitter_path),
                        "script_path": str(p.script_path),
                        "offset": int(p.offset),
                        "size_bytes": int(p.size_bytes),
                    }})
            except Exception as exc:
                rapid_params.append({{"error": str(exc)}})

        print(json.dumps({{
            "material_info": {{
                "found": material_info.found,
                "name": material_info.name,
                "path": material_info.path,
                "is_material_instance": material_info.is_material_instance,
                "parent_path": material_info.parent_path,
                "base_path": material_info.base_path,
                "material_domain": material_info.material_domain,
                "blend_mode": material_info.blend_mode,
                "usage_flags": list(material_info.usage_flags),
                "scalar_parameters": [serialize_param_default(item) for item in material_info.scalar_parameters],
                "vector_parameters": [serialize_param_default(item) for item in material_info.vector_parameters],
                "texture_parameters": [serialize_param_default(item) for item in material_info.texture_parameters],
                "static_switch_parameters": [serialize_param_default(item) for item in material_info.static_switch_parameters],
            }},
            "chain": {{
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
                ]
            }},
            "mi_parameters": None if mi is None else {{
                "name": mi.name,
                "parent_path": mi.parent_path,
                "parameters": [serialize_param(item) for item in mi.parameters],
            }},
            "graph": {{
                "found": graph.found,
                "path": graph.path,
                "is_material_function": graph.is_material_function,
                "nodes": graph_nodes,
            }},
            "mpcs": mpcs,
            "rapid_iteration_parameters": rapid_params,
        }}, ensure_ascii=False))
        """
    ).strip()


def infer_mpc_refs(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for node in nodes:
        class_name = str(node.get("class_name") or "")
        key = str(node.get("key_properties") or "")
        caption = str(node.get("caption") or "")
        if "CollectionParameter" not in class_name and "Collection" not in caption:
            continue
        path_match = re.search(r"/(?:Game|Engine)/[^;\s,]+", key)
        refs.append(
            {
                "class_name": class_name,
                "caption": caption,
                "key_properties": key,
                "collection_path_hint": path_match.group(0) if path_match else "",
            }
        )
    return refs


def infer_runtime_links(report: dict[str, Any]) -> list[dict[str, Any]]:
    material_params = {
        item["name"]: item
        for key in ("scalar_parameters", "vector_parameters", "texture_parameters", "static_switch_parameters")
        for item in report["material_info"].get(key) or []
    }
    rapid = report.get("rapid_iteration_parameters") or []
    links: list[dict[str, Any]] = []
    for name, param in material_params.items():
        name_tokens = {token.lower() for token in re.split(r"[^A-Za-z0-9]+", name) if token}
        matched = []
        for row in rapid:
            pname = str(row.get("parameter_name") or "")
            lowered = pname.lower()
            if name.lower() in lowered:
                matched.append(row)
                continue
            token_overlap = [token for token in name_tokens if token and token in lowered]
            if len(token_overlap) >= 2:
                matched.append(row)
        if matched:
            links.append(
                {
                    "material_param": name,
                    "param_type": param.get("param_type"),
                    "matched_rapid_params": matched,
                }
            )
    return links


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Runtime Param Trace: {report['material_info']['path']}",
        "",
        f"- Domain: `{report['material_info']['material_domain']}`",
        f"- Blend mode: `{report['material_info']['blend_mode']}`",
        f"- Base material: `{report['material_info']['base_path']}`",
        "",
        "## Chain",
        "",
    ]
    for layer in report["chain"]["layers"]:
        tag = "BASE" if layer["is_base_material"] else "MI"
        lines.append(f"- [{tag}] `{layer['path']}` overrides={len(layer['override_parameters'])}")
    lines.extend(["", "## MPC Hints", ""])
    mpc_refs = report.get("mpc_refs") or []
    if mpc_refs:
        for item in mpc_refs:
            lines.append(f"- `{item['class_name']}` `{item['caption']}` path_hint=`{item['collection_path_hint'] or 'none'}`")
    else:
        lines.append("- No obvious Material Parameter Collection references in the graph.")
    lines.extend(["", "## Rapid Iteration Links", ""])
    links = report.get("runtime_links") or []
    if links:
        for item in links:
            lines.append(f"- `{item['material_param']}` -> {len(item['matched_rapid_params'])} rapid params")
    else:
        lines.append("- No obvious rapid-iteration matches to material parameter names.")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.material_path, args.system_path, args.mpc))
    raw["mpc_refs"] = infer_mpc_refs(raw["graph"]["nodes"])
    raw["runtime_links"] = infer_runtime_links(raw)
    effect = slugify(args.effect or args.material_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "runtime-trace", effect, f"{slugify(args.material_path)}-runtime-param-trace", ".json")
    save_json(out, raw)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(raw))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trace runtime-facing parameter sources for a material and optional Niagara system.")
    parser.add_argument("material_path")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--system-path")
    parser.add_argument("--mpc", action="append", default=[])
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
