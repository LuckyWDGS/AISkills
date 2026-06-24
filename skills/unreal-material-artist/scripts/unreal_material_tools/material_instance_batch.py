from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def load_spec(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_ue_script(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import os
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary
        payload = json.loads({payload!r})

        def serialize_create(result):
            return {{
                "success": bool(result.success),
                "path": result.path,
                "error": result.error,
            }}

        def make_param(row):
            param = unreal.BridgeMIParamSet()
            param.name = row["name"]
            param.type = row["type"]
            param.value = str(row["value"])
            return param

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

        def run_tool_candidates(names, payload):
            attempts = []
            for candidate in names:
                result = run_tool(candidate, payload)
                attempts.append({{"name": candidate, "success": result["success"], "error": result["error"]}})
                if result["success"]:
                    result["attempts"] = attempts
                    result["tool_name"] = candidate
                    return result
            last = attempts[-1] if attempts else {{"name": "", "error": "no_tool_candidates"}}
            return {{
                "success": False,
                "error": last.get("error") or "No candidate tool succeeded.",
                "output": None,
                "attempts": attempts,
                "tool_name": last.get("name", ""),
            }}

        def parse_bool(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            text = str(value).strip().lower()
            if text in ("true", "1", "yes", "on"):
                return True
            if text in ("false", "0", "no", "off"):
                return False
            raise RuntimeError(f"Unsupported static switch boolean value: {{value!r}}")

        report = {{"instances": []}}
        preview_defaults = payload.get("preview", {{}})
        reuse_existing = bool(payload.get("reuse_existing"))
        use_official_toolsets = bool(payload.get("use_official_toolsets", True))

        for item in payload["instances"]:
            parent_path = item.get("parent_path") or payload["parent_path"]
            instance_path = item["path"]
            instance_leaf = instance_path.rsplit("/", 1)[-1].split(".", 1)[0]
            instance_folder = instance_path.rsplit("/", 1)[0]
            row = {{
                "path": instance_path,
                "parent_path": parent_path,
            }}

            if use_official_toolsets:
                created_error = ""
                create_row = run_tool(
                    "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.create",
                    {{
                        "folder_path": instance_folder,
                        "asset_name": instance_leaf,
                        "parent": {{"refPath": parent_path}},
                    }},
                )
                row["create"] = {{
                    "success": create_row["success"],
                    "path": ((create_row.get("output") or {{}}).get("returnValue") or {{}}).get("refPath", instance_path),
                    "error": create_row["error"],
                    "route": "official-toolset",
                }}
                created_error = create_row["error"]
                usable = bool(create_row["success"])
            else:
                created = MAT.create_material_instance(parent_path, instance_path)
                row["create"] = serialize_create(created)
                row["create"]["route"] = "local-bridge"
                usable = bool(created.success)
                created_error = created.error

            official_create_error = row["create"].get("error") or ""
            create_error_text = ((created_error if not use_official_toolsets else official_create_error) or "").lower()
            if not usable and reuse_existing and ("already occupied" in create_error_text or "already exists" in create_error_text):
                usable = True
                row["create"]["success"] = True
                row["create"]["reused_existing"] = True

            if usable and item.get("params"):
                if use_official_toolsets:
                    applied = 0
                    skipped = []
                    param_rows = []
                    for param in item["params"]:
                        ptype = str(param["type"]).strip().lower()
                        pname = param["name"]
                        pvalue = param["value"]
                        if ptype == "scalar":
                            result = run_tool(
                                "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.set_scalar_parameter",
                                {{
                                    "instance": {{"refPath": instance_path}},
                                    "name": pname,
                                    "value": float(pvalue),
                                }},
                            )
                        elif ptype == "vector":
                            vector_value = pvalue if isinstance(pvalue, dict) else {{}}
                            if not vector_value and isinstance(pvalue, str):
                                try:
                                    parsed = json.loads(pvalue)
                                    if isinstance(parsed, dict):
                                        vector_value = parsed
                                except Exception:
                                    vector_value = {{}}
                            result = run_tool(
                                "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.set_vector_parameter",
                                {{
                                    "instance": {{"refPath": instance_path}},
                                    "name": pname,
                                    "value": {{
                                        "r": float(vector_value.get("r", 0.0)),
                                        "g": float(vector_value.get("g", 0.0)),
                                        "b": float(vector_value.get("b", 0.0)),
                                        "a": float(vector_value.get("a", 1.0)),
                                    }},
                                }},
                            )
                        elif ptype == "texture":
                            texture_path = pvalue["refPath"] if isinstance(pvalue, dict) and "refPath" in pvalue else str(pvalue)
                            if texture_path.startswith("{") and texture_path.endswith("}"):
                                try:
                                    parsed = json.loads(texture_path)
                                    if isinstance(parsed, dict) and "refPath" in parsed:
                                        texture_path = str(parsed["refPath"])
                                except Exception:
                                    pass
                            result = run_tool(
                                "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.set_texture_parameter",
                                {{
                                    "instance": {{"refPath": instance_path}},
                                    "name": pname,
                                    "value": {{"refPath": texture_path}},
                                }},
                            )
                        elif ptype == "static_switch":
                            result = run_tool_candidates(
                                [
                                    "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.set_static_switch_parameter",
                                    "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools.set_static_switch_param",
                                ],
                                {{
                                    "instance": {{"refPath": instance_path}},
                                    "name": pname,
                                    "value": parse_bool(pvalue),
                                }},
                            )
                        else:
                            result = {{
                                "success": False,
                                "error": f"Unsupported official toolset parameter type: {{param['type']}}",
                                "output": None,
                            }}
                        param_rows.append({{"name": pname, "type": param["type"], "result": result}})
                        if result["success"]:
                            applied += 1
                        else:
                            skipped.append(pname)
                    save_row = run_tool(
                        "toolset_registry.toolsets.core.asset.AssetTools.save_assets",
                        {{"asset_paths": [instance_path]}},
                    )
                    row["set_params"] = {{
                        "success": len(skipped) == 0,
                        "applied": applied,
                        "skipped": skipped,
                        "route": "official-toolset",
                        "param_results": param_rows,
                        "save": save_row,
                    }}
                else:
                    params = [make_param(param) for param in item["params"]]
                    set_result = MAT.set_mi_params(instance_path, params)
                    row["set_params"] = {{
                        "success": bool(set_result.success),
                        "applied": int(set_result.applied),
                        "skipped": list(set_result.skipped),
                        "route": "local-bridge",
                    }}

            preview = dict(preview_defaults)
            preview.update(item.get("preview", {{}}))
            if usable and preview.get("enabled"):
                os.makedirs(os.path.dirname(preview["out_png"]) or ".", exist_ok=True)
                preview_ok = MAT.preview_material(
                    instance_path,
                    preview.get("mesh", "shaderball"),
                    preview.get("lighting", "hdri"),
                    int(preview.get("resolution", 512)),
                    float(preview.get("yaw", 30.0)),
                    float(preview.get("pitch", 15.0)),
                    float(preview.get("distance", 0.0)),
                    preview["out_png"],
                )
                row["preview"] = {{
                    "ok": bool(preview_ok),
                    "out_png": preview["out_png"],
                }}

            report["instances"].append(row)

        print(json.dumps(report, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Material Instance Batch", ""]
    for item in report["instances"]:
        create = item.get("create") or {}
        lines.extend(
            [
                f"## {item['path']}",
                "",
                f"- Parent: `{item['parent_path']}`",
                f"- Created: `{create.get('success')}`",
            ]
        )
        if create.get("reused_existing"):
            lines.append("- Reused existing asset: `True`")
        if create.get("error"):
            lines.append(f"- Create error: `{create['error']}`")
        if item.get("set_params"):
            lines.append(f"- Params applied: `{item['set_params']['applied']}`")
            skipped = item["set_params"].get("skipped") or []
            lines.append(f"- Param skipped count: `{len(skipped)}`")
        if item.get("preview"):
            lines.append(f"- Preview ok: `{item['preview']['ok']}`")
            lines.append(f"- Preview png: `{item['preview']['out_png']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    spec = load_spec(args.spec)
    if args.reuse_existing:
        spec["reuse_existing"] = True

    effect = slugify(args.effect or spec.get("effect") or spec.get("parent_path") or "material-instances")
    preview_defaults = spec.setdefault("preview", {})
    if args.preview:
        preview_defaults["enabled"] = True
    if preview_defaults.get("enabled"):
        preview_defaults.setdefault("mesh", args.mesh)
        preview_defaults.setdefault("lighting", args.lighting)
        preview_defaults.setdefault("resolution", args.resolution)
        preview_defaults.setdefault("yaw", args.yaw)
        preview_defaults.setdefault("pitch", args.pitch)
        preview_defaults.setdefault("distance", args.distance)
        for instance in spec["instances"]:
            preview = dict(preview_defaults)
            preview.update(instance.get("preview", {}))
            if preview.get("enabled"):
                preview.setdefault(
                    "out_png",
                    str(default_report_path(ctx, "instances", effect, f"{slugify(instance['path'])}-preview", ".png")),
                )
            instance["preview"] = preview

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(spec))
    report = {
        "tool": "material_instance_batch",
        "effect": effect,
        "source_spec": str(Path(args.spec).resolve()),
        "instances": raw["instances"],
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "instances", effect, "material-instance-batch", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and parameterize Unreal material instances from a JSON spec.")
    parser.add_argument("spec", help="Path to the batch spec JSON.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--mesh", default="shaderball")
    parser.add_argument("--lighting", default="hdri")
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--yaw", type=float, default=30.0)
    parser.add_argument("--pitch", type=float, default=15.0)
    parser.add_argument("--distance", type=float, default=0.0)
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
