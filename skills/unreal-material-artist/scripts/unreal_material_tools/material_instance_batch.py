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

        report = {{"instances": []}}
        preview_defaults = payload.get("preview", {{}})
        reuse_existing = bool(payload.get("reuse_existing"))

        for item in payload["instances"]:
            parent_path = item.get("parent_path") or payload["parent_path"]
            instance_path = item["path"]
            row = {{
                "path": instance_path,
                "parent_path": parent_path,
            }}

            created = MAT.create_material_instance(parent_path, instance_path)
            row["create"] = serialize_create(created)
            usable = bool(created.success)

            if not usable and reuse_existing and "already occupied" in (created.error or "").lower():
                usable = True
                row["create"]["reused_existing"] = True

            if usable and item.get("params"):
                params = [make_param(param) for param in item["params"]]
                set_result = MAT.set_mi_params(instance_path, params)
                row["set_params"] = {{
                    "success": bool(set_result.success),
                    "applied": int(set_result.applied),
                    "skipped": list(set_result.skipped),
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
