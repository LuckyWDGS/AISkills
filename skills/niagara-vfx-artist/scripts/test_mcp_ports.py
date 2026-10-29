"""Offline checks for the Niagara tools ported from UnrealBridge to Epic MCP: their pure planning and report code."""

import json
from pathlib import Path
import unittest

from vfx_delivery import asset_cleanup, delivery_finalize, effect_control_schema, live_asset_verify, niagara_audit


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class LiveAssetVerifyTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((FIXTURES / "mcp-niagara-NS_JumpPad.json").read_text(encoding="utf-8"))
        self.niagara = niagara_audit.build_report(fixture["system_path"], fixture["raw"])
        self.material = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/M_GradientGlow"

    def test_renderer_path_forms(self):
        self.assertEqual(live_asset_verify.split_renderer_path("/Game/FX/NS_X.NS_X:Trail.Renderer"), ("/Game/FX/NS_X", "Trail"))
        self.assertEqual(live_asset_verify.split_renderer_path("/Game/FX/NS_X"), ("/Game/FX/NS_X", ""))

    def test_route_through_instance_parameter(self):
        raw = {"texture_asset_exists": True, "material_exists": True, "material_class": "MaterialInstanceConstant",
               "texture_parameters": [{"name": "Mask", "value": {"refPath": "/Game/T/T_Mask.T_Mask"}}], "dependencies": []}
        payload = live_asset_verify.build_payload("/Game/T/T_Mask", self.material, "/Game/X/NS_JumpPad:Glow_Base", raw, self.niagara)
        self.assertTrue(payload["material_references_target_texture"])
        self.assertTrue(payload["renderer_references_material"])
        self.assertTrue(live_asset_verify.verification_passed({**payload, "source_policy": "ue-only"}))

    def test_base_material_uses_dependencies_and_emitter_filter(self):
        raw = {"texture_asset_exists": True, "material_exists": True, "material_class": "Material",
               "texture_parameters": [{"name": "Mask", "value": ""}], "dependencies": ["/Game/T/T_Mask"]}
        payload = live_asset_verify.build_payload("/Game/T/T_Mask.T_Mask", self.material, "/Game/X/NS_JumpPad:NoSuchEmitter", raw, self.niagara)
        self.assertTrue(payload["material_references_target_texture"])
        self.assertFalse(payload["renderer_exists"])
        self.assertFalse(payload["renderer_references_material"])


class CleanupTests(unittest.TestCase):
    def test_policy(self):
        self.assertTrue(asset_cleanup.classify_ue_asset("/Game/CodexTemp/X/Niagara/NS_Smoke")["safe_delete"])
        self.assertFalse(asset_cleanup.classify_ue_asset("/Game/CodexTemp/X/Niagara/NS_Quarantine")["safe_delete"])
        self.assertIsNone(asset_cleanup.classify_ue_asset("/Game/VFX/Fire/Niagara/NS_Fire"))

    def test_delete_steps_honour_flags_and_safety(self):
        candidates = [
            {"type": "ue-asset", "asset_path": "/Game/CodexTemp/X/Niagara/NS_Smoke", "safe_delete": True},
            {"type": "ue-asset", "asset_path": "/Game/CodexTemp/X/Niagara/NS_Quarantine", "safe_delete": False},
            {"type": "ue-actor", "actor_name": "Preview", "actor_ref": "/Game/Map.Map:PersistentLevel.Preview", "safe_delete": True},
            {"type": "file", "path": "x.tmp", "safe_delete": True},
        ]
        steps = asset_cleanup.build_delete_steps(candidates, actors=False, assets=True)
        self.assertEqual([(step["tool"], step["args"]["path"]) for step in steps], [("delete", "/Game/CodexTemp/X/Niagara/NS_Smoke")])
        self.assertEqual((steps[0]["readback"]["tool"], steps[0]["expect"]), ("exists", False))
        both = asset_cleanup.build_delete_steps(candidates, actors=True, assets=True)
        self.assertEqual([step["tool"] for step in both], ["delete", "remove_from_scene"])


class ControlAndPromotionTests(unittest.TestCase):
    def test_user_variables_from_audit(self):
        summary = effect_control_schema.user_variables_summary({
            "system_path": "/Game/FX/NS_X",
            "user_variables": [{"name": "User.Color", "description": "tint",
                                "type": {"classStructOrEnum": {"refPath": "/Script/CoreUObject.LinearColor"}},
                                "defaultValue": {"struct": {"refPath": "/Script/CoreUObject.LinearColor"}, "value": {"r": 1}}}],
        })
        row = summary["variables"][0]
        self.assertEqual((row["name"], row["type_name"], json.loads(row["value_json"])), ("User.Color", "LinearColor", {"r": 1}))

    def test_promote_steps_skip_blocked_and_save_targets(self):
        mappings = [{"source": "/Game/CodexTemp/NS_A.NS_A", "target": "/Game/VFX/Fire/NS_A.NS_A"},
                    {"source": "/Game/CodexTemp/NS_B", "target": "/Game/VFX/Fire/NS_B"}]
        steps = delivery_finalize.promote_steps(mappings, "duplicate", True, {"/Game/CodexTemp/NS_B": "target asset already exists"})
        self.assertEqual([(step["tool"], step["args"]) for step in steps],
                         [("duplicate", {"path": "/Game/CodexTemp/NS_A", "new_path": "/Game/VFX/Fire/NS_A"}),
                          ("save_assets", {"asset_paths": ["/Game/VFX/Fire/NS_A"]})])
        moves = delivery_finalize.promote_steps(mappings[:1], "move", False, {})
        self.assertEqual([step["tool"] for step in moves], ["move"])


if __name__ == "__main__":
    unittest.main()
