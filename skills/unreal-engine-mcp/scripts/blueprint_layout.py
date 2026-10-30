#!/usr/bin/env python3
"""Left-to-right layout for authored Blueprint graphs.

Each event or function reads as one execution lane. Every exec node gets the data (pure)
nodes that feed it as a small tree in columns directly to its left, below the exec wire,
so data wires run left-to-right into the pin they feed. The lane continues to the right
(a loop continues from Completed); loop bodies, else branches and other extra exec outputs
become rows dropped just below everything already placed above them. Event modules stack
vertically. Sizes come from blueprint_geometry estimates, which lean large.

    python scripts/blueprint_layout.py /Game/Path/BP_Feature --graph EventGraph --graph UpdatePreview
    python scripts/blueprint_layout.py /Game/Path/BP_Feature --all --write --reframe

Without --write it only prints the plan. --write moves nodes with BlueprintTools.set_node_position
(nothing is compiled or saved). --reframe then rebuilds each comment frame around the module
that holds most of its members, keeping its text, details, color and font size. Lay out only
graphs you authored; never re-layout a user's hand-arranged graph without asking.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from blueprint_geometry import estimate_size, has_exec, is_exec_pin, node_path, pin_offset, segment_hits_box  # noqa: E402

SCHEMA_VERSION = "blueprint_layout/1"
EXEC_GAP = 96        # after an exec node, before the next data tree or exec node
COLUMN_GAP = 56      # between data-tree columns and before the consumer
STACK_GAP = 24       # between data nodes stacked in one column
EXEC_CLEAR = 72      # data nodes start this far below their consumer's top; the exec wire runs above
BRANCH_GAP = 64      # extra corridor before a branch row so its drop wire clears the next data tree
LANE_GAP = 96        # between a branch row and whatever sits above it
MODULE_GAP = 240     # between event modules
GRID = 16
CONTINUE_PINS = ("Completed", "then", "Then", "True")
REPAIR_ROUNDS = 4
HEADER_PIN = 50      # typical height of an exec input pin; EXEC_CLEAR is measured from it


def short(path: str) -> str:
    return path.rsplit(".", 1)[-1]


class Planner:
    def __init__(self, infos: list[dict[str, Any]]):
        self.nodes = {node_path(n): n for n in infos}
        self.size = {p: estimate_size(n) for p, n in self.nodes.items()}
        self.execs = {p for p, n in self.nodes.items() if has_exec(n)}
        self.claimed: set[str] = set()
        self.placed_exec: set[str] = set()

    def source_pin_name(self, link: dict[str, Any]) -> str:
        source = self.nodes[link["node"]["refPath"]]
        for pin in source["output_pins"]:
            if pin["pin_id"].get("index_id") == link.get("index_id"):
                return pin["name"]
        return source["output_pins"][0]["name"] if source["output_pins"] else ""

    def data_inputs(self, path: str):
        for pin in self.nodes[path]["input_pins"]:
            if is_exec_pin(pin):
                continue
            for link in pin["connected_pins"]:
                source = link["node"]["refPath"]
                if source in self.nodes:
                    yield pin["name"], source, self.source_pin_name(link)

    def exec_outputs(self, path: str) -> list[tuple[str, list[str]]]:
        return [(pin["name"], [l["node"]["refPath"] for l in pin["connected_pins"] if l["node"]["refPath"] in self.nodes])
                for pin in self.nodes[path]["output_pins"] if is_exec_pin(pin)]

    def entries(self, order: dict[str, int] | None) -> list[str]:
        found = [p for p in self.execs
                 if not any(is_exec_pin(pin) and pin["connected_pins"] for pin in self.nodes[p]["input_pins"])]
        order = order or {}
        pos = lambda p: self.nodes[p].get("position") or {"x": 0, "y": 0}  # noqa: E731
        return sorted(found, key=lambda p: (order.get(short(p), 1e9), pos(p)["y"], pos(p)["x"]))

    # -- data trees ------------------------------------------------------------------
    def claim_tree(self, consumer: str) -> dict[str, int]:
        """Unclaimed pure nodes feeding consumer (transitively), with their column (1 = next to it)."""
        members: list[str] = []
        frontier = [consumer]
        while frontier:
            current = frontier.pop(0)
            for _, source, _ in self.data_inputs(current):
                if source in self.execs or source in self.claimed:
                    continue
                self.claimed.add(source)
                members.append(source)
                frontier.append(source)
        column = {consumer: 0}
        for _ in range(len(members) + 1):  # longest path from the consumer; data graphs are acyclic
            changed = False
            for path in [consumer, *members]:
                if path not in column:
                    continue
                for _, source, _ in self.data_inputs(path):
                    if source in members and column.get(source, 0) < column[path] + 1:
                        column[source] = column[path] + 1
                        changed = True
            if not changed:
                break
        column.pop(consumer)
        return column

    def place_tree(self, consumer: str, column: dict[str, int], rects: dict[str, list[float]], top: float) -> None:
        """Columns right-aligned toward the consumer; each node aims its output at the pin it feeds, not above top."""
        cx = rects[consumer][0]
        widths = {}
        for path, col in column.items():
            widths[col] = max(widths.get(col, 0.0), self.size[path][0])
        right = cx - COLUMN_GAP
        for col in sorted(widths):
            members = [p for p, c in column.items() if c == col]
            wanted = {}
            for path in members:
                targets = []
                for placed, box in rects.items():
                    for pin, source, source_pin in self.data_inputs(placed):
                        if source == path:
                            targets.append(box[1] + pin_offset(self.nodes[placed], pin, False)
                                           - pin_offset(self.nodes[path], source_pin, True))
                wanted[path] = min(targets) if targets else EXEC_CLEAR
            bottom = None
            for path in sorted(members, key=lambda p: (wanted[p], short(p))):
                y = max(wanted[path], rects[consumer][1] + top)
                if bottom is not None:
                    y = max(y, bottom + STACK_GAP)
                w, h = self.size[path]
                rects[path] = [right - w, y, w, h]
                bottom = y + h
            right -= widths[col] + COLUMN_GAP

    # -- exec blocks -----------------------------------------------------------------
    def build(self, path: str, incoming: float = 0.0) -> dict[str, list[float]]:
        """Block for path and everything it executes, relative to the block's left edge and top.

        incoming is the height of the exec pin that leads here on the same row; the data tree stays
        below it so the exec wire does not cut through the tree.
        """
        self.placed_exec.add(path)
        column = self.claim_tree(path)
        widths: dict[int, float] = {}
        for node, col in column.items():
            widths[col] = max(widths.get(col, 0.0), self.size[node][0])
        tree_width = sum(widths.values()) + COLUMN_GAP * len(widths)
        w, h = self.size[path]
        rects: dict[str, list[float]] = {path: [tree_width, 0.0, w, h]}
        self.place_tree(path, column, rects, max(EXEC_CLEAR, incoming + EXEC_CLEAR - HEADER_PIN))
        next_x = tree_width + w + EXEC_GAP
        outputs = [(name, targets) for name, targets in self.exec_outputs(path) if targets]
        outputs.sort(key=lambda item: 0 if item[0] == "Completed" else 1)  # a loop's lane continues from Completed
        main = next((item for item in outputs if item[0] in CONTINUE_PINS), outputs[0] if outputs else None)
        for item in ([main] if main else []) + [item for item in outputs if item is not main]:
            for target in item[1]:
                if target in self.placed_exec:
                    continue
                on_row = item is main and target == item[1][0]
                block = self.build(target, pin_offset(self.nodes[path], item[0], True) if on_row else 0.0)
                if on_row:
                    self.merge(rects, block, next_x, 0.0)
                else:
                    x = next_x + BRANCH_GAP
                    self.merge(rects, block, x, self.drop(rects, block, x, h + LANE_GAP))
        return rects

    # -- repair -----------------------------------------------------------------------
    def wires(self, rects: dict[str, list[float]]):
        """(start, end, source, target) for every wire between placed nodes."""
        for target, box in rects.items():
            for pin in self.nodes[target]["input_pins"]:
                for link in pin["connected_pins"]:
                    source = link["node"]["refPath"]
                    if source in rects:
                        sbox = rects[source]
                        start = (sbox[0] + sbox[2], sbox[1] + pin_offset(self.nodes[source], self.source_pin_name(link), True))
                        yield start, (box[0], box[1] + pin_offset(self.nodes[target], pin["name"], False)), source, target

    def repair(self, rects: dict[str, list[float]]) -> int:
        """Move data nodes down until wires from other nodes clear them; skip a move that would overlap."""
        moved = 0
        for _ in range(REPAIR_ROUNDS):
            changed = False
            for start, end, source, target in list(self.wires(rects)):
                for path, box in rects.items():
                    if path in (source, target) or path in self.execs or not segment_hits_box(start, end, box):
                        continue
                    line = lambda x: start[1] + (end[1] - start[1]) * (x - start[0]) / ((end[0] - start[0]) or 1)  # noqa: E731
                    y = max(line(box[0]), line(box[0] + box[2])) + STACK_GAP
                    candidate = [box[0], y, box[2], box[3]]
                    clear = all(other == path or not (candidate[0] < o[0] + o[2] + STACK_GAP and o[0] < candidate[0] + candidate[2] + STACK_GAP
                                                      and candidate[1] < o[1] + o[3] + STACK_GAP and o[1] < candidate[1] + candidate[3] + STACK_GAP)
                                for other, o in rects.items())
                    if clear and not any(segment_hits_box(a, b, candidate) for a, b, s, t in self.wires(rects) if path not in (s, t)):
                        rects[path] = candidate
                        moved += 1
                        changed = True
            if not changed:
                break
        return moved

    @staticmethod
    def drop(rects: dict[str, list[float]], block: dict[str, list[float]], x: float, minimum: float) -> float:
        """Smallest y offset at which block (placed at x) clears every rect already placed."""
        dy = minimum
        for bx, by, bw, bh in block.values():
            for ex, ey, ew, eh in rects.values():
                if bx + x < ex + ew + COLUMN_GAP and ex < bx + x + bw + COLUMN_GAP:
                    dy = max(dy, ey + eh + LANE_GAP - by)
        return dy

    @staticmethod
    def merge(rects: dict[str, list[float]], block: dict[str, list[float]], x: float, y: float) -> None:
        for path, (bx, by, bw, bh) in block.items():
            rects[path] = [bx + x, by + y, bw, bh]


def plan_layout(infos: list[dict[str, Any]], entry_order: dict[str, int] | None = None) -> dict[str, Any]:
    """Return {"positions": {path: [x, y]}, "modules": {entry path: [paths]}, "leftovers": [paths]}."""
    planner = Planner(infos)
    positions: dict[str, list[int]] = {}
    modules: dict[str, list[str]] = {}
    cursor = 0.0
    for entry in planner.entries(entry_order):
        if entry in planner.placed_exec:
            continue
        block = planner.build(entry)
        planner.repair(block)
        left = min(r[0] for r in block.values())
        for path, (x, y, _, _) in block.items():
            positions[path] = [int(round((x - left) / GRID) * GRID), int(round((y + cursor) / GRID) * GRID)]
        modules[entry] = list(block)
        cursor += max(r[1] + r[3] for r in block.values()) + MODULE_GAP
    leftovers = [p for p in planner.nodes if p not in positions]
    x = 0.0
    for path in leftovers:
        positions[path] = [int(round(x / GRID) * GRID), int(round(cursor / GRID) * GRID)]
        x += planner.size[path][0] + EXEC_GAP
    return {"positions": positions, "modules": modules, "leftovers": leftovers}


# -- editor side -----------------------------------------------------------------------
REFRAME_SCRIPT = r"""
import json, unreal
def _codex_reframe():
    lib, ge = unreal.BlueprintEditorLibrary, unreal.BlueprintGraphEditor
    bp = unreal.load_asset(__ASSET__)
    editor = ge.get_graph_editor(lib.find_graph(bp, __GRAPH__))
    modules = json.loads(__MODULES__)        # [[entry name, [node names]], ...]
    frame_map = json.loads(__FRAMEMAP__)     # entry name -> text found in that module's frame title
    by_name = {n.get_name(): n for n in editor.list_all_nodes() if not isinstance(n, unreal.EdGraphNode_Comment)}
    done = []
    frames = list(editor.list_comment_nodes())
    for frame in frames:
        text = str(lib.get_comment_text(frame))
        members = {m.get_name() for m in lib.get_nodes_in_comment(frame)}
        best = max(modules, key=lambda m: len(members & set(m[1])), default=None)
        if not members:
            # Membership is only computed once the graph is shown in the editor UI (and is lost on
            # duplicates): fall back to the frame map, or to the only frame and module of a graph.
            mapped = [m for m in modules if frame_map.get(m[0]) and frame_map[m[0]] in text]
            if len(mapped) == 1:
                best = mapped[0]
            elif len(frames) == 1 and len(modules) == 1:
                best = modules[0]
            members = set(best[1]) if best and (mapped or len(modules) == 1) else set()
        if not best or not members & set(best[1]):
            done.append({"text": text, "status": "unmapped"})
            continue
        spec = {"text": text, "details": frame.get_editor_property("node_details"),
                "font": frame.get_editor_property("font_size"), "color": frame.get_editor_property("comment_color")}
        editor.remove_comment_node(frame)
        new = editor.add_comment_to_nodes(spec["text"], [by_name[n] for n in best[1] if n in by_name], 60)
        new.set_editor_property("node_details", spec["details"])
        new.set_editor_property("font_size", spec["font"])
        new.set_editor_property("comment_color", spec["color"])
        modules = [m for m in modules if m is not best]
        done.append({"text": spec["text"], "status": "reframed", "members": len(best[1])})
    print("CODEX_REFRAME " + json.dumps(done, ensure_ascii=False))
_codex_reframe()
"""


def reframe(asset: str, graph: str, modules: dict[str, list[str]], project: str | None,
            frame_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Rebuild comment frames around the moved modules (stock BlueprintGraphEditor over Remote Execution)."""
    names = [[short(entry), [short(p) for p in paths]] for entry, paths in modules.items()]
    script = (REFRAME_SCRIPT.replace("__ASSET__", json.dumps(asset.split(".")[0])).replace("__GRAPH__", json.dumps(graph))
              .replace("__MODULES__", repr(json.dumps(names)))
              .replace("__FRAMEMAP__", repr(json.dumps(frame_map or {}, ensure_ascii=False))))
    command = [sys.executable, str(_HERE / "python_remote.py")] + (["--project", project] if project else [])
    proc = subprocess.run([*command, "exec", "--code", script], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
    for row in payload.get("output") or []:
        text = str(row.get("output", ""))
        if text.startswith("CODEX_REFRAME "):
            return json.loads(text[len("CODEX_REFRAME "):])
    raise RuntimeError(f"reframe failed: {(payload.get('result') or proc.stderr or proc.stdout)[:400]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blueprint")
    parser.add_argument("--graph", action="append", default=[], help="Graph to lay out (repeatable)")
    parser.add_argument("--all", action="store_true", help="Every graph of the Blueprint")
    parser.add_argument("--entry-order", default="", help="Comma-separated entry node names, top module first")
    parser.add_argument("--write", action="store_true", help="Move the nodes (default: print the plan only)")
    parser.add_argument("--reframe", action="store_true", help="With --write, rebuild comment frames around modules")
    parser.add_argument("--frame-map", default="",
                        help="Entry=text pairs (K2Node_Event_0=BP.Feature.Init,...) matching a module's entry to text in its "
                             "frame title; used when frame membership is empty (graph not yet shown in the editor UI)")
    parser.add_argument("--out", type=Path, help="Write the plan JSON here")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    args = parser.parse_args(argv)

    from ue_mcp import unwrap_result
    from ue_mcp.skill_api import connect

    asset = args.blueprint if "." in args.blueprint.rsplit("/", 1)[-1] else f"{args.blueprint}.{args.blueprint.rsplit('/', 1)[-1]}"
    client = connect()
    call = lambda tool, **kw: unwrap_result(client.call_resolved_tool("BlueprintTools", tool, kw))  # noqa: E731
    order = {name: i for i, name in enumerate(filter(None, args.entry_order.split(",")))}
    frame_map = dict(pair.split("=", 1) for pair in filter(None, args.frame_map.split(",")))
    report: dict[str, Any] = {"tool": "blueprint_layout", "schema_version": SCHEMA_VERSION, "blueprint": asset, "graphs": {}}
    try:
        names = args.graph
        if args.all:
            names = [g["refPath"].rsplit(":", 1)[-1] if isinstance(g, dict) else str(g)
                     for g in call("list_graphs", blueprint={"refPath": asset})]
        for name in names:
            graph = call("get_graph", blueprint={"refPath": asset}, graph_name=name)
            found = call("find_nodes", graph=graph, title="")
            infos = call("get_node_infos", nodes=found) if found else []
            plan = plan_layout(infos, order)
            moved = 0
            if args.write:
                for info in infos:
                    x, y = plan["positions"][node_path(info)]
                    if [info["position"]["x"], info["position"]["y"]] != [x, y]:
                        call("set_node_position", node=info["node"], pos={"x": x, "y": y})
                        moved += 1
            entry = {"nodes": len(infos), "moved": moved, "modules": {short(k): len(v) for k, v in plan["modules"].items()},
                     "leftovers": [short(p) for p in plan["leftovers"]], "plan": plan}
            if args.write and args.reframe:
                entry["frames"] = reframe(asset, name, plan["modules"], args.project, frame_map)
            report["graphs"][name] = entry
    finally:
        client.close()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    summary = {name: {k: v for k, v in g.items() if k != "plan"} for name, g in report["graphs"].items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
