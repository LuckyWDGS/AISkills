"""Report-contract tests: real MCP data recorded from UE 5.8.4 drives the audit and its consumers offline."""

import json
from pathlib import Path
import tempfile
import unittest

from unreal_material_tools import delivery_packager, graph_diff_refactor, material_acceptance_gate, material_preview
from unreal_material_tools import material_audit as audit


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def report(name: str) -> dict:
    data = json.loads((FIXTURES / f"mcp-material-{name}.json").read_text(encoding="utf-8"))
    return audit.build_report(data["asset_path"], data["raw"], data["outputs"], data["stats"],
                              instruction_budget=150, sampler_budget=4)


class ReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material, cls.instance = report("M_PrototypeGrid"), report("MI_PrototypeGrid_Gray")

    def test_material_report(self):
        rep = self.material
        self.assertEqual(rep["schema_version"], audit.SCHEMA_VERSION)
        self.assertEqual(rep["material_info"]["num_expressions"], 104)
        self.assertEqual(rep["material_info"]["material_domain"], "MD_Surface")
        self.assertEqual({row["property"] for row in rep["graph_summary"]["output_chains"]}, {"MP_BaseColor", "MP_Roughness"})
        self.assertEqual([node["class_name"] for node in rep["graph_summary"]["dead_nodes"]], ["LocalPosition"])
        self.assertTrue(rep["analysis"]["shader_stats_ready"])
        self.assertEqual(rep["analysis"]["max_instructions"], rep["analysis"]["shader_stats"]["num_pixel_shader_instructions"])
        self.assertIn("instruction_budget", {row["rule_id"] for row in rep["analysis"]["findings"]})

    def test_instance_report(self):
        rep = self.instance
        self.assertTrue(rep["material_info"]["is_material_instance"])
        self.assertEqual([layer["is_base_material"] for layer in rep["instance_chain"]["layers"]], [False, True])
        self.assertEqual(len(rep["instance_chain"]["layers"][0]["override_parameters"]), 7)
        self.assertEqual(rep["stale_overrides"], [])  # RefractionDepthBias is engine-managed, not stale.

    def test_consumers_accept_the_report(self):
        fields = delivery_packager.report_key_fields(self.material)
        self.assertEqual((fields["domain"], fields["dead_nodes"]), ("MD_Surface", 1))
        self.assertGreater(fields["instructions"], 0)
        errors, warnings, _ = material_acceptance_gate._material_audit_counts(
            {"payload": self.material, "path": "audit.json"}, "/Game/LevelPrototyping/Materials/M_PrototypeGrid")
        self.assertEqual((errors, warnings), (1, 1))  # instruction budget error, one dead node
        snapshot = {"material_info": self.material["material_info"], "graph": self.material["raw_graph"],
                    "analysis": self.material["analysis"]}
        self.assertIsInstance(material_preview.build_preview_contract_scan(snapshot, {}), dict)

    def test_gate_counts_each_problem_once(self):
        payload = {
            "material_path": "/Game/M", "material_info": {"path": "/Game/M"},
            "graph_summary": {"dead_nodes": [{"guid": "P", "class_name": "ScalarParameter", "parameter_name": "Unused"}]},
            "stale_overrides": [{"name": "Gone", "instance": "/Game/MI"}],
            "analysis": {"shader_stats": {"ready": False}, "compile_errors": []},
        }
        payload["analysis"]["findings"] = audit.findings(payload, 0, 0)
        self.assertEqual([row["source"] for row in payload["analysis"]["findings"]], ["graph_summary", "stale_overrides"])
        errors, warnings, rows = material_acceptance_gate._material_audit_counts({"payload": payload, "path": "a.json"}, "/Game/M")
        self.assertEqual((errors, warnings), (0, 2))  # one dead parameter + one stale override, not 4
        self.assertEqual({row["rule"] for row in rows}, {"dead_nodes", "stale_overrides"})

    def test_graph_diff_reads_two_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            before, after, out = (Path(folder) / name for name in ("before.json", "after.json", "diff.json"))
            before.write_text(json.dumps(self.material), encoding="utf-8")
            after.write_text(json.dumps(self.instance), encoding="utf-8")
            code = graph_diff_refactor.main(["diff", "--before-audit", str(before), "--after-audit", str(after),
                                             "--root", folder, "--out", str(out)])
            self.assertEqual(code, 0)
            diff = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(diff["diffs"]["graph"]["raw_graph"]["available"])
            nodes = diff["diffs"]["graph"]["raw_graph"]["guid_nodes"]
            # An instance shares its base graph, so node ids must line up exactly.
            self.assertEqual((nodes["added_count"], nodes["removed_count"], nodes["changed_count"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
