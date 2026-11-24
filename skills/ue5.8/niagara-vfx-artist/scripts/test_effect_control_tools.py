from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image

from vfx_delivery import control_binding_generator, control_preset, control_provenance_check, effect_control_schema, motion_qa
from vfx_delivery.core import save_json


def run_tool(module, args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = module.main(args)
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
            audit_path = root / "niagara-audit.json"
            save_json(audit_path, {
                "tool": "niagara_audit", "system_path": "/Game/VFX/NS_Test",
                "user_variables": [{
                    "name": "User.Intensity", "description": "",
                    "type": {"classStructOrEnum": {"refPath": "/Script/Niagara.NiagaraFloat"}},
                    "defaultValue": {"struct": {"refPath": "/Script/Niagara.NiagaraFloat"}, "value": 1.0},
                }],
            })
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
                    "--niagara-audit",
                    str(audit_path),
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
