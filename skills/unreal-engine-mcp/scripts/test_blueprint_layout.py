"""blueprint_layout and blueprint_geometry on synthetic graphs: lanes, data trees, branch rows, lint-clean output."""

import copy
import unittest

import blueprint_geometry as geo
import blueprint_layout as layout
import blueprint_lint as lint
import blueprint_normalize as normalize

BP = "/Game/T/BP_T.BP_T"
G = "Fn"
IN, OUT = "EGPD_Input", "EGPD_Output"


def path(name, graph=G):
    return f"{BP}:{graph}.{name}"


class Graph:
    """Tiny builder: nodes with named pins, links added afterwards on both ends."""

    def __init__(self, graph=G):
        self.graph, self.nodes = graph, {}

    def add(self, name, type_id, inputs=(), outputs=()):
        p = path(name, self.graph)
        make = lambda n, d, i, t, v: {"name": n, "type_id": t, "value": v, "connected_pins": [],  # noqa: E731
                                      "pin_id": {"node": {"refPath": p}, "direction": d, "index_id": i}}
        self.nodes[name] = {"node": {"refPath": p}, "type_id": type_id, "position": {"x": 0, "y": 0},
                            "input_pins": [make(n, IN, i, t, v) for i, (n, t, v) in enumerate(inputs)],
                            "output_pins": [make(n, OUT, i, t, "") for i, (n, t) in enumerate(outputs)]}
        return self

    def link(self, source, out_pin, target, in_pin):
        out = next(p for p in self.nodes[source]["output_pins"] if p["name"] == out_pin)
        inp = next(p for p in self.nodes[target]["input_pins"] if p["name"] == in_pin)
        out["connected_pins"].append(dict(inp["pin_id"]))
        inp["connected_pins"].append(dict(out["pin_id"]))
        return self

    def infos(self):
        return list(self.nodes.values())


EX = ("execute", "Exec", "")
THEN = ("then", "Exec")


def preview_graph():
    """Entry -> Trace -> SetStart -> Loop(body: AddDot, completed: Place); data trees and a loop element."""
    g = Graph()
    g.add("K2Node_FunctionEntry_0", "|UpdatePreview", outputs=[THEN])
    g.add("K2Node_VariableGet_0", "|GetCamera", outputs=[("Camera", "object")])
    g.add("K2Node_CallFunction_0", "Transformation|GetWorldLocation", inputs=[("self", "object", "")],
          outputs=[("ReturnValue", "vector")])
    g.add("K2Node_CallFunction_1", "Collision|SphereTraceByChannel",
          inputs=[EX, ("Start", "vector", "0, 0, 0"), ("End", "vector", "0, 0, 0"), ("Radius", "real", "8.0"),
                  ("TraceChannel", "enum", "TraceTypeQuery1")],
          outputs=[THEN, ("OutHit", "struct"), ("ReturnValue", "bool")])
    g.add("K2Node_CallFunction_2", "Collision|BreakHitResult", inputs=[("Hit", "struct", "")],
          outputs=[("bBlockingHit", "bool"), ("bInitialOverlap", "bool"), ("Time", "real"), ("Distance", "real"),
                   ("Location", "vector"), ("ImpactPoint", "vector"), ("Normal", "vector"), ("TraceEnd", "vector")])
    g.add("K2Node_VariableSet_0", "|SetStart", inputs=[EX, ("Start", "vector", "0, 0, 0")],
          outputs=[THEN, ("Output_Get", "vector")])
    g.add("K2Node_VariableGet_1", "|GetPoints", outputs=[("Points", "array")])
    g.add("K2Node_MacroInstance_0", "Utilities|Array|ForEachLoop", inputs=[("Exec", "Exec", ""), ("Array", "array", "")],
          outputs=[("LoopBody", "Exec"), ("Array Element", "vector"), ("Array Index", "int"), ("Completed", "Exec")])
    g.add("K2Node_CallFunction_3", "Math|Transform|MakeTransform",
          inputs=[("Location", "vector", "0, 0, 0"), ("Rotation", "rotator", "0, 0, 0"), ("Scale", "vector", "1, 1, 1")],
          outputs=[("ReturnValue", "transform")])
    g.add("K2Node_CallFunction_4", "Components|InstancedStaticMesh|AddInstance",
          inputs=[EX, ("self", "object", ""), ("InstanceTransform", "transform", "")], outputs=[THEN, ("ReturnValue", "int")])
    g.add("K2Node_VariableGet_2", "|GetMarker", outputs=[("Marker", "object")])
    g.add("K2Node_CallFunction_5", "Transformation|SetWorldLocation",
          inputs=[EX, ("self", "object", ""), ("NewLocation", "vector", "0, 0, 0"), ("bSweep", "bool", "false")],
          outputs=[THEN])
    (g.link("K2Node_FunctionEntry_0", "then", "K2Node_CallFunction_1", "execute")
     .link("K2Node_VariableGet_0", "Camera", "K2Node_CallFunction_0", "self")
     .link("K2Node_CallFunction_0", "ReturnValue", "K2Node_CallFunction_1", "Start")
     .link("K2Node_CallFunction_1", "then", "K2Node_VariableSet_0", "execute")
     .link("K2Node_CallFunction_1", "OutHit", "K2Node_CallFunction_2", "Hit")
     .link("K2Node_CallFunction_2", "Location", "K2Node_VariableSet_0", "Start")
     .link("K2Node_VariableSet_0", "then", "K2Node_MacroInstance_0", "Exec")
     .link("K2Node_VariableGet_1", "Points", "K2Node_MacroInstance_0", "Array")
     .link("K2Node_MacroInstance_0", "LoopBody", "K2Node_CallFunction_4", "execute")
     .link("K2Node_MacroInstance_0", "Array Element", "K2Node_CallFunction_3", "Location")
     .link("K2Node_CallFunction_3", "ReturnValue", "K2Node_CallFunction_4", "InstanceTransform")
     .link("K2Node_MacroInstance_0", "Completed", "K2Node_CallFunction_5", "execute")
     .link("K2Node_VariableGet_2", "Marker", "K2Node_CallFunction_5", "self"))
    return g


def placed(infos, plan):
    moved = copy.deepcopy(infos)
    for info in moved:
        x, y = plan["positions"][info["node"]["refPath"]]
        info["position"] = {"x": x, "y": y}
    return {info["node"]["refPath"].rsplit(".", 1)[-1]: info for info in moved}


def lint_findings(nodes, graph=G):
    snapshot = {"blueprint": {"refPath": BP}, "variables": [], "parent": None, "event_dispatchers": [],
                "graphs": [{"graph": {"refPath": f"{BP}:{graph}"}, "node_refs": [n["node"] for n in nodes.values()],
                            "nodes": list(nodes.values())}]}
    return [f for f in lint.lint(snapshot)["findings"] if f["severity"] == "warning"]


def box(nodes, name):
    return geo.estimate_box(nodes[name])


class GeometryTests(unittest.TestCase):
    def test_sizes_follow_pins_and_widgets(self):
        g = preview_graph()
        getter = geo.estimate_size(g.nodes["K2Node_VariableGet_0"])
        trace = geo.estimate_size(g.nodes["K2Node_CallFunction_1"])
        self.assertEqual(getter[1], geo.COMPACT_HEIGHT)
        self.assertGreater(trace[0], 300)                 # long title and enum dropdown
        self.assertGreater(trace[1], getter[1] * 5)
        folded = geo.estimate_size(g.nodes["K2Node_CallFunction_2"])
        self.assertLess(folded[1], geo.HEADER + geo.ROW * 8)  # Break shows few pins until expanded

    def test_pin_offsets_grow_down_the_node(self):
        trace = preview_graph().nodes["K2Node_CallFunction_1"]
        offsets = [geo.pin_offset(trace, name, False) for name in ("execute", "Start", "End", "Radius", "TraceChannel")]
        self.assertEqual(offsets, sorted(offsets))
        self.assertLess(geo.pin_offset(trace, "then", True), geo.pin_offset(trace, "ReturnValue", True))

    def test_segment_hits_box(self):
        self.assertTrue(geo.segment_hits_box((0, 50), (300, 50), (100, 0, 100, 100)))
        self.assertFalse(geo.segment_hits_box((0, 150), (300, 150), (100, 0, 100, 100)))


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.graph = preview_graph()
        self.plan = layout.plan_layout(self.graph.infos())
        self.nodes = placed(self.graph.infos(), self.plan)

    def test_planned_graph_is_lint_clean(self):
        self.assertEqual(lint_findings(self.nodes), [])
        self.assertEqual(self.plan["leftovers"], [])

    def test_exec_lane_runs_left_to_right_on_one_row(self):
        lane = ["K2Node_FunctionEntry_0", "K2Node_CallFunction_1", "K2Node_VariableSet_0", "K2Node_MacroInstance_0",
                "K2Node_CallFunction_5"]
        xs = [self.nodes[n]["position"]["x"] for n in lane]
        self.assertEqual(xs, sorted(xs))
        self.assertEqual({self.nodes[n]["position"]["y"] for n in lane}, {0})

    def test_data_nodes_sit_left_of_and_below_their_consumer(self):
        for source, consumer in [("K2Node_CallFunction_0", "K2Node_CallFunction_1"), ("K2Node_VariableGet_0", "K2Node_CallFunction_0"),
                                 ("K2Node_CallFunction_2", "K2Node_VariableSet_0"), ("K2Node_CallFunction_3", "K2Node_CallFunction_4")]:
            sx, sy, sw, _ = box(self.nodes, source)
            cx, cy, _, _ = box(self.nodes, consumer)
            self.assertLessEqual(sx + sw, cx, (source, consumer))
            self.assertGreaterEqual(sy, cy + layout.EXEC_CLEAR - layout.GRID, (source, consumer))

    def test_loop_body_drops_below_and_completed_continues(self):
        loop = box(self.nodes, "K2Node_MacroInstance_0")
        body = box(self.nodes, "K2Node_CallFunction_4")
        place = box(self.nodes, "K2Node_CallFunction_5")
        self.assertGreater(body[1], loop[1] + loop[3])
        self.assertGreater(body[0], loop[0] + loop[2])
        self.assertEqual(place[1], loop[1])
        # The Completed pin sits low on the loop node; the marker getter stays below that exec wire.
        self.assertGreater(box(self.nodes, "K2Node_VariableGet_2")[1],
                           geo.pin_offset(self.nodes["K2Node_MacroInstance_0"], "Completed", True))

    def test_entries_stack_as_modules(self):
        g = preview_graph()
        g.graph = "EventGraph"
        events = Graph("EventGraph")
        events.add("K2Node_Event_0", "Events|BeginPlay", outputs=[THEN])
        events.add("K2Node_Event_1", "Events|Tick", outputs=[THEN])
        events.add("K2Node_CallFunction_0", "Development|PrintString", inputs=[EX, ("InString", "string", "Hello")], outputs=[THEN])
        events.add("K2Node_CallFunction_1", "Development|PrintString", inputs=[EX, ("InString", "string", "Tick")], outputs=[THEN])
        events.link("K2Node_Event_0", "then", "K2Node_CallFunction_0", "execute").link("K2Node_Event_1", "then", "K2Node_CallFunction_1", "execute")
        plan = layout.plan_layout(events.infos(), {"K2Node_Event_1": 0, "K2Node_Event_0": 1})
        tick, begin = (plan["positions"][path(n, "EventGraph")] for n in ("K2Node_Event_1", "K2Node_Event_0"))
        self.assertEqual(tick, [0, 0])
        self.assertGreater(begin[1], layout.MODULE_GAP)
        self.assertEqual(len(plan["modules"]), 2)


class LintWiringTests(unittest.TestCase):
    def test_backward_data_and_wires_through_nodes_are_flagged(self):
        nodes = placed(preview_graph().infos(), layout.plan_layout(preview_graph().infos()))
        nodes["K2Node_CallFunction_0"]["position"] = {"x": 4000, "y": 400}          # data source right of its consumer
        for name, x in (("K2Node_VariableGet_0", 0), ("K2Node_VariableGet_1", 0), ("K2Node_VariableGet_2", 0)):
            nodes[name]["position"] = {"x": x, "y": 30}                             # getters on the exec line
        rules = {f["rule"] for f in lint_findings(nodes)}
        self.assertIn("backward_data_wire", rules)
        self.assertIn("wire_through_node", rules)


def chain_graph():
    """Entry -> A -> B -> C; Speed getter -> Double (pure) feeds A and C; A.Value is read by C; SET B output feeds C."""
    g = Graph()
    g.add("K2Node_FunctionEntry_0", "|Fn", outputs=[THEN])
    g.add("K2Node_VariableGet_0", "|GetSpeed", outputs=[("Speed", "real")])
    g.add("K2Node_PromotableOperator_0", "Math|Float|Multiply", inputs=[("A", "real", ""), ("B", "real", "2.0")],
          outputs=[("ReturnValue", "real")])
    g.add("K2Node_CallFunction_0", "Game|A", inputs=[EX, ("In", "real", "0.0")], outputs=[THEN, ("Value", "real")])
    g.add("K2Node_VariableSet_0", "|SetSpeed", inputs=[EX, ("Speed", "real", "0.0")], outputs=[THEN, ("Output_Get", "real")])
    g.add("K2Node_CallFunction_1", "Game|C", inputs=[EX, ("In", "real", "0.0"), ("Prev", "real", "0.0"), ("Set", "real", "0.0")],
          outputs=[THEN])
    (g.link("K2Node_FunctionEntry_0", "then", "K2Node_CallFunction_0", "execute")
     .link("K2Node_CallFunction_0", "then", "K2Node_VariableSet_0", "execute")
     .link("K2Node_VariableSet_0", "then", "K2Node_CallFunction_1", "execute")
     .link("K2Node_VariableGet_0", "Speed", "K2Node_PromotableOperator_0", "A")
     .link("K2Node_PromotableOperator_0", "ReturnValue", "K2Node_CallFunction_0", "In")
     .link("K2Node_PromotableOperator_0", "ReturnValue", "K2Node_CallFunction_1", "In")
     .link("K2Node_CallFunction_0", "Value", "K2Node_CallFunction_1", "Prev")
     .link("K2Node_VariableSet_0", "Output_Get", "K2Node_CallFunction_1", "Set"))
    return g


class NormalizeTests(unittest.TestCase):
    def test_shared_pure_splits_downstream_first(self):
        found = normalize.next_shared_pure(chain_graph().infos())
        self.assertEqual(normalize.short(found[0]), "K2Node_PromotableOperator_0")   # not its getter input
        self.assertEqual({normalize.short(o) for o in found[1]}, {"K2Node_CallFunction_0", "K2Node_CallFunction_1"})

    def test_single_owner_graph_has_nothing_to_split(self):
        self.assertIsNone(normalize.next_shared_pure(preview_graph().infos()))

    def test_set_outputs_and_exec_skips_are_found(self):
        infos = chain_graph().infos()
        self.assertEqual([v for _, _, v in normalize.set_output_links(infos)], ["Speed"])
        skips = normalize.exec_output_skips(infos)
        self.assertIn({"node": "K2Node_CallFunction_0", "pin": "Value", "read_by": "K2Node_CallFunction_1"}, skips)
        self.assertNotIn("K2Node_VariableSet_0", {s["node"] for s in skips})   # SET -> next node is adjacent


if __name__ == "__main__":
    unittest.main()
