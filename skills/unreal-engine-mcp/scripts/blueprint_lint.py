#!/usr/bin/env python3
"""Read-only delivery lint for an authored Blueprint: layout, Chinese annotations, debug leftovers, logging.

It reads the graph through inspect_blueprint.py (Epic MCP), comment frames through Epic's
public BlueprintGraphEditor API over Python Remote Execution, and variable categories through
BlueprintTools. Nothing is edited, compiled or saved.

    python scripts/blueprint_lint.py /Game/Gameplay/BP_Throwable --out <dir>
    python scripts/blueprint_lint.py /Game/Gameplay/BP_Throwable --inspect-dir <existing inspect output> --no-comments

Layout geometry is estimated from node positions and pin counts (the API has no node sizes),
so treat counts as review pointers, not pixel-exact measurements.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from inspect_blueprint import EXEC_TYPES, analyze_snapshot, ref_path  # noqa: E402


SCHEMA_VERSION = "blueprint_lint/1"
# Thresholds in graph units (one grid square is 16).
BACKWARD_TOLERANCE = 40          # an exec target this far left of its source counts as a backward wire
EXEC_LANE_JUMP = 480             # vertical jump between consecutive exec nodes
LONG_DATA_WIRE = 1400            # data wire length; getters should sit next to their consumer
GETTER_SPREAD = 900              # distance between the farthest consumers of one getter node
OVERLAP_SHARE = 0.25             # overlap area relative to the smaller node
LARGE_GRAPH_NODES = 30
CJK = re.compile(r"[一-鿿]")
MODULE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+){1,}")
DEBUG_NODE = re.compile(r"DrawDebug|FlushPersistentDebugLines", re.IGNORECASE)
ENTRY_TYPES = ("K2Node_Event", "K2Node_CustomEvent", "K2Node_ComponentBoundEvent", "K2Node_InputAction",
               "K2Node_EnhancedInputAction", "K2Node_FunctionEntry")


def node_name(path: str) -> str:
    return path.rsplit(".", 1)[-1]


def short_title(type_id: str) -> str:
    return type_id.rsplit("|", 1)[-1] or type_id


def node_box(node: dict[str, Any], exec_types: set[str]) -> tuple[float, float, float, float]:
    """Estimated (x, y, width, height) of a node from its title and pin counts."""
    x, y = node["position"]["x"], node["position"]["y"]
    ins, outs = len(node["input_pins"]), len(node["output_pins"])
    is_getter = node_name(ref_path(node["node"])).startswith("K2Node_VariableGet") and ins == 0
    has_exec = any(pin["type_id"] in exec_types for pin in node["input_pins"] + node["output_pins"])
    if is_getter or (ins + outs <= 2 and not has_exec):
        return x, y, 160.0, 48.0
    width = min(420.0, max(200.0, 120 + 7 * len(short_title(node["type_id"]))))
    return x, y, width, 44.0 + 24.0 * max(ins, outs)


def pin_point(node: dict[str, Any], box: tuple[float, float, float, float], pin_name: str, output: bool) -> tuple[float, float]:
    pins = node["output_pins"] if output else node["input_pins"]
    index = next((i for i, pin in enumerate(pins) if pin["name"] == pin_name), 0)
    x, y, width, _ = box
    return (x + width if output else x), y + 36 + 24 * index


def segments_cross(a: tuple, b: tuple, c: tuple, d: tuple) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0


def overlap_share(a: tuple, b: tuple) -> float:
    width = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    height = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0.0
    return width * height / min(a[2] * a[3], b[2] * b[3])


def lint_layout(snapshot: dict[str, Any], analysis: dict[str, Any], exec_types: set[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for graph in snapshot["graphs"]:
        gpath = ref_path(graph["graph"])
        gname = gpath.rsplit(":", 1)[-1]
        nodes = {ref_path(node["node"]): node for node in graph["nodes"]}
        boxes = {path: node_box(node, exec_types) for path, node in nodes.items()}
        edges = [edge for edge in analysis["edges"] if edge["graph"] == gpath and edge.get("resolved")]

        def add(rule: str, severity: str, message: str, **detail: Any) -> None:
            findings.append({"graph": gname, "rule": rule, "severity": severity, "message": message, **detail})

        def label(path: str) -> str:
            node = nodes.get(path)
            title = short_title(node["type_id"]) if node else node_name(path)
            return f"{title} ({node_name(path)})"

        segments = []
        getter_targets: dict[str, list[tuple[float, float]]] = {}
        for edge in edges:
            source = ref_path(edge["source"]["pin_id"]["node"])
            target = ref_path(edge["target"]["pin_id"]["node"])
            if source not in nodes or target not in nodes:
                continue
            start = pin_point(nodes[source], boxes[source], edge["source"]["name"], True)
            end = pin_point(nodes[target], boxes[target], edge["target"]["name"], False)
            segments.append((start, end, source, target))
            if edge["kind"] == "execution":
                if end[0] < start[0] - BACKWARD_TOLERANCE:
                    add("backward_exec", "warning", f"exec wire runs right-to-left: {label(source)} -> {label(target)}",
                        nodes=[node_name(source), node_name(target)])
                elif abs(end[1] - start[1]) > EXEC_LANE_JUMP:
                    add("exec_lane_jump", "info", f"exec wire jumps {abs(end[1] - start[1]):.0f} units vertically: "
                        f"{label(source)} -> {label(target)}", nodes=[node_name(source), node_name(target)])
            else:
                length = math.dist(start, end)
                if length > LONG_DATA_WIRE:
                    add("long_data_wire", "warning", f"{length:.0f}-unit data wire {label(source)}.{edge['source']['name']} -> "
                        f"{label(target)}.{edge['target']['name']}; place a getter or reroute next to the consumer",
                        nodes=[node_name(source), node_name(target)])
                if node_name(source).startswith("K2Node_VariableGet"):
                    getter_targets.setdefault(source, []).append(end)
        for getter, points in getter_targets.items():
            spread = max((math.dist(a, b) for a in points for b in points), default=0)
            if len(points) > 1 and spread > GETTER_SPREAD:
                add("getter_fanout", "warning", f"one getter {label(getter)} feeds {len(points)} pins up to {spread:.0f} "
                    "units apart; use one getter per consumer", nodes=[node_name(getter)])
        paths = list(nodes)
        for i, first in enumerate(paths):
            for second in paths[i + 1:]:
                share = overlap_share(boxes[first], boxes[second])
                if share > OVERLAP_SHARE:
                    add("node_overlap", "warning", f"{label(first)} and {label(second)} overlap (~{share:.0%})",
                        nodes=[node_name(first), node_name(second)])
        crossings = sum(1 for i, a in enumerate(segments) for b in segments[i + 1:]
                        if not {a[2], a[3]} & {b[2], b[3]} and segments_cross(a[0], a[1], b[0], b[1]))
        limit = max(4, len(segments) // 6)
        if crossings > limit:
            add("wire_crossings", "warning", f"about {crossings} wire crossings across {len(segments)} wires (limit {limit}); "
                "reorder rows so data flows left-to-right under its exec line", count=crossings)
        if len(nodes) > LARGE_GRAPH_NODES:
            add("large_graph", "info", f"{len(nodes)} nodes; split repeated or separable steps into functions")
    return findings


def lint_debug_and_logging(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    logs = 0
    for graph in snapshot["graphs"]:
        gname = ref_path(graph["graph"]).rsplit(":", 1)[-1]
        for node in graph["nodes"]:
            title, name = short_title(node["type_id"]), node_name(ref_path(node["node"]))
            values = {pin["name"]: str(pin.get("value") or "") for pin in node["input_pins"]}
            if DEBUG_NODE.search(title):
                findings.append({"graph": gname, "rule": "debug_draw", "severity": "warning", "nodes": [name],
                                 "message": f"{title} draws debug geometry; ship a mesh/spline/Niagara/material presentation instead"})
            debug_type = values.get("DrawDebugType", "")
            if debug_type and debug_type.split("::")[-1] not in ("None", "EDrawDebugTrace::None"):
                findings.append({"graph": gname, "rule": "debug_draw", "severity": "warning", "nodes": [name],
                                 "message": f"{title} DrawDebugType={debug_type}; set None in the delivered graph"})
            if title in ("PrintString", "PrintText"):
                if values.get("bPrintToScreen", "true").lower() == "true":
                    findings.append({"graph": gname, "rule": "screen_print", "severity": "warning", "nodes": [name],
                                     "message": "Print String writes to the screen; log only (bPrintToScreen=false) behind the debug switch"})
                if values.get("bPrintToLog", "true").lower() == "true":
                    logs += 1
    if not logs:
        findings.append({"graph": "", "rule": "no_logging", "severity": "info",
                         "message": "no log output; state changes and failure branches should log with a [BP][module ID] prefix"})
    return findings


def lint_annotations(snapshot: dict[str, Any], comments: list[dict[str, Any]],
                     categories: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    by_graph: dict[str, list[dict[str, Any]]] = {}
    for comment in comments:
        by_graph.setdefault(comment["graph"], []).append(comment)
    for graph in snapshot["graphs"]:
        gname = ref_path(graph["graph"]).rsplit(":", 1)[-1]
        nodes = {node_name(ref_path(node["node"])): node for node in graph["nodes"]}
        frames = by_graph.get(gname, [])
        framed = {member for frame in frames for member in frame.get("members", [])}
        is_function = any(name.startswith("K2Node_FunctionEntry") for name in nodes) and gname != "UserConstructionScript"
        if gname == "UserConstructionScript" and len(nodes) <= 1:
            continue
        if is_function and not any(CJK.search(frame.get("text", "")) for frame in frames):
            findings.append({"graph": gname, "rule": "function_without_description", "severity": "warning",
                             "message": "function has no Chinese description frame (purpose, inputs, outputs, side effects, caller)"})
        for name, node in nodes.items():
            if name.startswith(ENTRY_TYPES) and name not in framed and not is_function:
                findings.append({"graph": gname, "rule": "entry_without_frame", "severity": "warning", "nodes": [name],
                                 "message": f"entry {short_title(node['type_id'])} is not inside a Chinese module frame"})
        for frame in frames:
            text = frame.get("text", "")
            title = text.splitlines()[0] if text else ""
            if not CJK.search(text):
                findings.append({"graph": gname, "rule": "frame_not_chinese", "severity": "warning",
                                 "message": f"comment frame without Chinese text: {title[:60]!r}"})
            elif not MODULE_ID.search(text):
                findings.append({"graph": gname, "rule": "frame_without_module_id", "severity": "info",
                                 "message": f"frame has no searchable module ID (e.g. BP.Throw.Release): {title[:60]!r}"})
            if len(title) > 48:
                findings.append({"graph": gname, "rule": "frame_title_too_long", "severity": "info",
                                 "message": f"{len(title)}-character title wraps and can overlap; keep the title short and "
                                            "move details to the frame's details text"})
        boxes = []
        for frame in frames:
            points = [nodes[m]["position"] for m in frame.get("members", []) if m in nodes]
            if points:
                boxes.append((frame.get("text", "")[:40], min(p["x"] for p in points), min(p["y"] for p in points),
                              max(p["x"] for p in points) + 260, max(p["y"] for p in points) + 120))
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a[3], b[3]) > max(a[1], b[1]) and min(a[4], b[4]) > max(a[2], b[2]):
                    findings.append({"graph": gname, "rule": "frame_overlap", "severity": "warning",
                                     "message": f"comment frames overlap: {a[0]!r} and {b[0]!r}"})
    for variable, category in categories.items():
        if category in ("", "Default", "默认"):
            findings.append({"graph": "", "rule": "variable_without_category", "severity": "warning", "nodes": [variable],
                             "message": f"variable {variable} has no Chinese category group"})
    return findings


def lint(snapshot: dict[str, Any], *, comments: list[dict[str, Any]] | None = None,
         categories: dict[str, str] | None = None, exec_types: set[str] | None = None) -> dict[str, Any]:
    exec_types = exec_types or EXEC_TYPES
    analysis = analyze_snapshot(snapshot, exec_types)
    findings = lint_layout(snapshot, analysis, exec_types) + lint_debug_and_logging(snapshot)
    if comments is not None:
        findings += lint_annotations(snapshot, comments, categories or {})
    counts = {level: sum(1 for item in findings if item["severity"] == level) for level in ("warning", "info")}
    return {
        "tool": "blueprint_lint",
        "schema_version": SCHEMA_VERSION,
        "blueprint": ref_path(snapshot["blueprint"]),
        "checked": {"layout": True, "debug_and_logging": True, "annotations": comments is not None},
        "summary": {**counts, "graphs": len(snapshot["graphs"])},
        "findings": findings,
        "passed": counts["warning"] == 0,
    }


COMMENT_SCRIPT = r"""
import json, unreal

def _codex_comment_frames():
    lib = unreal.BlueprintEditorLibrary
    bp = unreal.load_asset(__ASSET__)
    rows = []
    for name in lib.list_graph_names(bp):
        editor = unreal.BlueprintGraphEditor.get_graph_editor(lib.find_graph(bp, name))
        for node in editor.list_comment_nodes():
            rows.append({"graph": str(name), "text": lib.get_comment_text(node),
                         "members": [member.get_name() for member in lib.get_nodes_in_comment(node)]})
    print("CODEX_COMMENTS " + json.dumps(rows, ensure_ascii=False))

_codex_comment_frames()
"""


def read_comments(asset: str, project: str | None) -> list[dict[str, Any]]:
    """Comment frames are not in the MCP graph model; read them with stock editor Python (read-only)."""
    script = COMMENT_SCRIPT.replace("__ASSET__", json.dumps(asset.split(".")[0]))
    command = [sys.executable, str(_HERE / "python_remote.py")]
    if project:
        command += ["--project", project]
    proc = subprocess.run([*command, "exec", "--code", script], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
    for row in payload.get("output") or []:
        text = str(row.get("output", ""))
        if text.startswith("CODEX_COMMENTS "):
            return json.loads(text[len("CODEX_COMMENTS "):])
    raise RuntimeError(f"comment frame read failed: {(payload.get('result') or proc.stderr or proc.stdout)[:400]}")


def read_categories(asset: str, variables: list[str]) -> dict[str, str]:
    from ue_mcp import unwrap_result
    from ue_mcp.skill_api import connect

    client = connect()
    try:
        blueprint = {"refPath": asset if "." in asset.rsplit("/", 1)[-1] else f"{asset}.{asset.rsplit('/', 1)[-1]}"}
        return {name: str(unwrap_result(client.call_resolved_tool("BlueprintTools", "get_variable_category",
                                                                   {"blueprint": blueprint, "variable_name": name})) or "")
                for name in variables}
    finally:
        client.close()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Blueprint lint: {report['blueprint']}", "",
             f"- Passed: **{report['passed']}** (warnings {report['summary']['warning']}, info {report['summary']['info']})",
             f"- Checked: {', '.join(key for key, on in report['checked'].items() if on)}", ""]
    for finding in report["findings"]:
        lines.append(f"- [{finding['severity']}] `{finding['graph'] or 'asset'}` {finding['rule']}: {finding['message']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blueprint")
    parser.add_argument("--out", type=Path, required=True, help="Output directory (inspection plus lint.json/lint.md)")
    parser.add_argument("--inspect-dir", type=Path, help="Reuse an inspect_blueprint.py output instead of capturing")
    parser.add_argument("--no-comments", action="store_true", help="Skip the comment-frame and category checks")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any warning remains")
    args = parser.parse_args(argv)
    inspect_dir = args.inspect_dir or args.out / "inspect"
    if not args.inspect_dir:
        proc = subprocess.run([sys.executable, str(_HERE / "inspect_blueprint.py"), args.blueprint, "--out", str(inspect_dir)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode:
            print(proc.stdout + proc.stderr, file=sys.stderr)
            return 2
    snapshot = json.loads((inspect_dir / "snapshot.json").read_text(encoding="utf-8"))
    comments = categories = None
    if not args.no_comments:
        comments = read_comments(args.blueprint, args.project)
        categories = read_categories(args.blueprint, list(snapshot.get("variables") or []))
    report = lint(snapshot, comments=comments, categories=categories)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "lint.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "lint.md").write_text(render_markdown(report), encoding="utf-8")
    print(args.out / "lint.json")
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
