from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .control_common import load_control_schema, resolve_root
from .core import default_report_path, normalize_cli_global_args, save_json, slugify, write_text
from .effect_state import integration_default, load_effect_record


def blueprint_type_for(control: dict[str, Any]) -> str:
    type_blob = " ".join([str(control.get("type_name") or ""), str(control.get("type_object_path") or "")]).lower()
    if "float" in type_blob or "double" in type_blob:
        return "float"
    if "int32" in type_blob or type_blob.endswith(" int"):
        return "int"
    if "bool" in type_blob:
        return "bool"
    if "linearcolor" in type_blob:
        return "LinearColor"
    if "vector" in type_blob:
        return "Vector"
    return "variant"


def suggested_setter(control: dict[str, Any]) -> str:
    surface = str(control.get("surface") or "")
    if surface in {"niagara_user_variable", "niagara_component_variable"}:
        return "Niagara.set_official_component_variable(component_path, variable_name, type_object_path, value_struct_path, value_json)"
    if surface == "material_instance_parameter":
        type_blob = str(control.get("type_name") or "").lower()
        if "scalar" in type_blob:
            return "MaterialInstanceTools.set_scalar_parameter(instance, name, value)"
        if "vector" in type_blob:
            return "MaterialInstanceTools.set_vector_parameter(instance, name, value)"
        if "texture" in type_blob:
            return "MaterialInstanceTools.set_texture_parameter(instance, name, value)"
    return "manual wiring required"


def generate_bindings(schema: dict[str, Any], integration: dict[str, Any], owner_override: str = "") -> dict[str, Any]:
    owner = owner_override or str(integration.get("owner") or "runtime")
    socket_list = list(integration.get("sockets") or [])
    notifies = list(integration.get("notifies") or [])
    rows = []
    for control in schema.get("controls") or []:
        runtime_surface = str(control.get("runtime_surface") or control.get("surface") or "")
        rows.append(
            {
                "control_id": control.get("id", ""),
                "logical_name": control.get("logical_name", ""),
                "surface": control.get("surface", ""),
                "runtime_surface": runtime_surface,
                "blueprint_variable_name": str(control.get("logical_name") or "").replace(".", "_"),
                "blueprint_variable_type": blueprint_type_for(control),
                "setter_call": suggested_setter(control),
                "binding_owner": owner,
                "binding_route": {
                    "socket": socket_list[0] if socket_list else "",
                    "notify": notifies[0] if notifies else "",
                    "attachment_mode": integration.get("attachment_mode", ""),
                    "source_space": integration.get("source_space", ""),
                },
                "runtime_tunable": bool(control.get("runtime_tunable")),
                "driven_by": control.get("driven_by", ""),
            }
        )
    return {
        "effect_name": schema.get("effect_name", ""),
        "system_path": schema.get("system_path", ""),
        "component_path": schema.get("component_path", ""),
        "bindings": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Control Binding Generator: {report.get('effect_name', '')}", ""]
    for item in report.get("bindings") or []:
        lines.extend(
            [
                f"- `{item.get('control_id', '')}`",
                f"  bp_var=`{item.get('blueprint_variable_name', '')}` type=`{item.get('blueprint_variable_type', '')}`",
                f"  setter=`{item.get('setter_call', '')}` owner=`{item.get('binding_owner', '')}` driven_by=`{item.get('driven_by', '')}`",
                f"  notify=`{(item.get('binding_route') or {}).get('notify', '') or 'unset'}` socket=`{(item.get('binding_route') or {}).get('socket', '') or 'unset'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def command_generate(args: argparse.Namespace) -> int:
    ctx = resolve_root(args.root)
    schema = load_control_schema(args.schema)
    effect = str(schema.get("effect_name") or args.effect or "Effect")
    integration = (
        json.loads(Path(args.integration_plan).read_text(encoding="utf-8"))
        if args.integration_plan
        else load_effect_record(ctx, "integration-plans", effect, integration_default(effect))
    )
    report = {
        "tool": "control_binding_generator",
        **generate_bindings(schema, integration, args.owner),
        "source": {
            "schema": str(Path(args.schema).resolve()),
            "integration_plan": args.integration_plan or "effect_state:integration-plans",
        },
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "control-bindings", effect, "control-binding-generator", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate first-pass Blueprint/GAS/Notify binding scaffolds from an effect control schema.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--integration-plan", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command_generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands=set())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
