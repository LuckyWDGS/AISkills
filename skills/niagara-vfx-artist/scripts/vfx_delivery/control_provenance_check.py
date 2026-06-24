from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bridge import BridgeClient
from .control_common import load_control_schema, resolve_root
from .core import default_report_path, normalize_cli_global_args, save_json, utc_now_iso, write_text
from .effect_control_schema import build_system_user_variables_script, load_json_file


def command_check(args: argparse.Namespace) -> int:
    ctx = resolve_root(args.root)
    schema = load_control_schema(args.schema)
    effect = str(schema.get("effect_name") or "Effect")
    material_package = load_json_file(args.material_delivery_package)
    live_summary = {}
    if args.system_path and (args.project or args.endpoint):
        client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
        client.ping()
        live_summary = client.exec_json(build_system_user_variables_script(args.system_path), no_preflight=True)
    live_names = {str(item.get("name") or "") for item in live_summary.get("variables") or []}
    package_params = {str(item.get("name") or "") for item in material_package.get("parameters") or [] if isinstance(item, dict)}
    rows = []
    for control in schema.get("controls") or []:
        surface = str(control.get("surface") or "")
        target_name = str(control.get("target_name") or "")
        if surface == "niagara_user_variable":
            exists = target_name in live_names
            status = "pass" if exists else "missing"
            evidence = "live system user variable summary" if exists else "not found in live system summary"
        elif surface == "material_instance_parameter":
            exists = target_name in package_params
            status = "pass" if exists else "missing"
            evidence = "material delivery package parameters" if exists else "not found in material delivery package"
        else:
            exists = False
            status = "unknown"
            evidence = "no provenance rule implemented"
        rows.append(
            {
                "control_id": control.get("id", ""),
                "surface": surface,
                "target_name": target_name,
                "status": status,
                "evidence": evidence,
            }
        )
    report = {
        "tool": "control_provenance_check",
        "generated_utc": utc_now_iso(),
        "effect_name": effect,
        "schema": str(Path(args.schema).resolve()),
        "system_path": args.system_path,
        "rows": rows,
        "summary": {
            "pass": sum(1 for item in rows if item["status"] == "pass"),
            "missing": sum(1 for item in rows if item["status"] == "missing"),
            "unknown": sum(1 for item in rows if item["status"] == "unknown"),
        },
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "control-provenance", effect, "control-provenance-check", ".json")
    save_json(out, report)
    if args.markdown:
        lines = [f"# Control Provenance: {effect}", ""]
        for item in rows:
            lines.append(f"- `{item['control_id']}` status=`{item['status']}` evidence={item['evidence']}")
        write_text(out.with_suffix(".md"), "\n".join(lines).rstrip() + "\n")
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether declared controls can be traced to live Niagara user vars or material parameter evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--system-path", default="")
    parser.add_argument("--material-delivery-package", default="")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands=set())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
