"""Create and parameterize Material Instances through Epic's built-in MCP.

Plan, validate, then run: live reads (instance existence, current parents, the
parent's parameters) turn the JSON spec into a reviewable JSONL step plan for
``builtin_mcp.py batch``. Every write carries a readback with an ``expect``, and
each instance ends with a save of that package only. Without ``--execute``
nothing is written; ``--from-plan`` runs a previously reviewed plan.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .material_audit import object_path
from .mcp import DEFAULT_MCP_URL, builtin_mcp, connect


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "material_instance_batch/2"

MI = "MaterialInstanceTools"
# spec type -> (setter, getter, list_parameters type)
PARAM_TOOLS = {
    "scalar": ("set_scalar_parameter", "get_scalar_parameter", "Scalar"),
    "vector": ("set_vector_parameter", "get_vector_parameter", "Vector"),
    "texture": ("set_texture_parameter", "get_texture_parameter", "Texture"),
    "static_switch": ("set_static_switch_parameter", "get_static_switch_parameter", "StaticSwitch"),
}
COVERAGE_GAPS = [
    "Previews use EditorAppToolset.CaptureAssetImage (the editor's thumbnail renderer); "
    "mesh, lighting, camera and resolution options of the retired plugin preview are not available.",
]


def load_spec(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def asset_path(path: str) -> str:
    """'/Game/M/MI_X.MI_X' -> '/Game/M/MI_X' (AssetTools takes package paths)."""
    head, _, leaf = path.rpartition("/")
    return f"{head}/{leaf.split('.', 1)[0]}"


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"unsupported boolean value {value!r}")


def normalize_value(ptype: str, value: Any) -> Any:
    """The tool argument for a spec value; it is also the readback expectation."""
    if ptype == "scalar":
        return float(value)
    if ptype == "vector":
        if isinstance(value, str) and value.strip().startswith("("):
            # UE text form, e.g. "(R=1,G=0.6,B=0.2,A=1)".
            value = {key.lower(): float(number) for key, number in
                     re.findall(r"([RGBA])\s*=\s*([-+0-9.eE]+)", value, re.IGNORECASE)}
        elif isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError(f"vector value must be an object with r/g/b/a, got {value!r}")
        return {channel: float(value.get(channel, 1.0 if channel == "a" else 0.0)) for channel in "rgba"}
    if ptype == "texture":
        if isinstance(value, str) and value.strip().startswith("{"):
            value = json.loads(value)
        path = value.get("refPath") if isinstance(value, dict) else str(value)
        if not path:
            raise ValueError("texture value needs a refPath")
        return {"refPath": object_path(path)}
    if ptype == "static_switch":
        return parse_bool(value)
    raise ValueError(f"unsupported parameter type {ptype!r}")


def collect_facts(client: Any, module: Any, spec: dict[str, Any]) -> dict[str, Any]:
    """Read-only live facts the plan depends on."""
    def call(toolset: str, tool: str, args: dict[str, Any]) -> Any:
        return module.unwrap_result(client.call_resolved_tool(toolset, tool, args))

    facts: dict[str, Any] = {"instances": {}, "parents": {}}
    parents = {item.get("parent_path") or spec.get("parent_path") for item in spec.get("instances", [])}
    for parent in sorted(path for path in parents if path):
        exists = bool(call("AssetTools", "exists", {"path": asset_path(parent)}))
        params = call(MI, "list_parameters", {"material": {"refPath": object_path(parent)}}) if exists else []
        facts["parents"][parent] = {"exists": exists, "parameters": params}
    for item in spec.get("instances", []):
        path = item["path"]
        exists = bool(call("AssetTools", "exists", {"path": asset_path(path)}))
        current_parent = ""
        if exists:
            props = call("ObjectTools", "get_properties", {"instance": {"refPath": object_path(path)}, "properties": ["parent"]})
            parent = props.get("parent") if isinstance(props, dict) else ""
            current_parent = parent.get("refPath", "") if isinstance(parent, dict) else str(parent or "")
        facts["instances"][path] = {"exists": exists, "parent": current_parent}
    return facts


def build_plan(spec: dict[str, Any], facts: dict[str, Any], *, reuse_existing: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Turn the spec into batch steps; returns (steps, problems). Pure: no editor access."""
    steps: list[dict[str, Any]] = []
    problems: list[str] = []
    for item in spec.get("instances", []):
        path = item["path"]
        parent = item.get("parent_path") or spec.get("parent_path") or ""
        leaf = asset_path(path).rsplit("/", 1)[-1]
        ref = {"refPath": object_path(path)}
        parent_facts = facts["parents"].get(parent) or {"exists": False, "parameters": []}
        instance_facts = facts["instances"].get(path) or {"exists": False, "parent": ""}
        if not parent:
            problems.append(f"{path}: no parent_path")
            continue
        if not parent_facts["exists"]:
            problems.append(f"{path}: parent {parent} does not exist")
            continue
        if instance_facts["exists"]:
            if not reuse_existing:
                problems.append(f"{path}: already exists; pass --reuse-existing to update it")
                continue
            if object_path(instance_facts["parent"]) != object_path(parent):
                problems.append(f"{path}: exists with parent {instance_facts['parent']}, not {parent}; refusing to reparent")
                continue
        else:
            steps.append({
                "label": f"{leaf}: create", "instance": path, "kind": "create",
                "toolset": MI, "tool": "create",
                "args": {"folder_path": asset_path(path).rsplit("/", 1)[0], "asset_name": leaf,
                         "parent": {"refPath": object_path(parent)}},
                "readback": {"toolset": "ObjectTools", "tool": "get_properties",
                             "args": {"instance": ref, "properties": ["parent"]}},
                "expect": {"parent": {"refPath": object_path(parent)}},
            })
        available = {(row.get("name"), row.get("type")) for row in parent_facts["parameters"]}
        for param in item.get("params") or []:
            name, ptype = param.get("name", ""), str(param.get("type", "")).strip().lower()
            if ptype not in PARAM_TOOLS:
                problems.append(f"{path}: parameter {name!r} has unsupported type {param.get('type')!r}")
                continue
            setter, getter, listed_type = PARAM_TOOLS[ptype]
            if (name, listed_type) not in available:
                problems.append(f"{path}: parent {parent} has no {listed_type} parameter {name!r}")
                continue
            try:
                value = normalize_value(ptype, param.get("value"))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                problems.append(f"{path}: parameter {name!r}: {exc}")
                continue
            steps.append({
                "label": f"{leaf}: {name}", "instance": path, "kind": "param", "param": name, "param_type": ptype,
                "toolset": MI, "tool": setter, "args": {"instance": ref, "name": name, "value": value},
                "readback": {"toolset": MI, "tool": getter, "args": {"instance": ref, "name": name}},
                "expect": value,
            })
        steps.append({
            "label": f"{leaf}: save", "instance": path, "kind": "save",
            "toolset": "AssetTools", "tool": "save_assets", "args": {"asset_paths": [asset_path(path)]},
            "readback": {"toolset": "AssetTools", "tool": "is_dirty", "args": {"asset_path": asset_path(path)}},
            "expect": False,
        })
    return steps, problems


def write_plan(path: Path, steps: list[dict[str, Any]]) -> None:
    lines = ["# material_instance_batch plan: one builtin_mcp batch step per line; review before --execute"]
    lines += [json.dumps(step, ensure_ascii=False) for step in steps]
    write_text(path, "\n".join(lines) + "\n")


def instance_rows(entries: list[dict[str, Any]], batch: dict[str, Any] | None,
                  spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Per-instance rows in the legacy report shape (create / set_params / save)."""
    results = {row["line"]: row for row in (batch or {}).get("results", [])}
    rows: dict[str, dict[str, Any]] = {}
    planned_creates = {entry.get("instance") for entry in entries if entry.get("kind") == "create"}
    parents = {item["path"]: item.get("parent_path") or (spec or {}).get("parent_path", "") for item in (spec or {}).get("instances", [])}
    for entry in entries:
        path = entry.get("instance", "")
        row = rows.setdefault(path, {
            "path": path, "parent_path": parents.get(path, ""),
            # No create step means the plan reuses an existing instance.
            "create": {"success": False, "path": object_path(path) if path else "", "error": "", "route": "epic-mcp",
                       "reused_existing": path not in planned_creates},
            "set_params": {"success": True, "applied": 0, "skipped": [], "route": "epic-mcp", "param_results": []},
        })
        result = results.get(entry["_line"], {"status": "not-run"})
        ok = result.get("status") == "ok"
        if entry.get("kind") == "create":
            row["create"].update(success=ok, error=result.get("error", ""))
        elif entry.get("kind") == "param":
            row["set_params"]["param_results"].append({"name": entry["param"], "type": entry["param_type"],
                                                       "status": result.get("status"), "error": result.get("error", "")})
            if ok:
                row["set_params"]["applied"] += 1
            else:
                row["set_params"]["success"] = False
                row["set_params"]["skipped"].append(entry["param"])
        elif entry.get("kind") == "save":
            row["save"] = {"success": ok, "status": result.get("status"), "error": result.get("error", "")}
    for row in rows.values():
        if row["create"]["reused_existing"]:
            row["create"]["success"] = True
        if not row["set_params"]["param_results"]:
            row.pop("set_params")
    return list(rows.values())


def capture_previews(client: Any, module: Any, rows: list[dict[str, Any]], out_dir: Path) -> None:
    for row in rows:
        if not (row["create"]["success"] and (row.get("save") or {}).get("success")):
            continue
        out_png = out_dir / f"{slugify(row['path'])}-preview.png"
        try:
            image = module.unwrap_result(client.call_resolved_tool(
                "EditorAppToolset", "CaptureAssetImage", {"assetPath": asset_path(row["path"])}))
            out_png.parent.mkdir(parents=True, exist_ok=True)
            out_png.write_bytes(base64.b64decode(image["data"]))
            row["preview"] = {"ok": True, "out_png": str(out_png)}
        except Exception as exc:  # A preview failure never undoes the batch; report it.
            row["preview"] = {"ok": False, "out_png": str(out_png), "error": str(exc)}


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Material Instance Batch", "", f"- Status: `{report['status']}`", f"- Plan: `{report['plan']}`", ""]
    if report.get("problems"):
        lines += ["## Problems", ""] + [f"- {item}" for item in report["problems"]] + [""]
    for item in report["instances"]:
        create = item.get("create") or {}
        lines += [f"## {item['path']}", "", f"- Parent: `{item['parent_path']}`", f"- Created: `{create.get('success')}`"]
        if create.get("reused_existing"):
            lines.append("- Reused existing asset: `True`")
        if create.get("error"):
            lines.append(f"- Create error: `{create['error']}`")
        if item.get("set_params"):
            lines.append(f"- Params applied: `{item['set_params']['applied']}`")
            lines.append(f"- Param skipped count: `{len(item['set_params'].get('skipped') or [])}`")
        if item.get("save"):
            lines.append(f"- Saved: `{item['save']['success']}`")
        if item.get("preview"):
            lines.append(f"- Preview ok: `{item['preview']['ok']}` `{item['preview']['out_png']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    module = builtin_mcp(ctx.skill_root)
    spec = load_spec(args.spec) if args.spec else {}
    effect = slugify(args.effect or spec.get("effect") or spec.get("parent_path") or "material-instances")
    out = Path(args.out) if args.out else default_report_path(ctx, "instances", effect, "material-instance-batch", ".json")
    client = connect(ctx.skill_root, url=args.mcp_url, timeout=args.timeout, project=args.project)
    try:
        entries: list[dict[str, Any]] = []
        batch = None
        plan_path = Path(args.from_plan) if args.from_plan else out.with_name(out.stem + "-plan.jsonl")
        if client.pie_running():
            # During PIE, existence checks report false, so a plan would try to recreate existing assets.
            problems = ["Play-In-Editor is running; stop PIE and run again."]
            status = "blocked"
        else:
            problems = []
            if not args.from_plan:
                facts = collect_facts(client, module, spec)
                steps, problems = build_plan(spec, facts, reuse_existing=args.reuse_existing or bool(spec.get("reuse_existing")))
                write_plan(plan_path, steps)
            entries = module.load_batch(plan_path)
            if problems:
                status = "blocked"
            else:
                validation = module.run_batch(client, entries, dry_run=True)
                problems = validation["problems"]
                if problems:
                    status = "blocked"
                elif not args.execute:
                    status = "planned"
                else:
                    batch = module.run_batch(client, entries)
                    status = "applied" if batch["ok"] else "failed"
                    if batch.get("left_dirty"):
                        problems = [f"left unsaved after the batch (clean or absent before): {', '.join(batch['left_dirty'])}"]
                        status = "applied_with_side_effects" if batch["ok"] else status
        rows = instance_rows(entries, batch, spec)
        if batch and args.preview:
            capture_previews(client, module, rows, out.parent)
    finally:
        client.close()

    report = {
        "tool": "material_instance_batch",
        "schema_version": SCHEMA_VERSION,
        "effect": effect,
        "status": status,
        "source_spec": str(Path(args.spec).resolve()) if args.spec else "",
        "plan": str(plan_path.resolve()),
        "problems": problems,
        "transport": "epic-mcp batch",
        "instances": rows,
        "batch": batch,
        "coverage_gaps": COVERAGE_GAPS,
    }
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0 if status in ("planned", "applied") else 1  # side effects or failures need a look


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, validate and (with --execute) create and parameterize Material Instances through Epic's built-in MCP.")
    parser.add_argument("spec", nargs="?", help="Batch spec JSON (omit with --from-plan).")
    parser.add_argument("--from-plan", help="Run a previously generated, reviewed JSONL plan instead of planning from a spec.")
    parser.add_argument("--execute", action="store_true", help="Apply the plan; without it nothing is written.")
    parser.add_argument("--reuse-existing", action="store_true", help="Update instances that already exist with the same parent.")
    parser.add_argument("--preview", action="store_true", help="After --execute, save a thumbnail PNG per saved instance.")
    parser.add_argument("--project", help="Refuse to run unless the MCP endpoint is served by this project.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--root", default="auto")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.spec and not args.from_plan:
        parser.error("give a spec, or --from-plan with a reviewed plan")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
