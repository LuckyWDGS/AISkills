"""Topology and read-only capture regressions; no Unreal editor required."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from inspect_blueprint import (
    INPUT, OUTPUT, ReadOnlyCapture, analyze_snapshot, asset_paths, capture,
    pin_ref, snapshot_fingerprint,
)


GRAPH = "/Game/Test.Test:EventGraph"


def node(name, kind="Call", count=1, pin_type="float"):
    path = GRAPH + "." + name
    return {"node": {"refPath": path}, "type_id": kind, "position": {"x": 0, "y": 0},
            **{field: [{"pin_id": pin_ref((path, direction, i)), "name": "same name",
                        "value": "0", "type_id": pin_type, "connected_pins": []}
                       for i in range(count)] for field, direction in
               (("input_pins", INPUT), ("output_pins", OUTPUT))}}


def wire(a, b, out_index=0, in_index=0):
    src, dst = a["output_pins"][out_index], b["input_pins"][in_index]
    src["connected_pins"].append(copy.deepcopy(dst["pin_id"]))
    dst["connected_pins"].append(copy.deepcopy(src["pin_id"]))


def snapshot(*nodes):
    return {"blueprint": {"refPath": "/Game/Test.Test"}, "graphs": [
        {"graph": {"refPath": GRAPH}, "node_refs": [n["node"] for n in nodes], "nodes": list(nodes)}]}


class TopologyTests(unittest.TestCase):
    def test_fanout_merge_and_parallel_same_named_pins(self):
        a, b, c = (node(s, count=2) for s in ("A", "B", "C"))
        wire(a, b)
        wire(a, b, 1, 1)
        wire(a, c)
        wire(c, b)
        data = snapshot(a, b, c)
        saved = copy.deepcopy(data)
        result = analyze_snapshot(data)
        self.assertTrue(result["valid_returned_topology"])
        self.assertEqual(result["totals"]["wires"], 4)
        self.assertEqual(result["totals"]["data"], 4)
        self.assertEqual(data, saved)
        self.assertEqual(len({(json.dumps(e["source"]["pin_id"], sort_keys=True),
                               json.dumps(e["target"]["pin_id"], sort_keys=True)) for e in result["edges"]}), 4)

    def test_reroute_chain_cycle_keeps_all_segments(self):
        a, b, c = node("A"), node("K2Node_Knot_1", "Knot"), node("K2Node_Knot_2", "Knot")
        wire(a, b)
        wire(b, c)
        wire(c, a)
        result = analyze_snapshot(snapshot(a, b, c))
        self.assertTrue(result["valid_returned_topology"])
        self.assertEqual(result["totals"]["wires"], 3)
        self.assertEqual(result["totals"]["nodes"], 3)

    def test_dangling_and_one_sided_links_are_retained(self):
        a, b = node("A"), node("B")
        wire(a, b)
        b["input_pins"][0]["connected_pins"].clear()
        a["output_pins"][0]["connected_pins"].append(pin_ref((GRAPH + ".Missing", INPUT, 0)))
        result = analyze_snapshot(snapshot(a, b))
        self.assertFalse(result["valid_returned_topology"])
        self.assertEqual(result["totals"]["wires"], 2)
        self.assertEqual(result["totals"]["unknown"], 1)
        self.assertEqual({d["code"] for d in result["diagnostics"]}, {"missing_endpoint", "one_sided_link"})
        self.assertFalse(result["graphs"][0]["input_output_sets_equal"])

    def test_duplicate_pin_wrong_direction_and_missing_readback(self):
        a = node("A")
        a["input_pins"].append(copy.deepcopy(a["input_pins"][0]))
        a["output_pins"][0]["connected_pins"].append(copy.deepcopy(a["output_pins"][0]["pin_id"]))
        data = snapshot(a)
        data["graphs"][0]["node_refs"].append({"refPath": GRAPH + ".Omitted"})
        result = analyze_snapshot(data)
        self.assertEqual({d["code"] for d in result["diagnostics"]},
                         {"duplicate_pin_id", "same_direction_link", "node_readback_mismatch"})

    def test_localized_execution_and_endpoint_mismatch(self):
        a, b = node("A", pin_type="执行"), node("B", pin_type="Exec")
        wire(a, b)
        result = analyze_snapshot(snapshot(a, b))
        self.assertEqual(result["totals"]["execution"], 1)
        self.assertTrue(result["valid_returned_topology"])
        b["input_pins"][0]["type_id"] = "float"
        result = analyze_snapshot(snapshot(a, b))
        self.assertEqual(result["totals"]["unknown"], 1)
        self.assertEqual(result["diagnostics"][0]["code"], "execution_type_mismatch")
        a["output_pins"][0]["type_id"] = b["input_pins"][0]["type_id"] = "Exécution"
        self.assertEqual(analyze_snapshot(snapshot(a, b), {"Exécution"})["totals"]["execution"], 1)

    def test_snapshot_compare_ignores_order_but_detects_defaults(self):
        original = snapshot(node("A"), node("B"))
        other = copy.deepcopy(original)
        other["graphs"][0]["nodes"].reverse()
        self.assertEqual(snapshot_fingerprint(original), snapshot_fingerprint(other))
        other["graphs"][0]["nodes"][0]["input_pins"][0]["value"] = "42"
        self.assertNotEqual(snapshot_fingerprint(original), snapshot_fingerprint(other))

    def test_missing_pin_type_is_not_silently_classified_as_data(self):
        a, b = node("A"), node("B")
        wire(a, b)
        del a["output_pins"][0]["type_id"]
        with self.assertRaisesRegex(ValueError, "metadata schema changed"):
            analyze_snapshot(snapshot(a, b))


class FakeClient:
    def __init__(self, *, pie=False, dirty=True, fail=False, change=False):
        self.calls, self.pie, self.was_dirty = [], pie, dirty
        self.fail, self.change, self.reads, self.closed = fail, change, 0, False
        a, b = node("A"), node("B")
        wire(a, b)
        self.nodes = [a, b]

    def open(self):
        self.initialize_result = {"protocolVersion": "test"}
        return self

    def describe_toolset(self, name):
        return {"name": name, "tools": []}

    def close(self):
        self.closed = True

    def call_resolved_tool(self, toolset, tool, arguments):
        self.calls.append((toolset, tool, arguments))
        if tool == "IsPIERunning":
            value = self.pie
        elif tool == "is_dirty":
            value = self.was_dirty
        elif tool == "get_parent":
            value = {"refPath": "/Script/Engine.Character"}
        elif tool in {"list_variables", "list_event_dispatchers"}:
            value = []
        elif tool == "list_graphs":
            value = [{"refPath": GRAPH}]
        elif tool == "find_nodes":
            value = [n["node"] for n in self.nodes]
        elif tool == "get_node_infos":
            if self.fail:
                raise RuntimeError("simulated official tool failure")
            self.reads += 1
            value = copy.deepcopy(self.nodes)
            if self.change and self.reads > 1:
                value[0]["input_pins"][0]["value"] = "changed"
        else:
            raise AssertionError(f"Unexpected editor operation: {toolset}.{tool}")
        return {"content": [{"type": "text", "text": json.dumps({"returnValue": value})}]}


class CaptureTests(unittest.TestCase):
    def test_official_only_preserves_existing_dirty_asset(self):
        client = FakeClient(dirty=True)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "capture"
            self.assertEqual(capture(client, "/Game/Test", out, verify_snapshot=True), 0)
            result = json.loads((out / "result.json").read_text())
            self.assertTrue(result["dirty_before"])
            self.assertTrue(result["dirty_after"])
            self.assertTrue(result["snapshot_unchanged"])
            self.assertTrue((out / "connections.csv").exists())
        self.assertTrue(client.closed)
        self.assertEqual({t for _, t, _ in client.calls}, {
            "IsPIERunning", "is_dirty", "get_parent", "list_variables", "list_event_dispatchers",
            "list_graphs", "find_nodes", "get_node_infos"})
        self.assertEqual([a for _, t, a in client.calls if t == "is_dirty"],
                         [{"asset_path": "/Game/Test"}] * 2)

    def test_pie_is_preserved_and_no_dirty_query_is_sent(self):
        client = FakeClient(pie=True)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "capture"
            self.assertEqual(capture(client, "/Game/Test.Test", out), 1)
            self.assertIn("PIE is running", (out / "result.json").read_text())
        self.assertEqual([t for _, t, _ in client.calls], ["IsPIERunning"])

    def test_failure_keeps_evidence_without_retry_or_fallback(self):
        client = FakeClient(fail=True)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "capture"
            self.assertEqual(capture(client, "/Game/Test", out), 1)
            calls = json.loads((out / "calls.json").read_text())
            self.assertIn("simulated official tool failure", calls[-1]["error"])
            self.assertFalse((out / "connections.csv").exists())
            self.assertFalse(json.loads((out / "result.json").read_text())["passed"])
        self.assertEqual(sum(t == "get_node_infos" for _, t, _ in client.calls), 1)

    def test_changed_snapshot_fails_and_never_saves(self):
        client = FakeClient(change=True)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "capture"
            self.assertEqual(capture(client, "/Game/Test", out, verify_snapshot=True), 1)
            self.assertFalse(json.loads((out / "result.json").read_text())["snapshot_unchanged"])
            self.assertTrue((out / "snapshot-verification.json").exists())

    def test_allowlist_and_existing_evidence_are_enforced(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaisesRegex(ValueError, "allowlist"):
                ReadOnlyCapture(client, out).read("BlueprintTools", "compile_blueprint", {})
            (out / "keep.txt").write_text("existing evidence")
            with self.assertRaisesRegex(ValueError, "new or empty"):
                capture(client, "/Game/Test", out)
            self.assertEqual((out / "keep.txt").read_text(), "existing evidence")
        self.assertFalse(client.calls)

    def test_package_and_object_paths(self):
        self.assertEqual(asset_paths("/Game/Test"), ("/Game/Test", "/Game/Test.Test"))
        self.assertEqual(asset_paths("/Game/Test.Test"), ("/Game/Test", "/Game/Test.Test"))
        for value in ("Test", "/Game/Test.Test_C", "/Game/Test.Test:EventGraph", "Blueprint'/Game/Test.Test'"):
            with self.assertRaises(ValueError):
                asset_paths(value)


if __name__ == "__main__":
    unittest.main()
