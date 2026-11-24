"""blueprint_lint on synthetic snapshots: layout, debug leftovers, logging and Chinese annotation rules."""

import unittest

import blueprint_lint as lint

BP = "/Game/T/BP_T.BP_T"


def pin(node, name, direction, index, type_id="Exec", value="", links=()):
    return {"name": name, "type_id": type_id, "value": value,
            "pin_id": {"node": {"refPath": node}, "direction": direction, "index_id": index},
            "connected_pins": [{"node": {"refPath": n}, "direction": d, "index_id": i} for n, d, i in links]}


def node(graph, name, type_id, x, y, inputs=(), outputs=()):
    path = f"{BP}:{graph}.{name}"
    return {"node": {"refPath": path}, "type_id": type_id, "position": {"x": x, "y": y},
            "input_pins": [pin(path, *spec) for spec in inputs], "output_pins": [pin(path, *spec) for spec in outputs]}


def ref(graph, name):
    return f"{BP}:{graph}.{name}"


def snapshot(*graphs, variables=()):
    return {"blueprint": {"refPath": BP}, "variables": list(variables), "parent": None, "event_dispatchers": [],
            "graphs": [{"graph": {"refPath": f"{BP}:{name}"}, "node_refs": [n["node"] for n in nodes], "nodes": nodes}
                       for name, nodes in graphs]}


IN, OUT = "EGPD_Input", "EGPD_Output"


def clean_event_graph():
    g = "EventGraph"
    return (g, [
        node(g, "K2Node_Event_0", "事件|BeginPlay", 0, 0,
             outputs=[("then", OUT, 0, "Exec", "", [(ref(g, "K2Node_CallFunction_0"), IN, 0)])]),
        node(g, "K2Node_CallFunction_0", "Development|PrintString", 400, 0,
             inputs=[("execute", IN, 0, "Exec", "", [(ref(g, "K2Node_Event_0"), OUT, 0)]),
                     ("bPrintToScreen", IN, 1, "bool", "false"), ("bPrintToLog", IN, 2, "bool", "true")]),
    ])


class LayoutTests(unittest.TestCase):
    def test_clean_graph_passes(self):
        report = lint.lint(snapshot(clean_event_graph()),
                           comments=[{"graph": "EventGraph", "text": "【初始化】【BP.T.Init】开始时打印", "members": ["K2Node_Event_0", "K2Node_CallFunction_0"]}],
                           categories={})
        self.assertTrue(report["passed"], report["findings"])

    def test_backward_exec_overlap_and_long_getter_wires(self):
        g = "EventGraph"
        nodes = [
            node(g, "K2Node_Event_0", "事件|BeginPlay", 1200, 0,
                 outputs=[("then", OUT, 0, "Exec", "", [(ref(g, "K2Node_CallFunction_0"), IN, 0)])]),
            node(g, "K2Node_CallFunction_0", "Utilities|DoThing", 0, 0,
                 inputs=[("execute", IN, 0, "Exec", "", [(ref(g, "K2Node_Event_0"), OUT, 0)]),
                         ("Target", IN, 1, "object", "", [(ref(g, "K2Node_VariableGet_0"), OUT, 0)])]),
            node(g, "K2Node_CallFunction_1", "Utilities|Other", 2600, 1400,
                 inputs=[("Target", IN, 0, "object", "", [(ref(g, "K2Node_VariableGet_0"), OUT, 0)])]),
            node(g, "K2Node_VariableGet_0", "|GetMesh", -200, 300,
                 outputs=[("Mesh", OUT, 0, "object", "", [(ref(g, "K2Node_CallFunction_0"), IN, 1),
                                                          (ref(g, "K2Node_CallFunction_1"), IN, 0)])]),
            node(g, "K2Node_CallFunction_2", "Utilities|Stacked", 10, 10),
        ]
        rules = {item["rule"] for item in lint.lint(snapshot((g, nodes)))["findings"]}
        self.assertTrue({"backward_exec", "long_data_wire", "getter_fanout", "node_overlap"} <= rules, rules)

    def test_debug_draw_and_screen_print_are_flagged(self):
        g = "UpdatePreview"
        nodes = [
            node(g, "K2Node_FunctionEntry_0", "|UpdatePreview", 0, 0),
            node(g, "K2Node_CallFunction_0", "游戏|PredictProjectilePathByTraceChannel", 300, 0,
                 inputs=[("DrawDebugType", IN, 0, "enum", "ForDuration")]),
            node(g, "K2Node_CallFunction_1", "调试|DrawDebugSphere", 800, 0),
            node(g, "K2Node_CallFunction_2", "Development|PrintString", 1200, 0,
                 inputs=[("bPrintToScreen", IN, 0, "bool", "true"), ("bPrintToLog", IN, 1, "bool", "true")]),
        ]
        findings = lint.lint(snapshot((g, nodes)))["findings"]
        self.assertEqual(sum(item["rule"] == "debug_draw" for item in findings), 2)
        self.assertIn("screen_print", {item["rule"] for item in findings})
        self.assertNotIn("no_logging", {item["rule"] for item in findings})


class AnnotationTests(unittest.TestCase):
    def test_functions_entries_frames_and_categories(self):
        g = "ReleaseThrow"
        function = (g, [node(g, "K2Node_FunctionEntry_0", "|ReleaseThrow", 0, 0)])
        comments = [
            {"graph": "EventGraph", "text": "Init without Chinese", "members": ["K2Node_Event_0"]},
            {"graph": "EventGraph", "text": "【打印】说明但没有模块编号，而且标题写得非常非常长以至于在编辑器里会换行并与下一个注释框的标题叠在一起",
             "members": ["K2Node_CallFunction_0", "K2Node_Event_0"]},
        ]
        report = lint.lint(snapshot(clean_event_graph(), function), comments=comments,
                           categories={"bHeld": "抛物线投掷|运行时", "Speed": "Default"})
        rules = [item["rule"] for item in report["findings"]]
        for rule in ("function_without_description", "frame_not_chinese", "frame_without_module_id",
                     "frame_title_too_long", "frame_overlap", "variable_without_category"):
            self.assertIn(rule, rules)
        self.assertFalse(report["passed"])

    def test_annotations_are_skipped_without_comment_data(self):
        report = lint.lint(snapshot(clean_event_graph()))
        self.assertFalse(report["checked"]["annotations"])
        self.assertNotIn("entry_without_frame", {item["rule"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main()
