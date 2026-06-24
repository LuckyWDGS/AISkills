from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_parameter_schema
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def complete_contract_payload() -> dict[str, object]:
    return {
        "tool": "material_contract",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "parameters": [
            {
                "name": "OpacityBoost",
                "type": "scalar",
                "default": 1.0,
                "unit": "multiplier",
                "range": {"min": 0.0, "max": 4.0},
                "runtime_owner": "Niagara",
                "writable_by": ["Niagara", "MID"],
                "artist_tunable": True,
                "regression_participation": True,
            }
        ],
    }


def minimal_contract_payload() -> dict[str, object]:
    return {
        "tool": "material_contract",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "parameters": [{"name": "OpacityBoost", "type": "scalar", "default": 1.0}],
    }


def audit_payload() -> dict[str, object]:
    return {
        "tool": "material_audit",
        "material_path": "/Game/Materials/M_WingEcho_RibbonTrail",
        "material_info": {
            "scalar_parameters": [{"name": "OpacityBoost", "param_type": "Scalar", "value": 1.0}],
            "vector_parameters": [],
            "texture_parameters": [],
            "static_switch_parameters": [],
        },
    }


def run_schema(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_parameter_schema.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialParameterSchemaTests(unittest.TestCase):
    def test_complete_contract_schema_passes_require_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = write_json(root, "contract.json", complete_contract_payload())
            audit = write_json(root, "audit.json", audit_payload())
            code, stdout, stderr = run_schema(
                ["--root", str(root), "--contract", str(contract), "--audit-report", str(audit), "--require-complete"]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["schema_complete"])
            self.assertEqual(report["schema"]["parameters"][0]["runtime_owner"], "Niagara")

    def test_require_complete_blocks_minimal_name_only_parameter_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = write_json(root, "contract.json", minimal_contract_payload())
            code, stdout, stderr = run_schema(["--root", str(root), "--contract", str(contract), "--require-complete"])
            self.assertEqual(code, 2)
            self.assertIn("incomplete", stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertFalse(report["gate"]["schema_complete"])
            self.assertIn("missing_contract_fields", {item["rule"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
