from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .control_common import (
    find_control,
    infer_group,
    infer_runtime_tunable,
    infer_unit,
    load_control_schema,
    make_control_row,
    resolve_root,
    save_control_schema,
    sorted_groups,
)
from .core import normalize_cli_global_args, write_text
from .effect_state import control_schema_default, integration_default, load_effect_record


def build_system_user_variables_script(system_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        summary = unreal.UnrealBridgeNiagaraLibrary.get_official_system_user_variables_summary({system_path!r})
        rows = []
        for item in list(summary.variables):
            rows.append({{
                "name": str(item.name),
                "type_name": str(item.type_name),
                "type_object_path": str(item.type_path),
                "value_struct_path": str(item.value_struct_path),
                "value_json": str(item.value_json),
                "description": str(item.description),
            }})
        print(json.dumps({{
            "success": bool(summary.success),
            "error": str(summary.error),
            "system_path": str(summary.system_path),
            "variables": rows,
        }}, ensure_ascii=False))
        """
    ).strip()


def load_json_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def parse_extra_controls(paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = load_json_file(path)
        items = payload.get("controls") if isinstance(payload.get("controls"), list) else [payload]
        for item in items:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def controls_from_integration(
    integration: dict[str, Any],
    source_path: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    owner = str(integration.get("owner") or "runtime")
    for name in integration.get("user_parameters") or []:
        runtime_surface = "niagara_component_variable"
        rows.append(
            make_control_row(
                logical_name=str(name),
                target_name=str(name),
                surface="niagara_user_variable",
                runtime_surface=runtime_surface,
                type_name="Unknown",
                type_object_path="",
                value_struct_path="",
                default_value_json="",
                range_text="",
                unit=infer_unit(name),
                group=infer_group(name),
                runtime_tunable=infer_runtime_tunable(owner, str(name)),
                driven_by=owner,
                owner=owner,
                purpose=f"Inferred from integration plan user parameter `{name}`.",
                source_kind="integration_placeholder",
                source_path=source_path,
            )
        )
    return rows


def controls_from_system_summary(
    summary: dict[str, Any],
    integration_owner: str,
    source_path: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in summary.get("variables") or []:
        name = str(item.get("name") or "")
        rows.append(
            make_control_row(
                logical_name=name,
                target_name=name,
                surface="niagara_user_variable",
                runtime_surface="niagara_component_variable",
                type_name=str(item.get("type_name") or ""),
                type_object_path=str(item.get("type_object_path") or ""),
                value_struct_path=str(item.get("value_struct_path") or ""),
                default_value_json=str(item.get("value_json") or ""),
                range_text="",
                unit=infer_unit(name),
                group=infer_group(name),
                runtime_tunable=infer_runtime_tunable(integration_owner, name),
                driven_by=integration_owner or "runtime",
                owner=integration_owner or "runtime",
                purpose=str(item.get("description") or f"Live Niagara user variable `{name}`."),
                source_kind="live_system_user_variable",
                source_path=source_path,
            )
        )
    return rows


def controls_from_material_parameters(
    rows: list[dict[str, Any]],
    material_path: str,
    source_path: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in rows:
        name = str(item.get("name") or "")
        param_type = str(item.get("type") or "Unknown")
        owner = str(item.get("owner") or "artist")
        default_value = str(item.get("default") or item.get("default_value") or "")
        range_text = str(item.get("range") or "")
        items.append(
            make_control_row(
                logical_name=name,
                target_name=name,
                surface="material_instance_parameter",
                runtime_surface="material_instance_parameter",
                type_name=param_type,
                type_object_path=param_type,
                value_struct_path=param_type,
                default_value_json=default_value,
                range_text=range_text,
                unit=infer_unit(name, range_text),
                group=infer_group(name),
                runtime_tunable=infer_runtime_tunable(owner, name),
                driven_by=owner,
                owner=owner,
                purpose=str(item.get("purpose") or f"Material parameter `{name}`."),
                source_kind="material_parameter",
                source_path=source_path or material_path,
            )
        )
    return items


def merge_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("id") or "")
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
            continue
        for field in (
            "type_name",
            "type_object_path",
            "value_struct_path",
            "default_value_json",
            "default_value_text",
            "range_text",
            "unit",
            "purpose",
            "source_kind",
            "source_path",
        ):
            if not existing.get(field) and row.get(field):
                existing[field] = row[field]
        existing["runtime_tunable"] = bool(existing.get("runtime_tunable") or row.get("runtime_tunable"))
        if row.get("probe_support", "").startswith("runtime_component"):
            existing["probe_support"] = row["probe_support"]
        if row.get("suggested_sweep_values"):
            existing["suggested_sweep_values"] = row["suggested_sweep_values"]
    return sorted(merged.values(), key=lambda item: (str(item.get("group") or ""), str(item.get("logical_name") or "")))


def build_schema(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root(args.root)
    effect = args.effect or Path(args.system_path or args.material_delivery_package or "effect").stem
    payload = control_schema_default(effect)
    payload["effect_name"] = effect
    payload["system_path"] = args.system_path
    payload["component_path"] = args.component_path
    payload["material_paths"] = [item for item in [args.material_path] if item]
    payload["notes"] = list(args.note or [])
    payload["sources"] = {
        "integration_plan": args.integration_plan,
        "material_delivery_package": args.material_delivery_package,
        "material_contract": args.material_contract,
        "extra_controls": args.extra_control,
    }

    integration = (
        load_json_file(args.integration_plan)
        if args.integration_plan
        else load_effect_record(ctx, "integration-plans", effect, integration_default(effect))
    )
    integration_source = args.integration_plan or "effect_state:integration-plans"
    all_controls = controls_from_integration(integration, integration_source)

    live_summary = {}
    if args.system_path and (args.project or args.endpoint):
        client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
        client.ping()
        live_summary = client.exec_json(build_system_user_variables_script(args.system_path), no_preflight=True)
        all_controls.extend(
            controls_from_system_summary(
                live_summary,
                str(integration.get("owner") or "runtime"),
                args.system_path,
            )
        )

    material_package = load_json_file(args.material_delivery_package)
    material_contract = load_json_file(args.material_contract)
    material_parameter_rows = []
    if isinstance(material_package.get("parameters"), list):
        material_parameter_rows.extend(material_package["parameters"])
    if not material_parameter_rows and isinstance(material_contract.get("parameters"), list):
        material_parameter_rows.extend(material_contract["parameters"])
    material_path = args.material_path or str(material_package.get("material_path") or "")
    if material_parameter_rows:
        all_controls.extend(
            controls_from_material_parameters(
                material_parameter_rows,
                material_path,
                args.material_delivery_package or args.material_contract,
            )
        )
        if material_path and material_path not in payload["material_paths"]:
            payload["material_paths"].append(material_path)

    for item in parse_extra_controls(args.extra_control):
        all_controls.append(
            make_control_row(
                logical_name=str(item.get("logical_name") or item.get("target_name") or item.get("name") or ""),
                target_name=str(item.get("target_name") or item.get("name") or item.get("logical_name") or ""),
                surface=str(item.get("surface") or "manual_control"),
                runtime_surface=str(item.get("runtime_surface") or item.get("surface") or "manual_control"),
                type_name=str(item.get("type_name") or item.get("type") or ""),
                type_object_path=str(item.get("type_object_path") or ""),
                value_struct_path=str(item.get("value_struct_path") or ""),
                default_value_json=str(item.get("default_value_json") or item.get("default") or ""),
                range_text=str(item.get("range_text") or item.get("range") or ""),
                unit=str(item.get("unit") or infer_unit(str(item.get("name") or ""))),
                group=str(item.get("group") or infer_group(str(item.get("name") or ""))),
                runtime_tunable=bool(item.get("runtime_tunable", True)),
                driven_by=str(item.get("driven_by") or "runtime"),
                owner=str(item.get("owner") or "runtime"),
                purpose=str(item.get("purpose") or "manual extra control"),
                source_kind="manual_extra",
                source_path=";".join(args.extra_control),
            )
        )

    controls = merge_controls(all_controls)
    payload["controls"] = controls
    payload["groups"] = sorted_groups(controls)
    payload["summary"] = {
        "control_count": len(controls),
        "runtime_probe_supported": sum(1 for item in controls if str(item.get("probe_support") or "").startswith("runtime_component")),
        "sweep_supported": sum(1 for item in controls if str(item.get("sweep_support") or "").endswith("sweep")),
        "live_system_user_variable_count": len(live_summary.get("variables") or []),
        "material_parameter_count": len(material_parameter_rows),
    }
    out_path = save_control_schema(ctx, effect, payload, args.out)
    return payload, out_path


def render_markdown(schema: dict[str, Any]) -> str:
    lines = [
        f"# Effect Control Schema: {schema.get('effect_name', '')}",
        "",
        f"- System path: `{schema.get('system_path', '') or 'unset'}`",
        f"- Component path: `{schema.get('component_path', '') or 'unset'}`",
        f"- Material paths: {', '.join(schema.get('material_paths') or []) or 'none'}",
        f"- Control count: `{(schema.get('summary') or {}).get('control_count', 0)}`",
        "",
    ]
    for group in schema.get("groups") or []:
        lines.extend([f"## {group}", ""])
        for item in schema.get("controls") or []:
            if item.get("group") != group:
                continue
            lines.extend(
                [
                    f"- `{item.get('id', '')}`",
                    f"  surface=`{item.get('surface', '')}` runtime_surface=`{item.get('runtime_surface', '')}` type=`{item.get('type_name', '') or 'unknown'}`",
                    f"  default=`{item.get('default_value_text', '') or 'unset'}` range=`{item.get('range_text', '') or 'unset'}` unit=`{item.get('unit', '') or 'unset'}`",
                    f"  driven_by=`{item.get('driven_by', '')}` runtime_tunable=`{item.get('runtime_tunable')}` probe=`{item.get('probe_support', '')}` sweep=`{item.get('sweep_support', '')}`",
                    f"  purpose={item.get('purpose', '') or 'none'}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def command_generate(args: argparse.Namespace) -> int:
    schema, out_path = build_schema(args)
    if args.markdown:
        write_text(out_path.with_suffix(".md"), render_markdown(schema))
    print(out_path)
    return 0


def command_show(args: argparse.Namespace) -> int:
    schema = load_control_schema(args.schema)
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    return 0


def command_export(args: argparse.Namespace) -> int:
    schema = load_control_schema(args.schema)
    out = Path(args.out) if args.out else Path(args.schema).with_suffix(".md")
    write_text(out, render_markdown(schema))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a unified control table across Niagara user vars, component vars, and material parameters.")
    parser.add_argument("--root", default="auto")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--effect", default="")
    generate.add_argument("--system-path", default="")
    generate.add_argument("--component-path", default="")
    generate.add_argument("--material-path", default="")
    generate.add_argument("--integration-plan", default="")
    generate.add_argument("--material-delivery-package", default="")
    generate.add_argument("--material-contract", default="")
    generate.add_argument("--extra-control", action="append", default=[])
    generate.add_argument("--project")
    generate.add_argument("--endpoint")
    generate.add_argument("--timeout", type=int, default=180)
    generate.add_argument("--out")
    generate.add_argument("--note", action="append", default=[])
    generate.add_argument("--markdown", action="store_true")
    generate.set_defaults(func=command_generate)

    show = sub.add_parser("show")
    show.add_argument("schema")
    show.set_defaults(func=command_show)

    export_md = sub.add_parser("export-md")
    export_md.add_argument("schema")
    export_md.add_argument("--out")
    export_md.set_defaults(func=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands={"generate", "show", "export-md"}, global_opts_with_value={"--root"})
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
