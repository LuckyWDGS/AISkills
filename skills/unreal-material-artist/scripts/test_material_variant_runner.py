from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_variant_runner
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
                {
                    "name": "OpacityBoost",
                    "type": "scalar",
                    "default": 1.0,
                    "range": {"min": 0.0, "max": 4.0},
                    "regression_participation": True,
                },
                {
                    "name": "Tint",
                    "type": "vector",
                    "default": {"r": 0.5, "g": 0.8, "b": 1.0, "a": 1.0},
                    "regression_participation": True,
                },
                {
                    "name": "UseNoise",
                    "type": "static_switch",
                    "default": True,
                    "regression_participation": True,
                },
            ]
        },
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_variant_runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialVariantRunnerTests(unittest.TestCase):
    def test_runner_emits_variant_spec_and_skips_static_switches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = write_json(root, "schema.json", schema_payload())
            code, stdout, stderr = run_tool(["--root", str(root), "--parameter-schema", str(schema), "--markdown"])
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["variant_count"], 5)
            self.assertTrue(Path(report["material_instance_batch_spec"]).exists())
            self.assertTrue(any(item["reason"] == "unsupported_for_material_instance_batch" for item in report["skipped_parameters"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
