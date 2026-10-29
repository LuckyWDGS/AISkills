import json
import unittest

from vfx_delivery import niagara_audit
from vfx_delivery.niagara_material_integration_probe import renderer_props_from_audit


SYSTEM = "/Game/FX/NS_Trail.NS_Trail"


def module(name):
    return {"moduleName": name, "enabled": True, "moduleScript": {"refPath": f"/Niagara/Modules/{name}.{name}"}}


def raw_payload():
    ribbon = {"Material": {"refPath": "/Game/FX/M_Trail.M_Trail"}, "MaterialUserParamBinding": {"parameter": {"name": "None"}},
              "RibbonWidthBinding": {"rootName": "RibbonWidth"}, "bSubImageBlend": True}
    mesh = {"Meshes": [{"mesh": {"refPath": "/Game/FX/SM_Ring.SM_Ring"}}], "bOverrideMaterials": False, "OverrideMaterials": []}
    return {
        "summary": {"emitters": [
            {"emitterName": "Source", "bEnabled": True, "simTarget": "CPUSim", "rendererClasses": []},
            {"emitterName": "Trail", "bEnabled": True, "simTarget": "CPUSim", "rendererClasses": []},
            {"emitterName": "Ring", "bEnabled": False, "simTarget": "CPUSim", "rendererClasses": []},
        ], "userVariables": []},
        "system_data": json.dumps({"bFixedBounds": False, "FixedBounds": {}, "EffectType": None, "WarmupTickCount": 0}),
        "dependencies": {"usedRenderers": [{"refPath": "/Script/Niagara.NiagaraRibbonRendererProperties"}]},
        "emitters": [
            {"summary": {"emitterName": "Source", "bEnabled": True}, "data": json.dumps({"SimTarget": "CPUSim", "IdName": "S1"}),
             "topology": {"particleSpawnScript": {"modules": [module("InitializeParticle")]}, "renderers": []}, "renderers": []},
            {"summary": {"emitterName": "Trail", "bEnabled": True}, "data": json.dumps({"SimTarget": "CPUSim", "IdName": "T1"}),
             "topology": {"particleSpawnScript": {"modules": [module("SpawnParticlesFromOtherEmitter")]},
                          "renderers": [{"rendererIndex": 0}]},
             "renderers": [{"index": 0, "class": {"refPath": "/Script/Niagara.NiagaraRibbonRendererProperties"},
                            "data": json.dumps(ribbon), "mesh_materials": {}}]},
            {"summary": {"emitterName": "Ring", "bEnabled": False}, "data": json.dumps({"SimTarget": "CPUSim"}),
             "topology": {"renderers": [{"rendererIndex": 0}]},
             "renderers": [{"index": 0, "class": "/Script/Niagara.NiagaraMeshRendererProperties", "data": json.dumps(mesh),
                            "mesh_materials": {"/Game/FX/SM_Ring.SM_Ring": [{"refPath": "/Game/FX/M_Ring.M_Ring"}]}}]},
        ],
    }


class ToPayloadTests(unittest.TestCase):
    def setUp(self):
        self.report = niagara_audit.summarize(niagara_audit.to_payload(SYSTEM, raw_payload()))
        self.emitters = {item["name"]: item for item in self.report["emitters"]}

    def test_roles_renderers_and_materials(self):
        trail = self.emitters["Trail"]
        self.assertIn("trail-receiver", trail["roles"])
        self.assertIn("attribute-reader-receiver", trail["roles"])
        self.assertEqual(trail["parsed"]["renderer_classes"], ["RibbonRendererProperties"])
        self.assertEqual(trail["parsed"]["renderer_materials"], ["/Game/FX/M_Trail.M_Trail"])

    def test_mesh_without_override_uses_mesh_slots(self):
        row = self.emitters["Ring"]["versioned_renderer_objects"][0]
        self.assertEqual(row["material_paths"], ["/Game/FX/M_Ring.M_Ring"])
        self.assertEqual(row["material_source"], "mesh-slots")

    def test_warnings(self):
        self.assertIn("Emitter `Ring` is disabled.", self.report["warnings"])
        self.assertIn("System has ribbon/trail emitters but no FixedBounds export text.", self.report["warnings"])

    def test_probe_reads_renderer_props_from_audit(self):
        rows = renderer_props_from_audit(self.report)["renderer_properties"]
        trail = next(row for row in rows if "Trail" in row["renderer_path"])
        self.assertEqual(trail["properties"]["Material"]["text"], "/Game/FX/M_Trail.M_Trail")
        self.assertEqual(trail["properties"]["SubImageBlend"]["text"], "true")
        self.assertIn("RibbonWidth", trail["properties"]["RibbonWidthBinding"]["text"])

    def test_git_bash_rewritten_path_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "MSYS_NO_PATHCONV"):
            niagara_audit.object_path("C:/Program Files/Git/Game/FX/NS_Trail")


if __name__ == "__main__":
    unittest.main()
