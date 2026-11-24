#!/usr/bin/env python3
"""Scoped wiring cleanup for authored Blueprint graphs; report first, then opt in to --write.

Only supported pure call/operator nodes are copied, retaining every input and Target link.
Variable getters and SET outputs are reported and left intact: the MCP node info does not prove
their member owner/local scope, so recreating them by name is unsafe. Read back and compile a
candidate asset before promoting it; this tool does not prove runtime equivalence.

An exec node's output read past the next exec node is reported, not changed: store it in a
local variable right after the producer (function graphs) and read it with getters.

    python scripts/blueprint_normalize.py /Game/Path/BP_Feature --graph UpdatePreview            # report
    python scripts/blueprint_normalize.py /Game/Path/BP_Feature --all --write --project MyGame    # apply

--write edits the graph (nothing is compiled or saved); back the asset up first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from blueprint_geometry import has_exec, is_exec_pin, node_kind, node_path  # noqa: E402

SCHEMA_VERSION = "blueprint_normalize/1"


def short(path: str) -> str:
    return path.rsplit(".", 1)[-1]


def set_output_links(infos: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    """(SET node, its value output pin, variable name) for SET outputs that are wired onward."""
    found = []
    for info in infos:
        if node_kind(info) != "K2Node_VariableSet":
            continue
        out = next((p for p in info["output_pins"] if not is_exec_pin(p) and p["connected_pins"]), None)
        if out:
            found.append((info, out, next(p["name"] for p in info["input_pins"] if not is_exec_pin(p))))
    return found


def owners_of(infos: list[dict[str, Any]]):
    """Return (nodes by path, owners(path)): the exec nodes a pure node ultimately feeds."""
    by_path = {node_path(i): i for i in infos}
    memo: dict[str, set[str]] = {}

    def owners(path: str) -> set[str]:
        if path not in memo:
            memo[path] = set()
            found: set[str] = set()
            for pin in by_path[path]["output_pins"]:
                for link in pin["connected_pins"]:
                    consumer = link["node"]["refPath"]
                    if consumer in by_path:
                        found |= {consumer} if has_exec(by_path[consumer]) else owners(consumer)
            memo[path] = found
        return memo[path]

    return by_path, owners


def next_shared_pure(infos: list[dict[str, Any]], skip: set[str] | None = None) -> tuple[str, dict[str, list[tuple[str, dict, dict]]]] | None:
    """The next pure node to split (all its pure consumers already single-owner) and its links per owner."""
    by_path, owners = owners_of(infos)
    for path, info in by_path.items():
        if path in (skip or set()) or has_exec(info) or len(owners(path)) < 2:
            continue
        consumers = {l["node"]["refPath"] for p in info["output_pins"] for l in p["connected_pins"]} & set(by_path)
        if not all(has_exec(by_path[c]) or len(owners(c)) == 1 for c in consumers):
            continue
        groups: dict[str, list[tuple[str, dict, dict]]] = {}
        for pin in info["output_pins"]:
            for link in pin["connected_pins"]:
                consumer = link["node"]["refPath"]
                if consumer in by_path:
                    owner = consumer if has_exec(by_path[consumer]) else next(iter(owners(consumer)))
                    groups.setdefault(owner, []).append((pin["name"], pin["pin_id"], link))
        return path, groups
    return None


def exec_output_skips(infos: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Exec-node data outputs read by a node other than the next exec node in the chain (report only)."""
    by_path, owners = owners_of(infos)
    found = []
    for path, info in by_path.items():
        if not has_exec(info):
            continue
        following = {l["node"]["refPath"] for p in info["output_pins"] if is_exec_pin(p) for l in p["connected_pins"]}
        for pin in info["output_pins"]:
            if is_exec_pin(pin):
                continue
            for link in pin["connected_pins"]:
                consumer = link["node"]["refPath"]
                if consumer not in by_path:
                    continue
                targets = {consumer} if has_exec(by_path[consumer]) else owners(consumer)
                if targets - following:
                    found.append({"node": short(path), "pin": pin["name"], "read_by": ", ".join(sorted(short(t) for t in targets - following))})
    return found


def copy_gap(info: dict[str, Any]) -> str | None:
    if node_kind(info) not in {"K2Node_CallFunction", "K2Node_PromotableOperator"}:
        return "Member owner/local scope or node reconstruction is not proven; preserve the original node."
    if any(len(p.get("connected_pins", [])) > 1 for p in info["input_pins"]):
        return "Multiple sources on an input are outside the supported clone contract."
    return None


class Editor:
    def __init__(self, asset: str, project: str | None):
        from ue_mcp import unwrap_result
        from ue_mcp.skill_api import connect

        self.asset, self.project = asset, project
        self.client = connect(project=project)
        self._unwrap = unwrap_result

    def bt(self, tool: str, **args: Any) -> Any:
        return self._unwrap(self.client.call_resolved_tool("BlueprintTools", tool, args))

    def infos(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        found = self.bt("find_nodes", graph=graph, title="")
        return self.bt("get_node_infos", nodes=found) if found else []

    def node(self, graph: dict[str, Any], name: str) -> dict[str, Any]:
        return next(i for i in self.infos(graph) if short(node_path(i)) == name)

    def rewire(self, out_pin: dict, link: dict, new_out: dict) -> None:
        try:
            self.bt("break_pins", output_pin=out_pin, input_pin=link)
            self.bt("connect_pins", output_pin=new_out, input_pin=link)
            target = self.bt("get_node_infos", nodes=[link["node"]])[0]
            pin = next(p for p in target["input_pins"] if p["pin_id"] == link)
            if pin["connected_pins"] != [new_out]:
                raise RuntimeError("Rewire was not confirmed by input-pin readback")
        except Exception:
            # A timeout is unknown completion. Inspect before repairing only a missing old edge.
            target = self.bt("get_node_infos", nodes=[link["node"]])[0]
            pin = next(p for p in target["input_pins"] if p["pin_id"] == link)
            if new_out in pin["connected_pins"]:
                return
            if not pin["connected_pins"]:
                self.bt("connect_pins", output_pin=out_pin, input_pin=link)
            raise

    def copy_node(self, graph_name: str, graph: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
        gap = copy_gap(info)
        if gap:
            raise RuntimeError(gap)
        pos = {"x": info["position"]["x"], "y": info["position"]["y"] + 40}
        copy = self.bt("get_node_infos", nodes=[self.bt("create_node", graph=graph, type_id=info["type_id"], pos=pos)])[0]
        try:
            for side in ("input_pins", "output_pins"):
                if [(p["name"], p["type_id"]) for p in copy[side]] != [(p["name"], p["type_id"]) for p in info[side]]:
                    raise RuntimeError("Clone pin schema differs")
            for pin, target in zip(info["input_pins"], copy["input_pins"]):
                for link in pin["connected_pins"]:
                    self.bt("connect_pins", output_pin=link, input_pin=target["pin_id"])
                if not pin["connected_pins"] and pin.get("value") is not None and not is_exec_pin(pin) and pin["value"] != target.get("value"):
                    self.bt("set_pin_value", pin=target["pin_id"], value=pin["value"])
            result = self.bt("get_node_infos", nodes=[copy["node"]])[0]
            for pin, target in zip(info["input_pins"], result["input_pins"]):
                if target["connected_pins"] != pin["connected_pins"]:
                    raise RuntimeError("Clone input/Target links were not confirmed")
                if not pin["connected_pins"] and pin.get("value") != target.get("value"):
                    raise RuntimeError("Clone input default was not confirmed")
            return result
        except Exception:
            # No original output has been moved yet; removing this confirmed new node is safe.
            self.bt("delete_node", node=copy["node"])
            raise


def normalize_graph(editor: Editor, graph_name: str, write: bool, limit: int = 100) -> dict[str, Any]:
    graph = editor.bt("get_graph", blueprint={"refPath": editor.asset}, graph_name=graph_name)
    infos = editor.infos(graph)
    report: dict[str, Any] = {"set_outputs": [f"{short(node_path(i))}->{len(o['connected_pins'])}" for i, o, _ in set_output_links(infos)],
                              "getters_added": 0, "pure_copies": 0, "skipped": []}
    for info, _, _ in set_output_links(infos):
        report["skipped"].append({"node": node_path(info), "reason": "SET output preserved: variable owner/Target/local scope is unverified."})
    if write:
        from ue_mcp.skill_api import ensure_editor_idle
        ensure_editor_idle(editor.client)
        skipped: set[str] = set()
        for _ in range(limit):
            infos = editor.infos(graph)
            found = next_shared_pure(infos, skipped)
            if not found:
                break
            path, groups = found
            info = next(i for i in infos if node_path(i) == path)
            gap = copy_gap(info)
            if gap:
                skipped.add(path)
                report["skipped"].append({"node": path, "reason": gap})
                continue
            keep = min(groups, key=lambda o: (next(i for i in infos if node_path(i) == o)["position"]["x"], o))
            for owner, links in groups.items():
                if owner == keep:
                    continue
                copy = editor.copy_node(graph_name, graph, info)
                for pin_name, pin_id, link in links:
                    editor.rewire(pin_id, link, next(p for p in copy["output_pins"] if p["name"] == pin_name)["pin_id"])
                report["pure_copies"] += 1
        else:
            raise RuntimeError(f"{graph_name}: shared pure nodes did not converge")
    else:
        found = next_shared_pure(infos)
        report["next_shared_pure"] = short(found[0]) if found else None
    report["exec_output_skips"] = exec_output_skips(editor.infos(graph) if write else infos)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blueprint")
    parser.add_argument("--graph", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--write", action="store_true", help="Apply the edits (default: report only)")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    args = parser.parse_args(argv)
    if bool(args.graph) == args.all:
        parser.error("choose --graph (repeatable) or --all explicitly")
    if args.write and not args.project:
        parser.error("--write requires --project or UE_MCP_PROJECT")
    asset = args.blueprint if "." in args.blueprint.rsplit("/", 1)[-1] else f"{args.blueprint}.{args.blueprint.rsplit('/', 1)[-1]}"
    editor = Editor(asset, args.project)
    try:
        names = args.graph or [g["refPath"].rsplit(":", 1)[-1] for g in editor.bt("list_graphs", blueprint={"refPath": asset})]
        report = {"tool": "blueprint_normalize", "schema_version": SCHEMA_VERSION, "blueprint": asset, "write": args.write,
                  "graphs": {name: normalize_graph(editor, name, args.write) for name in names}}
    finally:
        editor.client.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
