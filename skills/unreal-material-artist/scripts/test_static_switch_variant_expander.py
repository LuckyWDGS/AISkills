from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import static_switch_variant_expander
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
                {"name": "OpacityBoost", "type": "scalar", "default": 1.0, "range": {"min": 0.0, "max": 4.0}},
                {"name": "UseNoise", "type": "static_switch", "default": True, "range": {"allowed": [True, False]}},
                {"name": "UseFresnel", "type": "static_switch", "default": False},
            ]
        },
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = static_switch_variant_expander.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class StaticSwitchVariantExpanderTests(unittest.TestCase):
    def test_expander_crosses_tiers_with_switch_permutations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = write_json(root, "schema.json", schema_payload())
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--parameter-schema",
                    str(schema),
                    "--tiers",
                    "default,gameplay-safe",
                    "--max-permutations",
                    "8",
                    "--markdown",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["switch_parameter_count"], 2)
            self.assertEqual(report["summary"]["requested_permutation_count"], 4)
            self.assertEqual(report["summary"]["variant_count"], 8)
            self.assertTrue(Path(report["material_instance_batch_spec"]).exists())
            params = report["variants"][0]["params"]
            self.assertTrue(any(item["type"] == "static_switch" for item in params))

    def test_expander_caps_large_switch_space(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = write_json(root, "schema.json", schema_payload())
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--parameter-schema",
                    str(schema),
                    "--tiers",
                    "default",
                    "--max-permutations",
                    "2",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["switch_space_truncated"])
            self.assertEqual(report["summary"]["emitted_permutation_count"], 2)
            self.assertEqual(report["summary"]["variant_count"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
