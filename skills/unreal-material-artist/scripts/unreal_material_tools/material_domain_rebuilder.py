from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .material_asset_library import upsert_material_record


TARGET_DOMAINS = {"DeferredDecal", "PostProcess"}


def _default_target_path(source_path: str, target_domain: str) -> str:
    object_path = source_path.split(".", 1)[0]
    suffix = "Decal" if target_domain == "DeferredDecal" else "PostProcess"
    return f"{object_path}_{suffix}"


def build_ue_script(
    source_material_path: str,
    target_domain: str,
    target_path: str,
    blendable_location: str,
    output_alpha: bool,
    reuse_existing: bool,
) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary

        SOURCE_PATH = {source_material_path!r}
        TARGET_DOMAIN = {target_domain!r}
        TARGET_PATH = {target_path!r}
        BLENDABLE_LOCATION = {blendable_location!r}
        OUTPUT_ALPHA = {output_alpha!r}
        REUSE_EXISTING = {reuse_existing!r}

        def guid_text(value):
            try:
                return value.to_string()
            except Exception:
                try:
                    return str(value)
                except Exception:
                    return ""

        def run_tool(name, payload):
            result = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)
            output = None
            if result.json_output:
                try:
                    output = json.loads(result.json_output)
                except Exception:
                    output = result.json_output
            return {{
                "success": bool(result.success),
                "error": result.error,
                "output": output,
            }}

        def parse_key_props(text):
            props = []
            for chunk in str(text or "").split(";"):
                part = chunk.strip()
                if not part or "=" not in part:
                    continue
                name, value = part.split("=", 1)
                props.append({{"name": name.strip(), "value": value.strip()}})
            return props

        def to_expression_class_path(short_name):
            short = str(short_name or "").strip()
            if not short:
                return ""
            if short.startswith("/Script/"):
                return short
            if "." in short and short.startswith("/Script"):
                return short
            if short.startswith("MaterialExpression"):
                return short
            return short

        def map_output_name(src_output_name):
            name = str(src_output_name or "").strip()
            if name.startswith("MP_"):
                name = name[3:]
            if TARGET_DOMAIN == "PostProcess":
                if name in ("EmissiveColor", "BaseColor"):
                    return "EmissiveColor"
                return ""
            if TARGET_DOMAIN == "DeferredDecal":
                allowed = {{
                    "BaseColor",
                    "EmissiveColor",
                    "Opacity",
                    "OpacityMask",
                    "Normal",
                    "Roughness",
                    "Metallic",
                    "AmbientOcclusion",
                }}
                return name if name in allowed else ""
            return name

        report = {{
            "tool": "material_domain_rebuilder",
            "source_material_path": SOURCE_PATH,
            "target_domain": TARGET_DOMAIN,
            "target_path": TARGET_PATH,
            "create": None,
            "target_material_ref": "",
            "copied_nodes": [],
            "skipped_nodes": [],
            "copied_connections": [],
            "skipped_connections": [],
            "copied_outputs": [],
            "skipped_outputs": [],
            "compile": None,
            "save": None,
        }}

        source_info = MAT.get_material_info(SOURCE_PATH)
        source_graph = MAT.get_material_graph(SOURCE_PATH)
        if not source_info.found:
            raise RuntimeError(f"Could not load source material: {{SOURCE_PATH}}")
        if not source_graph.found:
            raise RuntimeError(f"Could not read source material graph: {{SOURCE_PATH}}")

        target_object_path = TARGET_PATH + "." + TARGET_PATH.rsplit("/", 1)[-1]
        if REUSE_EXISTING:
            exists = run_tool("toolset_registry.toolsets.core.asset.AssetTools.exists", {{"path": target_object_path}})
            if exists["success"] and isinstance(exists["output"], dict) and exists["output"].get("returnValue") is True:
                report["create"] = {{"success": True, "error": "", "reused_existing": True}}
                report["target_material_ref"] = target_object_path
            else:
                report["create"] = None

        if not report["target_material_ref"]:
            if TARGET_DOMAIN == "PostProcess":
                created = MAT.create_post_process_material(TARGET_PATH, BLENDABLE_LOCATION, bool(OUTPUT_ALPHA))
                report["create"] = {{
                    "success": bool(created.success),
                    "error": created.error,
                    "path": created.path,
                    "route": "local-create-post-process",
                }}
                if not created.success:
                    raise RuntimeError(created.error or "CreatePostProcessMaterial failed.")
                report["target_material_ref"] = created.path
            else:
                shading_models = list(source_info.shading_models) if getattr(source_info, "shading_models", None) else []
                shading_model = shading_models[0] if shading_models else "DefaultLit"
                blend_mode = source_info.blend_mode or "Translucent"
                created = MAT.create_material(
                    TARGET_PATH,
                    TARGET_DOMAIN,
                    shading_model,
                    blend_mode,
                    bool(source_info.two_sided),
                    bool(source_info.use_material_attributes),
                )
                report["create"] = {{
                    "success": bool(created.success),
                    "error": created.error,
                    "path": created.path,
                    "route": "local-create-material",
                    "shading_model": shading_model,
                    "blend_mode": blend_mode,
                }}
                if not created.success:
                    raise RuntimeError(created.error or "CreateMaterial failed.")
                report["target_material_ref"] = created.path

        guid_map = {{}}
        for node in list(source_graph.nodes):
            class_name = to_expression_class_path(node.class_name)
            if not class_name:
                report["skipped_nodes"].append({{"class_name": node.class_name, "reason": "empty-class-name"}})
                continue
            added = MAT.add_material_expression(
                report["target_material_ref"],
                class_name,
                int(node.x),
                int(node.y),
            )
            if not added.success:
                report["skipped_nodes"].append({{
                    "class_name": node.class_name,
                    "caption": node.caption,
                    "reason": added.error,
                }})
                continue
            src_guid = guid_text(node.guid)
            guid_map[src_guid] = added.guid
            report["copied_nodes"].append({{
                "source_guid": src_guid,
                "class_name": node.class_name,
                "caption": node.caption,
                "target_guid": guid_text(added.guid),
            }})
            if node.desc:
                MAT.set_material_expression_property(report["target_material_ref"], added.guid, "Desc", str(node.desc))
            for prop in parse_key_props(node.key_properties):
                MAT.set_material_expression_property(
                    report["target_material_ref"],
                    added.guid,
                    prop["name"],
                    prop["value"],
                )

        for connection in list(source_graph.connections):
            src_guid = guid_map.get(guid_text(connection.src_guid))
            dst_guid = guid_map.get(guid_text(connection.dst_guid))
            if src_guid is None or dst_guid is None:
                report["skipped_connections"].append({{
                    "src_guid": guid_text(connection.src_guid),
                    "dst_guid": guid_text(connection.dst_guid),
                    "reason": "missing-guid-map",
                }})
                continue
            ok = MAT.connect_material_expressions(
                report["target_material_ref"],
                src_guid,
                str(connection.src_output_name or ""),
                dst_guid,
                str(connection.dst_input_name or ""),
            )
            if ok:
                report["copied_connections"].append({{
                    "src_guid": guid_text(connection.src_guid),
                    "dst_guid": guid_text(connection.dst_guid),
                    "src_output_name": connection.src_output_name,
                    "dst_input_name": connection.dst_input_name,
                }})
            else:
                report["skipped_connections"].append({{
                    "src_guid": guid_text(connection.src_guid),
                    "dst_guid": guid_text(connection.dst_guid),
                    "reason": "connect_material_expressions failed",
                }})

        for output in list(source_graph.output_connections):
            src_guid = guid_map.get(guid_text(output.src_guid))
            if src_guid is None:
                report["skipped_outputs"].append({{
                    "src_guid": guid_text(output.src_guid),
                    "dst_property_name": output.dst_property_name,
                    "reason": "missing-guid-map",
                }})
                continue
            mapped = map_output_name(output.dst_property_name)
            if not mapped:
                report["skipped_outputs"].append({{
                    "src_guid": guid_text(output.src_guid),
                    "dst_property_name": output.dst_property_name,
                    "reason": f"no-output-map-for-{{TARGET_DOMAIN}}",
                }})
                continue
            ok = MAT.connect_material_output(
                report["target_material_ref"],
                src_guid,
                str(output.src_output_name or ""),
                mapped,
            )
            if ok:
                report["copied_outputs"].append({{
                    "src_guid": guid_text(output.src_guid),
                    "source_output_name": output.src_output_name,
                    "source_property_name": output.dst_property_name,
                    "target_property_name": mapped,
                }})
            else:
                report["skipped_outputs"].append({{
                    "src_guid": guid_text(output.src_guid),
                    "dst_property_name": output.dst_property_name,
                    "reason": f"connect_material_output failed for {{mapped}}",
                }})

        compile_ok = MAT.compile_material(report["target_material_ref"], False)
        report["compile"] = {{"success": bool(compile_ok), "error": "" if compile_ok else "compile_material returned false"}}
        report["save"] = run_tool("toolset_registry.toolsets.core.asset.AssetTools.save_assets", {{"asset_paths": [report["target_material_ref"]]}})

        target_info = MAT.get_material_info(report["target_material_ref"])
        report["target_material_info"] = {{
            "found": target_info.found,
            "path": target_info.path,
            "material_domain": target_info.material_domain,
            "blend_mode": target_info.blend_mode,
            "shading_models": list(target_info.shading_models),
            "num_expressions": target_info.num_expressions,
        }}
        print(json.dumps(report, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Material Domain Rebuilder",
        "",
        f"- Source: `{report['source_material_path']}`",
        f"- Target Domain: `{report['target_domain']}`",
        f"- Target: `{report.get('target_material_ref')}`",
        f"- Create success: `{(report.get('create') or {}).get('success')}`",
        f"- Compile success: `{(report.get('compile') or {}).get('success')}`",
        f"- Save success: `{(report.get('save') or {}).get('success')}`",
        "",
        f"- Copied nodes: `{len(report.get('copied_nodes') or [])}`",
        f"- Skipped nodes: `{len(report.get('skipped_nodes') or [])}`",
        f"- Copied connections: `{len(report.get('copied_connections') or [])}`",
        f"- Skipped connections: `{len(report.get('skipped_connections') or [])}`",
        f"- Copied outputs: `{len(report.get('copied_outputs') or [])}`",
        f"- Skipped outputs: `{len(report.get('skipped_outputs') or [])}`",
        "",
    ]
    if report.get("skipped_outputs"):
        lines.append("## Skipped Outputs")
        lines.append("")
        for item in report["skipped_outputs"]:
            lines.append(f"- `{item['dst_property_name']}` -> `{item['reason']}`")
        lines.append("")
    return "\n".join(lines)


def command(args: argparse.Namespace) -> int:
    if args.target_domain not in TARGET_DOMAINS:
        raise SystemExit(f"Unsupported target domain `{args.target_domain}`.")
    ctx = resolve_root_context(args.root)
    target_path = args.target_path or _default_target_path(args.source_material_path, args.target_domain)
    effect = slugify(args.effect or target_path)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    report = client.exec_json(
        build_ue_script(
            args.source_material_path,
            args.target_domain,
            target_path,
            args.blendable_location,
            args.output_alpha,
            args.reuse_existing,
        )
    )
    if args.register_candidate:
        target_info = report.get("target_material_info") or {}
        category = "decal" if args.target_domain == "DeferredDecal" else "post_process"
        role = "decal-material" if args.target_domain == "DeferredDecal" else "post-process-material"
        report_path = str(Path(args.out) if args.out else default_report_path(ctx, "domain-rebuild", effect, slugify(target_path), ".json"))
        record = upsert_material_record(
            ue_asset_path=report.get("target_material_ref") or target_path,
            stage="candidates",
            category=category,
            role=role,
            name=args.name,
            tags=(args.tags or []),
            notes=args.notes or f"Auto-rebuilt from {args.source_material_path} into {args.target_domain}.",
            qa_status=args.qa_status,
            source_kind="rebuilt",
            source_material_path=args.source_material_path,
            report_paths=[report_path],
            material_info=target_info,
        )
        report["candidate_record"] = record
    out = Path(args.out) if args.out else default_report_path(ctx, "domain-rebuild", effect, slugify(target_path), ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild a material into a legal DeferredDecal or PostProcess material and migrate basic graph logic.")
    parser.add_argument("source_material_path")
    parser.add_argument("target_domain", choices=sorted(TARGET_DOMAINS))
    parser.add_argument("--target-path")
    parser.add_argument("--blendable-location", default="AfterTonemapping")
    parser.add_argument("--output-alpha", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--effect")
    parser.add_argument("--register-candidate", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--tags", action="append")
    parser.add_argument("--notes")
    parser.add_argument("--qa-status", default="candidate")
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
