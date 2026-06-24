from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import permutation_budget_guard
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def schema_payload() -> dict[str, object]:
    return {
        "tool": "material_parameter_schema",
        "effect": "WingEcho",
        "material_path": "/Game/Materials/M_WingEcho_Master",
        "schema": {
            "parameters": [
                {"name": "UseNoise", "type": "static_switch", "default": True},
                {"name": "UseFresnel", "type": "static_switch", "default": False},
                {"name": "UseDistortion", "type": "static_switch", "default": False},
                {"name": "UseTrailMask", "type": "static_switch", "default": True},
            ]
        },
    }


def expander_payload() -> dict[str, object]:
    return {
        "tool": "static_switch_variant_expander",
        "effect": "WingEcho",
        "material_path": "/Game/Materials/M_WingEcho_Master",
        "switch_parameters": [
            {"name": "UseNoise", "default": True, "allowed_values": [True, False]},
            {"name": "UseFresnel", "default": False, "allowed_values": [False, True]},
        ],
        "summary": {"requested_permutation_count": 4, "emitted_permutation_count": 4},
        "gate": {"switch_space_truncated": False},
    }


def shader_report_payload() -> dict[str, object]:
    return {
        "tool": "shader_permutation_report",
        "groups": [
            {"base_path": "/Game/Materials/M_WingEcho_Master", "switch_signature": ["UseNoise=True"], "instances": ["/Game/A"]},
            {"base_path": "/Game/Materials/M_WingEcho_Master", "switch_signature": ["UseNoise=False"], "instances": ["/Game/B"]},
        ],
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = permutation_budget_guard.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PermutationBudgetGuardTests(unittest.TestCase):
    def test_schema_can_fail_android_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = write_json(root, "schema.json", schema_payload())
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--parameter-schema",
                    str(schema),
                    "--platform",
                    "android",
                    "--strict",
                ]
            )
            self.assertEqual(code, 1)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertFalse(report["gate"]["passed"])
            self.assertTrue(any(item["severity"] == "error" for item in report["findings"]))

    def test_expander_and_realized_report_are_summarized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expander = write_json(root, "expander.json", expander_payload())
            shader_report = write_json(root, "shader.json", shader_report_payload())
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--switch-expander-report",
                    str(expander),
                    "--shader-permutation-report",
                    str(shader_report),
                    "--platform",
                    "pc",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["passed"])
            self.assertEqual(report["summary"]["realized_group_count"], 2)
            self.assertEqual(report["summary"]["requested_permutation_count"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
