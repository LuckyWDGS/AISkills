"""Verify that a generated texture is imported into UE and referenced by the live material/renderer route.

Reads through Epic's built-in MCP: one ProgrammaticToolset script checks the texture
and material, the material's texture parameters and its dependencies; the renderer
side comes from ``niagara_audit`` (renderer materials of the system's emitters).
``--renderer-path`` takes a Niagara System path, optionally ``<system>:<emitter>``.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .core import default_report_path, normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, write_text
from .mcp import DEFAULT_MCP_URL, run_tool_script


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "live_asset_verify/2"


def package_path(path: str) -> str:
    """'/Game/T/T_X.T_X' -> '/Game/T/T_X'."""
    head, _, leaf = (path or "").split(":", 1)[0].rpartition("/")
    return f"{head}/{leaf.split('.', 1)[0]}" if head else path


def split_renderer_path(renderer_path: str) -> tuple[str, str]:
    """'/Game/FX/NS_X.NS_X:Trail.Renderer' -> ('/Game/FX/NS_X', 'Trail'); a bare system path has no emitter."""
    system, _, rest = (renderer_path or "").partition(":")
    emitter = rest.split(".", 1)[0].split("#", 1)[0]
    return package_path(system), emitter


def build_collect_script(texture_asset_path: str, material_path: str) -> str:
    return textwrap.dedent(
        """
        import json

        TEXTURE = __TEXTURE__
        MATERIAL = __MATERIAL__
        A = "editor_toolset.toolsets.asset.AssetTools."
        MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools."

        def call(tool, **args):
            return json.loads(json.dumps(execute_tool(tool, json.dumps(args))["returnValue"]))

        def ref(path):
            return {"refPath": path + "." + path.rsplit("/", 1)[-1]}

        def run():
            out = {"texture_asset_exists": bool(TEXTURE) and call(A + "exists", path=TEXTURE),
                   "material_exists": bool(MATERIAL) and call(A + "exists", path=MATERIAL),
                   "material_class": "", "texture_parameters": [], "dependencies": []}
            if out["material_exists"]:
                out["material_class"] = call(A + "get_asset_class", asset_path=MATERIAL)
                out["dependencies"] = call(A + "get_dependencies", asset_path=MATERIAL)
                for param in call(MI + "list_parameters", material=ref(MATERIAL)):
                    if param.get("type") != "Texture":
                        continue
                    value = ""
                    if "MaterialInstance" in out["material_class"]:
                        value = call(MI + "get_texture_parameter", instance=ref(MATERIAL), name=param["name"])
                    out["texture_parameters"].append({"name": param["name"], "value": value})
            return out
        """
    ).strip().replace("__TEXTURE__", json.dumps(package_path(texture_asset_path))) \
        .replace("__MATERIAL__", json.dumps(package_path(material_path)))


def _value_path(value: Any) -> str:
    return package_path(value.get("refPath", "") if isinstance(value, dict) else str(value or ""))


def build_payload(texture_asset_path: str, material_path: str, renderer_path: str,
                  raw: dict[str, Any], niagara: dict[str, Any] | None) -> dict[str, Any]:
    """The verification fields from collected MCP data and an optional niagara_audit report. Pure."""
    texture = package_path(texture_asset_path)
    material = package_path(material_path)
    params = [{"name": item["name"], "value": _value_path(item.get("value")),
               "matches_target": bool(texture) and _value_path(item.get("value")) == texture}
              for item in raw.get("texture_parameters") or []]
    dependencies = sorted(package_path(item) for item in raw.get("dependencies") or [])
    _, emitter_name = split_renderer_path(renderer_path)
    renderer_materials: list[str] = []
    for emitter in (niagara or {}).get("emitters") or []:
        if emitter_name and emitter.get("name") != emitter_name:
            continue
        renderer_materials += (emitter.get("parsed") or {}).get("renderer_materials") or []
    return {
        "texture_asset_path": texture_asset_path,
        "material_path": material_path,
        "renderer_path": renderer_path,
        "texture_asset_exists": bool(raw.get("texture_asset_exists")),
        "material_exists": bool(raw.get("material_exists")),
        "material_class": raw.get("material_class", ""),
        # Instance overrides and the effective values both come from get_texture_parameter.
        "material_texture_parameters": params,
        "material_effective_texture_parameters": params,
        "material_dependencies": dependencies,
        "renderer_exists": bool(renderer_materials),
        "renderer_material_path": ", ".join(renderer_materials),
        "material_references_target_texture": any(item["matches_target"] for item in params) or texture in dependencies,
        "renderer_references_material": bool(material) and material in {package_path(item) for item in renderer_materials},
    }


def collect(skill_root: Path, texture_asset_path: str, material_path: str, renderer_path: str, *,
            url: str = DEFAULT_MCP_URL, timeout: float = 180) -> dict[str, Any]:
    raw = run_tool_script(skill_root, build_collect_script(texture_asset_path, material_path), url=url, timeout=timeout)
    niagara = None
    system, _ = split_renderer_path(renderer_path)
    if system:
        from .niagara_audit import audit

        niagara = audit(skill_root, system, url=url, timeout=timeout)
    return build_payload(texture_asset_path, material_path, renderer_path, raw, niagara)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Live Asset Verify: {report.get('texture_asset_path') or report.get('local_file')}",
        "",
        f"- Source policy: `{report.get('source_policy', 'required')}`",
        f"- Verification passed: `{report.get('verification_passed')}`",
        f"- Local file exists: `{report.get('local_file_exists')}`",
        f"- Texture asset exists: `{report.get('texture_asset_exists')}`",
        f"- Material exists: `{report.get('material_exists')}`",
        f"- Renderer exists: `{report.get('renderer_exists')}`",
        f"- Material references target texture: `{report.get('material_references_target_texture')}`",
        f"- Renderer references material: `{report.get('renderer_references_material')}`",
        "",
        "## Material Texture Parameters",
        "",
    ]
    params = report.get("material_texture_parameters", [])
    lines += [f"- `{item['name']}` -> `{item['value']}` match=`{item['matches_target']}`" for item in params] or ["- none"]
    return "\n".join(lines).rstrip() + "\n"


def verification_passed(report: dict[str, Any]) -> bool:
    source_policy = str(report.get("source_policy") or "required")
    source_ok = True
    if source_policy in {"generated", "required"}:
        source_ok = bool(report.get("local_file_exists"))
    return bool(
        source_ok
        and report.get("texture_asset_exists")
        and report.get("material_references_target_texture")
        and report.get("renderer_references_material")
    )


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    local_file = Path(args.local_file).resolve() if args.local_file else None
    raw = collect(ctx.skill_root, args.texture_asset_path, args.material_path, args.renderer_path,
                  url=getattr(args, "mcp_url", DEFAULT_MCP_URL), timeout=args.timeout)
    report = {
        "tool": "live_asset_verify",
        "schema_version": SCHEMA_VERSION,
        "transport": "epic-mcp",
        "effect": args.effect or "",
        "source_policy": args.source_policy,
        "local_file": str(local_file) if local_file else "",
        "local_file_exists": bool(local_file and local_file.exists()),
        **raw,
    }
    report["verification_passed"] = verification_passed(report)
    out = Path(args.out) if args.out else default_report_path(ctx, "live-asset-verify", args.effect or "shared", "live-asset-verify", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify that a generated texture is imported into UE and referenced by the live material/renderer route.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--project")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--local-file", default="")
    parser.add_argument(
        "--source-policy",
        default="required",
        choices=("generated", "required", "ue-only"),
        help="Whether a local source file is required. Use ue-only for hand-authored or UE-native assets.",
    )
    parser.add_argument("--texture-asset-path", required=True)
    parser.add_argument("--material-path", required=True)
    parser.add_argument("--renderer-path", default="", help="Niagara System path, optionally <system>:<emitter>.")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
