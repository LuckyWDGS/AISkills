"""Read Blueprint node/pin topology using Epic MCP; never compile, save or edit."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import os

from builtin_mcp import (
    DEFAULT_PROTOCOL, DEFAULT_URL, McpError, UnrealMcpClient, _decode_text_value, default_cache_dir,
    default_session_dir,
)


INPUT, OUTPUT = "EGPD_Input", "EGPD_Output"
EXEC_TYPES = {"Exec", "执行"}
COVERAGE = (
    "Only nodes and pins returned by Epic's Blueprint APIs are covered. "
    "Some UEdGraphNode subclasses (including animation state-machine topology) "
    "are omitted in tested UE 5.8.4. Empty results do not prove an empty graph. "
    "Connections are logical endpoints, not UI wire curves or runtime traces. "
    "Capture uses multiple reads, not an atomic editor transaction."
)
READ_CALLS = {
    ("EditorAppToolset", "IsPIERunning"),
    ("AssetTools", "is_dirty"),
    *(('BlueprintTools', name) for name in (
        "get_parent", "list_variables", "list_event_dispatchers", "list_graphs",
        "find_nodes", "get_node_infos",
    )),
}


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def asset_paths(value: str) -> tuple[str, str]:
    """Accept an absolute package or Blueprint object path, never a generated class."""
    if not value.startswith("/") or ":" in value or "\\" in value or "'" in value:
        raise ValueError("Use an absolute package or object path, not export-text syntax or a graph ref")
    package, sep, obj = value.partition(".")
    if not package.rsplit("/", 1)[-1] or (sep and (not obj or "." in obj or "/" in obj)):
        raise ValueError("Invalid Blueprint asset path")
    obj = obj if sep else package.rsplit("/", 1)[-1]
    if obj.endswith("_C"):
        raise ValueError("Pass the Blueprint asset, not its generated _C class")
    return package, f"{package}.{obj}"


def ref_path(ref: Any) -> str:
    if not isinstance(ref, dict) or not isinstance(ref.get("refPath"), str) or not ref["refPath"]:
        raise ValueError(f"Invalid UObject reference: {ref!r}")
    return ref["refPath"]


def pin_key(value: Any) -> tuple[str, str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid PinID: {value!r}")
    direction, index = value.get("direction"), value.get("index_id")
    if direction not in {INPUT, OUTPUT} or type(index) is not int or index < 0:
        raise ValueError(f"Invalid pin direction/index: {value!r}")
    return ref_path(value.get("node")), direction, index


def pin_ref(key: tuple[str, str, int]) -> dict:
    return {"node": {"refPath": key[0]}, "direction": key[1], "index_id": key[2]}


def analyze_snapshot(snapshot: dict, exec_types: set[str] | None = None) -> dict:
    """Derive input/output edge sets separately; retain unresolved links as evidence."""
    exec_types = EXEC_TYPES if exec_types is None else exec_types
    diagnostics, edges, summaries = [], [], []

    def issue(code: str, graph: str, **detail: Any) -> None:
        diagnostics.append({"code": code, "graph": graph, **detail})

    seen_graphs = set()
    for graph in snapshot["graphs"]:
        path = ref_path(graph["graph"])
        if path in seen_graphs:
            issue("duplicate_graph", path)
        seen_graphs.add(path)
        nodes, pins = {}, {}
        for node in graph["nodes"]:
            node_path = ref_path(node["node"])
            if node_path in nodes:
                issue("duplicate_node", path, node=node_path)
            nodes[node_path] = node
            for field, direction in (("input_pins", INPUT), ("output_pins", OUTPUT)):
                for pin in node[field]:
                    if (not isinstance(pin, dict) or not isinstance(pin.get("name"), str)
                            or not isinstance(pin.get("type_id"), str) or "value" not in pin):
                        raise ValueError(f"Pin metadata schema changed on {node_path}; inspect snapshot.json")
                    try:
                        key = pin_key(pin["pin_id"])
                    except (KeyError, ValueError) as exc:
                        issue("invalid_pin_id", path, node=node_path, error=str(exc))
                        continue
                    if key[0] != node_path or key[1] != direction:
                        issue("pin_owner_or_direction_mismatch", path, pin=pin_ref(key))
                    if key in pins:
                        issue("duplicate_pin_id", path, pin=pin_ref(key))
                    pins[key] = pin
        if "node_refs" in graph:
            queried = [ref_path(r) for r in graph["node_refs"]]
            if len(queried) != len(set(queried)):
                issue("duplicate_queried_node", path)
            if set(queried) != set(nodes):
                issue("node_readback_mismatch", path, missing=sorted(set(queried) - set(nodes)),
                      unexpected=sorted(set(nodes) - set(queried)))

        from_inputs, from_outputs = set(), set()
        for key, pin in pins.items():
            if not isinstance(pin["connected_pins"], list):
                raise ValueError(f"connected_pins is not a list: {key}")
            seen_links = set()
            for connected in pin["connected_pins"]:
                try:
                    other = pin_key(connected)
                except ValueError as exc:
                    issue("invalid_connected_pin", path, pin=pin_ref(key), error=str(exc))
                    continue
                if other in seen_links:
                    issue("duplicate_link", path, pin=pin_ref(key), other=connected)
                seen_links.add(other)
                if other[1] == key[1]:
                    issue("same_direction_link", path, pin=pin_ref(key), other=connected)
                    continue
                edge = (key, other) if key[1] == OUTPUT else (other, key)
                (from_outputs if key[1] == OUTPUT else from_inputs).add(edge)
                if other not in pins:
                    issue("missing_endpoint", path, pin=pin_ref(key), other=connected)

        graph_edges = []
        for source, target in sorted(from_outputs | from_inputs):
            both = (source, target) in from_outputs and (source, target) in from_inputs
            if not both:
                issue("one_sided_link", path, source=pin_ref(source), target=pin_ref(target),
                      observed_from="output" if (source, target) in from_outputs else "input")

            def endpoint(key: tuple[str, str, int]) -> dict:
                pin, node = pins.get(key, {}), nodes.get(key[0], {})
                return {"pin_id": pin_ref(key), "name": pin.get("name"),
                        "type_id": pin.get("type_id"), "node_type_id": node.get("type_id")}

            src, dst = endpoint(source), endpoint(target)
            src_exec, dst_exec = src["type_id"] in exec_types, dst["type_id"] in exec_types
            resolved = source in pins and target in pins
            kind = "unknown" if not resolved else "execution" if src_exec and dst_exec else "data"
            if resolved and src_exec != dst_exec:
                kind = "unknown"
                issue("execution_type_mismatch", path, source=src, target=dst)
            graph_edges.append({"graph": path, "source": src, "target": dst,
                                "kind": kind, "reciprocal": both, "resolved": resolved})
        summaries.append({"graph": path, "nodes": len(nodes), "pins": len(pins),
                          "wires": len(graph_edges),
                          "execution": sum(e["kind"] == "execution" for e in graph_edges),
                          "data": sum(e["kind"] == "data" for e in graph_edges),
                          "unknown": sum(e["kind"] == "unknown" for e in graph_edges),
                          "input_output_sets_equal": from_inputs == from_outputs})
        edges.extend(graph_edges)
    return {"coverage": COVERAGE, "exec_types": sorted(exec_types), "graphs": summaries,
            "totals": {k: sum(g[k] for g in summaries) for k in
                       ("nodes", "pins", "wires", "execution", "data", "unknown")},
            "valid_returned_topology": not diagnostics, "diagnostics": diagnostics, "edges": edges}


class ReadOnlyCapture:
    def __init__(self, client: UnrealMcpClient, out: Path):
        self.client, self.out, self.calls = client, out, []

    def read(self, toolset: str, tool: str, arguments: dict) -> Any:
        if (toolset, tool) not in READ_CALLS:
            raise ValueError(f"Operation is outside the read-only allowlist: {toolset}.{tool}")
        entry = {"toolset": toolset, "tool": tool, "arguments": arguments}
        self.calls.append(entry)
        try:
            entry["result"] = self.client.call_resolved_tool(toolset, tool, arguments)
            value = _decode_text_value(entry["result"])
            if not isinstance(value, dict) or "returnValue" not in value:
                raise McpError(f"Unexpected result schema for {toolset}.{tool}: {value!r}")
            return value["returnValue"]
        except Exception as exc:
            entry["error"] = str(exc)
            raise
        finally:
            save_json(self.out / "calls.json", self.calls)

    def outside_pie(self) -> None:
        value = self.read("EditorAppToolset", "IsPIERunning", {})
        if type(value) is not bool:
            raise McpError("IsPIERunning did not return a boolean")
        if value:
            raise McpError("PIE is running; inspection did not stop it or query package dirty state")

    def dirty(self, package: str) -> bool:
        self.outside_pie()
        value = self.read("AssetTools", "is_dirty", {"asset_path": package})
        if type(value) is not bool:
            raise McpError("is_dirty did not return a boolean")
        return value

    def snapshot(self, bp: dict, batch_size: int) -> dict:
        result = {"blueprint": bp, "graphs": []}
        for name, field in (("get_parent", "parent"), ("list_variables", "variables"),
                            ("list_event_dispatchers", "event_dispatchers")):
            result[field] = self.read("BlueprintTools", name, {"blueprint": bp})
        graphs = self.read("BlueprintTools", "list_graphs", {"blueprint": bp})
        if not isinstance(graphs, list):
            raise McpError("list_graphs did not return a list")
        for graph in graphs:
            ref_path(graph)
            refs = self.read("BlueprintTools", "find_nodes", {"graph": graph, "title": ""})
            if not isinstance(refs, list):
                raise McpError("find_nodes did not return a list")
            nodes = []
            for start in range(0, len(refs), batch_size):
                batch = self.read("BlueprintTools", "get_node_infos", {"nodes": refs[start:start + batch_size]})
                if not isinstance(batch, list):
                    raise McpError("get_node_infos did not return a list")
                nodes.extend(batch)
            result["graphs"].append({"graph": graph, "node_refs": refs, "nodes": nodes})
        return result


def snapshot_fingerprint(snapshot: dict) -> str:
    """Ignore collection order, retaining every value, duplicate, default and link."""
    def canonical(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in sorted(value.items())}
        if isinstance(value, list):
            return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
        return value
    return json.dumps(canonical(snapshot), ensure_ascii=False, sort_keys=True)


def write_outputs(out: Path, result: dict, analysis: dict | None) -> None:
    if analysis is not None:
        save_json(out / "connections.json", analysis)
        with (out / "connections.csv").open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["graph", "kind", "reciprocal", "resolved"]
            endpoint_fields = ["node", "node_type_id", "direction", "index_id", "name", "type_id"]
            writer = csv.DictWriter(f, fieldnames=fields + [f"{s}_{k}" for s in ("source", "target") for k in endpoint_fields])
            writer.writeheader()
            for edge in analysis["edges"]:
                row = {k: edge[k] for k in fields}
                for side in ("source", "target"):
                    ep = edge[side]
                    row.update({f"{side}_{k}": v for k, v in {
                        "node": ep["pin_id"]["node"]["refPath"], "node_type_id": ep["node_type_id"],
                        "direction": ep["pin_id"]["direction"], "index_id": ep["pin_id"]["index_id"],
                        "name": ep["name"], "type_id": ep["type_id"],
                    }.items()})
                writer.writerow(row)
    save_json(out / "result.json", result)
    lines = ["# Official MCP Blueprint inspection", "", f"Asset: `{result['blueprint']}`", "",
             f"Capture passed: **{result['passed']}**", "", COVERAGE, "",
             f"Dirty before/after: {result.get('dirty_before')} / {result.get('dirty_after')}",
             f"Snapshot unchanged on reread: {result.get('snapshot_unchanged', 'not checked')}", ""]
    if analysis:
        lines += ["| Graph | Nodes | Pins | Wires | Exec | Data | Unknown |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for graph in analysis["graphs"]:
            name = graph["graph"].split(":", 1)[-1].replace("|", "\\|")
            lines.append(f"| {name} | " + " | ".join(str(graph[k]) for k in
                         ("nodes", "pins", "wires", "execution", "data", "unknown")) + " |")
        lines += ["", f"Totals: `{json.dumps(analysis['totals'])}`", "",
                  "Pin defaults and all raw Knot segments remain in snapshot.json.",
                  "Use connections.csv/JSON for exact endpoints; function calls require separate interpretation.", ""]
        if analysis["diagnostics"]:
            lines += ["Topology diagnostics:", "", "```json",
                      json.dumps(analysis["diagnostics"], ensure_ascii=False, indent=2), "```", ""]
    if result.get("error"):
        lines += [f"Failure: {result['error']}", ""]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def capture(client: UnrealMcpClient, blueprint: str, out: Path, *, batch_size: int = 100,
            verify_snapshot: bool = False, exec_types: set[str] | None = None) -> int:
    package, obj = asset_paths(blueprint)
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output directory must be new or empty; preserve previous capture evidence")
    out.mkdir(parents=True, exist_ok=True)
    result = {"blueprint": obj, "package": package, "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "coverage": COVERAGE}
    reader, analysis = ReadOnlyCapture(client, out), None
    try:
        result["server"] = client.open().initialize_result or {}
        schemas = {}
        for name in ("EditorAppToolset", "AssetTools", "BlueprintTools"):
            schemas[name] = client.describe_toolset(name)
            save_json(out / "schemas.json", schemas)
        result["dirty_before"] = reader.dirty(package)
        snapshot = reader.snapshot({"refPath": obj}, batch_size)
        save_json(out / "snapshot.json", snapshot)
        analysis = analyze_snapshot(snapshot, exec_types)
        if verify_snapshot:
            again = reader.snapshot({"refPath": obj}, batch_size)
            save_json(out / "snapshot-verification.json", again)
            result["snapshot_unchanged"] = snapshot_fingerprint(snapshot) == snapshot_fingerprint(again)
        result["dirty_after"] = reader.dirty(package)
        failures = []
        if not analysis["valid_returned_topology"]:
            failures.append("Returned topology has unresolved diagnostics; review connections.json")
        if result.get("snapshot_unchanged") is False:
            failures.append("Blueprint changed between snapshots")
        if result["dirty_before"] != result["dirty_after"]:
            failures.append("Dirty flag changed during capture; asset was not saved or cleared")
        if failures:
            result["error"] = "; ".join(failures)
        result["passed"] = not failures
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        client.close()
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_outputs(out, result, analysis)
    return 0 if result["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Absolute Blueprint package or object path")
    parser.add_argument("--out", required=True, type=Path, help="New or empty local output directory")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--verify-snapshot", action="store_true", help="Reread and compare graph/default/link data")
    parser.add_argument("--exec-type", action="append", default=[], help="Additional locale-specific execution type ID")
    parser.add_argument("--expect-project", default=os.environ.get("UE_MCP_PROJECT"),
                        help="Refuse unless the endpoint is served by this project; env UE_MCP_PROJECT")
    parser.add_argument("--new-session", action="store_true", help="Do not resume or keep a saved MCP session")
    args = parser.parse_args()
    client = UnrealMcpClient(
        args.url, args.protocol, args.timeout, cache_dir=default_cache_dir(),
        session_dir=None if args.new_session else default_session_dir(), expected_project=args.expect_project,
    )
    try:
        code = capture(client, args.blueprint, args.out,
                       batch_size=args.batch_size, verify_snapshot=args.verify_snapshot,
                       exec_types=EXEC_TYPES | set(args.exec_type))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"exit_code": code, "report": str(args.out.resolve() / "report.md")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
