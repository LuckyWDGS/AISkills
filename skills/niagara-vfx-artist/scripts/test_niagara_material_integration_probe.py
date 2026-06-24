from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfx_delivery.core import save_json
from vfx_delivery.niagara_material_integration_probe import build_findings, build_report


def audit_fixture(*, material: str = "/Game/VFX/MI_Flame", bounds: bool = True, rich_bindings: bool = True) -> dict:
    renderer_text = ""
    if rich_bindings:
        renderer_text = (
            "SubImageSize=(X=8,Y=8) SubImageIndexBinding=Particles.SubImageIndex "
            "ColorBinding=Particles.Color DynamicMaterialBinding=Particles.DynamicMaterialParameter "
            "SortMode=ViewDepth"
        )
    return {
        "tool": "niagara_audit",
        "system_path": "/Game/VFX/NS_Flame",
        "system_properties": {
            "FixedBounds": {"text": "(Min=(X=-100,Y=-100,Z=-100),Max=(X=100,Y=100,Z=100))" if bounds else ""},
        },
        "emitters": [
            {
                "name": "FlameSprite",
                "properties": {
                    "RendererProperties": {"text": renderer_text},
                    "SpawnScriptProps": {"text": "Particles.Color Particles.DynamicMaterialParameter"},
                    "UpdateScriptProps": {"text": ""},
                    "EmitterSpawnScriptProps": {"text": ""},
                    "EmitterUpdateScriptProps": {"text": ""},
                    "EventHandlerScriptProps": {"text": ""},
                    "SimulationStages": {"text": ""},
                    "GraphSource": {"text": ""},
                    "GPUComputeScript": {"text": ""},
                },
                "parsed": {
                    "renderer_classes": ["SpriteRendererProperties"],
                    "renderer_materials": [material],
                    "renderer_objects": [],
                    "versioned_renderer_objects": [],
                    "function_names": ["InitializeParticle"],
                    "data_interface_classes": [],
                    "data_interface_bindings": [],
                },
            }
        ],
    }


class NiagaraMaterialIntegrationProbeTests(unittest.TestCase):
    def test_sorting_properties_count_as_live_sorting_evidence(self) -> None:
        expectations = {
            "carrier": "sprite",
            "material_path": "/Game/VFX/MI_Flame",
            "expects_subuv": False,
            "expects_particle_color": False,
            "expects_dynamic_parameter": False,
            "expects_ribbon_width": False,
            "expects_sorting": True,
            "expects_bounds": True,
        }
        renderer_rows = [
            {
                "classes": ["NiagaraSpriteRendererProperties"],
                "materials": ["/Game/VFX/MI_Flame"],
                "properties": {
                    "SortMode": {"success": True, "text": "None"},
                    "CustomSortingBinding": {"success": True, "text": "(RootName=\"NormalizedAge\")"},
                },
                "text_blob": "",
            }
        ]
        findings = build_findings(expectations, audit_fixture(rich_bindings=False), renderer_rows, strict_unknown=False)
        sorting_rules = {(item["rule"], item["severity"]) for item in findings}
        self.assertIn(("sorting", "ok"), sorting_rules)
        self.assertNotIn(("sorting_unproven", "warning"), sorting_rules)

    def test_ready_sprite_subuv_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit.json"
            contract_path = root / "contract.json"
            save_json(audit_path, audit_fixture())
            save_json(
                contract_path,
                {
                    "tool": "material_contract",
                    "effect": "Flame",
                    "carrier": {
                        "renderer": "sprite",
                        "uv_expectations": "SubUV flipbook 8x8",
                        "particle_inputs": ["ParticleColor", "DynamicParameter"],
                        "dynamic_parameters": ["EmissiveBoost"],
                        "sort_or_depth_notes": "Sort by view depth.",
                    },
                    "material": {"blend_mode": "Additive"},
                    "textures": [{"name": "T_Flame_VFX", "role": "flipbook", "grid": "8x8"}],
                },
            )
            args = type(
                "Args",
                (),
                {
                    "root": str(root),
                    "effect": "",
                    "system_path": "",
                    "niagara_audit": str(audit_path),
                    "material_contract": str(contract_path),
                    "material_delivery_package": "",
                    "preview_report": "",
                    "material_path": "/Game/VFX/MI_Flame",
                    "carrier": "",
                    "subuv_grid": "",
                    "particle_input": [],
                    "dynamic_parameter": [],
                    "require_particle_color": False,
                    "require_dynamic_parameter": False,
                    "require_subimage_index": False,
                    "require_ribbon_width": False,
                    "require_sorting": False,
                    "no_require_bounds": False,
                    "strict_unknown": False,
                    "fail_on_warning": False,
                    "project": None,
                    "endpoint": None,
                    "timeout": 180,
                    "out": "",
                    "markdown": False,
                    "strict": False,
                },
            )()
            report, _out = build_report(args)
            self.assertTrue(report["gate"]["integration_ready"], json.dumps(report["findings"], indent=2))
            self.assertEqual(report["summary"]["errors"], 0)

    def test_missing_renderer_material_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit.json"
            save_json(audit_path, audit_fixture(material="/Game/VFX/MI_Other", rich_bindings=False))
            args = type(
                "Args",
                (),
                {
                    "root": str(root),
                    "effect": "Flame",
                    "system_path": "",
                    "niagara_audit": str(audit_path),
                    "material_contract": "",
                    "material_delivery_package": "",
                    "preview_report": "",
                    "material_path": "/Game/VFX/MI_Flame",
                    "carrier": "sprite",
                    "subuv_grid": "8x8",
                    "particle_input": ["ParticleColor"],
                    "dynamic_parameter": [],
                    "require_particle_color": True,
                    "require_dynamic_parameter": False,
                    "require_subimage_index": True,
                    "require_ribbon_width": False,
                    "require_sorting": False,
                    "no_require_bounds": False,
                    "strict_unknown": True,
                    "fail_on_warning": False,
                    "project": None,
                    "endpoint": None,
                    "timeout": 180,
                    "out": "",
                    "markdown": False,
                    "strict": False,
                },
            )()
            report, _out = build_report(args)
            self.assertFalse(report["gate"]["integration_ready"])
            self.assertGreater(report["summary"]["errors"], 0)
            rules = {item["rule"] for item in report["findings"] if item["severity"] == "error"}
            self.assertIn("material_binding", rules)
            self.assertIn("subuv_missing", rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
