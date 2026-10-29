import unittest

from unreal_material_tools import material_audit as audit


M = "/Game/M/M_X.M_X:MaterialExpression"


def node(name, inputs=(), **extra):
    return {"id": M + name, "class_name": audit.expression_class(M + name),
            "inputs": [{"input_name": "A", "output_name": "", "source": M + src} for src in inputs], **extra}


class PathTests(unittest.TestCase):
    def test_object_path(self):
        self.assertEqual(audit.object_path("/Game/M/M_X"), "/Game/M/M_X.M_X")
        self.assertEqual(audit.object_path("/Game/M/M_X.M_X"), "/Game/M/M_X.M_X")

    def test_git_bash_rewritten_path_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "MSYS_NO_PATHCONV"):
            audit.object_path("C:/Program Files/Git/Game/M/M_X")

    def test_expression_class_and_refs(self):
        self.assertEqual(audit.expression_class(M + "LinearInterpolate_5"), "LinearInterpolate")
        self.assertEqual(audit.expression_class(M + "TextureSampleParameter2D_12"), "TextureSampleParameter2D")
        self.assertEqual(audit.ref_of({"refPath": "/Game/A"}), "/Game/A")
        self.assertEqual(audit.ref_of("None"), "")
        self.assertEqual(audit.ref_of(None), "")


class GraphTests(unittest.TestCase):
    def test_dead_and_unused_parameter(self):
        nodes = [node("Add_0", ["Constant_0"]), node("Constant_0"),
                 node("ScalarParameter_1", parameterName="Unused"), node("Comment_0")]
        graph = audit.trace_graph(nodes, [{"property": "MP_BaseColor", "source": M + "Add_0", "output_name": ""}])
        self.assertEqual(graph["live_count"], 2)
        self.assertEqual([item["parameter_name"] for item in graph["dead_nodes"]], ["Unused"])

    def test_named_reroute_declarations_stay_live_when_a_usage_is_live(self):
        nodes = [node("Add_0", ["NamedRerouteUsage_0"]), node("NamedRerouteUsage_0"),
                 node("NamedRerouteDeclaration_0", ["Constant_0"]), node("Constant_0")]
        graph = audit.trace_graph(nodes, [{"property": "MP_BaseColor", "source": M + "Add_0", "output_name": ""}])
        self.assertEqual(graph["dead_nodes"], [])

    def test_function_outputs_are_roots(self):
        nodes = [node("FunctionOutput_0", ["Constant_0"]), node("Constant_0"), node("Constant_1")]
        graph = audit.trace_graph(nodes, [])
        self.assertEqual([item["guid"] for item in graph["dead_nodes"]], ["MaterialExpressionConstant_1"])


class FindingTests(unittest.TestCase):
    def test_stale_overrides_skip_engine_managed(self):
        chain = [{"path": "/Game/MI", "overrides": [
            {"name": "Gone", "expression_guid": "24F0A099-4A5F-B333-0BF3-8D8355E1A214"},
            {"name": "RefractionDepthBias", "expression_guid": "00000000-0000-0000-0000-000000000000"},
            {"name": "Kept", "expression_guid": "11111111-0000-0000-0000-000000000000"},
        ]}]
        stale = audit.stale_overrides(chain, {"/Game/M": [{"name": "Kept", "type": "Scalar"}]}, "/Game/M")
        self.assertEqual([item["name"] for item in stale], ["Gone"])

    def test_budgets_only_with_ready_stats(self):
        report = {"graph_summary": {"dead_nodes": []}, "stale_overrides": [],
                  "analysis": {"shader_stats": {"ready": True, "num_pixel_shader_instructions": 300, "num_samplers": 3}}}
        rules = [row["rule_id"] for row in audit.findings(report, 200, 2)]
        self.assertEqual(rules, ["instruction_budget", "sampler_budget"])
        report["analysis"]["shader_stats"] = {"ready": False}
        self.assertEqual(audit.findings(report, 200, 2), [])


if __name__ == "__main__":
    unittest.main()
