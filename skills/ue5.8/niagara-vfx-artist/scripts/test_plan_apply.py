"""niagara_asset_assistant apply: plan operations run against a fake editor that keeps real state."""

from __future__ import annotations

import copy
import json
import unittest

from vfx_delivery.niagara_plan_apply import apply_plan, plan_problems


SYSTEM = "/Game/VFX/NS_Fire"


class FakeEditor:
    """Just enough of AssetTools, MaterialInstanceTools and NiagaraToolset_System, with readable state."""

    def __init__(self) -> None:
        self.assets = {"/Game/Templates/NS_Template", "/Niagara/DefaultAssets/DefaultRibbonMaterial"}
        self.system_data = {"bFixedBounds": False, "FixedBounds": {}, "WarmupTickCount": 0}
        self.emitters = {"Core": {"bIsEnabled": True, "renderers": [{"class": "/Script/Niagara.NiagaraSpriteRendererProperties", "Material": None}]},
                         "Trail": {"bIsEnabled": True, "renderers": []}}
        self.scalars: dict[str, float] = {}
        self.saved: list[str] = []
        self.pie = False
        self.fail_tool = ""
        self.closed = False

    def pie_running(self) -> bool:
        return self.pie

    def close(self) -> None:
        self.closed = True

    def call_resolved_tool(self, toolset: str, tool: str, args: dict) -> dict:
        if tool == self.fail_tool:
            from vfx_delivery.mcp import builtin_mcp
            raise builtin_mcp().McpError(f"{tool} exploded")
        return {"returnValue": getattr(self, tool)(**args)}

    # AssetTools
    def exists(self, path):
        return path.split(".")[0] in self.assets

    def create_folder(self, path):
        return True

    def duplicate(self, path, new_path):
        if path not in self.assets:
            return False
        self.assets.add(new_path)
        return True

    def save_assets(self, asset_paths):
        self.saved.extend(asset_paths)
        return True

    # MaterialInstanceTools
    def create(self, folder_path, asset_name, parent):
        self.assets.add(f"{folder_path}/{asset_name}")
        return {"refPath": f"{folder_path}/{asset_name}.{asset_name}"}

    def set_scalar_parameter(self, instance, name, value):
        self.scalars[name] = value

    def get_scalar_parameter(self, instance, name):
        return self.scalars.get(name, 0.0)

    # NiagaraToolset_System
    def GetSystemSummary(self, system):
        return {"emitters": [{"emitterName": name} for name in self.emitters]}

    def GetSystemData(self, system):
        return {"propertyValues": json.dumps(self.system_data)}

    def SetSystemData(self, system, systemData):
        values = json.loads(systemData["propertyValues"])
        self.system_data.update(values)
        if "FixedBounds" in values:
            self.system_data["FixedBounds"] = {**values["FixedBounds"], "isValid": True}

    def GetEmitterTopology(self, emitterRef):
        renderers = self.emitters[emitterRef["emitterName"]]["renderers"]
        return {"renderers": [{"rendererIndex": index, "rendererClass": {"refPath": row["class"]}} for index, row in enumerate(renderers)]}

    def AddRenderer(self, newRendererLocation, rendererClass):
        renderers = self.emitters[newRendererLocation["emitterName"]]["renderers"]
        renderers.append({"class": rendererClass, "Material": None})
        return {"rendererIndex": len(renderers) - 1, "rendererClass": {"refPath": rendererClass}}

    def renderer(self, ref):
        return self.emitters[ref["emitterName"]]["renderers"][ref["rendererIndex"]]

    def SetRendererData(self, renderer, rendererData):
        values = json.loads(rendererData["propertyValues"])
        if "Material" in values:  # UE hands references back with its own casing
            values["Material"] = {"refPath": values["Material"].replace("Ribbon", "RIbbon", 1)}
        self.renderer(renderer).update(values)

    def GetRendererData(self, rendererRef):
        return {"propertyValues": json.dumps(self.renderer(rendererRef))}

    def SetEmitterData(self, emitter, emitterData):
        self.emitters[emitter["emitterName"]].update(json.loads(emitterData["propertyValues"]))

    def GetEmitterData(self, emitterRef):
        return {"propertyValues": json.dumps({"bIsEnabled": self.emitters[emitterRef["emitterName"]]["bIsEnabled"]})}


def plan(*operations: dict) -> dict:
    return {"tool": "niagara_asset_assistant", "effect_name": "Fire", "target_system": SYSTEM, "operations": list(operations)}


FULL = plan(
    {"op": "duplicate_asset", "source": "/Game/Templates/NS_Template", "target": SYSTEM},
    {"op": "set_niagara_system_props", "system_path": SYSTEM, "fixed_bounds": "-10,-10,0,10,10,40", "warmup_tick_count": 2},
    {"op": "create_material_instance", "parent": "/Game/M/M_Fire", "target": "/Game/VFX/MI_Fire",
     "params": [{"name": "Intensity", "type": "Scalar", "value": "3.5"}]},
    {"op": "add_ribbon_renderer", "emitter_name": "Trail", "material_path": "/Niagara/DefaultAssets/DefaultRibbonMaterial",
     "facing_mode": "Screen", "width_segmentation_count": "2"},
    {"op": "patch_renderer_material", "emitter_name_contains": ["core"], "renderer_class_contains": ["SpriteRenderer"],
     "material_path": "/Game/VFX/MI_Fire"},
    {"op": "set_emitter_enabled_in_system", "emitter_name": "Core", "enabled": False},
    {"op": "save_assets", "asset_paths": [SYSTEM, "/Game/VFX/MI_Fire"]},
)


class PlanApplyTests(unittest.TestCase):
    def test_dry_run_needs_no_editor_and_lists_routes(self) -> None:
        report = apply_plan(FULL, execute=False)
        self.assertEqual(report["status"], "planned")
        # `enabled` is the value of set_emitter_enabled_in_system, not the plan's skip flag.
        self.assertEqual({row["status"] for row in report["operations"]}, {"planned"})
        self.assertIn("SetRendererData", report["operations"][3]["route"])

    def test_execute_applies_every_operation_with_readback(self) -> None:
        editor = FakeEditor()
        report = apply_plan(FULL, execute=True, connect=lambda: editor)
        self.assertEqual(report["status"], "applied", json.dumps(report["operations"], indent=1)[:2000])
        self.assertEqual(editor.system_data["FixedBounds"]["max"], {"x": 10.0, "y": 10.0, "z": 40.0})
        self.assertEqual(editor.scalars, {"Intensity": 3.5})
        trail = editor.emitters["Trail"]["renderers"][0]
        self.assertEqual((trail["FacingMode"], trail["WidthSegmentationCount"]), ("Screen", 2))
        self.assertEqual(editor.emitters["Core"]["renderers"][0]["Material"], {"refPath": "/Game/VFX/MI_Fire.MI_Fire"})
        self.assertFalse(editor.emitters["Core"]["bIsEnabled"])
        self.assertEqual(report["saved"], [SYSTEM, "/Game/VFX/MI_Fire"])
        self.assertTrue(editor.closed)

    def test_a_failure_stops_the_plan_and_nothing_is_saved(self) -> None:
        editor = FakeEditor()
        editor.fail_tool = "AddRenderer"
        report = apply_plan(FULL, execute=True, connect=lambda: editor)
        statuses = [row["status"] for row in report["operations"]]
        self.assertEqual(report["status"], "failed")
        self.assertEqual(statuses, ["ok", "ok", "ok", "error", "skipped", "skipped", "skipped"])
        self.assertIn("AddRenderer exploded", report["operations"][3]["error"])
        self.assertEqual((editor.saved, report["saved"]), ([], []))

    def test_unmatched_renderer_is_an_error_unless_noop_is_allowed(self) -> None:
        missing = {"op": "patch_renderer_material", "emitter_name": "Core", "renderer_class_contains": ["Mesh"], "material_path": "/Game/M"}
        report = apply_plan(plan(missing), execute=True, connect=FakeEditor)
        self.assertIn("no renderer matches", report["operations"][0]["error"])
        report = apply_plan(plan({**missing, "allow_noop": True}), execute=True, connect=FakeEditor)
        self.assertEqual(report["operations"][0]["status"], "noop")

    def test_existing_targets_are_reused_only_when_asked(self) -> None:
        editor = FakeEditor()
        editor.assets.add(SYSTEM)
        duplicate = {"op": "duplicate_asset", "source": "/Game/Templates/NS_Template", "target": SYSTEM}
        self.assertIn("already exists", apply_plan(plan(duplicate), execute=True, connect=lambda: editor)["operations"][0]["error"])
        reused = apply_plan(plan({**duplicate, "reuse_if_exists": True}), execute=True, connect=lambda: copy.deepcopy(editor))
        self.assertEqual(reused["operations"][0]["status"], "reused")

    def test_unsafe_or_unrouted_operations_refuse_the_whole_plan(self) -> None:
        bad = plan({"op": "remove_emitter_from_system", "emitter_name": "Core"}, {"op": "set_u_property_export"},
                   {"op": "toolset_add_module"})
        problems = plan_problems(bad)
        self.assertEqual(len(problems), 3)
        report = apply_plan(bad, execute=True, connect=FakeEditor)
        self.assertEqual(report["status"], "refused")

    def test_pie_blocks_execution(self) -> None:
        editor = FakeEditor()
        editor.pie = True
        report = apply_plan(FULL, execute=True, connect=lambda: editor)
        self.assertEqual(report["status"], "refused")
        self.assertIn("Play-In-Editor", report["problems"][0])


if __name__ == "__main__":
    unittest.main()
