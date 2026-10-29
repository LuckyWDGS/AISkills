from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, normalize_cli_global_args, resolve_root_context, save_json, slugify, write_text
from .effect_state import asset_plan_default, load_effect_record


PLAN_VERSION = 1
SUPPORTED_OPS = {
    "duplicate_asset",
    "create_material_instance",
    "add_emitter_to_system_from_asset",
    "duplicate_emitter_in_system",
    "remove_emitter_from_system",
    "set_emitter_enabled_in_system",
    "toolset_get_system_info",
    "toolset_get_system_topology",
    "toolset_get_emitter_topology",
    "toolset_get_module_topology",
    "toolset_get_stack_input_data",
    "toolset_set_stack_input_data",
    "toolset_add_module",
    "toolset_remove_module",
    "toolset_set_module_enabled",
    "toolset_get_system_compile_state",
    "toolset_get_stack_issues",
    "toolset_apply_stack_issue_fix",
    "add_ribbon_renderer",
    "set_mi_params",
    "set_niagara_system_props",
    "patch_renderer_material",
    "set_u_property_export",
    "save_assets",
}

SEMANTIC_ENABLED_OPS = {
    "set_emitter_enabled_in_system",
    "toolset_set_module_enabled",
}


def full_object_path(path: str) -> str:
    clean = path.strip()
    match = re.search(r"'([^']+)'", clean)
    if match:
        clean = match.group(1)
    if not clean:
        return clean
    last = clean.rsplit("/", 1)[-1]
    if "." in last:
        return clean
    return f"{clean}.{last}"


def package_path(path: str) -> str:
    return full_object_path(path).split(".", 1)[0]


def asset_folder_from_path(path: str) -> str:
    return package_path(path).rsplit("/", 1)[0]


def asset_token(text: str) -> str:
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")
    return token or "Layer"


def plan_path(ctx, effect: str, stem: str = "mutation-plan") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".json")


def script_path(ctx, effect: str, stem: str = "apply-niagara-plan") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".py")


def result_path(ctx, effect: str, stem: str = "apply-result") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".json")


def load_plan(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_plan(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    save_json(target, payload)
    return target


def make_plan(effect: str, mode: str, target_system: str, project: str = "", notes: str = "") -> dict[str, Any]:
    return {
        "version": PLAN_VERSION,
        "tool": "niagara_asset_assistant",
        "effect_name": effect,
        "mode": mode,
        "project": project,
        "target_system": target_system,
        "notes": notes,
        "safety": {
            "dry_run_default": True,
            "requires_apply_flag": True,
            "delete_ops_allowed": False,
            "template_first": True,
        },
        "operations": [],
        "warnings": [],
    }


def renderer_parent_map(items: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        mapping[key.strip().lower()] = value.strip()
    return mapping


def pick_parent_for_renderers(renderers: list[str], default_parent: str, mapping: dict[str, str]) -> str:
    for renderer in renderers:
        hit = mapping.get(str(renderer).strip().lower())
        if hit:
            return hit
    return default_parent


def parse_param_set(items: list[str]) -> list[dict[str, str]]:
    params: list[dict[str, str]] = []
    for item in items:
        parts = item.split("=", 2)
        if len(parts) != 3:
            raise ValueError(f"Param must be name=type=value: {item}")
        params.append({"name": parts[0], "type": parts[1], "value": parts[2]})
    return params


def op_summary(op: dict[str, Any]) -> str:
    kind = op.get("op", "")
    if kind == "duplicate_asset":
        return f"duplicate `{op.get('source')}` -> `{op.get('target')}`"
    if kind == "create_material_instance":
        return f"create MI `{op.get('target')}` parent=`{op.get('parent')}`"
    if kind == "add_emitter_to_system_from_asset":
        return f"add emitter asset `{op.get('emitter_asset_path')}` to system `{op.get('system_path')}` as `{op.get('new_emitter_name') or 'auto'}`"
    if kind == "duplicate_emitter_in_system":
        return f"duplicate emitter `{op.get('source_emitter_name')}` in `{op.get('system_path')}` as `{op.get('new_emitter_name') or 'auto'}`"
    if kind == "remove_emitter_from_system":
        return f"remove emitter `{op.get('emitter_name')}` from `{op.get('system_path')}`"
    if kind == "set_emitter_enabled_in_system":
        return f"set emitter `{op.get('emitter_name')}` enabled=`{op.get('enabled')}` in `{op.get('system_path')}`"
    if kind == "toolset_get_system_info":
        return f"official get system info `{op.get('system_path')}`"
    if kind == "toolset_get_system_topology":
        return f"official get system topology `{op.get('system_path')}`"
    if kind == "toolset_get_emitter_topology":
        return f"official get emitter topology `{op.get('emitter_name')}`"
    if kind == "toolset_get_module_topology":
        return f"official get module topology `{op.get('module_name')}` in `{op.get('script_name')}`"
    if kind == "toolset_get_stack_input_data":
        return f"official get stack input `{op.get('input_name_stack') or op.get('input_name')}` in `{op.get('module_name')}`"
    if kind == "toolset_set_stack_input_data":
        return f"official set stack input `{op.get('input_name_stack') or op.get('input_name')}` in `{op.get('module_name')}`"
    if kind == "toolset_add_module":
        return f"official add module asset `{op.get('module_asset_path')}` into `{op.get('script_name')}`"
    if kind == "toolset_remove_module":
        return f"official remove module `{op.get('module_name')}` from `{op.get('script_name')}`"
    if kind == "toolset_set_module_enabled":
        return f"official set module `{op.get('module_name')}` enabled=`{op.get('enabled')}`"
    if kind == "toolset_get_system_compile_state":
        return f"official get compile state `{op.get('system_path')}`"
    if kind == "toolset_get_stack_issues":
        return f"official get stack issues `{op.get('system_path')}`"
    if kind == "toolset_apply_stack_issue_fix":
        return f"official apply stack issue fix `{op.get('issue_id')}` / `{op.get('fix_id')}`"
    if kind == "add_ribbon_renderer":
        return f"add Ribbon Renderer to `{op.get('emitter_path') or op.get('emitter_name_contains')}` material=`{op.get('material_path')}`"
    if kind == "set_mi_params":
        return f"set {len(op.get('params', []))} MI params on `{op.get('material_instance')}`"
    if kind == "set_niagara_system_props":
        return f"set Niagara system props on `{op.get('system_path')}`"
    if kind == "patch_renderer_material":
        return f"patch renderer material to `{op.get('material_path')}`"
    if kind == "set_u_property_export":
        return f"set UPROPERTY `{op.get('property_path')}` on `{op.get('object_path')}`"
    if kind == "save_assets":
        return f"save {len(op.get('asset_paths', []))} assets"
    return kind or "unknown"


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# Niagara Asset Mutation Plan: {plan.get('effect_name', '')}",
        "",
        f"- Mode: `{plan.get('mode', '')}`",
        f"- Target system: `{plan.get('target_system', '')}`",
        f"- Project: `{plan.get('project', '') or 'default bridge project'}`",
        f"- Dry-run default: `{plan.get('safety', {}).get('dry_run_default', True)}`",
        "",
        "## Operations",
        "",
    ]
    for index, op in enumerate(plan.get("operations", []), start=1):
        enabled = op.get("enabled", True)
        lines.append(f"{index}. [{'enabled' if enabled else 'disabled'}] `{op.get('op')}` {op_summary(op)}")
    if not plan.get("operations"):
        lines.append("- No operations.")
    warnings = plan.get("warnings", [])
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- No plan warnings.")
    return "\n".join(lines).rstrip() + "\n"


def append_template_layer_ops(
    plan: dict[str, Any],
    layers: list[dict[str, Any]],
    folder_root: str,
    default_parent: str,
    parent_map: dict[str, str],
    default_params: list[dict[str, str]],
) -> None:
    material_paths: list[str] = []
    for layer in layers:
        renderers = [str(item) for item in layer.get("renderers", [])]
        parent = pick_parent_for_renderers(renderers, default_parent, parent_map)
        if not parent:
            plan["warnings"].append(f"No material parent supplied for layer `{layer.get('layer_name', '')}`.")
            continue
        layer_name = str(layer.get("layer_name", "Layer"))
        layer_emitters = [str(item) for item in layer.get("emitters", [])]
        materials = layer.get("materials", []) or [{"instance": f"MI_{asset_token(plan['effect_name'])}_{asset_token(layer_name)}"}]
        for material in materials:
            instance_name = str(material.get("instance") or material.get("name") or f"MI_{asset_token(plan['effect_name'])}_{asset_token(layer_name)}")
            mi_path = f"{folder_root.rstrip('/')}/Materials/{instance_name}"
            material_paths.append(mi_path)
            plan["operations"].append(
                {
                    "op": "create_material_instance",
                    "parent": parent,
                    "target": mi_path,
                    "reuse_if_exists": True,
                    "params": default_params,
                    "reason": f"Create tunable material instance for layer {layer_name}.",
                }
            )
            plan["operations"].append(
                {
                    "op": "patch_renderer_material",
                    "system_path": plan["target_system"],
                    "emitter_name_contains": [layer_name, asset_token(layer_name), *layer_emitters],
                    "renderer_class_contains": renderers,
                    "material_path": mi_path,
                    "replace_all": False,
                    "allow_noop": False,
                    "reason": f"Bind layer material to matching Niagara renderer for {layer_name}.",
                }
            )
    if material_paths:
        plan["operations"].append({"op": "save_assets", "asset_paths": [plan["target_system"], *material_paths]})


def plan_template_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    asset_plan = load_effect_record(ctx, "asset-plans", args.effect, asset_plan_default(args.effect))
    target_system = args.target_system or f"{asset_plan.get('naming', {}).get('folder_root', '/Game/VFX').rstrip('/')}/{asset_plan.get('naming', {}).get('system_name', 'NS_' + asset_token(args.effect))}"
    folder_root = args.folder_root or asset_plan.get("naming", {}).get("folder_root") or asset_folder_from_path(target_system)
    plan = make_plan(args.effect, "create-from-template", target_system, args.project or "", args.notes)
    if args.template_system:
        plan["operations"].append(
            {
                "op": "duplicate_asset",
                "source": args.template_system,
                "target": target_system,
                "reuse_if_exists": args.reuse_existing,
                "reason": "Template-first Niagara creation keeps emitter graphs and renderer setup valid.",
            }
        )
    if args.fixed_bounds or args.warmup_tick_count is not None or args.warmup_tick_delta is not None or args.effect_type_path:
        op: dict[str, Any] = {"op": "set_niagara_system_props", "system_path": target_system}
        if args.effect_type_path:
            op["effect_type_path"] = args.effect_type_path
        if args.fixed_bounds:
            op["fixed_bounds"] = args.fixed_bounds
        if args.warmup_tick_count is not None:
            op["warmup_tick_count"] = args.warmup_tick_count
        if args.warmup_tick_delta is not None:
            op["warmup_tick_delta"] = args.warmup_tick_delta
        plan["operations"].append(op)
    layers = asset_plan.get("assets", {}).get("layers", [])
    append_template_layer_ops(
        plan,
        layers,
        folder_root,
        args.material_parent,
        renderer_parent_map(args.material_parent_by_renderer),
        parse_param_set(args.mi_param),
    )
    if not layers:
        plan["warnings"].append("No asset-plan layers found; generated only template/system operations.")
    out = Path(args.out) if args.out else plan_path(ctx, args.effect)
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def repair_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    target_system = args.target_system or audit.get("system_path", "")
    effect = args.effect or slugify(target_system)
    plan = make_plan(effect, "repair-existing", target_system, args.project or "", args.notes)
    if args.fixed_bounds and any("FixedBounds" in item for item in audit.get("warnings", [])):
        plan["operations"].append({"op": "set_niagara_system_props", "system_path": target_system, "fixed_bounds": args.fixed_bounds})
    parent_map = renderer_parent_map(args.material_by_renderer)
    for emitter in audit.get("emitters", []):
        parsed = emitter.get("parsed", {})
        renderers = parsed.get("renderer_classes", [])
        materials = parsed.get("renderer_materials", [])
        if materials:
            continue
        renderer_text = emitter.get("properties", {}).get("RendererProperties", {}).get("text", "")
        has_any_renderer = bool(renderers or renderer_text.strip())
        if not has_any_renderer:
            role = str(emitter.get("role", "")).lower()
            if role in {"receiver", "trail-receiver"}:
                material = args.default_material or pick_parent_for_renderers(renderers, "", parent_map)
                if material:
                    plan["operations"].append(
                        {
                            "op": "add_ribbon_renderer",
                            "system_path": target_system,
                            "emitter_name": emitter.get("name", ""),
                            "emitter_path": emitter.get("emitter_path", ""),
                            "material_path": material,
                            "renderer_name": args.renderer_name,
                            "facing_mode": args.facing_mode,
                            "max_num_ribbons": args.max_num_ribbons,
                            "width_segmentation_count": args.width_segmentation_count,
                            "curve_tension": args.curve_tension,
                            "reason": f"Create missing Ribbon Renderer on receiver emitter {emitter.get('name', '')}.",
                        }
                    )
                    continue
                plan["warnings"].append(
                    f"Skipped receiver `{emitter.get('name', '')}` with empty RendererProperties because no material was supplied."
                )
                continue
            plan["warnings"].append(
                f"Skipped emitter `{emitter.get('name', '')}` because RendererProperties is empty; material binding repair needs an existing renderer slot."
            )
            continue
        if not renderer_text.strip() and renderers:
            plan["warnings"].append(
                f"Emitter `{emitter.get('name', '')}` has versioned renderers `{', '.join(renderers)}`; material patching for existing versioned renderer slots is not automatic yet."
            )
            continue
        material = pick_parent_for_renderers(renderers, args.default_material, parent_map)
        if not material:
            plan["warnings"].append(
                f"Skipped emitter `{emitter.get('name', '')}` because no default material was supplied for renderers `{', '.join(renderers) or 'unknown'}`."
            )
            continue
        plan["operations"].append(
            {
                "op": "patch_renderer_material",
                "system_path": target_system,
                "emitter_path": emitter.get("emitter_path", ""),
                "renderer_class_contains": renderers,
                "material_path": material,
                "replace_all": False,
                "allow_noop": False,
                "reason": f"Repair missing renderer material on emitter {emitter.get('name', '')}.",
            }
        )
    if not plan["operations"]:
        plan["warnings"].append("No automatic repairs were inferred from the audit and supplied defaults.")
    out = Path(args.out) if args.out else plan_path(ctx, effect, "repair-plan")
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def new_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = make_plan(args.effect, args.mode, args.target_system, args.project or "", args.notes)
    for op_json in args.op_json:
        op = json.loads(op_json)
        if op.get("op") not in SUPPORTED_OPS:
            raise ValueError(f"Unsupported operation: {op.get('op')}")
        plan["operations"].append(op)
    out = Path(args.out) if args.out else plan_path(ctx, args.effect)
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def inspect_system_command(args: argparse.Namespace) -> int:
    """Structural readback of a live system through Epic MCP (the niagara_audit report)."""
    from .niagara_audit import audit

    ctx = resolve_root_context(args.root)
    report = audit(ctx.skill_root, args.system_path, timeout=args.timeout)
    out = Path(args.out) if args.out else default_report_path(ctx, "ue-inspect", slugify(args.system_path), "niagara-system-inspect", ".json")
    save_json(out, report)
    print(out)
    return 0


def export_md_command(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    out = Path(args.out) if args.out else Path(args.plan).with_suffix(".md")
    write_text(out, render_plan_markdown(plan))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and repair reviewable Niagara asset mutation plans; apply them with NiagaraToolset_System through builtin_mcp.py batch.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_template = subparsers.add_parser("plan-template")
    plan_template.add_argument("--effect", required=True)
    plan_template.add_argument("--template-system", default="")
    plan_template.add_argument("--target-system", default="")
    plan_template.add_argument("--folder-root", default="")
    plan_template.add_argument("--material-parent", default="")
    plan_template.add_argument("--material-parent-by-renderer", action="append", default=[], help="Renderer=/Game/Path/M_Master")
    plan_template.add_argument("--mi-param", action="append", default=[], help="Name=Type=Value, for example Intensity=Scalar=1.0")
    plan_template.add_argument("--effect-type-path", default="")
    plan_template.add_argument("--fixed-bounds", default="")
    plan_template.add_argument("--warmup-tick-count", type=int)
    plan_template.add_argument("--warmup-tick-delta", type=float)
    plan_template.add_argument("--reuse-existing", action="store_true")
    plan_template.add_argument("--project", default="")
    plan_template.add_argument("--notes", default="")
    plan_template.add_argument("--out")
    plan_template.add_argument("--markdown", action="store_true")
    plan_template.set_defaults(func=plan_template_command)

    repair = subparsers.add_parser("repair-plan")
    repair.add_argument("--audit", required=True)
    repair.add_argument("--effect", default="")
    repair.add_argument("--target-system", default="")
    repair.add_argument("--default-material", default="")
    repair.add_argument("--material-by-renderer", action="append", default=[], help="Renderer=/Game/Path/MI_Fix")
    repair.add_argument("--fixed-bounds", default="")
    repair.add_argument("--renderer-name", default="CodexRibbonRenderer")
    repair.add_argument("--facing-mode", default="Screen")
    repair.add_argument("--max-num-ribbons", default="")
    repair.add_argument("--width-segmentation-count", default="1")
    repair.add_argument("--curve-tension", default="0.0")
    repair.add_argument("--project", default="")
    repair.add_argument("--notes", default="")
    repair.add_argument("--out")
    repair.add_argument("--markdown", action="store_true")
    repair.set_defaults(func=repair_plan_command)

    new_plan = subparsers.add_parser("new-plan")
    new_plan.add_argument("--effect", required=True)
    new_plan.add_argument("--mode", default="manual")
    new_plan.add_argument("--target-system", required=True)
    new_plan.add_argument("--project", default="")
    new_plan.add_argument("--notes", default="")
    new_plan.add_argument("--op-json", action="append", default=[])
    new_plan.add_argument("--out")
    new_plan.add_argument("--markdown", action="store_true")
    new_plan.set_defaults(func=new_plan_command)

    inspect = subparsers.add_parser("inspect-system")
    inspect.add_argument("system_path")
    inspect.add_argument("--effect", default="")
    inspect.add_argument("--project")
    inspect.add_argument("--timeout", type=int, default=180)
    inspect.add_argument("--out")
    inspect.set_defaults(func=inspect_system_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--plan", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_md_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"plan-template", "repair-plan", "new-plan", "inspect-system", "export-md"},
        global_opts_with_value={"--root"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
