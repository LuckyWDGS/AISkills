from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfx_delivery import control_binding_generator, control_preset, control_provenance_check, effect_control_schema, motion_qa, niagara_param_sweep, runtime_control_probe
from vfx_delivery.core import save_json, slugify


class FakeBridgeClient:
    responses: list[object] = []
    scripts: list[str] = []

    def __init__(self, skill_root: Path, project: str | None = None, endpoint: str | None = None, timeout_seconds: int = 120) -> None:
        self.skill_root = skill_root
        self.project = project
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def ping(self) -> dict[str, object]:
        return {"ready": True}

    def exec_json(self, script_text: str, *, no_preflight: bool = False) -> object:
        FakeBridgeClient.scripts.append(script_text)
        if not FakeBridgeClient.responses:
            raise AssertionError("FakeBridgeClient had no queued response.")
        return FakeBridgeClient.responses.pop(0)


def run_tool(module, args: list[str], responses: list[object] | None = None) -> tuple[int, str, str]:
    FakeBridgeClient.responses = list(responses or [])
    FakeBridgeClient.scripts = []
    stdout = StringIO()
    stderr = StringIO()
    patcher = patch.object(module, "BridgeClient", FakeBridgeClient) if hasattr(module, "BridgeClient") else None
    if patcher is not None:
        patcher.start()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = module.main(args)
    finally:
        if patcher is not None:
            patcher.stop()
    return code, stdout.getvalue(), stderr.getvalue()


def write_png(path: Path, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 64), color).save(path)


class EffectControlToolTests(unittest.TestCase):
    def test_effect_control_schema_generate_merges_integration_and_material_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            integration_path = root / "integration.json"
            save_json(
                integration_path,
                {
                    "owner": "animation_notify",
                    "user_parameters": ["User.Intensity", "User.ColorTint"],
                },
            )
            package_path = root / "material-package.json"
            save_json(
                package_path,
                {
                    "material_path": "/Game/VFX/MI_Test",
                    "parameters": [
                        {
                            "name": "EmissiveIntensity",
                            "type": "Scalar",
                            "default": "4.0",
                            "range": "0..10",
                            "owner": "artist/runtime",
                            "purpose": "Glow control",
                        }
                    ],
                },
            )
            code, stdout, stderr = run_tool(
                effect_control_schema,
                [
                    "generate",
                    "--root",
                    str(root),
                    "--effect",
                    "TestEffect",
                    "--integration-plan",
                    str(integration_path),
                    "--material-delivery-package",
                    str(package_path),
                    "--markdown",
                ],
            )
            self.assertEqual(code, 0, stderr)
            out_path = Path(stdout.strip().splitlines()[-1])
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            ids = {item["id"] for item in payload["controls"]}
            self.assertIn("niagara_user_variable:User.Intensity", ids)
            self.assertIn("material_instance_parameter:EmissiveIntensity", ids)
            self.assertEqual(payload["summary"]["control_count"], 3)

    def test_control_preset_set_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            save_json(
                schema_path,
                {
                    "effect_name": "PresetEffect",
                    "controls": [
                        {"id": "niagara_user_variable:User.Intensity", "logical_name": "User.Intensity", "target_name": "User.Intensity"},
                        {"id": "material_instance_parameter:EmissiveIntensity", "logical_name": "EmissiveIntensity", "target_name": "EmissiveIntensity"},
                    ],
                },
            )
            code, _stdout, stderr = run_tool(
                control_preset,
                [
                    "set",
                    "--root",
                    str(root),
                    "--schema",
                    str(schema_path),
                    "--name",
                    "BurstHigh",
                    "--value",
                    'niagara_user_variable:User.Intensity={"value":2.0}',
                    "--value",
                    'EmissiveIntensity={"value":8.0}',
                    "--note",
                    "High burst preset",
                ],
            )
            self.assertEqual(code, 0, stderr)
            code, stdout, stderr = run_tool(
                control_preset,
                ["show", "--root", str(root), "--effect", "PresetEffect", "--name", "BurstHigh"],
            )
            self.assertEqual(code, 0, stderr)
            shown = json.loads(stdout)
            self.assertEqual(shown["notes"], "High burst preset")
            self.assertEqual(shown["values"]["niagara_user_variable:User.Intensity"], '{"value":2.0}')

    def test_control_binding_generator_outputs_setter_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            save_json(
                schema_path,
                {
                    "effect_name": "BindingEffect",
                    "controls": [
                        {
                            "id": "niagara_user_variable:User.Intensity",
                            "logical_name": "User.Intensity",
                            "surface": "niagara_user_variable",
                            "runtime_surface": "niagara_component_variable",
                            "type_name": "Float",
                            "type_object_path": "/Script/CoreUObject.FloatProperty",
                            "driven_by": "runtime",
                            "runtime_tunable": True,
                        },
                        {
                            "id": "material_instance_parameter:EmissiveIntensity",
                            "logical_name": "EmissiveIntensity",
                            "surface": "material_instance_parameter",
                            "runtime_surface": "material_instance_parameter",
                            "type_name": "Scalar",
                            "driven_by": "runtime",
                            "runtime_tunable": True,
                        },
                    ],
                },
            )
            code, stdout, stderr = run_tool(
                control_binding_generator,
                ["--root", str(root), "--schema", str(schema_path), "--markdown"],
            )
            self.assertEqual(code, 0, stderr)
            payload = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            setters = {item["control_id"]: item["setter_call"] for item in payload["bindings"]}
            self.assertIn("set_official_component_variable", setters["niagara_user_variable:User.Intensity"])
            self.assertIn("set_scalar_parameter", setters["material_instance_parameter:EmissiveIntensity"])

    def test_control_provenance_check_uses_live_and_package_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            save_json(
                schema_path,
                {
                    "effect_name": "ProvEffect",
                    "controls": [
                        {"id": "niagara_user_variable:User.Intensity", "surface": "niagara_user_variable", "target_name": "User.Intensity"},
                        {"id": "material_instance_parameter:EmissiveIntensity", "surface": "material_instance_parameter", "target_name": "EmissiveIntensity"},
                    ],
                },
            )
            package_path = root / "material-package.json"
            save_json(package_path, {"parameters": [{"name": "EmissiveIntensity"}]})
            code, stdout, stderr = run_tool(
                control_provenance_check,
                [
                    "--root",
                    str(root),
                    "--schema",
                    str(schema_path),
                    "--system-path",
                    "/Game/VFX/NS_Test",
                    "--material-delivery-package",
                    str(package_path),
                    "--project",
                    "DummyProject",
                ],
                responses=[
                    {
                        "variables": [
                            {
                                "name": "User.Intensity",
                                "type_name": "Float",
                                "type_object_path": "/Script/CoreUObject.FloatProperty",
                                "value_struct_path": "/Script/Niagara.NiagaraFloat",
                                "value_json": '{"value":1.0}',
                                "description": "",
                            }
                        ]
                    }
                ],
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            statuses = {item["control_id"]: item["status"] for item in report["rows"]}
            self.assertEqual(statuses["niagara_user_variable:User.Intensity"], "pass")
            self.assertEqual(statuses["material_instance_parameter:EmissiveIntensity"], "pass")

    def test_motion_qa_compare_reports_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            candidate = root / "candidate"
            write_png(baseline / "000.png", (0, 0, 0, 255))
            write_png(candidate / "000.png", (255, 0, 0, 255))
            code, stdout, stderr = run_tool(
                motion_qa,
                [
                    "--root",
                    str(root),
                    "--baseline-dir",
                    str(baseline),
                    "--candidate-dir",
                    str(candidate),
                    "--markdown",
                ],
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertEqual(report["frame_count"], 1)
            self.assertGreater(report["worst_mean_abs_diff"], 0.0)

    def test_runtime_control_probe_roundtrip_and_visual_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            save_json(
                schema_path,
                {
                    "effect_name": "ProbeEffect",
                    "controls": [
                        {
                            "id": "niagara_user_variable:User.Intensity",
                            "logical_name": "User.Intensity",
                            "target_name": "User.Intensity",
                            "surface": "niagara_user_variable",
                            "runtime_surface": "niagara_component_variable",
                            "type_name": "Float",
                            "type_object_path": "/Script/CoreUObject.FloatProperty",
                            "value_struct_path": "/Script/Niagara.NiagaraFloat",
                            "default_value_json": '{"value":1.0}',
                            "default_value_text": "1.0",
                            "probe_support": "runtime_component_numeric",
                            "suggested_sweep_values": ['{"value":0.5}', '{"value":1.0}', '{"value":2.0}'],
                        }
                    ],
                },
            )
            before_png = root / "before.png"
            after_png = root / "after.png"
            write_png(before_png, (0, 0, 0, 255))
            write_png(after_png, (255, 255, 255, 255))
            code, stdout, stderr = run_tool(
                runtime_control_probe,
                [
                    "--root",
                    str(root),
                    "--schema",
                    str(schema_path),
                    "--control",
                    "User.Intensity",
                    "--system-path",
                    "/Game/VFX/NS_Test",
                    "--project",
                    "DummyProject",
                    "--capture",
                    "--before-png",
                    str(before_png),
                    "--after-png",
                    str(after_png),
                    "--markdown",
                ],
                responses=[
                    {
                        "success": True,
                        "component_path": "/Temp/BeforeComponent",
                        "summary": {"value_json": '{"value":1.0}'},
                        "capture_ok": True,
                    },
                    {
                        "success": True,
                        "component_path": "/Temp/AfterComponent",
                        "summary": {"value_json": '{"value":2.0}'},
                        "capture_ok": True,
                    },
                ],
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["value_roundtrip_passed"])
            self.assertTrue(report["gate"]["visual_change_detected"])
            self.assertTrue(report["gate"]["probe_passed"])
            self.assertEqual(report["image_diff"]["selected_mode"], "center-crop")

    def test_runtime_control_probe_center_roi_catches_small_central_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            save_json(
                schema_path,
                {
                    "effect_name": "ProbeRoiEffect",
                    "controls": [
                        {
                            "id": "niagara_user_variable:User.Intensity",
                            "logical_name": "User.Intensity",
                            "target_name": "User.Intensity",
                            "surface": "niagara_user_variable",
                            "runtime_surface": "niagara_component_variable",
                            "type_name": "Float",
                            "type_object_path": "/Script/CoreUObject.FloatProperty",
                            "value_struct_path": "/Script/Niagara.NiagaraFloat",
                            "default_value_json": '{"value":1.0}',
                            "default_value_text": "1.0",
                            "probe_support": "runtime_component_numeric",
                            "suggested_sweep_values": ['{"value":0.5}', '{"value":1.0}', '{"value":2.0}'],
                        }
                    ],
                },
            )
            before_png = root / "before.png"
            after_png = root / "after.png"
            write_png(before_png, (0, 0, 0, 255))
            write_png(after_png, (0, 0, 0, 255))
            with Image.open(after_png) as image:
                patched = image.copy()
                for x in range(31, 33):
                    for y in range(31, 33):
                        patched.putpixel((x, y), (255, 255, 255, 255))
                patched.save(after_png)
            code, stdout, stderr = run_tool(
                runtime_control_probe,
                [
                    "--root",
                    str(root),
                    "--schema",
                    str(schema_path),
                    "--control",
                    "User.Intensity",
                    "--system-path",
                    "/Game/VFX/NS_Test",
                    "--project",
                    "DummyProject",
                    "--capture",
                    "--before-png",
                    str(before_png),
                    "--after-png",
                    str(after_png),
                    "--min-mean-diff",
                    "0.5",
                    "--roi-scale",
                    "0.25",
                ],
                responses=[
                    {
                        "success": True,
                        "component_path": "/Temp/BeforeComponent",
                        "summary": {"value_json": '{"value":1.0}'},
                        "capture_ok": True,
                    },
                    {
                        "success": True,
                        "component_path": "/Temp/AfterComponent",
                        "summary": {"value_json": '{"value":2.0}'},
                        "capture_ok": True,
                    },
                ],
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertLess(report["image_diff"]["full_frame"]["mean_abs_diff"], 0.5)
            self.assertGreater(report["image_diff"]["selected_region"]["mean_abs_diff"], 0.5)
            self.assertTrue(report["gate"]["visual_change_detected"])

    def test_niagara_param_sweep_builds_contact_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            control_id = "niagara_user_variable:User.Intensity"
            save_json(
                schema_path,
                {
                    "effect_name": "SweepEffect",
                    "controls": [
                        {
                            "id": control_id,
                            "logical_name": "User.Intensity",
                            "target_name": "User.Intensity",
                            "surface": "niagara_user_variable",
                            "runtime_surface": "niagara_component_variable",
                            "type_name": "Float",
                            "type_object_path": "/Script/CoreUObject.FloatProperty",
                            "value_struct_path": "/Script/Niagara.NiagaraFloat",
                            "default_value_json": '{"value":1.0}',
                            "default_value_text": "1.0",
                            "sweep_support": "niagara_numeric_preview_sweep",
                            "suggested_sweep_values": ['{"value":0.5}', '{"value":1.0}'],
                        }
                    ],
                },
            )
            out_dir = root / "sweep"
            stem = slugify(control_id)
            write_png(out_dir / f"{stem}-value-00.png", (10, 10, 10, 255))
            write_png(out_dir / f"{stem}-value-01.png", (240, 240, 240, 255))
            code, stdout, stderr = run_tool(
                niagara_param_sweep,
                [
                    "--root",
                    str(root),
                    "--schema",
                    str(schema_path),
                    "--control",
                    control_id,
                    "--system-path",
                    "/Game/VFX/NS_Test",
                    "--project",
                    "DummyProject",
                    "--out-dir",
                    str(out_dir),
                    "--markdown",
                ],
                responses=[
                    {"success": True, "out_png": str(out_dir / f"{stem}-value-00.png"), "summary": {"value_json": '{"value":0.5}'}},
                    {"success": True, "out_png": str(out_dir / f"{stem}-value-01.png"), "summary": {"value_json": '{"value":1.0}'}},
                ],
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertEqual(report["value_count"], 2)
            self.assertTrue(Path(report["contact_sheet_png"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
