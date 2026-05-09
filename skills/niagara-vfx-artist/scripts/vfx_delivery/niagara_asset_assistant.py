from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .effect_state import asset_plan_default, load_effect_record


PLAN_VERSION = 1
SUPPORTED_OPS = {
    "duplicate_asset",
    "create_material_instance",
    "set_mi_params",
    "set_niagara_system_props",
    "patch_renderer_material",
    "set_u_property_export",
    "save_assets",
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


def build_apply_script(plan: dict[str, Any], verify: bool) -> str:
    plan_json = json.dumps(plan, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import hashlib
        import json
        import re
        import unreal

        PLAN = json.loads({plan_json!r})
        PROP = unreal.UnrealBridgePropertyLibrary
        MAT = unreal.UnrealBridgeMaterialLibrary

        def full_object_path(path):
            path = (path or "").strip()
            match = re.search(r"'([^']+)'", path)
            if match:
                path = match.group(1)
            if not path:
                return path
            last = path.rsplit("/", 1)[-1]
            if "." in last:
                return path
            return path + "." + last

        def package_path(path):
            return full_object_path(path).split(".", 1)[0]

        def split_target(path):
            pkg = package_path(path)
            folder, name = pkg.rsplit("/", 1)
            return folder, name

        def asset_exists(path):
            return bool(unreal.EditorAssetLibrary.does_asset_exist(package_path(path)))

        def read_export(path, prop_name):
            text, ok = PROP.get_u_property_as_export_text(path, prop_name)
            return text or "", bool(ok)

        def digest(text):
            return hashlib.sha1((text or "").encode("utf-8", errors="ignore")).hexdigest()[:12]

        def as_list(value):
            if value is None or value == "":
                return []
            if isinstance(value, list):
                return [str(item) for item in value if str(item)]
            return [str(value)]

        def make_mi_param(item):
            param = unreal.BridgeMIParamSet()
            param.name = str(item.get("name", ""))
            param.type = str(item.get("type", ""))
            param.value = str(item.get("value", ""))
            return param

        def inspect_niagara_system(system_path):
            system_props = {{}}
            for name in ["EmitterHandles", "EffectType", "FixedBounds", "WarmupTickCount", "WarmupTickDelta", "SystemScalabilityOverrides"]:
                text, ok = read_export(system_path, name)
                system_props[name] = {{"success": ok, "text": text}}
            handle_text = system_props["EmitterHandles"]["text"]
            names = re.findall(r'(?<!Id)Name="([^"]+)"', handle_text)
            id_names = re.findall(r'IdName="([^"]*)"', handle_text)
            enabled = re.findall(r'bIsEnabled=(True|False)', handle_text)
            emitter_paths = re.findall(r'Emitter="([^"]+)"', handle_text)
            emitters = []
            for index, emitter_path in enumerate(emitter_paths):
                props = {{}}
                for prop in ["SimTarget", "FixedBounds", "RendererProperties", "EventHandlerScriptProps"]:
                    text, ok = read_export(emitter_path, prop)
                    props[prop] = {{"success": ok, "text": text, "digest": digest(text)}}
                renderer_text = props["RendererProperties"]["text"]
                renderers = sorted(set(re.findall(r"Niagara([A-Za-z0-9_]+RendererProperties)", renderer_text)))
                materials = sorted(set(re.findall(r"/(?:Game|Engine)[^'\\\",)]+", renderer_text)))
                emitters.append({{
                    "index": index,
                    "name": names[index] if index < len(names) else "",
                    "id_name": id_names[index] if index < len(id_names) else "",
                    "enabled": enabled[index] if index < len(enabled) else "",
                    "emitter_path": emitter_path,
                    "renderer_classes": renderers,
                    "renderer_materials": materials,
                    "properties": props,
                }})
            return {{"system_path": system_path, "system_properties": system_props, "emitters": emitters}}

        def match_emitter(emitter, op):
            name_blob = (emitter.get("name", "") + " " + emitter.get("id_name", "") + " " + emitter.get("emitter_path", "")).lower()
            name_tokens = [item.lower() for item in as_list(op.get("emitter_name_contains"))]
            if name_tokens and not any(token in name_blob for token in name_tokens):
                return False
            renderer_blob = emitter.get("properties", {{}}).get("RendererProperties", {{}}).get("text", "").lower()
            renderer_tokens = [item.lower() for item in as_list(op.get("renderer_class_contains"))]
            if renderer_tokens and not any(token in renderer_blob for token in renderer_tokens):
                return False
            return True

        def patch_material_text(text, material_path, replace_all=False, material_regex=""):
            target = "Material=MaterialInterface'\\\"" + full_object_path(material_path) + "\\\"'"
            count = 0 if replace_all else 1
            if material_regex:
                new_text, hits = re.subn(material_regex, target, text, count=count)
                return new_text, hits
            patterns = [
                r"Material=MaterialInterface'\\\"[^\\\"]*\\\"'",
                r"Material=Material'\\\"[^\\\"]*\\\"'",
                r"Material=Object'\\\"[^\\\"]*\\\"'",
                r"Material=\\\"[^\\\"]*\\\"",
                r"Material=None",
            ]
            for pattern in patterns:
                new_text, hits = re.subn(pattern, target, text, count=count)
                if hits:
                    return new_text, hits
            return text, 0

        def duplicate_asset(op):
            source = op.get("source", "")
            target = op.get("target", "")
            if asset_exists(target):
                if op.get("reuse_if_exists", True):
                    return {{"success": True, "status": "exists", "target": target}}
                return {{"success": False, "error": "target already exists", "target": target}}
            source_asset = unreal.load_asset(source)
            if source_asset is None:
                return {{"success": False, "error": "source asset not found", "source": source}}
            folder, name = split_target(target)
            created = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, folder, source_asset)
            if created is None:
                return {{"success": False, "error": "duplicate_asset returned None", "target": target}}
            unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{"success": True, "status": "created", "target": full_object_path(target)}}

        def create_material_instance(op):
            parent = op.get("parent", "")
            target = op.get("target", "")
            if asset_exists(target):
                if not op.get("reuse_if_exists", True):
                    return {{"success": False, "error": "target already exists", "target": target}}
                status = "exists"
            else:
                result = MAT.create_material_instance(parent, target)
                if not result.success:
                    return {{"success": False, "error": result.error, "target": target, "parent": parent}}
                status = "created"
            params = op.get("params", [])
            param_result = None
            if params:
                param_result = MAT.set_mi_params(target, [make_mi_param(item) for item in params])
            unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{
                "success": True if param_result is None else bool(param_result.success),
                "status": status,
                "target": full_object_path(target),
                "param_result": None if param_result is None else {{"success": param_result.success, "applied": param_result.applied, "skipped": list(param_result.skipped)}},
            }}

        def set_mi_params(op):
            mi_path = op.get("material_instance", "")
            params = [make_mi_param(item) for item in op.get("params", [])]
            result = MAT.set_mi_params(mi_path, params)
            unreal.EditorAssetLibrary.save_asset(package_path(mi_path), False)
            return {{"success": bool(result.success), "applied": result.applied, "skipped": list(result.skipped), "target": mi_path}}

        def set_niagara_system_props(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            system = unreal.load_asset(system_path)
            if system is None:
                return {{"success": False, "error": "system not found", "system_path": system_path}}
            results = {{}}
            effect_type_path = op.get("effect_type_path", "")
            if effect_type_path:
                effect_type = unreal.load_asset(effect_type_path)
                if effect_type is None:
                    results["EffectType"] = {{"success": False, "error": "effect type not found"}}
                else:
                    try:
                        system.set_editor_property("effect_type", effect_type)
                        results["EffectType"] = {{"success": True}}
                    except Exception as exc:
                        results["EffectType"] = {{"success": False, "error": str(exc)}}
            prop_map = {{
                "fixed_bounds": "FixedBounds",
                "warmup_tick_count": "WarmupTickCount",
                "warmup_tick_delta": "WarmupTickDelta",
                "system_scalability_overrides": "SystemScalabilityOverrides",
            }}
            for key, prop_name in prop_map.items():
                if key in op and op[key] not in (None, ""):
                    ok = PROP.set_u_property_from_export_text(system_path, prop_name, str(op[key]), True)
                    results[prop_name] = {{"success": bool(ok), "value": str(op[key])}}
            unreal.EditorAssetLibrary.save_asset(package_path(system_path), False)
            return {{"success": all(item.get("success", False) for item in results.values()) if results else True, "results": results, "system_path": system_path}}

        def patch_renderer_material(op):
            material_path = op.get("material_path", "")
            if not material_path:
                return {{"success": False, "error": "material_path is required"}}
            emitter_paths = as_list(op.get("emitter_path"))
            matched = []
            if not emitter_paths:
                snapshot = inspect_niagara_system(op.get("system_path") or PLAN.get("target_system", ""))
                for emitter in snapshot.get("emitters", []):
                    if match_emitter(emitter, op):
                        emitter_paths.append(emitter["emitter_path"])
                        matched.append({{"name": emitter.get("name", ""), "emitter_path": emitter["emitter_path"]}})
            changed = []
            failed = []
            for emitter_path in emitter_paths:
                renderer_text, ok = read_export(emitter_path, "RendererProperties")
                if not ok or not renderer_text:
                    failed.append({{"emitter_path": emitter_path, "error": "RendererProperties not readable"}})
                    continue
                new_text, hits = patch_material_text(renderer_text, material_path, bool(op.get("replace_all", False)), op.get("material_regex", ""))
                if not hits:
                    if op.get("allow_noop", False):
                        changed.append({{"emitter_path": emitter_path, "status": "no material slot found", "hits": 0}})
                    else:
                        failed.append({{"emitter_path": emitter_path, "error": "no material slot found", "renderer_digest": digest(renderer_text)}})
                    continue
                ok = PROP.set_u_property_from_export_text(emitter_path, "RendererProperties", new_text, True)
                if ok:
                    unreal.EditorAssetLibrary.save_asset(package_path(emitter_path), False)
                    changed.append({{"emitter_path": emitter_path, "hits": hits, "material": full_object_path(material_path)}})
                else:
                    failed.append({{"emitter_path": emitter_path, "error": "RendererProperties write failed"}})
            return {{"success": bool(changed) and not failed, "matched": matched, "changed": changed, "failed": failed}}

        def set_u_property_export(op):
            target = op.get("object_path", "")
            prop = op.get("property_path", "")
            value = str(op.get("export_text", ""))
            ok = PROP.set_u_property_from_export_text(target, prop, value, bool(op.get("fire_change_notify", True)))
            if ok and op.get("save", True):
                unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{"success": bool(ok), "object_path": target, "property_path": prop}}

        def save_assets(op):
            results = {{}}
            for path in op.get("asset_paths", []):
                results[path] = bool(unreal.EditorAssetLibrary.save_asset(package_path(path), False))
            return {{"success": all(results.values()) if results else True, "results": results}}

        HANDLERS = {{
            "duplicate_asset": duplicate_asset,
            "create_material_instance": create_material_instance,
            "set_mi_params": set_mi_params,
            "set_niagara_system_props": set_niagara_system_props,
            "patch_renderer_material": patch_renderer_material,
            "set_u_property_export": set_u_property_export,
            "save_assets": save_assets,
        }}

        operation_results = []
        for index, op in enumerate(PLAN.get("operations", [])):
            if not op.get("enabled", True):
                operation_results.append({{"index": index, "op": op.get("op"), "success": True, "status": "disabled"}})
                continue
            kind = op.get("op")
            handler = HANDLERS.get(kind)
            if handler is None:
                operation_results.append({{"index": index, "op": kind, "success": False, "error": "unsupported operation"}})
                continue
            try:
                result = handler(op)
                result["index"] = index
                result["op"] = kind
                operation_results.append(result)
            except Exception as exc:
                operation_results.append({{"index": index, "op": kind, "success": False, "error": str(exc)}})

        verification = None
        if {str(bool(verify))}:
            target_system = PLAN.get("target_system", "")
            if target_system:
                try:
                    verification = inspect_niagara_system(target_system)
                except Exception as exc:
                    verification = {{"success": False, "error": str(exc)}}

        payload = {{
            "success": all(item.get("success", False) for item in operation_results),
            "plan_effect": PLAN.get("effect_name", ""),
            "target_system": PLAN.get("target_system", ""),
            "operation_results": operation_results,
            "verification": verification,
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


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
        if not renderer_text.strip():
            plan["warnings"].append(
                f"Skipped emitter `{emitter.get('name', '')}` because RendererProperties is empty; material binding repair needs an existing renderer slot."
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


def render_script_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = load_plan(args.plan)
    target = Path(args.out) if args.out else script_path(ctx, plan.get("effect_name", "effect"))
    write_text(target, build_apply_script(plan, args.verify))
    print(target)
    return 0


def apply_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = load_plan(args.plan)
    script_text = build_apply_script(plan, args.verify)
    script_out = Path(args.script_out) if args.script_out else script_path(ctx, plan.get("effect_name", "effect"))
    write_text(script_out, script_text)
    if args.markdown:
        write_text(Path(args.plan).with_suffix(".md"), render_plan_markdown(plan))
    if not args.apply:
        print(json.dumps({"dry_run": True, "script": str(script_out), "operations": len(plan.get("operations", []))}, ensure_ascii=False))
        return 0
    client = BridgeClient(ctx.skill_root, project=args.project or plan.get("project") or None, timeout_seconds=args.timeout)
    client.ping()
    result = client.exec_json(script_text)
    out = Path(args.out) if args.out else result_path(ctx, plan.get("effect_name", "effect"))
    save_json(out, result)
    print(out)
    return 0


def inspect_system_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = make_plan(args.effect or slugify(args.system_path), "inspect-only", args.system_path, args.project or "", "")
    script_text = build_apply_script(plan, verify=True)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    result = client.exec_json(script_text)
    out = Path(args.out) if args.out else default_report_path(ctx, "ue-inspect", slugify(args.system_path), "niagara-system-inspect", ".json")
    save_json(out, result.get("verification") or result)
    print(out)
    return 0


def export_md_command(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    out = Path(args.out) if args.out else Path(args.plan).with_suffix(".md")
    write_text(out, render_plan_markdown(plan))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, repair, dry-run, and apply safe Niagara asset mutation plans.")
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

    render = subparsers.add_parser("render-script")
    render.add_argument("--plan", required=True)
    render.add_argument("--out")
    render.add_argument("--verify", action="store_true")
    render.set_defaults(func=render_script_command)

    apply_plan = subparsers.add_parser("apply-plan")
    apply_plan.add_argument("--plan", required=True)
    apply_plan.add_argument("--project", default="")
    apply_plan.add_argument("--timeout", type=int, default=240)
    apply_plan.add_argument("--script-out")
    apply_plan.add_argument("--out")
    apply_plan.add_argument("--verify", action="store_true")
    apply_plan.add_argument("--markdown", action="store_true")
    apply_plan.add_argument("--apply", action="store_true", help="Actually execute the generated script through unreal-bridge.")
    apply_plan.set_defaults(func=apply_plan_command)

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
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
