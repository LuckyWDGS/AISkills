"""Report-contract tests: real MCP data recorded from UE 5.8.4 drives the audit and its consumers offline."""

import json
from pathlib import Path
import unittest

from vfx_delivery import delivery_package, niagara_audit
from vfx_delivery.niagara_material_integration_probe import collect_renderer_evidence, renderer_props_from_audit


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class NiagaraReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads((FIXTURES / "mcp-niagara-NS_JumpPad.json").read_text(encoding="utf-8"))
        cls.report = niagara_audit.build_report(data["system_path"], data["raw"])

    def test_report(self):
        rep = self.report
        self.assertEqual(rep["schema_version"], niagara_audit.SCHEMA_VERSION)
        self.assertEqual([emitter["name"] for emitter in rep["emitters"]], ["Glow_Base", "Bands", "Spores"])
        spores = rep["emitters"][2]
        self.assertEqual(spores["parsed"]["sim_target"], "GPUComputeSim")
        self.assertIn("ScaleColor", spores["parsed"]["function_names"])
        self.assertEqual(rep["warnings"], [])
        self.assertIn("/Script/Niagara.NiagaraDataInterfaceCurve", rep["system_dependencies"]["usedDataInterfaces"])

    def test_mesh_renderers_report_mesh_slot_materials(self):
        glow = self.report["emitters"][0]["versioned_renderer_objects"]
        mesh = next(row for row in glow if row["class_name"] == "NiagaraMeshRendererProperties")
        self.assertEqual(mesh["material_source"], "mesh-slots")
        self.assertEqual(mesh["material_paths"], ["/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/M_GradientGlow.M_GradientGlow"])

    def test_delivery_package_helpers(self):
        rep = self.report
        self.assertEqual(delivery_package.niagara_audit_warning_count(rep), 0)
        self.assertEqual(delivery_package.niagara_audit_system_path(rep), rep["system_path"])
        self.assertIn("MeshRendererProperties", delivery_package.niagara_audit_renderer_classes(rep))
        self.assertTrue(any("M_SimpleGlow" in path for path in delivery_package.niagara_audit_renderer_materials(rep)))
        self.assertEqual(delivery_package.niagara_audit_roles(rep), {"generic"})

    def test_integration_probe_reads_renderer_bindings(self):
        props = renderer_props_from_audit(self.report)
        self.assertEqual(len(props["renderer_properties"]), 5)
        sprite = props["renderer_properties"][0]["properties"]
        self.assertEqual(sprite["Material"]["text"], "/Niagara/DefaultAssets/DefaultSpriteMaterial.DefaultSpriteMaterial")
        self.assertIn("SubImageBlend", sprite)
        rows = collect_renderer_evidence(self.report, props)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["properties"] for row in rows))


if __name__ == "__main__":
    unittest.main()
